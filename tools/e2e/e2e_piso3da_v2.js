// Verificação E2E em navegador real (Playwright/Chromium) do PISO 3D-A — integração operacional do motor V2 (MILP–MPC).
//
// Preparação (diretório VAZIO; duas microrredes fictícias do catálogo, dados sintéticos de teste):
//   python tools/e2e/seed_piso3da.py <DIR_ORIGEM>
//   ORIGEM (com Pyomo/HiGHS):  SEEDS2_DATA_DIR=<DIR_ORIGEM> python -m streamlit run app.py --server.headless true --server.port <porta>
//   DESTINO (instalação LIMPA, SEM solver e com os motores sabotados):
//     PYTHONPATH=tools/e2e/sabotage_v2 SEEDS2_E2E_ENGINE_LOG=<arquivo> SEEDS2_E2E_ROOT=<raiz> SEEDS2_DATA_DIR=<DIR_VAZIO> \
//       python -m streamlit run app.py --server.headless true --server.port <porta>
// Uso:
//   node tools/e2e/e2e_piso3da_v2.js <url> <fase> <pasta_capturas>
// Fases (o roteiro troca/derruba/reinicia o servidor ENTRE as fases):
//   operar   — Gestor (2 microrredes) → ABRIR → Centro → Estratégia: motor V1.6 por omissão → seleção EXPLÍCITA do V2 →
//              declaração EM BRANCO (nenhum parâmetro físico pré-preenchido) → salvar → Execução BLOQUEADA com cada
//              declaração ausente explicada → declarar TUDO pela interface (com procedência) → preflight V2 apto +
//              matriz → EXECUTAR (HiGHS real) → rodada imutável: custo REALIZADO R$ 50,20 (analítico), evidência
//              verificada, gráficos, downloads → recarga (mesma rodada) → exportar o estudo → microrrede B (isolamento:
//              outra rodada, outro custo, históricos separados) → missão longa iniciada; o servidor é derrubado
//              DURANTE essa rodada ("KILL_NOW").
//   reinicio — depois do kill -9 e do reinício: a rodada concluída reabre com o MESMO custo e a evidência verificada
//              (sem reotimizar); a rodada derrubada está "Interrompida", sem resultados; executar volta a ser possível.
//   importar — DESTINO limpo, sem solver, motores sabotados: importar o estudo → rodada V2 com o mesmo custo, evidência
//              verificada e gráficos; recarga pelo link; nenhuma microrrede criada.
//   tablet   — rodada V2 em tablet (retrato) sem rolagem horizontal da página.
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const { expandirCartoes } = require("./catalogo_util");
// Piso 3D-B3: com a Partitura desenhada, a vista clássica da rodada V2 fica RECOLHIDA num expansor identificado. Este
// roteiro continua verificando a vista clássica: apenas a abre antes (navegação) — nenhuma verificação foi alterada.
const abrirClassica = async (p) => {
  const s = p.locator('[data-testid="stExpander"] summary', { hasText: "Vista clássica" }).first();
  try { await s.waitFor({ timeout: 120000 }); } catch (_) { return; }       // sem Partitura a vista clássica já está aberta
  if (!(await s.evaluate((e) => e.parentElement.open))) { await s.click(); await p.waitForTimeout(800); }
};
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
const runFile = path.join(outDir, "rodada_v2.json");
const pkgFile = path.join(outDir, "estudo_v2.seeds2study.zip");
const CUSTO = "R$ 50,20";
const TARIFA = "0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 1.5 1.5 0.5 0.5";
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(700);
}
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function visible(p, text) { return (await p.getByText(text, { exact: false }).count()) > 0; }
async function btn(p, name) { await p.getByRole("button", { name }).first().click(); await ready(p); }
async function abrirMicrorrede(p, nome) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await expandirCartoes(p);
  await p.getByText(nome, { exact: true }).first().waitFor({ timeout: 60000 });
  // cartão = contêiner MAIS INTERNO que tem o nome exato da microrrede e um botão ABRIR MICRORREDE
  const cartao = p.locator('[data-testid="stVerticalBlock"]')
    .filter({ has: p.getByText(nome, { exact: true }) })
    .filter({ has: p.getByRole("button", { name: "ABRIR MICRORREDE" }) }).last();
  await cartao.waitFor({ timeout: 60000 });       // os cartões são desenhados depois do cabeçalho
  assert(await cartao.count() === 1, `microrrede '${nome}' listada no Gestor`);
  await expandirCartoes(cartao); await cartao.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
  assert(await visible(p, nome), `microrrede aberta: ${nome}`);
}
async function cenarioAtual(p) {
  // o selectbox do Streamlit mostra o valor num <input> (não no texto do contêiner)
  const box = p.getByLabel("Cenário selecionado", { exact: true }).first();
  await box.waitFor({ timeout: 60000 });
  const caixa = p.locator('[data-testid="stSelectbox"]').filter({ has: p.getByText("Cenário selecionado", { exact: true }) }).first();
  return (await box.inputValue().catch(() => "")) + " " + (await caixa.innerText().catch(() => ""));
}
async function selecionarCenario(p, nome) {
  if (!(await cenarioAtual(p)).includes(nome)) {
    const box = p.getByLabel("Cenário selecionado", { exact: true }).first();
    const opt = p.getByRole("option").filter({ hasText: nome }).first();
    for (let i = 0; i < 5; i++) {
      await box.click();
      try { await opt.waitFor({ state: "visible", timeout: 2500 }); break; } catch (e) { await p.keyboard.press("Escape"); await p.waitForTimeout(500); }
    }
    await opt.click(); await ready(p);
  }
  assert((await cenarioAtual(p)).includes(nome), `cenário selecionado: ${nome}`);
}
async function num(p, label, value, nth = 0) {
  const box = p.getByLabel(label, { exact: true }).nth(nth);
  await box.fill(String(value)); await box.press("Enter"); await ready(p);
}
async function txt(p, label, value, nth = 0) {
  const box = p.getByLabel(label, { exact: true }).nth(nth);
  await box.fill(String(value)); await box.press("Enter"); await ready(p);
}
async function area(p, label, value) {
  const box = p.getByLabel(label, { exact: true }).first();
  await box.fill(String(value)); await box.press("Control+Enter"); await ready(p);
}
async function sel(p, label, valor, nth = 0) {
  // o selectbox pode fechar a lista se o clique coincidir com uma nova renderização: repetir até a opção ficar visível
  const box = p.getByLabel(label, { exact: true }).nth(nth);
  const opt = p.getByRole("option", { name: new RegExp("^" + valor) }).first();
  for (let i = 0; i < 5; i++) {
    await box.scrollIntoViewIfNeeded(); await box.click();
    try { await opt.waitFor({ state: "visible", timeout: 2500 }); break; } catch (e) { await p.keyboard.press("Escape"); await p.waitForTimeout(500); }
  }
  await opt.click(); await ready(p);
}
async function kpi(p, label) {
  return p.evaluate((l) => {
    const k = [...document.querySelectorAll(".sd-kpi")].find((e) => e.querySelector("small") && e.querySelector("small").textContent === l);
    return k ? k.querySelector("b").textContent : null;
  }, label);
}
async function chart(p, titlePart) {
  return p.evaluate((t) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title &&
      String(el.layout.title.text || "").includes(t));
    if (!g) return null;
    const r = g.getBoundingClientRect();
    return { traces: g._fullData.map((d) => ({ name: d.name, n: (d.y && d.y.length) || 0 })), w: r.width };
  }, titlePart);
}
async function waitRun(p, seconds = 180) {
  let saw = false;
  for (let i = 0; i < seconds * 2; i++) {
    if (await p.getByText("Rodada · imutável").count()) return saw;
    if (await p.getByText(/intervalo \d+ de \d+/).count()) saw = true;
    await p.waitForTimeout(500);
  }
  throw new Error(`FALHA: a rodada V2 não terminou em ${seconds} s`);
}
async function conferirRodada(p, tag, custo) {
  // a leitura inclui a VERIFICAÇÃO da evidência (hashes + reauditoria): esperar os indicadores serem desenhados
  await abrirClassica(p); await p.getByText("Custo REALIZADO").first().waitFor({ timeout: 90000 }); await ready(p);
  assert((await kpi(p, "Custo REALIZADO")) === custo, `${tag}: custo REALIZADO ${custo}`);
  assert(await visible(p, "sem valor futuro"), `${tag}: custo rotulado sem valor futuro`);
  assert(await visible(p, "Motor V2 experimental"), `${tag}: rodada identificada como motor V2 experimental`);
  assert(await visible(p, "Simulação OFFLINE"), `${tag}: alcance declarado (simulação offline, não é validação física)`);
  assert(await visible(p, "✓ Evidência verificada"), `${tag}: evidência verificada na reabertura (sem otimizador)`);
  assert(!(await visible(p, "EVIDÊNCIA COM PROBLEMAS")), `${tag}: nenhuma falha de integridade`);
}

