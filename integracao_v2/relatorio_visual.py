"""UI-RESULTADOS-02 (melhoria 05) — RELATÓRIO PDF visual de uma rodada V2 concluída, com a identidade da Partitura.

Como é produzido (e por que assim):

* os gráficos, cartões e indicadores vêm do PRÓPRIO instrumento Partitura (``seeds2/ui/static/trama/partitura.js``,
  função ``relatorio``): o navegador redesenha, com as MESMAS raias, painéis e funções derivadas da interface, a missão
  COMPLETA (sem o zoom nem o recorte da tela), no tema claro e numa largura fixa, e serializa cada gráfico como SVG
  vetorial restrito (cores resolvidas). Não há uma segunda implementação dos gráficos no servidor;
* o servidor CONFERE o pacote: rodada concluída, evidência V2 verificada (``documentos.carregar`` → ``registro.verificar``:
  hashes, vistas regeneradas, reauditoria independente; sem solver) e o ``hash`` do pacote igual ao do marco Trama
  remontado AGORA a partir dos dados gravados (``trama_frame.montar``) — um pacote de outra rodada, de outra versão dos dados
  ou adulterado no identificador é recusado;
* o servidor só DIAGRAMA: capa, sumário, seções Operação (com o detalhamento por fonte e a Carga líquida), Visão Geral,
  Decisão, Economia e Evidência; a Evidência é montada aqui a partir do marco, do dossiê do 2D-B e da verificação (os
  mesmos dados da lente Evidência) e preserva o conteúdo científico do relatório técnico anterior (configuração, condições
  iniciais, método e escopo, advertências do preflight, discussão factual, procedência com SHA-256 e limitações);
* nada é recalculado nem gravado; o pacote do navegador é entrada NÃO confiável (tamanhos limitados, texto sempre escapado,
  SVG restrito por ``svg_pdf``). Rodadas falhas/interrompidas não têm relatório visual (há o diagnóstico de ``documentos``).
"""
from __future__ import annotations

import io
import json
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from seeds2.report import dossier as D

from . import documentos as DOC
from . import registro as RG
from . import svg_pdf as SVG
from . import trama_frame as TF

FORMATO, VERSAO = "seeds2-relatorio-partitura", 1
MAX_PACOTE = 80 * 1024 * 1024                # bytes do JSON recebido
MAX_SECOES, MAX_BLOCOS, MAX_FIGURAS, MAX_TEXTO, MAX_LINHAS = 12, 4000, 3000, 6000, 20000
SECOES = ("operacao", "fontes", "visao", "decisao", "economia", "evidencia")
TITULOS = {"operacao": "Operação", "fontes": "Operação — detalhamento por fonte", "visao": "Visão Geral", "decisao": "Decisão",
           "economia": "Economia", "evidencia": "Evidência"}

PAGE_W, PAGE_H = landscape(A4)
MX, MT, MB = 12 * mm, 17 * mm, 13 * mm
TW, TH = PAGE_W - 2 * MX, PAGE_H - MT - MB
# identidade da Partitura (trama.css): neutros + violeta SEEDS2 + cores das tecnologias vêm já resolvidas nos SVG
INK, INK2, INK3 = colors.HexColor("#171717"), colors.HexColor("#4d545b"), colors.HexColor("#7c848c")
SURF, SURF2, LINE = colors.HexColor("#f4f4f2"), colors.HexColor("#e9e9e6"), colors.HexColor("#d9d9d5")
VIO, VIO_E, VIO_C = colors.HexColor("#7a63e0"), colors.HexColor("#4a36b0"), colors.HexColor("#c4bdec")
ESC, ESC2 = colors.HexColor("#0a0a0a"), colors.HexColor("#1c1c1c")
OK, WARN, BAD, INFO = colors.HexColor("#1e7a50"), colors.HexColor("#a56400"), colors.HexColor("#b8323a"), colors.HexColor("#2a6fb5")
ORIGENS = {"selado": ("SELADO", INK3), "derivado": ("DERIVADO", INFO), "declarado": ("DECLARADO", WARN), "servidor": ("SERVIDOR", OK)}


class PacoteInvalido(ValueError):
    """O pacote do navegador não serve para o relatório desta rodada (mensagem apresentável)."""


# ====================================================================================================== validação
def _txt(x, n: int = MAX_TEXTO) -> str:
    s = "" if x is None else str(x)
    return s[:n]


def validar(pacote, *, run_uid: str, frame_hash: str) -> dict:
    """Estrutura, limites e identidade do pacote (o conteúdo gráfico é validado na diagramação por ``svg_pdf``)."""
    if not isinstance(pacote, dict) or pacote.get("formato") != FORMATO or pacote.get("versao") != VERSAO:
        raise PacoteInvalido("Pacote do relatório em formato desconhecido (esperado seeds2-relatorio-partitura v1).")
    if pacote.get("rodada") != run_uid:
        raise PacoteInvalido("O pacote do relatório pertence a outra rodada.")
    if pacote.get("hash") != frame_hash:
        raise D.DossierIntegrityError("O pacote do relatório não corresponde aos dados gravados desta rodada (hash do marco "
                                      "Trama diferente). Nenhum documento é gerado.")
    secs = pacote.get("secoes")
    if not isinstance(secs, list) or not secs or len(secs) > MAX_SECOES:
        raise PacoteInvalido("Pacote do relatório sem seções válidas.")
    ids = [s.get("id") if isinstance(s, dict) else None for s in secs]
    if any(i not in SECOES for i in ids) or len(set(ids)) != len(ids):
        raise PacoteInvalido("Pacote do relatório com seções desconhecidas ou repetidas.")
    nb = nf = 0

    def blocos(lista):
        nonlocal nb, nf
        if not isinstance(lista, list):
            raise PacoteInvalido("Bloco do relatório malformado.")
        for b in lista:
            nb += 1
            if not isinstance(b, dict) or nb > MAX_BLOCOS:
                raise PacoteInvalido("Blocos demais (ou malformados) no pacote do relatório.")
            if b.get("tipo") == "figura":
                nf += 1
            elif b.get("tipo") == "galeria":
                itens = b.get("itens") or []
                nf += sum(1 for x in itens if isinstance(x, dict) and x.get("tipo") == "figura")
                if not isinstance(itens, list):
                    raise PacoteInvalido("Galeria malformada.")
            elif b.get("tipo") == "tabela" and len(b.get("linhas") or []) > MAX_LINHAS:
                raise PacoteInvalido("Tabela longa demais no pacote do relatório.")
            if nf > MAX_FIGURAS:
                raise PacoteInvalido("Gráficos demais no pacote do relatório.")
    for s in secs:
        blocos(s.get("blocos") or [])
        for sub in s.get("subsecoes") or []:
            if not isinstance(sub, dict):
                raise PacoteInvalido("Subseção malformada.")
            blocos(sub.get("blocos") or [])
    return {"secoes": len(secs), "blocos": nb, "figuras": nf}


def ler_pacote(dado) -> dict:
    """``dado`` = dict (do componente) ou texto/bytes JSON. Limita o tamanho antes de interpretar."""
    if isinstance(dado, dict):
        return dado
    if isinstance(dado, (bytes, bytearray)):
        if len(dado) > MAX_PACOTE:
            raise PacoteInvalido("Pacote do relatório grande demais.")
        dado = dado.decode("utf-8")
    if not isinstance(dado, str) or len(dado) > MAX_PACOTE:
        raise PacoteInvalido("Pacote do relatório ausente ou grande demais.")
    try:
        return json.loads(dado)
    except ValueError as exc:
        raise PacoteInvalido(f"Pacote do relatório não é JSON válido ({exc}).") from exc


