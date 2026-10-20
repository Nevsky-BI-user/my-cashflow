const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const model=html.split('/* MONTHLY BUDGET MODEL */')[1].split('/* END MONTHLY BUDGET MODEL */')[0];
const facts=html.slice(html.indexOf('function budgetRangeFacts('),html.indexOf('/* MONTHLY BUDGET MODEL */'));
const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const pbDate=s=>new Date(s+'T12:00:00'),pbAdd=(d,n)=>{const q=new Date(d);q.setDate(q.getDate()+n);return q};
const {monthlyMoney,monthlyValidate,monthlyBudgetModel}=new Function('pbIso','pbDate','pbAdd','pbDm',facts+model+';return{monthlyMoney,monthlyValidate,monthlyBudgetModel}')(iso,pbDate,pbAdd,iso);
const cats=[{id:1,name:'Food',limit:1},{id:2,name:'Health',limit:50}];
const row={month_start:'2026-10-01',total_cents:100001,allocations:{1:30001,2:60000}};
test('monthly money parses cents exactly and rejects invalid/unsafe inputs',()=>{
 assert.equal(monthlyMoney('1 234,56'),123456);assert.equal(monthlyMoney('0'),0);
 for(const x of ['',-1,'1.234','1e3','Infinity','90071992547410'])assert.throws(()=>monthlyMoney(x));
 assert.equal(monthlyValidate(row),90001);
 assert.throws(()=>monthlyValidate({...row,allocations:{1:100002}}));
 assert.throws(()=>monthlyValidate({...row,allocations:{1:0.5}}));
});
test('absent monthly plan differs from explicit zero and facts remain visible',()=>{
 const tx=[{id:1,type:'expense',amount:1.25,date:'2026-10-02',category_id:1}];
 const absent=monthlyBudgetModel(null,tx,cats,2026,9,'2026-10-03');
 const zero=monthlyBudgetModel({...row,total_cents:0,allocations:{}},tx,cats,2026,9,'2026-10-03');
 assert.equal(absent.plan,null);assert.equal(absent.fact,125);assert.equal(absent.remaining,null);
 assert.equal(zero.plan,0);assert.equal(zero.remaining,-125);
});
test('monthly saved allocation does not change with early spending or global category weights',()=>{
 const tx=[{id:1,type:'expense',amount:700,date:'2026-10-01',category_id:2}];
 const first=monthlyBudgetModel(row,[],cats,2026,9,'2026-10-01');
 const later=monthlyBudgetModel(row,tx,cats.map(c=>({...c,limit:99999,limitAbs:999})),2026,9,'2026-10-19');
 assert.equal(later.plan,first.plan);assert.deepEqual(later.rows.map(c=>c.totalCents),first.rows.map(c=>c.totalCents));
 assert.equal(later.rows.find(c=>c.id===2).remainingCents,-10000);assert.equal(later.unallocated,10000);
 assert.equal(monthlyBudgetModel(row,tx,cats,2026,10,'2026-11-03').plan,null);
 assert.deepEqual(row.allocations,{1:30001,2:60000});
});
test('monthly boundaries include leap February and year rollover, exclude fixed, credit, transfers, future and duplicate facts',()=>{
 for(const [y,m,start,end,days] of [[2028,1,'2028-02-01','2028-03-01',29],[2026,11,'2026-12-01','2027-01-01',31]]){
  const tx=[{id:1,date:start,type:'expense',amount:1.01,category_id:1},{id:2,date:start,type:'expense',amount:2,fixed_id:1},{id:3,date:start,type:'expense',amount:3,credit_id:1},{id:4,date:start,type:'transfer',amount:4},{id:5,date:end,type:'expense',amount:5},{id:6,date:start.slice(0,8)+'03',type:'expense',amount:6}];tx.push(tx[0]);
  const b=monthlyBudgetModel(null,tx,cats,y,m,start);
  assert.equal(b.start,start);assert.equal(b.end,end);assert.equal(b.days,days);assert.equal(b.fact,101);
 }
});
test('archived category snapshots and uncategorized facts are retained',()=>{
 const saved={...row,allocations:{3:100}};
 const b=monthlyBudgetModel(saved,[{id:1,date:'2026-10-01',type:'expense',amount:.5,category_id:3},{id:2,date:'2026-10-01',type:'expense',amount:.25,category_id:999}],cats,2026,9,'2026-10-01');
 assert.equal(b.rows.find(c=>c.id==='3').remainingCents,50);
 assert.equal(b.rows.find(c=>c.id==='unallocated').factCents,25);
});
