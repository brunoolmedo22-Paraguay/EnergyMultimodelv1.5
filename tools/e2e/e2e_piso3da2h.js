// E2E em navegador real (Playwright/Chromium) do PISO 3D-A2-H — PEMFC/H₂ no EMS V2.
// Preparação: python tools/e2e/seed_piso3da2h.py <DIR> [bloqueio|fluxo]; roteiro completo: tools/e2e/run_piso3da2h.sh
// Uso: node tools/e2e/e2e_piso3da2h.js <url> <fase> <pasta_capturas>
//   bloqueio — política B04 do repositório (PENDENTE): execução bloqueada e explicada; curva q(P) na bancada H₂;
//   fluxo    — servidor com APROVAÇÃO B04 SIMULADA: declarações PEMFC preenchidas PELA INTERFACE, preflight apto,
//              missão real (HiGHS), rodada com aceitação separada (algébrica × dinâmica × física);
//   reabrir  — servidor NOVO, SEM solver, com motor e modelos PEMFC sabotados: a rodada é reaberta pela interface.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const [url, fase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const runFile = path.join(outDir, "rodada_3da2h.json");
let count = 0;
const log = (...a) => console.log(`[3da2h:${fase}]`, ...a);
function assert(c, msg) { if (!c) throw new Error("FALHA: " + msg); count += 1; log("ok —", msg); }
async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 180000 }).catch(() => {});
  await p.waitForTimeout(700);
}
const visible = async (p, t) => (await p.getByText(t, { exact: false }).count()) > 0;
async function btn(p, name) { await p.getByRole("button", { name }).first().click(); await ready(p); }
async function chart(p, t) {
  return p.evaluate((tt) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title && String(el.layout.title.text || "").includes(tt));
    return g ? g._fullData.map((d) => d.name) : null;
  }, t);
}
async function rolarAte(p, loc, n = 240) {
  for (let i = 0; i < n && !(await loc.count()); i++) { await p.mouse.wheel(0, 1200); await p.waitForTimeout(400); }
  await loc.first().waitFor({ timeout: 30000 });
  await loc.first().scrollIntoViewIfNeeded();
}
async function abrirMicrorrede(p) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  const cartao = p.locator('[data-testid="stVerticalBlock"]').filter({ has: p.getByText("Microrrede E2E 3D-A2-H", { exact: true }) })
    .filter({ has: p.getByRole("button", { name: "ABRIR MICRORREDE" }) }).last();
  await cartao.waitFor({ timeout: 60000 });
  await cartao.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
}
async function numero(escopo, p, rotulo, valor) {
  const inp = escopo.getByLabel(rotulo, { exact: true }).first();
  await inp.scrollIntoViewIfNeeded();
  await inp.fill(String(valor)); await inp.press("Tab"); await ready(p);
}
async function texto(escopo, p, rotulo, valor) {
  const inp = escopo.getByLabel(rotulo, { exact: true }).first();
  await inp.scrollIntoViewIfNeeded();
  await inp.fill(String(valor)); await inp.press("Tab"); await ready(p);
}
async function opcao(escopo, p, rotulo, valor) {
  const box = escopo.locator('div[data-testid="stSelectbox"]').filter({ hasText: rotulo }).first();
  await box.scrollIntoViewIfNeeded();
  await box.locator("input").click();
  await p.keyboard.type(valor); await p.waitForTimeout(300); await p.keyboard.press("Enter"); await ready(p);
}
async function waitRun(p, seconds = 600) {
  for (let i = 0; i < seconds * 2; i++) {
    if (await p.getByText("Rodada · imutável").count()) return;
    await p.waitForTimeout(500);
  }
  throw new Error(`FALHA: a rodada V2 não terminou em ${seconds} s`);
}
async function conferirRodada(p, tag) {
  await p.getByText("Custo REALIZADO").first().waitFor({ timeout: 120000 }); await ready(p);
  assert(await visible(p, "✓ Evidência verificada"), `${tag}: evidência verificada (hashes, vistas regeneradas, auditoria, B04)`);
  assert(!(await visible(p, "EVIDÊNCIA COM PROBLEMAS")), `${tag}: nenhuma falha de integridade`);
  assert(await visible(p, "Critério de aceitação"), `${tag}: aceitação SEPARADA exibida`);
  assert(await visible(p, "Despacho ALGEBRICAMENTE aprovado e COERENTE com o modelo dinâmico aproximado"),
    `${tag}: algébrica APROVADA · dinâmica COERENTE`);
  assert(await visible(p, "NÃO VALIDADO"), `${tag}: física NÃO VALIDADA (modelo aproximado)`);
  assert(!(await visible(p, "DINAMICAMENTE INCOERENTE")), `${tag}: nenhum alerta de incoerência dinâmica`);
  assert(await visible(p, "PEMFC (unidade)") && await visible(p, "Partidas · paradas"), `${tag}: tabela PEMFC por unidade`);
  const pot = await chart(p, "Demanda × atendimento por recurso");
  assert(pot && pot.some((n) => n.startsWith("PEMFC ")), `${tag}: atendimento da carga inclui a PEMFC`);
}

