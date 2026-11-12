// Bancada de navegador do componente Partitura (Piso 3D-B). Abre páginas geradas por bancada_piso3db.py e percorre
// as quatro lentes e todos os painéis do explorador (recurso × vista × UID), devolvendo em JSON, por página, os erros
// de execução e o texto de cada vista. Uso: node bancada_piso3db.js <plano.json>
//   plano = { paginas: { nome: caminho.html }, passos: null | [[acao, ...args]], largura, altura, capturas: pasta|null }
//   ações: ["lente", id] ["clicar", seletor] ["escolher", seletor, valor] ["tecla", k] ["mover", x, y] ["texto", chave]
//          ["avaliar", chave, expressão] ["recarregar"] ["captura", nome] ["clicarEm", seletor, [fx, fy]] ["percorrer"]
const { chromium } = require("playwright");
const fs = require("fs");
const plano = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const texto = (p) => p.evaluate(() => (document.querySelector(".pt") || document.body).textContent.replace(/\s+/g, " "));

async function percorrer(p, vistas) {
  for (const l of ["operacao", "decisao", "economia", "evidencia"]) { await p.click(`[data-lente="${l}"]`); await p.waitForTimeout(250); vistas["lente:" + l] = await texto(p); }
  await p.click('[data-lente="operacao"]'); await p.waitForTimeout(150);
  await p.click(".status .pill"); await p.waitForTimeout(250);
  const n = await p.locator('.dtools [role="tab"]').count();
  for (let r = 0; r < n; r++) {
    await p.locator('.dtools [role="tab"]').nth(r).click(); await p.waitForTimeout(220);
    const nome = (await p.locator('.dtools [role="tab"]').nth(r).textContent()).trim();
    const nUid = await p.locator(".dhead select.sel option").count(), uids = nUid ? await p.locator(".dhead select.sel option").evaluateAll((o) => o.map((e) => e.value)) : [null];
    for (const u of uids) {
      if (u) { await p.selectOption(".dhead select.sel", u); await p.waitForTimeout(200); }
      const nv = await p.locator('.dtools [role="group"][aria-label="Vista"] button').count();
      for (let v = 0; v < Math.max(nv, 1); v++) {
        if (nv) { await p.locator('.dtools [role="group"][aria-label="Vista"] button').nth(v).click(); await p.waitForTimeout(220); }
        vistas[`painel:${nome}${u ? ":" + u : ""}${nv ? ":" + v : ""}`] = await p.evaluate(() => document.querySelector(".pt .dlg").textContent.replace(/\s+/g, " "));
      }
    }
  }
  await p.keyboard.press("Escape"); await p.waitForTimeout(150);
}

(async () => {
  const b = await chromium.launch(), saida = {};
  for (const [nome, caminho] of Object.entries(plano.paginas)) {
    const p = await b.newPage({ viewport: { width: plano.largura || 1400, height: plano.altura || 900 }, deviceScaleFactor: 1 }), erros = [], vistas = {};
    p.on("pageerror", (e) => erros.push(String(e.message) + " @ " + String(e.stack || "").split("\n").slice(1, 3).join(" | ")));
    p.on("console", (m) => { if (m.type() === "error") erros.push("console: " + m.text()); });
    await p.goto("file://" + caminho); await p.waitForTimeout(350);
    try {
      if (!plano.passos) await percorrer(p, vistas);
      else for (const [a, x, y] of plano.passos) {
        if (a === "lente") await p.click(`[data-lente="${x}"]`); else if (a === "clicar") await p.click(x); else if (a === "escolher") await p.selectOption(x, y);
        else if (a === "tecla") await p.keyboard.press(x); else if (a === "clicarEm") { const c = await p.locator(x).first().boundingBox(); await p.mouse.click(c.x + c.width * y[0], c.y + c.height * y[1]); } else if (a === "mover") await p.mouse.move(x, y); else if (a === "texto") vistas[x] = await texto(p);
        else if (a === "avaliar") vistas[x] = await p.evaluate(y); else if (a === "recarregar") await p.reload(); else if (a === "percorrer") await percorrer(p, vistas);
        else if (a === "captura" && plano.capturas) await p.screenshot({ path: `${plano.capturas}/${nome}_${x}.png` });
        await p.waitForTimeout(260);
      }
    } catch (e) { erros.push("percurso: " + e.message.split("\n")[0]); }
    saida[nome] = { erros, vistas }; await p.close();
  }
  await b.close(); console.log(JSON.stringify(saida));
})().catch((e) => { console.error(e); process.exit(1); });
