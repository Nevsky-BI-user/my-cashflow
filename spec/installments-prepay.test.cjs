// v153 доповнення 5 (власник: «ідея в тому що ми не можемо заощаджувати поки не закриємо борги за кредиткою та за розстрочками»).
// Розподіл кожної виплати: резерв (бюджет періоду і всі обовʼязкові до наступної виплати, з платежами розстрочок), погашення кредиток,
// без боргу кредиток надлишок іде в дострокове погашення розстрочок (найменший залишок першим), накопичення лише коли закрито все.
// Дострокове погашення зрізає графік розстрочки з кінця: останній платіж може бути частковим, далі платежів у прогнозі немає. Лише прогноз.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const stamp='2026-10-12T07:00:00Z';
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(d,asof='2026-10-12',through='2027-08-31'){
 const input=JSON.stringify([{data:d,asof,through}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 assert.equal(new Set(ts.events.map(e=>e.id)).size,ts.events.length,'id без колізій');
 return ts;
}
// власні 0; виплати 21-го і 6-го по 60 000; оренда 10 000 1-го з дебетової; кредитка з боргом; дві розстрочки з дебетової
// (start_month рушія: індекс місяця, як у наявних даних): Ноутбук 3 100 × 10 після asof, Станція 4 700 × 3 після asof
const data=(debt)=>({accounts:[{id:1,kind:'debit',balance:0,debt:0,balance_updated_at:stamp},{id:2,name:'Приват',kind:'credit',balance:0,debt,credit_limit:200000,debt_month:'2026-10-01',balance_updated_at:stamp}],
 fixed:[{id:1,name:'Оренда',type:'expense',amount:10000,day_of_month:1,credit_ok:false}],
 credits:[{id:3,name:'Ноутбук',monthly_amount:3100,payment_day:24,start_year:2026,start_month:9,total_payments:10,credit_ok:false},
          {id:5,name:'Станція',monthly_amount:4700,payment_day:12,start_year:2026,start_month:10,total_payments:3,credit_ok:false}],
 categories:[],transactions:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:60000}});
const of=(r,cid)=>r.events.filter(e=>e.id.startsWith('installment:'+cid+':')||e.id.startsWith('prepay:'+cid+':'));
const dayOf=(r,d)=>r.days.find(x=>x.date===d);

// день виплати: борг кредиток після її погашень (остання подія дня до обовʼязкових і змінних)
const debtAfterPayout=(r,d)=>r.events.filter(e=>e.date===d&&['payout','income','arrears','repay','prepay','savings'].includes(e.kind)).pop().debtAfterCents;

test('savings stay 0 while a credit card has debt or any installment is not closed; they start only after everything is closed',()=>{
 const r=both(data(90000));
 const at=d=>r.periods.find(p=>p.start===d);
 // скриптом із рушія: 21.10 і 06.11 гасять кредитку, 20.11 закриває її і починає дострокове, 07.12 закриває розстрочки, 21.12 перші накопичення
 // (v153 доповнення 7: накопичення 21.12 = залишок періоду 07.12-20.12, тобто надлишок виплати 07.12 після дострокових; з самої виплати 21.12 нуль)
 assert.deepEqual(['2026-10-21','2026-11-06','2026-11-20','2026-12-07','2026-12-21'].map(d=>[at(d).repayCents,at(d).prepayCents,at(d).savingsCents]),
  [[3190000,0,0],[4030000,0,0],[2580000,110000,0],[0,2840000,690000],[0,0,3000000]]);
 for(const p of r.periods.filter(p=>p.basis!=='current')){
  const instAhead=r.events.some(e=>e.id.startsWith('installment:')&&e.date>=p.end);
  if(debtAfterPayout(r,p.start)>0||instAhead)assert.equal(p.savingsCents,0,p.start+': накопичення при боргу кредитки або незакритій розстрочці');
  if(p.prepayCents>0)assert.equal(debtAfterPayout(r,p.start),0,p.start+': дострокове погашення розстрочки при боргу кредитки');
  // v153 доповнення 7: накопичення лише з залишку попереднього періоду (власні на початок дня виплати), з нової виплати нуль
  assert.equal(p.leftoverSavingsCents,0,p.start);if(p.savingsCents>0)assert.equal(p.savingsCents,p.availableCents-p.targetCents-p.prepayCents,p.start+': funded residual after living and installment payoff');
 }
 const first=r.events.find(e=>e.kind==='savings');
 assert.equal(first.date,'2026-12-07','накопичення лише після закриття кредитки й розстрочок');
 assert.ok(!r.events.some(e=>(e.id.startsWith('installment:')||e.kind==='prepay')&&e.date>=at(first.date).end),'після перших накопичень лишились платежі розстрочок');
});

test('early repayment goes to the installment with the smallest remaining balance first, the next one only after it is closed',()=>{
 const r=both(data(0));
 const p=r.periods.find(p=>p.start==='2026-10-21');
 // Станція: 14 100 залишку (3 × 4 700) менше за Ноутбук 27 900 після цього періоду, тож гаситься першою і повністю, решта на Ноутбук
 // порядок розподілу з виплати (payoutPrepay): спершу найменший залишок; p.prepay: та сама сума за розстрочками дня
 assert.deepEqual(p.payoutPrepay.map(x=>[x.creditId,x.cents]),[['5',1410000],['3',480000]]);
 assert.deepEqual(p.prepay.map(x=>[x.creditId,x.cents]),[['3',480000],['5',1410000]]);
 assert.deepEqual(r.events.filter(e=>e.kind==='prepay'&&e.date==='2026-10-21').map(e=>[e.id,e.name,e.amountCents,e.cashDeltaCents,e.debtDeltaCents]),
  [['prepay:3:2026-10-21','Дострокове погашення Ноутбук',480000,-480000,0],['prepay:5:2026-10-21','Дострокове погашення Станція',1410000,-1410000,0]]);
 assert.deepEqual(p.installmentsLeft.map(x=>[x.creditId,x.cents]),[['3',2620000]],'Станцію закрито, Ноутбук 31 000 − 4 800');
});

test('a closed installment disappears from the forecast; the schedule is conserved and the remaining balance may end with a partial payment',()=>{
 const r=both(data(0));
 // Станція закрита 21.10: жодного платежу в прогнозі; Ноутбук: 24.10 за планом (у резерві), решта закрита 06.11
 assert.deepEqual(r.events.filter(e=>e.id.startsWith('installment:')).map(e=>[e.id,e.amountCents]),[['installment:3:2026-10',310000]]);
 for(const [cid,m,n] of [['3',310000,10],['5',470000,3]])
  assert.equal(r.events.filter(e=>e.id.startsWith('installment:'+cid+':')||e.id.startsWith('prepay:'+cid+':')).reduce((s,e)=>s+e.amountCents,0),m*n,cid+': платежі подіями плюс дострокові = весь залишок графіка');
 // менше грошей (виплати по 33 000 і разова премія 5 000 1.11): дострокові частинами, залишок не кратний платежу (останній частковий)
 const low=data(0);low.salary.advance_amount=33000;low.salary.salary_amount=33000;low.fixed.push({id:9,name:'Премія',type:'income',amount:5000,day_of_month:1,end_date:'2026-11-01'});
 const q=both(low),left=d=>(q.periods.find(p=>p.start===d).installmentsLeft.find(x=>x.creditId==='3')||{cents:0}).cents;
 assert.deepEqual(['2026-11-06','2026-12-07','2027-01-06'].map(left),[2710000,1100000,0]);
 assert.notEqual(left('2026-12-07')%310000,0,'залишок 11 000: три платежі по 3 100 і частковий 1 700');
 assert.deepEqual(q.events.filter(e=>e.id.startsWith('installment:3:')).map(e=>[e.date,e.amountCents]),[['2026-10-24',310000],['2026-11-24',310000],['2026-12-24',310000]],'після закриття 06.01 платежів Ноутбука немає');
 assert.equal(q.events.find(e=>e.kind==='savings').date,'2027-01-06');
});

// v153 доповнення 7 (власник: «заощадження відкладаються в день заробітньої плати з того, що залишилося за поточний період, тобто в день
// отримання заробітньої плати ми відкладаємо з авансу і навпаки»): без боргів накопичення в день виплати = власні перед виплатою (залишок
// попереднього періоду), а з самої нової виплати нуль: її надлишок понад резерв і бюджет лишається у власних до наступної виплати.
test('without debts each payout saves the combined own residual after upcoming rent and living',()=>{
 const d=data(0);d.credits=[];d.accounts[0].balance=12000;
 const r=both(d,'2026-10-12','2027-01-31'),ps=r.periods.filter(p=>p.basis!=='current');
 for(const p of ps){
  const before=r.days.find(x=>x.date===p.start).openingCashCents;
  assert.equal(p.savingsCents,before+p.payoutCents-p.reserveCents-p.targetCents,p.start+': combined sources minus protected obligations and living');
  assert.equal(p.leftoverCents,before,p.start);
  // власні після розподілу = уся нова виплата (накопичень з неї немає, боргів немає)
  const after=r.events.filter(e=>e.date===p.start&&['payout','income','arrears','repay','prepay','savings'].includes(e.kind)).pop().cashAfterCents;
  assert.equal(after,p.reserveCents+p.targetCents,p.start+': protected own cash survives distribution');
 }
 assert.deepEqual(r.events.filter(e=>e.kind==='savings').map(e=>[e.date,e.amountCents]),
  [['2026-10-21',3000000],['2026-11-06',4000000],['2026-11-20',3000000],['2026-12-07',4000000],['2026-12-21',3000000],['2027-01-06',4000000],['2027-01-21',3000000]]);
 assert.equal(ps[0].savingsCents,3000000,'60 000 payout minus 10 000 rent and 20 000 living');
});
