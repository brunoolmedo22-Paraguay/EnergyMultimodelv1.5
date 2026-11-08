"""Contrato canônico por UID: casos positivos, rejeições explícitas (ordem 3A.1, 05_FIXTURES §Rechazos) e
serialização/hash. Sintético/algébrico."""
import dataclasses
import json
from dataclasses import replace

import pytest

from ems_v2 import fixtures as F
from ems_v2.contracts import (ClasseDemanda, CurvaPWL, DispositivoDescarte, EntradaModeloEMS, EstadoBateria,
                              EstadoGerador, PoliticaObjetivo, PoliticaServico, PoliticaTerminal, UIDRecurso,
                              entrada_de_json, hash_entrada, json_canonico, validar_entrada)
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.parameters import Parametro
from ems_v2.provenance import Procedencia
from ems_v2.series import SerieTemporal, alinhar_a_malha
from ems_v2.units import para_canonica

pytestmark = pytest.mark.synthetic_algebraic
P = F.proc("teste")


def cods(e: EntradaModeloEMS, sev=None):
    return validar_entrada(e).codigos(sev)


def base():
    return F.a05_feas()[0]


def test_fixtures_de_referencia_validas():
    for f in (F.a01, F.a02, F.a03, F.a04, F.b01a, F.b01b):
        rel = validar_entrada(f()[0])
        assert rel.aceito, (f.__name__, rel.bloqueantes())
    assert validar_entrada(base()).aceito


def test_convencao_de_sinais_e_fronteira_fixas():
    e = base()
    assert e.fronteira.convencao_potencia == "kW_liquido_no_barramento"
    assert "fronteira_incerta" in cods(replace(e, fronteira=replace(e.fronteira, convencao_potencia="kW_stack")))
    assert "topologia_nao_suportada_3A" in cods(replace(e, fronteira=replace(e.fronteira, topologia="conectada")), "pendente")


def test_uid_duplicado_entre_familias():
    e = base()
    d = replace(e.demandas[0], uid=UIDRecurso("syn-fv"))
    assert "uid_duplicado" in cods(replace(e, demandas=(d,)))


def test_uid_invalido():
    e = base()
    assert "uid_invalido" in cods(replace(e, demandas=(replace(e.demandas[0], uid=UIDRecurso("carga 1")),)))


def test_nan_na_serie_nunca_vira_zero():
    e = base()
    d = replace(e.demandas[0], potencia=replace(e.demandas[0].potencia, valores=(float("nan"),)))
    assert "valor_ausente_ou_nao_finito" in cods(replace(e, demandas=(d,)))


def test_potencia_negativa_e_unidade_inconsistente():
    e = base()
    s = e.renovaveis[0].potencial
    assert "quantidade_negativa" in cods(replace(e, renovaveis=(replace(e.renovaveis[0], potencial=replace(s, valores=(-1.0,))),)))
    assert "unidade_nao_canonica" in cods(replace(e, renovaveis=(replace(e.renovaveis[0], potencial=replace(s, unidade="W")),)))
    assert "unidade_incompativel" in cods(replace(e, renovaveis=(replace(e.renovaveis[0], potencial=replace(s, unidade="kWh")),)))


def test_potencia_bruta_misturada_ao_barramento_rejeitada():
    e = base()
    s = e.renovaveis[0].potencial
    assert "potencia_fora_do_barramento" in cods(
        replace(e, renovaveis=(replace(e.renovaveis[0], potencial=replace(s, fronteira="stack_bruta")),)))
    assert "fronteira_incerta" in cods(replace(e, renovaveis=(replace(e.renovaveis[0], potencial=replace(s, fronteira=None)),)))


def test_cadeia_bruto_normalizado_da_serie():
    e = base()
    s = e.demandas[0].potencia
    ok = replace(s, valores_brutos=(10000.0,), unidade_bruta="W", transformacoes=(para_canonica(10000, "W")[2],))
    assert validar_entrada(replace(e, demandas=(replace(e.demandas[0], potencia=ok),))).aceito
    ruim = replace(ok, valores_brutos=(9000.0,))
    assert "cadeia_transformacao_inconsistente" in cods(replace(e, demandas=(replace(e.demandas[0], potencia=ruim),)))


