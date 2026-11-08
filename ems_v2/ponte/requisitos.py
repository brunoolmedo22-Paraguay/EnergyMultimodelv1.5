"""Inventário científico de parâmetros (3C-0 §3.2): o que cada papel do EMS V2 exige e como classificar o que existe.

``REQUISITOS`` é DECLARATIVO (fonte da matriz ``docs/ems_v2/MATRIZ_PARAMETROS_3C0.md``; um teste confere que a
documentação lista todo símbolo). ``classificar_dispositivo`` aplica-o a um dispositivo do instantâneo
(``inventario.DispositivoInventario``) e devolve, por símbolo, uma das cinco classes:

1. ``disponivel_verificavel`` — declarado com procedência rastreável (revisão + caminho no documento);
2. ``derivavel`` — obtido por relação registrada a partir de valores declarados ou de catálogo de referência;
3. ``faltante_necessario`` — ausente (ou apenas SUGERIDO pelo SEEDS2) e exigido ⇒ bloqueia;
4. ``opcional`` — ausente, mas não exigido pela configuração declarada (termo do objetivo inativo etc.);
5. ``sintetico_ensaio`` — de origem sintética: aceito só em contexto de ensaio; em contexto operacional bloqueia.

Nenhum valor ausente é substituído. Requisitos ``futuro_3C1`` (rampas, permanências, partidas) são INFORMADOS, sem
bloquear o 3C-0: o 3C-1 os tornará obrigatórios para o commitment dinâmico.

``fontes`` lista as chaves aceitas no instantâneo. Chaves que NÃO existem no inventário do Piso 1 (p. ex.
``eta_carga``, ``p_carga_barramento_kW``, ``hipotese_autodescarga``, ``custo_*``, ``t_on_min``) são PROPOSTAS de
contrato: hoje só aparecem em inventários sintéticos de ensaio; numa microrrede real ficam ausentes ⇒ faltantes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..diagnostics import Constatacao, ContratoInvalido, aviso, erro, pendente
from ..provenance import Procedencia, Transformacao
from ..units import CONVERSOES, UNIDADES_CANONICAS, para_canonica
from .canonico import sha256
from .inventario import DispositivoInventario, InventarioMicrorrede

CLASSES = {
    "disponivel_verificavel": "Disponível e verificável",
    "derivavel": "Derivável por transformação registrada",
    "faltante_necessario": "Faltante e necessário",
    "opcional": "Opcional (não exigido pela configuração declarada)",
    "sintetico_ensaio": "Sintético — exclusivo para ensaio",
}
OBRIGATORIEDADES = {"obrigatorio": "Sempre exigido para o papel",
                    "condicional": "Exigido só quando a condição declarada está ativa (p. ex. termo do objetivo)",
                    "opcional": "Nunca exigido",
                    "futuro_3C1": "Exigido a partir do 3C-1 (commitment dinâmico); informado no 3C-0"}
NATUREZAS = {"fisico": "Grandeza física", "economico": "Coeficiente econômico", "modelagem": "Opção/identidade de modelo",
             "declaracao": "Hipótese que deve ser declarada (sem valor padrão)", "contagem": "Contagem de unidades"}
CONTEXTOS = {"ensaio": "Ensaio/teste (dados sintéticos permitidos, rotulados)",
             "operacional": "Uso sobre microrrede real (dados sintéticos proibidos)"}


@dataclass(frozen=True)
class RequisitoParametro:
    simbolo: str
    tipos: tuple[str, ...]              # tipos de dispositivo (inventario.TIPOS_DISPOSITIVO)
    descricao: str
    natureza: str
    unidade_canonica: str | None        # None para texto/contagem/declaração
    obrigatoriedade: str
    equacoes: tuple[str, ...]
    fontes: tuple[str, ...] = ()        # chaves aceitas no instantâneo, em ordem de prioridade
    condicao: str | None = None         # p. ex. "termo:throughput_bess"
    severidade_ausencia: str = "erro"   # "erro" (dado faltante) | "pendente" (exige método/capacidade aprovados)
    unidades_equivalentes: tuple[str, ...] = ()   # unidade da fonte semanticamente idêntica à canônica (fator 1)
    nota: str = ""


_R = RequisitoParametro
_V16_IDENT = ("o V1.6 IDENTIFICA este valor a partir de séries simuladas do próprio modelo (ems_integration/fontes.py, "
              "medianas/regressão); o método não está aprovado como fonte de parâmetro do EMS V2")
REQUISITOS: tuple[RequisitoParametro, ...] = (
    # ------------------------------------------------------------------ bateria
    _R("C_b", ("bateria",), "Capacidade energética utilizável do banco", "fisico", "kWh", "obrigatorio",
       ("M06", "M07", "M08"), ("energy_kWh", "energy_kWh_derivada", "energy_kWh_modelo"),
       nota="Prioridade: energia declarada; E = V·Q/1000 a partir do datasheet; energia da parametrização do modelo "
            "científico (célula de referência × Ns × Np)."),
    _R("s_min", ("bateria",), "Limite inferior de SOC (fração)", "fisico", "1", "obrigatorio", ("M08",), ("soc_min_pct",),
       nota="Valor apenas SUGERIDO pelo SEEDS2 (origem 'sugerido') não sustenta limite físico/operacional."),
    _R("s_max", ("bateria",), "Limite superior de SOC (fração)", "fisico", "1", "obrigatorio", ("M08",), ("soc_max_pct",),
       nota="Idem s_min."),
    _R("eta_c", ("bateria",), "Eficiência de carga barramento → energia interna", "fisico", "1", "obrigatorio", ("M07",),
       ("eta_carga",), nota=f"Não existe no inventário; {_V16_IDENT}."),
    _R("eta_d", ("bateria",), "Eficiência de descarga energia interna → barramento", "fisico", "1", "obrigatorio",
       ("M07",), ("eta_descarga",), nota=f"Não existe no inventário; {_V16_IDENT}."),
    _R("Pc_max", ("bateria",), "Potência máxima de carga NO BARRAMENTO", "fisico", "kW", "obrigatorio", ("M06",),
       ("p_carga_barramento_kW",), severidade_ausencia="pendente",
       nota="C·E dá a potência no TERMINAL CC do banco (chave p_carga_terminal_kW, informativa); a conversão de "
            "fronteira terminal → barramento (BND-BESS) não está aprovada (3D)."),
    _R("Pd_max", ("bateria",), "Potência máxima de descarga NO BARRAMENTO", "fisico", "kW", "obrigatorio", ("M06",),
       ("p_descarga_barramento_kW",), severidade_ausencia="pendente", nota="Idem Pc_max (chave informativa p_descarga_terminal_kW)."),
    _R("hipotese_autodescarga", ("bateria",), "Hipótese de autodescarga (α = 1 declarada ou λ)", "declaracao", None,
       "obrigatorio", ("M07",), ("hipotese_autodescarga",), nota="Sem valor padrão (3A)."),
    _R("c_thr", ("bateria",), "Custo de throughput", "economico", "R$/kWh", "condicional", ("M21-v1.1",),
       ("custo_throughput",), condicao="termo:throughput_bess"),
    # ------------------------------------------------------------------ fotovoltaica (arranjo)
    _R("modulo_ref", ("pv_arranjo",), "Módulo FV (catálogo) — entrada do modelo físico", "modelagem", None, "obrigatorio",
       ("M03-v1.1",), ("reference",), nota="Arranjo 'potência declarada' não tem módulo: o modelo físico não o representa."),
    _R("Ns", ("pv_arranjo",), "Módulos em série", "contagem", None, "obrigatorio", ("M03-v1.1",), ("n_series",)),
    _R("Np", ("pv_arranjo",), "Strings em paralelo", "contagem", None, "obrigatorio", ("M03-v1.1",), ("n_parallel",)),
    _R("perdas_sujeira", ("pv_arranjo",), "Perdas por sujeira (fração)", "fisico", "1", "obrigatorio", ("M03-v1.1",),
       ("soiling_pct",), nota="0 % aplicado como hipótese PADRÃO (não declarada) é tratado como sugerido."),
    _R("c_curt", ("pv_arranjo", "eolica"), "Custo de curtailment operacional", "economico", "R$/kWh", "condicional",
       ("M21-CURT",), ("custo_curtailment",), condicao="termo:curtailment_operacional"),
    # ------------------------------------------------------------------ eólica
    _R("turbina_ref", ("eolica",), "Aerogerador (catálogo) — entrada do modelo físico", "modelagem", None, "obrigatorio",
       ("M03-v1.1",), ("reference",)),
    _R("n_turbinas", ("eolica",), "Aerogeradores idênticos no registro", "contagem", None, "obrigatorio", ("M03-v1.1",),
       ("count",)),
    _R("perda_rede_generica", ("eolica",), "Opção de perda genérica do modelo eólico", "modelagem", None, "obrigatorio",
       ("M03-v1.1",), ("apply_grid_loss",)),
    # ------------------------------------------------------------------ PEMFC
    _R("perfil_pemfc", ("pemfc",), "Perfil/dispositivo PEMFC", "modelagem", None, "obrigatorio", ("M10", "M13"),
       ("reference",)),
    _R("n_sistemas", ("pemfc",), "Sistemas PEMFC idênticos no registro", "contagem", None, "obrigatorio", ("M10",),
       ("quantity",)),
    _R("P_max", ("pemfc", "termica"), "Potência máxima líquida no barramento (por unidade)", "fisico", "kW",
       "obrigatorio", ("M10",), ("p_max_liquida_unidade_kW", "pmax_kW"),
       nota="PEMFC: calculada pelo modelo dinâmico de referência (h2_pemfc, perfil aproximado). Térmica: declarada."),
    _R("P_min", ("pemfc", "termica"), "Potência mínima técnica líquida (por unidade, quando ON)", "fisico", "kW",
       "obrigatorio", ("M10",), ("pmin_kW",), nota=f"PEMFC: não existe no inventário; {_V16_IDENT}."),
    _R("curva_h2", ("pemfc",), "Curva q(P_net) de H₂ suprido", "fisico", "kg/h", "obrigatorio", ("M14", "M15", "M16"),
       severidade_ausencia="pendente",
       nota=f"Adenda B04: curva real exige certificação estática; {_V16_IDENT} (curva kg/kWh)."),
    _R("c_H", ("pemfc",), "Preço do hidrogênio", "economico", "R$/kg", "condicional", ("M17",), ("preco_h2",), condicao="termo:combustivel_h2"),
    _R("dinamica_termica", ("termica",), "Dinâmica operacional (pequena unidade geradora)", "modelagem", None,
       "obrigatorio", ("M10",), ("dynamic",)),
    _R("CVU", ("termica",), "Custo variável unitário", "economico", "R$/kWh", "condicional", ("M19",), ("cvu_rs_MWh",),
       condicao="termo:geracao_termica", nota="R$/MWh ÷ 1000 (conversão exata registrada)."),
    _R("rampa", ("pemfc", "termica"), "Rampa máxima", "fisico", "kW/min", "futuro_3C1", ("M11a", "M11b"),
       ("ramp_kW_min",), nota="Ausente NÃO significa rampa ilimitada: o 3C-1 exigirá declaração explícita."),
    _R("t_on_min", ("pemfc", "termica"), "Tempo mínimo em operação", "fisico", "min", "futuro_3C1", ("M12",), ("t_on_min",)),
    _R("t_off_min", ("pemfc", "termica"), "Tempo mínimo em repouso", "fisico", "min", "futuro_3C1", ("M12",), ("t_off_min",)),
    _R("C_SU", ("pemfc", "termica"), "Custo de partida (por evento)", "economico", "R$/evento", "futuro_3C1", ("M21-v1.1",),
       ("startup_cost_rs",), unidades_equivalentes=("R$",),
       nota="Inventário SEEDS2 declara 'Custo de partida' em R$ — por definição, um custo por evento."),
    _R("C_SD", ("pemfc", "termica"), "Custo de parada (por evento)", "economico", "R$/evento", "futuro_3C1", ("M21-v1.1",),
       ("shutdown_cost_rs",)),
    _R("partida_pemfc", ("pemfc",), "Parâmetros de partida (durações/estados intermediários)", "fisico", "s",
       "futuro_3C1", ("M20", "B05"), nota="Decisão D05 pendente (30 s / 600 s não são inferidos do V1.6)."),
)
INDICE = {r.simbolo: r for r in REQUISITOS}


@dataclass(frozen=True)
class ClassificacaoParametro:
    uid: str
    tipo: str
    simbolo: str
    classe: str
    obrigatoriedade: str
    bloqueia: bool
    codigo: str
    mensagem: str
    unidade: str | None = None
    numero: float | None = None              # valor CANÔNICO (convertido), se numérico
    texto: str | None = None
    logico: bool | None = None
    chave_fonte: str | None = None
    origem: str | None = None
    procedencia: Procedencia | None = None
    transformacoes: tuple[Transformacao, ...] = field(default_factory=tuple)
    numero_bruto: float | None = None
    unidade_bruta: str | None = None


@dataclass(frozen=True)
class MatrizParametros:
    microrrede_uid: str
    contexto: str
    termos: tuple[str, ...]
    entradas: tuple[ClassificacaoParametro, ...]

    def de(self, uid: str, simbolo: str) -> ClassificacaoParametro | None:
        return next((c for c in self.entradas if c.uid == uid and c.simbolo == simbolo), None)

    def bloqueantes(self) -> tuple[ClassificacaoParametro, ...]:
        return tuple(c for c in self.entradas if c.bloqueia)


def _condicao_ativa(r: RequisitoParametro, termos: frozenset[str]) -> bool:
    if r.condicao is None:
        return True
    tipo, _, alvo = r.condicao.partition(":")
    return tipo == "termo" and alvo in termos


def _converter(numero: float, unidade_fonte: str, r: RequisitoParametro) -> tuple[float, tuple[Transformacao, ...]]:
    """Fonte → unidade canônica do requisito com conversão EXPLÍCITA (3A ``units``); incompatível ⇒ ``ContratoInvalido``."""
    alvo = r.unidade_canonica
    if alvo is None or unidade_fonte == alvo:
        return float(numero), ()
    if unidade_fonte in r.unidades_equivalentes:
        return float(numero), (Transformacao("reinterpretacao_declarada", f"{unidade_fonte} ≡ {alvo} ({r.nota})",
                                             unidade_fonte, alvo, "1"),)
    if unidade_fonte in CONVERSOES and CONVERSOES[unidade_fonte][0] == alvo:
        v, _, t = para_canonica(numero, unidade_fonte, r.simbolo)
        return v, (t,) if t else ()
    raise ContratoInvalido([erro("unidade_incompativel", r.simbolo,
                                 f"Unidade da fonte {unidade_fonte!r} não converte para {alvo!r} (sem conversão declarada)."
                                 if unidade_fonte in UNIDADES_CANONICAS or unidade_fonte in CONVERSOES else
                                 f"Unidade da fonte {unidade_fonte!r} desconhecida; exigida {alvo!r}.")])


def classificar_dispositivo(d: DispositivoInventario, *, termos: frozenset[str] | set[str] = frozenset(),
                            contexto: str = "operacional") -> tuple[ClassificacaoParametro, ...]:
    if contexto not in CONTEXTOS:
        raise ValueError(f"Contexto desconhecido: {contexto!r}")
    termos = frozenset(termos)
    out: list[ClassificacaoParametro] = []
    for r in REQUISITOS:
        if d.tipo not in r.tipos:
            continue
        exigido = r.obrigatoriedade == "obrigatorio" or (r.obrigatoriedade == "condicional" and _condicao_ativa(r, termos))
        base = dict(uid=d.uid, tipo=d.tipo, simbolo=r.simbolo, obrigatoriedade=r.obrigatoriedade, unidade=r.unidade_canonica)
        v = next((d.valor(k) for k in r.fontes if d.valor(k) is not None and d.valor(k).presente), None)
        sugerido = next((d.valor(k) for k in r.fontes if d.valor(k) is not None
                         and d.valor(k).origem == "inventario_sugerido_seeds2"), None)
        if v is None or v.origem == "inventario_sugerido_seeds2":
            if v is not None or sugerido is not None:
                s = v or sugerido
                out.append(ClassificacaoParametro(**base, classe="faltante_necessario" if exigido else "opcional",
                                                  bloqueia=exigido and d.habilitado, codigo="valor_sugerido_nao_confirmado",
                                                  mensagem=f"{s.chave} = {s.numero if s.numero is not None else s.texto} "
                                                           f"{s.unidade_fonte} é apenas valor inicial SUGERIDO pelo SEEDS2; "
                                                           "declare a origem (fabricante/instalação).",
                                                  chave_fonte=s.chave, origem=s.origem))
            elif r.obrigatoriedade == "futuro_3C1":
                out.append(ClassificacaoParametro(**base, classe="faltante_necessario", bloqueia=False,
                                                  codigo="necessario_3C1", mensagem=f"{r.descricao}: ausente; exigido "
                                                  "pelo commitment dinâmico (3C-1). " + r.nota))
            elif exigido:
                out.append(ClassificacaoParametro(**base, classe="faltante_necessario", bloqueia=d.habilitado,
                                                  codigo="parametro_obrigatorio_ausente",
                                                  mensagem=f"{r.descricao}: ausente; nenhum valor é presumido. " + r.nota))
            else:
                out.append(ClassificacaoParametro(**base, classe="opcional", bloqueia=False, codigo="opcional_ausente",
                                                  mensagem=f"{r.descricao}: ausente e não exigido ({r.condicao or 'opcional'})."))
            continue
        try:
            numero, trans = (None, ())
            if v.numero is not None:
                numero, trans = _converter(v.numero, v.unidade_fonte, r)
        except ContratoInvalido as exc:
            out.append(ClassificacaoParametro(**base, classe="faltante_necessario", bloqueia=d.habilitado and exigido,
                                              codigo="unidade_incompativel", mensagem=str(exc), chave_fonte=v.chave,
                                              origem=v.origem, procedencia=v.procedencia, numero_bruto=v.numero,
                                              unidade_bruta=v.unidade_fonte))
            continue
        sint = v.origem == "sintetico" or (v.procedencia is not None and v.procedencia.tipo == "sintetico")
        if sint:
            classe, bloq = "sintetico_ensaio", (contexto != "ensaio" and d.habilitado)
            cod = "dado_sintetico_fora_de_ensaio" if contexto != "ensaio" else "dado_sintetico_em_ensaio"
            msg = "Valor sintético: aceito apenas em contexto de ensaio."
        elif v.origem in ("derivado", "catalogo_referencia"):
            classe, bloq, cod, msg = "derivavel", False, "derivado", f"Derivado: {v.derivacao}"
        else:
            classe, bloq, cod, msg = "disponivel_verificavel", False, "disponivel", f"{v.chave} ({v.origem})"
        out.append(ClassificacaoParametro(**base, classe=classe, bloqueia=bloq, codigo=cod, mensagem=msg, numero=numero,
                                          texto=v.texto, logico=v.logico, chave_fonte=v.chave, origem=v.origem,
                                          procedencia=v.procedencia, transformacoes=trans,
                                          numero_bruto=v.numero if trans else None,
                                          unidade_bruta=v.unidade_fonte if trans else None))
    return tuple(out)


def matriz_parametros(inv: InventarioMicrorrede, *, termos=frozenset(), contexto: str = "operacional") -> MatrizParametros:
    entradas: list[ClassificacaoParametro] = []
    for d in inv.dispositivos:
        entradas += classificar_dispositivo(d, termos=termos, contexto=contexto)
    return MatrizParametros(inv.identidade.uid, contexto, tuple(sorted(frozenset(termos))), tuple(entradas))


def constatacoes(m: MatrizParametros) -> list[Constatacao]:
    """Constatações da matriz: bloqueantes ⇒ ``erro``/``pendente`` (conforme o requisito); 3C-1 ⇒ ``aviso``."""
    out: list[Constatacao] = []
    for c in m.entradas:
        cam = f"dispositivos[{c.uid}].{c.simbolo}"
        if c.bloqueia:
            sev = INDICE[c.simbolo].severidade_ausencia if c.codigo == "parametro_obrigatorio_ausente" else "erro"
            out.append((pendente if sev == "pendente" else erro)(c.codigo, cam, c.mensagem))
        elif c.codigo in ("necessario_3C1", "dado_sintetico_em_ensaio"):
            out.append(aviso(c.codigo, cam, c.mensagem))
    return out


def hash_matriz(m: MatrizParametros) -> str:
    return sha256(m)


__all__ = ["CLASSES", "CONTEXTOS", "ClassificacaoParametro", "INDICE", "MatrizParametros", "NATUREZAS", "OBRIGATORIEDADES",
           "REQUISITOS", "RequisitoParametro", "classificar_dispositivo", "constatacoes", "hash_matriz", "matriz_parametros"]
