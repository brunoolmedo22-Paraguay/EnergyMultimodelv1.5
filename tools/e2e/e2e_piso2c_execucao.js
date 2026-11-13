// Verificação E2E em navegador real (Playwright/Chromium) do PISO 2C — Execução EMS e persistência científica.
//
// Preparação (diretório VAZIO; microrrede fictícia com cenário cujos estados e previsões já estão gravados):
//   python tools/e2e/seed_piso2c.py <SEEDS2_DATA_DIR>
//   SEEDS2_DATA_DIR=<dir> python -m streamlit run app.py --server.headless true --server.port <porta>
// Uso:
//   node tools/e2e/e2e_piso2c_execucao.js <url> <fase> <pasta_capturas>
// Fases (o servidor é encerrado/reiniciado ENTRE as fases pelo roteiro de execução):
//   operar   — Gestor → ABRIR → Centro (4 etapas reais) → Estratégia EMS (função objetivo única; padrão V1.6; salvar)
//              → Execução (horizonte disponível; janela; salvar; relatório com conversão UTC e interpolação) →
//              EXECUTAR → progresso real → rodada imutável (indicadores, curvas Plotly) → recarga da página (mesma
//              rodada, nenhuma nova) → cenário incompatível (SOC 15 %) NÃO executável → corrigido → missão longa
//              iniciada; o processo termina com o servidor a ser derrubado DURANTE essa rodada ("KILL_NOW").
//   reinicio — depois do reinício do servidor: rodada concluída reaberta com o MESMO custo (sem recalcular) e a
//              rodada derrubada marcada "Interrompida", sem resultados; execução volta a ser possível.
//   tablet   — rodada em tablet (retrato/paisagem, sem rolagem horizontal, gráficos dentro da tela) e tema escuro.
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const { expandirCartoes } = require("./catalogo_util");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
const costFile = path.join(outDir, "custo_rodada_1.txt");
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(900);
}
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function overflow(p) { return p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }
async function abrir(p) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await expandirCartoes(p); await p.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
}
async function btn(p, name) { await p.getByRole("button", { name }).first().click(); await ready(p); }
async function voltar(p) { await btn(p, "← Centro de Operação"); }
async function setNumber(p, label, value, nth = 0) {
  const box = p.getByLabel(label, { exact: true }).nth(nth);
  await box.fill(String(value)); await box.press("Enter"); await ready(p);
}
async function chart(p, titlePart) {
  return p.evaluate((t) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title &&
      String(el.layout.title.text || "").includes(t) && el.offsetParent !== null);
    if (!g) return null;
    const r = g.getBoundingClientRect();
    return { traces: g._fullData.map((d) => ({ name: d.name, n: (d.y && d.y.length) || 0 })), box: { x: r.x, y: r.y, w: r.width, h: r.height } };
  }, titlePart);
}
async function kpi(p, label) {
  return p.evaluate((l) => {
    const k = [...document.querySelectorAll(".sd-kpi")].find((e) => e.querySelector("small") && e.querySelector("small").textContent === l);
    return k ? k.querySelector("b").textContent : null;
  }, label);
}
async function execucao(p) {
  await btn(p, "ABRIR EXECUÇÃO");
  await p.getByText("Execução do cenário", { exact: false }).first().waitFor({ timeout: 60000 });
}
async function waitRun(p) {
  // a execução segue no servidor; a página acompanha o progresso real (lido do banco) e abre a rodada ao concluir
  let sawProgress = false;
  for (let i = 0; i < 240; i++) {
    if (await p.getByText("Rodada · imutável").count()) return sawProgress;
    if (await p.getByText(/Despacho EMS · passo \d+ de \d+/).count()) sawProgress = true;
    await p.waitForTimeout(500);
  }
  throw new Error("FALHA: a rodada não terminou em 120 s");
}