def test_serie_de_instantes_rejeita_duplicata_ordem_passo_e_fuso():
    kw = dict(grandeza="potencia", unidade="kW", semantica="media_intervalo", procedencia=P, fronteira="barramento_liquido")
    ok = SerieTemporal.de_instantes(["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z"], [1, 2], **kw)
    assert ok.passo_s == 60 and ok.inicio_utc.startswith("2026-01-01T00:00:00")
    casos = {
        "instante_duplicado": ["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z", "2026-01-01T00:01:00Z"],
        "instantes_nao_monotonos": ["2026-01-01T00:01:00Z", "2026-01-01T00:00:00Z", "2026-01-01T00:02:00Z"],
        "passo_irregular": ["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z"],
        "fuso_ambiguo": ["2026-01-01T00:00:00", "2026-01-01T00:01:00", "2026-01-01T00:02:00"],
    }
    for cod, inst in casos.items():
        with pytest.raises(ContratoInvalido) as ex:
            SerieTemporal.de_instantes(inst, [1, 2, 3], **kw)
        assert cod in ex.value.codigos, cod


def test_periodo_final_duplicado_rejeitado():
    """Último período repetido no arquivo de origem (instante final duplicado)."""
    inst = [f"2026-01-01T00:{i:02d}:00Z" for i in range(60)] + ["2026-01-01T00:59:00Z"]
    with pytest.raises(ContratoInvalido) as ex:
        SerieTemporal.de_instantes(inst, [60.0] * 61, grandeza="potencia", unidade="kW", semantica="media_intervalo",
                                   procedencia=P, fronteira="barramento_liquido")
    assert "instante_duplicado" in ex.value.codigos


def test_semantica_resolucao_cobertura_e_causalidade():
    e = base()
    s = e.demandas[0].potencia
    m = e.malha

    def c(serie):
        return {x.codigo for x in alinhar_a_malha(serie, m, "s")[1]}
    assert "amostra_instantanea_como_media" in c(replace(s, semantica="amostra_instantanea"))
    assert "resolucao_incompativel" in c(replace(s, passo_s=60))
    assert "cobertura_insuficiente" in c(replace(s, inicio_utc="2026-01-01T00:30:00+00:00"))
    assert "serie_desalinhada" in c(replace(s, inicio_utc="2025-12-31T23:30:00+00:00", valores=(10.0, 10.0)))
    assert "previsao_nao_causal" in c(replace(s, emissao_utc="2026-01-01T00:10:00+00:00"))
    assert "emissao_nao_declarada" in c(replace(s, emissao_utc=None))
    assert "semantica_nao_declarada" in cods(replace(e, demandas=(replace(e.demandas[0], potencia=replace(s, semantica="")),)))


def test_fonte_sem_procedencia_rejeitada():
    e = base()
    s = e.demandas[0].potencia
    assert "sem_procedencia" in cods(replace(e, demandas=(replace(e.demandas[0], potencia=replace(s, procedencia=None)),)))
    assert "procedencia_nao_declarada" in cods(replace(e, politica_terminal=replace(
        e.politica_terminal, procedencia=Procedencia("nao_declarado", "x"))))


def _bat(e, **kw):
    return replace(e, baterias=(replace(e.baterias[0], **kw),))


def test_bateria_eficiencia_capacidade_soc():
    e = base()
    assert "eficiencia_fora_do_dominio" in cods(_bat(e, eta_carga=Parametro(0.0, "1", P)))
    assert "eficiencia_fora_do_dominio" in cods(_bat(e, eta_descarga=Parametro(1.2, "1", P)))
    assert "capacidade_nula" in cods(_bat(e, capacidade_kWh=Parametro(0.0, "kWh", P)))
    assert "limites_soc_incoerentes" in cods(_bat(e, soc_min=Parametro(0.8, "1", P), soc_max=Parametro(0.2, "1", P)))
    assert "parametro_ausente" in cods(_bat(e, eta_carga=Parametro(None, "1", P)))
    assert "hipotese_autodescarga_nao_declarada" in cods(_bat(e, hipotese_autodescarga=""))
    assert "parametro_ausente" in cods(_bat(e, hipotese_autodescarga="lambda_declarado"))
    assert "autodescarga_contraditoria" in cods(_bat(e, autodescarga_1_h=Parametro(0.01, "1/h", P)))


def test_estado_inicial_bateria():
    e = base()
    uid = e.baterias[0].uid
    fora = replace(e, baterias=(replace(e.baterias[0], soc_min=Parametro(0.6, "1", P)),))
    assert "soc_inicial_fora_dos_limites" in cods(fora)
    assert "estado_inicial_ausente" in cods(replace(e, estados_baterias=()))
    dup = EstadoBateria(uid, Parametro(50.0, "kWh", P))
    assert "estado_inicial_duplicado" in cods(replace(e, estados_baterias=(dup, dup)))
    orfao = EstadoBateria(UIDRecurso("syn-outro"), Parametro(50.0, "kWh", P))
    assert "estado_orfao" in cods(replace(e, estados_baterias=e.estados_baterias + (orfao,)))
    pct = EstadoBateria(uid, Parametro(50.0, "kWh", P), Parametro(50.0, "%", P))
    assert "soc_em_percentual_sem_conversao" in cods(replace(e, estados_baterias=(pct,)))
    incoerente = EstadoBateria(uid, Parametro(50.0, "kWh", P), Parametro(0.6, "1", P))
    assert "soc_e_energia_inconsistentes" in cods(replace(e, estados_baterias=(incoerente,)))
    coerente = EstadoBateria(uid, Parametro(50.0, "kWh", P), Parametro.de_bruto(50, "%", P))
    assert validar_entrada(replace(e, estados_baterias=(coerente,))).aceito
    maior = EstadoBateria(uid, Parametro(150.0, "kWh", P))
    assert "energia_maior_que_capacidade" in cods(replace(e, estados_baterias=(maior,)))


