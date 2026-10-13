// v147: одне правило погашення кредитки скрізь (рішення власника 12.10.2026, «прибери залишки 24-го»).
// v151: правило власника «погашення 21.10 гаситься максимум, спершу обовʼязкове, далі Приват, далі Mono»; правило v147
// «Mono 20.11» скасоване. Обовʼязкова дата кошика лишається repayDate (борг місяця M з виплати 21-го в M+1, вихідні
// зсуваються), але фактичне погашення бере рушій: на прод-фікстурі 21.10 гасить і Приват (борг вересня, обовʼязкове),
// і Mono (борг жовтня, додатково). Кожен шлях показує дату події рушія: чип і картка рахунку (debtDue), каса
// cashRepayDate, позначка «з кредитки, гасимо» (planRepay), бот (formatFinanceMessage).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const ASOF='2026-10-12',WANT={3:'2026-10-21',4:'2026-10-21'},DUE={3:'2026-11-20',4:'2026-10-21'};
const salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:51000,salary_amount:51000};
const stamp='2026-10-12T07:00:00Z';
const own={id:1,name:'Ощадбанк',kind:'debit',balance:2519,debt:0,balance_updated_at:stamp};
const mono={id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:29070.45,credit_limit:50000,debt_month:'2026-10-01',balance_updated_at:stamp};
const privat={id:4,name:'ПриватБанк',kind:'credit',balance:0,debt:9256.55,credit_limit:30000,debt_month:'2026-09-01',balance_updated_at:stamp};
const prod=()=>({accounts:[own,mono,privat],salary,fixed:[],credits:[],categories:[],transactions:[]});
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(data,asof=ASOF,scenario){
 const input=JSON.stringify([{data,asof,through:'2027-01-10',scenario}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
const repayOf=(r,id)=>r.events.filter(e=>e.kind==='repay'&&e.id.startsWith('repay:'+id+':')).map(e=>e.date);

// функції фронтенду рівно так, як вони лежать в index.html: вбудована копія рушія і обгортки, без копій правила
function front(){
 const canon=html.split('/* CANONICAL FINANCE PROJECTION */')[1].split('/* END CANONICAL FINANCE PROJECTION */')[0];
 const pick=re=>{const m=html.match(re);assert.ok(m,'не знайдено в index.html: '+re);return m[0];};
 const src=[pick(/const pbIso=[^;]+;/),pick(/const pbDate=v=>\{.*?\};/),pick(/const pbDiff=[^;]+;/),pick(/const pbDm=[^;]+;/),
  pick(/^function cashBuckets\(.*$/m),pick(/^let REPAY_EV=.*$/m),pick(/^function repayKind\(.*$/m),pick(/^function debtDue\(.*$/m),pick(/^function dueCls\(.*$/m),pick(/^function cashRepayDate\(.*$/m),canon,
  'const planRepayOf=function(now){'+pick(/const planRepay=function\(y,m,d\)\{.*?\};/)+'return planRepay};',
  'return {repayDate,financeProjection,setRepayEvents,debtDue,dueCls,cashRepayDate,pbDate,pbIso,pbDm,planRepayOf};'].join('\n');
 return new Function(src)();
}

test('engine repay events (TS and Python): 21.10 repays Privat (due) and Mono (extra); contractual 24th is informational only',()=>{
 const r=both(prod());
 // Mono: 21.10 гасить увесь борг на той день, хвіст жовтня (витрати після 21.10) і борг листопада йдуть 20.11
 assert.deepEqual(repayOf(r,3),[WANT[3],'2026-11-20','2026-11-20']);assert.deepEqual(repayOf(r,4),[WANT[4]]);
 for(const a of [3,4]){const e=r.events.find(e=>e.id==='repay:'+a+':'+(a===3?'2026-10':'2026-09'));assert.equal(e.date,WANT[a]);assert.equal(e.plannedRepaymentDate,DUE[a]);}
 // без прострочки: подія не пізніша за обовʼязкову дату кошика
 for(const e of r.events.filter(e=>e.kind==='repay')){assert.ok(e.date<=e.plannedRepaymentDate,e.id);assert.equal(e.contractualDueDate.slice(8),'24');}
});

test('credit scenario repays by the same rule: October debt 20.11, September debt 21.10',()=>{
 const fixed=[{id:1,name:'Комуналка',type:'expense',amount:3000,day_of_month:20,credit_ok:true,active:true}];
 for(const id of [3,4]){
  const r=both({...prod(),fixed},ASOF,{selections:[{occurrenceId:'fixed:1:2026-10',accountId:id,amountCents:300000}]});
  assert.deepEqual(r.scenario.errors,[]);assert.equal(r.scenario.repayments[0].date,'2026-11-20');
 }
 // вересневий сценарій можливий лише до кінця вересня: «зараз» 15.09
 const r=both({...prod(),fixed},'2026-09-15',{selections:[{occurrenceId:'fixed:1:2026-09',accountId:4,amountCents:300000}]});
 assert.deepEqual(r.scenario.errors,[]);assert.equal(r.scenario.repayments[0].date,'2026-10-21');
});

test('account chip, bank card, cash line and credit tag in index.html give the engine dates',()=>{
 const f=front(),today=f.pbDate(ASOF),proj=f.financeProjection(prod(),{asof:ASOF,through:'2027-01-10'});
 f.setRepayEvents(proj.events);
 for(const a of [mono,privat]){
  // чип рахунку: дата з події рушія (вбудована копія); картка «закрити до» з debtDue, що читає ті самі події
  const ev=proj.events.find(e=>e.kind==='repay'&&String(e.id).indexOf('repay:'+a.id+':')===0);
  assert.equal(ev.date,WANT[a.id]);
  assert.equal(f.pbIso(f.debtDue(a,today).date),WANT[a.id]);
  // каса cashEvents: погашення кошика за місяцем боргу
  assert.equal(f.pbIso(f.cashRepayDate(a.debt_month.slice(0,7),today,a.id)),WANT[a.id]);
  // позначка «з кредитки, гасимо DD.MM» для витрати в місяці боргу
  const m=Number(a.debt_month.slice(5,7))-1;assert.equal(f.planRepayOf(today)(2026,m),f.pbDm(f.pbDate(WANT[a.id])));
 }
 assert.equal(f.debtDue(privat,today).level,'ok');assert.equal(f.debtDue(privat,f.pbDate('2026-10-22')).level,'late');
 // v151: вид найближчого погашення на чипі: Приват 21.10 обовʼязкове (попередження за 5 днів), Mono 21.10 додатково (нейтральне)
 const near=f.pbDate('2026-10-18'),dp=f.debtDue(privat,near),dm=f.debtDue(mono,near);
 assert.deepEqual([dp.kind,dp.level,f.dueCls(dp)],['обовʼязкове','warn','']);
 assert.deepEqual([dm.kind,dm.level,f.dueCls(dm)],['додатково','ok',' extra']);
 assert.equal(f.dueCls(f.debtDue(privat,f.pbDate('2026-10-22'))),' late');
 assert.equal(f.repayDate('2026-12',''),'2027-01-21');assert.equal(f.repayDate('2026-10','2026-11-25'),'2026-11-25');
});

test('bot message shows the same dates',async()=>{
 const {financeProjection}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 const {formatFinanceMessage}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/finance-message.ts')).href);
 const lines=formatFinanceMessage(financeProjection(prod(),{asof:ASOF,through:'2027-01-10'})).split('\n').filter(l=>/борг/.test(l));
 assert.ok(lines.some(l=>l.includes('Monobank')&&l.includes('план погашення 21.10')),lines.join('\n'));
 assert.ok(lines.some(l=>l.includes('ПриватБанк')&&l.includes('план погашення 21.10')),lines.join('\n'));
});
