"""Instantânea completa (``.seeds2snapshot.zip``) e exemplos persistentes (``seeds2/exemplos/``).

Missão «Exemplos persistentes» (decisão do responsável, 14/11/2026): o botão GUARDAR COMPLETO do Gestor exporta o
banco inteiro de uma microrrede; as instantâneas colocadas em ``seeds2/exemplos/`` são restauradas automaticamente
quando o SEEDS2 inicia (o disco do Streamlit Cloud é efímero). Dados de TESTE sintéticos (``piso3da_util``).
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3da_util as U  # noqa: E402

from seeds2.microgrid import exemplos as E  # noqa: E402
from seeds2.microgrid import snapshot as S  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry, RegistryError  # noqa: E402
from seeds2.microgrid.store import DB_FILENAME, INCARNATION_KEY, LIFECYCLE_KEY  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

OWNER = "teste-snapshot"
NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def microrrede_completa(reg: MicrogridRegistry, nome: str = "Snapshot (teste)", *, rodadas: bool = True) -> str:
    """Microrrede com configuração, cenário com duas versões, uma rodada concluída (com dados) e uma que falhou."""
    cfg = U.config_bateria(nome)
    reg.create(cfg)
    uid = cfg["installation"]["uid"]
    st = reg.open(uid)
    sc = U.criar_cenario_v2(st)
    if rodadas:
        run, _ = st.start_run(run_uid="a" * 32, request_id="pedido-snapshot-01", scenario_uid=sc.scenario_uid,
                              scenario_version=sc.version, scenario_fingerprint=sc.fingerprint,
                              manifest={"engine": {"id": "milp_mpc_v1"}, "scenario": {"name": sc.name}}, owner=OWNER)
        st.finish_run(run.run_uid, OWNER, outcome={"estado": "ok"}, summary={"custo": 12.5},
                      data={"v2/intervalos.csv": (b"k,p\n" + b"1,2.5\n" * 2000, "text/csv"),
                            "v2/modelo.json": (b'{"x": 1}', "application/json")})
        run2, _ = st.start_run(run_uid="b" * 32, request_id="pedido-snapshot-02", scenario_uid=sc.scenario_uid,
                               scenario_version=sc.version, scenario_fingerprint=sc.fingerprint,
                               manifest={"engine": {"id": "milp_mpc_v1"}}, owner=OWNER)
        st.fail_run(run2.run_uid, OWNER, {"kind": "falha", "message": "falha de teste"})
    return uid


def editar_cenario(st, nota: str):
    """Nova versão do (único) cenário, com a descrição alterada: o que um usuário faz ao experimentar um exemplo."""
    sc = st.list_scenarios()[0]
    doc = json.loads(json.dumps(st.get_scenario(sc.scenario_uid).document))
    doc["description"] = f"{doc.get('description', '')} [{nota}]"
    st.save_scenario(doc, sc.version, note=nota)
    return sc.version


def dump(db: Path) -> dict:
    """Todas as linhas de todas as tabelas (exceto as marcas de catálogo em ``meta``)."""
    con = sqlite3.connect(db)
    try:
        out = {}
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            rows = con.execute(f"SELECT * FROM {t}").fetchall()
            if t == "meta":
                rows = [r for r in rows if r[0] not in (INCARNATION_KEY, LIFECYCLE_KEY)]
            out[t] = sorted(map(repr, rows))
        out["__user_version__"] = con.execute("PRAGMA user_version").fetchone()[0]
        return out
    finally:
        con.close()


def reempacotar(data: bytes, *, manifest=None, db: bytes | None = None, extra: dict | None = None,
                ajustar_hash: bool = True) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(data))
    m = json.loads(zin.read("manifest.json"))
    dbb = zin.read(DB_FILENAME) if db is None else db
    if manifest:
        m.update(manifest)
    if ajustar_hash:
        m["db_sha256"] = sha256(dbb).hexdigest()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m))
        z.writestr(DB_FILENAME, dbb)
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return buf.getvalue()


def alterar_banco(data: bytes, sql: list[str]) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / DB_FILENAME
        p.write_bytes(zipfile.ZipFile(io.BytesIO(data)).read(DB_FILENAME))
        con = sqlite3.connect(p, isolation_level=None)
        for s in sql:
            con.execute(s)
        con.close()
        return p.read_bytes()


class _Dirs(unittest.TestCase):
    def setUp(self):
        self._a = tempfile.TemporaryDirectory()
        self._b = tempfile.TemporaryDirectory()
        self.a, self.b = self._a.name, self._b.name

    def tearDown(self):
        self._a.cleanup()
        self._b.cleanup()


class InstantaneaTest(_Dirs):
    def test_restauracao_reproduz_o_banco_inteiro(self):
        ra = MicrogridRegistry(self.a)
        uid = microrrede_completa(ra)
        data = S.export_snapshot(ra.open(uid))
        rep = S.inspect_snapshot(data)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.uid, uid)
        self.assertEqual(rep.manifest["counts"]["scenario_runs"], 2)
        rb = MicrogridRegistry(self.b)
        self.assertEqual(S.restore_snapshot(rb, data), uid)
        self.assertEqual(dump(ra.dir_for(uid) / DB_FILENAME), dump(rb.dir_for(uid) / DB_FILENAME))   # linha a linha
        sa, sb = ra.open(uid), rb.open(uid)
        self.assertEqual(sa.load().fingerprint, sb.load().fingerprint)
        self.assertEqual([(s.scenario_uid, s.version, s.fingerprint) for s in sa.list_scenarios()],
                         [(s.scenario_uid, s.version, s.fingerprint) for s in sb.list_scenarios()])
        ga, gb = sa.get_run("a" * 32), sb.get_run("a" * 32)
        self.assertEqual(gb.state, "concluida")
        self.assertEqual(ga.summary, gb.summary)
        self.assertEqual(ga.data, gb.data)                                     # dados gravados da rodada, bit a bit
        self.assertEqual(sb.get_run("b" * 32).state, "falhou")
        self.assertEqual(S.schema(rb.dir_for(uid) / DB_FILENAME), S.reference_schema())
        # a restaurada é uma microrrede normal do catálogo: aceita novas versões do cenário
        v = editar_cenario(sb, "edição pós-restauração")
        self.assertEqual(sb.list_scenarios()[0].version, v + 1)

    def test_incarnacao_viaja_e_lapide_nao(self):
        ra = MicrogridRegistry(self.a)
        uid = microrrede_completa(ra, rodadas=False)
        data = S.export_snapshot(ra.open(uid))
        con = sqlite3.connect(":memory:")
        con.deserialize(zipfile.ZipFile(io.BytesIO(data)).read(DB_FILENAME))
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        self.assertNotIn(LIFECYCLE_KEY, meta)
        self.assertEqual(meta[INCARNATION_KEY], ra.get(uid).incarnation)
        rb = MicrogridRegistry(self.b)
        S.restore_snapshot(rb, data)
        self.assertEqual(rb.get(uid).incarnation, ra.get(uid).incarnation)   # documentos dos cenários continuam válidos

    def test_exportacao_recusa_rodada_em_execucao(self):
        ra = MicrogridRegistry(self.a)
        uid = microrrede_completa(ra, rodadas=False)
        st = ra.open(uid)
        sc = st.list_scenarios()[0]
        st.start_run(run_uid="c" * 32, request_id="pedido-snapshot-03", scenario_uid=sc.scenario_uid,
                     scenario_version=sc.version, scenario_fingerprint=sc.fingerprint, manifest={}, owner=OWNER)
        with self.assertRaisesRegex(S.SnapshotError, "rodada em execução"):
            S.export_snapshot(st)

    def test_impressao_do_estado_e_estavel_e_sensivel(self):
        ra = MicrogridRegistry(self.a)
        uid = microrrede_completa(ra, rodadas=False)
        s1 = S.state_stamp(ra.open(uid))
        self.assertEqual(s1, S.state_stamp(ra.open(uid)))                   # leituras repetidas: mesma impressão
        S.export_snapshot(ra.open(uid))
        self.assertEqual(s1, S.state_stamp(ra.open(uid)))                   # exportar não altera o estado
        editar_cenario(ra.open(uid), "muda")
        self.assertNotEqual(s1, S.state_stamp(ra.open(uid)))

    def test_identidade_existente_e_recusada_sem_alterar_nada(self):
        ra = MicrogridRegistry(self.a)
        uid = microrrede_completa(ra)
        data = S.export_snapshot(ra.open(uid))
        before = dump(ra.dir_for(uid) / DB_FILENAME)
        with self.assertRaisesRegex(RegistryError, "já existe"):
            S.restore_snapshot(ra, data)
        self.assertEqual(before, dump(ra.dir_for(uid) / DB_FILENAME))
        self.assertEqual(len(ra.entries()), 1)


class InspecaoAdversarialTest(_Dirs):
    @classmethod
    def setUpClass(cls):
        cls._t = tempfile.TemporaryDirectory()
        reg = MicrogridRegistry(cls._t.name)
        cls.uid = microrrede_completa(reg)
        cls.data = S.export_snapshot(reg.open(cls.uid))

    @classmethod
    def tearDownClass(cls):
        cls._t.cleanup()

    def recusa(self, data: bytes, trecho: str):
        rep = S.inspect_snapshot(data)
        self.assertFalse(rep.ok)
        self.assertTrue(any(trecho in e for e in rep.errors), rep.errors)
        rb = MicrogridRegistry(self.b)
        with self.assertRaises(RegistryError):
            S.restore_snapshot(rb, data)
        self.assertEqual(rb.entries(), [])                                     # catálogo intocado
        self.assertEqual(list(rb.microgrids_dir.iterdir()), [])
        self.assertEqual(list(rb.staging_dir.iterdir()), [])

    def test_nao_zip(self):
        self.recusa(b"isto nao e um zip", "ZIP válido")

    def test_entrada_extra(self):
        self.recusa(reempacotar(self.data, extra={"../fora.txt": "x"}), "exatamente")

    def test_formato_errado(self):
        self.recusa(reempacotar(self.data, manifest={"format": "seeds2-backup"}), "Formato desconhecido")

    def test_versao_de_esquema_futura(self):
        self.recusa(reempacotar(self.data, manifest={"db_schema_version": 999}), "Atualize o SEEDS2")

    def test_banco_alterado_sem_atualizar_hash(self):
        db = bytearray(zipfile.ZipFile(io.BytesIO(self.data)).read(DB_FILENAME))
        db[-10] ^= 0xFF
        self.recusa(reempacotar(self.data, db=bytes(db), ajustar_hash=False), "SHA-256")

    def test_contagens_divergentes(self):
        m = json.loads(zipfile.ZipFile(io.BytesIO(self.data)).read("manifest.json"))
        cont = dict(m["counts"], scenario_run_data=m["counts"]["scenario_run_data"] + 1)
        self.recusa(reempacotar(self.data, manifest={"counts": cont}), "número de registros")

    def test_registros_removidos_exigem_violar_o_esquema(self):
        db = alterar_banco(self.data, ["DROP TRIGGER IF EXISTS scenario_run_data_immutable_d",
                                       "DELETE FROM scenario_run_data"])
        self.assertFalse(S.inspect_snapshot(reempacotar(self.data, db=db)).ok)

    def test_gatilho_injetado(self):
        db = alterar_banco(self.data, ["CREATE TRIGGER intruso AFTER INSERT ON revisions BEGIN DELETE FROM blobs; END"])
        self.recusa(reempacotar(self.data, db=db), "esquema do banco difere")

    def test_microrrede_excluida(self):
        db = alterar_banco(self.data, [f"INSERT INTO meta(key, value) VALUES ('{LIFECYCLE_KEY}', '{{}}')"])
        self.recusa(reempacotar(self.data, db=db), "excluída")

    def test_identidade_divergente(self):
        self.recusa(reempacotar(self.data, manifest={"installation_uid": "f" * 32}), "identidade do banco difere")

    def test_rodada_em_execucao(self):
        db = alterar_banco(self.data, ["DROP TRIGGER scenario_runs_final_u",
                                       "UPDATE scenario_runs SET state='em_execucao' WHERE run_uid='" + "b" * 32 + "'"])
        rep = S.inspect_snapshot(reempacotar(self.data, db=db))
        self.assertFalse(rep.ok)                                              # gatilho removido e rodada em execução


class ExemplosTest(_Dirs):
    def setUp(self):
        super().setUp()
        self._ex = tempfile.TemporaryDirectory()
        self.ex = Path(self._ex.name)
        origem = tempfile.TemporaryDirectory()
        self.addCleanup(origem.cleanup)
        reg = MicrogridRegistry(origem.name)
        self.uids = []
        for nome in ("C1 (teste)", "C2 (teste)"):
            uid = microrrede_completa(reg, nome)
            self.uids.append(uid)
            (self.ex / f"{nome[:2]}{S.SUFFIX}").write_bytes(S.export_snapshot(reg.open(uid)))
        self.origem_db = {u: dump(reg.dir_for(u) / DB_FILENAME) for u in self.uids}

    def tearDown(self):
        self._ex.cleanup()
        super().tearDown()

    def test_restaura_faltantes_sem_duplicar(self):
        reg = MicrogridRegistry(self.a)
        rel = E.garantir(reg, self.ex)
        self.assertEqual(len(rel.restaurados), 2)
        self.assertEqual(rel.falhas, [])
        self.assertEqual({e.uid for e in reg.entries()}, set(self.uids))
        self.assertTrue(all(E.eh_exemplo(e) for e in reg.entries()))
        for u in self.uids:
            self.assertEqual(dump(reg.dir_for(u) / DB_FILENAME), self.origem_db[u])
        rel2 = E.garantir(reg, self.ex)                                       # segundo início: nada a fazer
        self.assertEqual((rel2.restaurados, len(rel2.presentes)), ([], 2))
        self.assertEqual(len(reg.entries()), 2)

    def test_edicao_vale_ate_o_reinicio_e_exclusao_volta(self):
        reg = MicrogridRegistry(self.a)
        E.garantir(reg, self.ex)
        u0, u1 = self.uids
        v = editar_cenario(reg.open(u0), "experimento do usuário")
        E.garantir(reg, self.ex)                                              # exemplo presente: intocado
        self.assertEqual(reg.open(u0).list_scenarios()[0].version, v + 1)
        reg.delete(u1)
        rel = E.garantir(reg, self.ex)                                        # próximo início: volta ao guardado
        self.assertEqual(len(rel.restaurados), 1)
        self.assertEqual(dump(reg.dir_for(u1) / DB_FILENAME), self.origem_db[u1])
        # «reinício» com disco novo (Streamlit Cloud): tudo volta ao estado guardado, inclusive o editado
        reg2 = MicrogridRegistry(self.b)
        E.garantir(reg2, self.ex)
        self.assertEqual(dump(reg2.dir_for(u0) / DB_FILENAME), self.origem_db[u0])

    def test_arquivo_defeituoso_nao_impede_os_demais(self):
        (self.ex / f"C9{S.SUFFIX}").write_bytes(b"corrompido")
        (self.ex / "LEIA-ME.md").write_text("ignorado")
        reg = MicrogridRegistry(self.a)
        rel = E.garantir(reg, self.ex)
        self.assertEqual(len(rel.restaurados), 2)
        self.assertEqual(len(rel.falhas), 1)
        self.assertIn(f"C9{S.SUFFIX}", rel.falhas[0])

    def test_inicializacoes_concorrentes_nao_duplicam(self):
        regs = [MicrogridRegistry(self.a) for _ in range(4)]
        barreira = threading.Barrier(len(regs))
        rels = []

        def corre(r):
            barreira.wait()
            rels.append(E.garantir(r, self.ex))
        ts = [threading.Thread(target=corre, args=(r,)) for r in regs]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(len(MicrogridRegistry(self.a).entries()), 2)
        self.assertEqual(sum(len(r.restaurados) for r in rels), 2)
        self.assertEqual([f for r in rels for f in r.falhas], [])

    def test_desligado_por_variavel(self):
        reg = MicrogridRegistry(self.a)
        with mock.patch.dict(os.environ, {E.ENV_ENABLE: "0", E.ENV_DIR: str(self.ex)}):
            self.assertEqual(E.garantir_na_inicializacao(reg).restaurados, [])
        self.assertEqual(reg.entries(), [])
        with mock.patch.dict(os.environ, {E.ENV_ENABLE: "1", E.ENV_DIR: str(self.ex)}):
            self.assertEqual(len(E.garantir_na_inicializacao(reg).restaurados), 2)

    def test_diretorio_do_codigo_existe_e_so_tem_instantaneas_validas(self):
        self.assertTrue(E.DEFAULT_DIR.is_dir())
        for p in E.arquivos(E.DEFAULT_DIR):
            rep = S.inspect_snapshot(p.read_bytes())
            self.assertTrue(rep.ok, (p.name, rep.errors))


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class GestorTest(_Dirs):
    def setUp(self):
        super().setUp()
        self._env = mock.patch.dict(os.environ, {**NO_ADMIN, "SEEDS2_DATA_DIR": self.a})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        super().tearDown()

    def app(self) -> AppTest:
        from apptest_utils import APP_PATH

        app = AppTest.from_file(str(APP_PATH), default_timeout=180)
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_guardar_completo_gera_instantanea_restauravel(self):
        reg = MicrogridRegistry(self.a)
        uid = microrrede_completa(reg)
        app = self.app()
        next(b for b in app.button if b.key == f"g_snap_{uid}").click().run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        stamp, name, data = app.session_state["gestor_snap"][uid]
        self.assertTrue(name.endswith(S.SUFFIX) and uid[:8] in name)
        self.assertIn("⬇ Baixar instantânea completa", [d.proto.label for d in app.get("download_button")])
        rep = S.inspect_snapshot(data)
        self.assertTrue(rep.ok, rep.errors)
        rb = MicrogridRegistry(self.b)
        S.restore_snapshot(rb, data)
        self.assertEqual(dump(reg.dir_for(uid) / DB_FILENAME), dump(rb.dir_for(uid) / DB_FILENAME))
        # depois de uma nova versão do cenário, a instantânea preparada deixa de ser oferecida (estado mudou)
        editar_cenario(reg.open(uid), "nova versão")
        app.run()
        self.assertNotIn("⬇ Baixar instantânea completa", [d.proto.label for d in app.get("download_button")])
        self.assertTrue(any("GUARDAR COMPLETO de novo" in c.value for c in app.caption))

    def test_exemplos_restaurados_ao_iniciar_aparecem_marcados(self):
        origem = tempfile.TemporaryDirectory()
        self.addCleanup(origem.cleanup)
        ex = tempfile.TemporaryDirectory()
        self.addCleanup(ex.cleanup)
        ro = MicrogridRegistry(origem.name)
        uid = microrrede_completa(ro, "C1 — exemplo (teste)")
        (Path(ex.name) / f"C1{S.SUFFIX}").write_bytes(S.export_snapshot(ro.open(uid)))
        (Path(ex.name) / f"C9{S.SUFFIX}").write_bytes(b"corrompido")
        with mock.patch.dict(os.environ, {E.ENV_ENABLE: "1", E.ENV_DIR: ex.name}):
            app = self.app()
        html = "\n".join(h.proto.body for h in app.get("html"))
        self.assertIn("C1 — exemplo (teste)", html)
        self.assertIn(">Exemplo</span>", html)
        self.assertTrue(any("não é um ZIP válido" in w.value for w in app.warning), [w.value for w in app.warning])
        self.assertTrue(MicrogridRegistry(self.a).exists(uid))


if __name__ == "__main__":
    unittest.main()
