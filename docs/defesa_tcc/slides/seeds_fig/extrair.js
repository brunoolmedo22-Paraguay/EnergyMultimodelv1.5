// Desenha, na página de bancada gerada por extrair.py, uma figura com as raias escolhidas da Partitura (lanesOperacao) usando
// o próprio motor Trama, e devolve o SVG serializado por svgPdf (cores explícitas) + a geometria das raias.
// Uso: node extrair.js <pagina.html> <largura> <altura> '{"lanes": ["prefixo", ...], "labW": px, "major": n}'
const { chromium } = require("playwright");
(async () => {
  const [pag, W, H, pref] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 1200 } });
  const erros = []; p.on("pageerror", (e) => erros.push(e.message)); p.on("console", (m) => { if (m.type() === "error") erros.push(m.text()); });
  await p.goto("file://" + pag); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(600);
  const r = await p.evaluate(({ W, H, pref, o }) => {
    const P = document.querySelector(".pt.partitura").__pt, X = P.__x;
    const todas = X.lanesOperacao().filter(Boolean);
    const lanes = pref.map((q) => { const L = todas.find((l) => l.title.startsWith(q)); if (!L) throw new Error("raia não encontrada: " + q); return L; });
    const box = document.createElement("div"); box.className = "pt"; box.dataset.theme = "light";
    box.style.cssText = "display:block;height:auto;padding:0;background:transparent;width:" + W + "px";
    const host = document.createElement("div"); host.style.cssText = `width:${W}px;height:${H}px;position:relative`;
    box.append(host); document.body.append(box);
    const T = trama(host, { K: X.K, lab: X.lab, lanes, fill: true, pat: "pth", label: "Partitura da operação", labW: o.labW, major: o.major, view: o.view || null });
    const svg = T.svg || host.querySelector("svg.trama");
    const titulos = [...svg.querySelectorAll("text.t")].map((t) => ({ title: t.textContent, y: +t.getAttribute("y") }));
    const rot = [...svg.querySelectorAll("text")].filter((t) => !t.classList.contains("t")).map((t) => ({ t: t.textContent, x: +t.getAttribute("x"), y: +t.getAttribute("y") }));
    return { svg: X.svgPdf(svg), meta: { W: +svg.getAttribute("width"), H: +svg.getAttribute("height"), padL: 46, padR: 10, K: X.K, view: o.view || [0, X.K], lanes: titulos, rotulos: rot } };
  }, { W: +W, H: +H, pref: JSON.parse(pref).lanes, o: JSON.parse(pref) });
  console.log(JSON.stringify({ ...r, erros }));
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