async function bloqueio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  try {
    await p.goto(url); await ready(p);
    await abrirMicrorrede(p);
    await btn(p, "ABRIR EXECUÇÃO");
    assert(await visible(p, "AGUARDANDO APROVAÇÃO"), "execução PEMFC bloqueada: certificação B04 aguardando aprovação");
    assert(await visible(p, "curva q(P) do modelo físico"), "curva derivada do modelo físico reportada no preflight");
    assert(await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isDisabled(), "EXECUTAR MISSÃO V2 desabilitado");
    await p.getByText("AGUARDANDO APROVAÇÃO", { exact: false }).first().scrollIntoViewIfNeeded().catch(() => {});
    await p.mouse.wheel(0, -200); await p.waitForTimeout(600);
    await p.screenshot({ path: path.join(outDir, "p3da2h_01_bloqueio_b04.png") });
    await btn(p, "← Centro de Operação");
    const exp = p.getByText("bancadas individuais dos modelos", { exact: false });
    await rolarAte(p, exp);
    await exp.first().click(); await ready(p);
    await p.getByRole("button", { name: "ABRIR H₂ / PEMFC" }).first().waitFor({ timeout: 60000 });
    await btn(p, "ABRIR H₂ / PEMFC");
    await btn(p, "Caracterização");
    await p.getByText("H₂ · Curva de consumo do EMS", { exact: false }).first().scrollIntoViewIfNeeded();
    for (let i = 0; i < 60 && !(await chart(p, "Consumo de hidrogênio × potência líquida")); i++) {
      await p.mouse.wheel(0, 600); await p.waitForTimeout(500);
    }
    await ready(p);
    const nomes = await chart(p, "Consumo de hidrogênio × potência líquida");
    assert(nomes && nomes.includes("Modelo físico (H₂ suprido)") && nomes.includes("PWL usada pelo EMS") && nomes.includes("Vértices da PWL"),
      "bancada: modelo físico × PWL do EMS × vértices");
    assert(await visible(p, "não são medições"), "bancada: modelo aproximado identificado (não são medições)");
    for (let i = 0; i < 20 && !(await chart(p, "Erro da aproximação")); i++) { await p.mouse.wheel(0, 500); await p.waitForTimeout(400); }
    assert((await chart(p, "Erro da aproximação")) !== null, "bancada: diagnóstico do erro da aproximação");
    assert(await visible(p, "Não aprovada"), "bancada: certificação B04 declarada NÃO aprovada");
    await p.getByText("H₂ · Curva de consumo do EMS", { exact: false }).first().scrollIntoViewIfNeeded().catch(() => {});
    await p.mouse.wheel(0, 260); await p.waitForTimeout(600);
    await p.screenshot({ path: path.join(outDir, "p3da2h_02_bancada_curva.png") });
    const graf = p.locator(".js-plotly-plot").filter({ has: p.getByText("Consumo de hidrogênio × potência líquida", { exact: false }) }).first();
    await graf.scrollIntoViewIfNeeded(); await p.waitForTimeout(600);
    await graf.screenshot({ path: path.join(outDir, "p3da2h_03_grafico_modelo_pwl.png") });
    assert(errs.length === 0, `sem erros de JavaScript: ${JSON.stringify(errs)}`);
  } catch (e) { await p.screenshot({ path: path.join(outDir, "FALHA_bloqueio.png") }).catch(() => {}); throw e; }
}