// ------------------------------------------------------------------ ORIGEM
async function operar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrirMicrorrede(p, "Microrrede E2E 3D-A");
  await selecionarCenario(p, "Experimento V2 pela interface");
  assert(await visible(p, "Experimento V2 pela interface"), "cenário versionado da microrrede registrada selecionado");
  await shot(p, "p3da_01_centro.png");

  // ---------------- 03 Estratégia: V1.6 por omissão, seleção EXPLÍCITA do V2, declaração em branco
  await btn(p, "ABRIR ESTRATÉGIA EMS");
  assert(await visible(p, "Motor de execução deste cenário"), "seletor de motor na etapa 03");
  assert(await p.getByRole("radio", { name: /EMS V1\.6/ }).isChecked(), "motor V1.6 selecionado por omissão (nenhuma troca implícita)");
  await p.getByText("EMS V2 EXPERIMENTAL", { exact: false }).first().click(); await ready(p);
  assert(await visible(p, "Estratégia EMS · motor V2 experimental"), "motor V2 selecionado explicitamente");
  assert(await visible(p, "não é controle de equipamentos nem validação física"), "alcance: simulação offline, sem promessa física");
  await btn(p, "CRIAR DECLARAÇÃO DA ESTRATÉGIA V2 (CAMPOS EM BRANCO)");
  assert(await visible(p, "declaração(ões) ausente(s)"), "declaração criada com campos científicos ausentes");
  const etaVazio = await p.getByLabel("Eficiência de carga (barramento → energia interna) [1]", { exact: true }).first().inputValue();
  assert(etaVazio === "", "eficiência da bateria VAZIA (nenhum parâmetro físico pré-preenchido)");
  await shot(p, "p3da_02_declaracao_em_branco.png");
  await btn(p, "SALVAR CENÁRIO");
  assert(await visible(p, "Cenário salvo (versão 3)"), "seleção do motor V2 gravada como versão 3 do cenário");

  // ---------------- 04 Execução BLOQUEADA: cada ausência explicada, nada é executado
  await btn(p, "← Centro de Operação");
  assert(await visible(p, "Não executável (V2)"), "painel: preflight V2 da versão salva não executável");
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "NÃO pode ser executado pelo motor V2"), "preflight V2 bloqueia o cenário incompleto");
  assert(await visible(p, "Potência máxima de carga NO BARRAMENTO [kW] não declarado"), "bloqueio explica o parâmetro ausente da bateria");
  assert(await visible(p, "PCC ausente NÃO é conexão ilimitada"), "bloqueio explica o PCC não declarado");
  assert(await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isDisabled(), "EXECUTAR MISSÃO V2 desabilitado");
  assert(await p.getByRole("button", { name: /EXECUTAR CENÁRIO/ }).count() === 0, "sem botão do motor V1.6 para um cenário V2");
  await shot(p, "p3da_03_preflight_bloqueado.png");

  // ---------------- 03 Estratégia: declarar TUDO pela interface, com procedência
  await btn(p, "← Centro de Operação"); await btn(p, "ABRIR ESTRATÉGIA EMS");
  await num(p, "Passo Δ [min]", 60); await num(p, "Bloco aplicado m [intervalos]", 1);
  await num(p, "Horizonte curto N [intervalos]", 3); await num(p, "Horizonte longo H_L [intervalos]", 10);
  await sel(p, "Procedência (tipo)", "decisao_responsavel", 0);
  await txt(p, "Fonte (documento, pessoa ou 'sintético de ensaio')", "Responsável pelo ensaio E2E 3D-A", 0);
  await sel(p, "Criticidade", "critica"); await sel(p, "Semântica da série", "media_intervalo");
  await txt(p, "Emissão da previsão (UTC)", "2025-12-31T12:00:00+00:00");
  await sel(p, "Realização", "igual_a_previsao");
  await txt(p, "Fonte (documento, pessoa ou 'sintético de ensaio')", "Realização sintética do E2E 3D-A", 1);
  await num(p, "Eficiência de carga (barramento → energia interna) [1]", 1);
  await num(p, "Eficiência de descarga (energia interna → barramento) [1]", 1);
  await num(p, "Potência máxima de carga NO BARRAMENTO [kW]", 5);
  await num(p, "Potência máxima de descarga NO BARRAMENTO [kW]", 10);
  await num(p, "Custo de throughput [R$/kWh]", 0.01);
  await sel(p, "Hipótese de autodescarga", "nao_modelada_alpha_1");
  await sel(p, "Procedência (tipo)", "sintetico", 1);
  await txt(p, "Fonte (documento, pessoa ou 'sintético de ensaio')", "Declaração SINTÉTICA do E2E 3D-A (bateria)", 2);
  await sel(p, "Modo do PCC", "conectado"); await sel(p, "Sentidos permitidos", "somente_importacao");
  await num(p, "Limite de importação [kW]", 50);
  await sel(p, "Disponibilidade do PCC", "disponivel_em_toda_a_missao");
  await sel(p, "Ajuste do PCC na execução", "ajuste_local_algebrico");
  await sel(p, "Liquidação", "igual_a_tarifa_declarada");
  await txt(p, "Emissão das tarifas (UTC)", "2025-12-31T12:00:00+00:00");
  await area(p, "Tarifa de importação [R$/kWh] — um valor por intervalo", TARIFA);
  await txt(p, "Rótulo da tarifa (p. ex. 'SINTÉTICA — não é tarifa real')", "SINTÉTICA — não é tarifa real");
  await txt(p, "Justificativa da declaração do PCC", "PCC sintético do E2E: limite e tarifa declarados para o ensaio");
  await sel(p, "Procedência (tipo)", "sintetico", 2);
  await txt(p, "Fonte (documento, pessoa ou 'sintético de ensaio')", "Declaração SINTÉTICA do E2E 3D-A (PCC)", 3);
  await p.getByLabel("Termos de custo no objetivo", { exact: true }).first().click();
  await p.getByRole("option", { name: /throughput/ }).first().click(); await ready(p);
  await p.keyboard.press("Escape");
  await sel(p, "Degradação (sinal indisponível)", "sem_valor_futuro_rotulado");
  await sel(p, "Termo terminal Φ_L (fim do horizonte longo)", "nenhum_declarado");
  await txt(p, "Justificativa do termo terminal Φ_L", "Fim da missão de ensaio: energia residual avaliada em zero por declaração");
  await txt(p, "Justificativa dos parâmetros do planejador", "Parâmetros numéricos dos ensaios 3C-4");
  assert(await visible(p, "Estratégia V2 completa"), "todas as declarações feitas pela interface, com procedência");
  await shot(p, "p3da_04_estrategia_declarada.png");
  await btn(p, "SALVAR CENÁRIO");
  assert(await visible(p, "Cenário salvo (versão 4)"), "estratégia V2 completa gravada como versão 4");
  await noErrors(p, "estratégia V2");

  // ---------------- 04 Execução: preflight apto, matriz, EXECUTAR
  await btn(p, "← Centro de Operação");
  assert(await visible(p, "Pronto para executar (V2)"), "painel: preflight V2 pronto");
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "Preflight V2 · versão salva v4"), "preflight V2 da versão salva v4");
  assert(await visible(p, "Apto para o motor V2"), "preflight V2 apto");
  assert(await visible(p, "K_M = 12 intervalos de decisão e 13 fronteiras de estado"), "malha N intervalos / N + 1 fronteiras");
  assert(await visible(p, "emissão declarada 2025-12-31T12:00:00+00:00 (anterior a τ₀)"), "previsão causal (emitida antes do início)");
  assert(await visible(p, "ENSAIO rotulado"), "dados sintéticos rotulados (ensaio)");
  assert(await visible(p, "Matriz fonte → transformação → validação → registro → vista"), "matriz de dados disponível");
  await shot(p, "p3da_05_preflight_apto.png");
  const run = p.getByRole("button", { name: "▶ EXECUTAR MISSÃO V2 · VERSÃO 4" });
  assert(await run.isEnabled(), "EXECUTAR MISSÃO V2 habilitado");
  await run.click();
  const saw = await waitRun(p);
  log(saw ? "progresso real da missão observado" : "missão concluiu antes de o progresso ser amostrado");
  await ready(p);
  await conferirRodada(p, "rodada", CUSTO);
  assert((await kpi(p, "Não atendida")) !== null && (await kpi(p, "Importada da rede")) !== null, "déficit e importação exibidos");
  const pot = await chart(p, "Demanda × atendimento por recurso");
  assert(pot && pot.traces.find((t) => t.name === "Demanda realizada").n === 12, "gráfico: demanda realizada (12 intervalos)");
  assert(pot.traces.some((t) => t.name.startsWith("Importação")) && pot.traces.some((t) => t.name.startsWith("Descarga")), "gráfico: composição por recurso");
  const ene = await chart(p, "Energia armazenada nas fronteiras");
  assert(ene && ene.traces[0].n === 13, "gráfico: energia em 13 fronteiras (N + 1)");
  assert(p.url().includes("run="), "URL identifica a rodada (?run=)");
  assert(await p.getByRole("button", { name: "Baixar", exact: true }).count() === 10, "10 dados gravados disponíveis para download");
  const runUid = new URL(p.url()).searchParams.get("run");
  fs.writeFileSync(runFile, JSON.stringify({ run: runUid, custo: CUSTO, link: p.url() }));
  await shot(p, "p3da_06_rodada_v2.png");
  await p.reload(); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  await conferirRodada(p, "recarga", CUSTO);
  await noErrors(p, "rodada V2");

  // ---------------- exportar o estudo (Arquivo Científico)
  await btn(p, "← Execução do cenário");
  assert(await visible(p, "V2 · custo realizado R$ 50,20"), "histórico: rodada V2 rotulada com o custo realizado");
  await btn(p, "← Centro de Operação"); await btn(p, "ABRIR ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  await btn(p, "PREPARAR EXPORTAÇÃO");
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }),
    p.getByRole("button", { name: "EXPORTAR CENÁRIO COMPLETO" }).first().click()]);
  await dl.saveAs(pkgFile);
  assert(fs.readFileSync(pkgFile).subarray(0, 2).toString("latin1") === "PK", `estudo exportado (${fs.statSync(pkgFile).size} bytes)`);

  // ---------------- isolamento: microrrede B
  await btn(p, "TROCAR MICRORREDE");
  await abrirMicrorrede(p, "Microrrede E2E 3D-A · B");
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "Apto para o motor V2"), "microrrede B: preflight V2 apto");
  assert(!(await visible(p, runUid.slice(0, 8))), "microrrede B: a rodada da microrrede A não aparece");
  await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).click();
  await waitRun(p); await ready(p);
  await conferirRodada(p, "microrrede B", "R$ 55,10");
  await shot(p, "p3da_07_microrrede_b.png");

  // ---------------- missão longa na microrrede A: o servidor é derrubado DURANTE a rodada
  await btn(p, "TROCAR MICRORREDE");
  await abrirMicrorrede(p, "Microrrede E2E 3D-A");
  await selecionarCenario(p, "Missão longa V2");
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "K_M = 48 intervalos"), "missão longa (48 intervalos) selecionada");
  await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).click();
  let k = 0;
  for (let i = 0; i < 240 && k < 2; i++) {
    const t = await p.getByText(/intervalo \d+ de 48/).first().textContent().catch(() => null);
    const m = t && t.match(/intervalo (\d+) de 48/);
    if (m) k = Number(m[1]);
    await p.waitForTimeout(250);
  }
  assert(k >= 2 && k < 48, `missão longa em andamento (intervalo ${k} de 48) — progresso real lido do banco`);
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  console.log("KILL_NOW");
  await p.waitForTimeout(4000);
  await ctx.close();
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(info.link.replace(/^https?:\/\/[^/]+/, url.replace(/\/$/, ""))); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 });
  await conferirRodada(p, "após kill -9 + reinício", info.custo);
  await shot(p, "p3da_08_reaberta_apos_reinicio.png");
  await btn(p, "← Execução do cenário");
  await p.goto(url); await ready(p);
  await abrirMicrorrede(p, "Microrrede E2E 3D-A");
  await selecionarCenario(p, "Missão longa V2");
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "Interrompida"), "a rodada derrubada está 'Interrompida' (nunca concluída)");
  assert(await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isEnabled(), "executar volta a ser possível após a recuperação");
  await btn(p, "Abrir");
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  assert(await visible(p, "Nenhum resultado foi gravado como concluído"), "rodada interrompida sem resultados concluídos");
  assert((await kpi(p, "Custo REALIZADO")) === null, "rodada interrompida não apresenta custo de missão");
  await shot(p, "p3da_09_interrompida.png");
  await noErrors(p, "reinício");
}

