"""Contrato de leitura unificado dos relatórios científicos (Piso 2D-B, Hito A).

``RunDossier`` é a ÚNICA fonte de dados dos exportadores (PDF, Excel e figuras) e pode ser montado a partir de:

* **rodada local** (``load_local``): ``MicrogridStore`` da microrrede — documentos lidos num ÚNICO instantâneo de
  leitura (``MicrogridStore.snapshot``, H-03) e liberados antes de qualquer geração;
* **estudo arquivado** (``load_archived``): ``StudyView`` do Arquivo Científico — SOMENTE os recursos do estudo
  (documento EXATO da versão executada, revisão do inventário incluída no pacote, séries da rodada). A microrrede de
  origem, o cenário original e o motor atual NÃO são consultados.

Regras:

* Nada aqui importa ``orchestrator_runtime``, o EMS ou os modelos: não há como recalcular. Os indicadores vêm do
  resumo persistido (``StoredRun.summary``) e do relatório do EMS gravado (``saidas/relatorio_ems.json``).
* Integridade conferida na leitura: impressões digitais (``config.fingerprint``) da versão do cenário e da revisão
  do inventário recalculadas sobre o texto gravado e comparadas com as registradas pela rodada; identidade do
  manifesto conferida com as colunas da rodada; TODOS os dados da rodada relidos com SHA-256 conferido (pela fonte)
  e o tamanho comparado ao índice original. Qualquer divergência → ``DossierIntegrityError`` (nenhum documento é
  gerado a partir de dados inconsistentes).
* Somente leitura: nenhum método grava em bancos de microrrede ou do Arquivo Científico.
"""
from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from seeds2 import APP_NAME, APP_VERSION
from seeds2.microgrid import config as C
from seeds2.microgrid.migrations import MigrationError, migrate_document
from seeds2.microgrid.store import StoredRun, StoreError
from seeds2.operation import contracts
from seeds2.operation import forecasts as F
from seeds2.operation import initialization as I

LOCAL, ARCHIVED = "local", "arquivo"
ORIGIN_LABELS = {LOCAL: "Rodada local (armazenamento desta microrrede)",
                 ARCHIVED: "Estudo arquivado (Arquivo Científico desta instalação)"}
MAX_DOSSIER_BYTES = 512 * 1024 * 1024      # mesmo teto do pacote seeds2-study (proteção de memória)
CSV_INPUTS, CSV_OUTPUTS, EMS_REPORT, EXCHANGE = ("entradas/missao.csv", "saidas/despacho_ems.csv",
                                                  "saidas/relatorio_ems.json", "pacote_troca.zip")
# C-04.1 — recursos ESSENCIAIS de uma rodada concluída (gravados pelo runner do 2C na mesma transação da conclusão).
# Modelos físicos (``modelos/*.csv``) NÃO entram: dependem das tecnologias que participaram da rodada.
REQUIRED_CONCLUDED = (CSV_INPUTS, CSV_OUTPUTS, EMS_REPORT)
DERIVED_NOTE = ("Documento DERIVADO: representação dos dados persistidos de uma rodada já executada. A geração deste "
                "documento não executa modelos nem o EMS e não altera rodadas, cenários, inventário ou estudos. "
                "A fonte portátil integral do experimento é o pacote .seeds2study.zip (Arquivo Científico).")


class DossierError(StoreError):
    """Os dados da rodada não podem ser lidos para um relatório (rodada inexistente, em execução, ...)."""


