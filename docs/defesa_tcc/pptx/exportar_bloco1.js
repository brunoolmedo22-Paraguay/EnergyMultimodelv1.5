// Exporta o bloco I aprovado: PNG em alta resolução (3840 × 2160) dos slides 3–7 para o PPTX
// e o PDF vetorial dos slides 1–7 direto dos HTML aprovados (fontes reais, texto selecionável).
// Uso: NODE_PATH=$(npm root -g) node exportar_bloco1.js
const { chromium } = require("playwright");
const path = require("path"); const fs = require("fs"); const { execFileSync } = require("child_process");
const R = path.join(__dirname, "..");
const PAGS = [["capa/capa_oficial.html", 1], ["capa/sumario.html", 2], ["slides/slide03_aprovado.html", 3],
              ["slides/slide04_aprovado.html", 4], ["slides/slide05_aprovado.html", 5], ["slides/slide06_aprovado.html", 6],
              ["slides/slide07_aprovado.html", 7]];
(async () => {
  const HD = path.join(__dirname, "img_hd"); fs.mkdirSync(HD, { recursive: true });
  const TMP = fs.mkdtempSync(path.join(require("os").tmpdir(), "bloco1-"));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  const pdfs = [];
  for (const [f, n] of PAGS) {
    await p.goto("file://" + path.join(R, f)); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
    if (n >= 3) await p.screenshot({ path: path.join(HD, `slide${String(n).padStart(2, "0")}.png`) });
    const out = path.join(TMP, `${n}.pdf`);
    await p.pdf({ path: out, width: "1920px", height: "1080px", printBackground: true, pageRanges: "1" });
    pdfs.push(out); console.log("ok", f);
  }
  await b.close();
  execFileSync("pdfunite", [...pdfs, path.join(__dirname, "SEEDS_Defesa_TCC_Bloco_I.pdf")]);
  fs.rmSync(TMP, { recursive: true, force: true });
})();
