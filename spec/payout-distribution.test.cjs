const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const code=html.split('/* PAYOUT DISTRIBUTION ADAPTER */')[1].split('/* END PAYOUT DISTRIBUTION ADAPTER */')[0];
const adapt=new Function(code+';return projectionPayoutDistribution')();
const kernel=import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
const fixture=()=>({accounts:[{id:'own',kind:'debit',balance:0,debt:0}],transactions:[],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:60000,budget_manual:15000},categories:[{id:'food',name:'Продукти',type:'expense',budget_limit:1}]});
async function project(data=fixture(),options={}){const opts={asof:'2026-10-20',through:'2026-12-01',...options};return{pr:(await kernel).financeProjection(data,opts),today:opts.asof};}
function verify(pr,today){
 const before=JSON.stringify(pr),v=adapt(pr,today);assert.equal(v.status,'available',JSON.stringify(v));assert.equal(JSON.stringify(pr),before,'adapter does not mutate kernel');
 const q=pr.periods.find(q=>q.start===pr.nextPlan.start),events=pr.events.filter(e=>e.date===q.start),sum=a=>a.reduce((n,x)=>n+x,0);
 const incomes=sum(events.filter(e=>e.kind==='payout'||e.kind==='income').map(e=>e.amountCents));
 const exits=sum(events.filter(e=>['repay','prepay','savings','arrears'].includes(e.kind)).map(e=>e.amountCents));
 assert.equal(q.openingCashCents+incomes-exits,v.pool.reserve+v.pool.free,'independent event cash conservation before daily spending');
 assert.equal(v.sources.total,v.arrears.paid+v.carry.repay+v.carry.prepay+v.carry.savings+v.pool.own);
 assert.equal(v.pool.own,v.pool.reserve+v.pool.repay+v.pool.prepay+v.pool.savings+v.pool.free);
 assert.equal(v.pool.free,v.placement.cash+v.placement.mono);
 assert.equal(v.budget.target,v.budget.covered+v.budget.gap);
 assert.equal(v.pool.free,v.budget.covered+v.budget.surplus);
 assert.equal(v.categories.reduce((n,c)=>n+c.cents,0),v.budget.target);
 assert.equal(v.schedule.reduce((n,d)=>n+d.cents,0),v.budget.target);
 for(const group of ['sources','carry','pool','budget','placement'])for(const n of Object.values(v[group]))assert.ok(Number.isSafeInteger(n)&&n>=0);
 if(v.periodComplete){const period=pr.events.filter(e=>e.date>=q.start&&e.date<q.end);assert.equal(v.period.newCredit,sum(period.map(e=>Math.max(0,e.debtDeltaCents))));assert.equal(v.period.short,sum(period.map(e=>e.shortCents||0)));}
 return v;
}
test('simple payout protects living and saves the remaining own funds once',async()=>{const {pr,today}=await project();const v=verify(pr,today);assert.equal(v.date,'2026-10-21');assert.equal(v.sources.payout,5000000);assert.equal(v.sources.opening,0);assert.equal(v.pool.free,1500000);assert.equal(v.pool.savings,3500000);assert.equal(v.budget.target,1500000);assert.deepEqual(v.placement,{cash:300000,mono:1200000});assert.equal(pr.events.filter(e=>e.kind==='savings'&&e.date===v.date).length,1);});
test('today payout excluded, weekend adjusted and simultaneous payouts summed',async()=>{
 for(const [asof,expected] of [['2026-10-21','2026-11-06'],['2026-11-19','2026-11-20']]){const {pr,today}=await project(fixture(),{asof,through:'2027-01-01'});assert.equal(verify(pr,today).date,expected);}
 const data=fixture();data.salary.salary_day=21;const {pr,today}=await project(data);const v=verify(pr,today);assert.equal(v.sources.payout,11000000);assert.equal(pr.events.filter(e=>e.kind==='payout'&&e.date===v.date).length,2);
});
test('same-day other income and arrears are separate, exact to cents',async()=>{
 const data=fixture();data.accounts[0].balance=-123.45;data.fixed=[{id:'extra',name:'Інший дохід',type:'income',amount:321.09,day_of_month:21}];data.salary.advance_amount=50000.37;
 const {pr,today}=await project(data);const v=verify(pr,today);assert.equal(v.sources.otherIncome,32109);assert.equal(v.sources.payout,5000037);assert.equal(v.arrears.paid,12345);assert.equal(v.arrears.remaining,0);
});
test('prior shortage can consume opening own funds and the entire payout',async()=>{
 const data=fixture();data.accounts[0].balance=5000;data.accounts.push({id:'overdrawn',kind:'debit',balance:-100000,debt:0});
 const {pr,today}=await project(data);const v=verify(pr,today);
 assert.equal(v.sources.opening,500000);assert.equal(v.sources.payout,5000000);
 assert.equal(v.arrears.paid,5500000);assert.equal(v.arrears.remaining,4500000);
 assert.equal(v.carry.total,0);assert.ok(v.carry.total<v.sources.opening);
 assert.equal(v.pool.own,0);assert.equal(v.pool.free,0);
});
test('opening own funds and payout form one protected pool for debt and savings',async()=>{
 const debt=fixture();debt.accounts[0].balance=20000;debt.accounts.push({id:'credit',kind:'credit',balance:0,debt:10000,credit_limit:30000,debt_month:'2026-09-01'});
 const a=await project(debt);const x=verify(a.pr,a.today);assert.equal(x.carry.repay,0);assert.equal(x.carry.savings,0);assert.equal(x.pool.repay,1000000);assert.equal(x.pool.savings,4500000);
 const inst=fixture();inst.accounts[0].balance=5000;inst.credits=[{id:'loan',name:'Розстрочка',monthly_amount:1000,payment_day:25,start_year:2026,start_month:9,total_payments:4}];
 const b=await project(inst);const y=verify(b.pr,b.today);assert.equal(y.carry.prepay,0);assert.equal(y.carry.savings,0);assert.equal(y.pool.prepay,300000);assert.equal(y.pool.savings,3600000);assert.equal(y.pool.reserve,100000,'next installment is protected before prepayment and savings');
 inst.accounts[0].balance=0;const c=await project(inst);assert.ok(verify(c.pr,c.today).pool.prepay>0,'prepay can come from new payout pool');
});
test('manual zero/high budgets, no fabricated credit source, integer rounding',async()=>{
 for(const manual of [0,15000.01,150000.03]){const data=fixture();data.salary.budget_manual=manual;data.salary.advance_amount=12345.67;const {pr,today}=await project(data);const v=verify(pr,today);assert.equal(v.budget.target,Math.round(manual*100));assert.equal(v.sources.total,1234567);assert.equal(v.budget.gap,Math.max(0,Math.round(manual*100)-1234567));}
});
test('scenario is explicit and period new credit is summed only once',async()=>{const data=fixture();data.accounts.push({id:'credit',kind:'credit',balance:0,debt:0,credit_limit:10000});data.fixed.push({id:'bill',name:'Платіж',type:'payment',amount:3000,day_of_month:25,credit_ok:true});const {pr,today}=await project(data,{scenario:{selections:[{occurrenceId:'fixed:bill:2026-10',accountId:'credit',amountCents:100000}]}});const v=verify(pr,today);assert.equal(v.scenario,true);assert.ok(v.period.newCredit>=100000);assert.equal(v.sources.payout,5000000);});
test('missing payout/record and partial horizon are honest',async()=>{
 assert.equal(adapt(null,'2026-10-20').reason,'no_future_payout');
 const a=await project(fixture(),{asof:'2026-10-19',through:'2026-10-20'});assert.equal(adapt(a.pr,a.today).reason,'outside_horizon');
 const b=await project(fixture(),{through:'2026-10-21'});const v=verify(b.pr,b.today);assert.equal(v.periodComplete,false);assert.equal(v.period,null);assert.ok(v.budget.target>0);
 const no=fixture();no.salary=null;const c=await project(no);assert.equal(adapt(c.pr,c.today).status,'unavailable');
});
test('corrupt or absent decomposition cannot silently show zeros',async()=>{const {pr,today}=await project();for(const key of ['ownCents','payoutCents','leftoverSavingsCents']){const bad=structuredClone(pr);delete bad.periods.find(q=>q.start===bad.nextPlan.start)[key];assert.equal(adapt(bad,today).status,'unavailable');}const bad=structuredClone(pr);bad.periods.find(q=>q.start===bad.nextPlan.start).reserveCents++;assert.equal(adapt(bad,today).reason,'inconsistent');});
test('synthetic positive Mono offset is netted once, not an extra source',async()=>{const {pr,today}=await project();const q=pr.periods.find(q=>q.start===pr.nextPlan.start);q.monoOffsetCents=12345;q.payoutRepayCents+=12345;q.repayCents+=12345;const v=adapt(pr,today);assert.equal(v.status,'available');assert.equal(v.pool.free,1500000-12345);assert.equal(v.placement.mono,1200000-12345);assert.equal(v.pool.repay,12345);assert.equal(v.sources.total,5000000);assert.equal(v.pool.savings,3500000);});

test('underfunded mandatory costs remain visible without inventing a reserve or savings',async()=>{const data=fixture();data.salary.advance_amount=10000;data.fixed=[{id:'bill',name:'Mandatory',type:'payment',amount:50000,day_of_month:25,credit_ok:true}];const {pr,today}=await project(data);const v=verify(pr,today);assert.equal(v.pool.requiredReserve,5000000);assert.equal(v.pool.reserve,1000000);assert.equal(v.pool.reserveGap,4000000);assert.equal(v.pool.savings,0);assert.equal(v.pool.free,0);});
