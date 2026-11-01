const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=[path.join(root,'.venv/Scripts/python.exe'),path.resolve(root,'../../..','.venv/Scripts/python.exe')].find(fs.existsSync);
function run(inputs){const json=JSON.stringify(inputs);const ts=spawnSync(process.execPath,['spec/ts_finance.mts'],{cwd:root,input:json,encoding:'utf8'});assert.equal(ts.status,0,ts.stderr);const result=JSON.parse(ts.stdout);const py=spawnSync(python,['scripts/budget_pool.py','--finance'],{cwd:root,input:json,encoding:'utf8'});assert.equal(py.status,0,py.stderr);assert.deepEqual(result,JSON.parse(py.stdout));return result;}
for(const [month,next,after] of [['2026-10','2026-11','2026-12'],['2026-12','2027-01','2027-02']]){
 test('completed month deficit survives boundary '+month,()=>{
 const data={accounts:[{id:1,kind:'debit',balance:50000}],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[{id:1,name:'Food',type:'expense',budget_limit:100}],monthly_budgets:[{month_start:month+'-01',total_cents:3100000,allocations:{1:3100000}},{month_start:next+'-01',total_cents:3100000,allocations:{1:3100000}},{month_start:after+'-01',total_cents:3100000,allocations:{1:3100000}}],transactions:[{id:1,type:'expense',amount:14000,category_id:1,date:month+'-25',created_at:month+'-25T12:00:00Z'}]};
 const dates=[month+'-31',next+'-01',next+'-02'];const rs=run(dates.map(asof=>({data,asof,through:after+'-08'})));
 const before=rs[0].currentPeriod.signedSpendableRemainingCents;
 for(const r of rs){assert.equal(r.currentPeriod.start,month+'-21');assert.equal(r.currentPeriod.signedSpendableRemainingCents,before);assert.equal(r.currentPeriod.futureSchedule.reduce((s,d)=>s+d.spendCents,0),Math.max(0,before));}
 // Наступний день не віднімає перенесену перевитрату вдруге.
 assert.equal(rs[1].currentPeriod.signedSpendableRemainingCents,rs[2].currentPeriod.signedSpendableRemainingCents);
 });
}

test('monthly due debt wins over discretionary budget and actual insufficiency stays visible',()=>{
 for(const cash of [10000,2000]){
 const data={accounts:[{id:1,kind:'debit',balance:cash},{id:2,kind:'credit',balance:0,debt:5000,debt_month:'2026-08-01',credit_limit:10000,mono_account_id:'synthetic'}],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[{id:1,name:'Food',type:'expense',budget_limit:100}],monthly_budgets:[{month_start:'2026-10-01',total_cents:3100000,allocations:{1:3100000}}],transactions:[]};
 const [r]=run([{data,asof:'2026-10-10',through:'2026-10-20'}]);const paid=r.events.filter(e=>e.kind==='repay').reduce((s,e)=>s+e.amountCents,0),available=Math.max(0,cash-5000)*100;
 assert.equal(paid,Math.min(5000,cash)*100);assert.equal(r.events.filter(e=>e.kind==='variable').reduce((s,e)=>s+e.amountCents,0),r.currentPeriod.futureSchedule.filter(d=>d.date>'2026-10-10').reduce((s,d)=>s+d.spendCents,0));assert.ok(r.currentPeriod.futureSchedule.every(d=>Math.abs(d.spendCents-available/11)<1));assert.equal(r.currentPeriod.spendableRemainingCents,available);assert.equal(r.currentPeriod.futureSchedule.reduce((s,e)=>s+e.spendCents,0),available);assert.equal(r.currentPeriod.dailyCents,available/11);assert.ok(r.days.every(d=>d.closingCashCents>=0&&d.debtCents>=0));assert.equal(r.snapshot.warnings.filter(w=>w.kind==='due_short').reduce((s,w)=>s+w.shortCents,0),Math.max(0,5000-cash)*100);
 }
});
test('payout monthly distribution honors reduced cash after mandatory debt',()=>{
 const data={accounts:[{id:1,kind:'debit',balance:0},{id:2,kind:'credit',balance:0,debt:8687.72,debt_month:'2026-10-01',credit_limit:30000,mono_account_id:'synthetic'}],fixed:[{id:1,name:'Mandatory',type:'expense',amount:34073.27,day_of_month:25}],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:69476.19,salary_amount:50000},categories:[{id:1,name:'Food',type:'expense',budget_limit:100}],monthly_budgets:[{month_start:'2026-11-01',total_cents:10000000,allocations:{1:10000000}},{month_start:'2026-12-01',total_cents:10000000,allocations:{1:10000000}}],transactions:[]};
 const [r]=run([{data,asof:'2026-11-19',through:'2026-12-07'}]);const p=r.periods.find(p=>p.start==='2026-11-20');assert.equal(p.repayCents,868772);assert.equal(p.dueShortCents,0);assert.equal(p.reserveCents,3407327);assert.equal(p.availableCents,2671520);assert.equal(p.schedule.reduce((s,e)=>s+e.spendCents,0),2671520);assert.equal(p.categories.reduce((s,c)=>s+c.totalCents,0),2671520);assert.ok(r.events.filter(e=>e.kind==='repay'&&e.id.startsWith('repay:2:2026-10')).every(e=>e.date<='2026-11-20'));assert.ok(r.days.every(d=>d.closingCashCents>=0));
});
test('future due within current period keeps remaining KPI and funded schedule aligned',()=>{
 const data={accounts:[{id:1,kind:'debit',balance:10000},{id:2,kind:'credit',balance:0,debt:5000,debt_month:'2026-09-01',credit_limit:10000,mono_account_id:'synthetic'}],fixed:[],credits:[],salary:{rate:0,advance_day:25,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[{id:1,name:'Food',type:'expense',budget_limit:100}],monthly_budgets:[{month_start:'2026-10-01',total_cents:3100000,allocations:{1:3100000}}],transactions:[]};
 const [r]=run([{data,asof:'2026-10-19',through:'2026-10-25'}]);const cp=r.currentPeriod,schedule=cp.futureSchedule.reduce((n,d)=>n+d.spendCents,0),events=r.events.filter(e=>e.kind==='variable'&&e.date<cp.end).reduce((n,e)=>n+e.amountCents,0);assert.equal(cp.end,'2026-10-26');assert.equal(cp.spendableRemainingCents,schedule);assert.equal(cp.signedSpendableRemainingCents,schedule);assert.equal(cp.dailyCents,schedule/7);assert.equal(events,cp.futureSchedule.filter(d=>d.date>'2026-10-19').reduce((n,d)=>n+d.spendCents,0));assert.ok(r.events.some(e=>e.kind==='repay'&&e.date==='2026-10-21'));assert.ok(r.days.every(d=>d.closingCashCents>=0));
});
