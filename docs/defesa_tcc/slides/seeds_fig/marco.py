"""Monta, SOMENTE LEITURA, o marco «seeds2-trama-frame» (o mesmo que a Partitura do SEEDS desenha) de rodadas V2 dos
exemplos persistentes (`seeds2/exemplos`, C4 e C5), num diretório de dados TEMPORÁRIO — nunca no armazenamento real.
Uso (na raiz do repositório):  PYTHONDONTWRITEBYTECODE=1 python3 docs/defesa_tcc/slides/seeds_fig/marco.py <dados_tmp> <saida> <run8>...
Cada marco é verificado por `integracao_v2.registro.verificar` (hashes, vistas regeneradas, reauditoria) antes de ser gravado."""
import json
import os
import sys

os.environ["SEEDS2_DATA_DIR"] = sys.argv[1]
sys.path.insert(0, os.getcwd())
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.microgrid import exemplos  # noqa: E402
from integracao_v2 import registro as RG, trama_frame as TF  # noqa: E402

reg = MicrogridRegistry(sys.argv[1])
exemplos.garantir(reg)
for e in reg.entries():
    st = reg.open(e.uid)
    for r in st.list_runs():
        if r.run_uid[:8] in sys.argv[3:]:
            v = RG.verificar(st, r)
            if not v.ok:
                raise SystemExit(f"evidência NÃO verificada: {r.run_uid}")
            f = TF.montar(st, r, verificacao=v)
            json.dump(f, open(os.path.join(sys.argv[2], r.run_uid[:8] + ".json"), "w"), ensure_ascii=False, allow_nan=False)
            print("marco", r.run_uid[:8], "K =", f["rodada"]["K"], "verificado")