# ====================================================================================================== estilos
def _estilos() -> dict:
    from seeds2.report import run_pdf as RP

    RP._fonts()
    b = dict(fontName="DV", textColor=INK, fontSize=8.6, leading=11.8)
    return {
        "corpo": ParagraphStyle("corpo", **b, spaceAfter=3),
        "peq": ParagraphStyle("peq", **{**b, "fontSize": 7.2, "leading": 9.4, "textColor": INK2}, spaceAfter=2),
        "nota": ParagraphStyle("nota", **{**b, "fontSize": 7.2, "leading": 9.4, "textColor": INK3}, spaceBefore=2, spaceAfter=6),
        "cel": ParagraphStyle("cel", **{**b, "fontSize": 7.2, "leading": 9.0}),
        "celn": ParagraphStyle("celn", **{**b, "fontSize": 7.2, "leading": 9.0, "alignment": 2}),
        "mono": ParagraphStyle("mono", **{**b, "fontSize": 6.6, "leading": 8.4, "textColor": INK2}),
        "th": ParagraphStyle("th", **{**b, "fontSize": 7.0, "leading": 8.8, "fontName": "DV-B", "textColor": INK2}),
        "fig": ParagraphStyle("fig", **{**b, "fontSize": 9.6, "leading": 12, "fontName": "DV-B"}, spaceBefore=4, spaceAfter=2, keepWithNext=1),
        "h2": ParagraphStyle("h2", **{**b, "fontSize": 10.5, "leading": 13.5, "fontName": "DV-B", "textColor": VIO_E}, spaceBefore=8,
                             spaceAfter=4, keepWithNext=1),
        "sub": ParagraphStyle("sub", **{**b, "fontSize": 14, "leading": 17, "fontName": "DV-B"}, keepWithNext=1),
        "subr": ParagraphStyle("subr", **{**b, "fontSize": 7.6, "leading": 9.6, "textColor": INK3}, spaceAfter=6, keepWithNext=1),
        "ct": ParagraphStyle("ct", **{**b, "fontSize": 7.4, "leading": 9.2, "fontName": "DV-B", "textColor": INK2}),
        "cg": ParagraphStyle("cg", **{**b, "fontSize": 13.5, "leading": 16, "fontName": "DV-B"}),
        "kl": ParagraphStyle("kl", **{**b, "fontSize": 6.8, "leading": 8.6, "fontName": "DV-B", "textColor": INK2}),
        "kv": ParagraphStyle("kv", **{**b, "fontSize": 14, "leading": 16.5, "fontName": "DV-B"}),
        "ks": ParagraphStyle("ks", **{**b, "fontSize": 6.8, "leading": 8.6, "textColor": INK3}),
        "toc0": ParagraphStyle("toc0", **{**b, "fontSize": 10.5, "leading": 15, "fontName": "DV-B"}),
        "toc1": ParagraphStyle("toc1", **{**b, "fontSize": 8.2, "leading": 11, "leftIndent": 14, "textColor": INK2}),
        "bullet": ParagraphStyle("bullet", **b, leftIndent=10, bulletIndent=2, spaceAfter=2, bulletFontName="DV"),
    }


ST: dict = {}


def _p(texto: str, estilo: str = "corpo") -> Paragraph:
    return Paragraph(texto, ST[estilo])


def _e(x, n: int = MAX_TEXTO) -> str:
    from seeds2.report.run_pdf import t

    return t(_txt(x, n))


