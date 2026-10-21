const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const model=html.split('/* MONTHLY BUDGET MODEL */')[1].split('/* END MONTHLY BUDGET MODEL */')[0];
const facts=html.slice(html.indexOf('function budgetRangeFacts('),html.indexOf('/* MONTHLY BUDGET MODEL */'));
const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const pbDate=s=>new Date(s+'T12:00:00'),pbAdd=(d,n)=>{const q=new Date(d);q.setDate(q.getDate()+n);return q};
const dependencies=html.split(/\r?\n/).filter(l=>/^const (getDow|wdRange|pbIso)=|^function pbPayouts\(|^function pbObl\(|^function fpWd\(|function fpEnded\(|const crOk=/.test(l)).join('\n');
const {monthlyMoney,monthlyValidate,monthlyBudgetModel,monthlySalaryEnvelope,monthlyPercentCents}=new Function('const fmtM=v=>String(v);\n'+dependencies+'\n'+facts+model+';return{monthlyMoney,monthlyValidate,monthlyBudgetModel,monthlySalaryEnvelope,monthlyPercentCents}')();
const cats=[{id:1,name:'Food',limit:1},{id:2,name:'Health',limit:50}];
const row={month_start:'2026-10-01',total_cents:100001,allocations:{1:30001,2:60000}};
test('monthly percentage uses net capacity, exact basis points and half-up cents',()=>{
 assert.equal(monthlyPercentCents('25',75000),18750);
 assert.equal(monthlyPercentCents('12,50',10004),1251);
 assert.equal(monthlyPercentCents('50',1),1);
 assert.equal(monthlyPercentCents('0.01',5000),1);
 assert.equal(monthlyPercentCents('100',Number.MAX_SAFE_INTEGER),Number.MAX_SAFE_INTEGER);
 assert.equal(monthlyPercentCents('50',Number.MAX_SAFE_INTEGER),4503599627370496);
 assert.equal(monthlyPercentCents('0',Number.MAX_SAFE_INTEGER),0);
 assert.equal(monthlyPercentCents('25',0),0);
 for(const value of ['',-1,'100.01','0.001','1e2','Infinity','NaN'])assert.throws(()=>monthlyPercentCents(value,75000));
 for(const capacity of [-1,.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1])assert.throws(()=>monthlyPercentCents('25',capacity));
});
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
const salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:600,salary_amount:400};
const obligation={key:'fixed:1:2026-10-15',date:'2026-10-15',name:'Rent',amount_cents:25000,kind:'fixed'};
test('salary envelope subtracts recurring commitments once even when already paid',()=>{
 const fixed=[{id:1,name:'Rent',amount:250,type:'payment',day_of_month:15,active:true,paid:{'2026-10':true}},
  {id:2,name:'Income excluded',amount:200,type:'income',day_of_month:15},
  {id:3,name:'Inactive excluded',amount:200,type:'payment',day_of_month:15,active:false}];
 const envelope=monthlySalaryEnvelope(salary,fixed,[],2026,9);
 assert.equal(envelope.total_cents,100000);
 assert.equal(envelope.mandatory_items.length,1);
 assert.equal(envelope.mandatory_items[0].amount_cents,25000);
 assert.equal(fixed[0].paid['2026-10'],true);
 const saved={...envelope,allocations:{1:40000}};
 assert.equal(monthlyValidate(saved),40000);
 const b=monthlyBudgetModel(saved,[{id:1,date:'2026-10-02',type:'expense',amount:10,category_id:1},{id:2,date:'2026-10-15',type:'expense',amount:250,fixed_id:1}],cats,2026,9,'2026-10-20');
 assert.equal(b.gross,100000);assert.equal(b.mandatory,25000);assert.equal(b.plan,75000);
 assert.equal(b.fact,1000);assert.equal(b.remaining,74000);assert.equal(b.unallocated,35000);
 assert.throws(()=>monthlyValidate({...saved,allocations:{1:75001}}));
});
test('mandatory snapshots validate dates, keys, cents and capacity, preserving legacy plans',()=>{
 const saved={...row,mandatory_items:[obligation],allocations:{1:75001}};
 assert.equal(monthlyValidate(saved),75001);
 for(const item of [{...obligation,amount_cents:-1},{...obligation,amount_cents:.5},{...obligation,amount_cents:Number.MAX_SAFE_INTEGER+1},{...obligation,date:'2026-11-15'},{...obligation,date:'2026-10-99'},{...obligation,date:20261015},{...obligation,key:''},{...obligation,estimated:null},{...obligation,unknown:true}]){
  assert.throws(()=>monthlyValidate({...saved,mandatory_items:[item],allocations:{}}));
 }
 assert.throws(()=>monthlyValidate({...saved,mandatory_items:[obligation,obligation],allocations:{}}));
 const legacy=monthlyBudgetModel(row,[],cats,2026,9,'2026-10-03');
 assert.equal(legacy.legacy,true);assert.equal(legacy.plan,row.total_cents);
 const deficit=monthlyBudgetModel({...saved,total_cents:10000,allocations:{}},[],cats,2026,9,'2026-10-03');
 assert.equal(deficit.plan,0);assert.equal(deficit.deficit,15000);assert.equal(deficit.remaining,0);
});
test('weekly commitments, end dates, active installment range and variable estimates',()=>{
 const fixed=[{id:1,name:'Weekly',amount:10,period:'week',weekday:1,type:'payment',end_date:'2026-10-19',paid:{'W2026-10-05':true}},
  {id:2,name:'Ended',amount:99,day_of_month:20,type:'payment',end_date:'2026-10-19'},
  {id:3,name:'Variable',amount:30,day_of_month:8,type:'payment',variable:true}];
 const credits=[{id:1,name:'Active',monthly_amount:25,payment_day:9,start_year:2026,start_month:9,total_payments:2,paid:{'2026-10':true}},
  {id:2,name:'Expired',monthly_amount:99,payment_day:9,start_year:2026,start_month:7,total_payments:2}];
 const env=monthlySalaryEnvelope(salary,fixed,credits,2026,9);
 const items=env.mandatory_items;
 assert.equal(items.filter(i=>i.name==='Weekly').length,3);
 assert.equal(items.reduce((n,i)=>n+i.amount_cents,0),8500);
 assert.equal(items.find(i=>i.name==='Variable').estimated,true);
 assert.equal(new Set(items.map(i=>i.key)).size,items.length);
});
test('salary calendar includes neighboring shifted payouts and workday prorating',()=>{
 const cfg={...salary,advance_day:31,salary_day:6};
 // Sunday 31 Jan shifts into February; a configured Feb 31 is in March.
 assert.equal(monthlySalaryEnvelope(cfg,[],[],2027,0).total_cents,40000);
 assert.equal(monthlySalaryEnvelope(cfg,[],[],2027,1).total_cents,100000);
 // Saturday 1 May 2027 shifts into April: include next month's salary.
 assert.equal(monthlySalaryEnvelope({...salary,salary_day:1},[],[],2027,3).total_cents,140000);
 const env=monthlySalaryEnvelope({...salary,rate:23000},[],[],2026,9);
 // October advance and September remainder are both 11/22 working days.
 assert.equal(env.total_cents,2300000);
});
test('generated labels fit snapshots and unsafe salary is rejected',()=>{
 const label='Long '.repeat(100);
 const env=monthlySalaryEnvelope(salary,[{id:1,name:label,amount:10,day_of_month:5,type:'payment'}],[{id:2,name:label,monthly_amount:20,payment_day:6,start_year:2026,start_month:9,total_payments:2}],2026,9);
 assert.equal(env.mandatory_items.length,2);
 assert.ok(env.mandatory_items.every(i=>i.name.length===240));
 assert.equal(monthlyValidate(env),0);
 assert.throws(()=>monthlySalaryEnvelope({...salary,advance_amount:Number.MAX_SAFE_INTEGER},[],[],2026,9));
});
