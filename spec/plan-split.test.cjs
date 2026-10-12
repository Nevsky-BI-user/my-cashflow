const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
// v150: план категорій від повного бюджету періоду (planSplit в index.html) ділить суму так само, як split рушія
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const src=html.split(/\r?\n/).find(l=>l.startsWith('function planSplit('));
const planSplit=new Function('return '+src)();
const base=cats=>({accounts:[{id:1,kind:'debit',balance:2800,debt:0}],fixed:[],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:cats,transactions:[]});
const C=(id,o)=>Object.assign({id,name:'Cat '+id,type:'expense'},o);
const cases={
 weights:[C('1',{budget_limit:40}),C('2',{budget_limit:20.5}),C('3',{budget_limit:15}),C('4',{budget_limit:0}),C('5',{budget_limit:7})],
 mixed:[C('a',{budget_limit:30,limit_abs:null}),C('b',{limit_abs:4000,sort_order:2}),C('c',{limit_abs:2500.5,sort_order:1}),C('d',{budget_limit:10}),C('e',{limit_abs:900,sort_order:null})],
 absOnly:[C('x',{limit_abs:3000,sort_order:0}),C('y',{limit_abs:2000,sort_order:1})],
 absOver:[C('x',{limit_abs:90000,sort_order:0}),C('y',{limit_abs:2000,sort_order:1}),C('z',{budget_limit:5})],
 none:[C('p',{budget_limit:0}),C('q',{})],
 income:[C('1',{budget_limit:50}),Object.assign(C('2',{budget_limit:50}),{type:'income'}),Object.assign(C('3',{budget_limit:25}),{active:false}),C('4',{budget_limit:25})]
};
test('planSplit matches the engine split of a headline period',async()=>{
 const {financeProjection}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 for(const [name,cats] of Object.entries(cases)){
  const r=financeProjection(base(cats),{asof:'2026-10-10',through:'2026-12-01'});
  const ps=r.periods.filter(p=>p.basis!=='current');
  assert.ok(ps.length,name);
  for(const p of ps)assert.deepEqual(planSplit(p.targetCents,cats),p.categories.map(({totalCents,...c})=>({...c,totalCents})),name+' '+p.start);
 }
});
test('planSplit splits the full budget exactly',()=>{
 for(const [name,cats] of Object.entries(cases))for(const t of [0,1,1500000,1764023,99999999]){
  const rows=planSplit(t,cats);assert.equal(rows.reduce((s,c)=>s+c.totalCents,0),t,name+' '+t);
 }
});
