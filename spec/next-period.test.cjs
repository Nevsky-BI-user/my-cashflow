const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const base=()=>({accounts:[{id:1,kind:'debit',balance:2800,debt:0},{id:2,kind:'credit',balance:0,debt:16000,credit_limit:999999}],fixed:[{id:1,name:'Payment',type:'expense',amount:28000,day_of_month:25,credit_ok:true}],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[40,20,15,10,10,5].map((w,i)=>({id:String(i+1),name:'Category '+i,type:'expense',budget_limit:w})),transactions:[]});
function both(data,asof='2026-10-10') {
 const input=JSON.stringify([{data,asof}]);
 const run=(exe,args)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
 const ts=run(process.execPath,['spec/ts_next_period.mts']);
 const py=run(path.join(root,'.venv','Scripts','python.exe'),['scripts/budget_pool.py','--next-period']);
 assert.deepEqual(ts,py,'TS/Python full output parity');return ts;
}
function invariants(p){
 assert.equal(p.categories.reduce((s,c)=>s+c.totalCents,0),p.targetCents);
 assert.equal(p.schedule.reduce((s,d)=>s+d.spendCents,0),p.targetCents);
 let balance=p.baseAvailableCents;
 for(const d of p.schedule){assert.equal(d.byCategory.reduce((s,c)=>s+c.amountCents,0),d.spendCents);balance-=d.spendCents;assert.equal(d.remainingCents,balance);}
 for(const c of p.categories) assert.equal(p.schedule.reduce((s,d)=>s+d.byCategory.find(x=>x.id===c.id).amountCents,0),c.totalCents);
}
test('base formula, DST calendar days, exact weighted columns and daily rows',()=>{
 const p=both(base());assert.equal(p.baseAvailableCents,880000);assert.equal(p.targetCents,1500000);assert.equal(p.gapCents,620000);assert.equal(p.days,16);assert.equal(p.start,'2026-10-21');assert.equal(p.end,'2026-11-06');assert.equal(p.averageDailyCents,93750);assert.equal(p.eligibleMandatoryCents,2800000);assert.deepEqual(p.categories.map(c=>c.totalCents),[600000,300000,225000,150000,150000,75000]);invariants(p);
});
test('above floor and negative base retain full planned spending',()=>{let d=base();d.fixed[0].amount=10000;let p=both(d);assert.equal(p.baseAvailableCents,2680000);assert.equal(p.targetCents,2680000);assert.equal(p.gapCents,0);invariants(p);d=base();d.salary.advance_amount=10000;p=both(d);assert.equal(p.baseAvailableCents,-3120000);assert.equal(p.gapCents,4620000);invariants(p);});
test('positive credit own included, limit excluded, inactive accounts excluded',()=>{const d=base();d.accounts[1].balance=1200;d.accounts.push({id:3,balance:900000,debt:900000,kind:'credit',active:false});const p=both(d);assert.equal(p.positiveOwnCents,400000);assert.equal(p.debtCents,1600000);assert.equal(p.baseAvailableCents,1000000);});
test('paid partial fixed closes only transaction month; fixed income separate',()=>{const d=base();d.fixed=[{id:3,name:'Fixed',type:'expense',amount:3000,day_of_month:25},{id:4,name:'Extra',type:'income',amount:900,day_of_month:26}];d.transactions=[{account_id:1,type:'expense',amount:1000,fixed_id:3,date:'2026-10-10',created_at:'2026-10-10T12:00:00Z'}];let p=both(d);assert.equal(p.mandatoryCents,0);assert.equal(p.otherIncomeCents,90000);assert.equal(p.baseAvailableCents,3680000);p=both(d,'2026-11-10');assert.equal(p.mandatoryCents,300000);});
test('strict future on payday and unknown payout',()=>{const p=both(base(),'2026-10-21');assert.equal(p.start,'2026-11-06');assert.equal(p.end,'2026-11-20');const d=base();delete d.salary;assert.deepEqual(both(d),{plan:null,reason:'no_next_payout'});});
test('no weights gives explicit unallocated and exact fractional cents allocation',()=>{const d=base();d.categories=[];d.fixed=[];d.accounts=[];d.salary.advance_amount='15000.125';const p=both(d);assert.equal(p.targetCents,1500013);assert.equal(p.categories[0].id,'unallocated');invariants(p);d.categories=[{id:'z',type:'expense',limit:-4},{id:'a',type:'income',limit:999},{id:'x',type:'expense',active:false,limit:999}];assert.equal(both(d).categories.find(c=>c.id==='unallocated').totalCents,1500013);});
test('derived manual accounts and unassigned adjustment are applied once',()=>{const d=base();d.accounts[0].balance_updated_at='2026-10-01T00:00:00Z';d.accounts[1].balance_updated_at='2026-10-01T00:00:00Z';d.transactions=[{account_id:1,type:'expense',amount:100,created_at:'2026-10-09T00:00:00Z'},{account_id:2,type:'expense',amount:300,created_at:'2026-10-09T00:00:00Z'},{account_id:null,type:'expense',amount:200,created_at:'2026-10-09T00:00:00Z'},{account_id:null,type:'expense',amount:9999,source:'mono',created_at:'2026-10-09T00:00:00Z'}];const p=both(d);assert.equal(p.positiveOwnCents,250000);assert.equal(p.debtCents,1630000);assert.equal(p.baseAvailableCents,820000);});
test('installments are reserved even credit eligible; window excludes ending date',()=>{const d=base();d.fixed=[];d.credits=[{name:'Installment',monthly_amount:1234,payment_day:25,start_year:2026,start_month:9,total_payments:3,credit_ok:true}];d.fixed.push({name:'End',type:'expense',amount:999,day_of_month:6});const p=both(d);assert.equal(p.mandatoryCents,123400);assert.equal(p.eligibleMandatoryCents,123400);});
test('input category order cannot change allocation',()=>{const d=base();const p=both(d);d.categories.reverse();assert.deepEqual(both(d),p);});
test('unallocated Ukrainian name and duplicate fallback id',()=>{const d=base();d.categories=[{id:'unallocated',type:'expense',budget_limit:0}];const p=both(d);assert.equal(p.categories.length,1);assert.equal(p.categories[0].name,'Не розподілено');invariants(p);});
test('salary days 29-31 follow existing calendar rollover and weekend rules',()=>{const d=base();d.salary.advance_day=31;d.salary.salary_day=15;let p=both(d,'2026-10-16');assert.equal(p.start,'2026-10-30');assert.equal(p.end,'2026-11-16');p=both(d,'2026-02-16');assert.equal(p.start,'2026-03-03');assert.equal(p.end,'2026-03-16');});
test('credit eligibility requires explicit flag regardless of installment source',()=>{const d=base();d.fixed=[];d.credits=[{name:'Installment',monthly_amount:1234,payment_day:25,start_year:2026,start_month:9,total_payments:3,source:'privat'}];const p=both(d);assert.equal(p.mandatoryCents,123400);assert.equal(p.eligibleMandatoryCents,0);});
test('previous month payout rolling into current month remains the nearest',()=>{const d=base();d.salary.advance_day=31;d.salary.salary_day=15;const p=both(d,'2026-03-01');assert.equal(p.start,'2026-03-03');assert.equal(p.end,'2026-03-16');});
// v149 (міграція 29): обовʼязкові й інші доходи нового періоду без подій після end_date (включно), щомісяця і щотижня
test('fixed end_date excludes obligations and income after the last date',()=>{
 const d=base();d.fixed=[{id:3,name:'Fixed',type:'expense',amount:3000,day_of_month:25,end_date:'2026-10-24'},{id:4,name:'Extra',type:'income',amount:900,day_of_month:26,end_date:'2026-10-26'},{id:5,name:'Weekly',type:'expense',amount:100,day_of_month:1,period:'week',weekday:1,end_date:'2026-10-27'}];
 const p=both(d);
 assert.equal(p.mandatoryCents,10000,'Fixed ended before 25th; Weekly only 26.10 (Monday) in [21.10; 06.11)');
 assert.equal(p.otherIncomeCents,90000,'Extra on its last date 26.10 counts');
 d.fixed[1].end_date='2026-10-25';assert.equal(both(d).otherIncomeCents,0);
});
