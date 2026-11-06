// Verificação E2E em navegador real (Playwright/Chromium) do Piso 1 do SEEDS2 (com o refinamento), percorrido a
// partir do GESTOR DE MICRORREDES (o fluxo de várias microrredes é coberto por e2e_gestor_microrredes.js).
//
// Uso (servidor já em execução com SEEDS2_DATA_DIR apontando para um diretório VAZIO):
//   node tools/e2e/e2e_piso1_microrrede.js <url> <fase> <pasta_capturas>
// Fases:
//   comissionar  — primeiro acesso: cartões da etapa 01 com LOCALIZAÇÃO AUTOMÁTICA (concedida, negada e
//                  indisponível, emuladas no Chromium), catálogo visual de tecnologias, usina FV com dois arranjos,
//                  curva eólica, bateria salva como pendente, esquema lógico do balanço, demanda, exportação ZIP e
//                  relatório PDF (PRELIMINAR) na etapa 05 e ativação
//   reabrir      — executar DEPOIS de reiniciar o servidor: mesma microrrede; edição direta de equipamento existente
//                  (bateria → configuração avançada), condições da rodada (SOC inicial), rodada EMS real, backup,
//                  relatório PDF ativado, restauração e resultado obsoleto
//   tablet       — capturas em largura de tablet (retrato e paisagem) e tema escuro
// Requer o pacote "playwright" com Chromium disponível. Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: true });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;   // página ativa (captura de diagnóstico em caso de falha)
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } log("ok —", msg); }
const GEO = { latitude: -25.4434, longitude: -54.5861, accuracy: 28 };   // coordenada emulada (não é dado de instalação)

async function novaMicrorrede(p) {                // Gestor → "＋ NOVA MICRORREDE" → comissionamento
  await p.getByRole("button", { name: "＋ NOVA MICRORREDE" }).click(); await ready(p);
}
async function abrirUnica(p) {                    // Gestor → "ABRIR MICRORREDE" na (única) tarjeta
  await p.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
}
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
async function noErrors(p, tag) {
  const n = await p.locator('[data-testid="stException"]').count();
  assert(n === 0, `${tag}: nenhuma exceção na página`);
}
async function download(p, prepare, button, outName) {
  await p.getByRole("button", { name: prepare }).click(); await ready(p);
  const [dl] = await Promise.all([p.waitForEvent("download"), p.getByRole("button", { name: button }).first().click()]);
  const f = path.join(outDir, outName || await dl.suggestedFilename()); await dl.saveAs(f);
  return f;
}
const arrayCards = (dlg) => dlg.locator('div[data-testid="stVerticalBlock"][class*="_arr_arr-"][class*="_card"]');

// Etapa 01: os três desfechos da geolocalização, cada um numa página/contexto próprio.
async function geoOutcomes(b) {
  // negada: contexto sem permissão concedida (o Chromium headless nega)
  const c1 = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p1 = await c1.newPage(); await p1.goto(url); await ready(p1); await novaMicrorrede(p1);
  await p1.locator(".geo-btn").click(); await ready(p1);
  assert(await p1.getByText("Permissão de localização negada", { exact: false }).first().isVisible(), "geolocalização negada é informada");
  assert(await p1.getByLabel("Latitude [°]").inputValue() === "", "negada: nenhuma coordenada é preenchida");
  await c1.close();
  // indisponível: o navegador devolve POSITION_UNAVAILABLE
  const c2 = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c2.addInitScript(() => {
    navigator.geolocation.getCurrentPosition = (ok, err) => setTimeout(() => err({ code: 2, message: "unavailable" }), 50);
  });
  const p2 = await c2.newPage(); await p2.goto(url); await ready(p2); await novaMicrorrede(p2);
  await p2.locator(".geo-btn").click(); await ready(p2);
  assert(await p2.getByText("não conseguiu determinar a posição", { exact: false }).first().isVisible(), "posição indisponível é informada");
  await c2.close();
}

