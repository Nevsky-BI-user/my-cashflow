const {test}=require('node:test'),assert=require('node:assert/strict');const {pathToFileURL}=require('node:url');const path=require('node:path');const load=n=>import(pathToFileURL(path.resolve('supabase/functions/_shared/'+n+'.ts')).href);
const row=(month,total,allocations={},mandatory_items=[])=>({month_start:month+'-01',total_cents:total,allocations,mandatory_items});
const salary={rate:0,salary_amount:50000,advance_amount:50000,salary_day:21,advance_day:6,split_day:15,budget_manual:15000};
const data={accounts:[{id:1,name:'Cash',kind:'debit',balance:10000,debt:0,balance_updated_at:'2026-10-01T00:00:00Z'}],salary,fixed:[],credits:[],categories:[{id:1,name:'Food',type:'expense',budget_limit:99},{id:2,name:'Other',type:'expense',budget_limit:1}],transactions:[]};
test('monthly pool subtracts obligation snapshot and preserves exact allocations plus unallocated',async()=>{
 const {monthlyPeriodBudget:f}=await load('monthly-budget'),rows=[row('2026-10',100000,{1:60000},[{amount_cents:30000}])];const p=f(rows,'2026-10-01','2026-11-01');assert.equal(p.targetCents,70000);assert.equal(p.categories[0].totalCents,60000);assert.equal(p.unallocatedCents,10000);assert.equal(p.estimated,false);
});
test('category daily prefixes conserve odd cents leap month and crossmonth inheritance provenance',async()=>{
 const {monthlyPeriodBudget:f}=await load('monthly-budget'),rows=[row('2028-02',101,{1:61,2:29})];let sums={1:0,2:0,u:0};for(let d=1;d<=29;d++){const a='2028-02-'+String(d).padStart(2,'0'),b=d===29?'2028-03-01':'2028-02-'+String(d+1).padStart(2,'0'),p=f(rows,a,b);for(const c of p.categories)sums[c.id]+=c.totalCents;sums.u+=p.unallocatedCents;}assert.deepEqual(sums,{1:61,2:29,u:11});const p=f(rows,'2028-02-21','2028-03-06');assert.equal(p.segments.length,2);assert.equal(p.estimated,true);assert.deepEqual(p.sourceMonths,['2028-02-01']);
});
test('saved zero is authoritative, prior history legacy, mixed legacy slices are explicit',async()=>{
 const {monthlyPeriodBudget:f}=await load('monthly-budget'),rows=[row('2026-11',0)];assert.equal(f(rows,'2026-11-01','2026-12-01',{legacyTargetCents:1500000}).targetCents,0);assert.equal(f(rows,'2026-10-01','2026-11-01',{legacyTargetCents:99}).covered,false);const p=f(rows,'2026-10-21','2026-11-06',{legacyTargetCents:1600,legacyAllocations:{1:1600}});assert.equal(p.targetCents,1100);assert.equal(p.legacy,true);assert.equal(p.covered,true);
});
test('engine current and payout periods use saved plans rather than global 15000 and category weights',async()=>{
 const {financeProjection}=await load('budget'),{monthlyPeriodBudget:f}=await load('monthly-budget'),rows=[row('2026-10',310000,{1:155000,2:124000})];const p=financeProjection({...data,monthly_budgets:rows},{asof:'2026-10-21',through:'2026-12-01'});assert.equal(p.currentPeriod.targetCents,f(rows,p.currentPeriod.start,p.currentPeriod.end).targetCents);assert.equal(p.nextPlan.targetCents,f(rows,p.nextPlan.start,p.nextPlan.end).targetCents);assert.equal(p.nextPlan.categories.find(c=>c.id==='1').totalCents,f(rows,p.nextPlan.start,p.nextPlan.end).categories.find(c=>c.id==='1').totalCents);const zero=financeProjection({...data,monthly_budgets:[row('2026-10',0)]},{asof:'2026-10-21',through:'2026-12-01'});assert.equal(zero.currentPeriod.targetCents,0);assert.equal(zero.nextPlan.targetCents,0);
});
test('earlier period actual spending caps current month future, transfers/fixed do not consume plan',async()=>{
 const {financeProjection}=await load('budget'),rows=[row('2026-10',310000,{1:310000})],tx={id:1,type:'expense',amount:3000,account_id:1,category_id:1,date:'2026-10-10',created_at:'2026-10-10T10:00:00Z'};const p=financeProjection({...data,transactions:[tx],monthly_budgets:rows},{asof:'2026-10-21',through:'2026-11-01'});const october=p.currentPeriod.futureSchedule.filter(s=>s.date<'2026-11-01').reduce((n,s)=>n+s.spendCents,0);assert.ok(october<=10000,october);const excluded=financeProjection({...data,transactions:[{...tx,transfer_id:'t'}],monthly_budgets:rows},{asof:'2026-10-21',through:'2026-11-01'});assert.ok(excluded.currentPeriod.remainingTargetCents>p.currentPeriod.remainingTargetCents);
});
test('empty monthly input preserves exact legacy result',async()=>{
 const {financeProjection}=await load('budget'),opt={asof:'2026-10-21',through:'2026-11-01'};assert.deepEqual(financeProjection(data,opt),financeProjection({...data,monthly_budgets:[]},opt));
});
test('monthly loader reads every page and rejects lookup failures',async()=>{
 const {loadMonthlyBudgets}=await load('bot-data');const seen=[];const sb={from(name){assert.equal(name,'monthly_budgets');return {select(){return this},order(){return this},range(a,b){seen.push([a,b]);return Promise.resolve({data:a===0?Array.from({length:1000},()=>row('2026-10',1)):[row('2026-11',0)],error:null})}}}};
 assert.equal((await loadMonthlyBudgets(sb)).length,1001);assert.deepEqual(seen,[[0,999],[1000,1999]]);
 const failed={from(){return {select(){return this},order(){return this},range(){return Promise.resolve({data:null,error:{message:'offline'}})}}}};await assert.rejects(()=>loadMonthlyBudgets(failed),/monthly budgets lookup failed/);
});
test('bot category model retains exact plans and separate unallocated pool',async()=>{
 const {financeProjection}=await load('budget'),{budgetModel}=await load('bot-reports');const input={...data,monthly_budgets:[row('2026-10',310000,{1:62000,2:155000})]};const p=financeProjection(input,{asof:'2026-10-21',through:'2026-12-01'}),m=budgetModel(p,[],data.categories,'2026-10-21',input,data.accounts);
 assert.ok(m);assert.equal(m.poolCents,p.currentPeriod.monthlyBudget.rawTargetCents);for(const c of p.currentPeriod.monthlyBudget.rawCategories)assert.equal(m.rows.find(r=>r.id===c.id).plan,c.totalCents);assert.equal(m.rows.find(r=>r.id==='unallocated').plan,p.currentPeriod.monthlyBudget.rawUnallocatedCents);
});
test('repayment advice reserves monthly remaining budget including authoritative zero',async()=>{
 const {financeProjection}=await load('budget'),{repaymentAdvice}=await load('repayment');const input={...data,accounts:[{...data.accounts[0],balance:20000},{id:2,name:'Debt',kind:'credit',active:true,balance:0,debt:20000,balance_updated_at:'2026-10-01T00:00:00Z'}],monthly_budgets:[row('2026-10',0)]};const p=financeProjection(input,{asof:'2026-10-21',through:'2026-12-01'});const a=repaymentAdvice(input,p,1,'2026-10-21');assert.equal(a.availableCents,2000000);
});
test('bot spendable and daily use canonical month cap while raw period label remains intact',async()=>{
 const {financeProjection}=await load('budget'),{budgetModel,perDayOf}=await load('bot-reports');const input={...data,monthly_budgets:[row('2026-10',310000,{1:310000})],transactions:[{id:1,type:'expense',amount:3000,account_id:1,category_id:1,date:'2026-10-10',created_at:'2026-10-10T10:00:00Z'}]};const p=financeProjection(input,{asof:'2026-10-21',through:'2026-12-01'}),m=budgetModel(p,input.transactions,data.categories,'2026-10-21',input,data.accounts);assert.equal(m.leftCents,p.currentPeriod.remainingTargetCents);assert.equal(m.poolCents,p.currentPeriod.targetCents);assert.equal(m.dailyCents,perDayOf(p.currentPeriod.remainingTargetCents,'2026-10-21',p.currentPeriod.start,p.currentPeriod.end));assert.ok(m.leftCents<m.poolCents-m.spentCents);
});
