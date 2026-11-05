"""Backend do Piso 1: persistência, validação, backup e adaptador ao orquestrador V1.6.

A persistência é verificada REABRINDO o armazenamento (nova instância e novo processo
Python), não apenas pelo ``st.session_state``.
"""
from __future__ import annotations

import copy
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.store import (ConflictError, IdentityError, MicrogridStore, StoreError, ValidationError,
                                    LATEST_DB_VERSION)
from seeds2_fixtures import v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]


class _TmpStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = MicrogridStore(self.dir)

    def tearDown(self):
        self._tmp.cleanup()


class PersistenciaTest(_TmpStore):
    def test_primeiro_acesso_sem_configuracao(self):
        self.assertIsNone(self.store.load())
        self.assertFalse(self.store.is_commissioned())
        self.assertEqual(self.store.db_version(), LATEST_DB_VERSION)
        self.assertTrue(str(self.store.path).startswith(str(self.dir)))

    def test_salvar_reabrir_recupera_exatamente(self):
        cfg = v16_equivalent_config()
        saved = self.store.save(cfg, 0, note="comissionamento", origin="commissioning")
        self.assertEqual(saved.revision, 1)
        reopened = MicrogridStore(self.dir).load()            # nova instância = reinício da aplicação
        self.assertEqual(reopened.config, json.loads(json.dumps(cfg)))
        self.assertEqual(reopened.revision, 1)
        self.assertEqual(reopened.fingerprint, C.fingerprint(cfg))
        self.assertEqual([e["id"] for e in reopened.config["equipment"]], [e["id"] for e in cfg["equipment"]])

    def test_persistencia_em_outro_processo(self):
        cfg = v16_equivalent_config("Planta persistente")
        self.store.save(cfg, 0)
        code = ("import json,sys; from seeds2.microgrid.store import MicrogridStore; "
                "s=MicrogridStore(sys.argv[1]).load(); "
                "print(json.dumps({'rev': s.revision, 'name': s.config['installation']['name'], "
                "'uid': s.config['installation']['uid'], 'ids': [e['id'] for e in s.config['equipment']], "
                "'params': [e['params'] for e in s.config['equipment']]}))")
        out = subprocess.run([sys.executable, "-c", code, str(self.dir)], cwd=RAIZ, capture_output=True, text=True,
                             env={**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"}, check=True)
        got = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(got["rev"], 1)
        self.assertEqual(got["name"], "Planta persistente")
        self.assertEqual(got["uid"], cfg["installation"]["uid"])
        self.assertEqual(got["ids"], [e["id"] for e in cfg["equipment"]])
        self.assertEqual(got["params"], [e["params"] for e in cfg["equipment"]])

    def test_edicao_preserva_identidade_e_gera_revisao(self):
        cfg = v16_equivalent_config()
        s1 = self.store.save(cfg, 0)
        work = copy.deepcopy(s1.config)
        bat = next(e for e in work["equipment"] if e["kind"] == "battery")
        C.update_equipment(work, bat["id"], params={"soc_min_pct": 25.0})
        s2 = self.store.save(work, s1.revision, note="ajuste SOC")
        self.assertEqual(s2.revision, 2)
        self.assertEqual(s2.config["installation"]["uid"], cfg["installation"]["uid"])
        self.assertNotEqual(s2.fingerprint, s1.fingerprint)
        with sqlite3.connect(self.store.path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM microgrid").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM revisions").fetchone()[0], 2)
        # salvar sem mudanças não cria revisão nova
        self.assertEqual(self.store.save(copy.deepcopy(s2.config), 2).revision, 2)
        self.assertEqual(self.store.get_revision(1).config["equipment"][4]["params"]["soc_min_pct"], 20.0)

    def test_tabela_aceita_uma_unica_microrrede(self):
        self.store.save(v16_equivalent_config(), 0)
        with sqlite3.connect(self.store.path) as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO microgrid(id, installation_uid, revision, fingerprint, document, saved_at) "
                            "VALUES (2, 'x', 1, 'f', '{}', 'now')")

    def test_outra_instalacao_e_recusada_no_salvamento(self):
        s = self.store.save(v16_equivalent_config("A"), 0)
        with self.assertRaises(IdentityError):
            self.store.save(v16_equivalent_config("B"), s.revision)

    def test_conflito_de_concorrencia_nao_sobrescreve(self):
        s1 = self.store.save(v16_equivalent_config(), 0)
        a, b = copy.deepcopy(s1.config), copy.deepcopy(s1.config)
        a["installation"]["description"] = "sessão A"
        b["installation"]["description"] = "sessão B"
        self.store.save(a, s1.revision)
        with self.assertRaises(ConflictError):
            self.store.save(b, s1.revision)
        self.assertEqual(MicrogridStore(self.dir).load().config["installation"]["description"], "sessão A")

    def test_revisoes_sao_imutaveis(self):
        self.store.save(v16_equivalent_config(), 0)
        with sqlite3.connect(self.store.path) as con:
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("UPDATE revisions SET note = 'x'")
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("DELETE FROM revisions")

    def test_reversao_cria_revisao_nova(self):
        s1 = self.store.save(v16_equivalent_config(), 0)
        w = copy.deepcopy(s1.config)
        C.retire_equipment(w, w["equipment"][0]["id"], "teste")
        s2 = self.store.save(w, 1)
        s3 = self.store.revert_to(1, s2.revision)
        self.assertEqual(s3.revision, 3)
        self.assertEqual(s3.fingerprint, s1.fingerprint)
        self.assertEqual(self.store.history()[0]["origin"], "revert")

    def test_banco_mais_novo_e_recusado(self):
        with sqlite3.connect(self.store.path) as con:
            con.execute(f"PRAGMA user_version = {LATEST_DB_VERSION + 1}")
        with self.assertRaises(StoreError):
            MicrogridStore(self.dir)

    def test_blobs_integridade_e_referencia(self):
        data = b"t_min,P_kW\n" + b"".join(f"{i},{50 + i}\n".encode() for i in range(30))
        h = self.store.put_blob(data, "carga.csv")
        self.assertEqual(MicrogridStore(self.dir).get_blob(h), data)
        cfg = v16_equivalent_config()
        cfg["demand"].update(source="csv", provenance="medido",
                             csv={"blob": "0" * 64, "filename": "x.csv", "start_min": 0, "duration_min": 20})
        with self.assertRaises(StoreError):
            self.store.save(cfg, 0)                       # blob inexistente não pode ser referenciado
        cfg["demand"]["csv"]["blob"] = h
        self.assertEqual(self.store.save(cfg, 0).revision, 1)

    def test_registro_de_rodada_com_procedencia(self):
        s = self.store.save(v16_equivalent_config(), 0)
        rid = self.store.record_run(config_revision=s.revision, config_fingerprint=s.fingerprint, spec_fingerprint="ab" * 32,
                                    spec_origin="microrrede", excluded=[{"id": "eq-x"}], summary={"custo": 1.0})
        run = MicrogridStore(self.dir).runs()[0]
        self.assertEqual((run["run_id"], run["config_revision"], run["config_fingerprint"]), (rid, 1, s.fingerprint))
        self.assertEqual(run["excluded"], [{"id": "eq-x"}])


