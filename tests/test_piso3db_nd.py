"""Piso 3D-B3 — N/D no navegador: dado ausente nunca vira zero (sem solver; marco sintético de teste).

Três situações que o componente distingue e estes testes atacam, uma a uma:

* ZERO GRAVADO      → número 0: entra nas somas e é desenhado como zero;
* DADO AUSENTE      → ``null``: vira «N/D», não é somado e torna N/D toda grandeza derivada que dependa dele;
* NÃO APLICÁVEL     → o recurso/termo não existe nesta microrrede (``undefined``): é omitido, sem N/D e sem zero inventado.

A primeira parte executa o MODELO DE VISTA em Node (funções puras). A segunda monta o componente REAL num navegador
(Chromium + Playwright, quando instalados) com marcos adulterados e confere o que a pessoa VÊ.
"""
from __future__ import annotations

import copy
import unittest

import piso3db_util as P

ND = "__undefined__"          # como o executor Node serializa ``undefined`` (não aplicável)


def _sem(f: dict, caminho: str, *, intervalo: int | None = None, remover: bool = False) -> dict:
    """Cópia do marco com ``caminho`` (chaves separadas por «/») AUSENTE: toda a série (None), um só intervalo ou a
    chave removida (coluna que a rodada nunca gravou)."""
    g = copy.deepcopy(f)
    *pais, ultima = caminho.split("/")
    alvo = g
    for c in pais:
        alvo = alvo[c]
    if remover:
        del alvo[ultima]
    elif intervalo is None:
        alvo[ultima] = None
    else:
        alvo[ultima][intervalo] = None
    g["hash"] = f["hash"] + "|" + caminho + ("#" + str(intervalo) if intervalo is not None else "") + ("-" if remover else "")
    return g


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class UtilitariosPurosTest(unittest.TestCase):
    def test_aritmetica_nunca_trata_ausente_como_zero(self):
        r = P.node("""const a = api; return {
            mais: [a.mais(1, 2), a.mais(1, null), a.mais(1, undefined), a.mais(), a.mais(0, 0)],
            vezes: [a.vezes(2, 3), a.vezes(null, 100), a.vezes(undefined, 100), a.vezes(0, 100)],
            menos: [a.menos(5, 2), a.menos(5, null), a.menos(null, 2), a.menos(0, 0)],
            razao: [a.razao(1, 4), a.razao(null, 4), a.razao(1, null), a.razao(1, 0), a.razao(0, 4)],
            somaT: [a.somaT([1, 2]), a.somaT([1, null]), a.somaT(null), a.somaT(undefined), a.somaT([0, 0])],
            acum: [a.acum([1, 2, 3]), a.acum([1, null, 3]), a.acum(null), a.acum([0, 0])],
            agg: [a.agg([[1, 2], [3, 4]], 2), a.agg([[1, 2], null], 2), a.agg([[1, null], [3, 4]], 2), a.agg([], 2), a.agg([[0, 0]], 2)],
            opc: [a.opc([null, null]), a.opc([0, null]), a.opc(null)],
            conta: [a.conta([1, 5, 9], (v) => v > 4), a.conta([1, null, 9], (v) => v > 4), a.conta(null, (v) => v > 4)],
            el: [a.el([7], 0), a.el(null, 0), a.el(undefined, 0)],
            texto: [a.nf(null), a.nf(0, 1), a.nfu(undefined, 1, " %"), a.nfu(null, 1, " %"), a.nfu(0, 1, " %")] };""", {})
        self.assertEqual(r["mais"], [3, None, 1, 0, 0])
        self.assertEqual(r["vezes"], [6, None, ND, 0])
        self.assertEqual(r["menos"], [3, None, None, 0])
        self.assertEqual(r["razao"], [25, None, None, ND, 0])          # ÷ 0 = não aplicável, nunca N/D nem infinito
        self.assertEqual(r["somaT"], [3, None, None, ND, 0])
        self.assertEqual(r["acum"], [[0, 1, 3, 6], [0, 1, None, None], None, [0, 0, 0]])   # nada é acumulado depois da lacuna
        self.assertEqual(r["agg"], [[4, 6], None, [4, None], ND, [0, 0]])
        self.assertEqual(r["opc"], [ND, [0, None], None])               # termo opcional todo vazio = não declarado
        self.assertEqual(r["conta"], [2, None, None])
        self.assertEqual(r["el"], [7, None, ND])
        self.assertEqual(r["texto"], ["N/D", "0,0", "—", "N/D", "0,0 %"])


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class ModeloComDadosAusentesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = P.marco_sintetico()               # 2 eólicas, 1 FV, 1 banco, 1 PEMFC, PCC conectado
        cls.base = P.node("const M = api.modelo(F); return { A: M.A, ord: M.ord, b: api.balancoDe(M.A, 3) };", cls.f)

    def _modelo(self, marco, extra="null"):
        return P.node(f"const M = api.modelo(F); return {{ A: M.A, ord: M.ord, b: api.balancoDe(M.A, 3), b0: api.balancoDe(M.A, 0), x: {extra} }};", marco)

    def test_marco_integro_soma_exatamente_as_parcelas(self):
        A, b = self.base["A"], self.base["b"]
        self.assertEqual(A["wtP"], [16.0] * 6)                          # 2 aerogeradores × 8 kW
        self.assertEqual(b["total"], 16 + 4 + 1 + 10 + 5)
        self.assertEqual(b["faltam"], [])
        self.assertEqual(sum(v for _k, v in b["con"]), b["total"])     # o balanço sintético fecha

    def test_pcc_ausente_nao_vira_zero(self):
        for campo in ("pcc_importacao_realizada_kW", "custo_importacao_R", "tarifa_importacao_decisao_R_kWh"):
            for remover in (False, True):
                with self.subTest(campo=campo, remover=remover):
                    r = self._modelo(_sem(self.f, "intervalos/" + campo, remover=remover))
                    chave = {"pcc_importacao_realizada_kW": "impR", "custo_importacao_R": "cImp",
                             "tarifa_importacao_decisao_R_kWh": "tar"}[campo]
                    self.assertIsNone(r["A"][chave])
        r = self._modelo(_sem(self.f, "intervalos/pcc_importacao_realizada_kW"))
        self.assertIsNone(r["b"]["total"])                               # o total NÃO é a soma do resto
        self.assertEqual(r["b"]["faltam"], ["grid"])
        r = self._modelo(_sem(self.f, "intervalos/pcc_importacao_realizada_kW", intervalo=3))
        self.assertIsNone(r["b"]["total"])
        self.assertEqual(r["b0"]["total"], self.base["b"]["total"])     # os outros intervalos continuam íntegros
        self.assertEqual(r["A"]["impR"][3], None)
        self.assertEqual(r["A"]["impR"][2], 5.0)

    def test_renovavel_ausente_invalida_a_soma_da_tecnologia(self):
        r = self._modelo(_sem(self.f, "renovaveis/eq-wt2/P_R_kW"))
        self.assertIsNone(r["A"]["wtP"])                                 # nunca «8 kW» (só o outro aerogerador)
        self.assertEqual(r["A"]["fvP"], [4.0] * 6)                      # a outra tecnologia não é contaminada
        self.assertEqual(r["b"]["faltam"], ["wt"])
        r = self._modelo(_sem(self.f, "renovaveis/eq-wt2/P_R_kW", intervalo=3))
        self.assertEqual(r["A"]["wtP"], [16.0, 16.0, 16.0, None, 16.0, 16.0])
        r = self._modelo(_sem(self.f, "renovaveis/eq-wt1/vertimento_kW", remover=True))
        self.assertIsNone(r["A"]["wtV"])
        r = self._modelo(_sem(self.f, "renovaveis/eq-wt1", remover=True))   # o registro inteiro do equipamento sumiu
        self.assertIsNone(r["A"]["wtP"])

    def test_bateria_ausente(self):
        r = self._modelo(_sem(self.f, "baterias/eq-bat1/P_d_kW"))
        self.assertIsNone(r["A"]["pd"])
        self.assertEqual(r["b"]["faltam"], ["bat"])
        r = self._modelo(_sem(self.f, "baterias/eq-bat1/energia_kWh", intervalo=2))
        self.assertEqual(r["A"]["fr"][:4], [20.0, 19.0, None, 17.0])    # estado de fronteira ausente fica ausente
        r = self._modelo(_sem(self.f, "baterias/eq-bat1/resumo/capacidade_kWh"))
        self.assertIsNone(r["A"]["cap"])
        dois = P.marco_sintetico(bancos=2)
        r = self._modelo(_sem(dois, "baterias/eq-bat2/P_c_kW"))
        self.assertIsNone(r["A"]["pc"])                                  # 2 bancos, 1 sem dado ⇒ soma N/D
        self.assertEqual(r["A"]["pd"], [2.0] * 6)

    def test_custos_ausentes(self):
        r = self._modelo(_sem(self.f, "intervalos/custo_realizado_intervalo_R"), "api.acum(M.A.cInt)")
        self.assertIsNone(r["A"]["cInt"])
        self.assertIsNone(r["x"])
        r = self._modelo(_sem(self.f, "intervalos/custo_importacao_R", intervalo=2), "[api.acum(M.A.cImp), api.somaT(M.A.cImp)]")
        self.assertEqual(r["x"], [[0, 2.5, 5.0, None, None, None, None], None])
        r = self._modelo(_sem(self.f, "pemfc/eq-fc#1/custo_h2_R", intervalo=1))
        self.assertEqual(r["A"]["cH2"][:3], [6.0, None, 6.0])
        r = self._modelo(_sem(self.f, "intervalos/custo_realizado_acumulado_R", remover=True))
        self.assertIsNone(r["A"]["cAcc"])

    def test_zero_gravado_continua_zero(self):
        g = copy.deepcopy(self.f)
        for u in ("eq-wt1", "eq-wt2"):
            g["renovaveis"][u]["P_R_kW"] = [0.0] * 6
        g["intervalos"]["pcc_importacao_realizada_kW"] = [0.0] * 6
        r = self._modelo(g)
        self.assertEqual(r["A"]["wtP"], [0.0] * 6)
        self.assertEqual(r["A"]["impR"], [0.0] * 6)
        self.assertEqual(r["b"]["total"], 4 + 1 + 10)
        self.assertEqual(r["b"]["faltam"], [])

    def test_recurso_inexistente_e_omitido_sem_nd(self):
        r = self._modelo(P.marco_sintetico(pemfc=0, eolicas=0))
        self.assertEqual((r["A"]["fcP"], r["A"]["wtP"], r["A"]["cH2"], r["A"]["fcOn"]), (ND, ND, ND, ND))
        self.assertEqual(r["ord"], ["fv", "bat", "grid", "dem", "eco"])
        self.assertEqual([k for k, _v in r["b"]["inj"]], ["fv", "bat", "grid"])
        self.assertEqual(r["b"]["total"], 4 + 1 + 5)
        r = self._modelo(P.marco_sintetico(conectado=False))
        self.assertEqual((r["A"]["impR"], r["A"]["tar"], r["A"]["cImp"], r["A"]["expR"]), (ND, ND, ND, ND))
        self.assertNotIn("grid", r["ord"])
        self.assertEqual(r["b"]["total"], 16 + 4 + 1 + 10)              # isolado: a rede não entra nem como zero
        r = self._modelo(P.marco_sintetico(bancos=0))
        self.assertEqual((r["A"]["pd"], r["A"]["fr"], r["A"]["cThr"], r["A"]["cap"]), (ND, ND, ND, ND))

    def test_termo_opcional_nao_declarado_nao_e_dado_ausente(self):
        g = copy.deepcopy(self.f)
        g["pemfc"]["eq-fc#1"]["custo_eventos_R"] = [None] * 6           # termo de eventos fora do objetivo
        g["intervalos"]["custo_desvio_rede_R"] = [None] * 6
        r = self._modelo(g)
        self.assertEqual((r["A"]["cEv"], r["A"]["cDes"]), (ND, ND))
        self.assertEqual(r["A"]["cH2"], [6.0] * 6)

    def test_plano_de_janela_com_serie_ausente(self):
        r = P.node("return api.planoPorTipo(F, F.planos[0]);", self.f)
        self.assertEqual((r["wt"], r["pd"], r["imp"], r["n"]), ([16.0] * 4, [1.0] * 4, [5.0] * 4, 4))
        self.assertEqual(r["aplicado"], [True, True, False, False])
        g = copy.deepcopy(self.f)
        del g["planos"][0]["series"]["eq-wt2|P_R"]
        g["planos"][0]["series"]["pcc_importacao_programada_kW"][1] = None
        r = P.node("return [api.planoPorTipo(F, F.planos[0]), api.planoPorTipo(F, null)];", g)
        self.assertIsNone(r[0]["wt"])
        self.assertEqual(r[0]["imp"], [5.0, None, 5.0, 5.0])
        self.assertIsNone(r[1])
        r = P.node("return api.planoPorTipo(F, F.planos[0]);", P.marco_sintetico(conectado=False, pemfc=0))
        self.assertEqual((r["imp"], r["exp"], r["fc"]), (ND, ND, ND))

    def test_janela_sem_sinal_valido_e_identificada(self):
        r = P.node("const M = api.modelo(F); return M.jan.map((w) => [w.j, w.k, w.ok, w.custo_futuro_estimado]);", self.f)
        self.assertEqual(r, [[0, 0, False, None], [1, 2, True, 0.0], [2, 4, False, None]])


