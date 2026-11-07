"""Planilha científica ``.xlsx`` de UMA rodada (Piso 2D-B, Hito B) — a partir do ``RunDossier``, sem recalcular.

Garantias:

* **Completa:** todas as colunas de ``entradas/missao.csv``, ``saidas/despacho_ems.csv`` e de cada ``modelos/*.csv``
  (uma folha por modelo), as séries originais normalizadas das previsões, o resumo persistido integral, o relatório do
  EMS, o manifesto da rodada achatado e os SHA-256 de todos os dados. Nenhuma coluna é omitida; cabeçalho = nome
  EXATO da coluna original (leitura direta por pandas/R/MATLAB); unidades e significado em "Dicionário de dados".
* **Precisão:** cada número é escrito com a representação decimal MAIS CURTA que reproduz exatamente o double
  persistido (``repr``; até 17 algarismos significativos) — openpyxl, por padrão, escreveria 16. O formato de exibição
  "Geral" não altera o valor armazenado. Inteiros acima de 2⁵³ (não representáveis no Excel) seriam gravados como texto
  e listados em "Avisos".
* **Ausentes:** NaN → célula VAZIA (nunca zero); ±infinito → texto "inf"/"-inf"; ambos contados em "Avisos".
* **Tempo:** colunas de instante gravadas como data/hora do Excel (sem fuso, que o Excel não suporta) com formato
  ``aaaa-mm-dd hh:mm:ss``; a referência (UTC, relógio de parede do fuso da missão, grade do runtime) está no comentário
  do cabeçalho e no dicionário. Valores não interpretáveis permanecem como o texto original.
* **Segurança:** todo texto é gravado como texto literal (``inlineStr``) — nunca fórmula —, com o prefixo de citação
  do Excel quando começa por ``= + - @``; caracteres de controle ilegais em XML são substituídos por U+FFFD (contados).
* **Limites do formato:** linhas > 1.048.575 → tabela dividida EXPLICITAMENTE em partes numeradas (registradas no
  índice e em "Avisos"); volume acima de ``MAX_CELLS`` → recusa com mensagem (use o .seeds2study.zip).
* Fórmulas: nenhuma. Os indicadores oficiais são os valores persistidos.
"""
from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS
from seeds2.operation import contracts
from seeds2.operation import strategy as SG

from . import columns as COL
from . import dossier as D

EXCEL_MAX_ROWS = 1_048_576
DATA_ROWS_PER_SHEET = EXCEL_MAX_ROWS - 1           # 1 linha de cabeçalho
EXCEL_MAX_COLS = 16_384
CELL_TEXT_MAX = 32_767
MAX_CELLS = 12_000_000                             # proteção de memória/tempo (não é limite científico)
DATETIME_FMT = "yyyy-mm-dd hh:mm:ss"
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")
HEAD_FONT = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="0E5E66")
META_FONT = Font(bold=True, color="0A4A50")
TITLE_FONT = Font(bold=True, size=13, color="0A4A50")
NOTE_FONT = Font(italic=True, color="5B6B7C")
WRAP = Alignment(wrap_text=True, vertical="top")


class WorkbookLimitError(D.DossierError):
    """O volume excede o que esta exportação representa sem perda (use o pacote .seeds2study.zip)."""


@dataclass
class _Stats:
    nan: int = 0
    inf: int = 0
    big_int: int = 0
    illegal: int = 0
    truncated: int = 0
    split: list[str] = field(default_factory=list)
    sheets: list[tuple[str, str, int, int]] = field(default_factory=list)   # (folha, conteúdo, linhas, colunas)