class ValidacaoTest(unittest.TestCase):
    def test_configuracao_de_teste_e_valida(self):
        self.assertEqual(C.errors(C.validate(v16_equivalent_config())), [])

    def test_restricoes_fisicas_e_identificadores(self):
        cfg = v16_equivalent_config()
        bat = next(e for e in cfg["equipment"] if e["kind"] == "battery")
        bat["params"].update(soc_min_pct=80.0, soc_max_pct=50.0)
        cfg["equipment"][0]["arrays"][0]["n_series"] = 0
        cfg["equipment"][1]["id"] = cfg["equipment"][0]["id"]
        th = C.new_equipment("thermal", "Gerador", params={"dynamic": "local_generator", "pmax_kW": 10.0, "pmin_kW": 20.0})
        cfg["equipment"].append(th)
        cfg["installation"]["location"]["latitude"] = 123.0
        cfg["installation"]["location"]["longitude"] = 0.0
        cfg["installation"]["location"]["timezone"] = "Marte/Olympus"
        bat["params"]["capacity_Ah"] = -5.0
        cfg["run_conditions"]["battery_soc0_pct"][bat["id"]] = 140.0
        msgs = " | ".join(f"{i.path}: {i.message}" for i in C.errors(C.validate(cfg)))
        for esperado in ("SOC mínimo deve ser menor", "n_series", "Identificador duplicado",
                         "mínima técnica não pode superar", "latitude", "Fuso horário", "Capacidade nominal",
                         "SOC inicial deve estar entre"):
            self.assertIn(esperado, msgs)

    def test_referencias_inexistentes_e_parametros_desconhecidos(self):
        cfg = v16_equivalent_config()
        cfg["equipment"][0]["arrays"][0]["reference"] = "MODULO-INVENTADO"
        cfg["equipment"][1]["arrays"][0]["inventado"] = 1
        cfg["equipment"][2]["params"]["inventado"] = 1
        msgs = " | ".join(i.message for i in C.errors(C.validate(cfg)))
        self.assertIn("não pertence às referências", msgs)
        self.assertIn("Parâmetro desconhecido", msgs)
        self.assertIn("Campo desconhecido para arranjo", msgs)

    def test_valores_ausentes_sao_permitidos_mas_incompletos(self):
        eq = C.new_equipment("battery", "Banco sem dados")
        self.assertEqual(C.errors(C.equipment_issues(eq)), [])
        self.assertFalse(C.is_configured(eq))
        self.assertIn("Células em série (Ns)", C.missing_required(eq))
        self.assertIsNone(eq["params"]["model_n_series"])                 # nada é presumido
        self.assertIsNone(eq["params"]["energy_kWh"])
        self.assertNotIn("soc0_pct", eq["params"])                         # SOC inicial não é dado do inventário
        plant = C.new_equipment("pv", "Usina sem arranjos")
        self.assertEqual(C.errors(C.equipment_issues(plant)), [])
        self.assertEqual(C.missing_required(plant), ["ao menos um arranjo"])

    def test_perfil_de_referencia_nao_pode_ser_medido(self):
        cfg = v16_equivalent_config()
        cfg["demand"]["provenance"] = "medido"
        self.assertTrue(any("não podem ser declarados como medidos" in i.message for i in C.errors(C.validate(cfg))))

    def test_inventario_incorporar_e_retirar(self):
        cfg = v16_equivalent_config()
        n = len(cfg["equipment"])
        eq = C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador novo", params={"reference": "EWT DW61-1MW", "count": 1}))
        self.assertEqual(len(cfg["equipment"]), n + 1)
        C.retire_equipment(cfg, eq["id"], "desmontado")
        self.assertEqual(len(cfg["equipment"]), n)
        self.assertEqual(cfg["retired"][-1]["id"], eq["id"])
        self.assertEqual(C.errors(C.validate(cfg)), [])
        bat = next(e for e in cfg["equipment"] if e["kind"] == "battery")
        C.retire_equipment(cfg, bat["id"])                                   # condição de rodada do banco sai junto
        self.assertNotIn(bat["id"], cfg["run_conditions"]["battery_soc0_pct"])
        self.assertEqual(C.errors(C.validate(cfg)), [])
        with self.assertRaises(ValueError):
            C.update_equipment(cfg, cfg["equipment"][0]["id"], kind="wind")