@unittest.skipUnless(P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class NavegadorComDadosAusentesTest(unittest.TestCase):
    """O componente REAL, num navegador, com marcos adulterados: nada quebra e a ausência é VISÍVEL."""

    @classmethod
    def setUpClass(cls):
        f = P.marco_sintetico(bancos=2)
        cls.marcos = {
            "integro": f,
            "pcc": _sem(_sem(f, "intervalos/pcc_importacao_realizada_kW"), "intervalos/custo_importacao_R", remover=True),
            "renovavel": _sem(_sem(f, "renovaveis/eq-wt2/P_R_kW"), "renovaveis/arr-fv1/A_utilizavel_kW", intervalo=0),
            "bateria": _sem(_sem(_sem(f, "baterias/eq-bat2/P_d_kW"), "baterias/eq-bat1/energia_kWh", intervalo=0), "baterias/eq-bat1/soc"),
            "custos": _sem(_sem(_sem(f, "intervalos/custo_realizado_intervalo_R"), "intervalos/custo_realizado_acumulado_R", remover=True),
                           "resumo/custo_realizado_total_R"),
            "decisao": _sem(_sem(_sem(f, "planos"), "coordenacoes"), "auditoria"),
            "pemfc": _sem(_sem(f, "pemfc/eq-fc#1/p_kW"), "pemfc/eq-fc#1/u", intervalo=0),
            "sem_recursos": P.marco_sintetico(pemfc=0, eolicas=0, bancos=0, conectado=False),
        }
        cls.r = P.bancada(cls.marcos)

    def test_nenhum_marco_quebra_o_componente(self):
        for nome, res in self.r.items():
            with self.subTest(marco=nome):
                self.assertEqual(res["erros"], [])
                self.assertGreaterEqual(len(res["vistas"]), 4 + 3)

    def test_marco_integro_nao_mostra_nd_na_operacao(self):
        v = self.r["integro"]["vistas"]
        self.assertNotIn("N/D", v["lente:operacao"])
        self.assertIn("Σ injeção (derivado) = 37,00 kW", v["lente:operacao"])   # 16 + 4 + 2 + 10 + 5 (dois bancos)
        # na Economia o ÚNICO N/D legítimo é o custo futuro da janela 0, decidida sem sinal válido (resultado científico)
        self.assertEqual(v["lente:economia"].count("N/D"), 1)
        self.assertIn("sem valor futuroObjetivo do MILPR$ 34,08Custo operativo previstoR$ 34,08Custo futuro estimadoN/D", v["lente:economia"])

    def test_pcc_ausente_e_visivel_e_nao_some_nas_somas(self):
        v = self.r["pcc"]["vistas"]
        self.assertIn("balanço incompleto: rede sem dado", v["lente:operacao"])
        self.assertNotIn("Σ injeção (derivado)", v["lente:operacao"])
        self.assertIn("N/D", v["painel:Rede"])
        self.assertIn("N/DkW importados", v["painel:Rede"])                    # nunca «0,00 kW importados»
        self.assertNotIn("0,00kW importados", v["painel:Rede"])
        self.assertIn("Folga até o limiteN/D kW", v["painel:Rede"])            # derivado de dado ausente = N/D
        self.assertIn("Importação da redeN/D", v["lente:economia"])

    def test_renovavel_ausente(self):
        v = self.r["renovavel"]["vistas"]
        self.assertIn("balanço incompleto: eólica sem dado", v["lente:operacao"])
        self.assertIn("N/DkW aproveitados", v["painel:Eólica:eq-wt2"])
        self.assertIn("Da demanda (derivado)N/D", v["painel:Eólica:eq-wt2"])
        self.assertNotIn("N/DkW aproveitados", v["painel:Eólica:eq-wt1"])      # o outro aerogerador continua íntegro
        self.assertIn("8,00kW aproveitados", v["painel:Eólica:eq-wt1"])
        self.assertIn("Potencial utilizávelN/D kW", v["painel:Solar:arr-fv1"])

    def test_bateria_ausente(self):
        v = self.r["bateria"]["vistas"]
        self.assertIn("balanço incompleto: bateria sem dado", v["lente:operacao"])
        self.assertIn("N/D", v["painel:Bateria:eq-bat2"])
        self.assertIn("Potência no barramentoN/D", v["painel:Bateria:eq-bat2"])
        self.assertIn("N/D → 19,0kWh", v["painel:Bateria:eq-bat1"])            # energia inicial ausente, final gravada
        self.assertIn("SOCN/D → N/D %", v["painel:Bateria:eq-bat1"])

    def test_custos_ausentes(self):
        v = self.r["custos"]["vistas"]
        self.assertIn("N/D — custo realizado por intervalo não persistido", v["lente:economia"])
        self.assertIn("N/D — custo acumulado não persistido", v["lente:economia"])
        self.assertIn("Custo operacional realizadoliquidadoN/D", v["lente:economia"])
        self.assertIn("Intervalo 00h–01hrealizadoN/D", v["lente:economia"])
        self.assertIn("— N/D realizados", v["lente:operacao"])
        self.assertIn("Custo operacional realizadoliquidadoN/D", v["painel:Custos"])
        self.assertNotIn("R$ 0,00 realizados", v["lente:operacao"])

    def test_decisao_e_auditoria_ausentes_sao_declaradas(self):
        v = self.r["decisao"]["vistas"]
        self.assertIn("planos por janela não persistidos", v["lente:decisao"])
        self.assertIn("registro de coordenação desta janela não persistido", v["lente:decisao"])
        self.assertIn("v2/auditoria.json não persistido", v["lente:evidencia"])

    def test_pemfc_ausente(self):
        v = self.r["pemfc"]["vistas"]
        self.assertIn("balanço incompleto: PEMFC sem dado", v["lente:operacao"])
        self.assertIn("N/DkW pedidos", v["painel:PEMFC:eq-fc#1:0"])
        self.assertIn("Instante 00h–01hN/D", v["painel:PEMFC:eq-fc#1:0"])       # estado da unidade ausente ≠ OFF

    def test_recurso_inexistente_nao_gera_nd_nem_painel(self):
        v = self.r["sem_recursos"]["vistas"]
        self.assertEqual(sorted(k for k in v if k.startswith("painel:")), ["painel:Carga", "painel:Custos", "painel:Solar:arr-fv1"])
        self.assertNotIn("balanço incompleto", v["lente:operacao"])
        self.assertIn("Σ injeção (derivado) = 4,00 kW", v["lente:operacao"])
        for ausente in ("Eólica", "PEMFC", "Rede", "Bateria"):
            self.assertNotIn(ausente, v["lente:operacao"].split("RODADA")[0].split("hachura")[0])


if __name__ == "__main__":
    unittest.main()