# ====================================================================================================== peças visuais
class Secao(Flowable):
    """Abertura de seção: faixa escura da Partitura com o número em violeta (entra no sumário e nos marcadores do PDF).
    ``chips`` = indicadores da seção desenhados à direita da faixa, como na barra da Partitura (rótulo · valor · origem)."""

    def __init__(self, n: int, titulo: str, sub: str = "", chips: list | None = None):
        super().__init__()
        self.n, self.titulo, self.sub = n, titulo, sub
        self.chips = [q for q in chips or [] if isinstance(q, dict)][:8]
        self.width, self.height = TW, 64

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(ESC)
        c.roundRect(0, 0, self.width, self.height, 10, stroke=0, fill=1)
        c.setFillColor(VIO)
        c.roundRect(0, 0, 6, self.height, 3, stroke=0, fill=1)
        c.setFont("DV-B", 8)
        c.setFillColor(colors.HexColor("#b3a8ff"))
        c.drawString(20, self.height - 19, f"SEÇÃO {self.n:02d}")
        c.setFont("DV-B", 20)
        c.setFillColor(colors.HexColor("#f3f3f1"))
        c.drawString(20, self.height - 42, self.titulo)
        if self.sub:
            c.setFont("DV", 8.4)
            c.setFillColor(colors.HexColor("#a9afb5"))
            c.drawString(20, 10, _corta(self.sub, 70 if self.chips else 150))
        x0, cw = self.width - 4 * 128 - 8, 128
        for i, q in enumerate(self.chips):
            x, y = x0 + (i % 4) * cw, self.height - 30 - (i // 4) * 28
            c.setFillColor(ESC2)
            c.roundRect(x, y, cw - 6, 25, 5, stroke=0, fill=1)
            nome, cor = ORIGENS.get(q.get("o"), ("", INK3))
            c.setFont("DV", 5.8)
            c.setFillColor(colors.HexColor("#a9afb5"))
            rot, livre = str(q.get("t") or "").upper(), cw - 18 - (_sw(nome, 4.8) * 1.15 if nome else 0)
            while rot and _sw(rot, 5.8) > livre:
                rot = rot[:-2].rstrip() + "…" if len(rot) > 2 else ""
            c.drawString(x + 6, y + 16.5, rot)
            c.setFont("DV-B", 9.4)
            c.setFillColor(colors.HexColor("#f3f3f1"))
            val = _corta(f"{q.get('v') or ''}{(' ' + q['u']) if q.get('u') else ''}", 26)
            c.drawString(x + 6, y + 5, val)
            if nome:
                c.setFont("DV-B", 4.8)
                c.setFillColor(colors.HexColor("#8b7cff") if q.get("o") != "derivado" else colors.HexColor("#6fb0ee"))
                c.drawRightString(x + cw - 11, y + 17, nome)
        c.restoreState()


class Subtitulo(Flowable):
    """Cabeçalho de subseção (uma fonte do explorador de recursos): barra violeta + título + UID."""

    def __init__(self, titulo: str, rotulo: str = ""):
        super().__init__()
        self.titulo, self.rotulo = titulo, rotulo
        self.width, self.height = TW, 34

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(VIO)
        c.rect(0, 6, 3.5, 24, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("DV-B", 13.5)
        c.drawString(12, 17, _corta(self.titulo, 110))
        if self.rotulo:
            c.setFont("DV", 7.4)
            c.setFillColor(INK3)
            c.drawString(12, 6, _corta(self.rotulo, 160))
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(0, 0.5, self.width, 0.5)
        c.restoreState()


class Legenda(Flowable):
    """Amostras da legenda do gráfico (as mesmas da interface): área, linha, tracejado, pontilhado, hachura, ponto."""

    def __init__(self, itens: list, largura: float = TW, fonte: float = 7.2):
        super().__init__()
        self.itens = [i for i in itens or [] if isinstance(i, dict)][:40]
        self.largura, self.fs = largura, fonte
        self.linhas = []
        x, linha = 0.0, []
        for it in self.itens:
            t = _corta(it.get("t"), 80)
            w = 18 + _sw(t, self.fs) + 12
            if x + w > largura and linha:
                self.linhas.append(linha)
                linha, x = [], 0.0
            linha.append((x, t, it))
            x += w
        if linha:
            self.linhas.append(linha)
        self.width, self.height = largura, len(self.linhas) * (self.fs + 5.5) + (2 if self.linhas else 0)

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        lh = self.fs + 5.5
        for n, linha in enumerate(self.linhas):
            y = self.height - (n + 1) * lh + 2
            for x, t, it in linha:
                cor = _hexcor(it.get("cor"))
                tipo = it.get("tipo") or "area"
                c.saveState()
                c.setFillColor(cor)
                c.setStrokeColor(cor)
                if tipo in ("linha", "tracejado", "pontilhado"):
                    c.setLineWidth(1.8)
                    c.setDash([3, 2] if tipo == "tracejado" else [1, 1.4] if tipo == "pontilhado" else [])
                    c.line(x, y + self.fs * .38, x + 13, y + self.fs * .38)
                elif tipo == "ponto":
                    c.circle(x + 6, y + self.fs * .38, 2.8, stroke=0, fill=1)
                elif tipo == "hachura":
                    c.setFillColor(colors.white)
                    c.rect(x, y, 13, self.fs * .8, stroke=0, fill=1)
                    p = c.beginPath()
                    p.rect(x, y, 13, self.fs * .8)
                    c.clipPath(p, stroke=0, fill=0)
                    c.setLineWidth(1.2)
                    for k in range(-8, 16, 3):
                        c.line(x + k, y, x + k + 8, y + 8)
                else:
                    c.roundRect(x, y, 13, self.fs * .8, 1.5, stroke=0, fill=1)
                c.restoreState()
                c.setFont("DV", self.fs)
                c.setFillColor(INK2)
                c.drawString(x + 17, y + 0.5, t)


def _corta(s, n: int) -> str:
    s = re.sub(r"[\x00-\x1f\x7f]", " ", "" if s is None else str(s))
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _sw(s: str, fs: float) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    return stringWidth(s, "DV", fs)


def _hexcor(v):
    return colors.HexColor(v) if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) else INK3


def _tag_origem(o) -> str:
    nome, cor = ORIGENS.get(o, (_txt(o, 20).upper(), INK3)) if o else ("", INK3)
    return f'<font name="DV-B" size="5.8" color="{cor.hexval().replace("0x", "#")}">{_e(nome)}</font>' if nome else ""


def kpis(itens: list, por: int = 4) -> Table:
    cel = []
    for q in [i for i in itens or [] if isinstance(i, dict)][:24]:
        val = _e(q.get("v"), 80) + (f' <font size="7.4" color="#4d545b">{_e(q.get("u"), 20)}</font>' if q.get("u") else "")
        cel.append([_p(f'{_e(q.get("t"), 80)}&nbsp;&nbsp;{_tag_origem(q.get("o"))}', "kl"), _p(val, "kv"),
                    _p(_e(q.get("sub"), 160), "ks") if q.get("sub") else Spacer(1, 1)])
    linhas = [cel[i:i + por] + [""] * (por - len(cel[i:i + por])) for i in range(0, len(cel), por)]
    if not linhas:
        return Spacer(1, 1)
    t = Table([[c if c else "" for c in ln] for ln in linhas], colWidths=[TW / por] * por, hAlign="LEFT")
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
    for r, ln in enumerate(linhas):
        for c, v in enumerate(ln):
            if v:
                est += [("BACKGROUND", (c, r), (c, r), SURF), ("LINEABOVE", (c, r), (c, r), 1.6, VIO_C),
                        ("BOX", (c, r), (c, r), 2.2, colors.white)]
    t.setStyle(TableStyle(est))
    return t


def cartao(q: dict, largura: float) -> Table:
    """Cartão da interface (título · selo · valor grande · linhas rótulo/valor · N/D · nota) como bloco do PDF."""
    corpo = []
    cab = _e(q.get("t"), 160) + (f'&nbsp;&nbsp;<font name="DV-B" size="6" color="#7c848c">{_e(q.get("tag"), 40).upper()}</font>'
                                  if q.get("tag") else "")
    corpo.append([_p(cab, "ct")])
    if q.get("big"):
        corpo.append([_p(_e(q.get("big"), 120), "cg")])
    if q.get("sub"):
        corpo.append([_p(_e(q.get("sub"), 400), "peq")])
    lin = [ln for ln in (q.get("linhas") or []) if isinstance(ln, list) and len(ln) == 2][:60]
    if lin:
        t = Table([[_p(_e(a, 120), "peq"), _p(f"<b>{_e(b, 160)}</b>", "celn")] for a, b in lin],
                  colWidths=[largura * .58 - 8, largura * .42 - 8])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2), ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE)]))
        corpo.append([t])
    tab = q.get("tabela")
    if isinstance(tab, list) and tab and all(isinstance(r, list) for r in tab):
        n = max(len(r) for r in tab[:200])
        t = Table([[_p(_e(c, 120), "th" if i == 0 else "cel") for c in (r + [""] * (n - len(r)))] for i, r in enumerate(tab[:200])],
                  colWidths=[(largura - 16) / n] * n)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.5, VIO), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        corpo.append([t])
    for nd in (q.get("nd") or [])[:20]:
        corpo.append([_p(f'<font name="DV-B" color="#a56400">N/D</font> — {_e(nd, 300)}', "peq")])
    if q.get("nota"):
        corpo.append([_p(_e(q.get("nota"), 1500), "nota")])
    t = Table(corpo, colWidths=[largura])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SURF), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (0, 0), 7),
                           ("BOTTOMPADDING", (0, -1), (-1, -1), 7), ("TOPPADDING", (0, 1), (-1, -1), 1.5),
                           ("LINEABOVE", (0, 0), (-1, 0), 1.6, _hexcor(q.get("acc")) if q.get("acc") else VIO_C)]))
    return t


