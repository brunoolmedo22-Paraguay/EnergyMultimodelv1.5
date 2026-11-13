"""Piso 3D-B (correção C) — os roteiros E2E encerram o servidor e os seus processos filhos MESMO quando uma fase falha,
e recusam operar sobre uma porta já ocupada (servidor que sobrou de outra execução).

Exercita ``tools/e2e/servidor.sh`` com um servidor de MENTIRA (um ``python`` de fachada que atende ``/_stcore/health`` e
cria um processo filho): nenhum Streamlit, nenhum solver, nenhum navegador.
"""
from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LIB = RAIZ / "tools" / "e2e" / "servidor.sh"
BASH = shutil.which("bash")

FALSO_SERVIDOR = r'''
import http.server, os, subprocess, sys
porta = int(sys.argv[sys.argv.index("--server.port") + 1])
filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])       # processo FILHO do servidor
open(os.environ["PIDS"], "a").write(f"{os.getpid()} {filho.pid}\n")
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/_stcore/health" else 404); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", porta), H).serve_forever()
'''


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                              # um zumbi já terminou: só falta o pai recolhê-lo
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return True


def _ocupada(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


@unittest.skipUnless(BASH and shutil.which("curl") and sys.platform.startswith("linux"), "requer bash, curl e Linux")
class LimpezaDoServidorE2ETest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        (self.d / "servidor.py").write_text(FALSO_SERVIDOR, encoding="utf-8")
        fachada = self.d / "python_fachada"            # recebe «-m streamlit run app.py --server.port N …»
        fachada.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" "{self.d / "servidor.py"}" "$@"\n', encoding="utf-8")
        fachada.chmod(fachada.stat().st_mode | stat.S_IXUSR)
        self.py, self.pids, self.porta = fachada, self.d / "pids.txt", _porta_livre()

    def tearDown(self):
        for pid in self._pids():
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        self._tmp.cleanup()

    def _pids(self) -> list[int]:
        return [int(x) for x in self.pids.read_text().split()] if self.pids.exists() else []

    def _roteiro(self, corpo: str) -> subprocess.CompletedProcess:
        script = (f'set -euo pipefail\nsource "{LIB}"\nE2E_ESPERA=30\n'
                  f'e2e_servidor "{self.py}" "{self.d}" {self.porta} "{self.d}/servidor.log"\n{corpo}\n')
        return subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=120,
                              env={**os.environ, "PIDS": str(self.pids)}, cwd=str(self.d))

    def _espera_morrer(self) -> None:
        for _ in range(50):
            if not any(_vivo(p) for p in self._pids()) and not _ocupada(self.porta):
                return
            time.sleep(0.1)

    def test_fase_que_falha_nao_deixa_servidor_nem_filhos(self):
        r = self._roteiro('echo "servidor no ar"\ne2e_fase "$PWD/fase.log" bash -c "echo verificando; exit 7"\necho "NUNCA CHEGA AQUI"')
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn("servidor no ar", r.stdout)
        self.assertNotIn("NUNCA CHEGA AQUI", r.stdout)
        self.assertIn("fase falhou (código 7)", r.stderr)
        self.assertEqual((self.d / "fase.log").read_text().strip(), "verificando")
        self._espera_morrer()
        pids = self._pids()
        self.assertEqual(len(pids), 2)                                   # o servidor e o seu filho chegaram a existir
        self.assertEqual([p for p in pids if _vivo(p)], [])             # … e nenhum sobrou
        self.assertFalse(_ocupada(self.porta))

    def test_erro_qualquer_do_roteiro_tambem_limpa(self):
        r = self._roteiro("comando_que_nao_existe_e2e")
        self.assertNotEqual(r.returncode, 0)
        self._espera_morrer()
        self.assertEqual([p for p in self._pids() if _vivo(p)], [])
        self.assertFalse(_ocupada(self.porta))

    def test_sucesso_e_kill_9_simulado_limpam(self):
        r = self._roteiro(f'e2e_matar {self.porta}\necho "derrubado"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self._espera_morrer()
        self.assertEqual([p for p in self._pids() if _vivo(p)], [])
        r = self._roteiro(f'e2e_parar {self.porta}\necho "parado"')         # execuções sucessivas na MESMA porta
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("parado", r.stdout)
        self._espera_morrer()
        self.assertEqual([p for p in self._pids() if _vivo(p)], [])

    def test_porta_ocupada_e_recusada_em_vez_de_reutilizar_o_servidor_antigo(self):
        with socket.socket() as s:                                       # «servidor antigo» de outra execução
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", self.porta))
            s.listen(1)
            r = self._roteiro('echo "NUNCA CHEGA AQUI"')
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("já está ocupada", r.stderr)
        self.assertNotIn("NUNCA CHEGA AQUI", r.stdout)
        self.assertEqual(self._pids(), [])                               # nenhum servidor novo foi iniciado

    def test_os_quatro_roteiros_usam_a_biblioteca_e_nao_iniciam_servidor_por_fora(self):
        for nome in ("run_piso3da.sh", "run_piso3da2r.sh", "run_piso3da2h.sh", "run_piso3db.sh"):
            txt = (RAIZ / "tools" / "e2e" / nome).read_text(encoding="utf-8")
            self.assertIn('source "$RAIZ/tools/e2e/servidor.sh"', txt, nome)
            self.assertNotIn("streamlit run", txt, nome)                 # só a biblioteca inicia servidores
            self.assertIn("set -euo pipefail", txt, nome)


if __name__ == "__main__":
    unittest.main()
