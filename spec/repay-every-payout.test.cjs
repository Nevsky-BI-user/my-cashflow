// v152 (власник: «тут одразу має закритись кредитки з власних коштів, ми гасимо кредитку, щоб там не було заборгованості»):
// КОЖНА виплата в прогнозі (зарплата 06-го, аванс 21-го, будь-яка інша) у день надходження проходить той самий розподіл:
// резерв дебетових обовʼязкових до наступної виплати, погашення максимум (спершу належне, далі Приват, далі Mono), лишаючи бюджет
// періоду (payoutBudget), надлишок понад 10 000 у накопичення, готівка 3 000, решта на Mono. До v152 так ішла лише виплата 21-го.
// Інваріанти: власні ≥ 0 скрізь; якщо власних вистачає, кредитні після розподілу виплати = 0 і за день виплати борг не росте;
// кожне погашення окрема подія з унікальним id (перше repay:<рахунок>:<місяць>, наступні того ж кошика з датою); TS і Python однакові.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const stamp='2026-10-12T07:00:00Z';
const ASOF='2026-10-12',THROUGH='2027-01-31';
const data=()=>({
 accounts:[{id:1,name:'Ощадбанк',kind:'debit',balance:3000,debt:0,balance_updated_at:stamp},
  {id:2,name:'ПриватБанк',kind:'credit',balance:0,debt:9000,credit_limit:40000,debt_month:'2026-09-01',balance_updated_at:stamp},
  {id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:25000,credit_limit:50000,debt_month:'2026-10-01',balance_updated_at:stamp}],
 salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:60000},
 fixed:[{id:1,name:'Оренда',type:'expense',amount:7000,day_of_month:10,credit_ok:false,active:true},{id:2,name:'Звʼязок',type:'expense',amount:400,day_of_month:15,credit_ok:true,active:true},
  // 28-го власних на платіж не вистачає: він іде в борг Mono, тож до виплати 06-го висить борг, який вона має погасити
  {id:3,name:'Ремонт',type:'expense',amount:30000,day_of_month:28,credit_ok:true,active:true}],
 credits:[],categories:[{id:'1',name:'Їжа',type:'expense',budget_limit:70},{id:'2',name:'Інше',type:'expense',budget_limit:30}],transactions:[]});
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(d){
 const input=JSON.stringify([{data:d,asof:ASOF,through:THROUGH}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
const DIST=['payout','income','arrears','repay','savings'];

test('every payout repays card debt the same day when own funds cover it: credit 0 after the split, own never below zero',()=>{
 const r=both(data());
 const pays=r.periods.filter(p=>p.payoutCents>0&&p.start>=ASOF);
 assert.ok(pays.length>=6,'виплат у прогнозі '+pays.length);
 assert.ok(pays.some(p=>p.start.slice(8)==='06')&&pays.some(p=>p.start.slice(8)!=='06'),'є і зарплата 06-го, і аванс');
 for(const d of r.days)assert.ok(d.closingCashCents>=0&&d.minCashCents>=0,'власні мінус '+d.date);
 for(const e of r.events)if(e.cashAfterCents!=null)assert.ok(e.cashAfterCents>=0,'власні мінус після '+e.id);
 let covered=0;
 for(const p of pays){
  const prev=r.days.filter(d=>d.date<p.start).pop(),before=prev?prev.debtCents:r.snapshot.creditDebtCents,day=r.days.find(d=>d.date===p.start);
  const dist=r.events.filter(e=>e.date===p.start&&DIST.includes(e.kind)),last=dist[dist.length-1];
  // розподіл за правилом payoutBudget: погашення = min(борг, max(0, власні − резерв − 15 000)) (v153: бюджет до погашення, належне першим усередині цієї суми)
  // v153 доповнення 7: залишок періоду розподіляється до нової виплати (погашення, дострокове, накопичення), ownCents уже після нього
  assert.equal(p.leftoverRepayCents+p.leftoverPrepayCents+p.leftoverSavingsCents,p.leftoverCents,p.start+': залишок не сходиться');
  assert.equal(p.reserveCents+p.payoutRepayCents-p.monoOffsetCents+p.payoutPrepayCents+p.cashOutCents+p.toMonoCents,p.ownCents,p.start+': розподіл не сходиться');
  if(p.ownCents-p.reserveCents-1500000>=before){
   covered++;
   assert.equal(last.debtAfterCents,0,p.start+': кредитні після розподілу '+last.debtAfterCents+' при власних '+p.ownCents);
   assert.ok(day.debtCents<=before,p.start+': борг виріс за день виплати '+before+' -> '+day.debtCents);
   if(before>0)assert.ok(r.events.some(e=>e.kind==='repay'&&e.date===p.start),p.start+': немає погашення');
  }
 }
 assert.ok(covered>=4,'показових виплат (власних вистачає) '+covered);
 // 06.11: погашення раніше плану, вид «додатково» (дата події раніше планової)
 const nov=r.events.filter(e=>e.kind==='repay'&&e.date==='2026-11-06');
 assert.ok(nov.length>0&&nov.every(e=>e.date<e.plannedRepaymentDate),'06.11: '+JSON.stringify(nov.map(e=>[e.id,e.plannedRepaymentDate])));
});

test('repay event ids are unique per payout: the same bucket repaid on two payouts gets a dated id',()=>{
 const r=both(data());
 const ids=r.events.map(e=>e.id);
 assert.equal(new Set(ids).size,ids.length,'дублікати id подій');
 const rep=r.events.filter(e=>e.kind==='repay');
 for(const e of rep)assert.match(e.id,/^repay:\d+:\d{4}-\d{2}(:\d{4}-\d{2}-\d{2})?$/,e.id);
 // кошик, погашений кількома виплатами: перший без дати, наступні з датою своєї виплати
 const byBucket={};for(const e of rep){const k=e.id.split(':').slice(0,3).join(':');(byBucket[k]=byBucket[k]||[]).push(e);}
 const multi=Object.values(byBucket).filter(l=>l.length>1);
 assert.ok(multi.length>0,'немає кошика з двома погашеннями, перевірка не показова');
 for(const l of multi){assert.equal(l[0].id.split(':').length,3);for(const e of l.slice(1))assert.equal(e.id.split(':')[3],e.date);}
});