class _Book:
    def __init__(self):
        self.wb = Workbook(write_only=True)
        self.stats = _Stats()
        self._names: set[str] = set()

    # ------------------------------------------------------------ células
    def text(self, ws, value: Any, *, font=None, comment: str | None = None, wrap: bool = False) -> WriteOnlyCell:
        s = "" if value is None else str(value)
        if _ILLEGAL.search(s):
            self.stats.illegal += 1
            s = _ILLEGAL.sub("�", s)
        if len(s) > CELL_TEXT_MAX:
            self.stats.truncated += 1
            s = s[:CELL_TEXT_MAX - 120] + " […] TEXTO EXCEDE O LIMITE DE 32.767 CARACTERES DE UMA CÉLULA; íntegro no .seeds2study.zip"
        c = WriteOnlyCell(ws, value=s if s else None)
        if s:
            c.data_type = "s"                          # texto literal: nunca fórmula
            if s.startswith(_FORMULA_LEAD):
                c.quotePrefix = True
        if font is not None:
            c.font = font
        if wrap:
            c.alignment = WRAP
        if comment:
            c.comment = Comment(comment, "SEEDS2", width=320, height=120)
        return c

    def number(self, ws, v: Any) -> WriteOnlyCell:
        """Número com a representação exata (repr) do double; NaN → vazio; inf → texto."""
        if isinstance(v, (bool, np.bool_)):
            return WriteOnlyCell(ws, value=bool(v))
        if isinstance(v, (int, np.integer)):
            iv = int(v)
            if abs(iv) > 2 ** 53:
                self.stats.big_int += 1
                return self.text(ws, str(iv))
            c = WriteOnlyCell(ws, value=None)
            c._value, c.data_type = str(iv), "n"
            return c
        f = float(v)
        if math.isnan(f):
            self.stats.nan += 1
            return WriteOnlyCell(ws, value=None)
        if math.isinf(f):
            self.stats.inf += 1
            return self.text(ws, "inf" if f > 0 else "-inf")
        c = WriteOnlyCell(ws, value=None)
        c._value, c.data_type = repr(f), "n"            # repr = menor decimal que reproduz o double exatamente
        return c

    def when(self, ws, v: datetime) -> WriteOnlyCell:
        c = WriteOnlyCell(ws, value=v)
        c.number_format = DATETIME_FMT
        return c

    def value(self, ws, v: Any) -> WriteOnlyCell:
        if v is None:
            return WriteOnlyCell(ws, value=None)
        if isinstance(v, (bool, np.bool_, int, float, np.integer, np.floating)):
            return self.number(ws, v)
        if isinstance(v, (dict, list, tuple)):
            return self.text(ws, json.dumps(v, ensure_ascii=False))
        return self.text(ws, v)

    # ------------------------------------------------------------ folhas
    def sheet_name(self, base: str) -> str:
        name = re.sub(r"[\[\]:*?/\\]", "_", base).strip("'")[:31] or "Folha"
        stem, i = name, 2
        while name.lower() in self._names:
            suf = f" ({i})"
            name = stem[:31 - len(suf)] + suf
            i += 1
        self._names.add(name.lower())
        return name

    def kv_sheet(self, title: str, heading: str, rows: list[tuple], *, note: str | None = None,
                 headers=("Campo", "Valor"), widths=(42, 90)) -> None:
        """Folha de metadados: título, nota e pares campo/valor (sem filtros: não é tabela de dados)."""
        name = self.sheet_name(title)
        ws = self.wb.create_sheet(name)
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A4"
        ws.append([self.text(ws, heading, font=TITLE_FONT)])
        ws.append([self.text(ws, note or "", font=NOTE_FONT)])
        ws.append([self.text(ws, h, font=HEAD_FONT) for h in headers])
        n = 0
        for row in rows:
            if row and row[0] == "§":                   # subtítulo de seção
                ws.append([self.text(ws, row[1], font=META_FONT)])
            else:
                ws.append([self.text(ws, row[0], font=Font(bold=True))] + [self.value(ws, v) for v in row[1:]])
            n += 1
        self.stats.sheets.append((name, heading, n, len(headers)))

    def table_sheet(self, title: str, content: str, df: pd.DataFrame, *, tz: str | None = None, model: bool = False,
                    comments: dict[str, str] | None = None) -> list[str]:
        """Tabela de dados completa (cabeçalho = nomes EXATOS das colunas). Divide explicitamente se exceder o Excel."""
        if df.shape[1] > EXCEL_MAX_COLS:
            raise WorkbookLimitError(f"'{content}' tem {df.shape[1]} colunas (> {EXCEL_MAX_COLS} do Excel).")
        kinds = [_col_kind(df[c], c, model) for c in df.columns]
        parts = max(1, math.ceil(len(df) / DATA_ROWS_PER_SHEET))
        names = []
        for p in range(parts):
            lo, hi = p * DATA_ROWS_PER_SHEET, min(len(df), (p + 1) * DATA_ROWS_PER_SHEET)
            name = self.sheet_name(title if parts == 1 else f"{title[:24]} p{p + 1}")
            names.append(name)
            ws = self.wb.create_sheet(name)
            ws.freeze_panes = "B2"
            for i, c in enumerate(df.columns, start=1):
                ws.column_dimensions[get_column_letter(i)].width = max(11, min(34, len(str(c)) + 3)) if kinds[i - 1] != "time" else 21
            ws.auto_filter.ref = f"A1:{get_column_letter(max(1, df.shape[1]))}{max(1, hi - lo) + 1}"
            head = []
            for c in df.columns:
                unit, desc, _ = COL.describe(str(c))
                ref = COL.time_reference(str(c), tz, model=model)
                tip = (comments or {}).get(str(c)) or f"{desc}\nUnidade: {unit}" + (f"\nReferência temporal: {ref}" if ref else "")
                head.append(self.text(ws, c, font=HEAD_FONT, comment=tip))
            for cell in head:
                cell.fill = HEAD_FILL
            ws.append(head)
            cols = [df[c].to_numpy() for c in df.columns]
            for r in range(lo, hi):
                ws.append([self._cell(ws, cols[j][r], kinds[j]) for j in range(len(cols))])
            self.stats.sheets.append((name, content + (f" — parte {p + 1} de {parts}, linhas {lo + 1}–{hi}" if parts > 1 else ""),
                                      hi - lo, df.shape[1]))
        if parts > 1:
            self.stats.split.append(f"'{content}': {len(df)} linhas divididas em {parts} folhas ({', '.join(names)}) — "
                                    f"limite de {EXCEL_MAX_ROWS:,} linhas por folha do Excel. Nenhuma linha omitida.")
        return names

    def _cell(self, ws, v, kind: str):
        if kind == "time":
            if isinstance(v, str):
                t = _parse_time(v)
                return self.when(ws, t) if t is not None else self.text(ws, v)
            return self.value(ws, v)
        if kind == "num":
            return self.number(ws, v) if v is not None and not (isinstance(v, str)) else self.value(ws, v)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            if isinstance(v, float):
                self.stats.nan += 1
            return WriteOnlyCell(ws, value=None)
        return self.value(ws, v)


