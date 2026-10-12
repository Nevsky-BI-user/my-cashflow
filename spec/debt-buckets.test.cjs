// v145: кошики боргу кредитного рахунку за FIFO. Погашення гасять найстаріші кошики, тож залишок боргу
// складають найновіші витрати рахунку; борг, не більший за витрати поточного місяця, увесь у поточному місяці.
// Кожен випадок у TS і Python (повний паритет).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
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
const salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:51000,salary_amount:51000};
// Monobank-подібний рахунок: баланс з API, мітка сьогодні, збережений місяць боргу вересень (як було в проді)
const mono=(extra={})=>({id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:29070.45,credit_limit:50000,debt_month:'2026-09-01',balance_updated_at:'2026-10-12T07:00:00Z',...extra});
const tx=(id,date,amount,extra={})=>({id,account_id:3,type:'expense',amount,date,created_at:date+'T08:00:00Z',source:'mono',...extra});
// v151: виплата 21-го гасить і новіший борг (модель «власні >= 0»), тож перевіряємо кошики знімка: перша подія погашення кошика,
// її плановий день (правило 21-го M+1), договірний строк і сума кошика; погашення не пізніше планового дня
const buckets=r=>r.snapshot.accounts.flatMap(a=>a.debt_months.map(([m,v])=>{const id='repay:'+a.id+':'+m,e=r.events.find(e=>e.kind==='repay'&&(e.id===id||e.id.startsWith(id+':')));return {id,date:e&&e.date,plannedRepaymentDate:e&&e.plannedRepaymentDate,contractualDueDate:e&&e.contractualDueDate,amountCents:Math.round(v*100)};})).sort((x,y)=>String(x.plannedRepaymentDate).localeCompare(String(y.plannedRepaymentDate))||x.id.localeCompare(y.id));
const repay=buckets;

test('Mono: September spending repaid, October spending 29 070,45 is the October bucket due 24.11',()=>{
 const d={accounts:[{id:1,kind:'debit',balance:2519,debt:0},mono()],salary,fixed:[],credits:[],categories:[],
  transactions:[tx(1,'2026-09-15',20000),tx(2,'2026-10-02',20000,{type:'income'}),tx(3,'2026-10-03',15000),tx(4,'2026-10-08',14070.45)]};
 const r=both(d);
 const a=r.snapshot.accounts.find(a=>a.id===3);
 assert.deepEqual(a.debt_months,[['2026-10',29070.45]]);
 assert.equal(a.debtCents,2907045);
 const ev=repay(r);
 assert.equal(ev.length,1);
 assert.equal(ev[0].id,'repay:3:2026-10');
 assert.equal(ev[0].contractualDueDate,'2026-11-24');
 assert.equal(ev[0].amountCents,2907045);
 // не прострочене: дедлайн після сьогодні, плановане погашення не пізніше дедлайну і не в минулому
 assert.ok(ev[0].contractualDueDate>'2026-10-24');
 assert.ok(ev[0].date>='2026-10-12'&&ev[0].date<=ev[0].contractualDueDate,ev[0].date);
 assert.ok(!r.events.some(e=>e.kind==='repay'&&e.contractualDueDate<='2026-10-24'),'жодного погашення з дедлайном 24.10');
});

test('debt above this month spending: the rest goes to the previous month by spending, oldest first repaid',()=>{
 const d={accounts:[mono({debt:30000})],salary,fixed:[],credits:[],categories:[],
  transactions:[tx(1,'2026-08-20',5000),tx(2,'2026-09-15',12000),tx(3,'2026-10-03',20000)]};
 const r=both(d);
 assert.deepEqual(r.snapshot.accounts[0].debt_months,[['2026-09',10000],['2026-10',20000]]);
 assert.deepEqual(repay(r).map(e=>[e.id,e.contractualDueDate,e.amountCents]),[['repay:3:2026-09','2026-10-24',1000000],['repay:3:2026-10','2026-11-24',2000000]]);
});

test('debt above all known spending: the remainder stays in the stored older month',()=>{
 const d={accounts:[mono({debt:25000})],salary,fixed:[],credits:[],categories:[],transactions:[tx(1,'2026-10-03',20000)]};
 const r=both(d);
 assert.deepEqual(r.snapshot.accounts[0].debt_months,[['2026-09',5000],['2026-10',20000]]);
 // збережений місяць не старший за витрати: залишок у найранішому місяці витрат
 const d2={accounts:[mono({debt:25000,debt_month:'2026-10-01'})],salary,fixed:[],credits:[],categories:[],transactions:[tx(1,'2026-10-03',20000)]};
 assert.deepEqual(both(d2).snapshot.accounts[0].debt_months,[['2026-10',25000]]);
});

test('no spending on the account: stored debt month unchanged; debit accounts untouched',()=>{
 const d={accounts:[{id:1,kind:'debit',balance:1000,debt:0},mono()],salary,fixed:[],credits:[],categories:[],transactions:[{id:9,account_id:1,type:'expense',amount:300,date:'2026-10-05',created_at:'2026-10-05T08:00:00Z'}]};
 const r=both(d);
 assert.deepEqual(r.snapshot.accounts.find(a=>a.id===3).debt_months,[['2026-09',29070.45]]);
 assert.equal(r.snapshot.accounts.find(a=>a.id===1).debt_months.length,0);
});

test('manual credit card after the stamp: same buckets as before v145 (FIFO repayment)',()=>{
 const card={id:4,name:'Приват',kind:'credit',balance:0,debt:1000,credit_limit:30000,debt_month:'2026-09-01',balance_updated_at:'2026-10-01T09:00:00Z'};
 const t=(id,date,amount,type='expense')=>({id,account_id:4,type,amount,date,created_at:date+'T10:00:00Z'});
 const r=both({accounts:[card],salary,fixed:[],credits:[],categories:[],transactions:[t(1,'2026-10-03',500),t(2,'2026-10-05',300,'income')]});
 assert.deepEqual(r.snapshot.accounts[0].debt_months,[['2026-09',700],['2026-10',500]]);
});

test('mono-balance refresh never writes debt_month',()=>{
 const src=fs.readFileSync(path.join(root,'supabase/functions/mono-balance/index.ts'),'utf8');
 assert.ok(!/debt_month/.test(src),'«Оновити» Mono не має перезаписувати місяць боргу');
});