async function fluxo(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  try {
    await p.goto(url); await ready(p);
    await abrirMicrorrede(p);
    await btn(p, "ABRIR ESTRATÉGIA EMS");
    const cab = p.getByText("PEMFC / H₂: inicialização física e commitment", { exact: false });
    await rolarAte(p, cab);
    const fc = p.locator('[data-testid="stVerticalBlock"]').filter({ has: cab }).last();
    assert(await fc.getByLabel("Potência mínima técnica por unidade (ON) [kW]", { exact: true }).inputValue() === "",
      "declarações PEMFC começam VAZIAS (nada pré-preenchido)");
    for (const [rot, v] of [["Temperatura de operação do STACK [K]", 353.15], ["Pressão do ânodo (manométrica) [kPa(g)]", 140],
      ["Pressão do cátodo (manométrica) [kPa(g)]", 120], ["Pressão ambiente (absoluta) [kPa]", 101.325],
      ["Potência mínima técnica por unidade (ON) [kW]", 10], ["Rampa máxima (aplicada à subida E à descida pela ponte 3C-1) [kW/min]", 120],
      ["Tempo mínimo em operação [min]", 0], ["Tempo mínimo em repouso [min]", 0],
      ["Temperatura AMBIENTE (só o modelo dinâmico: durações de partida/parada) [°C]", 25], ["Preço do hidrogênio [R$/kg]", 10],
      ["Unidade 1 · potência anterior [kW]", 0], ["Unidade 1 · tempo no estado [min]", 600]]) {
      await numero(fc, p, rot, v);
    }
    await opcao(fc, p, "Abstração de partida/parada (D05)", "instantanea_unidade_quente");
    await opcao(fc, p, "Limites de partida/parada", "rampa_convencional");
    await opcao(fc, p, "Unidade 1 · estado inicial", "desligada");
    await opcao(fc, p, "Procedência (tipo)", "sintetico");
    await texto(fc, p, "Fonte (documento, pessoa ou 'sintético de ensaio')", "sintético de ensaio (E2E 3D-A2-H)");
    assert(await fc.getByLabel("Preço do hidrogênio [R$/kg]", { exact: true }).inputValue() === "10", "declarações PEMFC preenchidas pela interface");
    await p.screenshot({ path: path.join(outDir, "p3da2h_04_declaracoes_pemfc.png") });
    await btn(p, "SALVAR CENÁRIO");
    await btn(p, "← Centro de Operação");
    await btn(p, "ABRIR EXECUÇÃO");
    await p.getByText("Preflight V2", { exact: false }).first().waitFor({ timeout: 300000 }); await ready(p);
    assert(await visible(p, "Apto para o motor V2"), "preflight V2 apto (aprovação B04 SIMULADA no servidor de teste)");
    assert(await visible(p, "restrições do modelo dinâmico compatíveis"), "restrições do modelo dinâmico verificadas a priori");
    assert(!(await visible(p, "AGUARDANDO APROVAÇÃO")), "sem bloqueio B04 (aprovação simulada ativa)");
    await p.screenshot({ path: path.join(outDir, "p3da2h_05_preflight_apto.png") });
    await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).click();
    await waitRun(p); await ready(p);
    await conferirRodada(p, "rodada");
    fs.writeFileSync(runFile, JSON.stringify({ link: p.url() }));
    await p.getByText("Critério de aceitação", { exact: false }).first().scrollIntoViewIfNeeded();
    await p.screenshot({ path: path.join(outDir, "p3da2h_06_rodada_aceitacao.png") });
    assert(errs.length === 0, `sem erros de JavaScript: ${JSON.stringify(errs)}`);
  } catch (e) { await p.screenshot({ path: path.join(outDir, "FALHA_fluxo.png") }).catch(() => {}); throw e; }
}

async function reabrir(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  try {
    const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
    await p.goto(info.link.replace(/^https?:\/\/[^/]+/, url.replace(/\/$/, ""))); await ready(p);
    await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 });
    await conferirRodada(p, "reaberta após reinício (sem solver, modelos PEMFC sabotados)");
    await p.getByText("Critério de aceitação", { exact: false }).first().scrollIntoViewIfNeeded();
    await p.screenshot({ path: path.join(outDir, "p3da2h_07_rodada_reaberta.png") });
    assert(errs.length === 0, `sem erros de JavaScript: ${JSON.stringify(errs)}`);
  } catch (e) { await p.screenshot({ path: path.join(outDir, "FALHA_reabrir.png") }).catch(() => {}); throw e; }
}

(async () => {
  const b = await chromium.launch();
  try {
    await ({ bloqueio, fluxo, reabrir })[fase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    console.error(e.message || e); process.exitCode = 1;
  } finally { await b.close(); }
})();