def cartoes(itens: list, por: int = 3) -> Table | Spacer:
    its = [q for q in itens or [] if isinstance(q, dict)][:60]
    if not its:
        return Spacer(1, 1)
    w = TW / por
    linhas = [[cartao(q, w - 10) for q in its[i:i + por]] for i in range(0, len(its), por)]
    linhas = [ln + [""] * (por - len(ln)) for ln in linhas]
    t = Table(linhas, colWidths=[w] * por, hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    return t


def tabela(colunas: list, linhas: list, larguras: list | None = None, *, num: tuple = (), mono: tuple = (),
           fonte: str = "cel", largura: float = TW) -> Table:
    n = max([len(colunas)] + [len(r) for r in linhas[:1]]) if (colunas or linhas) else 1
    tot = sum(larguras) if larguras else n
    cw = [largura * w / tot for w in (larguras or [1] * n)]
    dados = [[_p(_e(c, 200), "th") for c in colunas]] if colunas else []
    if not num and linhas:                     # colunas numéricas (formato pt-BR) alinhadas à direita
        numero = re.compile(r"^[-−]?(\d{1,3}(\.\d{3})*|\d+)(,\d+)?( ?(%|kW|kWh|R\$|R\$/kWh))?$|^N/D$|^[-−]?\d\.\d+e[-+]\d+$")
        num = tuple(i for i in range(n) if sum(1 for r in linhas[:200] if i < len(r) and numero.match(str(r[i]).strip()))
                    >= 0.8 * min(len(linhas), 200) and any(i < len(r) and str(r[i]).strip() not in ("N/D",) for r in linhas[:200]))
    for r in linhas[:MAX_LINHAS]:
        r = list(r)[:n] + [""] * max(0, n - len(r))
        dados.append([_p(_e(c, 600), "celn" if i in num else "mono" if i in mono else fonte) for i, c in enumerate(r)])
    t = Table(dados, colWidths=cw, repeatRows=1 if colunas else 0, hAlign="LEFT")
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LINEBELOW", (0, -1), (-1, -1), 0.4, LINE)]
    if colunas:
        est += [("BACKGROUND", (0, 0), (-1, 0), SURF2), ("LINEBELOW", (0, 0), (-1, 0), 0.8, VIO)]
    for i in range(1 if colunas else 0, len(dados)):
        if i % 2 == 0:
            est.append(("BACKGROUND", (0, i), (-1, i), SURF))
    t.setStyle(TableStyle(est))
    return t


def kv(linhas: list, larguras=(0.30, 0.70)) -> Table:
    t = Table([[_p(_e(a, 200), "th"), _p(_e(b, 1200), "cel")] for a, b in linhas], colWidths=[TW * larguras[0], TW * larguras[1]],
              hAlign="LEFT")
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def caixa(texto: str, tom: str = "info") -> Table:
    bg = {"info": colors.HexColor("#eeecfb"), "warn": colors.HexColor("#fff4e0"), "bad": colors.HexColor("#fdecec")}[tom]
    barra = {"info": VIO, "warn": WARN, "bad": BAD}[tom]
    t = Table([[_p(texto)]], colWidths=[TW], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 2.4, barra),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def bullets(itens: list) -> list:
    return [Paragraph(x, ST["bullet"], bulletText="•") for x in itens]


# ====================================================================================================== blocos do pacote
CTX = {"escala": 0.744}                       # pt por px do desenho (largura útil ÷ largura de desenho do pacote)


def _figura(b: dict, largura: float = TW, altura_max: float | None = None, pequena: bool = False) -> list:
    """Título + legenda + gráfico vetorial + nota/fonte. Todos os gráficos usam a MESMA escala px → pt (textos com o mesmo
    tamanho em todo o documento); o gráfico só é reduzido se não couber na coluna ou, inteiro, numa página."""
    try:
        largura = min(largura, float(b.get("w") or 0) * CTX["escala"]) or largura
    except (TypeError, ValueError):
        pass
    tit = _p(_e(b.get("titulo"), 240), "ct" if pequena else "fig")
    leg = Legenda(b.get("legenda"), largura) if b.get("legenda") and not pequena else None
    rod = []
    if b.get("nota"):
        rod.append(_e(b.get("nota"), 1500))
    if b.get("fontes") and not pequena:
        rod.append("Fonte: " + _e(" · ".join(str(x) for x in b.get("fontes")[:8]), 400))
    nota = _p(" ".join(rod), "mono" if pequena else "nota") if rod else None
    ocup = tit.wrap(largura, TH)[1] + (leg.height + 4 if leg else 0) + (nota.wrap(largura, TH)[1] + 8 if nota else 0) + 10
    alvo = TH - ocup - float(b.get("_reserva") or 0)          # _reserva: espaço já ocupado na página (definido pelo servidor)
    fig = SVG.FiguraSVG(b.get("svg"), largura, altura_max=min(altura_max, alvo) if altura_max else alvo)
    return [x for x in (tit, leg, Spacer(1, 2) if leg else None, fig, nota) if x is not None]


def _galeria(b: dict) -> list:
    por = max(1, min(4, int(b.get("colunas") or 3)))
    w = TW / por
    out = [_p(_e(b.get("titulo"), 300), "h2")]
    if b.get("legenda"):
        out += [Legenda(b.get("legenda")), Spacer(1, 3)]
    if b.get("nota"):
        out.append(_p(_e(b.get("nota"), 1500), "nota"))
    cel = []
    for it in (b.get("itens") or [])[:MAX_FIGURAS]:
        if not isinstance(it, dict):
            continue
        if it.get("tipo") == "figura":
            partes = _figura(it, w - 8, altura_max=(TH - 40) / 3 - 22, pequena=True)
        elif it.get("tipo") == "tabela":
            partes = [_p(_e(it.get("titulo"), 200), "ct"), _p(_e(", ".join(it.get("colunas") or []), 400), "mono"),
                      _p(_e("; ".join(" · ".join(str(c) for c in r) for r in (it.get("linhas") or [])[:40]), 3000), "mono")]
        else:
            continue
        cel.append(partes)
    linhas = [cel[i:i + por] + [""] * (por - len(cel[i:i + por])) for i in range(0, len(cel), por)]
    if linhas:
        t = Table(linhas, colWidths=[w] * por, hAlign="LEFT")
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE)]))
        out.append(t)
    return out


def _bloco(b: dict) -> list:
    tipo = b.get("tipo")
    if tipo == "kpis":
        return [kpis(b.get("itens")), Spacer(1, 6)]
    if tipo == "figura":
        partes = _figura(b, TW / 2 - 8 if int(b.get("cols") or 1) == 2 else TW)
        extra = []
        if b.get("fatias"):
            extra = [tabela(["Fonte (injeção)", "Energia", "Participação"],
                            [[f.get("t"), f.get("v"), f.get("p")] for f in b["fatias"] if isinstance(f, dict)], [2.2, 1, 1],
                            num=(1, 2), largura=TW / 2 - 12)]
        if int(b.get("cols") or 1) == 2:
            return [_LadoALado(partes + extra)]
        return [KeepTogether(partes + extra), Spacer(1, 4)]
    if tipo == "galeria":
        return _galeria(b)
    if tipo == "cartoes":
        return [cartoes(b.get("itens")), Spacer(1, 2)]
    if tipo == "tabela":
        out = [_p(_e(b.get("titulo"), 300), "h2")] if b.get("titulo") else []
        out.append(tabela([_txt(c, 80) for c in (b.get("colunas") or [])], [list(r) for r in (b.get("linhas") or []) if isinstance(r, list)]))
        if b.get("nota"):
            out.append(_p(_e(b.get("nota"), 1500), "nota"))
        return out + [Spacer(1, 4)]
    if tipo == "texto":
        return [_p(_e(b.get("t"), 4000))]
    return []


def _lado(bf: dict, bc: dict | None) -> list:
    """Painel de uma fonte como na interface: gráfico à esquerda, cartões da missão à direita (os que couberem na altura da
    página; os demais seguem abaixo em grade)."""
    wl = TW * 0.70
    wr = TW - wl - 12
    partes = _figura(bf, wl)
    itens = [q for q in ((bc or {}).get("itens") or []) if isinstance(q, dict)]
    col, resto, acc = [], [], 0.0
    for q in itens:
        c = cartao(q, wr)
        hc = c.wrap(wr, TH)[1] + 8
        if not resto and acc + hc <= TH - 52:
            col += [c, Spacer(1, 8)]
            acc += hc
        else:
            resto.append(q)
    t = Table([[partes, col or [Spacer(1, 1)]]], colWidths=[wl + 12, wr], hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, 0), 12), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [t] + ([Spacer(1, 4), cartoes(resto)] if resto else [])


def _blocos(lista: list) -> list:
    """Sequência de blocos do pacote → flowables; um gráfico de painel (``lado``) seguido de cartões vira o painel lado a lado."""
    out, i = [], 0
    lista = [b for b in lista or [] if isinstance(b, dict)]
    while i < len(lista):
        b = lista[i]
        if b.get("tipo") == "figura" and b.get("lado"):
            prox = lista[i + 1] if i + 1 < len(lista) and lista[i + 1].get("tipo") == "cartoes" else None
            out += _lado(b, prox)
            i += 2 if prox else 1
            continue
        out += _bloco(b)
        i += 1
    return out


class _LadoALado(Flowable):
    """Dois blocos de meia página lado a lado (Energia por fonte | Participação), na ordem em que chegam."""
    fila: list = []

    def __init__(self, partes):
        super().__init__()
        self.partes = partes

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        return


def _par_lado_a_lado(story: list) -> list:
    """Agrupa blocos ``_LadoALado`` consecutivos numa tabela de duas colunas."""
    out, fila = [], []
    for f in story + [None]:
        if isinstance(f, _LadoALado):
            fila.append(f.partes)
            continue
        while fila:
            par = fila[:2]
            fila = fila[2:]
            par = par + [[Spacer(1, 1)]] * (2 - len(par))
            t = Table([par], colWidths=[TW / 2] * 2, hAlign="LEFT")
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
            out += [t, Spacer(1, 6)]
        if f is not None:
            out.append(f)
    return out


