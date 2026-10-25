const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const load=n=>import('../supabase/functions/_shared/'+n+'.ts');
const cats=[{id:1,name:'A',type:'expense'},{id:2,name:'B',type:'expense'},{id:77,name:'Заощадження',type:'expense'}];
function input(amount=80,saved=0,savings=true){return{accounts:[{id:1,kind:'debit',balance:1000}],categories:cats,salary:{rate:0,salary_amount:1000,advance_amount:1000,salary_day:1,advance_day:1,split_day:15},fixed:[],credits:[],monthly_budgets:[{month_start:'2026-10-01',total_cents:savings?20000:10000,mandatory_items:[],allocations:{1:5000,2:5000,...(savings?{77:10000}:{})}}],transactions:[{id:1,type:'expense',category_id:1,amount,date:'2026-10-02',created_at:'2026-10-02T12:00:00Z'},...(saved?[{id:2,type:'expense',category_id:77,amount:saved,date:'2026-10-03',created_at:'2026-10-03T12:00:00Z'}]:[])]}}
const options={asof:'2026-10-10',through:'2026-12-01'};
const october=p=>p.currentPeriod.monthlyBudget.remainingSegments.find(s=>s.month==='2026-10-01');
test('ordinary overspend consumes shared pool without shrinking savings; savings fact releases reserve once',async()=>{
 const {financeProjection:f}=await load('budget');
 for(const [amount,saved,expected,saveRemain]of [[80,0,2000,10000],[90,0,1000,10000],[110,0,-1000,10000],[80,20,2000,8000],[80,120,0,0]]){
  const p=f(input(amount,saved),options),s=october(p);assert.equal(s.signedSpendableRemainingCents,expected);assert.equal(s.spendableTargetCents,Math.max(0,expected));assert.equal(s.savingsTargetCents,saveRemain);assert.ok(s.categories.every(c=>c.totalCents>=0));assert.equal(p.currentPeriod.monthlyBudget.rawTargetCents,p.currentPeriod.targetCents);
 }
 assert.equal(october(f(input(80,0,false),options)).spendableTargetCents,2000);
});
test('prior-period overspend immediately caps current daily pool; deficit exposed signed with zero daily',async()=>{
 const {financeProjection:f}=await load('budget'),{budgetModel,formatDigest,formatBudget}=await load('bot-reports'),{budgetLeftLine}=await load('finance-message');
 for(const amount of [80,90,130]){const d=input(amount);d.salary.salary_day=21;d.salary.advance_day=6;const p=f(d,options),expected=(100-amount)*100;assert.equal(p.currentPeriod.signedSpendableRemainingCents,expected);assert.equal(p.currentPeriod.spendableRemainingCents,Math.max(0,expected));assert.equal(p.currentPeriod.overrunCents,Math.max(0,-expected));const b=budgetModel(p,d.transactions,cats,options.asof,d,d.accounts);assert.equal(b.leftCents,expected);assert.equal(b.dailyCents,Math.round(Math.max(0,expected)/11));if(amount===130){assert.match(formatDigest(p,[],d.transactions,options.asof,b),/перевитрата 30 ₴/);assert.match(formatBudget(b),/перевитрата 30 ₴/);assert.match(budgetLeftLine(b),/перевитрата 30 ₴/);assert.doesNotMatch(formatBudget(b),/лишилось 0 ₴/);}}
});
test('TS, Python and embedded projection agree for savings/no savings/negative/linked duplicate facts',async()=>{
 const {financeProjection:f}=await load('budget');const cases=[];for(const amount of [0,80,110,230])for(const saved of [0,20,120]){const d=input(amount,saved);d.transactions.push({...d.transactions[0]},{id:9,type:'expense',category_id:1,amount:999,date:'2026-10-02',created_at:'2026-10-02T12:00:00Z',transfer_id:'linked'});cases.push({data:d,options});}cases.push({data:input(80,0,false),options});
 const py=spawnSync(path.resolve('.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{input:JSON.stringify(cases),maxBuffer:16*1024*1024,encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});assert.equal(py.status,0,py.stderr);const expected=JSON.parse(py.stdout),h=fs.readFileSync('index.html','utf8'),m=h.split('/* CANONICAL MONTHLY PERIOD BUDGET */')[1].split('/* END CANONICAL MONTHLY PERIOD BUDGET */')[0],b=h.split('/* CANONICAL FINANCE PROJECTION */')[1].split('/* END CANONICAL FINANCE PROJECTION */')[0],embedded=new Function(m+b+';return financeProjection')();cases.forEach((c,i)=>{const actual=f(c.data,c.options);assert.deepEqual(actual,expected[i],'Python '+i);assert.deepEqual(actual,embedded(c.data,c.options),'browser '+i)});
});
test('month-keyed caps do not charge October deficit again against inherited November plan',async()=>{
 const {financeProjection:f}=await load('budget');const p=f(input(130),options),m=p.currentPeriod.monthlyBudget;assert.equal(m.monthSignedSpendableCaps['2026-10-01'],-3000);assert.equal(m.monthSignedSpendableCaps['2026-11-01'],10000);const nov=m.remainingSegments.find(s=>s.month==='2026-11-01');assert.equal(nov.signedSpendableRemainingCents,nov.spendableTargetCents);assert.ok(nov.spendableTargetCents>0);assert.ok(!p.events.some(e=>e.amountCents<0));
});
