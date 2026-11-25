"""Gera o HTML do guia da defesa (capa + corpo); o PDF é impresso por render_pdf.js."""
import html
import os

from conteudo import AUX, BLOCOS, DEMO, DEMO_CUIDADOS, PERGUNTA, SLIDES

D = os.path.dirname(os.path.abspath(__file__))
E = html.escape

STOPS = [(0, (0x6D, 0xB5, 0x27)), (.55, (0x1E, 0x8A, 0x72)), (1, (0x00, 0x72, 0xBA))]


def cor(t):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            return "#%02x%02x%02x" % tuple(round(x + (y - x) * u) for x, y in zip(ca, cb))
    return "#0072BA"


# cor de cada bloco = cor do(s) cartão(ões) correspondente(s) no sumário
COR = {"0": "#14213D", "I": cor(.12), "II": cor(.31), "III": cor(.5), "IV": cor(.63), "V": cor(.75), "VI": cor(.88)}

CSS = """
@import url("../capa/assets/fonts.css");
:root{--navy:#14213D;--slate:#4A5568;--teal:#1F7A6D;--light:#EEF3F2;--line:#DCE3E2;--lime:#C1FF72;--rust:#C0532F}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:"Manrope",sans-serif;color:var(--navy);font-size:10pt;line-height:1.45}
.serif{font-family:"Gelasio",Georgia,serif}
h1,h2,h3{font-family:"Gelasio",Georgia,serif;font-weight:700}
.pb{break-before:page}
/* ---------- capa ---------- */
.capa{position:relative;width:210mm;height:297mm;overflow:hidden;padding:22mm 20mm}
.capa .un{height:26mm}
.capa .k{margin-top:46mm;font:italic 400 15pt "Gelasio",serif;color:var(--teal)}
.capa h1{font-size:44pt;line-height:1.05;margin-top:4mm}
.capa .tt{margin-top:9mm;font:700 15pt/1.3 "Gelasio",serif;color:#2B3648;max-width:165mm}
.capa .meta{margin-top:10mm;font:500 10.5pt "Manrope";color:var(--slate);line-height:1.7}
.capa .meta b{color:var(--navy)}
.capa .bus{position:absolute;left:20mm;right:20mm;bottom:52mm;height:9mm;display:flex;gap:1.6mm}
.capa .seg{flex:1;clip-path:polygon(0 0,calc(100% - 4mm) 0,100% 50%,calc(100% - 4mm) 100%,0 100%,4mm 50%)}
.capa .seg:first-child{clip-path:polygon(0 0,calc(100% - 4mm) 0,100% 50%,calc(100% - 4mm) 100%,0 100%)}
.capa .lg{position:absolute;right:20mm;bottom:20mm;height:19mm}
.capa .dt{position:absolute;left:20mm;bottom:23mm;font:500 10pt "Manrope";color:var(--slate)}
/* ---------- textos gerais ---------- */
.sec{font-size:24pt;line-height:1.1;margin-bottom:5mm}
.lead{font-size:10.5pt;color:#2B3648;max-width:170mm}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:5mm}
.box{background:var(--light);border-radius:4mm;padding:5mm 6mm}
.box h4{font:700 12pt "Gelasio",serif;margin-bottom:2mm}
.dark{background:var(--navy);color:#fff}
.dark .lbl{font:italic 400 11pt "Gelasio",serif;color:var(--lime)}
.dark .q{font:400 15pt/1.35 "Gelasio",serif;margin-top:2.5mm}
.dark .nt{font-size:8.5pt;color:#B8C4D6;margin-top:3mm}
.pil{display:flex;gap:4mm;margin-top:3mm}
.pil div{flex:1;display:flex;gap:3mm;align-items:center}
.pil b{flex:none;width:9mm;height:9mm;border-radius:50%;border:1.5px solid var(--teal);color:var(--teal);display:flex;align-items:center;justify-content:center;font:700 11pt "Gelasio"}
/* barra de tempo */
.tbar{display:flex;gap:1.2mm;margin-top:4mm;height:16mm}
.tbar div{min-width:17mm;position:relative;color:#fff;font-size:7.5pt;line-height:1.15;padding:2mm 0 0 5mm;clip-path:polygon(0 0,calc(100% - 3mm) 0,100% 50%,calc(100% - 3mm) 100%,0 100%,3mm 50%)}
.tbar div:first-child{clip-path:polygon(0 0,calc(100% - 3mm) 0,100% 50%,calc(100% - 3mm) 100%,0 100%);padding-left:2.5mm}
.tbar b{display:block;font:700 10pt "Gelasio"}
.tbar .mg{background:#C9D3DD;color:var(--navy)}
.tleg{display:flex;justify-content:space-between;font-size:8pt;color:var(--slate);margin-top:1.5mm}
/* ---------- cabeçalho de bloco ---------- */
.bloco{display:flex;gap:6mm;align-items:center;border-radius:5mm;padding:6mm 7mm;margin:0 0 5mm;color:#fff;break-inside:avoid;break-after:avoid}
.bloco .r{font:700 34pt/1 "Gelasio",serif;min-width:20mm}
.bloco h2{font-size:18pt;line-height:1.15}
.bloco .f{font-size:9.5pt;opacity:.92;margin-top:1.5mm;max-width:140mm}
.bloco .d{margin-left:auto;font:700 13pt "Gelasio";white-space:nowrap;background:rgba(255,255,255,.16);border-radius:10mm;padding:1.5mm 4mm}
/* ---------- cartão de slide ---------- */
.card{display:grid;grid-template-columns:24mm 1fr;gap:5mm;border:1px solid var(--line);border-radius:5mm;padding:6mm 6mm 5.5mm;margin-bottom:5mm;break-inside:avoid;background:#fff}
.card .esq .nn{font:700 30pt/1 "Gelasio",serif}
.card .esq .tm{font:600 8.5pt "Manrope";color:var(--slate);margin-top:2mm}
.st{display:inline-block;margin-top:2.5mm;font:600 7.5pt "Manrope";border-radius:10mm;padding:.8mm 2.6mm}
.st.ok{background:#E3F4D9;color:#3E7A12}.st.td{background:var(--light);color:var(--slate)}
.ab{display:flex;gap:1.5mm;margin-top:2.5mm}
.ab span{width:6.5mm;height:6.5mm;border-radius:50%;border:1.3px solid var(--teal);color:var(--teal);font:700 8pt "Gelasio";display:flex;align-items:center;justify-content:center}
.card h3{font-size:15pt;line-height:1.2}
.msg{margin-top:2.5mm;font:italic 400 12pt/1.35 "Gelasio",serif;color:var(--teal)}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:6mm;margin-top:4mm}
.lab{font:700 7.5pt "Manrope";letter-spacing:.06em;color:#7B8794;text-transform:uppercase;margin-bottom:1.5mm}
ul{padding-left:4mm}li{margin-bottom:1mm;font-size:9pt;color:#2B3648}
li::marker{color:#9AA5B1}
.pq{font-size:9pt;color:#2B3648}
.vc{display:flex;flex-wrap:wrap;gap:1.5mm;margin-top:3.5mm}
.vc span{font:600 7.5pt "Manrope";background:var(--light);color:var(--slate);border-radius:10mm;padding:.8mm 2.4mm}
.fala{margin-top:4mm;padding-top:3mm;border-top:1px dashed var(--line);font:italic 400 9.5pt/1.45 "Gelasio",serif;color:#3A4558}
.fala::before{content:"Fala-guia  ";font:700 7.5pt "Manrope";font-style:normal;letter-spacing:.06em;text-transform:uppercase;color:#7B8794}
.thumb{width:118mm;border-radius:2.5mm;border:1px solid var(--line);margin-top:3mm;display:block}
/* demonstração */
table{width:100%;border-collapse:collapse;font-size:9pt}
td,th{text-align:left;vertical-align:top;padding:2.2mm 2.5mm;border-bottom:1px solid var(--line)}
th{font:700 7.5pt "Manrope";letter-spacing:.06em;text-transform:uppercase;color:#7B8794}
td.t{white-space:nowrap;font-weight:700;color:var(--navy)}
td.f{font-family:"Gelasio",serif;font-style:italic;color:#3A4558}
.demo{border:1px solid var(--line);border-radius:5mm;padding:6mm;margin-bottom:5mm;break-inside:avoid}
.demo h3{font-size:14pt;margin-bottom:1mm}
"""


