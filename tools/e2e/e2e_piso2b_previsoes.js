// Verificação E2E em navegador real (Playwright/Chromium) do PISO 2B — Previsões e Dados.
//
// Preparação (diretórios VAZIOS; microrrede comissionada fictícia FV + eólica e CSVs sintéticos de teste):
//   python tools/e2e/seed_piso2b.py <SEEDS2_DATA_DIR> <dir_csv>
//   SEEDS2_DATA_DIR=<dir> python -m streamlit run app.py --server.headless true --server.port <porta>
// Uso:
//   node tools/e2e/e2e_piso2b_previsoes.js <url> <fase> <pasta_capturas> <dir_csv>
// Fases:
//   operar   — Gestor → ABRIR → criar cenário → ABRIR PREVISÕES; CSV malformado recusado; CSV de demanda (vírgula
//              decimal, fuso -03:00) → pré-visualização Plotly com os valores do arquivo, hover, zoom e restauração;
//              incorporar; clima compartilhado FV + eólica por CSV com mapeamento e unidades confirmadas, painéis
//              por grandeza, direção 350°→5° sem passar por 180° na grade transformada; salvar (v2); nova fonte
//              sintética mostra a NOVA curva pendente sem alterar o perfil salvo; Inicialização intacta
//   reinicio — executar DEPOIS de reiniciar o servidor: as mesmas curvas recuperadas exatamente
//   tablet   — Previsões em tablet (retrato/paisagem, sem rolagem horizontal, gráficos dentro da tela) e tema escuro
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir, csvDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

// valores esperados lidos dos próprios CSVs de teste (vírgula decimal → ponto)
const demandaCSV = fs.readFileSync(path.join(csvDir, "demanda_e2e.csv"), "utf8").trim().split("\n").slice(1)
  .map((l) => parseFloat(l.split(";")[1].replace(",", ".")));
const climaCSV = fs.readFileSync(path.join(csvDir, "clima_e2e.csv"), "utf8").trim().split("\n").slice(1).map((l) => l.split(","));

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(1000);
}
async function selectOption(scope, p, label, text) {
  const box = scope.locator('div[data-testid="stSelectbox"]').filter({ hasText: label }).first();
  await box.locator("input").click();
  await p.keyboard.type(text);
  await p.waitForTimeout(300);
  await p.keyboard.press("Enter");
  await ready(p);
}
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function overflow(p) { return p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }
async function abrir(p) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await p.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
}
async function previsoes(p) {
  await p.getByRole("button", { name: "ABRIR PREVISÕES" }).click(); await ready(p);
  await p.getByText("Previsões e Dados", { exact: false }).first().waitFor({ timeout: 60000 });
}
const panel = (p) => p.locator('[role="tabpanel"]:visible');
async function tab(p, name) { await p.getByRole("tab", { name }).click(); await ready(p); }
// Gráfico Plotly identificado pelo título (os dados vêm do próprio objeto do Plotly no DOM)
async function chart(p, titlePart) {
  return p.evaluate((t) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title &&
      String(el.layout.title.text || "").includes(t) && el.offsetParent !== null);
    if (!g) return null;
    const r = g.getBoundingClientRect();
    return { traces: g.data.map((d) => ({ name: d.name, y: d.y, x: d.x, yaxis: d.yaxis || "y" })),
             layout: { yaxes: Object.keys(g._fullLayout).filter((k) => /^yaxis\d*$/.test(k))
                         .map((k) => ({ k, title: g._fullLayout[k].title.text, overlaying: g._fullLayout[k].overlaying || false })),
                       xrange: g._fullLayout.xaxis.range.slice(), title: g.layout.title.text },
             box: { x: r.x, y: r.y, w: r.width, h: r.height } };
  }, titlePart);
}
const finite = (ys) => ys.filter((v) => v !== null && v !== undefined);
const same = (a, b) => a.length === b.length && a.every((v, i) => Math.abs(v - b[i]) < 1e-9);

async function upload(p, file) {
  await panel(p).locator('input[type="file"]').setInputFiles(path.join(csvDir, file));
  await ready(p); await p.waitForTimeout(1200);
}

