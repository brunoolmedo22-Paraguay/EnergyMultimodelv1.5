const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
const { expandirCartoes } = require("./catalogo_util");
const [url,out,expectedFile]=process.argv.slice(2), expected=JSON.parse(fs.readFileSync(expectedFile));
fs.mkdirSync(out,{recursive:true});let p,checks=0;const receipt=[];
function check(ok,msg){if(!ok)throw Error(msg);checks++;console.log('PASS '+msg);}
async function ready(){await p.waitForLoadState('networkidle');await p.waitForTimeout(1000);check(await p.locator('[data-testid="stException"]').count()===0,'no Python exception');}
async function nav(name){await p.locator('[data-testid="stSidebar"]').getByRole('button',{name,exact:true}).click();await ready();}
async function select(label,value){const box=p.locator('[data-testid="stSelectbox"]').filter({hasText:label}).first();await box.locator('input').click();await p.keyboard.type(value);await p.getByRole('option',{name:value,exact:true}).click();await ready();}
(async()=>{const b=await chromium.launch();try{
 p=await b.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});await p.goto(url);await ready();await expandirCartoes(p); await p.getByRole('button',{name:'ABRIR MICRORREDE',exact:true}).first().click();await ready();await p.getByText('Ferramentas V1.6 — bancadas individuais dos modelos',{exact:true}).click();await p.getByRole('button',{name:'ABRIR EÓLICA',exact:true}).click();await ready();await nav('Catálogo de aerogeradores');
 const input=p.locator('[data-testid="stSelectbox"]').filter({hasText:'Aerogerador do catálogo'}).locator('input');await input.click();check(await p.getByRole('option').count()===13,'exactly thirteen selector entries');await p.keyboard.press('Escape');
 for(const entry of expected){await select('Aerogerador do catálogo',entry.key);
  check(await p.getByText('Potência nominal / referência',{exact:true}).isVisible(),'reference distinguished '+entry.key);
  check(await p.getByText('Pico documentado:',{exact:false}).isVisible(),'curve peak displayed '+entry.key);
  const chart=p.locator('[data-testid="stPlotlyChart"]').first();await chart.scrollIntoViewIfNeeded();await p.waitForTimeout(500);
  await p.waitForFunction(()=>document.querySelector('.js-plotly-plot')?._fullData?.length,null,{timeout:60000});
  const points=await p.evaluate(()=>{const d=document.querySelector('.js-plotly-plot')._fullData[0];return Array.from(d.x).map((x,i)=>[x,d.y[i]])});
  const divisor=Math.max(...entry.points.map(p=>p[1]))<1000?1:1000;
  check(JSON.stringify(points)===JSON.stringify(entry.points.map(([v,p])=>[v,p/divisor])),'all rendered nodes equal catalog in displayed units '+entry.key);
  if(entry.analysis){check((await p.locator('body').innerText()).includes('sem previsão operacional'),'analysis-only restriction '+entry.key);
   check(!(await p.locator('body').innerText()).includes('0.00 MW'),'small power remains legible '+entry.key);
  }
  if(entry.new)await p.screenshot({path:path.join(out,entry.slug+'-catalog.png'),fullPage:false});
  receipt.push({key:entry.key,nodes:points.length,analysisOnly:entry.analysis});
 }
 await nav('Simulação');
 for(const entry of expected.filter(e=>e.new)){
  await select('Aerogerador',entry.key);await p.getByText('Exemplo sintético · Ceará',{exact:true}).click();await ready();await p.getByRole('button',{name:'▶ CALCULAR PERFIL EÓLICO',exact:true}).click();await ready();
  if(entry.analysis){check(await p.getByText('Não foi possível executar o modelo:',{exact:false}).isVisible(),'energy simulation rejected '+entry.key);}
  else{check(await p.getByText('Simulação concluída.',{exact:true}).isVisible(),'new turbine energy run '+entry.key);await nav('Exportação');const[d]=await Promise.all([p.waitForEvent('download'),p.getByRole('button',{name:'⬇️ BAIXAR RESULTADO CSV',exact:true}).click()]);await d.saveAs(path.join(out,entry.slug+'-energy.csv'));await nav('Simulação');
    const selected=await p.locator('[data-testid="stSelectbox"]').filter({hasText:'Aerogerador'}).first().locator('input').inputValue();check(selected===entry.key,'successful selection persists across pages '+entry.key);
  }
 }
 fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify({passed:true,checks,receipt},null,2));console.log('COMPLETE wind catalog '+checks);
}catch(e){if(p){fs.writeFileSync(path.join(out,'failure.txt'),await p.locator('body').innerText());await p.screenshot({path:path.join(out,'FAIL.png')});}throw e;}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
