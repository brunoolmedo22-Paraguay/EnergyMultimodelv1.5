// Verificação E2E em navegador real (Playwright/Chromium) do PISO 2A — Centro de Operação.
//
// Preparação (diretório VAZIO; microrrede comissionada fictícia de teste):
//   python tools/e2e/seed_piso2a.py <SEEDS2_DATA_DIR>
//   SEEDS2_DATA_DIR=<dir> python -m streamlit run app.py --server.headless true --server.port <porta>
// Uso:
//   node tools/e2e/e2e_piso2a_centro_operacao.js <url> <fase> <pasta_capturas>
// Fases:
//   operar    — Gestor → ABRIR → Centro de Operação (início da microrrede), identidade na barra superior, navegação
//               agrupada, Alcance como link secundário, etapas futuras sem controles; criar cenário; Inicialização:
//               SOC fora da restrição (aviso sem bloqueio), PEMFC desligada com 25 kW (erro, nada gravado), correção e
//               gravação; duplicar; duas sessões editando o mesmo cenário (conflito explícito, sem sobrescrita);
//               bancada V1.6 e Simulação acessíveis; TROCAR MICRORREDE volta ao Gestor
//   reinicio  — executar DEPOIS de reiniciar o servidor: cenários e estados iniciais persistidos
//   tablet    — Centro de Operação e Inicialização em tablet (retrato/paisagem, sem rolagem horizontal) e tema escuro
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const { expandirCartoes } = require("./catalogo_util");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: true });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(900);
}
async function selectOption(scope, p, label, text) {
  const box = scope.locator('div[data-testid="stSelectbox"]').filter({ hasText: label }).first();
  await box.locator("input").click();
  await p.keyboard.type(text);
  await p.waitForTimeout(250);
  await p.keyboard.press("Enter");
  await ready(p);
}
async function fillNumber(scope, p, label, value) {
  const inp = scope.getByLabel(label, { exact: true });
  await inp.fill(String(value));
  await inp.press("Tab");
  await ready(p);
}
// Cartão (container com borda) mais interno que contém o texto.
const cardOf = (p, text) => p.locator('[data-testid="stVerticalBlock"]').filter({ hasText: text }).last();
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function abrir(p) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await expandirCartoes(p); await p.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
}
async function inicializacao(p) {
  await p.getByRole("button", { name: "ABRIR INICIALIZAÇÃO" }).click(); await ready(p);
  await p.getByText("Inicialização · estados iniciais", { exact: false }).first().waitFor({ timeout: 60000 });
}
async function overflow(p) { return p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }

