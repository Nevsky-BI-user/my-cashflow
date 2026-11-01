const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
const root=path.resolve(__dirname,'..');
const mod=f=>import(pathToFileURL(path.join(root,'supabase/functions/_shared',f)).href);
const cats=[{id:1,name:'Food',type:'expense'},{id:2,name:'Home',is_income:false},{id:3,name:'Income',type:'income'},{id:4,name:'Debt',budget_role:'debt_card'}];
const tx={id:7,category_id:1,type:'expense',amount:10.01,account_id:1,date:'2026-11-01',created_at:'2026-11-01T12:00:00Z',description:'Shop',expense_allocations:[{category_id:1,amount_cents:333,label:'a'},{category_id:2,amount_cents:334},{category_id:1,amount_cents:334,label:'b'}]};
test('exact cents, repeated categories, identity and labels; original stays intact',async()=>{
 const {expenseCategoryParts:parts}=await mod('expense-allocations.ts');
 const result=parts(tx,cats);assert.equal(result.length,3);assert.equal(result.reduce((s,r)=>s+r.amount_cents,0),1001);
 assert.deepEqual(result.map(r=>r.originalTransactionId),[7,7,7]);assert.equal(result[2].allocationLabel,'b');assert.equal(tx.amount,10.01);
 assert.equal(parts({...tx,expense_allocations:[]},cats)[0].amount_cents,1001);
});
test('malformed, partial, excluded category, transfer and payment never lose parent total',async()=>{
 const {expenseCategoryParts:parts}=await mod('expense-allocations.ts');
 const bad=[null,{},[tx.expense_allocations[0]],[{category_id:1,amount_cents:1.5},{category_id:2,amount_cents:999.5}],[{category_id:1,amount_cents:500},{category_id:3,amount_cents:501}],[{category_id:4,amount_cents:500},{category_id:2,amount_cents:501}],[{category_id:1,amount_cents:500,label:'x'.repeat(161)},{category_id:2,amount_cents:501}]];
 for(const rows of bad)assert.deepEqual(parts({...tx,expense_allocations:rows},cats).map(r=>r.amount_cents),[1001]);
 for(const k of ['transfer_id','fixed_id','credit_id'])assert.equal(parts({...tx,[k]:1},cats).length,1);
 assert.equal(parts({...tx,type:'income'},cats).length,1);
});
test('Python mirror equals TypeScript portions including fallback',async()=>{
 const {expenseCategoryParts:parts}=await mod('expense-allocations.ts');
 const inputs=[tx,{...tx,expense_allocations:[]},{...tx,transfer_id:'pair'},{...tx,expense_allocations:[{category_id:1,amount_cents:500},{category_id:2,amount_cents:501}]}];
 const py=spawnSync('python',['-c','import sys,json;sys.path.insert(0,"scripts");from expense_allocations import expense_category_parts;d=json.load(sys.stdin);print(json.dumps([expense_category_parts(t,d["cats"]) for t in d["txs"]]))'],{cwd:root,input:JSON.stringify({cats,txs:inputs}),encoding:'utf8'});
 assert.equal(py.status,0,py.stderr);assert.deepEqual(JSON.parse(py.stdout),inputs.map(t=>parts(t,cats)));
});
test('projection local helper stays identical and category analytics do not multiply receipts',async()=>{
 const source=fs.readFileSync(path.join(root,'supabase/functions/_shared/expense-allocations.ts'),'utf8').split('export ')[1].trim();
 assert.ok(fs.readFileSync(path.join(root,'supabase/functions/_shared/budget.ts'),'utf8').includes(source));
 const {monthModel,todayExpensesModel}=await mod('bot-reports.ts');
 const today=todayExpensesModel([tx],cats,[],'2026-11-01');assert.equal(today.count,1);assert.equal(today.totalCents,1001);
 const m=monthModel([tx],cats,[],'2026-11-01');
 assert.equal(m.curSpent,1001);assert.deepEqual(m.cats.map(c=>[c.name,c.cur]),[["Food",667],["Home",334]]);assert.equal(m.places[0].count,1);
});
test('automatic categorization mutation has split guard on every null category CAS',()=>{
 for(const name of ['categorize','categorize-batch']){
  const s=fs.readFileSync(path.join(root,'supabase/functions',name,'index.ts'),'utf8');
  assert.equal((s.match(/\.is\('category_id', null\)/g)||[]).length,(s.match(/\.is\('category_id', null\)\.eq\('expense_allocations', '\[\]'\)/g)||[]).length);
 }
});

test('monthly caps use portions while cash and minimum spend retain original; Python projection parity',async()=>{
 const {financeProjection}=await mod('budget.ts');
 const categories=cats.slice(0,2).map(c=>({...c,type:'expense',budget_limit:50}));
 const data={accounts:[{id:1,kind:'debit',balance:20000,debt:0,balance_updated_at:'2026-10-31T00:00:00Z',min_spend:10,min_spend_fee:5}],fixed:[],credits:[],categories,transactions:[tx],salary:{rate:0,salary_amount:10000,advance_amount:10000,salary_day:6,advance_day:21,split_day:15},monthly_budgets:[{month_start:'2026-11-01',total_cents:300000,mandatory_items:[],allocations:{1:150000,2:150000}}]};
 const options={asof:'2026-11-02',through:'2026-12-01'};
 const split=financeProjection(data,options),unsplit=financeProjection({...data,transactions:[{...tx,expense_allocations:[]}]},options);
 assert.deepEqual(split.snapshot,unsplit.snapshot,'one cash transaction');
 assert.equal(split.currentPeriod.actualVariableCents,1001);
 assert.notDeepEqual(split.currentPeriod.futureSchedule,unsplit.currentPeriod.futureSchedule,'category caps reflect allocation');
 const p=spawnSync('python',['scripts/budget_pool.py','--finance'],{cwd:root,input:JSON.stringify([{data,options}]),encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
 assert.equal(p.status,0,p.stderr);assert.deepEqual(split,JSON.parse(p.stdout)[0]);
});