# ====================================================================================================== Evidência (servidor)
def _evidencia(f: dict, d, v, avisos_grupos) -> list:
    from integracao_v2 import preflight as PF
    from seeds2.report import run_pdf as RP

    r, ac, au, pr, sol = f["rodada"], f.get("aceitacao") or {}, f.get("auditoria"), f.get("procedencia") or {}, f["resumo"].get("solver") or {}
    est = {"aprovada": "aprovado", "coerente": "coerente", "incoerente": "INCOERENTE", "nao_aplicavel": "não aplicável", "nao_validada": "não validado"}
    out = [_p("Estado e integridade da rodada", "h2")]
    ok = v.ok if v is not None else None
    out.append(caixa(f"<b>{'Evidência verificada' if ok else 'EVIDÊNCIA COM PROBLEMAS'}</b> — {sum(1 for x, _ in v.itens if x)} de "
                     f"{len(v.itens)} verificações aprovadas pelo servidor nesta leitura (hashes, vistas regeneradas byte a byte e "
                     "reauditoria independente; sem solver). A verificação é refeita a cada abertura da rodada e a cada geração "
                     "deste relatório.", "info" if ok else "bad"))
    out.append(Spacer(1, 4))
    out.append(kv([("Rodada", r["uid"]), ("Estado", f"{r['estado']} · somente leitura"),
                   ("Missão completa", "sim" if f["resumo"].get("missao_completa") else "NÃO" if f["resumo"].get("missao_completa") is False else "N/D"),
                   ("Criada · finalizada (UTC)", f"{r.get('criada')} · {r.get('finalizada')}"),
                   ("Contexto", f"{r.get('contexto')}" + (" · dados SINTÉTICOS de ensaio" if r.get("sintetico") else "")),
                   ("Contrato de dados", f"v{r.get('versao_dados')}")]))
    out += [_p("Verificações do servidor nesta leitura", "h2")] + bullets([("✓ " if a else "✕ ") + _e(t) for a, t in v.itens])
    out.append(_p("Aceitação — três estados separados", "h2"))
    out.append(tabela(["Nível", "Estado", "Critério / motivo"],
                      [[nome, est.get((ac.get(k) or {}).get("estado"), (ac.get(k) or {}).get("estado") or "N/D"),
                        ((ac.get(k) or {}).get("criterio") or "estado não gravado") + (f" — {(ac.get(k) or {}).get('motivo')}" if (ac.get(k) or {}).get("motivo") else "")]
                       for k, nome in (("algebrica", "Algébrica"), ("dinamica", "Dinâmica"), ("fisica", "Física"))], [1, 1, 5]))
    out.append(_p(_e(ac.get("rotulo") or "") + " Aprovação algébrica e coerência dinâmica referem-se a MODELOS; nenhuma delas é "
                  "validação física (nenhum equipamento real foi ensaiado).", "nota"))
    out.append(_p("Auditoria independente da missão", "h2"))
    if au:
        out.append(kv([("Resultado", "aceita" if au.get("aceito") else "REJEITADA" if au.get("aceito") is False else "N/D"),
                       ("Método", au.get("metodo") or "não registrado"),
                       ("Verificações gravadas", "; ".join(f"{k}: {'✓' if x else '✕'}" for k, x in (au.get("verificacoes") or {}).items())),
                       ("Constatações", f"{au.get('constatacoes')} (" + " · ".join(f"{n} {k}" for k, n in (au.get('constatacoes_por_severidade') or {}).items()) + ")"),
                       ("Normalizações numéricas do PCC", str(au.get("normalizacoes_pcc"))),
                       ("Projeções numéricas de energia", str(au.get("projecoes_numericas_energia"))),
                       ("Tolerâncias", str(au.get("tolerancias")))]))
    else:
        out.append(_p("<b>N/D</b> — v2/auditoria.json não persistido nesta rodada.", "peq"))
    out.append(_p("Solver e critérios por decisão", "h2"))
    sw = pr.get("software") or {}
    out.append(kv([("Janelas resolvidas · ótimas", f"{sol.get('janelas_resolvidas', 'N/D')} · {sol.get('janelas_otimas', 'N/D')}"),
                   ("Gap relativo máximo", f"{sol.get('gap_rel_max')}"),
                   ("Solver", " · ".join(x for x in (f"Pyomo {sw['pyomo']}" if sw.get("pyomo") else "", f"HiGHS {sw['highs']}" if sw.get("highs") else "") if x) or "N/D")]))
    jan = f.get("janelas") or []
    out.append(tabela(["j", "τ (UTC)", "N", "aplic.", "classe", "terminação", "objetivo [R$]", "limite dual [R$]", "gap rel.", "var.", "bin.", "restr.", "valor futuro"],
                      [[_int(q.get("j")), _loc(f, q.get("k")), _int(q.get("Nk")),
                        _int(q.get("ap")), str(q.get("classe")), str(q.get("terminacao")), _n(q.get("objetivo"), 4), _n(q.get("limite_dual"), 4),
                        _sci(q.get("gap_rel")), _int(q.get("variaveis")), _int(q.get("binarias")), _int(q.get("restricoes")),
                        "válido" if q.get("sinal_qualidade") == "valido" else "indisponível"] for q in jan],
                      [0.5, 1.6, 0.5, 0.6, 0.9, 1.1, 1.1, 1.1, 0.8, 0.6, 0.6, 0.6, 0.9], num=(2, 3, 6, 7, 8, 9, 10, 11)))
    out.append(_p("Objetivo e limite dual são do MILP de cada janela (previsão), não custo realizado.", "nota"))
    out.append(_p("Procedência e versões", "h2"))
    out.append(kv([("Microrrede (UID · incarnação)", f"{pr.get('microrrede_uid')} · {pr.get('incarnacao')}"),
                   ("Cenário (UID · versão)", f"{pr.get('cenario_uid')} · v{pr.get('cenario_versao')}"),
                   ("Impressão digital do cenário", str(pr.get("cenario_impressao"))),
                   ("Inventário (revisão · impressão)", f"rev. {pr.get('inventario_revisao')} · {pr.get('inventario_impressao')}"),
                   ("Motor · formulações", f"{pr.get('motor')} · " + " · ".join(f"{k} {x}" for k, x in (pr.get("formulacoes") or {}).items())),
                   ("Integração · contrato de dados", f"{pr.get('integracao')} · v{pr.get('contrato_dados')}"),
                   ("Software", " · ".join(f"{k} {x}" for k, x in (pr.get("software") or {}).items())),
                   ("Código científico (SHA-256)", str(pr.get("codigo_cientifico_sha256"))), ("Declarante", str(pr.get("declarante"))),
                   ("Objetivo", f"{pr.get('objetivo')} · termos: {', '.join(pr.get('termos_objetivo') or []) or 'nenhum termo opcional'}"),
                   ("Rótulo do motor", str(pr.get("rotulo_motor")))]))
    if pr.get("alcance"):
        out.append(_p(_e(pr.get("alcance")), "nota"))
    out.append(_p("Arquivos da evidência (SHA-256 do conteúdo, conferido nesta leitura)", "h2"))
    out.append(tabela(["Arquivo", "SHA-256", "bytes"], [[n, s, f"{int(b):,}".replace(",", ".") if isinstance(b, (int, float)) else "N/D"]
                                                        for n, s, b in (f.get("arquivos") or [])], [1.5, 3.6, 0.6], num=(2,), mono=(1,)))
    out.append(_p("Tabelas originais gravadas", "h2"))
    linhas = []
    for nome, tb in (f.get("tabelas") or {}).items():
        sha = next((s for n, s, _b in (f.get("arquivos") or []) if n == nome), None)
        linhas.append([nome, str(len(tb.get("linhas") or [])), str(len(tb.get("colunas") or [])), sha or "N/D"])
    out.append(tabela(["Tabela", "linhas", "colunas", "SHA-256"], linhas, [1.4, 0.5, 0.5, 3.6], num=(1, 2), mono=(3,)))
    out.append(_p("As tabelas completas, valor a valor e sem arredondamento, estão na planilha Excel da rodada e no pacote "
                  ".seeds2study.zip (fonte portátil integral); a vista clássica da página da rodada também as mostra.", "nota"))
    grupos = avisos_grupos if isinstance(avisos_grupos, list) and avisos_grupos else ([["Advertências", f.get("avisos") or []]] if f.get("avisos") else [])
    out.append(_p(f"Advertências registradas · {len(f.get('avisos') or [])}", "h2"))
    if grupos:
        for g in grupos[:20]:
            if isinstance(g, list) and len(g) == 2 and isinstance(g[1], list):
                out.append(_p(f"<b>{_e(g[0], 200)}</b> ({len(g[1])})", "peq"))
                out += bullets([_e(a, 2000) for a in g[1][:300]])
    else:
        out.append(_p("Nenhuma advertência registrada nesta rodada.", "peq"))
    # --------- conteúdo científico do relatório técnico anterior (dossiê do 2D-B), preservado e reorganizado
    out.append(_p("Configuração da microrrede (inventário de referência)", "h2"))
    eq = list(d.equipment())
    out.append(tabela(["Equipamento", "Tecnologia", "Características registradas", "Disponibilidade", "Situação na rodada"],
                      [[e["name"] + (f" ({e['tag']})" if e.get("tag") else ""), RP.KIND_LABELS.get(e["kind"], e["kind"]), RP._equipment_text(e),
                        e["availability"] or "não definido", e["situation"] + (f" — {e['situation_reason']}" if e.get("situation_reason") else "")]
                       for e in eq], [1.5, 0.9, 3.0, 1.0, 1.6]))
    out.append(_p(f"Revisão {d.run.config_revision} do inventário (impressão digital {_e(d.run.config_fingerprint)}). Potências são "
                  "NOMINAIS registradas (não resultados); a disponibilidade é condição da rodada.", "nota"))
    out.append(_p("Condições iniciais declaradas no cenário", "h2"))
    linhas = []
    for e in eq:
        s, k = e["state"], e["kind"]
        linhas.append([e["name"], RP.KIND_LABELS.get(k, k), e["availability"] or "não definido",
                       RP.num(s.get("soc0_pct"), 1, "%") if k == "battery" else "não aplicável",
                       RP.num(s.get("power_kW"), 2, "kW") if k in ("pemfc", "thermal") else "não aplicável",
                       (str(s.get("units_on")) if s.get("units_on") is not None else "N/D") if k == "pemfc" else "não aplicável"])
    out.append(tabela(["Equipamento", "Tipo", "Disponibilidade", "SOC inicial", "Potência inicial", "Unidades ativas"], linhas,
                      [1.6, 1, 1.2, 0.9, 0.9, 0.9]))
    mis = (d.summary or {}).get("mission") or {}
    out.append(_p("Método e escopo", "h2"))
    out.append(_p(_e((d.manifest or {}).get("scope") or PF.ESCOPO)))
    out.append(kv([("Motor", ((d.manifest or {}).get("engine") or {}).get("label") or DOC.MOTOR), ("Formulação", str(mis.get("formulacao"))),
                   ("Passo Δ · N · m · H_L", f"{mis.get('delta_min')} min · {mis.get('N')} · {mis.get('m')} · {mis.get('H_L')}"),
                   ("PCC", str(mis.get("pcc_modo"))), ("Sinal de valor futuro (contagens)", _dict(mis.get("sinal_valor_futuro"))),
                   ("Solver (na execução)", _dict(mis.get("solver")))]))
    out.append(_p("Advertências do preflight (versão executada)", "h2"))
    pre = d.json_data(RG.N_PREFLIGHT) or {}
    its = [i for i in (pre.get("items") or []) if i.get("level") in (PF.WARNING, PF.INFO, PF.ERROR)]
    out += bullets([f"[{_e(PF.LEVEL_LABELS.get(i['level'], i['level']))}] <b>{_e(PF.AREA_LABELS.get(i.get('area'), i.get('area')))}:</b> "
                    f"{_e(i.get('message'))}" for i in its]) or [_p("Nenhuma advertência registrada.", "peq")]
    out.append(_p("Discussão factual — apenas o que foi gravado", "h2"))
    out += bullets([
        _e(f"A missão aplicou {mis.get('intervalos_aplicados')} de {mis.get('intervalos_missao')} intervalos em {mis.get('janelas')} janela(s) "
           f"do MPC; situação registrada: {mis.get('situacao_missao')}."),
        _e(f"Custo realizado selado: {RP.num(mis.get('custo_realizado_total_R'), 2, 'R$')}; o custo futuro estimado pelo planejador não "
           f"está incluído (custo_realizado_inclui_valor_futuro = {mis.get('custo_realizado_inclui_valor_futuro')})."),
        _e(f"Energia demandada {RP.num(mis.get('energia_demanda_kWh'), 2, 'kWh')}, atendida {RP.num(mis.get('energia_atendida_kWh'), 2, 'kWh')}, "
           f"não atendida {RP.num(mis.get('energia_nao_atendida_kWh'), 2, 'kWh')}."),
        "Este documento descreve valores registrados; não atribui causas às decisões do controlador."])
    out.append(_p("Procedência do documento", "h2"))
    out.append(kv([("Microrrede", f"{d.microgrid.get('name')} · {d.run.microgrid_uid}"),
                   ("Cenário", f"{d.scenario_name} · v{d.run.scenario_version} · {d.run.scenario_fingerprint}"),
                   ("Origem dos dados", D.ORIGIN_LABELS[d.kind]), ("Marco Trama (SHA-256)", f["hash"])]))
    out.append(_p("Limitações científicas e convenções (fecham o relatório)", "h2"))
    out += bullets([_e(x) for x in (f.get("limitacoes") or [])])
    out.append(kv([(k, x) for k, x in (f.get("convencoes") or {}).items()], (0.18, 0.82)))
    out += bullets([_e(PF.ESCOPO), "Figuras, cartões e indicadores são DERIVADOS dos dados gravados; a fonte portátil integral é o "
                    "pacote .seeds2study.zip (Arquivo Científico)."])
    out.append(caixa(D.DERIVED_NOTE + " Os gráficos foram desenhados pelo instrumento Partitura a partir dos MESMOS dados gravados "
                     "(missão completa, tema claro) e conferidos pelo servidor pelo hash do marco; nenhum número foi recalculado."))
    return out


