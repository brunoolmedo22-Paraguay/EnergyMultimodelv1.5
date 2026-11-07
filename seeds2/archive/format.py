"""Contrato do pacote do Arquivo Científico (``seeds2-study``, formato v1) e inspeção de pacotes NÃO confiáveis.

Estrutura exata (todas as entradas são arquivos; nenhum diretório, link ou caminho absoluto)::

    manifest.json                                   índice: identidade de origem, contagens, recursos (SHA-256, tamanho,
                                                    tipo, papel) e grafo de dependências
    scenario/scenario.json                          linha ATUAL do cenário (sem documento): identidade, nome, datas
    scenario/versions/v000001.json                  metadados de cada versão (imutáveis na origem)
    scenario/versions/v000001.document.json         documento da versão — texto EXATO gravado na origem
    inventory/revisions/r000003.json                metadados de cada revisão do inventário referenciada
    inventory/revisions/r000003.document.json       documento da revisão — texto EXATO gravado na origem
    inventory/blobs/<sha256>                        dados de entrada referenciados pelas revisões (CSV, pacotes ModelLab)
    inventory/catalog_references.json               instantâneo das referências de catálogo usadas (somente leitura)
    forecasts/blobs/<sha256>                        séries normalizadas e arquivos originais das previsões (Piso 2B)
    runs/<run_uid>/run.json                         linha da rodada: identidade, estado, datas, progresso, índice de dados
    runs/<run_uid>/manifest.json                    manifesto de procedência — texto EXATO gravado na origem
    runs/<run_uid>/outcome.json | summary.json | error.json   (quando existem na origem; texto exato)
    runs/<run_uid>/data/<nome>                      séries e dados da rodada (``scenario_run_data``), descomprimidos

Regras: todo arquivo (exceto ``manifest.json``) é declarado em ``manifest.resources`` com SHA-256 e tamanho; nenhum
recurso declarado pode faltar e nenhum arquivo não declarado é aceito; os blobs são endereçados pelo próprio SHA-256;
os documentos têm a impressão digital (``config.fingerprint``) conferida; as relações cenário ↔ versões ↔ revisões ↔
previsões ↔ rodadas são verificadas. O SHA-256 detecta corrupção e inconsistência — **não é assinatura digital** nem
prova de autoria.

Compatibilidade: este leitor aceita ``format_version`` ∈ ``SUPPORTED_FORMAT_VERSIONS``. Um pacote de versão mais nova é
recusado com explicação (nunca lido parcialmente). A compatibilidade é de LEITURA: a inspeção não valida os documentos
contra as regras de edição/execução atuais (que podem mudar), apenas a estrutura mínima de que o visualizador precisa.
"""
from __future__ import annotations

import io
import json
import os
import re
import stat
import zipfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import IO, Any, Iterator

from seeds2.microgrid import config as C

FORMAT = "seeds2-study"
FORMAT_VERSION = 1
SUPPORTED_FORMAT_VERSIONS = (1,)
SUFFIX = ".seeds2study.zip"
RUN_FINAL_STATES = ("concluida", "falhou", "interrompida")
INTEGRITY_NOTE = ("O SHA-256 de cada recurso permite detectar corrupção acidental e inconsistências internas do pacote. "
                  "Não é uma assinatura digital: não comprova autoria nem autenticidade.")

# ------------------------------------------------------------------ limites (arquivo NÃO confiável)
MAX_PACKAGE_BYTES = 512 * 1024 * 1024          # tamanho do .zip
MAX_TOTAL_UNCOMPRESSED = 1024 * 1024 * 1024    # soma dos conteúdos descomprimidos (contada lendo, não declarada)
MAX_ENTRY_BYTES = 256 * 1024 * 1024            # um recurso de dados
MAX_JSON_BYTES = 32 * 1024 * 1024              # um documento JSON
MAX_ENTRIES = 20_000
MAX_JSON_DEPTH = 100
MAX_RATIO = 1000                               # compressão > 1000:1 em entradas > 1 MiB = suspeita de bomba ZIP
RATIO_MIN_BYTES = 1024 * 1024
_CHUNK = 1024 * 1024