class BackupTest(_TmpStore):
    def _zip(self, files: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for k, v in files.items():
                zf.writestr(k, v)
        return buf.getvalue()

    def _files(self, data: bytes) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return {n: zf.read(n) for n in zf.namelist()}

    def test_exportar_e_restaurar_em_instalacao_nova(self):
        csv = b"t_min,P_kW\n" + b"".join(f"{i},{40 + (i % 7)}\n".encode() for i in range(60))
        h = self.store.put_blob(csv, "carga.csv")
        cfg = v16_equivalent_config()
        cfg["demand"].update(source="csv", provenance="medido",
                             csv={"blob": h, "filename": "carga.csv", "start_min": 0, "duration_min": 50})
        s = self.store.save(cfg, 0)
        data = self.store.export_backup()
        with tempfile.TemporaryDirectory() as other:
            dst = MicrogridStore(other)
            rep = dst.inspect_backup(data)
            self.assertTrue(rep.ok, rep.errors)
            with self.assertRaises(StoreError):
                dst.restore_backup(data, 0, confirm=False)
            r = dst.restore_backup(data, 0, confirm=True)
            self.assertEqual(r.fingerprint, s.fingerprint)
            self.assertEqual(MicrogridStore(other).get_blob(h), csv)
            self.assertEqual(dst.history()[0]["origin"], "restore")

    def test_nome_do_backup_e_ascii_portavel(self):
        from seeds2.microgrid.store import BACKUP_SUFFIX, backup_filename

        name = backup_filename({"installation": {"name": "Laboratório de Microrredes — Bloco C / Ação"}})
        self.assertTrue(name.isascii())
        self.assertTrue(name.startswith("seeds2_Laboratorio_de_Microrredes_Bloco_C_Acao_"))
        self.assertTrue(name.endswith(BACKUP_SUFFIX))
        self.assertNotIn("/", name)

    def test_restaurar_sobre_a_mesma_instalacao_preserva_historico(self):
        s1 = self.store.save(v16_equivalent_config(), 0)
        data = self.store.export_backup()
        w = copy.deepcopy(s1.config)
        C.retire_equipment(w, w["equipment"][0]["id"])
        s2 = self.store.save(w, 1)
        r = self.store.restore_backup(data, s2.revision, confirm=True)
        self.assertEqual((r.revision, r.fingerprint), (3, s1.fingerprint))
        self.assertEqual(len(self.store.history()), 3)

    def test_restaurar_outra_instalacao_exige_confirmacao_de_identidade(self):
        self.store.save(v16_equivalent_config("Atual"), 0)
        with tempfile.TemporaryDirectory() as other:
            o = MicrogridStore(other)
            o.save(v16_equivalent_config("Outra"), 0)
            data = o.export_backup()
        rep = self.store.inspect_backup(data)
        self.assertTrue(rep.ok)
        self.assertFalse(rep.same_installation)
        with self.assertRaises(IdentityError):
            self.store.restore_backup(data, 1, confirm=True)
        r = self.store.restore_backup(data, 1, confirm=True, confirm_identity_change=True)
        self.assertEqual(r.config["installation"]["name"], "Outra")

    def test_importacoes_invalidas_sao_rejeitadas(self):
        self.store.save(v16_equivalent_config(), 0)
        good = self.store.export_backup()
        files = self._files(good)
        casos = {}
        casos["não-zip"] = b"isto nao e um zip"
        casos["sem manifesto"] = self._zip({"configuration.json": files["configuration.json"]})
        m = json.loads(files["manifest.json"]); m["format"] = "outro-software"
        casos["formato"] = self._zip({**files, "manifest.json": json.dumps(m).encode()})
        m = json.loads(files["manifest.json"]); m["format_version"] = 99
        casos["versão de formato"] = self._zip({**files, "manifest.json": json.dumps(m).encode()})
        cfg = json.loads(files["configuration.json"]); cfg["equipment"][0]["params"]["n_series"] = -3
        casos["adulterado (hash)"] = self._zip({**files, "configuration.json": json.dumps(cfg).encode()})
        # adulteração consistente (hashes recalculados) ainda é barrada pela validação física
        from hashlib import sha256
        body = json.dumps(cfg).encode()
        m = json.loads(files["manifest.json"]); m["files"]["configuration.json"] = sha256(body).hexdigest()
        m["fingerprint"] = C.fingerprint(cfg)
        casos["inválido fisicamente"] = self._zip({**files, "configuration.json": body, "manifest.json": json.dumps(m).encode()})
        cfg2 = json.loads(files["configuration.json"]); cfg2["schema_version"] = 7
        body2 = json.dumps(cfg2).encode()
        m2 = json.loads(files["manifest.json"]); m2["files"]["configuration.json"] = sha256(body2).hexdigest()
        m2["fingerprint"] = C.fingerprint(cfg2)
        casos["esquema incompatível"] = self._zip({**files, "configuration.json": body2, "manifest.json": json.dumps(m2).encode()})
        casos["caminho malicioso"] = self._zip({**files, "../fora.txt": b"x"})
        rev = self.store.load().revision
        for nome, data in casos.items():
            with self.subTest(nome):
                self.assertFalse(self.store.inspect_backup(data).ok)
                with self.assertRaises(StoreError):
                    self.store.restore_backup(data, rev, confirm=True)
        self.assertEqual(self.store.load().revision, rev)            # nada foi alterado


class BackupMaliciosoTest(_TmpStore):
    """Entradas maliciosas ou estruturalmente incorretas: rejeição controlada, sem exceções e sem efeitos."""

    def setUp(self):
        super().setUp()
        self.csv = b"t_min,P_kW\n" + b"".join(f"{i},{40 + (i % 7)}\n".encode() for i in range(60))
        h = self.store.put_blob(self.csv, "carga.csv")
        cfg = v16_equivalent_config()
        cfg["demand"].update(source="csv", provenance="medido",
                             csv={"blob": h, "filename": "carga.csv", "start_min": 0, "duration_min": 50})
        self.saved = self.store.save(cfg, 0)
        self.good = self.store.export_backup()
        with zipfile.ZipFile(io.BytesIO(self.good)) as zf:
            self.files = {n: zf.read(n) for n in zf.namelist()}
        self.manifest = json.loads(self.files["manifest.json"])
        self.blob_name = next(n for n in self.files if n.startswith("blobs/"))

    @staticmethod
    def _zip(entries, method=zipfile.ZIP_DEFLATED) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", method) as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return buf.getvalue()

    def _with(self, **replace) -> bytes:
        files = {**self.files, **replace}
        return self._zip(files.items())

    def _consistent(self, cfg: dict) -> bytes:
        """Configuração adulterada com hashes e impressão digital recalculados (passa a integridade)."""
        from hashlib import sha256

        body = json.dumps(cfg).encode()
        m = copy.deepcopy(self.manifest)
        m["files"]["configuration.json"] = sha256(body).hexdigest()
        m["fingerprint"] = C.fingerprint(cfg)
        return self._with(**{"configuration.json": body, "manifest.json": json.dumps(m).encode()})

    def _assert_rejected(self, data, nome: str):
        with self.subTest(nome):
            rep = self.store.inspect_backup(data)                     # nunca levanta exceção
            self.assertFalse(rep.ok, nome)
            self.assertTrue(rep.errors, nome)
            self.assertIsNone(rep.config)
            self.assertEqual(rep.blobs, {})
            with self.assertRaises(StoreError):
                self.store.restore_backup(data, self.saved.revision, confirm=True, confirm_identity_change=True)

    def _db_state(self):
        with sqlite3.connect(self.store.path) as con:
            return (con.execute("SELECT revision, fingerprint FROM microgrid").fetchall(),
                    con.execute("SELECT COUNT(*) FROM revisions").fetchone()[0],
                    con.execute("SELECT COUNT(*) FROM blobs").fetchone()[0])

    def test_backup_valido_de_referencia_e_aceito(self):
        self.assertTrue(self.store.inspect_backup(self.good).ok)

    def test_zip_malformado_e_bombas(self):
        import warnings

        antes = self._db_state()
        warnings.filterwarnings("ignore", "Duplicate name", UserWarning)  # ZIP duplicado é proposital
        casos = {
            "bytes aleatórios com assinatura PK": b"PK\x03\x04" + os.urandom(300),
            "ZIP truncado": self.good[: len(self.good) // 2],
            "ZIP vazio": self._zip([]),
            "tipo não-bytes": "texto",
            "entradas demais": self._zip([*self.files.items()] + [(f"blobs/{i:064x}", b"x") for i in range(20)]),
            "entrada duplicada": self._zip([*self.files.items(), ("configuration.json", self.files["configuration.json"])]),
            "diretório": self._zip([*self.files.items(), ("blobs/", b"")]),
            "nome de blob inválido": self._zip([*self.files.items(), ("blobs/abc", b"x")]),
            "caminho malicioso": self._zip([*self.files.items(), ("../fora.txt", b"x")]),
            "bomba: JSON > limite": self._with(**{"history.json": b"[" + b" " * (9 * 1024 * 1024) + b"]"}),
            "bomba: blob > limite": self._with(**{self.blob_name: b"0" * (51 * 1024 * 1024)}),
            "compressão não suportada": self._zip(self.files.items(), method=zipfile.ZIP_LZMA),
        }
        for nome, data in casos.items():
            self._assert_rejected(data, nome)
        self.assertEqual(self._db_state(), antes)

    def test_tamanho_declarado_falso_nao_engana_a_leitura(self):
        # Entrada cujo cabeçalho declara 10 bytes, mas cujo conteúdo real é muito maior (CRC divergente).
        big = b"[" + b" " * 2_000_000 + b"]"
        data = bytearray(self._with(**{"history.json": big}))
        size = len(big).to_bytes(4, "little")
        assert data.count(size) == 2                                  # cabeçalho local + diretório central
        data = bytes(data).replace(size, (10).to_bytes(4, "little"))
        self._assert_rejected(data, "tamanho declarado falso")

    def test_leitura_limitada_por_blocos(self):
        from seeds2.microgrid.store import _BackupRejected

        zf = zipfile.ZipFile(io.BytesIO(self.good))
        info = zf.getinfo("configuration.json")
        with self.assertRaises(_BackupRejected):
            MicrogridStore._read_capped(zf, info, 100, [10**9])            # limite por entrada
        with self.assertRaises(_BackupRejected):
            MicrogridStore._read_capped(zf, info, 10**9, [100])            # limite do total descomprimido

    def test_entrada_criptografada_e_rejeitada(self):
        # Marca o bit "criptografado" (bit 0 dos flags) nos cabeçalhos local e central de todas as entradas.
        data = bytearray(self.good)
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            i = data.find(sig)
            while i != -1:
                data[i + off] |= 0x1
                i = data.find(sig, i + 4)
        self.assertTrue(all(i.flag_bits & 0x1 for i in zipfile.ZipFile(io.BytesIO(bytes(data))).infolist()))
        self._assert_rejected(bytes(data), "criptografado")

    def test_tipos_e_estrutura_do_manifesto(self):
        m = self.manifest
        variantes = {
            "manifesto não-objeto": [1, 2],
            "files como lista": {**m, "files": list(m["files"])},
            "files vazio": {**m, "files": {}},
            "files com hash não-hex": {**m, "files": {**m["files"], "configuration.json": "zz"}},
            "files com entrada proibida": {**m, "files": {**m["files"], "../x": "0" * 64}},
            "blobs como lista": {**m, "blobs": []},
            "blobs com metadado não-objeto": {**m, "blobs": {k: "x" for k in m["blobs"]}},
            "blobs com tamanho textual": {**m, "blobs": {k: {**v, "size": "10"} for k, v in m["blobs"].items()}},
            "format_version texto": {**m, "format_version": "1"},
            "db_schema_version texto": {**m, "db_schema_version": "x"},
            "db_schema_version futura": {**m, "db_schema_version": 99},
            "doc_schema_version ausente": {k: v for k, v in m.items() if k != "doc_schema_version"},
            "revision booleana": {**m, "revision": True},
            "revision negativa": {**m, "revision": -1},
            "uid numérico": {**m, "installation_uid": 123},
            "fingerprint numérica": {**m, "fingerprint": 123},
            "created_at lista": {**m, "created_at": ["x"]},
            "nome gigante": {**m, "installation_name": "x" * 10_000},
            "uid divergente da configuração": {**m, "installation_uid": "0" * 32},
        }
        for nome, man in variantes.items():
            self._assert_rejected(self._with(**{"manifest.json": json.dumps(man).encode()}), nome)
        self._assert_rejected(self._with(**{"manifest.json": b"\xff\xfe nao utf8"}), "manifesto não-UTF-8")
        self._assert_rejected(self._with(**{"manifest.json": b"{nao json"}), "manifesto não-JSON")

    def test_configuracao_estruturalmente_incorreta(self):
        base = json.loads(self.files["configuration.json"])
        def mut(fn):
            c = copy.deepcopy(base)
            fn(c)
            return c
        variantes = {
            "equipment como objeto": mut(lambda c: c.__setitem__("equipment", {})),
            "equipment com inteiros": mut(lambda c: c.__setitem__("equipment", [1, 2])),
            "referência como lista": mut(lambda c: c["equipment"][0]["arrays"][0].__setitem__("reference", ["x"])),
            "parâmetro como objeto": mut(lambda c: c["equipment"][0]["arrays"][0].__setitem__("n_series", {"a": 1})),
            "arranjos como objeto": mut(lambda c: c["equipment"][0].__setitem__("arrays", {})),
            "balanço como lista": mut(lambda c: c.__setitem__("energy_balance", [])),
            "condições como lista": mut(lambda c: c["run_conditions"].__setitem__("battery_soc0_pct", [])),
            "localização como texto": mut(lambda c: c["installation"].__setitem__("location", "x")),
            "installation como texto": mut(lambda c: c.__setitem__("installation", "x")),
            "natureza como lista": mut(lambda c: c["installation"].__setitem__("nature", ["industrial"])),
            "demanda csv como texto": mut(lambda c: c["demand"].__setitem__("csv", "x")),
            "walkforward como lista vazia": mut(lambda c: c["demand"].__setitem__("walkforward", [])),
            "commissioning.completed texto": mut(lambda c: c["commissioning"].__setitem__("completed", "sim")),
            "tag numérica": mut(lambda c: c["equipment"][0].__setitem__("tag", 7)),
        }
        for nome, cfg in variantes.items():
            self.assertTrue(C.errors(C.validate(cfg)), nome)               # validação não levanta exceção
            self._assert_rejected(self._consistent(cfg), nome)
        cfg_list = [base]
        from hashlib import sha256
        body = json.dumps(cfg_list).encode()
        m = copy.deepcopy(self.manifest)
        m["files"]["configuration.json"] = sha256(body).hexdigest()
        self._assert_rejected(self._with(**{"configuration.json": body, "manifest.json": json.dumps(m).encode()}),
                              "configuração não-objeto")

    def test_entradas_nao_declaradas_ou_nao_referenciadas(self):
        from hashlib import sha256

        extra = b"dado estranho"
        d = sha256(extra).hexdigest()
        self._assert_rejected(self._with(**{f"blobs/{d}": extra}), "blob não declarado no manifesto")
        m = copy.deepcopy(self.manifest)
        m["files"][f"blobs/{d}"] = d
        self._assert_rejected(self._with(**{f"blobs/{d}": extra, "manifest.json": json.dumps(m).encode()}),
                              "blob declarado mas não referenciado")
        self._assert_rejected(self._with(**{"history.json": b'{"x": 1}'}), "history com estrutura inválida")


class RestauracaoAtomicaTest(_TmpStore):
    """A restauração grava dados de entrada e configuração na MESMA transação: tudo ou nada."""

    def setUp(self):
        super().setUp()
        self.cfg = v16_equivalent_config("Instalação alvo")
        self.store.save(self.cfg, 0)                                   # revisão 1, sem CSV
        self.csv = b"t_min,P_kW\n" + b"".join(f"{i},{70 + i % 5}\n".encode() for i in range(40))
        with tempfile.TemporaryDirectory() as other:                  # backup da MESMA instalação, com blob novo
            src = MicrogridStore(other)
            h = src.put_blob(self.csv, "medicao.csv")
            cfg2 = copy.deepcopy(self.cfg)
            cfg2["demand"].update(source="csv", provenance="medido",
                                  csv={"blob": h, "filename": "medicao.csv", "start_min": 0, "duration_min": 30})
            src.save(cfg2, 0)
            self.data = src.export_backup()
        self.digest = h

    def _counts(self):
        with sqlite3.connect(self.store.path) as con:
            return (con.execute("SELECT revision FROM microgrid").fetchone()[0],
                    con.execute("SELECT COUNT(*) FROM revisions").fetchone()[0],
                    con.execute("SELECT COUNT(*) FROM blobs").fetchone()[0])

    def test_conflito_de_revisao_nao_persiste_blobs(self):
        w = copy.deepcopy(self.store.load().config)
        w["installation"]["description"] = "outra sessão salvou antes"
        self.store.save(w, 1)                                          # revisão 2
        antes = self._counts()
        self.assertEqual(antes, (2, 2, 0))
        with self.assertRaises(ConflictError):
            self.store.restore_backup(self.data, 1, confirm=True)      # base desatualizada
        self.assertEqual(self._counts(), antes)
        with self.assertRaises(StoreError):
            MicrogridStore(self.dir).get_blob(self.digest)             # nenhum blob órfão

    def test_troca_de_identidade_nao_confirmada_nao_persiste_blobs(self):
        with tempfile.TemporaryDirectory() as other:
            src = MicrogridStore(other)
            h = src.put_blob(self.csv, "x.csv")
            cfg = v16_equivalent_config("Outra instalação")
            cfg["demand"].update(source="csv", provenance="medido",
                                 csv={"blob": h, "filename": "x.csv", "start_min": 0, "duration_min": 30})
            src.save(cfg, 0)
            data = src.export_backup()
        antes = self._counts()
        with self.assertRaises(IdentityError):
            self.store.restore_backup(data, 1, confirm=True, confirm_identity_change=False)
        self.assertEqual(self._counts(), antes)

    def test_falha_ao_gravar_revisao_desfaz_blobs(self):
        with sqlite3.connect(self.store.path) as con:
            con.execute("CREATE TRIGGER falha_teste BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'falha simulada'); END")
        antes = self._counts()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                self.store.restore_backup(self.data, 1, confirm=True)
            self.assertEqual(self._counts(), antes)
        finally:
            with sqlite3.connect(self.store.path) as con:
                con.execute("DROP TRIGGER falha_teste")

    def test_restauracao_bem_sucedida_grava_tudo_junto(self):
        r = self.store.restore_backup(self.data, 1, confirm=True)
        self.assertEqual(r.revision, 2)
        self.assertEqual(self._counts(), (2, 2, 1))
        self.assertEqual(MicrogridStore(self.dir).get_blob(self.digest), self.csv)


class AdaptadorTest(unittest.TestCase):
    def test_configuracao_equivalente_reproduz_spec_v16(self):
        from orchestrator_runtime import default_model_spec

        plan = A.build_plan(v16_equivalent_config())
        self.assertTrue(plan.runnable, plan.blockers)
        self.assertFalse(plan.needs_ack)
        ref = default_model_spec()
        for key in ("solar", "fc", "battery"):
            self.assertEqual(plan.spec[key], ref[key], key)
        self.assertFalse(plan.spec["wind"]["active"])
        self.assertFalse(plan.spec["thermal"]["active"])
        self.assertEqual(plan.spec["climate"], ref["climate"])
        self.assertEqual(len(plan.represented), 6)

    def test_equipamentos_nao_representaveis_sao_identificados(self):
        from seeds2_fixtures import module_array, pv_plant

        cfg = v16_equivalent_config()
        C.add_equipment(cfg, pv_plant("Usina heterogênea", module_array("Arranjo B", "CS3W-450MS", 3, 2, 2.0)))
        C.add_equipment(cfg, C.new_equipment("thermal", "UTE", params={
            "dynamic": "thermal_plant", "pmax_kW": 500.0, "pmin_kW": 100.0, "cvu_rs_MWh": 420.0, "startup_cost_rs": 0.0}))
        C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador sem dados"))
        off = C.add_equipment(cfg, C.new_equipment("thermal", "Diesel reserva", enabled=False, params={
            "dynamic": "local_generator", "pmax_kW": 80.0, "pmin_kW": 20.0, "cvu_rs_MWh": 1100.0, "startup_cost_rs": 50.0}))
        plan = A.build_plan(cfg)
        st = {m.name: m.status for m in plan.mappings}
        n_units = sum(len(e["arrays"]) if e["kind"] == "pv" else 1 for e in cfg["equipment"])
        self.assertEqual(len(plan.mappings), n_units)                    # nenhum omitido (FV: por arranjo)
        self.assertEqual(st["Usina heterogênea · Arranjo B"], A.INCOMPATIBLE)
        self.assertEqual(st["Arranjo FV 1 · Arranjo 01"], A.INCOMPATIBLE)  # grupo heterogêneo: nenhum escolhido
        self.assertEqual(st["UTE"], A.INCOMPATIBLE)
        self.assertEqual(st["Aerogerador sem dados"], A.INCOMPLETE)
        self.assertEqual(st[off["name"]], A.DISABLED)
        self.assertFalse(plan.spec["solar"]["active"])
        self.assertEqual(plan.pv_represented_kWp, 0.0)
        self.assertAlmostEqual(plan.pv_installed_kWp, 11.8 + 0.45 * 6)     # instalado ≠ simulado
        self.assertTrue(plan.needs_ack)
        self.assertEqual({m.name for m in plan.excluded},
                         {"Usina heterogênea · Arranjo B", "Arranjo FV 1 · Arranjo 01", "Arranjo FV 2 · Arranjo 01",
                          "UTE", "Aerogerador sem dados"})
        self.assertTrue(all(m.reason for m in plan.excluded))

    def test_bloqueios_sem_despachavel_ou_sem_demanda(self):
        cfg = v16_equivalent_config()
        for e in cfg["equipment"]:
            if e["kind"] in ("battery", "pemfc"):
                e["enabled"] = False
        cfg["demand"]["source"] = "nao_definida"
        plan = A.build_plan(cfg)
        self.assertFalse(plan.runnable)
        self.assertEqual(len(plan.blockers), 2)

    def test_impressao_digital_muda_com_a_configuracao(self):
        cfg = v16_equivalent_config()
        p1 = A.build_plan(cfg).spec_fingerprint
        cfg["equipment"][0]["params"]["n_parallel"] = 6
        self.assertNotEqual(A.build_plan(cfg).spec_fingerprint, p1)


class RodadaIntegradaTest(_TmpStore):
    def test_rodada_ems_real_com_configuracao_persistida(self):
        import orchestrator_runtime as RT

        s = self.store.save(v16_equivalent_config(), 0)
        loaded = MicrogridStore(self.dir).load()
        plan = A.build_plan(loaded.config, revision=loaded.revision, fingerprint=loaded.fingerprint)
        self.assertTrue(plan.runnable)
        carga = A.build_load(plan.load_descriptor, self.store.get_blob)
        opt = RT.default_optimizer_config()
        with tempfile.TemporaryDirectory() as pkg:
            path, outputs = RT.build_exchange_package(carga, plan.spec, opt, destino=Path(pkg))
            r, _ = RT.run_optimizer(path, opt)
        self.assertEqual(r["k_validos"], len(carga.P_kW))
        self.assertEqual(sorted(r["nomes"]), ["bateria", "fc"])
        self.assertTrue(np.all(np.isfinite(r["P_kW"][:r["k_validos"]])))
        # mesma rodada que o console V1.6 produziria com sua configuração padrão
        with tempfile.TemporaryDirectory() as pkg2:
            path2, _ = RT.build_exchange_package(carga, RT.default_model_spec(), opt, destino=Path(pkg2))
            r2, _ = RT.run_optimizer(path2, opt)
        np.testing.assert_allclose(r["P_kW"], r2["P_kW"])
        self.assertAlmostEqual(r["rel"]["custo_total_rs"], r2["rel"]["custo_total_rs"])
        self.assertEqual(plan.provenance()["config_revision"], s.revision)


if __name__ == "__main__":
    unittest.main()