def _dict(x) -> str:
    return "; ".join(f"{k} = {v}" for k, v in x.items()) if isinstance(x, dict) else ("—" if x in (None, "") else str(x))


def _loc(f: dict, k) -> str:
    loc = (f.get("fronteiras") or {}).get("local") or []
    try:
        return str(loc[int(round(float(k)))])[:16].replace("T", " ")
    except (TypeError, ValueError, IndexError):
        return "N/D"


def _int(x) -> str:
    try:
        return str(int(round(float(x))))
    except (TypeError, ValueError):
        return "N/D"


def _n(x, dd: int = 2) -> str:
    from seeds2.report.run_pdf import num

    return num(x, dd) if x is not None else "N/D"


def _sci(x) -> str:
    try:
        return f"{float(x):.1e}".replace("-0.0e+00", "0.0e+00")
    except (TypeError, ValueError):
        return "N/D"


# ====================================================================================================== documento
class _Canvas:
    """Fábrica do canvas com «Página X de Y» (total conhecido só no fim de cada passada)."""

    @staticmethod
    def criar(meta: dict):
        from reportlab.pdfgen import canvas as rl

        class C(rl.Canvas):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self._salvas = []

            def showPage(self):
                self._salvas.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._salvas)
                for s in self._salvas:
                    self.__dict__.update(s)
                    if self._pageNumber > 1:
                        self.setFont("DV", 6.8)
                        self.setFillColor(INK3)
                        self.drawRightString(PAGE_W - MX, 7 * mm, f"Página {self._pageNumber} de {total}")
                    super().showPage()
                super().save()
        return C


