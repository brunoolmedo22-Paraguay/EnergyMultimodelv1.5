// Real application controls, real calculations, downloads and rendered charts.
// node ... <url> <bench> <output>; bench: solar/wind/thermal/battery/h2/mix
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path');
const [url, bench, out] = process.argv.slice(2);
fs.mkdirSync(out, {recursive:true});
let page, checks=0;
const receipts=[];
function check(ok, msg) {if(!ok) throw Error(msg); checks++; console.log('PASS '+msg);}
async function ready() {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);
  await page.waitForFunction(()=>!document.querySelector('[data-testid="stStatusWidget"]'),null,{timeout:180000});
  await page.waitForTimeout(500);
  check(await page.locator('[data-testid="stException"]').count()===0,'no unhandled Python exception');
}
async function button(name,scope=page) {await scope.getByRole('button',{name,exact:true}).click();await ready();}
async function nav(name) {await button(name,page.locator('[data-testid="stSidebar"]'));}
async function charts() {
  await page.waitForFunction(()=>[...document.querySelectorAll('.js-plotly-plot')].some(g=>g._fullData?.some(d=>d.y?.length)),null,{timeout:60000});
  const data=await page.evaluate(()=>[...document.querySelectorAll('.js-plotly-plot')].filter(g=>g._fullData).map(g=>({title:g.layout?.title?.text,
    axes:Object.keys(g._fullLayout).filter(k=>/^yaxis\d*$/.test(k)).map(k=>g._fullLayout[k].title?.text),
    traces:g._fullData.map(d=>({name:d.name,n:d.y?.length||0,finite:Array.from(d.y||[]).filter(v=>Number.isFinite(v)).length}))})));
  check(data.some(g=>g.traces.some(t=>t.finite>1)),'rendered numeric chart traces');receipts.push({charts:data});
}
async function shot(tag) {
  await page.screenshot({path:path.join(out,`${bench}-${tag}.png`),fullPage:false});
  if(tag.includes('result')||tag.includes('comparison')){
    await page.setViewportSize({width:820,height:1180});await page.waitForTimeout(1000);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'tablet: no page horizontal overflow');
    await page.screenshot({path:path.join(out,`${bench}-${tag}-tablet.png`),fullPage:false});
    await page.setViewportSize({width:1440,height:1000});await ready();
  }
}
async function download(name,suffix='') {
  const [d]=await Promise.all([page.waitForEvent('download',{timeout:60000}),page.getByRole('button',{name,exact:true}).click()]);
  const target=path.join(out,bench+suffix+'-'+d.suggestedFilename());await d.saveAs(target);
  const text=fs.readFileSync(target,'utf8');check(text.split('\n').length>3,'downloaded result series '+d.suggestedFilename());
  receipts.push({download:path.basename(target),bytes:Buffer.byteLength(text)});await ready();
}
async function openBench() {
  if(bench==='mix') return;
  await page.getByRole('button',{name:'ABRIR MICRORREDE',exact:true}).first().click();await ready();
  await page.getByText('Ferramentas V1.6 — bancadas individuais dos modelos',{exact:true}).click();await ready();
  await button({'solar':'ABRIR SOLAR','wind':'ABRIR EÓLICA','thermal':'ABRIR TÉRMICA','battery':'ABRIR BATERIA','h2':'ABRIR H₂ / PEMFC'}[bench]);
}
async function invalidUpload(radio,fileLabel,csv,runButton) {
  await page.getByText(radio,{exact:true}).click();await ready();
  await page.locator('[data-testid="stFileUploader"]').filter({hasText:fileLabel}).locator('input[type="file"]').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});await ready();
  if(runButton && await page.getByRole('button',{name:runButton,exact:true}).count()){
    const b=page.getByRole('button',{name:runButton,exact:true});if(await b.isEnabled()){await b.click();await ready();}
  }
  const alerts=await page.locator('[data-testid="stAlert"]').allTextContents();
  check(alerts.some(t=>/inválid|invalid|Não foi possível|Falha|obrigat|numéric|timestamp|finito|Erro|Prepare/i.test(t)), 'invalid input rejected with visible message');
  receipts.push({invalidAlerts:alerts});await shot('invalid');
}
async function solar() {
  await nav('Entrada');await page.getByText('Perfil sintético',{exact:true}).click();await ready();
  await button('▶ RODAR MODELOS');await nav('Comparação');await charts();await shot('comparison-three-models');
  await nav('Exportação');await download('⬇️ BAIXAR CSV');
  await nav('Entrada');await page.getByText('Perfil sintético',{exact:true}).click();await ready();const t=page.getByLabel('Temperatura máxima [°C]',{exact:true});await t.fill('-100');await t.press('Tab');await ready();await button('▶ RODAR MODELOS');
  check(await page.getByText('A temperatura máxima deve ser maior ou igual à mínima.',{exact:true}).isVisible(),'invalid temperature bounds rejected');await shot('invalid');
}
async function wind() {
  await nav('Simulação');await page.getByText('Exemplo sintético · Ceará',{exact:true}).click();await ready();await button('▶ CALCULAR PERFIL EÓLICO');await charts();await shot('result');
  await nav('Exportação');await download('⬇️ BAIXAR RESULTADO CSV');await nav('Simulação');
  await invalidUpload('Carregar CSV','Arquivo CSV','timestamp,wind_speed_mps\n2026-01-01 00:00:00,-2\n2026-01-01 00:10:00,-1\n','▶ CALCULAR PERFIL EÓLICO');
}
async function thermal() {
  await nav('Simulação');await button('▶ CALCULAR MODELO TÉRMICO');await charts();await shot('result');await nav('Exportação');await download('⬇️ BAIXAR RESULTADO CSV');
  await nav('Simulação');await invalidUpload('Carregar CSV','CSV','timestamp,power_mw\ninvalid,1\ninvalid,2\n','▶ CALCULAR MODELO TÉRMICO');
}
async function battery() {
  await nav('Simulação');await button('▶ SIMULAR BATERIA');await charts();await shot('tremblay-result');await nav('Exportação');await download('⬇️ BAIXAR RESULTADO CSV','-tremblay');
  await button('Circuito equivalente · 2 RC',page.locator('[data-testid="stSidebar"]'));await nav('Simulação');await button('▶ SIMULAR BATERIA');await charts();await shot('2rc-result');await nav('Exportação');await download('⬇️ BAIXAR RESULTADO CSV','-2rc');
  await nav('Simulação');await invalidUpload('Carregar CSV','CSV de corrente','timestamp,current_A\ninvalid,no\ninvalid,no\n');
}
async function h2() {
  await nav('Simulação');await button('▶ SIMULAR PEMFC / H₂');await charts();await shot('result');await nav('Exportação');await download('⬇️ BAIXAR RESULTADO CSV');
  await nav('Simulação');await invalidUpload('Carregar CSV','CSV do EMS','timestamp,P_FC_requested_kW\ninvalid,no\ninvalid,no\n');
}
async function mix() {
  await nav('3 · Entrada de dados');await button('▶ EXECUTAR MIX');await nav('4 · Resultados');await charts();await shot('result');await nav('5 · Exportação');await download('⬇️ BAIXAR CSV MIX');
  await nav('3 · Entrada de dados');await page.getByText('Carregar CSVs',{exact:true}).click();await ready();
  await page.locator('[data-testid="stFileUploader"]').filter({hasText:'Operação / proposta do otimizador'}).locator('input[type="file"]').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from('timestamp,garbage\ninvalid,no\ninvalid,no\n')});await ready();
  check(await page.getByRole('button',{name:'▶ EXECUTAR MIX',exact:true}).count()===0 || await page.getByRole('button',{name:'▶ EXECUTAR MIX',exact:true}).isDisabled(),'incomplete MIX proposal cannot run');await shot('invalid');
}
(async()=>{const b=await chromium.launch();try{page=await b.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});await page.goto(url);await ready();await openBench();await ({solar,wind,thermal,battery,h2,mix}[bench])();
  await page.reload();await ready();check((await page.locator('body').innerText()).length>300,'reload remains usable');await shot('reload');
  if(bench!=='mix'){await page.getByText('Ferramentas V1.6 — bancadas individuais dos modelos',{exact:true}).click();await ready();check(await page.getByRole('button',{name:'ABRIR SOLAR',exact:true}).isVisible(),'navigation continues after reload');}
  fs.writeFileSync(path.join(out,bench+'-receipt.json'),JSON.stringify({bench,checks,passed:true,receipts},null,2));console.log(`COMPLETE ${bench}: ${checks} checks`);
}catch(e){if(page){await shot('FAIL');fs.writeFileSync(path.join(out,bench+'-failure.txt'),await page.locator('body').innerText());}throw e;}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
