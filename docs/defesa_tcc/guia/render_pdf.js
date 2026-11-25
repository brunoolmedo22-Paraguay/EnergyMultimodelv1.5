// Imprime capa.html e corpo.html em PDF (Chromium/Playwright) e une em Guia_Defesa_SEEDS.pdf.
const { chromium } = require("playwright");
const path = require("path");
const { execFileSync } = require("child_process");
(async () => {
  const d = __dirname;
  const b = await chromium.launch();
  const p = await b.newPage();
  const rodape = `<div style="width:100%;padding:0 16mm;font:500 7.5pt sans-serif;color:#8A96A3;display:flex;justify-content:space-between">
    <span>SEEDS · Guia da apresentação · Defesa de TCC</span><span><span class="pageNumber"></span></span></div>`;
  await p.goto("file://" + path.join(d, "capa.html")); await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: path.join(d, "_capa.pdf"), preferCSSPageSize: true, printBackground: true });
  await p.goto("file://" + path.join(d, "corpo.html")); await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: path.join(d, "_corpo.pdf"), preferCSSPageSize: true, printBackground: true,
                displayHeaderFooter: true, headerTemplate: "<span></span>", footerTemplate: rodape });
  await b.close();
  execFileSync("pdfunite", [path.join(d, "_capa.pdf"), path.join(d, "_corpo.pdf"), path.join(d, "Guia_Defesa_SEEDS.pdf")]);
  console.log("ok");
})();