class _Doc(BaseDocTemplate):
    def afterFlowable(self, fl):
        if isinstance(fl, Secao):
            chave = f"s{fl.n}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(f"{fl.n:02d} · {fl.titulo}", chave, level=0)
            self.notify("TOCEntry", (0, f"{fl.n:02d} · {_e(fl.titulo)}", self.page, chave))
        elif isinstance(fl, Subtitulo):
            chave = f"u{id(fl)}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(_corta(fl.titulo, 90), chave, level=1)
            self.notify("TOCEntry", (1, _e(_corta(fl.titulo, 110)), self.page, chave))


def _capa(meta: dict, f: dict):
    r = f["rodada"]
    dem = (f.get("intervalos") or {}).get("demanda_realizada_kW") or []
    tar = (f.get("intervalos") or {}).get("tarifa_importacao_decisao_R_kWh") or []

    def desenhar(c, doc):
        c.saveState()
        c.setFillColor(ESC)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        # «partitura»: cinco linhas de pauta e a demanda GRAVADA da missão (degrau por intervalo) em violeta
        x0, x1, y0, y1 = MX + 4, PAGE_W - MX - 4, 46 * mm, 92 * mm
        c.setStrokeColor(colors.HexColor("#2a2a2a"))
        c.setLineWidth(0.6)
        for k in range(5):
            y = y0 + k * (y1 - y0) / 4
            c.line(x0, y, x1, y)
        vals = [v for v in dem if isinstance(v, (int, float))]
        if vals and len(vals) == len(dem):
            lo, hi, n = 0.0, max(vals) or 1.0, len(dem)
            p = c.beginPath()
            for i, v in enumerate(dem):
                xa, xb, yv = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n, y0 + (y1 - y0) * (v - lo) / (hi - lo)
                p.moveTo(xa, yv) if i == 0 else p.lineTo(xa, yv)
                p.lineTo(xb, yv)
            c.setStrokeColor(VIO)
            c.setLineWidth(2.2)
            c.drawPath(p, stroke=1, fill=0)
            tv = [v for v in tar if isinstance(v, (int, float))]
            if tv and len(tv) == len(tar) and max(tv) > 0:
                p = c.beginPath()
                for i, v in enumerate(tar):
                    xa, xb, yv = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n, y0 - 9 * mm + 7 * mm * v / max(tv)
                    p.moveTo(xa, yv) if i == 0 else p.lineTo(xa, yv)
                    p.lineTo(xb, yv)
                c.setStrokeColor(colors.HexColor("#e05a5a"))
                c.setStrokeAlpha(0.7)
                c.setLineWidth(1.2)
                c.drawPath(p, stroke=1, fill=0)
                c.setStrokeAlpha(1)
            c.setFont("DV", 6.6)
            c.setFillColor(colors.HexColor("#777e85"))
            c.drawString(x0, y1 + 4, "demanda realizada da missão [kW] · degrau por intervalo (dados gravados)")
            if tv:
                c.drawString(x0, y0 - 12 * mm, "tarifa de importação da decisão [R$/kWh]")
        c.setFillColor(VIO)
        c.rect(0, PAGE_H - 5, PAGE_W, 5, stroke=0, fill=1)
        c.setFont("DV-B", 46)
        c.setFillColor(colors.HexColor("#f3f3f1"))
        c.drawString(MX + 4, PAGE_H - 40 * mm, "SEEDS2")
        c.setFont("DV-B", 9)
        c.setFillColor(colors.HexColor("#b3a8ff"))
        c.drawString(MX + 6, PAGE_H - 47 * mm, "RELATÓRIO CIENTÍFICO DA RODADA · EMS V2 HIERÁRQUICO MILP–MPC")
        c.setFont("DV-B", 19)
        c.setFillColor(colors.HexColor("#f3f3f1"))
        c.drawString(MX + 6, PAGE_H - 62 * mm, _corta(meta["microrrede"], 70))
        c.setFont("DV", 11)
        c.setFillColor(colors.HexColor("#c9cdd1"))
        c.drawString(MX + 6, PAGE_H - 70 * mm, _corta(f"Cenário «{r.get('cenario')}» · versão {r.get('versao_cenario')}", 110))
        linhas = [("Missão", meta["horizonte"]), ("Rodada", f"{r['uid']} · contrato de dados v{r.get('versao_dados')} · inventário rev. {r.get('revisao_inventario')}"),
                  ("Execução", meta["execucao"]), ("Auditoria", meta["auditoria"]), ("Evidência", meta["evidencia"]),
                  ("Gerado em", f"{meta['gerado']} · {meta['app']}")]
        y = PAGE_H - 84 * mm
        for a, b in linhas:
            c.setFont("DV-B", 7.4)
            c.setFillColor(colors.HexColor("#8b7cff"))
            c.drawString(MX + 6, y, a.upper())
            c.setFont("DV", 8.6)
            c.setFillColor(colors.HexColor("#e6e6e4"))
            c.drawString(MX + 62, y, _corta(b, 150))
            y -= 5.2 * mm
        if r.get("sintetico"):
            c.setFillColor(colors.HexColor("#3a2a00"))
            c.roundRect(PAGE_W - MX - 70 * mm, PAGE_H - 40 * mm, 70 * mm, 9 * mm, 4, stroke=0, fill=1)
            c.setFont("DV-B", 7.6)
            c.setFillColor(colors.HexColor("#e3a53d"))
            c.drawCentredString(PAGE_W - MX - 35 * mm, PAGE_H - 37 * mm, "DADOS SINTÉTICOS DE ENSAIO")
        import textwrap

        c.setFont("DV", 6.6)
        c.setFillColor(colors.HexColor("#777e85"))
        y = 17 * mm
        for ln in ["Ensaio — simulação OFFLINE algébrica de laço fechado (EMS hierárquico MILP–MPC): não é controle de equipamentos, "
                   "telemetria nem validação física."] + textwrap.wrap(D.DERIVED_NOTE, 200):
            c.drawString(MX + 4, y, ln)
            y -= 3.6 * mm
        c.restoreState()
    return desenhar


def _pagina(meta: dict):
    def desenhar(c, doc):
        c.saveState()
        c.setFont("DV-B", 7.4)
        c.setFillColor(VIO_E)
        c.drawString(MX, PAGE_H - 10 * mm, "SEEDS2")
        c.setFont("DV", 7)
        c.setFillColor(INK3)
        c.drawString(MX + _sw("SEEDS2", 7.4) * 1.12 + 4, PAGE_H - 10 * mm, "· RELATÓRIO CIENTÍFICO DA RODADA · EMS V2")
        c.drawRightString(PAGE_W - MX, PAGE_H - 10 * mm, _corta(meta["direita"], 110))
        c.setStrokeColor(VIO_C)
        c.setLineWidth(0.8)
        c.line(MX, PAGE_H - 12 * mm, PAGE_W - MX, PAGE_H - 12 * mm)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(MX, 10.5 * mm, PAGE_W - MX, 10.5 * mm)
        c.setFont("DV", 6.6)
        c.setFillColor(INK3)
        c.drawString(MX, 7 * mm, _corta(f"Rodada {meta['rodada']} · gerado em {meta['gerado']} · {meta['app']} · documento DERIVADO dos dados "
                                        "gravados (não executa modelos nem o EMS)", 190))
        c.restoreState()
    return desenhar