async function operar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p);
  await p.getByRole("button", { name: "＋ NOVO CENÁRIO" }).click(); await ready(p);
  await p.getByLabel("Nome do cenário *").fill("Experimento previsões E2E");
  await p.getByRole("button", { name: "Criar cenário" }).click(); await ready(p);
  assert(await p.getByRole("button", { name: "ABRIR PREVISÕES" }).isEnabled(), "etapa 02 Previsões disponível no Centro");
  assert(await p.getByText("Não implementado").count() >= 2, "Estratégia EMS e Execução continuam 'Não implementado'");
  assert(await p.getByRole("button", { name: /EXECUTAR|OTIMIZAR|RODAR/ }).count() === 0, "nenhum botão fictício de execução");
  await previsoes(p);
  assert(await p.getByRole("tab", { name: "Demanda elétrica (kW)" }).isVisible(), "aba Demanda elétrica");
  assert(await p.getByRole("tab", { name: "Clima — variáveis meteorológicas" }).isVisible(), "aba Clima");
  assert(await p.getByText("ainda não é executado", { exact: false }).first().isVisible(), "aviso: cenário ainda não executado (Piso 2C)");
  await shot(p, "p2b_01_previsoes_vazio.png");

  // ---------------- Demanda: CSV malformado → recusado, sem gráfico
  await panel(p).getByText("Importar CSV").click(); await ready(p);
  await upload(p, "malformado_e2e.csv");
  assert(await p.getByText("Arquivo recusado", { exact: false }).first().isVisible(), "CSV malformado recusado com mensagem");
  assert(await chart(p, "PRÉ-VISUALIZAÇÃO") === null, "CSV malformado: nenhuma pré-visualização (nem a anterior)");
  assert(await panel(p).getByRole("button", { name: "INCORPORAR AO CENÁRIO" }).isDisabled(), "CSV malformado: incorporação bloqueada");
  await noErrors(p, "CSV malformado");

  // ---------------- Demanda: CSV válido → pré-visualização com os valores do arquivo
  await upload(p, "demanda_e2e.csv");
  const pv = await chart(p, "PRÉ-VISUALIZAÇÃO");
  assert(pv !== null, "pré-visualização Plotly da demanda renderizada");
  assert(same(finite(pv.traces[0].y), demandaCSV), `curva pendente = ${demandaCSV.length} valores do CSV (vírgula decimal)`);
  assert(pv.layout.yaxes.length === 1 && pv.layout.yaxes[0].title === "Potência demandada (kW)", "eixo Y único em kW");
  assert(await panel(p).getByText("UTC-03:00 (do arquivo)").first().isVisible(), "fuso do arquivo identificado (UTC-03:00)");
  assert(await panel(p).getByText("1 min (regular)").first().isVisible(), "resolução original 1 min regular");
  assert(await panel(p).getByText(/Energia estimada no período/).first().isVisible(), "energia (kWh) separada da potência");
  // hover com valores concretos
  await p.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
  const box = (await chart(p, "PRÉ-VISUALIZAÇÃO")).box;
  await p.mouse.move(box.x + box.w * 0.5, box.y + box.h * 0.55); await p.waitForTimeout(700);
  const hover = await p.evaluate(() => [...document.querySelectorAll(".hoverlayer")].map((e) => e.textContent).join(" "));
  assert(/kW/.test(hover), "hover mostra valor com unidade (" + hover.replace(/\n/g, " ").slice(0, 60) + ")");
  await shot(p, "p2b_02_demanda_preview_hover.png");
  // zoom por arraste e restauração por duplo clique
  const r0 = (await chart(p, "PRÉ-VISUALIZAÇÃO")).layout.xrange;
  await p.mouse.move(box.x + box.w * 0.35, box.y + box.h * 0.5); await p.mouse.down();
  await p.mouse.move(box.x + box.w * 0.6, box.y + box.h * 0.5, { steps: 8 }); await p.mouse.up(); await p.waitForTimeout(800);
  const r1 = (await chart(p, "PRÉ-VISUALIZAÇÃO")).layout.xrange;
  assert(JSON.stringify(r1) !== JSON.stringify(r0), "zoom altera o intervalo do eixo X");
  await p.mouse.dblclick(box.x + box.w * 0.5, box.y + box.h * 0.5); await p.waitForTimeout(800);
  const r2 = (await chart(p, "PRÉ-VISUALIZAÇÃO")).layout.xrange;
  assert(JSON.stringify(r2) === JSON.stringify(r0), "duplo clique restaura o encuadre");
  await panel(p).getByRole("button", { name: "INCORPORAR AO CENÁRIO" }).click(); await ready(p);
  assert(await panel(p).getByText("Incorporado nesta sessão — não salvo").first().isVisible(), "demanda incorporada (ainda não salva)");
  const cur = await chart(p, "perfil do cenário");
  assert(cur && same(finite(cur.traces[0].y), demandaCSV), "perfil do cenário mostra a curva incorporada");

  // ---------------- Clima: conjunto compartilhado FV + eólica por CSV
  await tab(p, /Clima/);
  assert(await panel(p).getByText("Conjunto climático compartilhado", { exact: false }).first().isVisible(), "clima: conjunto compartilhado identificado");
  assert(await panel(p).getByText("Eólica: Aerogerador E2E", { exact: false }).first().isVisible(), "clima: tecnologias do inventário (FV + eólica) nomeadas");
  await panel(p).getByText("Importar CSV").click(); await ready(p);
  await upload(p, "clima_e2e.csv");
  assert(await panel(p).getByRole("button", { name: "INCORPORAR AO CENÁRIO" }).isDisabled(), "clima: bloqueado até mapear/confirmar");
  await selectOption(panel(p), p, "Velocidade do vento — obrigatória", "vento");
  await selectOption(panel(p), p, "Direção do vento — opcional", "direcao_vento_deg");
  await selectOption(panel(p), p, "Unidade de GHI", "W/m");
  await selectOption(panel(p), p, "Unidade de Vento", "m/s");
  assert(await panel(p).getByText("unidade detectada no cabeçalho").count() >= 1, "unidade detectada no cabeçalho sinalizada");
  assert(await panel(p).getByText("unidade confirmada pelo usuário").count() >= 2, "unidades confirmadas pelo usuário sinalizadas");
  assert(await panel(p).getByRole("button", { name: "INCORPORAR AO CENÁRIO" }).isEnabled(), "clima: incorporável após confirmar");
  await panel(p).getByText("Mostrar também a grade de 1 min").first().click(); await ready(p);
  const cl = await chart(p, "PRÉ-VISUALIZAÇÃO");
  const titles = cl.layout.yaxes.map((a) => a.title);
  assert(JSON.stringify(titles) === JSON.stringify(["W/m²", "°C", "m/s", "°"]), "clima: um painel por grandeza (" + titles.join(", ") + ")");
  assert(cl.layout.yaxes.every((a) => !a.overlaying), "clima: nenhum eixo Y sobreposto");
  const ghi = cl.traces.find((t) => t.name.startsWith("GHI — dados originais"));
  assert(same(finite(ghi.y), climaCSV.map((r) => parseFloat(r[1]))), "GHI pendente = valores do CSV");
  const dirGrid = cl.traces.find((t) => t.name.startsWith("Direção — grade 1 min"));
  const early = finite(dirGrid.y.slice(0, 31));
  assert(early.length > 20 && early.every((v) => v >= 345 || v <= 10.0001), "direção 350°→5° interpolada pelo menor arco (nunca 180°)");
  await panel(p).locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
  await shot(p, "p2b_03_clima_preview.png");
  await panel(p).getByRole("button", { name: "INCORPORAR AO CENÁRIO" }).click(); await ready(p);
  await p.getByRole("button", { name: "SALVAR CENÁRIO" }).click(); await ready(p);
  assert(await p.getByText("Cenário salvo (versão 2)").first().isVisible(), "SALVAR CENÁRIO grava a versão 2");
  assert(await panel(p).getByText("Salvo · v2").first().isVisible(), "clima salvo (v2)");
  await tab(p, "Demanda elétrica (kW)");
  assert(await panel(p).getByText("Salvo · v2").first().isVisible(), "demanda salva (v2)");

  // ---------------- nova fonte: pendente distinto do perfil atual (nada enganoso)
  await panel(p).getByText("Sintético").click(); await ready(p);
  assert(await panel(p).getByText("Perfil SINTÉTICO hipotético", { exact: false }).first().isVisible(), "sintético rotulado como hipotético");
  const pend = await chart(p, "PRÉ-VISUALIZAÇÃO");
  const atual = await chart(p, "perfil do cenário");
  assert(same(finite(atual.traces[0].y), demandaCSV), "perfil salvo continua o do CSV");
  assert(!same(finite(pend.traces[0].y), demandaCSV), "pré-visualização mostra a NOVA curva pendente");
  await shot(p, "p2b_04_pendente_vs_atual.png");
  // integridade e reprodutibilidade
  await panel(p).getByRole("button", { name: "VERIFICAR INTEGRIDADE E REPRODUTIBILIDADE" }).click(); await ready(p);
  assert(await panel(p).getByText("mesmo SHA-256", { exact: false }).first().isVisible(), "reprodutibilidade verificada (SHA-256)");

  // ---------------- Inicialização intacta
  await p.getByRole("button", { name: "← Centro de Operação" }).click(); await ready(p);
  assert(await p.getByText("Previsões — Definidas", { exact: false }).first().isVisible(), "painel: Previsões definidas");
  await p.getByRole("button", { name: "ABRIR INICIALIZAÇÃO" }).click(); await ready(p);
  assert(await p.getByText("Inicialização · estados iniciais", { exact: false }).first().isVisible(), "Inicialização abre normalmente");
  assert(await p.getByLabel("SOC inicial (%)", { exact: true }).count() === 2, "Inicialização: controles de SOC dos 2 bancos");
  await noErrors(p, "operar");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p);
  assert(await p.getByText("Experimento previsões E2E · v2").first().isVisible().catch(() => false) ||
         await p.getByText("Experimento previsões E2E", { exact: false }).first().isVisible(), "cenário persistido após reinício");
  assert(await p.getByText("Previsões — Definidas", { exact: false }).first().isVisible(), "prontidão: Previsões definidas");
  await previsoes(p);
  assert(await panel(p).getByText("Salvo · v2").first().isVisible(), "demanda: Salvo · v2");
  const d = await chart(p, "perfil do cenário");
  assert(d && same(finite(d.traces[0].y), demandaCSV), "demanda recuperada exatamente (121 valores)");
  await tab(p, /Clima/);
  const c = await chart(p, "perfil do cenário");
  assert(c && c.layout.yaxes.length === 4, "clima recuperado com 4 painéis");
  const ghi = c.traces.find((t) => t.name.startsWith("GHI — dados originais"));
  assert(same(finite(ghi.y), climaCSV.map((r) => parseFloat(r[1]))), "GHI recuperada exatamente");
  await shot(p, "p2b_10_reinicio_clima.png");
  await noErrors(p, "reinício");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 }); current = p;
    await p.goto(url); await ready(p); await abrir(p); await previsoes(p);
    assert(await overflow(p) <= 1, `tablet ${tag}: Previsões sem rolagem horizontal`);
    const d = await chart(p, "perfil do cenário");
    assert(d && d.box.w > 200 && d.box.x >= 0 && d.box.x + d.box.w <= w + 1, `tablet ${tag}: gráfico dentro da tela (${Math.round(d.box.w)} px)`);
    await p.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
    await shot(p, `p2b_20_tablet_${tag}.png`);
    await tab(p, /Clima/);
    assert(await overflow(p) <= 1, `tablet ${tag}: clima sem rolagem horizontal`);
    await p.close();
  }
  const dk = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 }); current = dk;
  await dk.goto(url); await ready(dk); await abrir(dk); await previsoes(dk);
  await dk.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
  await shot(dk, "p2b_22_escuro_demanda.png");
  await noErrors(dk, "tema escuro");
  await dk.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { operar, reinicio, tablet }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: false }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