_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?Z?$")


def _parse_time(s: str) -> datetime | None:
    if not _TIME_RE.match(s):
        return None
    try:
        return datetime.fromisoformat(s.rstrip("Z").replace(" ", "T"))
    except ValueError:
        return None


def _col_kind(series: pd.Series, name: str, model: bool) -> str:
    if name.startswith("timestamp"):
        sample = series.dropna().head(50)
        if len(sample) and all(isinstance(x, str) and _parse_time(x) is not None for x in sample):
            return "time"
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return "num"
    return "obj"


# ====================================================================== conteúdo
def _fmt_list(xs: Iterable) -> str:
    return "; ".join(str(x) for x in xs)


def _flatten(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        for i, v in enumerate(obj):
            out += _flatten(v, f"{prefix}[{i}]")
    else:
        out.append((prefix, obj))
    return out


def _identification(d: D.RunDossier, generated_at: str) -> list[tuple]:
    r, m = d.run, d.manifest
    sw = d.software
    rows: list[tuple] = [
        ("§", "Documento"),
        ("Tipo", "Planilha científica de rodada (documento DERIVADO; não é nova execução)"),
        ("Gerada em (UTC)", generated_at),
        ("Gerada por", f"{D.APP_NAME} {D.APP_VERSION}"),
        ("Origem dos dados", D.ORIGIN_LABELS[d.kind]),
        ("Nota", D.DERIVED_NOTE),
        ("§", "Experimento"),
        ("Microrrede de origem (nome na revisão)", d.microgrid.get("name")),
        ("UID da microrrede de origem", r.microgrid_uid),
        ("Incarnação da microrrede", r.incarnation or "não registrada"),
        ("Cenário", d.scenario_name),
        ("UID do cenário", r.scenario_uid),
        ("Versão do cenário", r.scenario_version),
        ("Impressão digital da versão (SHA-256)", r.scenario_fingerprint),
        ("Revisão do inventário", r.config_revision),
        ("Impressão digital da revisão (SHA-256)", r.config_fingerprint),
        ("UID da rodada", r.run_uid),
        ("Pedido (request_id)", r.request_id),
        ("Estado", d.state_label),
        ("Iniciada em (UTC)", r.created_at),
        ("Finalizada em (UTC)", r.finished_at),
        ("§", "Procedência do software que EXECUTOU a rodada"),
        ("Aplicação", sw.get("app")),
        ("Runtime", sw.get("runtime")),
        ("Python / numpy / pandas / scipy", f"{sw.get('python')} / {sw.get('numpy')} / {sw.get('pandas')} / {sw.get('scipy')}"),
        ("Código científico (SHA-256)", (sw.get("science") or {}).get("sha256")),
        ("Código científico (arquivos / caminhos)", f"{(sw.get('science') or {}).get('files')} · "
                                                    f"{_fmt_list((sw.get('science') or {}).get('paths') or [])}"),
        ("Formato do manifesto", f"{m.get('format')} v{m.get('format_version')}"),
    ]
    if d.microgrid.get("name_at_export") and d.microgrid.get("name_at_export") != d.microgrid.get("name"):
        rows.insert(8, ("Nome da microrrede na exportação", d.microgrid.get("name_at_export")))
    if d.archive:
        a = d.archive
        rows += [("§", "Estudo arquivado (esta instalação)"),
                 ("Nota", "Resultados produzidos na ORIGEM e apenas consultados nesta instalação."),
                 ("ID local do estudo (archive_uid)", a.get("archive_uid")), ("Identidade do conteúdo", a.get("content_id")),
                 ("SHA-256 do pacote", a.get("package_sha256")), ("Exportado em", a.get("exported_at")),
                 ("Importado em", a.get("imported_at")), ("Formato do pacote", a.get("format"))]
    return rows


def _indicator_rows(d: D.RunDossier) -> list[tuple]:
    rows = []
    for ind in D.indicators(d):
        rows.append((ind.label, ind.value if ind.value is not None else "não disponível", ind.unit, ind.key, ind.source,
                     ind.note))
    for a in d.engine_warnings():
        rows.append(("Aviso do motor", a, "—", "avisos", "StoredRun.summary", ""))
    return rows


def _equipment_rows(d: D.RunDossier) -> tuple[list[str], list[list]]:
    head = ["id", "tipo", "nome", "tag", "habilitado no inventário", "potência nominal registrada [kW|kWp]",
            "energia nominal [kWh]", "SOC mín. [%]", "SOC máx. [%]", "origem dos limites de SOC", "quantidade/unidades",
            "potência máx. por unidade [kW]", "Pmín [kW]", "Pmáx [kW]", "referência de catálogo",
            "disponibilidade no cenário", "situação na rodada", "motivo"]
    rows = []
    for e in d.equipment():
        ref = e["reference"]
        rows.append([e["id"], KIND_LABELS.get(e["kind"], e["kind"]), e["name"], e["tag"], bool(e["enabled"]),
                     ref.get("nominal_kW"), ref.get("energy_kWh"), ref.get("soc_min_pct"), ref.get("soc_max_pct"),
                     ref.get("soc_limits_source"), ref.get("quantity", ref.get("count", ref.get("arrays"))),
                     ref.get("unit_max_kW"), ref.get("pmin_kW"), ref.get("pmax_kW"), ref.get("reference"),
                     e["availability"], e["situation"], e["situation_reason"]])
    return head, rows


def _initial_rows(d: D.RunDossier) -> tuple[list[str], list[list]]:
    from seeds2.operation import initialization as I

    head = ["id", "tipo", "nome", "disponibilidade", "estado inicial", "SOC inicial [%]", "potência inicial [kW]",
            "unidades em operação", "nota"]
    rows = []
    for e in d.equipment():
        st = e["state"]
        states = I.THERMAL_STATES if e["kind"] == "thermal" else I.DISPATCH_STATES
        rows.append([e["id"], KIND_LABELS.get(e["kind"], e["kind"]), e["name"], e["availability"] or "não definido",
                     states.get(st.get("state"), st.get("state")) if "state" in st else None,
                     st.get("soc0_pct"), st.get("power_kW"), st.get("units_on"), st.get("note") or None])
    return head, rows


def _strategy_rows(d: D.RunDossier) -> list[tuple]:
    m = d.manifest
    s = m.get("strategy") or {}
    eng = (d.run.outcome or {}).get("effective_engine") or {}
    rows: list[tuple] = [("§", "Função objetivo (única no EMS V1.6)"),
                         ("Função objetivo", (m.get("objective") or {}).get("label")),
                         ("Chave", (m.get("objective") or {}).get("key"))]
    rows += [("Termo", t) for t in (m.get("objective") or {}).get("terms") or []]
    rows += [("§", "Estratégia gravada no cenário (versão executada)"),
             ("Algoritmo", SG.ALGORITHMS.get(s.get("algorithm"), s.get("algorithm")))]
    for k, lab in SG.LABELS.items():
        cur = s
        for part in k.split("."):
            cur = (cur or {}).get(part) if isinstance(cur, dict) else None
        rows.append((lab, cur))
    rows += [("Meta penalizada", s.get("meta_penalizada")), ("Validação dinâmica do H₂", s.get("validar_h2"))]
    rows += [("§", "Parâmetros fixos do motor V1.6 (não configuráveis)")] + list((m.get("engine_fixed") or {}).items())
    rows += [("§", "Configuração efetiva do motor (registrada na conclusão)")] + _flatten(eng)
    rows += [("§", "Janela da missão")] + _flatten(m.get("mission") or {})
    return rows


def _provenance_rows(d: D.RunDossier) -> list[tuple]:
    rows: list[tuple] = [("§", "Dados gravados da rodada (SHA-256 do conteúdo, conferido nesta leitura)")]
    for n in d.data_names():
        idx = d.run.data[n]
        rows.append((n, idx["sha256"], idx["size"], idx.get("media_type")))
    rows.append(("§", "Previsões do cenário (série normalizada e arquivo original)"))
    for slot, e in d.forecasts().items():
        rows.append((f"{slot} · série normalizada (SHA-256)", e.get("data"), e.get("n_points"), e.get("label")))
        if e.get("blob"):
            rows.append((f"{slot} · arquivo original (SHA-256)", e.get("blob"), None, None))
    rows.append(("§", "Manifesto científico da rodada (imutável, achatado; texto íntegro no .seeds2study.zip)"))
    rows += [(k, v, None, None) for k, v in _flatten(d.manifest)]
    if d.run.outcome:
        rows.append(("§", "Desfecho registrado (outcome)"))
        rows += [(k, v, None, None) for k, v in _flatten(d.run.outcome)]
    if d.run.error:
        rows.append(("§", "Erro registrado"))
        rows += [(k, v, None, None) for k, v in _flatten(d.run.error)]
    return rows


def _dictionary(d: D.RunDossier, tables: list[tuple[str, pd.DataFrame, bool]]) -> list[list]:
    out = []
    for sheet, df, model in tables:
        for c in df.columns:
            unit, desc, known = COL.describe(str(c))
            if model and not known:
                desc = "Saída do modelo físico preservada do arquivo original (unidade não declarada no arquivo)."
            out.append([sheet, str(c), unit, COL.time_reference(str(c), d.timezone, model=model) or "", desc,
                        str(df[c].dtype), int(df[c].isna().sum())])
    return out


def _table_sheet_simple(book: _Book, title: str, content: str, head: list[str], rows: list[list]) -> None:
    name = book.sheet_name(title)
    ws = book.wb.create_sheet(name)
    ws.freeze_panes = "B2"
    for i, h in enumerate(head, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(44, len(h) + 4))
    ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{max(1, len(rows)) + 1}"
    hcells = [book.text(ws, h, font=HEAD_FONT) for h in head]
    for c in hcells:
        c.fill = HEAD_FILL
    ws.append(hcells)
    for r in rows:
        ws.append([book.value(ws, v) for v in r])
    book.stats.sheets.append((name, content, len(rows), len(head)))


# ====================================================================== montagem
@dataclass
class WorkbookResult:
    data: bytes
    sheets: list[tuple[str, str, int, int]]
    warnings: list[str]


def build_workbook(d: D.RunDossier, *, generated_at: str | None = None, progress=None) -> WorkbookResult:
    generated_at = generated_at or D.utc_now()
    say = progress or (lambda _m: None)
    tables: list[tuple[str, str, pd.DataFrame, bool]] = []
    if d.concluded:
        for name, title, content in ((D.CSV_INPUTS, "06 Entradas", "Entradas da missão (entradas/missao.csv)"),
                                     (D.CSV_OUTPUTS, "07 Despacho EMS", "Despacho EMS (saidas/despacho_ems.csv)")):
            if d.has(name):
                tables.append((title, content, d.table(name), False))
        for slot in ("demand", "climate"):
            if slot in d.forecasts():
                tables.append((f"08 Previsão {'demanda' if slot == 'demand' else 'clima'}",
                               f"Previsão {contracts.FORECAST_SLOTS.get(slot, slot)} — série ORIGINAL normalizada do cenário "
                               f"(relógio de parede do fuso {d.forecasts()[slot].get('timezone') or 'não declarado'})",
                               d.forecast_frame(slot), False))
        for name in d.model_tables():
            stem = name[len("modelos/"):-len(".csv")]
            tables.append((f"09 {stem}", f"Dados do modelo físico ({name})", d.table(name), True))
    cells = sum(df.shape[0] * df.shape[1] for _, _, df, _ in tables)
    if cells > MAX_CELLS:
        raise WorkbookLimitError(
            f"As séries desta rodada somam {cells:,} células (limite desta exportação: {MAX_CELLS:,}). Para análise "
            "integral sem perda, use o pacote científico .seeds2study.zip (CSVs originais).")
    book = _Book()
    say("Montando identificação e indicadores")
    index_ws = book.wb.create_sheet(book.sheet_name("00 Índice"))
    book.kv_sheet("01 Identificação", "Identificação da rodada e procedência", _identification(d, generated_at),
                  note="Identificadores científicos preservados da rodada original.")
    if d.concluded:
        _table_sheet_simple(book, "02 Indicadores", "Indicadores (valores persistidos, sem recálculo)",
                            ["indicador", "valor", "unidade", "chave", "fonte", "definição / nota"], _indicator_rows(d))
    else:
        err = d.run.error or {}
        book.kv_sheet("02 Diagnóstico", "Diagnóstico — rodada NÃO concluída (sem resultados)",
                      [("Estado", d.state_label), ("Tipo", err.get("kind")), ("Exceção", err.get("type")),
                       ("Mensagem", err.get("message"))]
                      + [("Verificação do motor", f"[{i.get('level')}] {i.get('message')}") for i in d.engine_check_items()]
                      + [("Rastreamento (final)", err.get("traceback"))],
                      note="Rodada não concluída: nenhuma série de resultado foi gravada; nenhum indicador é apresentado.")
    head, rows = _equipment_rows(d)
    _table_sheet_simple(book, "03 Equipamentos", f"Inventário de referência (revisão {d.run.config_revision}) e situação "
                                                 "na rodada", head, rows)
    head, rows = _initial_rows(d)
    _table_sheet_simple(book, "04 Condições iniciais", "Estados iniciais declarados no cenário", head, rows)
    book.kv_sheet("05 Estratégia EMS", "Estratégia e parâmetros do EMS", _strategy_rows(d),
                  note="Somente opções existentes do EMS V1.6, tal como gravadas na versão executada.")
    for title, content, df, model in tables:
        say(f"Gravando {content}")
        book.table_sheet(title, content, df, tz=d.timezone, model=model)
    say("Gravando procedência e dicionário")
    book.kv_sheet("10 Procedência", "Procedência, hashes e manifesto da rodada", _provenance_rows(d),
                  headers=("Campo / dado", "Valor / SHA-256", "Tamanho (bytes) / pontos", "Tipo / rótulo"),
                  widths=(58, 70, 20, 30),
                  note="Hashes SHA-256 dos dados originais; o manifesto não é reescrito, apenas apresentado.")
    dict_rows = _dictionary(d, [(t, df, m) for t, _, df, m in tables])
    _table_sheet_simple(book, "11 Dicionário de dados", "Unidade, referência temporal e significado de cada coluna",
                        ["folha", "coluna", "unidade", "referência temporal", "descrição", "tipo", "valores ausentes"],
                        dict_rows)
    st = book.stats
    warnings = list(st.split)
    if st.nan:
        warnings.append(f"{st.nan} valor(es) ausente(s) (NaN) gravado(s) como célula VAZIA (nunca zero).")
    if st.inf:
        warnings.append(f"{st.inf} valor(es) infinito(s) gravado(s) como texto 'inf'/'-inf' (o Excel não representa ±∞).")
    if st.big_int:
        warnings.append(f"{st.big_int} inteiro(s) acima de 2^53 gravado(s) como texto (precisão do Excel).")
    if st.illegal:
        warnings.append(f"{st.illegal} texto(s) com caracteres de controle ilegais no XLSX: caracteres substituídos por U+FFFD.")
    if st.truncated:
        warnings.append(f"{st.truncated} texto(s) acima de 32.767 caracteres encurtado(s) e marcado(s) (íntegros no .seeds2study.zip).")
    ws = index_ws
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 100
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 10
    ws.append([book.text(ws, "SEEDS2 — Planilha científica da rodada", font=TITLE_FONT)])
    ws.append([book.text(ws, f"{d.scenario_name} · versão {d.run.scenario_version} · rodada {d.run_uid} · "
                             f"{d.state_label}", font=META_FONT)])
    ws.append([book.text(ws, D.DERIVED_NOTE, font=NOTE_FONT)])
    ws.append([book.text(ws, "Precisão: números gravados com a representação decimal exata do double persistido; "
                             "o formato de exibição não altera o valor. Célula vazia = valor ausente. Datas/horas sem fuso "
                             "no Excel: a referência de cada coluna está no comentário do cabeçalho e no dicionário.",
                         font=NOTE_FONT)])
    ws.append([])
    hc = [book.text(ws, h, font=HEAD_FONT) for h in ("Folha", "Conteúdo", "Linhas", "Colunas")]
    for c in hc:
        c.fill = HEAD_FILL
    ws.append(hc)
    for name, content, n, k in st.sheets:
        ws.append([book.text(ws, name), book.text(ws, content), book.number(ws, n), book.number(ws, k)])
    ws.append([])
    ws.append([book.text(ws, "Avisos da exportação", font=META_FONT)])
    for w in warnings or ["Nenhum: todas as séries foram representadas integralmente."]:
        ws.append([book.text(ws, "•"), book.text(ws, w)])
    ws.append([book.text(ws, "Gerada em (UTC)"), book.text(ws, generated_at)])
    say("Compactando o arquivo .xlsx")
    buf = io.BytesIO()
    book.wb.properties.creator = f"{D.APP_NAME} {D.APP_VERSION}"
    book.wb.properties.title = f"SEEDS2 · rodada {d.run_uid}"
    book.wb.save(buf)
    return WorkbookResult(buf.getvalue(), list(st.sheets), warnings)


__all__ = ["CELL_TEXT_MAX", "DATA_ROWS_PER_SHEET", "MAX_CELLS", "WorkbookLimitError", "WorkbookResult", "build_workbook"]
