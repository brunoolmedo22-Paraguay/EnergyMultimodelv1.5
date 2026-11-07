// Verificação E2E em navegador real (Playwright/Chromium) do PISO 2D-A — Arquivo Científico Portátil.
//
// Preparação:
//   ORIGEM:  python tools/e2e/seed_piso2da.py <DIR_ORIGEM>   (microrrede fictícia; rodada REAL concluída + rodada falha)
//            SEEDS2_DATA_DIR=<DIR_ORIGEM> python -m streamlit run app.py --server.headless true --server.port <porta>
//   DESTINO: SEEDS2_DATA_DIR=<DIR_VAZIO> (instalação LIMPA, sem microrredes), de preferência com o motor sabotado
//            (sitecustomize que faz run_optimizer/build_exchange_package falharem e registrarem a chamada).
// Uso:
//   node tools/e2e/e2e_piso2da_arquivo.js <url> <fase> <pasta_capturas> [custo_origem.txt]
// Fases (o roteiro troca/reinicia o servidor ENTRE as fases):
//   exportar — ORIGEM: Gestor → ABRIR → Centro de Operação (cartão Arquivo Científico) → Arquivo → cenário com versões e
//              rodadas → PREPARAR EXPORTAÇÃO → download real do .seeds2study.zip → ARQUIVAR NESTA INSTALAÇÃO.
//   importar — DESTINO vazio: Gestor (nenhuma microrrede) → ARQUIVO CIENTÍFICO → upload → relatório de verificação →
//              confirmação → estudo na lista → ABRIR ESTUDO → Configuração, Previsões (gráficos), Rodadas (concluída com
//              o MESMO custo da origem; falha com motivo e sem curvas), Integridade (verificação), recarga da página
//              (mesmo estudo e rodada) → reimportação reconhecida como duplicata → Gestor continua sem microrredes.
//   reinicio — DESTINO após reinício do servidor: o mesmo estudo reaberto (link direto e pela lista), mesmo custo.
//   tablet   — estudo em tablet retrato/paisagem (sem rolagem horizontal, gráfico dentro da tela) e tema escuro.
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir, costPath] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const pkgFile = path.join(outDir, "estudo_exportado.seeds2study.zip");
const linkFile = path.join(outDir, "link_estudo.txt");
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }
const cost = () => fs.readFileSync(costPath, "utf8").trim();

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(900);
}
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function overflow(p) { return p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }
async function btn(p, name, exact = false) { await p.getByRole("button", { name, exact }).first().click(); await ready(p); }
async function section(p, name) {
  await p.locator('[data-testid="stRadio"] label').filter({ hasText: name }).first().click(); await ready(p);
}
async function visible(p, text) { return p.getByText(text, { exact: false }).first().isVisible().catch(() => false); }
async function chart(p, titlePart) {
  // o Streamlit só desenha um gráfico Plotly quando ele entra na área visível: rolar até cada um antes de inspecionar
  const n = await p.locator('[data-testid="stPlotlyChart"]').count();
  for (let i = 0; i < n; i++) {
    await p.locator('[data-testid="stPlotlyChart"]').nth(i).scrollIntoViewIfNeeded().catch(() => {});
    await p.waitForTimeout(250);
  }
  await p.waitForTimeout(500);
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
async function consultar(p, nth) {
  const b = p.getByRole("button", { name: "Consultar", exact: true });
  await b.nth(nth).click(); await ready(p);
}

// ------------------------------------------------------------------ ORIGEM
async function exportar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await btn(p, "ABRIR MICRORREDE");
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
  assert(await visible(p, "Exportar, importar e consultar estudos"), "Centro de Operação: cartão do Arquivo Científico");
  assert(await p.getByRole("button", { name: "ABRIR EXECUÇÃO" }).count() === 1, "etapas 01–04 preservadas no painel");
  await shot(p, "p2da_01_centro_cartao.png");
  await btn(p, "ABRIR ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  assert(await visible(p, "Exportar cenário completo"), "seção de exportação da microrrede ativa");
  assert(await visible(p, "1 a 3 (todas)"), "todas as versões (1 a 3) incluídas");
  assert(await visible(p, "1 concluída, 1 falhou"), "rodadas concluída e falha incluídas com os estados originais");
  assert(await visible(p, "não substitui o backup", ), "alcance: não substitui o backup da microrrede");
  await btn(p, "PREPARAR EXPORTAÇÃO");
  assert(await visible(p, "Pacote preparado: 3 versão(ões), 2 rodada(s)"), "pacote preparado (3 versões, 2 rodadas)");
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }),
    p.getByRole("button", { name: "EXPORTAR CENÁRIO COMPLETO" }).first().click()]);
  assert(dl.suggestedFilename().endsWith(".seeds2study.zip"), `nome do arquivo: ${dl.suggestedFilename()}`);
  await dl.saveAs(pkgFile);
  const head = fs.readFileSync(pkgFile).subarray(0, 2).toString("latin1");
  assert(head === "PK" && fs.statSync(pkgFile).size > 10000, `arquivo baixado é um ZIP (${fs.statSync(pkgFile).size} bytes)`);
  await shot(p, "p2da_02_exportar.png");
  await btn(p, "ARQUIVAR NESTA INSTALAÇÃO");
  assert(await visible(p, "Arquivado localmente"), "ARQUIVAR NESTA INSTALAÇÃO: estudo na lista");
  assert(await visible(p, "Origem: esta microrrede"), "estudo local identificado como da microrrede ativa");
  await noErrors(p, "exportar");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