def test_demanda_critica_e_interrompivel():
    e = base()
    d = e.demandas[0]
    chi = F.serie("fracao_interrompivel", "1", [0.5], 60, "teste")
    assert "carga_critica_com_interrupcao" in cods(replace(e, demandas=(replace(d, fracao_interrompivel=chi),)))
    assert "fracao_interrompivel_ausente" in cods(replace(e, demandas=(replace(d, criticidade="interrompivel"),)))
    interr = replace(d, criticidade="interrompivel", fracao_interrompivel=chi)
    assert "interrupcao_ignorada_em_servico_duro" in cods(replace(e, demandas=(interr,)), "aviso")
    degr = replace(e, demandas=(interr,), politica_servico=PoliticaServico("degradado", P))
    assert "interrupcao_sem_autorizacao" in cods(degr)
    ok = replace(degr, politica_servico=PoliticaServico("degradado", P, "Autorização documentada (teste)"))
    assert validar_entrada(ok).aceito
    assert "degradado_sem_carga_interrompivel" in cods(replace(e, politica_servico=PoliticaServico("degradado", P, "x")))


def test_politicas_terminal_e_objetivo():
    e = base()
    assert "terminal_nenhuma_sem_justificativa" in cods(replace(e, politica_terminal=PoliticaTerminal("nenhuma", " ", P)))
    assert "politica_terminal_nao_suportada_3A" in cods(
        replace(e, politica_terminal=PoliticaTerminal("referencia_suave", "x", P)), "pendente")
    assert "termo_objetivo_proibido" in cods(
        replace(e, politica_objetivo=PoliticaObjetivo(("indisponibilidade_como_curtailment",), P)))
    assert "termo_objetivo_nao_suportado_3A" in cods(
        replace(e, politica_objetivo=PoliticaObjetivo(("combustivel_h2",), P)), "pendente")
    sem_custo = replace(e, politica_objetivo=PoliticaObjetivo(("curtailment_operacional",), P))
    assert "parametro_ausente" in cods(sem_custo)       # c^curt nunca é presumido
    assert "lexicografica_nao_suportada_3A" in cods(replace(e, politica_objetivo=PoliticaObjetivo((), P, lexicografica=True)))


def test_a05_opt_registrado_mas_nao_executavel_no_3A():
    rel = validar_entrada(F.a05_opt_entrada())
    assert not rel.aceito and rel.codigos("pendente") == {"termo_objetivo_nao_suportado_3A"}
    assert F.CASOS["A05-OPT"].etapa == "especificacao_3B" and not F.CASOS["A05-OPT"].executado_por_solver


def test_disponibilidade_binaria_e_base_do_potencial():
    e = F.b01b()[0]
    r = e.renovaveis[0]
    frac = replace(r, disponibilidade=replace(r.disponibilidade, serie=replace(r.disponibilidade.serie, valores=(0.5,))))
    assert "disponibilidade_fracionaria_nao_suportada" in cods(replace(e, renovaveis=(frac,)), "pendente")
    duas = replace(r, base_potencial="utilizavel_apos_disponibilidade",
                   disponibilidade=replace(r.disponibilidade, serie=replace(r.disponibilidade.serie, valores=(0.0,))))
    assert "disponibilidade_aplicada_duas_vezes" in cods(replace(e, renovaveis=(duas,)))
    assert "base_potencial_nao_declarada" in cods(replace(e, renovaveis=(replace(r, base_potencial=""),)))


def _com_gerador(**kw):
    g, st, _ = F.a06_gerador(1, 60)
    g = replace(g, **{k: v for k, v in kw.items() if k in g.__dataclass_fields__})
    st = kw.get("estado", st)
    e = base()
    return replace(e, geradores=(g,), estados_geradores=(st,))