# ------------------------------------------------------------------ nomes permitidos
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_SEG = r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,99}"
RUN_DATA_NAME = re.compile(rf"(?:{_SEG}/){{0,2}}{_SEG}\.(?:csv|json|zip|txt)")
_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"scenario/scenario\.json"), "scenario", "application/json"),
    (re.compile(r"scenario/versions/v(\d{6})\.json"), "version_meta", "application/json"),
    (re.compile(r"scenario/versions/v(\d{6})\.document\.json"), "version_document", "application/json"),
    (re.compile(r"inventory/revisions/r(\d{6})\.json"), "revision_meta", "application/json"),
    (re.compile(r"inventory/revisions/r(\d{6})\.document\.json"), "revision_document", "application/json"),
    (re.compile(r"inventory/blobs/([0-9a-f]{64})"), "inventory_blob", ""),
    (re.compile(r"inventory/catalog_references\.json"), "catalog_references", "application/json"),
    (re.compile(r"forecasts/blobs/([0-9a-f]{64})"), "forecast_blob", ""),
    (re.compile(r"runs/([0-9a-f]{32})/(run|manifest|outcome|summary|error)\.json"), "run_json", "application/json"),
    (re.compile(rf"runs/([0-9a-f]{{32}})/data/({RUN_DATA_NAME.pattern})"), "run_data", ""),
]
BLOB_MEDIA_TYPES = ("text/csv", "application/json", "application/zip", "text/plain", "application/octet-stream")
DATA_MEDIA_TYPES = {".csv": "text/csv", ".json": "application/json", ".zip": "application/zip", ".txt": "text/plain"}
_EXEC_MAGIC = (b"\x7fELF", b"MZ", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
               b"\xca\xfe\xba\xbe", b"#!")


def classify(path: str) -> tuple[str, tuple[str, ...]] | None:
    """Papel de um caminho do pacote (ou ``None`` se não permitido) e os grupos capturados."""
    for rx, role, _mt in _PATTERNS:
        m = rx.fullmatch(path)
        if m:
            return role, m.groups()
    return None


def version_path(v: int, document: bool = False) -> str:
    return f"scenario/versions/v{int(v):06d}{'.document' if document else ''}.json"


def revision_path(r: int, document: bool = False) -> str:
    return f"inventory/revisions/r{int(r):06d}{'.document' if document else ''}.json"


def expected_media_type(path: str) -> str | None:
    c = classify(path)
    if c is None:
        return None
    for rx, role, mt in _PATTERNS:
        if role == c[0]:
            if mt:
                return mt
            if role == "run_data":
                return DATA_MEDIA_TYPES[os.path.splitext(path)[1]]
            return None                                    # blobs: tipo declarado (lista permitida)
    return None


def safe_filename(name: str, uid: str) -> str:
    """Nome ASCII portátil para o pacote exportado (sem caminho; 8 dígitos do UID do cenário)."""
    import unicodedata
    from datetime import datetime

    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]", "_", ascii_name))[:48].strip("_") or "cenario"
    return f"{safe}_{re.sub(r'[^0-9a-f]', '', uid)[:8]}_{datetime.now():%Y%m%d_%H%M}{SUFFIX}"


# ------------------------------------------------------------------ JSON seguro
class _Rejected(Exception):
    """Rejeição controlada (mensagem apresentável)."""


