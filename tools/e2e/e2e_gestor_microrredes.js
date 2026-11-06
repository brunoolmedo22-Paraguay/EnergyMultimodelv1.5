// Verificação E2E em navegador real (Playwright/Chromium) do GESTOR DE MICRORREDES.
//
// Uso (servidor em execução com SEEDS2_DATA_DIR VAZIO e SEEDS2_DEV_MODE=1 para permitir a exclusão local):
//   node tools/e2e/e2e_gestor_microrredes.js <url> <fase> <pasta_capturas> <SEEDS2_DATA_DIR>
// Fases:
//   multi     — Gestor vazio → Criar A → configurar A → TROCAR → Criar B → configurar B → abrir A (sem
//               contaminação de B) → exportar ZIP de A pelo Gestor → PDF de B pelo Gestor (PRELIMINAR) →
//               importar o ZIP de A como cópia independente → excluir B (nome exato) → reabrir A
//   reinicio  — executar DEPOIS de reiniciar o servidor: o catálogo persiste; abrir A e a cópia
//   tablet    — Gestor em tablet (retrato/paisagem) e tema escuro, diálogos de importação e exclusão
//   legado    — servidor apontando para um SEEDS2_DATA_DIR com o seeds2.db ANTERIOR ao Gestor: adoção
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir, dataDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: true });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } log("ok —", msg); }
const ENTRIES = () => fs.existsSync(path.join(dataDir, "microgrids"))
  ? fs.readdirSync(path.join(dataDir, "microgrids")).filter((n) => /^[0-9a-f]{32}$/.test(n)) : [];

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
  await p.waitForTimeout(200);
}
const card = (p, name) => p.locator('[class*="st-key-mgc_"]').filter({ hasText: name });
const cards = (p) => p.locator('[class*="st-key-mgc_"]');
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function trocar(p) { await p.locator(".tb-switch").click(); await ready(p); assert(await p.getByText("GESTOR DE MICRORREDES").first().isVisible(), "TROCAR MICRORREDE volta ao Gestor"); }
async function nova(p, name) {
  await p.getByRole("button", { name: "＋ NOVA MICRORREDE" }).click(); await ready(p);
  assert(await p.getByText("Etapa 01 — Identificação e localização").isVisible(), `nova microrrede abre o comissionamento (${name})`);
  assert(await p.getByLabel("Nome da instalação *").inputValue() === "", "formulário da nova microrrede começa vazio");
  await p.getByLabel("Nome da instalação *").fill(name);
  await selectOption(p, p, "Natureza da atividade", "Laborat");
  await selectOption(p, p, "Modo de operação previsto", "Isolada");
  await p.getByRole("button", { name: "Salvar e continuar →" }).click(); await ready(p);
  assert(await p.getByText("Etapa 02 — Inventário energético").isVisible(), `etapa 02 de ${name}`);
  assert(await p.locator(".tb-site").innerText() === `Comissionamento · ${name}`, `barra superior mostra a microrrede ativa (${name})`);
}
async function addPV(p, name) {
  await p.locator(".inv-add").first().click(); await ready(p);
  const dlg = p.getByRole("dialog");
  await dlg.locator('.tp-card[data-kind="pv"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill(name);
  const arr = dlg.locator('div[data-testid="stVerticalBlock"][class*="_arr_arr-"][class*="_card"]').first();
  await selectOption(arr, p, "Módulo FV (referência)", "CS7L-590");
  await fillNumber(arr, p, "Módulos em série *", 2);
  await fillNumber(arr, p, "Strings em paralelo *", 10); await ready(p);
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
}
async function addWind(p, name) {
  await p.locator(".inv-add").first().click(); await ready(p);
  const dlg = p.getByRole("dialog");
  await dlg.locator('.tp-card[data-kind="wind"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill(name);
  await selectOption(dlg, p, "Aerogerador (referência)", "EWT DW61");
  await fillNumber(dlg, p, "Quantidade de aerogeradores [unidades] *", 1); await ready(p);
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
}
async function download(p, scope, prepare, button, outName) {
  await scope.getByRole("button", { name: prepare, exact: true }).click(); await ready(p);
  const [dl] = await Promise.all([p.waitForEvent("download"), p.getByRole("button", { name: button }).first().click()]);
  const f = path.join(outDir, outName || await dl.suggestedFilename()); await dl.saveAs(f);
  return f;
}

async function multi(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });   // servidor recém-iniciado: carga a frio
  assert(await p.getByText("GESTOR DE MICRORREDES").first().isVisible(), "a aplicação começa no Gestor de microrredes");
  assert(await p.getByText("Nenhuma microrrede registrada").isVisible(), "estado vazio no primeiro acesso");
  assert(ENTRIES().length === 0, "nenhuma microrrede criada automaticamente");
  await shot(p, "g01_gestor_vazio.png");
  // A
  await nova(p, "Microrrede A — Solar");
  await addPV(p, "Usina FV A");
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 1, "A: um equipamento");
  await shot(p, "g02_microrrede_A_inventario.png");
  await trocar(p);
  assert(await cards(p).count() === 1, "Gestor lista A");
  // B
  await nova(p, "Microrrede B — Eólica");
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 0, "B começa sem os equipamentos de A");
  await addWind(p, "Aerogerador B");
  await trocar(p);
  assert(await cards(p).count() === 2, "Gestor lista A e B");
  assert(ENTRIES().length === 2, "dois armazenamentos independentes em microgrids/");
  await shot(p, "g03_gestor_duas_microrredes.png");
  // abrir A: sem contaminação de B
  await card(p, "Microrrede A — Solar").getByRole("button", { name: "ABRIR MICRORREDE" }).click(); await ready(p);
  assert(await p.getByText("Etapa 02 — Inventário energético").isVisible(), "A reabre exatamente na etapa onde estava");
  assert(await p.locator(".inv-card", { hasText: "Usina FV A" }).count() === 1, "inventário de A preservado");
  assert(await p.locator(".inv-card", { hasText: "Aerogerador B" }).count() === 0, "nenhum equipamento de B aparece em A");
  await trocar(p);
  // exportar A e PDF de B pelo Gestor, sem abrir
  const zipA = await download(p, card(p, "Microrrede A — Solar"), "ZIP", "⬇ Baixar ZIP");
  assert(zipA.endsWith(".seeds2backup.zip") && /Microrrede_A_Solar_[0-9a-f]{8}_/.test(path.basename(zipA)), "ZIP de A com nome legível + identificador: " + path.basename(zipA));
  const pdfB = await download(p, card(p, "Microrrede B — Eólica"), "PDF", "⬇ Baixar relatório PDF", "relatorio_B.pdf");
  assert(fs.readFileSync(pdfB).subarray(0, 5).toString() === "%PDF-", "PDF de B gerado pelo Gestor");
  assert(await p.locator(".tb-site").innerText() === "Nenhuma microrrede aberta", "exportar/relatório não abrem a microrrede");
  await shot(p, "g04_gestor_exportacoes.png");
  // importar A como cópia independente
  await p.getByRole("button", { name: "IMPORTAR MICRORREDE (ZIP)" }).click(); await ready(p);
  const dlg = p.getByRole("dialog");
  await dlg.locator('[data-testid="stFileUploaderDropzoneInput"]').setInputFiles(zipA); await ready(p);
  assert(await dlg.getByText("Backup íntegro e compatível.").isVisible(), "backup inspecionado");
  assert(await dlg.getByText("Já existe no catálogo", { exact: false }).isVisible(), "identidade coincidente detectada");
  await shot(p, "g05_importacao_conflito.png");
  await dlg.getByText("Importar como cópia independente", { exact: true }).click(); await ready(p);
  await dlg.getByRole("button", { name: "IMPORTAR CÓPIA" }).click(); await ready(p);
  assert(await p.getByText("Cópia independente criada", { exact: false }).isVisible(), "cópia independente criada");
  assert(await cards(p).count() === 3, "Gestor lista A, B e a cópia de A");
  assert(await card(p, "Cópia independente importada").count() === 1, "cópia identificada pela origem");
  await shot(p, "g06_gestor_com_copia.png");
  // excluir B
  await card(p, "Microrrede B — Eólica").getByRole("button", { name: "Excluir" }).click(); await ready(p);
  const del = p.getByRole("dialog");
  assert(await del.getByText("Exclusão definitiva").isVisible(), "diálogo de exclusão com resumo");
  assert(await del.getByRole("button", { name: "EXCLUIR DEFINITIVAMENTE" }).isDisabled(), "botão bloqueado sem o nome");
  await del.getByLabel("Digite o nome exato da microrrede para confirmar").fill("Microrrede A — Solar");
  await del.getByLabel("Digite o nome exato da microrrede para confirmar").press("Tab"); await ready(p);
  assert(await del.getByRole("button", { name: "EXCLUIR DEFINITIVAMENTE" }).isDisabled(), "nome de OUTRA microrrede não libera a exclusão");
  await del.getByLabel("Digite o nome exato da microrrede para confirmar").fill("Microrrede B — Eólica");
  await del.getByLabel("Digite o nome exato da microrrede para confirmar").press("Tab"); await ready(p);
  await shot(p, "g07_exclusao_confirmacao.png");
  await del.getByRole("button", { name: "EXCLUIR DEFINITIVAMENTE" }).click(); await ready(p);
  assert(await p.getByText("excluída definitivamente", { exact: false }).isVisible(), "exclusão confirmada");
  assert(await card(p, "Microrrede B — Eólica").count() === 0 && await cards(p).count() === 2, "B removida; A e cópia permanecem");
  assert(ENTRIES().length === 2, "diretório de B removido do disco; os outros dois intactos");
  await shot(p, "g08_gestor_apos_exclusao.png");
  // reabrir A
  await card(p, "Microrrede A — Solar").filter({ hasText: "Criada no SEEDS2" }).getByRole("button", { name: "ABRIR MICRORREDE" }).click(); await ready(p);
  assert(await p.locator(".inv-card", { hasText: "Usina FV A" }).count() === 1, "A reaberta intacta após excluir B");
  await noErrors(p, "multi");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function reinicio(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await cards(p).nth(1).waitFor({ timeout: 120000 });            // servidor recém-reiniciado: carga a frio
  assert(await cards(p).count() === 2, "após reiniciar o servidor o catálogo persiste (A + cópia)");
  await card(p, "Cópia independente importada").getByRole("button", { name: "ABRIR MICRORREDE" }).click(); await ready(p);
  assert(await p.locator(".inv-card", { hasText: "Usina FV A" }).count() === 1, "cópia contém o inventário de A");
  await trocar(p);
  await card(p, "Criada no SEEDS2").getByRole("button", { name: "ABRIR MICRORREDE" }).click(); await ready(p);
  assert(await p.locator(".tb-site").innerText() === "Comissionamento · Microrrede A — Solar", "A aberta pelo Gestor após reinício");
  await noErrors(p, "reinicio");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 }); current = p;
    await p.goto(url); await ready(p);
    await cards(p).first().waitFor({ timeout: 120000 });
    const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(ov <= 1, `tablet ${tag}: Gestor sem rolagem horizontal (${ov}px)`);
    await shot(p, `g10_tablet_${tag}_gestor.png`);
    await p.close();
  }
  const d = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 }); current = d;
  await d.goto(url); await ready(d);
  await shot(d, "g11_tema_escuro_gestor.png");
  await d.getByRole("button", { name: "IMPORTAR MICRORREDE (ZIP)" }).click(); await ready(d);
  await shot(d, "g12_tema_escuro_importar.png");
  await d.close();
}

async function legado(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  await p.goto(url); await ready(p);
  await cards(p).first().waitFor({ timeout: 120000 });
  assert(await cards(p).count() === 1, "microrrede do armazenamento anterior adotada no catálogo");
  assert(await card(p, "Adotada do armazenamento anterior").count() === 1, "origem 'adotada' identificada");
  assert(await p.getByText("adotado em", { exact: false }).isVisible(), "aviso de adoção com o caminho do arquivo original");
  assert(fs.existsSync(path.join(dataDir, "seeds2.db")), "arquivo anterior mantido");
  await shot(p, "g20_gestor_legado_adotado.png");
  await cards(p).first().getByRole("button", { name: "ABRIR MICRORREDE" }).click(); await ready(p);
  assert(await p.getByText("Microrrede aberta nesta sessão").isVisible(), "microrrede adotada abre no Início");
  await shot(p, "g21_legado_inicio.png");
  await p.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { multi, reinicio, tablet, legado }[phase](b);
    log("CONCLUÍDO");
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: true }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
