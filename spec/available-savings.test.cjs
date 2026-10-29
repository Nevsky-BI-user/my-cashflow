const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const load=n=>import('../supabase/functions/_shared/'+n+'.ts');
const html=fs.readFileSync('index.html','utf8');
const names=['spendableFunds','kpiFunds','balanceNowCents','projectedSavingsReserveCents','projectionGrouped'];
const helpers=names.map(n=>html.split(/\r?\n/).find(l=>l.startsWith('function '+n+'('))).join('\n');
const {spendableFunds,kpiFunds,projectedSavingsReserveCents,projectionGrouped}=new Function(helpers+';return {spendableFunds,kpiFunds,projectedSavingsReserveCents,projectionGrouped}')();
const categories=[{id:1,name:'Продукти',type:'expense',budget_limit:90},{id:77,name:' Заощадження ',type:'expense',active:false,budget_limit:10},{id:78,name:'Благодійність',type:'expense'}];
const row=(saving=310000)=>({month_start:'2026-10-01',total_cents:3100000,mandatory_items:[],allocations:{1:2790000,77:saving}});
const data=(saving=310000)=>({accounts:[{id:1,kind:'debit',balance:50000,debt:0,balance_updated_at:'2026-10-01T00:00:00Z'},{id:2,kind:'credit',balance:0,debt:0,credit_limit:10000}],salary:{rate:0,salary_amount:20000,advance_amount:10000,salary_day:21,advance_day:6,split_day:15,budget_manual:15000},fixed:[],credits:[],transactions:[],categories,monthly_budgets:[row(saving)]});

test('future reserve releases only funded monthly allocation savings already removed from cash',()=>{
 const events=[{id:'budget-savings:a',date:'2026-11-06',amountCents:62000,cashDeltaCents:-62000},
  {id:'budget-savings:unfunded',date:'2026-11-06',amountCents:90000,cashDeltaCents:0},
  {id:'savings:auto',date:'2026-11-06',cashDeltaCents:-50000},
  {id:'budget-savings:previous',date:'2026-10-31',cashDeltaCents:-50000},
  {id:'budget-savings:later',date:'2026-11-07',cashDeltaCents:-50000}];
 assert.equal(projectedSavingsReserveCents(310000,events,'2026-11-06'),248000);
 assert.equal(projectedSavingsReserveCents(10000,events,'2026-11-06'),0);
});

test('unfunded savings reservations do not become zero-value income rows in cash flow',()=>{
 const events=[{id:'budget-savings:unfunded',kind:'savings',amountCents:0},
  {id:'budget-savings:funded',kind:'savings',amountCents:10000},
  {id:'savings:auto',kind:'savings',amountCents:0},
  {id:'fixed:bill',kind:'mandatory',amountCents:5000}];
 assert.deepEqual(projectionGrouped(events).map(e=>e.id),['budget-savings:funded','savings:auto','fixed:bill']);
});

