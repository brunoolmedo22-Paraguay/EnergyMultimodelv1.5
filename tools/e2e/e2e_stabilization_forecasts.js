// Separate operational acceptance. The legacy pixel-exact autorange assertion
// remains unchanged in e2e_piso2b_previsoes.js and is reported independently.
const{chromium}=require('playwright'),fs=require('fs'),path=require('path');
const { expandirCartoes } = require("./catalogo_util");
const[url,csv,out,phase='operar']=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
let p,n=0;function check(x,m){if(!x)throw Error(m);n++;console.log('PASS '+m)}
async function ready(){await p.waitForLoadState('networkidle');await p.waitForTimeout(1000);check(!await p.locator('[data-testid="stException"]').count(),'no Python exception')}
const panel=()=>p.locator('[role="tabpanel"]:visible');
async function btn(name){await p.getByRole('button',{name,exact:true}).click();await ready()}
async function tab(name){await p.getByRole('tab',{name}).click();await ready()}
async function select(label,value){const s=panel().locator('[data-testid="stSelectbox"]').filter({hasText:label}).first();await s.locator('input').click();await p.keyboard.type(value);await p.keyboard.press('Enter');await ready()}
async function upload(name){await panel().locator('input[type="file"]').setInputFiles(path.join(csv,name));await ready()}
async function data(title){for(const c of await panel().locator('[data-testid="stPlotlyChart"]').all()){await c.scrollIntoViewIfNeeded();await p.waitForTimeout(400)}
 await p.waitForFunction(t=>[...document.querySelectorAll('.js-plotly-plot')].some(g=>g._fullData&&g.layout?.title?.text?.includes(t)),title,{timeout:60000});
 return p.evaluate(t=>{const g=[...document.querySelectorAll('.js-plotly-plot')].find(g=>g._fullData&&g.layout?.title?.text?.includes(t));return g._fullData.map(d=>({name:d.name,x:Array.from(d.x||[]),y:Array.from(d.y||[])}))},title)}
async function reopen(){await p.goto(url);await ready();await expandirCartoes(p); await p.getByRole('button',{name:'ABRIR MICRORREDE',exact:true}).first().click();await ready();await btn('ABRIR PREVISÕES')}
(async()=>{const b=await chromium.launch();try{p=await b.newPage({viewport:{width:1440,height:900}});
 if(phase==='operar'){
  await p.goto(url);await ready();await expandirCartoes(p); await p.getByRole('button',{name:'ABRIR MICRORREDE',exact:true}).first().click();await ready();await btn('＋ NOVO CENÁRIO');await p.getByLabel('Nome do cenário *').fill('Aceitação integral de previsões');await btn('Criar cenário');await btn('ABRIR PREVISÕES');
  await panel().getByText('Importar CSV',{exact:true}).click();await ready();await upload('malformado_e2e.csv');check(await p.getByText('Arquivo recusado',{exact:false}).first().isVisible(),'corrupt input rejected');check(await panel().getByRole('button',{name:'INCORPORAR AO CENÁRIO',exact:true}).isDisabled(),'corrupt input cannot be incorporated');
  await upload('demanda_e2e.csv');const demand=await data('PRÉ-VISUALIZAÇÃO');check(demand[0].y.length===121,'121 demand samples rendered');await btn('INCORPORAR AO CENÁRIO');
  await tab(/Clima/);await panel().getByText('Importar CSV',{exact:true}).click();await ready();await upload('clima_e2e.csv');
  await select('Velocidade do vento — obrigatória','vento');await select('Direção do vento — opcional','direcao_vento_deg');await select('Unidade de GHI','W/m');await select('Unidade de Vento','m/s');
  const climate=await data('PRÉ-VISUALIZAÇÃO');check(climate.length>=4,'climate quantities rendered separately');await btn('INCORPORAR AO CENÁRIO');await btn('SALVAR CENÁRIO');check(await panel().getByText('Salvo · v2',{exact:true}).isVisible(),'scenario version 2 saved');
  await panel().getByRole('button',{name:'VERIFICAR INTEGRIDADE E REPRODUTIBILIDADE',exact:true}).click();await ready();check(await panel().getByText('mesmo SHA-256',{exact:false}).first().isVisible(),'integrity and reproducibility SHA-256');
  fs.writeFileSync(path.join(out,'expected.json'),JSON.stringify({demand,climate}));await p.screenshot({path:path.join(out,'saved-climate.png')});
 }
 const expected=JSON.parse(fs.readFileSync(path.join(out,'expected.json')));await reopen();check(JSON.stringify(await data('perfil do cenário'))===JSON.stringify(expected.demand),'saved demand exactly recovered');await tab(/Clima/);check(JSON.stringify(await data('perfil do cenário'))===JSON.stringify(expected.climate),'saved climate exactly recovered');
 for(const[w,h]of[[820,1180],[1180,820]]){await p.setViewportSize({width:w,height:h});await ready();check(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'tablet no horizontal overflow '+w);await p.screenshot({path:path.join(out,phase+'-tablet-'+w+'.png')})}
 fs.writeFileSync(path.join(out,phase+'-receipt.json'),JSON.stringify({passed:true,checks:n}));console.log('COMPLETE '+phase+' '+n);
}catch(e){if(p){await p.screenshot({path:path.join(out,phase+'-FAIL.png')});fs.writeFileSync(path.join(out,phase+'-failure.txt'),await p.locator('body').innerText())}throw e}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
