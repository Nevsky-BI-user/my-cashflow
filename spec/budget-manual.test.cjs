// v153 (власник: «має бути можливість встановлювати суму, яка розподіляється»): ручний бюджет періоду (salary_config.budget_manual)
// замість авто (15 000, до 20 000). Бюджет резервується з виплати до погашення (власник: «як ти гасиш кредитку, якщо на це немає білих
// грошей?»), тож різниця між ручною сумою і авто рівно переходить у погашення, поки є борг, а без боргу в накопичення.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const stamp='2026-10-12T07:00:00Z';
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(d,asof='2026-10-20',through='2026-12-31'){
 const input=JSON.stringify([{data:d,asof,through}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
// борг більший за все, що лишається після резерву й бюджету: власні 0, Mono 40 000, виплата 60 000 21.10, оренда 16 500 01.11 лише з дебетової
const indebted=(manual)=>({accounts:[{id:1,kind:'debit',balance:0,debt:0,balance_updated_at:stamp},{id:3,name:'Mono',kind:'credit',mono_account_id:'m',balance:0,debt:40000,credit_limit:40000,debt_month:'2026-10-01',balance_updated_at:stamp}],
 fixed:[{id:1,name:'Оренда',type:'expense',amount:16500,day_of_month:1,credit_ok:false}],credits:[],categories:[],transactions:[],
 salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:50000,budget_manual:manual}});
// без боргу: власні 0, виплати 60 000, оренда 7 000 10-го з дебетової
const clean=(manual)=>({accounts:[{id:1,kind:'debit',balance:0,debt:0,balance_updated_at:stamp}],
 fixed:[{id:1,name:'Оренда',type:'expense',amount:7000,day_of_month:10,credit_ok:false}],credits:[],categories:[],transactions:[],
 salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:60000,budget_manual:manual}});
const at=(r,d)=>r.periods.find(p=>p.start===d);

test('payoutBudget: budget is reserved before repayment; manual sum replaces the auto rule; uncovered due is dueShortCents',async()=>{
 const {payoutBudget}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 // авто: вільні 43 500, борг 40 000: погашення 28 500, A 15 000
 assert.deepEqual(payoutBudget(6000000,1650000,4000000,0,true),{repayCents:2850000,dueShortCents:0,availableCents:1500000,targetCents:1500000});
 // ручна 10 000: погашення на 5 000 більше; ручна 25 000: на 10 000 менше, бюджет рівно ручна сума
 assert.deepEqual(payoutBudget(6000000,1650000,4000000,0,true,1000000),{repayCents:3350000,dueShortCents:0,availableCents:1000000,targetCents:1000000});
 assert.deepEqual(payoutBudget(6000000,1650000,4000000,0,true,2500000),{repayCents:1850000,dueShortCents:0,availableCents:2500000,targetCents:2500000});
 // належне 20 000 понад вільні після бюджету (18 500): погашення 18 500, нестача 1 500 (не погашення з повітря)
 assert.deepEqual(payoutBudget(5000000,1650000,4000000,2000000,true),{repayCents:1850000,dueShortCents:150000,availableCents:1500000,targetCents:1500000});
 // ручна сума більша за вільні: погашення 0, бюджет лишається ручним (розрив показує UI), нестача = все належне
 assert.deepEqual(payoutBudget(3000000,1650000,4000000,500000,true,2000000),{repayCents:0,dueShortCents:500000,availableCents:1350000,targetCents:2000000});
 // 0 теж ручна сума
 assert.equal(payoutBudget(6000000,1650000,4000000,0,true,0).repayCents,4000000);
});

test('manual budget instead of auto: the difference goes exactly into repayment while there is debt (TS and Python)',()=>{
 const a=at(both(indebted(null)),'2026-10-21');
 assert.equal(a.targetCents,1500000);assert.equal(a.repayCents,2850000);
 for(const m of [10000,12345.67,18000]){
  const r=both(indebted(m)),p=at(r,'2026-10-21'),mc=Math.round(m*100);
  assert.equal(p.targetCents,mc,'бюджет = ручна сума');
  assert.equal(p.repayCents-a.repayCents,a.targetCents-mc,m+': погашення змінилось рівно на різницю бюджетів');
  assert.equal(p.savingsCents,a.savingsCents,m+': накопичення без змін, поки є борг');
  assert.equal(p.categories.reduce((s,c)=>s+c.totalCents,0),mc,'план змінних = ручна сума');
  // між виплатами кредитка не росте: змінні з бюджету власних
  assert.ok(r.events.filter(e=>e.date>'2026-10-21'&&e.date<'2026-11-06').every(e=>!(e.debtDeltaCents>0)),m+': борг росте між виплатами');
 }
});

test('manual budget without debt: the difference goes exactly into savings; empty or null means auto',()=>{
 const a=both(clean(null)),pa=at(a,'2026-10-21');
 assert.equal(pa.targetCents,2000000);assert.equal(pa.repayCents,0);
 const r=both(clean(15000)),p=at(r,'2026-10-21');
 assert.equal(p.targetCents,1500000);assert.equal(p.repayCents,0);
 // v153 доповнення 7: накопичення відкладаються з залишку періоду в день наступної виплати (06.11), а не з цієї виплати
 assert.deepEqual([p.savingsCents,pa.savingsCents],[0,0],'з нової виплати накопичень немає');
 const n=at(r,'2026-11-06'),na=at(a,'2026-11-06');
 assert.equal(n.savingsCents-na.savingsCents,pa.targetCents-p.targetCents,'накопичення 06.11 більше рівно на різницю бюджетів 21.10');
 assert.deepEqual([n.savingsCents,na.savingsCents],[n.openingCashCents,na.openingCashCents],'накопичення = залишок періоду (власні на початок дня виплати)');
 assert.deepEqual(both(clean('')),a,'порожнє поле = авто');
 assert.deepEqual(both(clean(undefined)),a,'немає поля = авто');
});

test('current period with a manual budget: forecast until the payout = max(pro rata of the sum, sum minus actual)',()=>{
 const d=clean(9000);d.transactions=[{id:1,account_id:1,type:'expense',amount:2000,date:'2026-10-08',created_at:'2026-10-08T00:00:00Z'}];d.accounts[0].balance=20000;
 const r=both(d,'2026-10-12','2026-11-30'),cp=r.currentPeriod;
 // період 06.10-20.10 (15 дн.), від завтра 8 дн.: частка 9 000 × 8 / 15 = 4 800, сума мінус факт 9 000 − 2 000 = 7 000
 assert.equal(cp.start,'2026-10-06');assert.equal(cp.periodDays,15);assert.equal(cp.leftDays,8);
 assert.equal(cp.actualVariableCents,200000);assert.equal(cp.remainingTargetCents,700000);
});
