const{chromium}=require('playwright'),fs=require('fs'),path=require('path');const[url,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});let p,n=0;
function check(x,m){if(!x)throw Error(m);n++;console.log('PASS '+m)}
async function ready(){await p.waitForLoadState('networkidle');await p.waitForTimeout(1200);check(!await p.locator('[data-testid="stException"]').count(),'no Python exception')}
const run=()=>p.getByRole('button',{name:'▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO',exact:true});
(async()=>{const b=await chromium.launch();try{p=await b.newPage({viewport:{width:1440,height:1000}});await p.goto(url);await ready();await p.getByRole('button',{name:'ABRIR MICRORREDE',exact:true}).first().click();await ready();const here=new URL(p.url());here.searchParams.set('view','simulacao');await p.goto(here.toString());await ready();await p.locator('[data-testid="stSidebar"]').getByRole('button',{name:'◎ Otimizador',exact:true}).click();await ready();check(await run().isEnabled(),'configuration A initially executable');
 await p.getByRole('button',{name:'ACEPTACIÓN: guardar B y fallar transferencia',exact:true}).click();await ready();check(await run().isDisabled(),'partial transfer of real revision B blocks execution');check(await p.getByText('Transferência BLOQUEADA',{exact:false}).first().isVisible(),'failure clearly identified');await p.screenshot({path:path.join(out,'blocked.png')});
 await p.locator('[data-testid="stSidebar"]').getByRole('button',{name:'◈ Modelos',exact:true}).click();await ready();await p.locator('[data-testid="stSidebar"]').getByRole('button',{name:'◎ Otimizador',exact:true}).click();await ready();check(await run().isDisabled(),'navigation/rerender cannot reopen execution');
 await p.getByRole('button',{name:'Reintentar transferência da configuração salva',exact:true}).click();await ready();check(await run().isEnabled(),'intentional retry applies B and reopens gate');check(!await p.getByText('Transferência BLOQUEADA',{exact:false}).count(),'failure latch cleared after successful retry');await p.screenshot({path:path.join(out,'retried.png')});for(const revision of ['first','second']){
  await p.getByRole('button',{name:'ACEPTACIÓN: agregar equipo excluido',exact:true}).click();await ready();
  check(await run().isDisabled(),revision+' changed exclusion blocks execution');
  const consent=p.getByRole('checkbox',{name:/^Confirmo executar esta rodada SEM/});
  check(!await consent.isChecked(),revision+' revision does not inherit old checkbox consent');
  await p.screenshot({path:path.join(out,revision+'-exclusion-blocked.png')});
  await p.getByText(/^Confirmo executar esta rodada SEM/).click();await ready();check(await run().isEnabled(),revision+' explicit new consent reopens gate');
 }
 fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify({passed:true,checks:n}));console.log('COMPLETE P0 and exclusion consent '+n)
}catch(e){if(p){await p.screenshot({path:path.join(out,'FAIL.png')});fs.writeFileSync(path.join(out,'failure.txt'),await p.locator('body').innerText())}throw e}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
