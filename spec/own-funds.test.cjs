// v151 (власник: «власні кошти не можуть бути мінусові»; «погашення кредитки має змінити баланс, тому що це операція а не статика»).
// Модель рушія: власні (дебетові й готівка) не нижче 0; витрата понад вільні власні йде в борг Mono до ліміту, далі інших кредиток;
// платіж лише з дебетової (credit_ok=false) кредиту не бере, непокрите стає нестачею. Виплата 21-го: резерв, погашення, бюджет 15-20 тис.,
// накопичення понад 10 тис., готівка 3 000, решта на Mono. Кожен випадок у TS і Python (повний паритет).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const {botFixture}=require('./bot-fixture.cjs');
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:60000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(data,asof,through){
 const input=JSON.stringify([{data,asof,through}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
const plus=(s,n)=>new Date(Date.parse(s+'T00:00:00Z')+n*864e5).toISOString().slice(0,10);
// власні не мінусові в кожній події й кожному дні; зміна (власні − борг − нестача) за день = надходження − обовʼязкові − комісії − змінні − накопичення
function invariants(r){
 for(const e of r.events)assert.ok(e.cashAfterCents>=0,e.id+' '+e.cashAfterCents);
 let prev=r.snapshot.cashCents-r.snapshot.creditDebtCents;
 for(const d of r.days){
  assert.ok(d.closingCashCents>=0&&d.minCashCents>=0,d.date);
  assert.equal(d.netCents,d.closingCashCents-d.debtCents-d.arrearsCents,d.date);
  const flow=r.events.filter(e=>e.date===d.date).reduce((s,e)=>s+(e.kind==='payout'||e.kind==='income'?e.amountCents:['mandatory','fee','variable','savings'].includes(e.kind)?-e.amountCents:0),0);
  assert.equal(d.netCents-prev,flow,'conservation '+d.date);prev=d.netCents;
 }
 for(const p of r.periods.filter(p=>p.ownCents!=null&&(p.cashOutCents>0||p.toMonoCents>0||p.savingsCents>0)))
  assert.equal(p.reserveCents+p.repayCents-p.monoOffsetCents+p.savingsCents+p.cashOutCents+p.toMonoCents,p.ownCents,'payout '+p.start);
}
const empty=(extra)=>Object.assign({accounts:[{id:1,kind:'debit',balance:0,debt:0}],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[],transactions:[]},extra);

test('budget rule at the 21st payout: A 12 000, 18 000, 35 000, 27 000',()=>{
 for(const [A,B,S] of [[12000,15000,0],[18000,18000,0],[35000,20000,15000],[27000,20000,0]]){
  const r=both(empty({salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:A,salary_amount:50000}}),'2026-10-20','2026-11-30');
  const p=r.periods.find(p=>p.start==='2026-10-21');
  assert.equal(p.availableCents,A*100);assert.equal(p.targetCents,B*100,'budget A='+A);assert.equal(p.savingsCents,S*100,'savings A='+A);
  assert.equal(p.cashOutCents,300000);assert.equal(p.toMonoCents,A*100-S*100-300000);
  assert.equal(r.nextPlan.targetCents,B*100);
  assert.equal(r.events.filter(e=>e.kind==='savings'&&e.date==='2026-10-21').length,S?1:0);
  invariants(r);
 }
});

// v152 (власник: «одразу має закритись кредитки з власних коштів»): аванс 06.11 проходить той самий розподіл, що й виплата 21-го.
// Власні 50 000, резерв 0, борг Mono 5 000 (жовтень, планове погашення 20.11, бо 21.11 субота): погашення min(5 000, 50 000 − 15 000) = 5 000 (додатково, раніше плану),
// A = 45 000, бюджет 20 000, надлишок 25 000 > 10 000 у накопичення, готівка 3 000, на Mono 17 000 (борг уже 0). До v152 аванс ішов без погашення й накопичень.
test('advance on the 6th: same distribution as the 21st (repay, savings, cash, Mono)',()=>{
 const r=both(empty({accounts:[{id:1,kind:'debit',balance:0,debt:0},{id:2,name:'Mono',kind:'credit',mono_account_id:'m',balance:0,debt:5000,credit_limit:30000,debt_month:'2026-10-01'}]}),'2026-11-05','2026-11-19');
 const p=r.periods.find(p=>p.start==='2026-11-06');
 assert.equal(p.reserveCents,0);assert.equal(p.repayCents,500000);
 assert.equal(p.availableCents,4500000);assert.equal(p.targetCents,2000000);assert.equal(p.savingsCents,2500000);
 assert.equal(p.cashOutCents,300000);assert.equal(p.toMonoCents,1700000);assert.equal(p.monoOffsetCents,0);
 const rep=r.events.filter(e=>e.kind==='repay');
 assert.deepEqual(rep.map(e=>[e.id,e.date,e.amountCents,e.plannedRepaymentDate]),[['repay:2:2026-10','2026-11-06',500000,'2026-11-20']]);
 assert.equal(r.days.find(d=>d.date==='2026-11-06').debtCents,0);
 assert.equal(r.events.filter(e=>e.kind==='savings'&&e.date==='2026-11-06').length,1);
 invariants(r);
});

test('spending over own funds goes to Mono up to its limit, then to the other card; debit-only payment never borrows',()=>{
 const d=empty({accounts:[{id:1,kind:'debit',balance:1000,debt:0},{id:2,name:'Приват',kind:'credit',balance:0,debt:0,credit_limit:5000},{id:3,name:'Mono',kind:'credit',mono_account_id:'m',balance:0,debt:0,credit_limit:2000}],
  fixed:[{id:1,name:'Оренда',type:'expense',amount:4000,day_of_month:14,credit_ok:false},{id:2,name:'Звʼязок',type:'expense',amount:3500,day_of_month:13,credit_ok:true}],
  categories:[{id:'1',name:'Їжа',type:'expense',budget_limit:100}]});
 const r=both(d,'2026-10-12','2026-12-15');
 invariants(r);
 const c13=r.events.find(e=>e.id==='fixed:2:2026-10'),rent=r.events.find(e=>e.id==='fixed:1:2026-10');
 // 13.10: вільних власних немає (1 000 зарезервовано під оренду лише з дебетової), 3 500 у борг: Mono 2 000, далі Приват 1 500
 assert.equal(c13.cashDeltaCents,0);assert.equal(c13.debtDeltaCents,350000);
 // 14.10: оренда 4 000 лише з дебетової: 1 000 власних, 3 000 нестача, власні 0, у кредит нічого
 assert.equal(rent.cashDeltaCents,-100000);assert.equal(rent.debtDeltaCents,0);assert.equal(rent.shortCents,300000);
 assert.ok(r.snapshot.warnings.some(w=>w.kind==='shortage'&&w.eventId==='fixed:1:2026-10'&&w.shortCents===300000));
 assert.equal(r.days.find(x=>x.date==='2026-10-14').closingCashCents,0);
 // ліміти: Mono не більше 2 000, Приват не більше 5 000 (погашення за рахунками до 21.10 = борг на ту дату)
 const rep=r.events.filter(e=>e.kind==='repay'&&e.date==='2026-10-21');
 assert.ok(rep.filter(e=>e.accountId===3).reduce((s,e)=>s+e.amountCents,0)<=200000);
 assert.ok(rep.filter(e=>e.accountId===2).reduce((s,e)=>s+e.amountCents,0)<=500000);
 // нестачу гасить перше надходження: виплата 21.10
 assert.ok(r.events.some(e=>e.kind==='arrears'&&e.date==='2026-10-21'));
 assert.equal(r.days.find(x=>x.date==='2026-10-21').arrearsCents,0);
});

test('21st payout repays mandatory first, then the other card, then Mono, leaving 15 000; the rest to Mono clears Mono',()=>{
 // власні 0, Приват 10 000 (вересень, належне 21.10), Mono 40 000 (жовтень), виплата 60 000, оренда 16 500 лише з дебетової 01.11
 const d=empty({accounts:[{id:1,kind:'debit',balance:0,debt:0},{id:2,name:'Приват',kind:'credit',balance:0,debt:10000,credit_limit:42500,debt_month:'2026-09-01'},{id:3,name:'Mono',kind:'credit',mono_account_id:'m',balance:0,debt:40000,credit_limit:40000,debt_month:'2026-10-01'}],
  fixed:[{id:1,name:'Оренда',type:'expense',amount:16500,day_of_month:1,credit_ok:false}],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:50000}});
 const r=both(d,'2026-10-20','2026-11-30');
 invariants(r);
 const p=r.periods.find(p=>p.start==='2026-10-21');
 // резерв 16 500; погашення min(50 000, 60 000 − 16 500 − 15 000 = 28 500) = 28 500: Приват 10 000, Mono 18 500; A = 15 000
 assert.equal(p.reserveCents,1650000);assert.equal(p.availableCents,1500000);assert.equal(p.targetCents,1500000);
 // готівка 3 000, на Mono 12 000 гасить залишок боргу Mono 21 500 частково
 assert.equal(p.cashOutCents,300000);assert.equal(p.toMonoCents,1200000);assert.equal(p.monoOffsetCents,1200000);
 const rep=r.events.filter(e=>e.kind==='repay'&&e.date==='2026-10-21');
 assert.deepEqual(rep.map(e=>[e.id,e.amountCents]),[['repay:2:2026-09',1000000],['repay:3:2026-10',3050000]]);
 assert.equal(rep.reduce((s,e)=>s+e.amountCents,0),p.repayCents);
 for(const e of rep)assert.equal(e.cashDeltaCents,-e.amountCents);
});

test('120 forecast days on the bot fixture: own funds never negative, invariants hold',()=>{
 const f=botFixture();const data=f.data??f;
 const r=both(data,'2026-10-12',plus('2026-10-12',120));
 assert.equal(r.days.length,121);
 invariants(r);
 assert.ok(r.days.some(d=>d.debtCents>0));
 const ids=r.events.map(e=>e.id);assert.equal(new Set(ids).size,ids.length);
 for(const e of r.events.filter(e=>e.kind==='repay'))assert.match(e.id,/^repay:[^:]+:\d{4}-\d{2}(:\d{4}-\d{2}-\d{2})?$/);
});
