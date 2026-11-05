// Verificação E2E em navegador real (Playwright/Chromium) do Piso 1 do SEEDS2.
//
// Uso (servidor já em execução com SEEDS2_DATA_DIR apontando para um diretório VAZIO):
//   node tools/e2e/e2e_piso1_microrrede.js <url> <fase> <pasta_capturas>
// Fases:
//   comissionar  — primeiro acesso, assistente completo usando os componentes (cartão "+", stepper)
//   reabrir      — executar DEPOIS de reiniciar o servidor: deve abrir no Início com a mesma microrrede;
//                  Gestão (inventário/topologia), edição + salvar, simulação EMS real, backup e restauração
//   tablet       — capturas em largura de tablet (retrato e paisagem) e tema escuro
// Requer o pacote "playwright" com Chromium disponível.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: true });
const log = (...a) => console.log(`[${phase}]`, ...a);
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(900);
}
async function selectOption(p, label, text) {
  const box = p.locator('div[data-testid="stSelectbox"]').filter({ hasText: label }).first();
  await box.locator("input").click();
  await p.keyboard.type(text);
  await p.waitForTimeout(250);
  await p.keyboard.press("Enter");
  await ready(p);
}
async function fillNumber(p, label, value) {
  const inp = p.getByLabel(label, { exact: true });
  await inp.fill(String(value));
  await inp.press("Tab");
  await p.waitForTimeout(150);
}
async function noErrors(p, tag) {
  const n = await p.locator('[data-testid="stException"]').count();
  assert(n === 0, `${tag}: nenhuma exceção na página`);
}