async function operar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p);
  for (const b2 of ["ABRIR INICIALIZAÇÃO", "ABRIR PREVISÕES", "ABRIR ESTRATÉGIA EMS", "ABRIR EXECUÇÃO"]) {
    assert(await p.getByRole("button", { name: b2 }).isEnabled(), `etapa real no Centro: ${b2}`);
  }
  assert(await p.getByText("Não implementado").count() === 0, "nenhuma etapa 'Não implementado'");
  assert(await p.getByRole("button", { name: /EXECUTAR CENÁRIO/ }).count() === 0, "EXECUTAR não aparece no painel");
  assert(await p.getByText("Não executável (v2)").first().isVisible(), "preflight da versão salva: não executável (sem estratégia)");
  await shot(p, "p2c_01_centro.png");

  // ---------------- 03 Estratégia EMS
  await btn(p, "ABRIR ESTRATÉGIA EMS");
  assert(await p.getByText("Custo econômico da operação (função objetivo do EMS V1.6)").first().isVisible(), "função objetivo única identificada");
  assert(await p.getByText("sem seletor multiobjetivo", { exact: false }).first().isVisible(), "sem seletor multiobjetivo");
  await btn(p, "DEFINIR COM OS VALORES PADRÃO DO MOTOR V1.6");
  assert(await p.getByText("GWO · Grey Wolf Optimizer").first().isVisible(), "algoritmos existentes do motor V1.6");
  await shot(p, "p2c_02_estrategia.png");
  await btn(p, "SALVAR CENÁRIO");
  assert(await p.getByText("Cenário salvo (versão 3)").first().isVisible(), "estratégia gravada como versão 3 do cenário");
  await noErrors(p, "estratégia");

  // ---------------- 04 Execução: janela, relatório, executar
  await voltar(p); await execucao(p);
  assert(await p.getByText("Horizonte disponível (cobertura comum)").first().isVisible(), "horizonte disponível dos perfis");
  assert(await p.getByText("60 s (fixo no runtime V1.6)").first().isVisible(), "passo do motor informado (não editável)");
  await btn(p, "DEFINIR JANELA DA MISSÃO");
  assert(await p.getByRole("button", { name: /EXECUTAR CENÁRIO/ }).isDisabled(), "EXECUTAR bloqueado com alterações não salvas");
  await btn(p, "SALVAR CENÁRIO");
  assert(await p.getByText("Cenário salvo (versão 4)").first().isVisible(), "janela gravada (versão 4)");
  assert(await p.getByText("Resumo de preparação · versão salva v4").first().isVisible(), "resumo de preparação da versão salva");
  assert(await p.getByText("convertidas para UTC", { exact: false }).first().isVisible(), "fusos convertidos para UTC (demanda × clima)");
  assert(await p.getByText(/interpolação linear em \d+ de 121 instantes, sem extrapolação/).first().isVisible(), "interpolação registrada, sem extrapolação");
  assert(await p.getByText("exatamente o estado inicial do EMS V1.6", { exact: false }).first().isVisible(), "PEMFC: equivalência exata com o motor");
  await shot(p, "p2c_03_preparacao.png");
  const run = p.getByRole("button", { name: "▶ EXECUTAR CENÁRIO · VERSÃO 4" });
  assert(await run.isEnabled(), "EXECUTAR habilitado para o cenário compatível");
  await run.click();
  const saw = await waitRun(p);
  log(saw ? "progresso real do despacho observado" : "rodada concluiu antes de o progresso ser amostrado");
  await ready(p);
  const custo = await kpi(p, "Custo total");
  assert(custo && /^R\$ \d/.test(custo), `rodada concluída com custo ${custo}`);
  fs.writeFileSync(costFile, custo);
  assert(await kpi(p, "Energia atendida") !== null && await kpi(p, "Não atendida") !== null && await kpi(p, "Excedente") !== null,
    "energia atendida, não atendida e excedente");
  assert(await kpi(p, "H₂ consumido") !== null, "consumo de H₂");
  const pw = await chart(p, "Demanda e potência por fonte");
  assert(pw && pw.traces.find((t) => t.name === "Demanda").n === 121, "curva de demanda (121 passos)");
  assert(pw.traces.some((t) => t.name === "H₂ / PEMFC") && pw.traces.some((t) => t.name.startsWith("Bateria")), "potência por fonte");
  assert(await chart(p, "Estado de carga da bateria") !== null, "curva de SOC");
  assert(p.url().includes("run="), "URL identifica a rodada (?run=)");
  await p.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
  await shot(p, "p2c_04_rodada.png");
  // recarga do navegador: mesma rodada, lida do armazenamento; nenhuma nova execução
  await p.reload(); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  assert(await kpi(p, "Custo total") === custo, "recarga: a mesma rodada é reaberta com o mesmo custo");
  await btn(p, "← Execução do cenário");
  assert(await p.getByText("Concluída", { exact: true }).count() === 1, "recarga não criou nova rodada (1 concluída no histórico)");

  // ---------------- cenário incompatível: SOC fora dos limites efetivos → gravável, mas não executável
  await voltar(p); await btn(p, "ABRIR INICIALIZAÇÃO");
  await setNumber(p, "SOC inicial (%)", 15, 0); await setNumber(p, "SOC inicial (%)", 15, 1);
  await btn(p, "SALVAR CENÁRIO");
  assert(await p.getByText("Cenário salvo (versão 5)").first().isVisible(), "SOC 15 % gravado (advertência, não bloqueio)");
  await voltar(p); await execucao(p);
  assert(await p.getByText("Este cenário NÃO pode ser executado", { exact: false }).first().isVisible(), "relatório: não executável");
  assert(await p.getByText("restrição EFETIVA", { exact: false }).first().isVisible(), "motivo: limites de SOC efetivos do EMS V1.6");
  assert(await p.getByRole("button", { name: "▶ EXECUTAR CENÁRIO · VERSÃO 5" }).isDisabled(), "EXECUTAR bloqueado (incompatível)");
  await shot(p, "p2c_05_incompativel.png");
  await noErrors(p, "incompatível");

  // ---------------- missão longa iniciada e servidor derrubado durante a rodada
  await voltar(p); await btn(p, "ABRIR INICIALIZAÇÃO");
  await setNumber(p, "SOC inicial (%)", 60, 0); await setNumber(p, "SOC inicial (%)", 60, 1);
  await btn(p, "SALVAR CENÁRIO");
  await voltar(p); await execucao(p);
  await setNumber(p, "Duração (min)", 700);
  await btn(p, "SALVAR CENÁRIO");
  assert(await p.getByText("Cenário salvo (versão 7)").first().isVisible(), "missão de 700 min gravada (versão 7)");
  await p.getByRole("button", { name: "▶ EXECUTAR CENÁRIO · VERSÃO 7" }).click();
  await p.getByText("Execução em andamento", { exact: false }).first().waitFor({ timeout: 30000 });
  assert(true, "rodada longa em andamento (o servidor será derrubado agora)");
  await shot(p, "p2c_06_em_execucao.png");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  console.log("KILL_NOW");
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p); await execucao(p);
  assert(await p.getByText("Interrompida", { exact: true }).count() === 1, "rodada derrubada marcada como Interrompida");
  assert(await p.getByText("Concluída", { exact: true }).count() === 1, "rodada concluída preservada");
  assert(await p.getByRole("button", { name: "▶ EXECUTAR CENÁRIO · VERSÃO 7" }).isEnabled(), "nenhuma rodada presa em execução");
  await shot(p, "p2c_10_reinicio_historico.png");
  const abrirBtns = p.getByRole("button", { name: "Abrir", exact: true });
  await abrirBtns.nth(1).click(); await ready(p);                   // mais antiga = a concluída
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  assert(await kpi(p, "Custo total") === fs.readFileSync(costFile, "utf8"), "após reinício: mesmo custo, lido do armazenamento");
  assert((await chart(p, "Demanda e potência por fonte")).traces.find((t) => t.name === "Demanda").n === 121, "séries completas recuperadas");
  await shot(p, "p2c_11_reinicio_rodada.png");
  await btn(p, "← Execução do cenário");
  await abrirBtns.nth(0).click(); await ready(p);
  assert(await p.getByText("Rodada interrompida", { exact: false }).first().isVisible(), "rodada interrompida: motivo exibido");
  assert(await p.getByText("Nenhum resultado foi gravado", { exact: false }).first().isVisible(), "interrompida: nenhum resultado parcial");
  assert(await chart(p, "Demanda e potência por fonte") === null, "interrompida: nenhuma curva");
  await noErrors(p, "reinício");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 }); current = p;
    await p.goto(url); await ready(p); await abrir(p); await execucao(p);
    assert(await overflow(p) <= 1, `tablet ${tag}: Execução sem rolagem horizontal`);
    await p.getByRole("button", { name: "Abrir", exact: true }).nth(1).click(); await ready(p);
    await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
    assert(await overflow(p) <= 1, `tablet ${tag}: rodada sem rolagem horizontal`);
    const c = await chart(p, "Demanda e potência por fonte");
    assert(c && c.box.w > 200 && c.box.x >= 0 && c.box.x + c.box.w <= w + 1, `tablet ${tag}: gráfico dentro da tela (${Math.round(c.box.w)} px)`);
    await p.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
    await shot(p, `p2c_20_tablet_${tag}.png`);
    await p.close();
  }
  const dk = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 }); current = dk;
  await dk.goto(url); await ready(dk); await abrir(dk); await execucao(dk);
  await dk.getByRole("button", { name: "Abrir", exact: true }).nth(1).click(); await ready(dk);
  await dk.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  await shot(dk, "p2c_22_escuro_rodada.png");
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