// ------------------------------------------------------------------ DESTINO (instalação limpa)
async function abrirEstudo(p) {
  await btn(p, "ABRIR ESTUDO");
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
}

async function importar(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  assert(await visible(p, "Nenhuma microrrede registrada"), "instalação limpa: nenhuma microrrede");
  await btn(p, "ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  assert(!(await visible(p, "Exportar cenário completo")), "sem microrrede: só importar e consultar");
  assert(await visible(p, "Nenhum estudo arquivado"), "arquivo vazio");
  await p.locator('input[type="file"]').first().setInputFiles(pkgFile); await ready(p);
  await p.getByText("Verificação concluída", { exact: false }).first().waitFor({ timeout: 60000 });
  assert(true, "relatório de verificação exibido");
  for (const t of ["Alta demanda E2E", "Industrial A — E2E 2D-A", "2 (1 concluída, 1 falhou)", "2.0.0-piso2da", "compactado",
    "Não é uma assinatura digital"]) {
    assert(await visible(p, t), `relatório: ${t}`);
  }
  assert(await p.getByRole("button", { name: "CONFIRMAR IMPORTAÇÃO" }).isDisabled(), "importação exige confirmação explícita");
  await shot(p, "p2da_10_inspecao.png");
  await p.getByText("Confirmo a importação deste estudo", { exact: false }).click(); await ready(p);
  await btn(p, "CONFIRMAR IMPORTAÇÃO");
  await p.getByText("Verificado na importação").first().waitFor({ timeout: 60000 });
  assert(await visible(p, "Importado"), "estudo importado na lista (somente leitura)");
  await shot(p, "p2da_11_lista.png");
  await abrirEstudo(p);
  assert(await visible(p, "não executa modelos nem o otimizador"), "consulta histórica declarada");
  fs.writeFileSync(linkFile, p.url());
  await section(p, "Configuração");
  for (const t of ["Inventário de referência", "Estados iniciais", "Estratégia EMS", "GWO", "Janela temporal da missão"]) {
    assert(await visible(p, t), `configuração: ${t}`);
  }
  await shot(p, "p2da_12_configuracao.png");
  await section(p, "Previsões");
  const dem = await chart(p, "Demanda elétrica — perfil do cenário");
  const cli = await chart(p, "Clima — perfil do cenário");
  assert(dem && dem.traces[0].n > 10, `previsão de demanda desenhada (${dem && dem.traces[0].n} pontos)`);
  assert(cli && cli.traces.length >= 2, "previsão de clima desenhada (irradiância e temperatura)");
  await shot(p, "p2da_13_previsoes.png");
  await section(p, "Rodadas e resultados");
  assert(await p.getByRole("button", { name: "Consultar", exact: true }).count() === 2, "duas rodadas no histórico");
  await consultar(p, 0);                                     // mais recente = a que falhou
  assert(await visible(p, "Rodada falhou"), "rodada falha: estado original preservado");
  assert(await visible(p, "otimizador indisponível"), "rodada falha: motivo original");
  assert(await chart(p, "Demanda e potência por fonte") === null, "rodada falha: nenhuma curva inventada");
  await consultar(p, 1);                                     // a concluída
  assert(await kpi(p, "Custo total") === cost(), `custo idêntico à origem (${cost()})`);
  const pw = await chart(p, "Demanda e potência por fonte");
  assert(pw && pw.traces.find((t) => t.name === "Demanda").n === 31, "séries completas (31 passos) da rodada original");
  assert(await chart(p, "Estado de carga da bateria") !== null, "SOC original desenhado");
  assert(await visible(p, "não recalculados"), "valores lidos do estudo, não recalculados");
  await shot(p, "p2da_14_rodada.png");
  await section(p, "Integridade");
  await btn(p, "VERIFICAR INTEGRIDADE AGORA");
  assert(await visible(p, "Integridade confirmada"), "verificação de integridade aprovada");
  await shot(p, "p2da_15_integridade.png");
  await p.reload(); await ready(p);
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
  assert(await kpi(p, "Custo total") === cost(), "recarga da página: mesmo estudo, mesma rodada, mesmo custo");
  await btn(p, "← Arquivo Científico");
  await p.locator('input[type="file"]').first().setInputFiles(pkgFile); await ready(p);
  await p.getByText("Este estudo já está no Arquivo Científico", { exact: false }).first().waitFor({ timeout: 60000 });
  assert(true, "reimportação reconhecida como duplicata (nada duplicado)");
  await p.getByRole("link", { name: "Gestor de microrredes" }).first().click().catch(async () => {
    await p.goto(url.replace(/\/?$/, "/?view=gestor"));
  });
  await ready(p);
  assert(await visible(p, "Nenhuma microrrede registrada"), "importação não criou nem restaurou microrredes");
  await noErrors(p, "importar");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(fs.readFileSync(linkFile, "utf8").trim()); await ready(p);
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 120000 });
  assert(await visible(p, "Alta demanda E2E"), "após reinício: link direto reabre o estudo");
  await p.goto(url); await ready(p);
  await btn(p, "ARQUIVO CIENTÍFICO");
  assert(await p.getByRole("button", { name: "ABRIR ESTUDO" }).count() === 1, "após reinício: exatamente um estudo");
  await abrirEstudo(p);
  await section(p, "Rodadas e resultados");
  await consultar(p, 1);
  assert(await kpi(p, "Custo total") === cost(), "após reinício: mesmo custo, lido do arquivo");
  assert((await chart(p, "Demanda e potência por fonte")).traces.find((t) => t.name === "Demanda").n === 31, "após reinício: séries completas");
  await section(p, "Procedência");
  assert(await visible(p, "Identidade de origem (preservada)"), "procedência: identidade de origem");
  assert(await visible(p, "Industrial A — E2E 2D-A"), "procedência: microrrede de origem");
  await shot(p, "p2da_20_reinicio.png");
  await noErrors(p, "reinício");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await p.close();
}