async function comissionar(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  assert(await p.getByText("Configure a microrrede desta instalação").isVisible(), "primeiro acesso abre o comissionamento");
  await shot(p, "e2e_01_primeiro_acesso.png");
  await p.getByLabel("Nome da instalação *").fill("Laboratório de Microrredes — Bloco C");
  await selectOption(p, "Natureza da atividade", "Laborat");
  await selectOption(p, "Modo de operação previsto", "Isolada");
  await p.getByRole("button", { name: "Salvar e continuar →" }).click(); await ready(p);
  assert(await p.getByText("Etapa 02 — Inventário energético").isVisible(), "etapa 02 após salvar identificação");
  // cartão "+" do componente de inventário (evento JS → Python)
  await p.locator(".inv-add").first().click(); await ready(p);
  const dlg = p.getByRole("dialog");
  assert(await dlg.isVisible(), "cartão '+' do inventário abre o diálogo");
  await dlg.getByLabel("Nome do equipamento *").fill("Arranjo FV Cobertura");
  await selectOption(p, "Módulo FV (referência)", "CS7L-590");
  await fillNumber(p, "Módulos em série por string [módulos] *", 2);
  await fillNumber(p, "Strings em paralelo [strings] *", 10);
  await fillNumber(p, "Perdas por sujeira [%] *", 0);
  await ready(p);
  assert(await dlg.getByText("Procedência:").first().isVisible(), "referência técnica exibe procedência do catálogo");
  await shot(p, "e2e_02_dialogo_equipamento.png");
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  await p.getByRole("button", { name: "＋ Adicionar equipamento" }).click(); await ready(p);
  await p.getByRole("dialog").getByText("H₂ / PEMFC", { exact: true }).click(); await ready(p);
  await p.getByRole("dialog").getByLabel("Nome do equipamento *").fill("Sistema PEMFC 1");
  await fillNumber(p, "Sistemas/stacks instalados [unidades] *", 2);
  await ready(p);
  await p.getByRole("dialog").getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 2, "dois equipamentos no inventário (componente)");
  await shot(p, "e2e_03_inventario_comissionamento.png");
  // stepper (evento JS) → etapa 03
  await p.locator(".stp-btn").nth(2).click(); await ready(p);
  assert(await p.getByText("Etapa 03 — Configuração elétrica").isVisible(), "stepper navega para a etapa 03");
  await p.getByText("Barramento CC", { exact: true }).click();
  await p.getByText("Sem conexão com a rede", { exact: true }).click();
  await p.getByRole("button", { name: "Salvar configuração elétrica" }).click(); await ready(p);
  assert(await p.locator(".topo-svg").count() === 1, "esquema de topologia renderizado a partir dos dados");
  await shot(p, "e2e_04_topologia.png");
  await p.getByRole("button", { name: "Continuar →" }).click(); await ready(p);
  await p.getByText("Perfil de referência walk-forward (embarcação, 2 h)", { exact: true }).click(); await ready(p);
  await selectOption(p, "Cenário", "Ideal");
  await selectOption(p, "Perfil", "Normal");
  await selectOption(p, "Início", "12:00");
  await p.getByRole("button", { name: "Salvar demanda" }).click(); await ready(p);
  await shot(p, "e2e_05_demanda.png");
  await p.getByRole("button", { name: "Continuar →" }).click(); await ready(p);
  assert(await p.getByText("Verificação técnica").isVisible(), "etapa 05 mostra a verificação técnica");
  await shot(p, "e2e_06_revisao.png");
  await p.getByRole("button", { name: "Ativar microrrede e concluir comissionamento" }).click(); await ready(p);
  assert(await p.getByText("Microrrede administrada por esta instalação").isVisible(), "ativação leva ao Início");
  await noErrors(p, "comissionamento");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function reabrir(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  assert(await p.getByText("Laboratório de Microrredes — Bloco C").first().isVisible(), "após reiniciar o servidor, abre a mesma microrrede");
  assert(await p.getByText("Configure a microrrede desta instalação").count() === 0, "o assistente não se repete");
  await shot(p, "e2e_10_inicio_apos_reinicio.png");
  // barra superior (evento JS) → Gestão
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 2, "Gestão mostra os 2 equipamentos persistidos");
  await shot(p, "e2e_11_gestao_inventario.png");
  await p.locator(".inv-card", { hasText: "Sistema PEMFC 1" }).click(); await ready(p);
  await fillNumber(p, "Sistemas/stacks instalados [unidades] *", 3); await ready(p);
  await p.getByRole("dialog").getByRole("button", { name: "Aplicar" }).click(); await ready(p);
  assert(await p.locator(".tb-save.s-pendente").count() === 1, "indicador mostra edição pendente");
  await shot(p, "e2e_12_edicao_pendente.png");
  await p.getByRole("button", { name: "Salvar alterações" }).click(); await ready(p);
  assert(await p.locator(".tb-save.s-salvo").count() === 1, "indicador volta a 'salvo' após gravar revisão");
  await p.getByText("Topologia", { exact: true }).first().click(); await ready(p);
  await shot(p, "e2e_13_gestao_topologia.png");
  // Simulação: rodada EMS real com a configuração salva
  await p.locator(".tb-link", { hasText: "Simulação" }).click(); await ready(p);
  await p.getByRole("button", { name: "◎  Otimizador" }).click(); await ready(p);
  await shot(p, "e2e_14_simulacao.png");
  await p.getByRole("button", { name: "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO" }).click();
  await p.getByText("RESULTADOS DO OTIMIZADOR", { exact: true }).first().waitFor({ timeout: 180000 }); await ready(p);
  assert(await p.getByText(/Resultado da rodada #1.*microrrede · revisão/).first().isVisible(), "resultado identifica a revisão da microrrede");
  await shot(p, "e2e_15_resultados.png");
  await noErrors(p, "simulação");
  // Backup: exportar e restaurar
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  await p.getByText("Histórico e backups", { exact: true }).first().click(); await ready(p);
  await p.getByRole("button", { name: "Preparar backup da revisão salva" }).click(); await ready(p);
  const [dl] = await Promise.all([p.waitForEvent("download"), p.getByRole("button", { name: "⬇ Baixar backup" }).click()]);
  const bk = path.join(outDir, await dl.suggestedFilename()); await dl.saveAs(bk);
  assert(fs.statSync(bk).size > 500 && bk.endsWith(".seeds2backup.zip"), "backup baixado: " + path.basename(bk));
  await p.locator('[data-testid="stFileUploaderDropzoneInput"]').last().setInputFiles(bk); await ready(p);
  assert(await p.getByText("Backup íntegro e compatível.").isVisible(), "backup inspecionado e aceito");
  await p.getByText("Confirmo substituir a configuração atual", { exact: false }).click(); await ready(p);
  await p.getByRole("button", { name: "Restaurar", exact: true }).click(); await ready(p);
  await shot(p, "e2e_16_historico_backup.png");
  assert(await p.getByText("restauração").first().isVisible(), "histórico registra a revisão de restauração");
  const bad = path.join(outDir, "invalido.seeds2backup.zip"); fs.writeFileSync(bad, "isto nao e um zip");
  await p.locator('[data-testid="stFileUploaderDropzoneInput"]').last().setInputFiles(bad); await ready(p);
  assert(await p.getByText("não é um ZIP válido").isVisible(), "importação inválida é rejeitada com mensagem");
  await noErrors(p, "gestão/backup");
  // Restaurar conteúdo idêntico mantém a mesma impressão digital → o resultado continua válido.
  await p.locator(".tb-link", { hasText: "Resultados" }).click(); await ready(p);
  assert(await p.getByText("Resultado de configuração anterior").count() === 0, "conteúdo restaurado idêntico: resultado continua válido");
  // Alterar a configuração torna o resultado anterior obsoleto (identificado, não reapresentado como atual).
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  await p.getByText("Inventário", { exact: true }).first().click(); await ready(p);
  await p.locator(".inv-card", { hasText: "Arranjo FV Cobertura" }).click(); await ready(p);
  await p.getByRole("dialog").getByText("Habilitado", { exact: true }).click(); await ready(p);
  await p.getByRole("dialog").getByRole("button", { name: "Aplicar" }).click(); await ready(p);
  await p.getByRole("button", { name: "Salvar alterações" }).click(); await ready(p);
  await p.locator(".tb-link", { hasText: "Resultados" }).click(); await ready(p);
  assert(await p.getByText("Resultado de configuração anterior").isVisible(), "resultado antigo identificado como obsoleto após mudança");
  await shot(p, "e2e_17_resultado_obsoleto.png");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto(url); await ready(p);
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(overflow <= 1, `tablet ${tag}: sem rolagem horizontal (${overflow}px)`);
    await shot(p, `e2e_20_tablet_${tag}_inicio.png`);
    await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
    await shot(p, `e2e_21_tablet_${tag}_gestao.png`);
    await p.close();
  }
  const d = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
  await d.goto(url); await ready(d);
  await shot(d, "e2e_22_tema_escuro_inicio.png");
  await d.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(d);
  await shot(d, "e2e_23_tema_escuro_gestao.png");
  await d.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { comissionar, reabrir, tablet }[phase](b);
    log("CONCLUÍDO");
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