def test_gerador_estado_inicial_declarado_nunca_inferido():
    assert validar_entrada(_com_gerador()).aceito
    uid = UIDRecurso("syn-fc")
    assert "estado_inicial_ausente" in cods(_com_gerador(estado=EstadoGerador(uid, None, Parametro(15.0, "kW", P))))
    assert "off_com_potencia" in cods(_com_gerador(estado=EstadoGerador(uid, False, Parametro(15.0, "kW", P))))
    assert "on_fora_do_dominio" in cods(_com_gerador(estado=EstadoGerador(uid, True, Parametro(5.0, "kW", P))))
    assert "parametro_ausente" in cods(_com_gerador(estado=EstadoGerador(uid, True, Parametro(None, "kW", P))))


def test_gerador_curva_variante_e_b04():
    assert "multimodo_nao_suportado_3A" in cods(_com_gerador(variante_commitment="multimodo"), "pendente")
    assert "curva_h2_ausente" in cods(_com_gerador(curva_h2=None), "pendente")
    real = CurvaPWL(((10.0, 0.7), (20.0, 1.1)), "real", P)
    assert "pwl_real_requer_certificacao_estatica" in cods(_com_gerador(curva_h2=real), "pendente")
    zero = CurvaPWL(((0.0, 0.0), (10.0, 0.7), (20.0, 1.1)), "sintetica_exata", P)
    assert {"curva_inclui_zero", "curva_abaixo_do_minimo"} <= cods(_com_gerador(curva_h2=zero))
    nao_cresc = CurvaPWL(((20.0, 1.1), (10.0, 0.7)), "sintetica_exata", P)
    assert "curva_nao_crescente" in cods(_com_gerador(curva_h2=nao_cresc))
    assert "limites_potencia_incoerentes" in cods(_com_gerador(p_min_kW=Parametro(30.0, "kW", P)))


def test_descarte_so_com_dispositivo_declarado():
    e = base()
    d = DispositivoDescarte(UIDRecurso("syn-dump"), Parametro(None, "kW", P))
    assert "parametro_ausente" in cods(replace(e, politica_servico=PoliticaServico("duro", P, descarte=d)))


def test_identidade_versoes_e_hashes():
    e = base()
    assert "motor_incompativel" in cods(replace(e, motor_id="legacy_v16"))
    assert "versao_esquema_incompativel" in cods(replace(e, versao_esquema=2))
    assert "hash_fonte_invalido" in cods(replace(e, hashes_fontes={"x": "abc"}))
    assert "identidade_ausente" in cods(replace(e, cenario_uid=""))


def test_json_canonico_ida_e_volta_e_hash_estavel():
    for f in (F.a01, F.a03, F.b01b):
        e = f()[0]
        s = json_canonico(e)
        e2 = entrada_de_json(s)
        assert e2 == e and hash_entrada(e2) == hash_entrada(e) and json_canonico(e2) == s
    g, st, _ = F.a06_gerador(1, 60)
    e = replace(base(), geradores=(g,), estados_geradores=(st,))
    assert entrada_de_json(json_canonico(e)) == e
    e = F.b01b()[0]
    alterado = replace(e, renovaveis=(replace(e.renovaveis[0], custo_curtailment=Parametro(0.6, "R$/kWh", P)),))
    assert hash_entrada(alterado) != hash_entrada(e)


def test_json_rejeita_nan_e_campos_desconhecidos():
    e = base()
    d = replace(e.demandas[0], potencia=replace(e.demandas[0].potencia, valores=(float("nan"),)))
    with pytest.raises(ValueError):
        hash_entrada(replace(e, demandas=(d,)))
    dado = json.loads(json_canonico(e))
    dado["campo_estranho"] = 1
    with pytest.raises(ValueError):
        entrada_de_json(json.dumps(dado))


@pytest.mark.parametrize("cls,campo", [
    (ClasseDemanda, "criticidade"), (SerieTemporal, "semantica"), (EntradaModeloEMS, "politica_terminal"),
    (EntradaModeloEMS, "politica_servico"), (EntradaModeloEMS, "politica_objetivo"), (EstadoGerador, "ligado"),
    (EstadoBateria, "energia_kWh"), (PoliticaServico, "modo"), (PoliticaTerminal, "tipo"),
] + [(F.EspecBateria, c) for c in ("capacidade_kWh", "soc_min", "soc_max", "eta_carga", "eta_descarga",
                                    "p_carga_max_kW", "p_descarga_max_kW", "hipotese_autodescarga")]
  + [(F.PotencialRenovavel, "base_potencial"), (F.EspecGerador, "variante_commitment")])
def test_campos_cientificos_sem_padrao_implicito(cls, campo):
    """Condição C: nenhum parâmetro físico, eficiência, estado inicial ou política tem valor padrão."""
    f = cls.__dataclass_fields__[campo]
    assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