class DossierIntegrityError(DossierError):
    """Os recursos originais estão inconsistentes ou corrompidos: nenhum documento deve ser gerado."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def generator_info() -> dict:
    """Software que GERA o documento derivado (≠ software que executou a rodada, registrado no manifesto)."""
    import platform

    out = {"app": APP_NAME, "app_version": APP_VERSION, "python": platform.python_version()}
    for mod in ("reportlab", "openpyxl", "matplotlib", "plotly", "pandas", "numpy", "pypdf"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", None) or getattr(m, "Version", None)
        except Exception:                              # noqa: BLE001 — dependência ausente: não declarada
            out[mod] = None
    return out


# ====================================================================== contrato
@dataclass
class RunDossier:
    """Tudo o que um relatório pode mostrar sobre UMA rodada finalizada, com a origem identificada.

    ``scenario`` é o documento EXATO da versão executada; ``inventory`` a revisão do inventário referenciada pela
    rodada (forma atual para exibição; o texto original teve a impressão digital conferida)."""
    kind: str
    run: StoredRun
    scenario: dict
    scenario_meta: dict
    inventory: dict | None
    inventory_meta: dict
    microgrid: dict
    archive: dict | None = None
    _reader: Callable[[str], bytes] | None = field(default=None, repr=False)
    _get_blob: Callable[[str], bytes] | None = field(default=None, repr=False)
    _cache: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------ identidade
    @property
    def run_uid(self) -> str:
        return self.run.run_uid

    @property
    def concluded(self) -> bool:
        return self.run.state == "concluida"

    @property
    def state_label(self) -> str:
        return contracts.RUN_STATE_LABELS.get(self.run.state, self.run.state)

    @property
    def manifest(self) -> dict:
        return self.run.manifest or {}

    @property
    def summary(self) -> dict:
        return self.run.summary or {}

    @property
    def mission(self) -> dict:
        return self.manifest.get("mission") or {}

    @property
    def timezone(self) -> str | None:
        return self.mission.get("timezone")

    @property
    def scenario_name(self) -> str:
        return str((self.manifest.get("scenario") or {}).get("name") or self.scenario.get("name") or "")

    @property
    def software(self) -> dict:
        return self.manifest.get("software") or {}

    def identity(self) -> dict:
        """Identificadores científicos da rodada (iguais para a rodada local e para a mesma rodada arquivada)."""
        r = self.run
        return {"run_uid": r.run_uid, "request_id": r.request_id, "microgrid_uid": r.microgrid_uid,
                "microgrid_name": self.microgrid.get("name"), "microgrid_incarnation": r.incarnation,
                "scenario_uid": r.scenario_uid, "scenario_name": self.scenario_name,
                "scenario_version": r.scenario_version, "scenario_fingerprint": r.scenario_fingerprint,
                "config_revision": r.config_revision, "config_fingerprint": r.config_fingerprint, "state": r.state,
                "created_at": r.created_at, "finished_at": r.finished_at, "software_app": self.software.get("app"),
                "science_sha256": (self.software.get("science") or {}).get("sha256")}

    # ------------------------------------------------------------ dados da rodada
    def data_names(self) -> list[str]:
        return sorted(self.run.data)

    def has(self, name: str) -> bool:
        return name in self.run.data

    def raw(self, name: str) -> bytes:
        """Conteúdo de um dado da rodada (SHA-256 conferido contra o índice ORIGINAL da rodada)."""
        if name not in self.run.data:
            raise DossierError(f"O dado '{name}' não existe nesta rodada.")
        key = ("raw", name)
        if key not in self._cache:
            try:
                b = self._reader(name)
            except StoreError as exc:
                raise DossierIntegrityError(f"Dado '{name}' ilegível: {exc}") from None
            idx = self.run.data[name]
            from hashlib import sha256

            if sha256(b).hexdigest() != idx["sha256"] or len(b) != int(idx["size"]):
                raise DossierIntegrityError(f"Dado '{name}' diverge do índice original da rodada (SHA-256/tamanho).")
            self._cache[key] = b
        return self._cache[key]

    def table(self, name: str) -> pd.DataFrame:
        """CSV da rodada como ``DataFrame``. Conversão de ponto flutuante ``round_trip``: cada número é o double
        EXATO escrito no CSV (sem a imprecisão do conversor rápido padrão do pandas)."""
        key = ("csv", name)
        if key not in self._cache:
            try:
                self._cache[key] = pd.read_csv(io.BytesIO(self.raw(name)), float_precision="round_trip",
                                               keep_default_na=True)
            except (ValueError, pd.errors.ParserError) as exc:
                raise DossierIntegrityError(f"CSV '{name}' ilegível: {exc}") from None
        return self._cache[key].copy()

    def json_data(self, name: str) -> Any:
        key = ("json", name)
        if key not in self._cache:
            try:
                self._cache[key] = json.loads(self.raw(name).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise DossierIntegrityError(f"JSON '{name}' ilegível: {exc}") from None
        return self._cache[key]

    def inputs(self) -> pd.DataFrame | None:
        return self.table(CSV_INPUTS) if self.has(CSV_INPUTS) else None

    def outputs(self) -> pd.DataFrame | None:
        return self.table(CSV_OUTPUTS) if self.has(CSV_OUTPUTS) else None

    def ems_report(self) -> dict | None:
        return self.json_data(EMS_REPORT) if self.has(EMS_REPORT) else None

    def model_tables(self) -> list[str]:
        return [n for n in self.data_names() if n.startswith("modelos/") and n.endswith(".csv")]

    # ------------------------------------------------------------ previsões (série ORIGINAL normalizada do cenário)
    def forecasts(self) -> dict[str, dict]:
        return dict(self.scenario.get("forecasts") or {})

    def forecast_frame(self, slot: str) -> pd.DataFrame:
        key = ("fc", slot)
        if key not in self._cache:
            entry = self.forecasts().get(slot)
            if not entry:
                raise DossierError(f"O cenário não declara previsão '{slot}'.")
            try:
                self._cache[key] = F.load(entry, self._get_blob)
            except F.ForecastDataError as exc:
                raise DossierIntegrityError(f"Previsão '{slot}': {exc}") from None
        return self._cache[key].copy()

    # ------------------------------------------------------------ inventário / estados iniciais
    def equipment(self) -> list[dict]:
        """Equipamentos da revisão de referência (ordem do inventário) com referência física, estado inicial do
        cenário e situação NA RODADA (representado/excluído/indisponível) — somente valores registrados."""
        refs = (self.scenario.get("inventory_ref") or {}).get("equipment") or {}
        states = (self.scenario.get("initialization") or {}).get("equipment") or {}
        pf = self.manifest.get("preflight") or {}
        excluded = {e.get("id"): e for e in pf.get("excluded") or []}
        represented: dict[str, list[dict]] = {}
        for e in pf.get("represented") or []:
            represented.setdefault(e.get("parent") or e.get("id"), []).append(e)
        eqs = (self.inventory or {}).get("equipment") or []
        rows = []
        seen = set()
        for eq in eqs:
            ref = I.equipment_reference(eq)
            rows.append(self._eq_row(eq["id"], ref, eq, states.get(eq["id"]), excluded, represented))
            seen.add(eq["id"])
        for eq_id, ref in refs.items():                # instantâneo do cenário sem a revisão (não deveria ocorrer)
            if eq_id not in seen:
                rows.append(self._eq_row(eq_id, dict(ref), None, states.get(eq_id), excluded, represented))
        return rows

    @staticmethod
    def _eq_row(eq_id, ref, eq, state, excluded, represented) -> dict:
        st = dict(state or {})
        rep = represented.get(eq_id) or []
        if eq_id in excluded:
            situation = "Excluído somente desta rodada"
            reason = excluded[eq_id].get("reason")
        elif rep:
            situation = "; ".join(sorted({str(r.get("status_label") or r.get("status")) for r in rep}))
            reason = "; ".join(sorted({str(r.get("reason")) for r in rep if r.get("reason")}))
        elif not ref.get("enabled", True):
            situation, reason = "Desabilitado no inventário", None
        else:
            situation, reason = "Não representado no EMS", None
        return {"id": eq_id, "kind": ref.get("kind"), "name": ref.get("name"), "tag": ref.get("tag"),
                "enabled": ref.get("enabled", True), "reference": ref, "state": st,
                "availability": I.AVAILABILITY.get(st.get("availability"), st.get("availability")) if st else None,
                "situation": situation, "situation_reason": reason, "params": (eq or {}).get("params") or {},
                "arrays": (eq or {}).get("arrays") or [], "manufacturer": (eq or {}).get("manufacturer"),
                "model": (eq or {}).get("model")}

    # ------------------------------------------------------------ mensagens
    def preflight_items(self) -> list[dict]:
        return list((self.manifest.get("preflight") or {}).get("items") or [])

    def engine_check_items(self) -> list[dict]:
        out = ((self.run.outcome or {}).get("engine_check") or {}).get("items") or []
        return list(out or (self.run.error or {}).get("items") or [])

    def engine_warnings(self) -> list[str]:
        return [str(a) for a in (self.summary.get("avisos") or (self.run.outcome or {}).get("warnings") or [])]


# ====================================================================== indicadores (fonte única PDF/Excel)
@dataclass(frozen=True)
class Indicator:
    key: str            # caminho no resumo persistido (ou no relatório do EMS gravado)
    label: str
    value: Any          # valor EXATO persistido (None = não disponível)
    unit: str
    source: str         # "StoredRun.summary" | "saidas/relatorio_ems.json" | "manifesto"
    note: str = ""


SOURCE_NAMES = {"fc": "H₂ / PEMFC", "bateria": "Bateria", "termica": "Térmica"}


def source_label(name: str) -> str:
    return SOURCE_NAMES.get(name, name)


def indicators(d: RunDossier) -> list[Indicator]:
    """Indicadores numéricos da rodada, SEM recálculo: cada valor é lido do resumo persistido da rodada ou do
    relatório do EMS gravado na mesma transação. Chaves ausentes aparecem com ``value=None`` (não disponível)."""
    s = d.summary
    S = "StoredRun.summary"
    out = [
        Indicator("custo_total_rs", "Custo total da operação", s.get("custo_total_rs"), "R$", S,
                  "Valor da função objetivo do EMS V1.6 (custo econômico) registrado pelo motor."),
        Indicator("energia_demanda_kWh", "Energia demandada", s.get("energia_demanda_kWh"), "kWh", S,
                  "Σ P_carga · Ts sobre os passos válidos (registrado pelo runner do Piso 2C)."),
        Indicator("energia_atendida_kWh", "Energia atendida", s.get("energia_atendida_kWh"), "kWh", S,
                  "Energia demandada − energia não atendida (registrado pelo runner)."),
        Indicator("energia_nao_atendida_kWh", "Energia não atendida (déficit)", s.get("energia_nao_atendida_kWh"), "kWh", S),
        Indicator("energia_excedente_kWh", "Excedente total (vertido)", s.get("energia_excedente_kWh"), "kWh", S),
        Indicator("energia_excedente_despachavel_kWh", "Excedente despachável", s.get("energia_excedente_despachavel_kWh"), "kWh", S),
        Indicator("energia_excedente_renovavel_kWh", "Excedente renovável", s.get("energia_excedente_renovavel_kWh"), "kWh", S),
        Indicator("energia_solar_kWh", "Energia solar FV (após η PV do EMS)", s.get("energia_solar_kWh"), "kWh", S,
                  "Σ η_PV · P_solar · Ts (registrado pelo runner)."),
        Indicator("energia_eolica_kWh", "Energia eólica (após η do EMS)", s.get("energia_eolica_kWh"), "kWh", S,
                  "Σ η_eol · P_eólica · Ts (registrado pelo runner)."),
    ]
    for n, v in (s.get("energia_por_fonte_kWh") or {}).items():
        out.append(Indicator(f"energia_por_fonte_kWh.{n}", f"Energia entregue · {source_label(n)}", v, "kWh", S,
                             "Σ max(P, 0) · Ts da fonte despachável (relatório do EMS V1.6)."))
    for n, v in (s.get("custo_por_fonte_rs") or {}).items():
        out.append(Indicator(f"custo_por_fonte_rs.{n}", f"Custo · {source_label(n)}", v, "R$", S))
    rel = (d.ems_report() or {}).get("rel") if d.concluded and d.has(EMS_REPORT) else None
    if rel:
        for n, v in zip(s.get("fontes") or [], rel.get("pct_atendimento") or []):
            out.append(Indicator(f"rel.pct_atendimento.{n}", f"Participação no atendimento · {source_label(n)}", v, "%",
                                 EMS_REPORT, "100 · E_fonte / Σ E das fontes despacháveis (definição do EMS V1.6)."))
    out.append(Indicator("h2_kg", "H₂ consumido (estimativa do EMS)", s.get("h2_kg"), "kg", S,
                         "Consumo físico calculado pelo EMS (curva empírica kg/kWh)."))
    out.append(Indicator("h2_kg_validacao_dinamica", "H₂ consumido (validação dinâmica PEMFC)",
                         s.get("h2_kg_validacao_dinamica"), "kg", S,
                         "Metodologia distinta (modelo dinâmico PEMFC); não é automaticamente equivalente à estimativa do EMS."))
    for n, v in (s.get("soc_final") or {}).items():
        out.append(Indicator(f"soc_final.{n}", f"SOC final · {source_label(n)}", v, "fração (0–1)", S))
    for n, v in (s.get("partidas") or {}).items():
        out.append(Indicator(f"partidas.{n}", f"Partidas · {source_label(n)}", v, "—", S))
    out += [
        Indicator("passos", "Passos válidos do despacho", s.get("passos"), "passos", S),
        Indicator("passos_inviaveis", "Passos inviáveis", s.get("passos_inviaveis"), "passos", S),
        Indicator("Ts_s", "Passo temporal do despacho", s.get("Ts_s"), "s", S),
        Indicator("N", "Horizonte móvel N", s.get("N"), "passos", S),
        Indicator("algoritmo", "Algoritmo", s.get("algoritmo"), "—", S),
        Indicator("tempo_otimizador_s", "Tempo do otimizador", s.get("tempo_otimizador_s"), "s", S),
    ]
    return out


def integration_convention(d: RunDossier) -> dict:
    """Duração declarada × passos integrados × convenção registrada pelo runner do Piso 2C (somente DESCRIÇÃO: nada é
    recalculado nem corrigido). Dívida científica prioritária — decisão matemática do piso dedicado ao EMS."""
    dur = d.mission.get("duration_min")
    n = d.summary.get("passos")
    ts = d.summary.get("Ts_s") or d.mission.get("step_s")
    integ = (float(n) * float(ts) / 60.0) if is_number(n) and is_number(ts) else None
    differs = is_number(dur) and integ is not None and abs(integ - float(dur)) > 1e-9
    return {
        "duration_min": dur, "steps": n, "Ts_s": ts, "integrated_min": integ, "differs": bool(differs),
        "formula": "E = Σ_{k=0}^{passos−1} P_k · Ts (runner do Piso 2C, seeds2.operation.runner.summarize)",
        "note": (f"Missão declarada de {dur} min; o motor usa {n} instantes (início ao fim, inclusive) e o resumo "
                 f"persistido integra cada um como um passo completo de {ts:g} s"
                 + (f" = {integ:g} min integrados (o instante terminal entra como um passo inteiro)." if differs else ".")
                 + " Convenção registrada e NÃO corrigida nos relatórios: dívida científica prioritária, a decidir no piso "
                   "dedicado ao EMS (PARAMIJEFE.md, Entrega 5 §16)."
                 if is_number(ts) else "Convenção de integração não disponível no resumo persistido."),
    }


def is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


# ====================================================================== carregamento
def _check_fp(doc_text: str, recorded: str, expected: str, what: str) -> dict:
    try:
        doc = json.loads(doc_text)
    except ValueError:
        raise DossierIntegrityError(f"{what}: documento ilegível.") from None
    if C.fingerprint(doc) != recorded:
        raise DossierIntegrityError(f"{what}: a impressão digital recalculada não confere com a gravada.")
    if recorded != expected:
        raise DossierIntegrityError(f"{what}: impressão digital diferente da registrada pela rodada.")
    return doc


def _display_revision(doc: dict) -> dict:
    try:
        out, _ = migrate_document(json.loads(json.dumps(doc)))
        return out
    except MigrationError:
        return doc


def _check_run(run: StoredRun) -> None:
    if run.state == "em_execucao":
        raise DossierError("A rodada ainda está em execução: os relatórios só podem ser gerados de rodadas finalizadas.")
    ref = (run.manifest or {}).get("reference") or {}
    pairs = (("microgrid_uid", run.microgrid_uid), ("scenario_uid", run.scenario_uid),
             ("scenario_version", run.scenario_version), ("scenario_fingerprint", run.scenario_fingerprint),
             ("config_revision", run.config_revision), ("config_fingerprint", run.config_fingerprint))
    bad = [k for k, v in pairs if ref.get(k) != v]
    if (run.manifest or {}).get("run_uid") != run.run_uid:
        bad.append("run_uid")
    if run.incarnation and ref.get("microgrid_incarnation") and ref["microgrid_incarnation"] != run.incarnation:
        bad.append("microgrid_incarnation")
    if bad:
        raise DossierIntegrityError("O manifesto da rodada diverge da identidade registrada: " + ", ".join(bad) + ".")
    if run.state == "concluida" and not run.summary:
        raise DossierIntegrityError("Rodada concluída sem resumo persistido.")
    missing = missing_required(run)
    if missing:
        raise DossierIntegrityError("Rodada concluída incompleta: recurso(s) essencial(is) ausente(s) do índice original "
                                    "da rodada: " + ", ".join(missing) + ". Nenhum documento é gerado.")
    total = sum(int(d.get("size") or 0) for d in run.data.values())
    if total > MAX_DOSSIER_BYTES:
        raise DossierError(f"Os dados desta rodada ({total / 2**20:.0f} MiB) excedem o limite de leitura dos "
                           f"relatórios ({MAX_DOSSIER_BYTES / 2**20:.0f} MiB).")


def missing_required(run: StoredRun) -> list[str]:
    """Recursos essenciais ausentes do índice ORIGINAL de uma rodada concluída (falha/interrupção: nenhum exigido)."""
    if run.state != "concluida":
        return []
    return [n for n in REQUIRED_CONCLUDED if n not in (run.data or {})]


def require_complete(d: RunDossier) -> None:
    """Barreira dos geradores (PDF, Excel, figuras): rodada concluída sem um recurso essencial → recusa explícita."""
    missing = missing_required(d.run)
    if missing:
        raise DossierIntegrityError("Rodada concluída incompleta: recurso(s) essencial(is) ausente(s) do índice original "
                                    "da rodada: " + ", ".join(missing) + ". Nenhum documento é gerado.")


def _verify_all(d: RunDossier) -> None:
    """Relê TODOS os dados da rodada (SHA-256 e tamanho) — um recurso corrompido impede o relatório."""
    for name in d.data_names():
        d.raw(name)
        if not name.endswith(".csv") and not name.endswith(".json"):
            d._cache.pop(("raw", name), None)              # binários grandes (pacote de troca): só conferidos
    for slot in d.forecasts():
        d.forecast_frame(slot)


def load_local(store, run_uid: str, *, verify: bool = True) -> RunDossier:
    """Dossiê de uma rodada do ``MicrogridStore`` (documentos de UM instantâneo de leitura; nada é gravado)."""
    from seeds2.microgrid.store import RunNotFound

    try:
        run = store.get_run(run_uid)
    except RunNotFound:
        raise DossierError("A rodada não existe nesta microrrede.") from None
    _check_run(run)
    with store.snapshot() as snap:
        versions = {int(v["version"]): v for v in snap.scenario_versions(run.scenario_uid)}
        rev = snap.revision_row(run.config_revision)
        incarnation = snap.meta("incarnation")
    v = versions.get(int(run.scenario_version))
    if v is None:
        raise DossierIntegrityError(f"A versão {run.scenario_version} do cenário não existe nesta microrrede.")
    doc = _check_fp(v["document"], v["fingerprint"], run.scenario_fingerprint, f"Versão {run.scenario_version} do cenário")
    inv = _check_fp(rev["document"], rev["fingerprint"], run.config_fingerprint, f"Revisão {run.config_revision} do inventário")
    inst = inv.get("installation") or {}
    d = RunDossier(
        kind=LOCAL, run=run, scenario=doc,
        scenario_meta={k: v.get(k) for k in ("version", "fingerprint", "saved_at", "note", "origin", "base_revision",
                                              "base_fingerprint")},
        inventory=_display_revision(inv),
        inventory_meta={k: rev.get(k) for k in ("revision", "fingerprint", "saved_at", "note", "origin")},
        microgrid={"uid": run.microgrid_uid, "name": inst.get("name"), "incarnation": run.incarnation,
                   "current_incarnation": incarnation, "present": True},
        archive=None, _reader=lambda name: store.run_data(run.run_uid, name), _get_blob=store.get_blob)
    if verify:
        _verify_all(d)
    return d


def load_archived(view, run_uid: str, *, verify: bool = True) -> RunDossier:
    """Dossiê de uma rodada de um estudo arquivado (SOMENTE recursos do estudo; sem microrrede nem motor)."""
    from seeds2.archive import format as FMT
    from seeds2.archive.store import ArchiveError

    try:
        run = view.get_run(run_uid)
    except ArchiveError as exc:
        raise DossierError(str(exc)) from None
    _check_run(run)
    try:
        vmeta = view.version_meta(run.scenario_version)
        rmeta = view.revision_meta(run.config_revision)
        vtext = view.raw(FMT.version_path(run.scenario_version, True)).decode("utf-8")
        rtext = view.raw(FMT.revision_path(run.config_revision, True)).decode("utf-8")
    except (ArchiveError, UnicodeDecodeError) as exc:
        raise DossierIntegrityError(f"Estudo incompleto ou corrompido: {exc}") from None
    if vmeta.get("fingerprint") != run.scenario_fingerprint:
        raise DossierIntegrityError("A versão arquivada do cenário não corresponde à registrada pela rodada.")
    doc = _check_fp(vtext, vmeta.get("fingerprint"), run.scenario_fingerprint, f"Versão {run.scenario_version} do cenário")
    inv = _check_fp(rtext, rmeta.get("fingerprint"), run.config_fingerprint, f"Revisão {run.config_revision} do inventário")
    origin = view.origin
    s = view.study
    inst = inv.get("installation") or {}
    d = RunDossier(
        kind=ARCHIVED, run=run, scenario=doc,
        scenario_meta={"version": run.scenario_version, **{k: vmeta.get(k) for k in (
            "fingerprint", "saved_at", "note", "origin", "base_revision", "base_fingerprint")}},
        inventory=_display_revision(inv),
        inventory_meta={"revision": run.config_revision, **{k: rmeta.get(k) for k in ("fingerprint", "saved_at", "note",
                                                                                      "origin")}},
        microgrid={"uid": run.microgrid_uid, "name": inst.get("name"), "incarnation": run.incarnation,
                   "name_at_export": origin.get("microgrid_name"), "present": None},
        archive={"archive_uid": s.archive_uid, "content_id": s.content_id, "package_sha256": s.package_sha256,
                 "imported_at": s.imported_at, "acquisition": s.acquisition, "copy_of": s.copy_of,
                 "exported_at": view.manifest.get("created_at"),
                 "exporter": (view.manifest.get("exporter") or {}).get("app_version"),
                 "format": f"{view.manifest.get('format')} v{view.manifest.get('format_version')}"},
        _reader=lambda name: view.run_data(run.run_uid, name), _get_blob=view.get_blob)
    if verify:
        _verify_all(d)
    return d


def load(source, run_uid: str, *, verify: bool = True) -> RunDossier:
    """``MicrogridStore`` → rodada local; ``StudyView`` → estudo arquivado."""
    from seeds2.archive.view import StudyView

    if isinstance(source, StudyView):
        return load_archived(source, run_uid, verify=verify)
    return load_local(source, run_uid, verify=verify)


def identity_for_manifest(d: RunDossier) -> dict:
    """Identificação do experimento para manifestos de documentos derivados (inclui a origem dos dados)."""
    out = {**d.identity(), "data_origin": d.kind, "data_origin_label": ORIGIN_LABELS[d.kind]}
    if d.archive:
        out["archive"] = {k: d.archive.get(k) for k in ("archive_uid", "content_id", "package_sha256", "imported_at")}
    return out


# ====================================================================== nomes de arquivo seguros
def safe_stem(d: RunDossier, kind: str) -> str:
    """Nome ASCII portátil: nunca contém texto não sanitizado do cenário (separadores, '..', controles)."""
    import re
    import unicodedata

    name = unicodedata.normalize("NFKD", d.scenario_name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]", "_", name))[:40].strip("_") or "cenario"
    uid = re.sub(r"[^0-9a-f]", "", d.run_uid)[:8] or "rodada"
    return f"seeds2_{kind}_{name}_v{int(d.run.scenario_version)}_{uid}"


__all__ = ["ARCHIVED", "DERIVED_NOTE", "DossierError", "DossierIntegrityError", "Indicator", "LOCAL",
           "ORIGIN_LABELS", "REQUIRED_CONCLUDED", "RunDossier", "generator_info", "identity_for_manifest",
           "indicators", "integration_convention", "is_number", "load", "load_archived", "load_local",
           "missing_required", "require_complete", "safe_stem", "source_label", "utc_now"]
