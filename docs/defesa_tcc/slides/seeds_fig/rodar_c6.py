"""Reproduz a configuração C6 (artigo, Seção 6.3.2): cenário de C5 duplicado, SOC inicial 12 % e sem termo terminal.
Executa o MILP–MPC pelo runner do SEEDS num diretório de dados TEMPORÁRIO e imprime os indicadores."""
import copy, os, sys, time
os.environ["SEEDS2_DATA_DIR"] = sys.argv[1]
sys.path.insert(0, os.getcwd())
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import service as SV
from integracao_v2 import execucao as EX
reg = MicrogridRegistry(sys.argv[1]); st = reg.open("085e4418f6f94ac6839597a3bf6b15a2")
c5 = [s for s in st.list_scenarios() if s.name.startswith("C5")][0]
novo = SV.duplicate(st, c5.scenario_uid, name="C6 — EMB-H2-120 · SOC inicial 12 % · sem reserva final")
doc = copy.deepcopy(st.get_scenario(novo.scenario_uid).document)
doc["initialization"]["equipment"]["eq-561e68f4a364"]["soc0_pct"] = 12.0
doc["milp_mpc"]["planejador"]["termo_longo"] = {"tipo": "nenhum_declarado", "valores": {},
    "justificativa": "C6 (artigo, Seção 6.3.2): sem condição terminal declarada."}
doc["description"] = "C6: igual a C5, com SOC inicial de 12 % e sem condição terminal."
sv = st.save_scenario(doc, novo.version, note="C6: SOC inicial 12 % e sem termo terminal")
pf = EX.prepare(st, sv.scenario_uid, sv.version)
print("preflight ok:", getattr(pf, "ok", None), [getattr(c, "codigo", c) for c in (getattr(pf, "bloqueios", None) or [])][:5])
run = EX.submit(st, sv.scenario_uid, sv.version, EX.new_request_id(), background=False)
print("run:", run)