def _como_ler() -> list:
    return [_p("Como ler este relatório", "h2"),
            tabela(["Marca", "Significado"], [
                ["SELADO", "Valor do resumo gravado e selado da missão (sem recálculo)."],
                ["DERIVADO", "Calculado a partir de valores gravados (somas, razões, energias = média de intervalo × Δ). Rotulado onde aparece."],
                ["DECLARADO", "Parâmetro declarado no cenário/estratégia (hipótese experimental, não resultado)."],
                ["SERVIDOR", "Verificação refeita pelo servidor ao gerar o documento (hashes, vistas, reauditoria; sem solver)."],
                ["N/D", "Dado AUSENTE na rodada: nunca desenhado nem somado como zero; torna N/D tudo o que dele depende."],
                ["—", "Não aplicável (recurso inexistente nesta microrrede ou termo não declarado no objetivo)."]], [0.7, 6]),
            Spacer(1, 4),
            _p("Convenções: potências em kW líquidos no barramento equivalente; valores de intervalo são MÉDIAS de [t_k, t_k+1) e "
               "estados de fronteira (energia/SOC) são pontos em t_k. Descarga, importação e geração injetam; carga da bateria, "
               "exportação e demanda consomem — nunca somadas como geração. Todos os gráficos mostram a missão COMPLETA, "
               "independentemente do zoom usado na tela. Custo realizado nunca inclui o custo futuro estimado (instrumento de "
               "decisão do planejador).", "peq")]


def pdf(source, run_uid: str, pacote, *, nomes: dict | None = None, progress=None) -> tuple[str, bytes, dict]:
    """Relatório PDF visual da rodada V2 concluída ``run_uid`` a partir do ``pacote`` desenhado pela Partitura.

    Devolve (nome do arquivo, bytes, informações {páginas, figuras, seções}). Recusa (exceção apresentável) se a rodada não
    estiver concluída, se a evidência não passar na verificação ou se o pacote não for desta rodada/destes dados."""
    from seeds2 import APP_NAME, APP_VERSION

    say = progress or (lambda _m: None)
    say("Lendo os dados gravados da rodada e verificando a evidência V2 (sem solver)")
    d, v = DOC.carregar(source, run_uid)
    if not d.concluded:
        raise PacoteInvalido("O relatório visual existe só para rodadas CONCLUÍDAS; para esta rodada gere o diagnóstico PDF.")
    f = TF.montar(source, d.run, verificacao=v, nomes=nomes)
    pac = ler_pacote(pacote)
    info = validar(pac, run_uid=d.run_uid, frame_hash=f["hash"])
    ST.update(_estilos())
    try:
        CTX["escala"] = TW / max(300.0, float(pac.get("largura") or 1040))
    except (TypeError, ValueError):
        CTX["escala"] = TW / 1040
    gerado = D.utc_now()
    r = f["rodada"]
    loc = f["fronteiras"].get("local") or []
    ac, au = f.get("aceitacao") or {}, f.get("auditoria") or {}
    estados = {"aprovada": "aprovada", "coerente": "coerente", "nao_aplicavel": "não aplicável", "nao_validada": "não validada", "incoerente": "INCOERENTE"}
    meta = {"microrrede": d.microgrid.get("name") or "Microrrede", "rodada": d.run_uid, "gerado": gerado, "app": f"{APP_NAME} {APP_VERSION}",
            "horizonte": (f"{loc[0][:16].replace('T', ' ')} → {loc[-1][:16].replace('T', ' ')} ({r.get('fuso') or 'fuso não declarado'}) · "
                          f"{r.get('K')} intervalos de {r.get('delta_min'):g} min · N {r.get('N')} · m {r.get('m')} · H_L {r.get('H_L')}") if loc else "N/D",
            "execucao": f"{r.get('estado')} · missão {'completa' if f['resumo'].get('missao_completa') else 'INCOMPLETA'} · {r.get('criada')} → {r.get('finalizada')}",
            "auditoria": ("aceita" if au.get("aceito") else "REJEITADA" if au.get("aceito") is False else "N/D") + " · aceitação algébrica "
                         f"{estados.get((ac.get('algebrica') or {}).get('estado'), 'N/D')} · dinâmica {estados.get((ac.get('dinamica') or {}).get('estado'), 'N/D')} · "
                         f"física {estados.get((ac.get('fisica') or {}).get('estado'), 'N/D')}",
            "evidencia": (f"verificada pelo servidor ({sum(1 for x, _ in v.itens if x)} de {len(v.itens)}) · sem solver" if v.ok else "COM PROBLEMAS"),
            "direita": f"{d.microgrid.get('name')} · {d.scenario_name} v{d.run.scenario_version}"}
    say("Diagramando capa, sumário e seções")
    toc = TableOfContents()
    toc.levelStyles = [ST["toc0"], ST["toc1"]]
    toc.dotsMinLevel = 0
    story: list = [NextPageTemplate("pagina"), PageBreak(), _p("Sumário", "sub"), Spacer(1, 6), toc, Spacer(1, 10)] + _como_ler()
    por_id = {s["id"]: s for s in pac["secoes"]}
    n = 0
    for sid in ("operacao", "fontes", "visao", "decisao", "economia", "evidencia"):
        s = por_id.get(sid)
        if sid == "fontes":
            if not s:
                continue
            for sub in s.get("subsecoes") or []:
                story += [PageBreak(), Subtitulo(_txt(sub.get("titulo"), 200), _txt(sub.get("rotulo"), 300))]
                story += _blocos(sub.get("blocos"))
            continue
        n += 1
        blocos = [b for b in (s or {}).get("blocos") or [] if isinstance(b, dict)]
        chips = None
        if sid == "operacao" and blocos and blocos[0].get("tipo") == "kpis":      # indicadores na faixa, gráfico na mesma página
            chips, blocos = blocos[0].get("itens"), blocos[1:]
            if blocos and blocos[0].get("tipo") == "figura":
                blocos[0] = {**blocos[0], "_reserva": 64 + 8 + 6}
        story += [PageBreak(), Secao(n, TITULOS[sid], _txt((s or {}).get("sub"), 200), chips=chips), Spacer(1, 8)]
        if sid == "evidencia":
            grupos = next((b.get("grupos") for b in (s or {}).get("blocos") or [] if isinstance(b, dict) and b.get("tipo") == "avisos"), None)
            story += _evidencia(f, d, v, grupos)
            continue
        story += _blocos(blocos)
    story = _par_lado_a_lado(story)
    buf = io.BytesIO()
    doc = _Doc(buf, pagesize=(PAGE_W, PAGE_H), leftMargin=MX, rightMargin=MX, topMargin=MT, bottomMargin=MB,
               title=f"SEEDS2 — Relatório da rodada · {d.scenario_name} v{d.run.scenario_version}", author=f"{APP_NAME} {APP_VERSION}",
               subject=f"Rodada {d.run_uid} · {d.microgrid.get('name')}", creator=f"{APP_NAME} {APP_VERSION} · Partitura")
    quadro = Frame(MX, MB, TW, TH, id="q", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("capa", [quadro], onPage=_capa(meta, f)), PageTemplate("pagina", [quadro], onPage=_pagina(meta))])
    say(f"Desenhando {info['figuras']} gráficos vetoriais e montando o sumário")
    doc.multiBuild(story, canvasmaker=_Canvas.criar(meta), maxPasses=4)
    dados = buf.getvalue()
    from pypdf import PdfReader

    info["paginas"] = len(PdfReader(io.BytesIO(dados)).pages)
    return D.safe_stem(d, "relatorio") + ".pdf", dados, info


__all__ = ["FORMATO", "MAX_PACOTE", "PacoteInvalido", "VERSAO", "ler_pacote", "pdf", "validar"]