def _no_dup_keys(pairs: list[tuple[str, Any]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise _Rejected(f"chave JSON duplicada {str(k)[:40]!r}")
        out[k] = v
    return out


def _depth(obj: Any) -> int:
    best, stack = 0, [(obj, 1)]
    while stack:
        o, d = stack.pop()
        if isinstance(o, (dict, list)):
            best = max(best, d)
            if d > MAX_JSON_DEPTH:
                return d
            stack.extend((x, d + 1) for x in (o.values() if isinstance(o, dict) else o))
    return best


def load_json(data: bytes, what: str) -> Any:
    """JSON de entrada não confiável: UTF-8, sem chaves duplicadas, profundidade limitada; erro → ``_Rejected``."""
    if len(data) > MAX_JSON_BYTES:
        raise _Rejected(f"{what}: documento JSON grande demais.")
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_no_dup_keys)
    except _Rejected as exc:
        raise _Rejected(f"{what}: {exc}.") from None
    except RecursionError:
        raise _Rejected(f"{what}: JSON aninhado demais.") from None
    except (UnicodeDecodeError, ValueError):
        raise _Rejected(f"{what}: JSON inválido ou ilegível.") from None
    if _depth(obj) > MAX_JSON_DEPTH:
        raise _Rejected(f"{what}: JSON aninhado demais (> {MAX_JSON_DEPTH} níveis).")
    return obj


# ------------------------------------------------------------------ inspeção
@dataclass
class Inspection:
    """Resultado da inspeção de um pacote. ``ok`` só quando NENHUM erro foi encontrado (uma única dependência
    obrigatória ausente ou corrompida impede aceitar o estudo como completo)."""
    ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    manifest_text: str = ""
    package_sha256: str = ""
    package_bytes: int = 0
    content_id: str = ""
    docs: dict[str, Any] = field(default_factory=dict)      # JSONs do pacote já validados (pequenos)
    summary: dict = field(default_factory=dict)

    def as_report(self) -> dict:
        return {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings), "summary": dict(self.summary),
                "package_sha256": self.package_sha256, "content_id": self.content_id}


def content_id(manifest: dict) -> str:
    """Identidade do CONTEÚDO do estudo (independe da data de exportação e da compressão): a mesma exportação feita
    duas vezes sem mudanças tem o mesmo ``content_id``."""
    core = {"format": manifest.get("format"), "format_version": manifest.get("format_version"),
            "origin": (manifest.get("study") or {}).get("origin"),
            "resources": {p: r.get("sha256") for p, r in sorted((manifest.get("resources") or {}).items())
                          if isinstance(r, dict)}}
    return sha256(C.canonical_json(core).encode("utf-8")).hexdigest()


def _open(source: str | os.PathLike | bytes | IO[bytes]) -> tuple[zipfile.ZipFile, int]:
    if isinstance(source, (bytes, bytearray)):
        fh: Any = io.BytesIO(source)
        size = len(source)
    elif isinstance(source, (str, os.PathLike)):
        size = Path(source).stat().st_size
        fh = open(source, "rb")
    else:
        fh = source
        fh.seek(0, io.SEEK_END)
        size = fh.tell()
        fh.seek(0)
    if size > MAX_PACKAGE_BYTES:
        raise _Rejected(f"Pacote grande demais ({size / 2**20:.0f} MiB > {MAX_PACKAGE_BYTES // 2**20} MiB).")
    try:
        return zipfile.ZipFile(fh), size
    except zipfile.BadZipFile:
        raise _Rejected("O arquivo não é um ZIP válido.") from None


def package_digest(source: str | os.PathLike | bytes | IO[bytes]) -> str:
    h = sha256()
    if isinstance(source, (bytes, bytearray)):
        h.update(source)
    elif isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                h.update(chunk)
    else:
        source.seek(0)
        for chunk in iter(lambda: source.read(_CHUNK), b""):
            h.update(chunk)
        source.seek(0)
    return h.hexdigest()