def capa():
    segs = "".join(f'<div class="seg" style="background:{cor(k/6)}"></div>' for k in range(7))
    return f"""<div class="capa">
<img class="un" src="../capa/assets/unila.png">
<div class="k">Defesa de TCC · Engenharia de Energia · ILATIT</div>
<h1>Guia da apresentação</h1>
<div class="tt">SEEDS: Desenvolvimento e Avaliação de um Simulador Modular Expansível com Gerenciamento Energético Hierárquico Baseado em MILP–MPC</div>
<div class="meta"><b>Bruno Manuel Olmedo Chávez</b><br>Orientador: Prof. Dr. Jorge Javier Gimenez Ledesma<br>Coorientador: Me. Daniel Firmo Kazay</div>
<div class="bus">{segs}</div>
<div class="dt">Foz do Iguaçu, 9 de dezembro de 2026</div>
<img class="lg" src="../capa/assets/seeds.png"></div>"""


def intro():
    dur = [(b[1] if b[0] != "0" else "Abertura", b[2], COR[b[0]], b[0]) for b in BLOCOS] + [("Margem", "0:35", None, "")]
    def mins(s):
        m, sec = s.split(":"); return int(m) + int(sec) / 60
    tb = "".join(
        f'<div class="{"mg" if c is None else ""}" style="flex:{mins(t):.3f};{"" if c is None else f"background:{c}"}"><b>{t}</b>{E(r if r else n)}</div>'
        for n, t, c, r in dur)
    return f"""<div>
<h2 class="sec">Como usar este guia</h2>
<p class="lead">Cada slide tem um cartão com o <b>título</b>, a <b>mensagem</b> que ele precisa deixar na banca, o que vai <b>na tela</b>,
o <b>motivo de existir</b>, os <b>vínculos</b> com outros slides e uma <b>fala-guia</b> — uma ideia para treinar, não um texto para decorar.
Os números de tempo somam 29 min 25 s, deixando 35 s de margem.</p>
<div class="box dark" style="margin-top:6mm">
<div class="lbl">Pergunta que guia a apresentação</div>
<div class="q">{E(PERGUNTA)}</div>
<div class="nt">Redação próxima ao objetivo do artigo; validar com o orientador. Aparece no slide 6 e é respondida no slide 26.</div>
<div class="pil"><div><b>A</b><span>Plataforma modular — a parte «diferentes configurações»</span></div>
<div><b>B</b><span>EMS hierárquico MILP–MPC — a parte «valor futuro»</span></div></div></div>
<div class="grid2" style="margin-top:5mm">
<div class="box"><h4>O fio condutor</h4>A metáfora do <b>custo futuro da água no SIN</b> (NEWAVE → DECOMP → DESSEM): a água turbinada hoje pode obrigar a acionar uma térmica amanhã;
a energia descarregada agora pode faltar na ponta. Aparece no slide 4, volta nos slides 11 e 22 e fecha no 26.</div>
<div class="box"><h4>As regras dos slides</h4>Uma ideia por slide · títulos curtos · números grandes e poucos · cores do aplicativo nos recursos ·
rodapé com UNILA, curso, Defesa de TCC e autor · número de página grande.</div></div>
<h2 class="sec" style="margin-top:9mm;font-size:17pt">Distribuição do tempo</h2>
<div class="tbar">{tb}</div>
<div class="tleg"><span>0 min</span><span>30 min</span></div>
</div>"""