async function comissionar(b) {
  await geoOutcomes(b);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true,
    permissions: ["geolocation"], geolocation: GEO });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  let geoCalls = 0;
  await p.exposeFunction("__geoCall", () => { geoCalls += 1; });
  await p.addInitScript(() => {
    const g = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
    navigator.geolocation.getCurrentPosition = (...a) => { window.__geoCall(); return g(...a); };
    navigator.geolocation.watchPosition = () => { throw new Error("watchPosition não deve ser usado"); };
  });
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 60000 }).catch(() => {});
  assert(await p.getByText("Nenhuma microrrede registrada").isVisible(), "primeiro acesso abre o Gestor vazio");
  await novaMicrorrede(p);
  assert(await p.getByText("Configure a nova microrrede").isVisible(), "＋ NOVA MICRORREDE abre o comissionamento");
  assert(geoCalls === 0, "nenhuma leitura de posição sem clique do usuário");
  // Cartão 1 — identificação
  await p.getByLabel("Nome da instalação *").fill("Laboratório de Microrredes — Bloco C");
  await selectOption(p, p, "Natureza da atividade", "Laborat");
  await selectOption(p, p, "Modo de operação previsto", "Conectada à rede");
  // Cartão 2 — localização automática (concedida)
  await p.locator(".geo-btn").click(); await ready(p);
  assert(geoCalls === 1, "uma única leitura de posição após o clique");
  assert(await p.getByText("precisão estimada ±28 m", { exact: false }).first().isVisible(), "precisão estimada exibida");
  assert(Math.abs(parseFloat(await p.getByLabel("Latitude [°]").inputValue()) - GEO.latitude) < 1e-5, "latitude preenchida pelo navegador");
  assert(await p.getByLabel("Cidade / localidade").inputValue() === "", "cidade NÃO é inferida das coordenadas");
  assert(await p.getByLabel("Endereço ou descrição do local").inputValue() === "", "endereço NÃO é inferido");
  await p.getByLabel("Cidade / localidade").fill("Foz do Iguaçu");                       // edição manual
  await p.getByLabel("Longitude [°]").fill("-54.5870"); await p.getByLabel("Longitude [°]").press("Tab");
  await p.waitForTimeout(300);
  await shot(p, "e2e_01_etapa01_cartoes_geolocalizacao.png");
  await p.getByRole("button", { name: "Salvar e continuar →" }).click(); await ready(p);
  assert(await p.getByText("Etapa 02 — Inventário energético").isVisible(), "etapa 02 após salvar identificação");

  // Etapa 02 — catálogo visual de tecnologias
  await p.locator(".inv-add").first().click(); await ready(p);
  let dlg = p.getByRole("dialog");
  assert(await dlg.locator(".tp-card").count() === 5, "catálogo de tecnologias com 5 cartões");
  await shot(p, "e2e_02_catalogo_tecnologias.png");
  await dlg.locator('.tp-card[data-kind="wind"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").waitFor({ timeout: 30000 });   // editor completamente desenhado
  await dlg.getByRole("button", { name: "← Voltar às tecnologias" }).click(); await ready(p);
  await dlg.locator(".tp-card").first().waitFor({ timeout: 30000 }).catch(() => {});
  assert(await dlg.locator(".tp-card").count() === 5, "'Voltar às tecnologias' retorna ao catálogo sem registrar");
  // Usina FV com dois arranjos (módulos identificados + potência declarada)
  await dlg.locator('.tp-card[data-kind="pv"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill("Usina FV Cobertura");
  let arr = arrayCards(dlg).nth(0);
  await selectOption(arr, p, "Módulo FV (referência)", "CS7L-590");
  await fillNumber(arr, p, "Módulos em série *", 2);
  await fillNumber(arr, p, "Strings em paralelo *", 10); await ready(p);
  assert(await arr.getByText("11,80 kWp").first().isVisible(), "P STC do arranjo homogêneo (20 × 590 Wp)");
  await dlg.getByRole("button", { name: "＋ Adicionar arranjo" }).click(); await ready(p);
  dlg = p.getByRole("dialog");
  arr = arrayCards(dlg).nth(1);
  await arr.getByText("Potência nominal declarada", { exact: true }).click(); await ready(p);
  await fillNumber(arr, p, "Potência nominal declarada [kWp] *", 3.5);
  await arr.getByLabel("Procedência (placa, projeto, as-built…)").fill("Projeto as-built (exemplo E2E)");
  await arr.getByLabel("Procedência (placa, projeto, as-built…)").press("Tab"); await ready(p);
  assert(await dlg.getByText("15,30 kWp").first().isVisible(), "potência total da usina = calculada + declarada");
  await shot(p, "e2e_03_usina_fv_arranjos.png");
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  // Eólica: curva do catálogo
  await p.getByRole("button", { name: "＋ Adicionar equipamento" }).click(); await ready(p);
  dlg = p.getByRole("dialog");
  await dlg.locator('.tp-card[data-kind="wind"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill("Aerogerador 01");
  await selectOption(dlg, p, "Aerogerador (referência)", "EWT DW61");
  await fillNumber(dlg, p, "Quantidade de aerogeradores [unidades] *", 1); await ready(p);
  assert(await dlg.locator(".js-plotly-plot").count() === 1, "curva de potência (Plotly) exibida");
  assert(await dlg.getByText("Pontos tabulados do catálogo").first().isVisible(), "pontos tabulados distinguidos na legenda");
  assert(await dlg.getByText("digitaliz", { exact: false }).first().isVisible(), "curva digitalizada identificada");
  await shot(p, "e2e_04_eolica_curva.png");
  await dlg.locator(".js-plotly-plot").scrollIntoViewIfNeeded(); await p.waitForTimeout(400);
  await dlg.locator('[data-testid="stPlotlyChart"]').screenshot({ path: path.join(outDir, "e2e_04b_eolica_curva_grafico.png") });
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  // Bateria somente com datasheet → confirmação de pendência
  await p.getByRole("button", { name: "＋ Adicionar equipamento" }).click(); await ready(p);
  dlg = p.getByRole("dialog");
  await dlg.locator('.tp-card[data-kind="battery"]').click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill("Banco de baterias 01");
  await fillNumber(dlg, p, "Energia nominal [kWh]", 100);
  await fillNumber(dlg, p, "Tensão nominal [V]", 660); await ready(p);
  assert(await dlg.getByText("estimativa", { exact: false }).first().isVisible(), "capacidade derivada como estimativa");
  assert(await dlg.getByLabel("SOC mínimo operacional [%] *").inputValue() === "20", "SOC mínimo padrão 20 %");
  assert(await dlg.getByLabel("SOC máximo operacional [%] *").inputValue() === "80", "SOC máximo padrão 80 %");
  assert(await dlg.getByText("SOC inicial", { exact: false }).first().isVisible(), "aviso: SOC inicial é condição da rodada");
  await shot(p, "e2e_05_bateria_datasheet.png");
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  assert(await dlg.getByText("Equipamento com configuração pendente").isVisible(), "confirmação de equipamento incompleto");
  await shot(p, "e2e_06_confirmacao_pendente.png");
  await dlg.getByRole("button", { name: "Voltar à configuração" }).click(); await ready(p);
  assert(await dlg.getByLabel("Energia nominal [kWh]").inputValue() === "100", "'Voltar à configuração' preserva os dados");
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  await dlg.getByRole("button", { name: "Salvar como pendente" }).click(); await ready(p);
  // PEMFC (catálogo) para a rodada EMS
  await p.getByRole("button", { name: "＋ Adicionar equipamento" }).click(); await ready(p);
  dlg = p.getByRole("dialog");
  await dlg.locator('.tp-card[data-kind="pemfc"]').click(); await ready(p);
  assert(await dlg.getByRole("link", { name: "CRIAR DISPOSITIVO NO PEMFC MODELLAB ↗" }).count() === 0, "catálogo SEEDS2 é a origem padrão");
  await dlg.getByText("Dispositivo importado do PEMFC ModelLab", { exact: true }).first().click(); await ready(p);
  const link = dlg.getByRole("link", { name: "CRIAR DISPOSITIVO NO PEMFC MODELLAB ↗" });
  assert(await link.getAttribute("href") === "https://pemfc-modelab.streamlit.app/?view=home", "link do ModelLab correto");
  assert(await link.getAttribute("target") === "_blank", "ModelLab abre em nova aba");
  await shot(p, "e2e_07_pemfc_modellab.png");
  await dlg.getByText("Sistema PEMFC equivalente", { exact: false }).first().click(); await ready(p);
  await dlg.getByLabel("Nome do equipamento *").fill("Sistema PEMFC 1");
  await fillNumber(dlg, p, "Sistemas/stacks instalados [unidades] *", 2); await ready(p);
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 4, "quatro equipamentos no inventário");
  await shot(p, "e2e_08_inventario.png");

  // Etapa 03 — esquema lógico do balanço
  await p.locator(".stp-btn").nth(2).click(); await ready(p);
  assert(await p.getByText("Etapa 03 — Esquema lógico do balanço energético").isVisible(), "stepper navega para a etapa 03");
  assert(await p.locator(".bal-core").count() === 1, "balanço agregado renderizado");
  assert(await p.locator(".topo-svg").count() === 0, "sem topologia elétrica fictícia");
  await p.getByText("Conectada à rede de distribuição", { exact: true }).click(); await ready(p);
  assert(await p.getByText("equivale a uma compra física", { exact: false }).first().isVisible(), "aviso: déficit ≠ compra da rede");
  assert(await p.locator(".bal-grid").count() === 1, "rede declarada aparece fora do balanço modelado");
  await shot(p, "e2e_09_balanco_logico.png");
  await p.getByRole("button", { name: "Continuar →" }).click(); await ready(p);
  // Etapa 04 — demanda
  await p.getByText("Perfil de referência walk-forward (embarcação, 2 h)", { exact: true }).click(); await ready(p);
  await selectOption(p, p, "Cenário", "Ideal");
  await selectOption(p, p, "Perfil", "Normal");
  await selectOption(p, p, "Início", "12:00");
  await p.getByRole("button", { name: "Salvar demanda" }).click(); await ready(p);
  await shot(p, "e2e_10_parametros_demanda.png");
  await p.getByRole("button", { name: "Continuar →" }).click(); await ready(p);
  // Etapa 05 — revisão, exportações e ativação
  assert(await p.getByText("Verificação técnica").isVisible(), "etapa 05 mostra a verificação técnica");
  const zip = await download(p, "EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)", "⬇ Baixar ZIP");
  assert(zip.endsWith(".seeds2backup.zip") && fs.statSync(zip).size > 500, "ZIP exportado: " + path.basename(zip));
  const pdf = await download(p, "GERAR RELATÓRIO TÉCNICO (PDF)", "⬇ Baixar PDF", "relatorio_preliminar.pdf");
  assert(fs.readFileSync(pdf).subarray(0, 5).toString() === "%PDF-", "PDF preliminar baixado");
  await shot(p, "e2e_11_revisao_exportacoes.png");
  await p.getByRole("button", { name: "Ativar microrrede e concluir comissionamento" }).click(); await ready(p);
  assert(await p.getByText("Microrrede aberta nesta sessão").isVisible(), "ativação leva ao Início");
  assert(geoCalls === 1, "nenhuma leitura adicional de posição (sem rastreamento)");
  await noErrors(p, "comissionamento");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function reabrir(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  assert(await p.getByText("GESTOR DE MICRORREDES").first().isVisible(), "após reiniciar, a sessão nova começa no Gestor");
  await abrirUnica(p);
  await p.locator(".tb-link").first().waitFor({ timeout: 60000 }).catch(() => {});
  assert(await p.getByText("Laboratório de Microrredes — Bloco C").first().isVisible(), "após reiniciar o servidor, abre a mesma microrrede");
  assert(await p.getByText("Configure a nova microrrede").count() === 0, "o assistente não se repete");
  await shot(p, "e2e_20_inicio_apos_reinicio.png");
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  assert(await p.locator(".inv-card:not(.inv-add)").count() === 4, "Gestão mostra os 4 equipamentos persistidos");
  // edição de equipamento existente abre o editor diretamente
  await p.locator(".inv-card", { hasText: "Banco de baterias 01" }).click(); await ready(p);
  const dlg = p.getByRole("dialog");
  assert(await dlg.locator(".tp-card").count() === 0, "edição abre o editor (sem catálogo)");
  assert(await dlg.getByLabel("Energia nominal [kWh]").inputValue() === "100", "dados do datasheet persistidos");
  if (!(await dlg.getByLabel("Células em série (Ns) [células] *").isVisible().catch(() => false))) {
    await dlg.getByText("Configuração avançada do modelo científico").click(); await ready(p);
  }
  await selectOption(dlg, p, "Modelo e célula de referência", "Li-Ion · 3,3 V");
  await fillNumber(dlg, p, "Células em série (Ns) [células] *", 200);
  await fillNumber(dlg, p, "Ramos em paralelo (Np) [ramos] *", 66); await ready(p);
  await fillNumber(dlg, p, "Taxa máxima de carga [C]", 0.5);
  await fillNumber(dlg, p, "Taxa máxima de descarga [C]", 1); await ready(p);
  assert(await dlg.getByText("Parametrizado para o modelo científico existente").isVisible(), "banco parametrizado para o modelo");
  await shot(p, "e2e_21_bateria_avancada.png");
  await dlg.getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  assert(await p.locator(".tb-save.s-pendente").count() === 1, "indicador mostra edição pendente");
  await p.getByRole("button", { name: "Salvar alterações" }).click(); await ready(p);
  assert(await p.locator(".tb-save.s-salvo").count() === 1, "indicador volta a 'salvo' após gravar revisão");
  await p.getByText("Balanço energético", { exact: true }).first().click(); await ready(p);
  await shot(p, "e2e_22_gestao_balanco.png");
  // Simulação: condições da rodada + rodada EMS real
  await p.locator(".tb-link", { hasText: "Simulação" }).click(); await ready(p);
  await p.getByRole("button", { name: "◎  Otimizador" }).click(); await ready(p);
  await fillNumber(p, p, "Banco de baterias 01 · SOC inicial [%]", 60);
  await p.getByRole("button", { name: "Salvar condições da rodada" }).click(); await ready(p);
  if (!(await p.getByText("Representado no EMS").first().isVisible().catch(() => false))) {   // expansor pode já estar aberto
    await p.getByText(/^Configuração aplicada · revisão/).first().click(); await ready(p);
  }
  assert(await p.getByText("Representado no EMS").first().isVisible(), "painel mostra a configuração aplicada ao EMS");
  const ack = p.getByText("Confirmo executar esta rodada SEM", { exact: false });
  if (await ack.count()) { await ack.first().click(); await ready(p); log("exclusões confirmadas (arranjo FV declarado sem módulo)"); }
  if (!(await p.getByText("Representado no EMS").first().isVisible().catch(() => false))) {
    await p.getByText(/^Configuração aplicada · revisão/).first().click(); await ready(p);
  }
  await shot(p, "e2e_23_simulacao.png");
  await p.getByRole("button", { name: "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO" }).click();
  await p.getByText("RESULTADOS DO OTIMIZADOR", { exact: true }).first().waitFor({ timeout: 300000 }); await ready(p);
  assert(await p.getByText(/Resultado da rodada #1.*microrrede [0-9a-f]{8}… · revisão/).first().isVisible(), "resultado identifica a revisão da microrrede");
  await shot(p, "e2e_24_resultados.png");
  await noErrors(p, "simulação");
  // Relatório, histórico e backups
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  await p.getByText("Relatório, histórico e backups", { exact: true }).first().click(); await ready(p);
  const pdf = await download(p, "GERAR RELATÓRIO TÉCNICO (PDF)", "⬇ Baixar PDF", "relatorio_ativado.pdf");
  assert(fs.readFileSync(pdf).subarray(0, 5).toString() === "%PDF-", "PDF da configuração ativada baixado");
  const bk = await download(p, "Preparar backup da revisão salva", "⬇ Baixar backup");
  assert(fs.statSync(bk).size > 500 && bk.endsWith(".seeds2backup.zip"), "backup baixado: " + path.basename(bk));
  await p.locator('[data-testid="stFileUploaderDropzoneInput"]').last().setInputFiles(bk); await ready(p);
  assert(await p.getByText("Backup íntegro e compatível.").isVisible(), "backup inspecionado e aceito");
  await p.getByText("Confirmo substituir a configuração atual", { exact: false }).click(); await ready(p);
  await p.getByRole("button", { name: "Restaurar", exact: true }).click(); await ready(p);
  await shot(p, "e2e_25_historico_backup.png");
  assert(await p.getByText("restauração").first().isVisible(), "histórico registra a revisão de restauração");
  const bad = path.join(outDir, "invalido.seeds2backup.zip"); fs.writeFileSync(bad, "isto nao e um zip");
  await p.locator('[data-testid="stFileUploaderDropzoneInput"]').last().setInputFiles(bad); await ready(p);
  assert(await p.getByText("não é um ZIP válido").isVisible(), "importação inválida é rejeitada com mensagem");
  await noErrors(p, "gestão/backup");
  await p.locator(".tb-link", { hasText: "Resultados" }).click(); await ready(p);
  assert(await p.getByText("Resultado de configuração anterior").count() === 0, "conteúdo restaurado idêntico: resultado continua válido");
  // Alterar a configuração torna o resultado anterior obsoleto.
  await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
  await p.getByText("Inventário", { exact: true }).first().click(); await ready(p);
  await p.locator(".inv-card", { hasText: "Aerogerador 01" }).click(); await ready(p);
  await p.getByRole("dialog").getByText("Habilitado", { exact: true }).click(); await ready(p);
  await p.getByRole("dialog").getByRole("button", { name: "Salvar equipamento" }).click(); await ready(p);
  await p.getByRole("button", { name: "Salvar alterações" }).click(); await ready(p);
  await p.locator(".tb-link", { hasText: "Resultados" }).click(); await ready(p);
  assert(await p.getByText("Resultado de configuração anterior").isVisible(), "resultado antigo identificado como obsoleto após mudança");
  await shot(p, "e2e_26_resultado_obsoleto.png");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function tablet(b) {
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
    await p.goto(url); await ready(p); await abrirUnica(p);
    await p.locator(".tb-link").first().waitFor({ timeout: 60000 });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(overflow <= 1, `tablet ${tag}: sem rolagem horizontal (${overflow}px)`);
    await shot(p, `e2e_30_tablet_${tag}_inicio.png`);
    await p.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(p);
    await shot(p, `e2e_31_tablet_${tag}_gestao.png`);
    await p.getByText("Balanço energético", { exact: true }).first().click(); await ready(p);
    const ov2 = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(ov2 <= 1, `tablet ${tag}: balanço sem rolagem horizontal (${ov2}px)`);
    await shot(p, `e2e_32_tablet_${tag}_balanco.png`);
    await p.close();
  }
  const d = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 });
  await d.goto(url); await ready(d); await abrirUnica(d);
  await d.locator(".tb-link").first().waitFor({ timeout: 60000 });
  await shot(d, "e2e_33_tema_escuro_inicio.png");
  await d.locator(".tb-link", { hasText: "Gestão da Microrrede" }).click(); await ready(d);
  await shot(d, "e2e_34_tema_escuro_gestao.png");
  await d.getByText("Balanço energético", { exact: true }).first().click(); await ready(d);
  await shot(d, "e2e_35_tema_escuro_balanco.png");
  await d.locator(".inv-card", { hasText: "Usina FV Cobertura" }).count();
  await d.getByText("Inventário", { exact: true }).first().click(); await ready(d);
  await d.locator(".inv-card", { hasText: "Usina FV Cobertura" }).click(); await ready(d);
  await shot(d, "e2e_36_tema_escuro_usina_fv.png");
  await d.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { comissionar, reabrir, tablet }[phase](b);
    log("CONCLUÍDO");
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: true }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