async function operar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p);
  assert(await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).isVisible(),
         "microrrede comissionada abre no Centro de Operação");
  // identidade da microrrede como "perfil" (contexto), não como item do menu
  assert((await p.locator(".tb-mg .tb-site").innerText()) === "Microrrede E2E Piso 2A", "barra superior: nome da microrrede ativa");
  assert((await p.locator(".tb-mg .tb-av").innerText()).length === 2, "barra superior: avatar com iniciais");
  assert(/^ID [0-9a-f]{8} · inventário rev\. 1$/.test(await p.locator(".tb-mg .tb-sub").innerText()), "barra superior: ID curto e revisão");
  assert(await p.locator(".tb-mg .tb-switch").isVisible(), "TROCAR MICRORREDE dentro do controle de identidade");
  const links = await p.locator(".tb-link").allInnerTexts();
  assert(JSON.stringify(links) === JSON.stringify(["Centro de Operação", "Simulação", "Gestão da Microrrede", "Resultados"]),
         "navegação: operação · gestão física · resultados (" + links.join(" | ") + ")");
  assert(await p.locator(".tb-nav .tb-sep").count() === 2, "grupos da navegação separados visualmente");
  assert(!links.some((l) => /Microrrede A|Microrrede E2E|Alcance/.test(l)), "microrrede e Alcance não são itens da navegação principal");
  assert(await p.locator(".tb-doc", { hasText: "Alcance" }).isVisible(), "Alcance acessível como documentação secundária");
  assert(await p.locator(".tb-link.on").innerText() === "Centro de Operação", "Centro de Operação marcado como atual");
  assert(await p.getByText("Nenhum cenário nesta microrrede", { exact: false }).isVisible(), "estado vazio de cenários");
  for (const s of ["Previsões", "Estratégia EMS", "Execução"]) {
    assert(await p.getByText(s, { exact: true }).first().isVisible(), `etapa identificada: ${s}`);
  }
  // Piso 2B/2C: as etapas 02–04 são reais (ABRIR PREVISÕES / ABRIR ESTRATÉGIA EMS / ABRIR EXECUÇÃO); EXECUTAR só
  // existe DENTRO da etapa 04, depois do preflight — nunca no painel.
  assert(await p.getByRole("button", { name: "ABRIR PREVISÕES" }).count() === 1, "etapa 02 Previsões com ABRIR PREVISÕES (Piso 2B)");
  assert(await p.getByRole("button", { name: "ABRIR ESTRATÉGIA EMS" }).count() === 1, "etapa 03 Estratégia EMS real (Piso 2C)");
  assert(await p.getByRole("button", { name: "ABRIR EXECUÇÃO" }).count() === 1, "etapa 04 Execução real (Piso 2C)");
  const fake = await p.getByRole("button", { name: /EXECUTAR|RODAR|OTIMIZAR|GERAR PREVIS/i }).count();
  assert(fake === 0, "nenhum botão de execução fora da etapa 04");
  await shot(p, "p2a_01_centro_vazio.png");
  // criar cenário
  await p.getByRole("button", { name: "＋ NOVO CENÁRIO" }).click(); await ready(p);
  await p.getByLabel("Nome do cenário *").fill("Operação nominal de inverno");
  await p.getByLabel("Descrição").fill("SOC reduzido; PEMFC inicialmente desligada.");
  await p.getByRole("button", { name: "Criar cenário" }).click(); await ready(p);
  assert(await p.getByText("criado (versão 1, inventário rev. 1)", { exact: false }).isVisible(), "cenário criado e vinculado à revisão 1");
  assert(await p.getByText("Revisão 1", { exact: true }).isVisible(), "card do inventário de referência");
  assert(await p.getByText("Não executável (v1)").isVisible(), "prontidão decidida pelo preflight (cenário incompleto não executável)");
  await shot(p, "p2a_02_centro_cenario.png");
  // inicialização
  await inicializacao(p);
  assert(await p.getByLabel("SOC inicial (%)", { exact: true }).count() === 2, "um controle de SOC por banco instalado");
  assert(await p.getByText("Gerador local", { exact: true }).first().isVisible(), "unidade térmica do inventário listada");
  const b1 = cardOf(p, "Banco de baterias 1");
  await fillNumber(b1, p, "SOC inicial (%)", 10);
  assert(await cardOf(p, "Banco de baterias 1").getByText("Advertência técnica", { exact: false }).first().isVisible(),
         "SOC 10 % fora da restrição: advertência");
  assert(await cardOf(p, "Banco de baterias 1").getByText("Capacidade científica pendente", { exact: false }).first().isVisible(),
         "SOC fora da restrição: incompatibilidade do EMS V1.6 registrada como pendente");
  await fillNumber(cardOf(p, "Banco de baterias 2"), p, "SOC inicial (%)", 10);
  for (const fc of ["Bloco PEMFC A", "Bloco PEMFC B"]) {
    await selectOption(cardOf(p, fc), p, "Estado operativo inicial", "Desligada");
  }
  await fillNumber(cardOf(p, "Bloco PEMFC A"), p, "Potência inicial (kW)", 25);
  assert(await p.getByText("PEMFC declarada desligada não pode entregar 25 kW", { exact: false }).first().isVisible(),
         "PEMFC desligada com 25 kW: erro de coerência");
  await shot(p, "p2a_03_inicializacao_erro.png");
  await p.getByRole("button", { name: "SALVAR CENÁRIO" }).click(); await ready(p);
  assert(await p.getByText("Nada foi gravado", { exact: false }).first().isVisible(), "estado contraditório não é gravado");
  await fillNumber(cardOf(p, "Bloco PEMFC A"), p, "Potência inicial (kW)", 0);
  await selectOption(cardOf(p, "Gerador local"), p, "Estado operativo inicial", "Em operação");
  await fillNumber(cardOf(p, "Gerador local"), p, "Potência inicial (kW)", 40);
  assert(await p.getByText("não modela", { exact: false }).count() === 0, "sem avisos de partida (nenhum estado 'em partida')");
  await p.getByRole("button", { name: "SALVAR CENÁRIO" }).click(); await ready(p);
  assert(await p.getByText("Cenário salvo (versão 2)").isVisible(), "cenário salvo com advertências (versão 2)");
  await shot(p, "p2a_04_inicializacao_salva.png");
  await noErrors(p, "inicialização");
  // duplicar
  await p.getByRole("button", { name: "← Centro de Operação" }).click(); await ready(p);
  await p.getByRole("button", { name: "Duplicar" }).click(); await ready(p);
  assert(await p.getByLabel("Nome do cenário *").inputValue() === "Cópia de Operação nominal de inverno", "nome sugerido da cópia");
  await p.getByRole("button", { name: "Duplicar cenário" }).click(); await ready(p);
  assert(await p.getByText("cópia independente", { exact: false }).first().isVisible(), "cópia independente criada");
  await selectOption(p, p, "Cenário selecionado", "Operação nominal de inverno");
  assert(await p.getByText("Salvo · v2").isVisible(), "cenário original continua na versão 2");
  // duas sessões editando o mesmo cenário
  const ctx2 = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const q = await ctx2.newPage();
  await q.goto(url); await ready(q); await abrir(q);
  await selectOption(q, q, "Cenário selecionado", "Operação nominal de inverno");
  await inicializacao(p); await inicializacao(q);
  await fillNumber(cardOf(p, "Banco de baterias 1"), p, "SOC inicial (%)", 30);
  await fillNumber(cardOf(q, "Banco de baterias 1"), q, "SOC inicial (%)", 70);
  await p.getByRole("button", { name: "SALVAR CENÁRIO" }).click(); await ready(p);
  assert(await p.getByText("Cenário salvo (versão 3)").isVisible(), "sessão 1 salva a versão 3");
  await q.getByRole("button", { name: "SALVAR CENÁRIO" }).click(); await ready(q);
  assert(await q.getByText("alterado por outra sessão", { exact: false }).first().isVisible(), "sessão 2 recebe conflito explícito");
  assert(await cardOf(q, "Banco de baterias 1").getByLabel("SOC inicial (%)", { exact: true }).inputValue() === "70.00", "edição da sessão 2 preservada na tela");
  await shot(q, "p2a_05_conflito_sessao2.png");
  await q.getByRole("button", { name: "Recarregar versão salva (descarta as alterações desta sessão)" }).click(); await ready(q);
  assert(await cardOf(q, "Banco de baterias 1").getByLabel("SOC inicial (%)", { exact: true }).inputValue() === "30.00", "sessão 2 recarrega a versão salva pela sessão 1");
  await ctx2.close();
  // bancadas preservadas — desde o UI-REDESIGN-01 no grupo «Bancadas» da barra lateral (no celular, no Centro de Operação)
  await p.getByRole("button", { name: "← Centro de Operação" }).click(); await ready(p);
  assert(await p.locator('.pt.sb .it[data-id="bancada_wind"]').isVisible(), "bancadas acessíveis pela barra lateral");
  await p.locator(".tb-link", { hasText: "Simulação" }).click(); await ready(p);
  await p.getByText("Configuração aplicada · revisão", { exact: false }).first().waitFor({ timeout: 120000 });
  assert(await p.getByText("Configuração aplicada · revisão", { exact: false }).first().isVisible(), "console V1.6 (Simulação) acessível");
  await noErrors(p, "simulação");
  await p.locator(".tb-link", { hasText: "Centro de Operação" }).click(); await ready(p);
  await p.locator(".tb-doc", { hasText: "Alcance" }).click(); await ready(p);
  assert(await p.locator(".tb-doc.on").count() === 1, "Alcance abre como documentação");
  await p.locator(".tb-switch").click(); await ready(p);
  assert(await p.getByText("GESTOR DE MICRORREDES").first().isVisible(), "TROCAR MICRORREDE volta ao Gestor");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrir(p);
  await selectOption(p, p, "Cenário selecionado", "Operação nominal de inverno");
  assert(await p.getByText("Salvo · v3").isVisible(), "após reiniciar o servidor, o cenário volta na versão 3");
  await inicializacao(p);
  assert(await cardOf(p, "Banco de baterias 1").getByLabel("SOC inicial (%)", { exact: true }).inputValue() === "30.00", "SOC inicial persistido");
  assert(await cardOf(p, "Gerador local").getByLabel("Potência inicial (kW)", { exact: true }).inputValue() === "40.00", "potência térmica persistida");
  await shot(p, "p2a_10_reinicio_inicializacao.png");
  await noErrors(p, "reinício");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 }); current = p;
    await p.goto(url); await ready(p); await abrir(p);
    assert(await overflow(p) <= 1, `tablet ${tag}: Centro de Operação sem rolagem horizontal`);
    await shot(p, `p2a_20_tablet_${tag}_centro.png`);
    await inicializacao(p);
    assert(await overflow(p) <= 1, `tablet ${tag}: Inicialização sem rolagem horizontal`);
    await shot(p, `p2a_21_tablet_${tag}_inicializacao.png`);
    await p.close();
  }
  const d = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 }); current = d;
  await d.goto(url); await ready(d); await abrir(d);
  await shot(d, "p2a_22_escuro_centro.png");
  await inicializacao(d);
  await shot(d, "p2a_23_escuro_inicializacao.png");
  await noErrors(d, "tema escuro");
  await d.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { operar, reinicio, tablet }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: true }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