def bloco_hdr(b):
    bid, nome, dur, fun = b
    c = COR[bid]
    r = "—" if bid == "0" else bid
    return f"""<div class="bloco" style="background:{c}"><div class="r">{r}</div>
<div><h2>{E(nome)}</h2><div class="f">{E(fun)}</div></div><div class="d">{dur}</div></div>"""


def cartao(s):
    c = COR[s["b"]]
    ok = s["status"] == "Pronto"
    ab = "".join(f"<span>{x}</span>" for x in s["contrib"].split())
    tela = "".join(f"<li>{E(x)}</li>" for x in s["tela"])
    vc = "".join(f"<span>{E(x)}</span>" for x in s["vinc"])
    img = f'<img class="thumb" src="{s["img"]}">' if s.get("img") else ""
    return f"""<div class="card"><div class="esq"><div class="nn" style="color:{c}">{s["n"]:02d}</div>
<div class="tm">{s["tempo"]} min</div><span class="st {"ok" if ok else "td"}">{"Pronto" if ok else "A desenhar"}</span>
{f'<div class="ab">{ab}</div>' if ab else ""}</div>
<div><h3>{E(s["t"])}</h3><div class="msg">{E(s["msg"])}</div>{img}
<div class="cols"><div><div class="lab">Na tela</div><ul>{tela}</ul></div>
<div><div class="lab">Por que existe</div><div class="pq">{E(s["porque"])}</div><div class="vc">{vc}</div></div></div>
<div class="fala">{E(s["fala"])}</div></div></div>"""


def demo():
    lin = "".join(f'<tr><td class="t">{t}</td><td>{E(a)}</td><td class="f">{E(f)}</td></tr>' for t, a, f in DEMO)
    cui = "".join(f"<li>{E(x)}</li>" for x in DEMO_CUIDADOS)
    return f"""<div class="demo"><h3>No aplicativo — reproduzir o C6 ao vivo (≈ 5:45)</h3>
<table><tr><th>Tempo</th><th>Ação</th><th>O que dizer</th></tr>{lin}</table>
<div class="lab" style="margin-top:4mm">Cuidados</div><ul>{cui}</ul></div>"""


def aux():
    lin = "".join(f'<tr><td class="t">{a}</td><td><b>{E(t)}</b></td><td>{E(c)}</td></tr>' for a, t, c in AUX)
    return f"""<div class="pb"><h2 class="sec">Slides auxiliares (arguição)</h2>
<p class="lead" style="margin-bottom:4mm">Ficam depois do slide 27 e só aparecem se a banca perguntar. Lista provisória, a reorganizar.</p>
<table><tr><th>#</th><th>Título</th><th>Conteúdo</th></tr>{lin}</table></div>"""


def corpo():
    partes = [intro()]
    for b in BLOCOS:
        partes.append(f'<div class="pb">{bloco_hdr(b)}')
        for s in (x for x in SLIDES if x["b"] == b[0]):
            partes.append(cartao(s))
            if s["n"] == 19:
                partes.append(demo())
        partes.append("</div>")
    partes.append(aux())
    return "".join(partes)


HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'
open(os.path.join(D, "capa.html"), "w", encoding="utf-8").write(HEAD.format(css=CSS + "@page{size:A4;margin:0}", body=capa()))
open(os.path.join(D, "corpo.html"), "w", encoding="utf-8").write(HEAD.format(css=CSS + "@page{size:A4;margin:16mm 16mm 18mm}", body=corpo()))
print("ok")
