const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const mod=f=>import(pathToFileURL(path.join(root,'supabase/functions/_shared',f+'.ts')).href);
function fixture(){return {accounts:[{id:1,kind:'debit',balance:50000}],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[{id:1,name:'Food',type:'expense',budget_limit:100}],monthly_budgets:['10','11','12'].map(m=>({month_start:`2026-${m}-01`,total_cents:3100000,allocations:{1:3100000}})),transactions:[{id:1,type:'expense',amount:25000,category_id:1,date:'2026-10-10'},{id:2,type:'expense',amount:10000,category_id:1,date:'2026-10-25'},{id:3,type:'expense',amount:2000.03,category_id:1,date:'2026-11-01'}]};}
function parity(cases,expected){const r=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{cwd:root,input:JSON.stringify(cases),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'},maxBuffer:16*1024*1024});assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),expected);}
test('closed month deficit and nominal unused budget reconcile through Oct 31 → Nov 1 to exact cents',async()=>{
 const {financeProjection}=await mod('budget'),data=fixture();data.transactions.forEach(t=>t.created_at=t.date+'T12:00:00Z');const before=structuredClone(data);
 const cases=['2026-10-31','2026-11-01'].map(asof=>({data,options:{asof,through:'2026-11-07'}}));
 const results=cases.map(c=>financeProjection(c.data,c.options));parity(cases,results);assert.deepEqual(data,before);
 for(const p of results){const cp=p.currentPeriod,r=cp.reconciliation;assert.equal(cp.start,'2026-10-21');assert.equal(r.plannedCents-r.actualCents-r.adjustmentCents,r.signedRemainingCents);assert.equal(r.availableCents,Math.max(0,r.signedRemainingCents));assert.equal(r.overrunCents,Math.max(0,-r.signedRemainingCents));assert.ok(Object.values(r).every(Number.isSafeInteger));assert.ok(p.days.every(d=>d.arrearsCents===0));}
 const a=results[0].currentPeriod.reconciliation,b=results[1].currentPeriod.reconciliation;
 assert.equal(b.actualCents-a.actualCents,200003);assert.equal(a.signedRemainingCents-b.signedRemainingCents,200003);
 assert.equal(b.adjustmentCents,500000); // 4000 грн дефіциту жовтня + 1000 грн невикористаного плану 21–31 жовтня.
 assert.equal(b.signedRemainingCents,516666-400000-200003);assert.equal(results[1].currentPeriod.dailyCents,0);
 const rep=await mod('bot-reports'),m=rep.budgetModel(results[1],data.transactions,data.categories,'2026-11-01',data,data.accounts);
 assert.deepEqual(m.reconciliation,b);assert.equal(m.leftCents,b.signedRemainingCents);assert.notEqual(m.poolCents-m.spentCents,m.leftCents);
 assert.equal(m.rows.find(r=>r.id==='1').fact,1200003);assert.match(rep.formatBudget(m),/Звірка: план/);assert.match(rep.formatDigest(results[1],[],data.transactions,'2026-11-01',m),/Звірка: план/);
});
test('metadata leaves every pre-existing forecast field unchanged, including legacy and missing periods',async()=>{
 const {financeProjection}=await mod('budget');
 // Виконуємо цей самий рушій без єдиного нового блоку метаданих: диференційна перевірка фінансового стану.
 const fs=require('node:fs'),{stripTypeScriptTypes}=require('node:module');
 let source=fs.readFileSync(path.join(root,'supabase/functions/_shared/budget.ts'),'utf8');
 source=source.replace(/  \/\/ Звірка пояснює[\s\S]*?  const visible=/,'  const visible=');
 source=source.replace(/from '\.\/([^']+)'/g,(_,f)=>`from '${pathToFileURL(path.join(root,'supabase/functions/_shared',f)).href}'`);
 const old=await import('data:text/javascript;base64,'+Buffer.from(stripTypeScriptTypes(source)).toString('base64'));
 const monthly=fixture(),legacy=fixture(),missing=fixture();for(const d of [monthly,legacy,missing])d.transactions.forEach(t=>t.created_at=t.date+'T12:00:00Z');delete legacy.monthly_budgets;missing.salary={};
 const cases=[monthly,legacy,missing].map(data=>({data,options:{asof:'2026-11-01',through:'2026-11-07'}}));
 for(const c of cases){const result=financeProjection(c.data,c.options),baseline=old.financeProjection(c.data,c.options);if(result.currentPeriod){assert.ok(result.currentPeriod.reconciliation);if(c.data===legacy)assert.equal(result.currentPeriod.reconciliation.adjustmentCents,0);delete result.currentPeriod.reconciliation;}assert.deepEqual(result,baseline);}
 parity(cases,cases.map(c=>financeProjection(c.data,c.options)));
});
