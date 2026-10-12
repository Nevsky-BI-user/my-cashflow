// v146: борг кредитки гаситься за місяцем, у якому він виник (рішення власника 12.10.2026).
// Борг місяця M гаситься з виплати 21-го числа в місяці M+1, як би її не названо в налаштуваннях;
// субота й неділя зсуваються, як сама виплата (21.11.2026 субота, виплата 20.11). Кожен випадок у TS і Python.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(data,asof='2026-10-12'){
 const input=JSON.stringify([{data,asof,through:'2026-12-31'}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
// як у проді: виплата 21-го в налаштуваннях записана як advance_day
const salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:51000,salary_amount:51000};
const stamp='2026-10-12T07:00:00Z';
const mono={id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:29070.45,credit_limit:50000,debt_month:'2026-10-01',balance_updated_at:stamp};
const privat={id:4,name:'ПриватБанк',kind:'credit',balance:0,debt:9256.55,credit_limit:30000,debt_month:'2026-09-01',balance_updated_at:stamp};
const repay=r=>r.events.filter(e=>e.kind==='repay').map(e=>[e.id,e.date,e.contractualDueDate,e.amountCents]);
// дата виплати 21-го числа місяця M+1 з подій рушія (та сама подія, що на графіку і в боті)
const payout21=(r,month)=>r.events.find(e=>e.kind==='payout'&&e.date.slice(0,7)===month&&Math.abs(Number(e.date.slice(8))-21)<=1).date;

test('October debt is repaid from the 21st payout of November, September debt from 21.10',()=>{
 const r=both({accounts:[{id:1,kind:'debit',balance:2519,debt:0},mono,privat],salary,fixed:[],credits:[],categories:[],transactions:[]});
 assert.equal(payout21(r,'2026-11'),'2026-11-20','21.11.2026 субота: виплата в пʼятницю 20.11');
 assert.equal(payout21(r,'2026-10'),'2026-10-21','21.10.2026 середа');
 assert.deepEqual(repay(r),[['repay:4:2026-09','2026-10-21','2026-10-24',925655],['repay:3:2026-10','2026-11-20','2026-11-24',2907045]]);
 for(const e of r.events.filter(e=>e.kind==='repay'))assert.equal(e.date,payout21(r,e.contractualDueDate.slice(0,7)));
});

test('the payout day 21 decides, not its name: salary_day 21 gives the same dates',()=>{
 const sw={...salary,advance_day:6,salary_day:21};
 const r=both({accounts:[mono,privat],salary:sw,fixed:[],credits:[],categories:[],transactions:[]});
 assert.deepEqual(repay(r).map(e=>e[1]),['2026-10-21','2026-11-20']);
});

test('partial FIFO: a repayment closes the oldest bucket first, the rest keeps its own month',()=>{
 // ручна кредитка: на мітці борг вересня 10 000; після мітки витрати жовтня 6 000, погашення 12 000
 const card={id:5,name:'Картка',kind:'credit',balance:0,debt:10000,credit_limit:40000,debt_month:'2026-09-01',balance_updated_at:'2026-10-01T07:00:00Z'};
 const t=(id,date,amount,type='expense')=>({id,account_id:5,type,amount,date,created_at:date+'T08:00:00Z',source:'manual'});
 const r=both({accounts:[card],salary,fixed:[],credits:[],categories:[],transactions:[t(1,'2026-10-03',6000),t(2,'2026-10-05',12000,'income')]});
 assert.deepEqual(r.snapshot.accounts[0].debt_months,[['2026-10',4000]]);
 assert.deepEqual(repay(r),[['repay:5:2026-10','2026-11-20','2026-11-24',400000]]);
 // часткове погашення вересня: лишається 3 000 вересня (21.10) і 6 000 жовтня (20.11)
 const r2=both({accounts:[card],salary,fixed:[],credits:[],categories:[],transactions:[t(1,'2026-10-03',6000),t(2,'2026-10-05',7000,'income')]});
 assert.deepEqual(repay(r2),[['repay:5:2026-09','2026-10-21','2026-10-24',300000],['repay:5:2026-10','2026-11-20','2026-11-24',600000]]);
});

test('overdue bucket repays today; without a payout on the 21st the old rule stays',()=>{
 const r=both({accounts:[{...privat,debt_month:'2026-08-01'}],salary,fixed:[],credits:[],categories:[],transactions:[]});
 assert.deepEqual(repay(r).map(e=>e[1]),['2026-10-12']);
 const r2=both({accounts:[mono],salary:{...salary,advance_day:20},fixed:[],credits:[],categories:[],transactions:[]});
 assert.deepEqual(repay(r2).map(e=>e[1]),['2026-10-20'],'перша виплата до 24.11');
});

test('stored debt_month is the oldest month: older spending in history does not roll the debt back',()=>{
 // Monobank: збережено жовтень; в історії витрати вересня (уже погашені) і жовтня 20 000 при боргу 29 070,45
 const t=(id,date,amount)=>({id,account_id:3,type:'expense',amount,date,created_at:date+'T08:00:00Z',source:'mono'});
 const r=both({accounts:[mono],salary,fixed:[],credits:[],categories:[],transactions:[t(1,'2026-09-10',15000),t(2,'2026-10-03',20000)]});
 assert.deepEqual(r.snapshot.accounts[0].debt_months,[['2026-10',29070.45]]);
 assert.deepEqual(repay(r).map(e=>e[1]),['2026-11-20']);
 // без збереженого місяця залишок понад витрати жовтня лишається у вересні, як у v145
 const {debt_month,...bare}=mono;
 const r2=both({accounts:[bare],salary,fixed:[],credits:[],categories:[],transactions:[t(1,'2026-09-10',15000),t(2,'2026-10-03',20000)]});
 assert.deepEqual(r2.snapshot.accounts[0].debt_months,[['2026-09',9070.45],['2026-10',20000]]);
});
