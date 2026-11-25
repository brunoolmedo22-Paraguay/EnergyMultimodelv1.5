// Exporta o deck inteiro a partir de deck.json (gerado por deck.py):
//  • img_hd/deckNN.png — imagem 3840 × 2160 de cada slide (usada no PPTX a partir do slide 3);
//  • SEEDS_Defesa_TCC.pdf — PDF vetorial completo (fontes reais, texto selecionável).
// O número de página de cada HTML é trocado pelo número do slide no deck.
// Uso: NODE_PATH=$(npm root -g) node exportar_deck.js
const { chromium } = require("playwright");
const path = require("path"); const fs = require("fs"); const { execFileSync } = require("child_process");
const R = path.join(__dirname, "..");
const deck = JSON.parse(fs.readFileSync(path.join(__dirname, "deck.json"), "utf8"));
(async () => {
  const HD = path.join(__dirname, "img_hd"); fs.rmSync(HD, { recursive: true, force: true }); fs.mkdirSync(HD);
  const TMP = fs.mkdtempSync(path.join(require("os").tmpdir(), "deck-"));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  const pdfs = [];
  for (const s of deck) {
    await p.goto("file://" + path.join(R, s.html)); await p.evaluate(() => document.fonts.ready);
    await p.evaluate((n) => { const e = document.querySelector(".pn"); if (e) e.textContent = String(n); }, s.n);
    await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(HD, `deck${String(s.n).padStart(2, "0")}.png`) });
    const out = path.join(TMP, `${String(s.n).padStart(2, "0")}.pdf`);
    await p.pdf({ path: out, width: "1920px", height: "1080px", printBackground: true, pageRanges: "1" });
    pdfs.push(out);
  }
  await b.close();
  execFileSync("pdfunite", [...pdfs, path.join(__dirname, "SEEDS_Defesa_TCC.pdf")]);
  fs.rmSync(TMP, { recursive: true, force: true });
  console.log("ok", deck.length, "slides");
})();