async function tablet(b) {
  const link = fs.readFileSync(linkFile, "utf8").trim();
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 }); current = p;
    await p.goto(url); await ready(p);
    await btn(p, "ARQUIVO CIENTÍFICO");
    assert(await overflow(p) <= 1, `tablet ${tag}: Arquivo sem rolagem horizontal`);
    await p.goto(link); await ready(p);
    await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
    await section(p, "Rodadas e resultados");
    await consultar(p, 1);
    assert(await overflow(p) <= 1, `tablet ${tag}: estudo sem rolagem horizontal`);
    const c = await chart(p, "Demanda e potência por fonte");
    assert(c && c.box.w > 200 && c.box.x >= 0 && c.box.x + c.box.w <= w + 1, `tablet ${tag}: gráfico dentro da tela (${Math.round(c.box.w)} px)`);
    await p.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
    await shot(p, `p2da_30_tablet_${tag}.png`);
    await p.close();
  }
  const dk = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", deviceScaleFactor: 2 }); current = dk;
  await dk.goto(link); await ready(dk);
  await dk.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
  await section(dk, "Previsões");
  await shot(dk, "p2da_32_escuro_previsoes.png");
  await noErrors(dk, "tema escuro");
  await dk.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { exportar, importar, reinicio, tablet }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: false }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