def _structure(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Estrutura do ZIP antes de descomprimir qualquer coisa."""
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise _Rejected(f"Pacote com entradas demais ({len(infos)} > {MAX_ENTRIES}).")
    names = [i.filename for i in infos]
    if len(set(names)) != len(names):
        raise _Rejected("Pacote com entradas duplicadas.")
    if len({n.lower() for n in names}) != len(names):
        raise _Rejected("Pacote com entradas que diferem apenas em maiúsculas/minúsculas (perigoso em alguns sistemas).")
    if "manifest.json" not in names:
        raise _Rejected("Pacote sem manifest.json: não é um arquivo científico do SEEDS2.")
    bad = []
    declared = 0
    for info in infos:
        n = info.filename
        if n != "manifest.json" and classify(n) is None:
            bad.append(n)
            continue
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            raise _Rejected(f"Entrada {n[:80]!r} é um link simbólico (não permitido).")
        if mode and not stat.S_ISREG(mode) and stat.S_IFMT(mode):
            raise _Rejected(f"Entrada {n[:80]!r} não é um arquivo regular.")
        if info.flag_bits & 0x1:
            raise _Rejected("Entradas criptografadas não são suportadas.")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise _Rejected("Método de compressão não suportado.")
        cap = MAX_JSON_BYTES if n.endswith(".json") else MAX_ENTRY_BYTES
        if info.file_size > cap:
            raise _Rejected(f"Entrada {n[:80]!r} excede o tamanho permitido.")
        if info.file_size > RATIO_MIN_BYTES and info.file_size > MAX_RATIO * max(info.compress_size, 1):
            raise _Rejected(f"Entrada {n[:80]!r} com taxa de compressão suspeita (possível bomba ZIP).")
        declared += info.file_size
    if bad:
        shown = ", ".join(repr(b[:60]) for b in sorted(bad)[:5])
        raise _Rejected(f"Entradas não permitidas no pacote (caminho inesperado, absoluto ou com '..'): {shown}")
    if declared > MAX_TOTAL_UNCOMPRESSED:
        raise _Rejected("O conteúdo declarado excede o limite total permitido.")
    return infos


def stream_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: list[int], *, keep: bool) -> tuple[str, int, bytes | None]:
    """Lê uma entrada em blocos sem confiar no tamanho declarado: (SHA-256, tamanho real, conteúdo se ``keep``)."""
    cap = MAX_JSON_BYTES if info.filename.endswith(".json") else MAX_ENTRY_BYTES
    h, n, out = sha256(), 0, bytearray() if keep else None
    head = b""
    with zf.open(info) as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            if n == 0:
                head = chunk[:8]
            n += len(chunk)
            budget[0] -= len(chunk)
            if n > cap:
                raise _Rejected(f"Entrada {info.filename[:80]!r} excede o tamanho permitido.")
            if budget[0] < 0:
                raise _Rejected("O conteúdo descomprimido excede o limite total permitido.")
            h.update(chunk)
            if keep:
                out += chunk
    if any(head.startswith(m) for m in _EXEC_MAGIC):
        raise _Rejected(f"Entrada {info.filename[:80]!r} tem conteúdo executável (não permitido).")
    return h.hexdigest(), n, (bytes(out) if keep else None)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _manifest_errors(m: Any) -> list[str]:
    if not isinstance(m, dict):
        return ["manifest.json não contém um objeto."]
    if m.get("format") != FORMAT:
        return ["Formato não reconhecido: não é um arquivo científico do SEEDS2 (seeds2-study). Backups de microrrede "
                "(.seeds2backup.zip) são importados pelo Gestor de microrredes."]
    fv = m.get("format_version")
    if not _is_int(fv):
        return ["Versão do formato ausente ou inválida."]
    if fv not in SUPPORTED_FORMAT_VERSIONS:
        newer = fv > max(SUPPORTED_FORMAT_VERSIONS)
        return [f"Versão do formato {fv} não suportada por esta instalação (lê: "
                f"{', '.join(map(str, SUPPORTED_FORMAT_VERSIONS))}). "
                + ("O pacote foi produzido por um SEEDS2 mais novo: atualize esta instalação para lê-lo." if newer else
                   "Versão desconhecida.") + " Nada foi importado."]
    errs: list[str] = []
    for k in ("created_at",):
        if not (isinstance(m.get(k), str) and 0 < len(m[k]) <= 64):
            errs.append(f"Campo {k!r} ausente ou inválido.")
    ex = m.get("exporter")
    if not isinstance(ex, dict) or not isinstance(ex.get("app_version"), str):
        errs.append("Campo 'exporter' ausente ou inválido.")
    st = m.get("study")
    if not isinstance(st, dict):
        return errs + ["Campo 'study' ausente ou inválido."]
    o = st.get("origin")
    if not isinstance(o, dict):
        errs.append("Identidade de origem ausente.")
    else:
        for k in ("microgrid_uid", "scenario_uid"):
            if not (isinstance(o.get(k), str) and _HEX32.fullmatch(o[k])):
                errs.append(f"Identidade de origem sem {k!r} válido.")
        for k in ("microgrid_name", "scenario_name"):
            if not (isinstance(o.get(k), str) and len(o[k]) <= 500):
                errs.append(f"Identidade de origem sem {k!r} válido.")
    for k in ("versions", "inventory_revisions"):
        v = st.get(k)
        if not isinstance(v, list) or not v or not all(_is_int(x) and x >= 1 for x in v) or len(set(v)) != len(v):
            errs.append(f"Índice 'study.{k}' ausente ou inválido.")
    runs = st.get("runs")
    if not isinstance(runs, list) or not all(isinstance(x, str) and _HEX32.fullmatch(x) for x in runs) or \
            len(set(runs)) != len(runs):
        errs.append("Índice 'study.runs' inválido.")
    res = m.get("resources")
    if not isinstance(res, dict) or not res:
        return errs + ["Campo 'resources' ausente ou inválido."]
    for path, r in res.items():
        if not isinstance(path, str) or path == "manifest.json" or classify(path) is None:
            errs.append(f"Recurso com caminho não permitido: {str(path)[:80]!r}.")
            break
        if not isinstance(r, dict) or not (isinstance(r.get("sha256"), str) and _HEX64.fullmatch(r["sha256"])) or \
                not (_is_int(r.get("size")) and r["size"] >= 0) or not isinstance(r.get("media_type"), str):
            errs.append(f"Recurso {path[:80]!r} sem SHA-256/tamanho/tipo válidos.")
            break
        exp = expected_media_type(path)
        if (exp is not None and r["media_type"] != exp) or (exp is None and r["media_type"] not in BLOB_MEDIA_TYPES):
            errs.append(f"Recurso {path[:80]!r} com tipo de conteúdo inesperado ({str(r['media_type'])[:40]}).")
            break
        role = classify(path)
        if role and role[0] in ("inventory_blob", "forecast_blob") and role[1][0] != r["sha256"]:
            errs.append(f"Recurso {path[:80]!r}: nome não corresponde ao SHA-256 declarado.")
            break
    return errs


def inspect(source: str | os.PathLike | bytes | IO[bytes]) -> Inspection:
    """Inspeciona um pacote NÃO confiável sem gravar nada e sem executar nada. Nunca levanta exceção: todo problema
    vira ``errors`` (mensagens apresentáveis)."""
    rep = Inspection()
    try:
        _inspect(source, rep)
    except _Rejected as exc:
        rep.errors.append(str(exc))
    except Exception as exc:  # noqa: BLE001 — qualquer outro defeito do arquivo é rejeição controlada
        rep.errors.append(f"Pacote malformado ou ilegível ({type(exc).__name__}).")
    rep.ok = not rep.errors
    if not rep.ok:
        rep.docs = {}
    return rep


def _inspect(source, rep: Inspection) -> None:
    zf, size = _open(source)
    rep.package_bytes = size
    with zf:
        infos = _structure(zf)
        by_name = {i.filename: i for i in infos}
        budget = [MAX_TOTAL_UNCOMPRESSED]
        _, _, mbytes = stream_entry(zf, by_name["manifest.json"], budget, keep=True)
        m = load_json(mbytes, "manifest.json")
        errs = _manifest_errors(m)
        if errs:
            rep.errors.extend(errs)
            return
        rep.manifest, rep.manifest_text = m, mbytes.decode("utf-8")
        res: dict = m["resources"]
        present = set(by_name) - {"manifest.json"}
        for p in sorted(present - set(res))[:10]:
            rep.errors.append(f"Arquivo {p[:80]!r} presente no pacote mas não declarado no manifesto.")
        missing = sorted(set(res) - present)
        for p in missing[:10]:
            rep.errors.append(f"Recurso obrigatório ausente: {p[:80]!r}.")
        if len(missing) > 10:
            rep.errors.append(f"… e mais {len(missing) - 10} recurso(s) ausente(s).")
        if rep.errors:
            return
        total = 0
        for path in sorted(res):
            keep = path.endswith(".json")
            digest, n, data = stream_entry(zf, by_name[path], budget, keep=keep)
            total += n
            if n != res[path]["size"]:
                rep.errors.append(f"Tamanho de {path[:80]!r} não confere com o manifesto ({n} ≠ {res[path]['size']} bytes).")
            if digest != res[path]["sha256"]:
                rep.errors.append(f"Integridade violada: SHA-256 de {path[:80]!r} não confere com o manifesto.")
            if keep and not rep.errors:
                rep.docs[path] = load_json(data, path)
        if rep.errors:
            return
    rep.package_sha256 = package_digest(source)
    rep.content_id = content_id(m)
    _relations(rep, total)


def _relations(rep: Inspection, total: int) -> None:
    """Relações entre cenário, versões, revisões do inventário, previsões e rodadas (tudo já com SHA-256 conferido)."""
    m, d, res = rep.manifest, rep.docs, rep.manifest["resources"]
    st, o = m["study"], m["study"]["origin"]
    err = rep.errors.append
    used: set[str] = set()
    scn = d.get("scenario/scenario.json")
    used.add("scenario/scenario.json")
    if not isinstance(scn, dict):
        err("Recurso obrigatório 'scenario/scenario.json' ausente ou inválido.")
        return
    if scn.get("scenario_uid") != o["scenario_uid"] or scn.get("microgrid_uid") != o["microgrid_uid"]:
        err("A identidade do cenário não confere com a identidade de origem declarada no manifesto.")
    versions = sorted(st["versions"])
    if versions != list(range(1, len(versions) + 1)):
        err("As versões do cenário não são contínuas a partir de 1 (histórico incompleto).")
    if scn.get("version") != versions[-1]:
        err("A versão atual do cenário não corresponde à última versão incluída.")
    revs = set(st["inventory_revisions"])
    vfp: dict[int, str] = {}
    blobs_needed: dict[str, str] = {}
    for v in versions:
        mp, dp = version_path(v), version_path(v, True)
        used.update((mp, dp))
        meta, doc = d.get(mp), d.get(dp)
        if not isinstance(meta, dict) or not isinstance(doc, dict):
            err(f"Versão {v}: metadados ou documento ausentes.")
            continue
        if meta.get("version") != v or meta.get("scenario_uid") != o["scenario_uid"]:
            err(f"Versão {v}: metadados não correspondem ao arquivo.")
        if C.fingerprint(doc) != meta.get("fingerprint"):
            err(f"Versão {v}: a impressão digital do documento não confere (documento alterado).")
        vfp[v] = str(meta.get("fingerprint"))
        if doc.get("schema") != "seeds2-scenario" or not _is_int(doc.get("schema_version")):
            err(f"Versão {v}: documento de cenário não reconhecido.")
            continue
        if doc.get("scenario_uid") != o["scenario_uid"] or (doc.get("microgrid") or {}).get("uid") != o["microgrid_uid"]:
            err(f"Versão {v}: o documento pertence a outro cenário ou microrrede.")
        ref = doc.get("inventory_ref") if isinstance(doc.get("inventory_ref"), dict) else {}
        br = meta.get("base_revision")
        if br != ref.get("config_revision") or meta.get("base_fingerprint") != ref.get("config_fingerprint"):
            err(f"Versão {v}: referência ao inventário inconsistente entre metadados e documento.")
        if br not in revs:
            err(f"Versão {v}: revisão {br} do inventário referenciada mas não incluída.")
        fc = doc.get("forecasts")
        for slot, e in (fc.items() if isinstance(fc, dict) else []):
            for k in ("data", "blob"):
                h = e.get(k) if isinstance(e, dict) else None
                if isinstance(h, str) and _HEX64.fullmatch(h):
                    blobs_needed[f"forecasts/blobs/{h}"] = f"versão {v}, previsão '{slot}'"
    rfp: dict[int, str] = {}
    for r in sorted(revs):
        mp, dp = revision_path(r), revision_path(r, True)
        used.update((mp, dp))
        meta, doc = d.get(mp), d.get(dp)
        if not isinstance(meta, dict) or not isinstance(doc, dict):
            err(f"Revisão {r} do inventário: metadados ou documento ausentes.")
            continue
        if meta.get("revision") != r:
            err(f"Revisão {r} do inventário: metadados não correspondem ao arquivo.")
        if C.fingerprint(doc) != meta.get("fingerprint"):
            err(f"Revisão {r} do inventário: a impressão digital do documento não confere (documento alterado).")
        if meta.get("installation_uid") != o["microgrid_uid"]:
            err(f"Revisão {r} do inventário pertence a outra microrrede.")
        rfp[r] = str(meta.get("fingerprint"))
        from seeds2.microgrid.store import MicrogridStore

        for h in MicrogridStore._referenced_blobs(doc):
            blobs_needed[f"inventory/blobs/{h}"] = f"revisão {r} do inventário"
    for v in versions:
        meta = d.get(version_path(v)) or {}
        if meta.get("base_revision") in rfp and meta.get("base_fingerprint") != rfp[meta["base_revision"]]:
            err(f"Versão {v}: a revisão do inventário incluída tem outra impressão digital.")
    for p, why in sorted(blobs_needed.items()):
        used.add(p)
        if p not in res:
            err(f"Dado referenciado ausente ({why}): {p[-64:][:12]}….")
    if "inventory/catalog_references.json" in res:
        used.add("inventory/catalog_references.json")
    states: dict[str, int] = {}
    run_dates = []
    for ru in st["runs"]:
        base = f"runs/{ru}/"
        for n in ("run", "manifest"):
            used.add(f"{base}{n}.json")
        row, man = d.get(f"{base}run.json"), d.get(f"{base}manifest.json")
        if not isinstance(row, dict) or not isinstance(man, dict):
            err(f"Rodada {ru[:8]}…: run.json ou manifest.json ausente.")
            continue
        state = row.get("state")
        if row.get("run_uid") != ru or row.get("scenario_uid") != o["scenario_uid"]:
            err(f"Rodada {ru[:8]}…: identidade não confere com o arquivo e o cenário.")
        if state not in RUN_FINAL_STATES:
            err(f"Rodada {ru[:8]}…: estado {str(state)[:20]!r} inválido para um arquivo (somente rodadas finalizadas).")
            continue
        states[state] = states.get(state, 0) + 1
        run_dates.append(str(row.get("created_at")))
        v = row.get("scenario_version")
        if v not in vfp or row.get("scenario_fingerprint") != vfp[v]:
            err(f"Rodada {ru[:8]}…: versão {v} do cenário ausente ou com outra impressão digital.")
        if row.get("config_revision") not in rfp or row.get("config_fingerprint") != rfp.get(row.get("config_revision")):
            err(f"Rodada {ru[:8]}…: revisão do inventário ausente ou com outra impressão digital.")
        ref = man.get("reference") if isinstance(man.get("reference"), dict) else {}
        if man.get("run_uid") != ru or ref.get("scenario_uid") != o["scenario_uid"] or \
                ref.get("scenario_version") != v or ref.get("scenario_fingerprint") != row.get("scenario_fingerprint"):
            err(f"Rodada {ru[:8]}…: o manifesto de procedência não corresponde à rodada.")
        for n in ("outcome", "summary", "error"):
            p = f"{base}{n}.json"
            if p in res:
                used.add(p)
            if bool(row.get(f"has_{n}")) != (p in res):
                err(f"Rodada {ru[:8]}…: '{n}' declarado de forma inconsistente.")
        idx = row.get("data")
        if not isinstance(idx, dict):
            err(f"Rodada {ru[:8]}…: índice de dados inválido.")
            continue
        if state == "concluida" and (not idx or f"{base}summary.json" not in res or f"{base}outcome.json" not in res):
            err(f"Rodada {ru[:8]}… concluída sem resultados completos (resumo, resultado ou dados ausentes).")
        if state != "concluida" and idx:
            err(f"Rodada {ru[:8]}… não concluída com dados de resultado (não permitido).")
        for name, info in idx.items():
            p = f"{base}data/{name}"
            used.add(p)
            if not (isinstance(name, str) and RUN_DATA_NAME.fullmatch(name)) or not isinstance(info, dict):
                err(f"Rodada {ru[:8]}…: nome de dado inválido.")
                continue
            if p not in res:
                err(f"Rodada {ru[:8]}…: dado '{name[:60]}' ausente.")
            elif res[p]["sha256"] != info.get("sha256") or res[p]["size"] != info.get("size"):
                err(f"Rodada {ru[:8]}…: dado '{name[:60]}' não confere com o índice da rodada.")
    extra = sorted(set(res) - used)
    for p in extra[:10]:
        err(f"Recurso não referenciado por nenhuma parte do estudo: {p[:80]!r}.")
    for rp in res:
        c = classify(rp)
        if c and c[0] in ("run_json", "run_data") and c[1][0] not in set(st["runs"]):
            err(f"Recurso de rodada não listada no índice: {rp[:80]!r}.")
            break
    cnt = st.get("counts") if isinstance(st.get("counts"), dict) else {}
    if cnt.get("versions") != len(versions) or cnt.get("runs") != len(st["runs"]):
        err("As contagens declaradas no manifesto não conferem com o conteúdo.")
    rep.summary = {
        "scenario_name": o.get("scenario_name"), "scenario_uid": o["scenario_uid"],
        "microgrid_name": o.get("microgrid_name"), "microgrid_uid": o["microgrid_uid"],
        "microgrid_incarnation": o.get("microgrid_incarnation"),
        "scenario_created_at": scn.get("created_at"), "scenario_updated_at": scn.get("updated_at"),
        "versions": len(versions), "runs": len(st["runs"]), "runs_by_state": states,
        "inventory_revisions": sorted(revs), "resources": len(res), "uncompressed_bytes": total,
        "package_bytes": rep.package_bytes, "exported_at": m.get("created_at"),
        "exporter_version": (m.get("exporter") or {}).get("app_version"),
        "exporter": m.get("exporter"), "format_version": m["format_version"],
        "first_run_at": min(run_dates) if run_dates else None, "last_run_at": max(run_dates) if run_dates else None,
    }


def iter_resources(source, manifest: dict) -> Iterator[tuple[str, dict, bytes]]:
    """Relê o pacote (2ª passagem, para a importação) e entrega cada recurso declarado com SHA-256 e tamanho
    RECONFERIDOS — o arquivo pode ter mudado depois da inspeção. Qualquer divergência → ``_Rejected``."""
    zf, _ = _open(source)
    with zf:
        infos = {i.filename: i for i in _structure(zf)}
        budget = [MAX_TOTAL_UNCOMPRESSED]
        if set(infos) - {"manifest.json"} != set(manifest["resources"]):
            raise _Rejected("O conteúdo do pacote mudou desde a inspeção.")
        for path, r in sorted(manifest["resources"].items()):
            digest, n, data = stream_entry(zf, infos[path], budget, keep=True)
            if digest != r["sha256"] or n != r["size"]:
                raise _Rejected(f"Integridade violada durante a importação: {path[:80]!r}.")
            yield path, r, data


Rejected = _Rejected

__all__ = ["FORMAT", "FORMAT_VERSION", "INTEGRITY_NOTE", "Inspection", "Rejected", "SUFFIX", "SUPPORTED_FORMAT_VERSIONS",
           "classify", "content_id", "inspect", "iter_resources", "load_json", "revision_path", "safe_filename",
           "version_path"]
