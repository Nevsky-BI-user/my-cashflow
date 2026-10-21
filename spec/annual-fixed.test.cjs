// Річні платежі й дострокові оплати: незалежні очікування та повний TS/Python-паритет.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const fixture=()=>({accounts:[{id:1,kind:'debit',balance:3000,debt:0}],fixed:[],credits:[],categories:[],transactions:[]});
const annual=(extra={})=>({id:7,name:'Підписка Claude',amount:100,type:'expense',period:'year',month_of_year:11,day_of_month:15,...extra});
const tx=(extra={})=>({id:1,account_id:1,type:'expense',amount:100,date:'2026-12-20',created_at:'2026-12-20T12:00:00Z',...extra});
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input:JSON.stringify(input),encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr||p.error?.message);return JSON.parse(p.stdout);};
function both(data,opts={}){
 const input=[{data,asof:'2026-10-10',through:'2027-01-31',...opts}];
 const ts=run(process.execPath,['spec/ts_finance.mts'],input)[0];
 assert.deepEqual(ts,run(python,['scripts/budget_pool.py','--finance'],input)[0],'full TS/Python parity');
 return ts;
}
const fixed=r=>r.events.filter(e=>e.id.startsWith('fixed:'));
test('annual payment occurs once in its chosen month, including annual income',()=>{
 const d=fixture();d.fixed=[annual(),annual({id:8,type:'income',month_of_year:12,amount:70})];
 const e=fixed(both(d));assert.deepEqual(e.map(x=>[x.id,x.date,x.kind,x.amountCents]),[['fixed:7:2026-11','2026-11-15','mandatory',10000],['fixed:8:2026-12','2026-12-15','income',7000]]);
});
test('annual leap day clamps to February 28 and preserves leap year February 29',()=>{
 const d=fixture();d.fixed=[annual({month_of_year:2,day_of_month:29})];
 assert.equal(fixed(both(d,{asof:'2027-02-01',through:'2027-03-01'}))[0].date,'2027-02-28');
 assert.equal(fixed(both(d,{asof:'2028-02-01',through:'2028-03-01'}))[0].date,'2028-02-29');
});
test('annual payment obeys active and inclusive end date; malformed month never repeats',()=>{
 for(const extra of [{active:false},{end_date:'2026-11-14'},{month_of_year:null},{month_of_year:13}]){
  const d=fixture();d.fixed=[annual(extra)];assert.equal(fixed(both(d)).length,0);
 }
 const d=fixture();d.fixed=[annual({end_date:'2026-11-15'})];assert.equal(fixed(both(d)).length,1);
});
test('December actual payment closes January rent only and cash moves on actual date',()=>{
 const d=fixture();d.accounts[0].balance_updated_at='2026-12-01T00:00:00Z';
 d.fixed=[annual({period:'month',month_of_year:null,day_of_month:25})];d.transactions=[tx({fixed_id:7,payment_due_date:'2027-01-25'})];
 const r=both(d,{asof:'2026-12-20',through:'2027-02-28'});
 assert.equal(r.snapshot.cashCents,290000);assert.ok(fixed(r).some(e=>e.id==='fixed:7:2026-12'));assert.ok(!fixed(r).some(e=>e.id==='fixed:7:2027-01'));assert.ok(fixed(r).some(e=>e.id==='fixed:7:2027-02'));
});
test('annual advance from previous year closes target year, next year stays planned',()=>{
 const d=fixture();d.fixed=[annual({month_of_year:1})];d.transactions=[tx({fixed_id:7,payment_due_date:'2027-01-15'})];
 assert.equal(fixed(both(d,{asof:'2027-01-01',through:'2027-02-01'})).length,0);
 assert.equal(fixed(both(d,{asof:'2028-01-01',through:'2028-02-01'})).length,1);
});
test('weekly advance across year closes selected week, leaving actual week open',()=>{
 const d=fixture();d.fixed=[annual({period:'week',weekday:5})];d.transactions=[tx({date:'2026-12-24',created_at:'2026-12-24T12:00:00Z',fixed_id:7,payment_due_date:'2027-01-01'})];
 const ids=fixed(both(d,{asof:'2026-12-24',through:'2027-01-10'})).map(e=>e.date);
 assert.deepEqual(ids,['2026-12-25','2027-01-08']);
});
test('correcting or unlinking an existing expense changes obligation only and never duplicates cash',()=>{
 const d=fixture();d.salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:5000,salary_amount:5000};d.fixed=[annual()];d.transactions=[tx({date:'2026-11-10',created_at:'2026-11-10T12:00:00Z'})];
 const before=both(d,{asof:'2026-11-10',through:'2026-11-20'});
 d.transactions[0].fixed_id=7;d.transactions[0].payment_due_date='2026-11-15';
 const after=both(d,{asof:'2026-11-10',through:'2026-11-20'});
 assert.equal(after.snapshot.cashCents,before.snapshot.cashCents);assert.equal(before.currentPeriod.actualVariableCents,10000);assert.equal(after.currentPeriod.actualVariableCents,0);assert.equal(fixed(after).length,0);assert.equal(fixed(before).length,1);
 delete d.transactions[0].fixed_id;delete d.transactions[0].payment_due_date;
 assert.deepEqual(both(d,{asof:'2026-11-10',through:'2026-11-20'}),before);
});
test('legacy null due date closes actual month and ignores income links',()=>{
 const d=fixture();d.fixed=[annual({period:'month',day_of_month:25})];d.transactions=[tx({fixed_id:7,payment_due_date:null})];
 assert.deepEqual(fixed(both(d,{asof:'2026-12-20',through:'2027-01-31'})).map(e=>e.date),['2027-01-25']);
 d.transactions[0].type='income';assert.equal(fixed(both(d,{asof:'2026-12-20',through:'2027-01-31'})).length,2);
});
test('early installment closes selected month only (without salary-driven automatic prepayment)',()=>{
 const d=fixture();d.credits=[{id:3,name:'Ноутбук',monthly_amount:100,payment_day:25,start_year:2026,start_month:0,total_payments:24}];d.transactions=[tx({credit_id:3,payment_due_date:'2027-01-25'})];
 const ids=both(d,{asof:'2026-12-20',through:'2027-02-28'}).events.filter(e=>e.id.startsWith('installment:')).map(e=>e.id);
 assert.deepEqual(ids,['installment:3:2026-12','installment:3:2027-02']);
});
test('next-period legacy engine shares annual and explicit advance semantics',()=>{
 const d=fixture();d.salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:5000,salary_amount:5000};d.fixed=[annual({month_of_year:12,day_of_month:25})];
 function next(){const input=[{data:d,asof:'2026-12-10'}];const ts=run(process.execPath,['spec/ts_next_period.mts'],input)[0];assert.deepEqual(ts,run(python,['scripts/budget_pool.py','--next-period'],input)[0]);return ts;}
 assert.equal(next().mandatoryCents,10000);d.transactions=[tx({date:'2026-11-20',created_at:'2026-11-20T12:00:00Z',fixed_id:7,payment_due_date:'2026-12-25'})];assert.equal(next().mandatoryCents,0);
 d.fixed=[];d.credits=[{id:3,name:'Ноутбук',monthly_amount:100,payment_day:25,start_year:2026,start_month:0,total_payments:24}];d.transactions=[tx({credit_id:3,payment_due_date:'2026-12-25'})];assert.equal(next().mandatoryCents,0);
});