// ------------------------------------------------------------------ DESTINO (instalação limpa, sem solver)
async function importar(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  assert(await visible(p, "Nenhuma microrrede registrada"), "instalação limpa: nenhuma microrrede");
  await btn(p, "ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  await p.locator('input[type="file"]').first().setInputFiles(pkgFile); await ready(p);
  await p.getByText("Verificação concluída", { exact: false }).first().waitFor({ timeout: 60000 });
  assert(await p.getByRole("button", { name: "CONFIRMAR IMPORTAÇÃO" }).isDisabled(), "importação exige confirmação explícita");
  await p.getByText("Confirmo a importação deste estudo", { exact: false }).click(); await ready(p);
  await btn(p, "CONFIRMAR IMPORTAÇÃO");
  await p.getByText("Verificado na importação").first().waitFor({ timeout: 60000 });
  await btn(p, "ABRIR ESTUDO");
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
  await p.locator('[data-testid="stRadio"] label').filter({ hasText: "Rodadas e resultados" }).first().click(); await ready(p);
  assert(await visible(p, "V2 · custo realizado R$ 50,20"), "estudo arquivado: rodada V2 listada com o custo realizado");
  await btn(p, "Consultar");
  await conferirRodada(p, "estudo arquivado (sem solver)", info.custo);
  const pot = await chart(p, "Demanda × atendimento por recurso");
  assert(pot && pot.traces.find((t) => t.name === "Demanda realizada").n === 12, "estudo arquivado: gráfico dos dados gravados");
  assert(await visible(p, info.run.slice(0, 8)), "mesma rodada (run_uid de origem preservado)");
  await shot(p, "p3da_10_estudo_arquivado.png");
  await p.reload(); await ready(p);
  await conferirRodada(p, "estudo arquivado após recarga", info.custo);
  await p.goto(url); await ready(p);
  assert(await visible(p, "Nenhuma microrrede registrada"), "importar e consultar não criou microrrede");
  await noErrors(p, "importar");
}

async function tablet(b) {
  const ctx = await b.newContext({ viewport: { width: 820, height: 1180 }, deviceScaleFactor: 2, hasTouch: true });
  const p = await ctx.newPage(); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(info.link.replace(/^https?:\/\/[^/]+/, url.replace(/\/$/, ""))); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 });
  await conferirRodada(p, "tablet", info.custo);
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert(ov <= 1, `tablet retrato: sem rolagem horizontal da página (${ov}px)`);
  const pot = await chart(p, "Demanda × atendimento por recurso");
  assert(pot && pot.w <= 820, "tablet: gráfico dentro da tela");
  await shot(p, "p3da_11_tablet.png");
  await ctx.close();
}

(async () => {
  const b = await chromium.launch();
  try {
    await { operar, reinicio, importar, tablet }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: false }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