test('reserve deducts only positive own funds; negative baseline and unused credit preserved',()=>{
 for(const [own,credit,saved,deduction,total]of [[1000000,200000,310000,310000,890000],[100000,200000,310000,100000,200000],[-100000,200000,310000,0,100000],[-100000,200000,0,0,100000],[100000,200000,-310000,0,300000]])assert.deepEqual(spendableFunds(own,credit,saved),{deduction,total});
});
test('provisional monthly savings affects daily allocation but never deducts actual available funds',async()=>{
 const {monthlySavingsReserve}=await load('monthly-budget'),{financeProjection}=await load('budget'),{budgetModel}=await load('bot-reports');
 const options={asof:'2026-10-25',through:'2026-12-01'},before=data(0),after=data(),a=financeProjection(before,options),b=financeProjection(after,options);
 const reserve=monthlySavingsReserve(after.monthly_budgets,categories,[],'2026-10-25');assert.equal(reserve.reserveCents,0);assert.equal(reserve.plannedCents,310000);
 assert.equal(kpiFunds(a).total-kpiFunds(b,reserve.reserveCents).total,0);assert.deepEqual(a.snapshot,b.snapshot);
 assert.equal(a.currentPeriod.targetCents,b.currentPeriod.targetCents);assert.ok(b.currentPeriod.spendableRemainingCents<a.currentPeriod.spendableRemainingCents);
 const ma=budgetModel(a,[],categories,options.asof,before,before.accounts),mb=budgetModel(b,[],categories,options.asof,after,after.accounts);
 assert.ok(mb.dailyCents<ma.dailyCents);assert.equal(mb.leftCents,b.currentPeriod.spendableRemainingCents);assert.ok(!mb.rows.some(r=>r.id==='77'));
 assert.equal(monthlySavingsReserve([],categories,[],'2026-10-25').reserveCents,0);
 assert.doesNotMatch(html,/fundsSavingsCents=savingsAtCents|saved=savingsAtCents/);
});
test('saving facts are recorded once without a preemptive reserve; duplicates and links excluded',async()=>{
 const {monthlySavingsReserve:f}=await load('monthly-budget');const tx={id:1,date:'2026-10-24',type:'expense',category_id:77,amount:1000};
 const rows=[tx,tx,...['transfer_id','fixed_id','credit_id'].map((key,i)=>({...tx,id:i+2,[key]:9})),{...tx,id:8,date:'2026-10-26'}];
 const p=f([row()],categories,rows,'2026-10-25');assert.equal(p.factCents,100000);assert.equal(p.reserveCents,0);
 assert.equal(spendableFunds(1000000,200000,0).total-spendableFunds(900000,200000,p.reserveCents).total,100000);
 assert.equal(f([row()],categories,[{...tx,amount:5000}],'2026-10-25').reserveCents,0);
 assert.equal(f([row()],categories,rows,'2026-10-23').factCents,0);
 assert.equal(f([row()],categories,[],'2026-11-25').plannedCents,310000);assert.equal(f([row()],categories,[],'2026-11-25').reserveCents,0);
 assert.equal(f([row()],categories,[],'2026-09-25').reserveCents,0);
});
test('monthly saving prefixes conserve cents for 28/29/30/31 days, inherited and zero plans',async()=>{
 const {monthlyPeriodBudget:f}=await load('monthly-budget');
 for(const month of ['2026-02','2028-02','2026-04','2026-10']){
  const start=month+'-01',days=new Date(Date.UTC(+month.slice(0,4),+month.slice(5),0)).getUTCDate(),rows=[{...row(),month_start:start,allocations:{1:2789997,77:310003}}];let sum=0;
  for(let d=0;d<days;d++){const a=new Date(start+'T00:00:00Z');a.setUTCDate(1+d);const b=new Date(a);b.setUTCDate(b.getUTCDate()+1);const p=f(rows,a.toISOString().slice(0,10),b.toISOString().slice(0,10),{categories});sum+=p.savingsTargetCents;assert.equal(p.targetCents,p.savingsTargetCents+p.spendableTargetCents)}assert.equal(sum,310003);
 }
 assert.equal(f([{...row(),total_cents:0,allocations:{}}],'2026-11-01','2026-12-01',{categories}).savingsTargetCents,0);
});
test('savings projected own-only and funded amount reported; TS/Python parity including low funds',async()=>{
 const {financeProjection}=await load('budget');const cases=[0,50000].map(balance=>({data:{...data(),accounts:[{id:1,kind:'debit',balance,debt:0},{id:2,kind:'credit',balance:0,debt:0,credit_limit:10000}]},options:{asof:'2026-10-25',through:'2026-12-01'}}));
 const py=spawnSync(path.resolve('.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{input:JSON.stringify(cases),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});assert.equal(py.status,0,py.stderr);const expected=JSON.parse(py.stdout);
 cases.forEach((c,i)=>{const p=financeProjection(c.data,c.options);assert.deepEqual(p,expected[i]);assert.equal(p.events.filter(e=>e.budgetSavings).length,0);const ev=p.events.filter(e=>e.kind==='savings');assert.equal(new Set(ev.map(e=>e.date)).size,ev.length);for(const e of ev){assert.equal(e.cashDeltaCents,0-e.amountCents);assert.equal(e.debtDeltaCents,0);assert.ok(p.events.some(x=>x.kind==='payout'&&x.date===e.date))}assert.ok(!p.events.some(e=>e.kind==='variable'&&String(e.categoryId)==='77'));});
});

test('last day before payout retains consumable remainder today without forecasting today again',async()=>{
 const {financeProjection}=await load('budget'),{budgetModel}=await load('bot-reports');const d=data(),options={asof:'2026-11-05',through:'2026-12-01'},p=financeProjection(d,options),cp=p.currentPeriod;
 assert.equal(cp.end,'2026-11-06');assert.equal(cp.futureSchedule.length,1);assert.equal(cp.futureSchedule[0].date,options.asof);assert.equal(cp.futureSchedule[0].spendCents,cp.spendableRemainingCents);assert.equal(p.events.filter(e=>(e.kind==='variable'||e.budgetSavings)&&e.date===options.asof).length,0);assert.equal(cp.spendableRemainingCents,465000);assert.equal(cp.dailyCents,465000);
 const b=budgetModel(p,[],categories,options.asof,d,d.accounts);assert.equal(b.leftDays,1);assert.equal(b.leftCents,465000);assert.equal(b.dailyCents,465000);
 const py=spawnSync(path.resolve('.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{input:JSON.stringify([{data:d,options}]),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});assert.equal(py.status,0,py.stderr);assert.deepEqual(p,JSON.parse(py.stdout)[0]);
});
test('ordinary overrun compares spendable target; savings facts do not create ordinary overrun',async()=>{
 const {financeProjection}=await load('budget'),{budgetModel,formatDigest}=await load('bot-reports');const options={asof:'2026-10-25',through:'2026-12-01'},cases=[1,77].map(category_id=>({data:{...data(),transactions:[{id:1,account_id:1,category_id,type:'expense',amount:15000,date:'2026-10-24',created_at:'2026-10-24T12:00:00Z'}]},options}));
 const py=spawnSync(path.resolve('.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{input:JSON.stringify(cases),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});assert.equal(py.status,0,py.stderr);const expected=JSON.parse(py.stdout);
 cases.forEach((c,i)=>{const p=financeProjection(c.data,options);assert.deepEqual(p,expected[i]);assert.equal(p.currentPeriod.overrunCents,i===0?45000:0);const b=budgetModel(p,c.data.transactions,categories,options.asof,c.data,c.data.accounts),digest=formatDigest(p,[],c.data.transactions,options.asof,b);if(i===0)assert.match(digest,/перевитрата 450 ₴/);else assert.equal(p.currentPeriod.actualSpendableCents,0);});
});
