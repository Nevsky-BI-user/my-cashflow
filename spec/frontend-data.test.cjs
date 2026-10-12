const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
function paged(rows,failSecond=false){
 const calls=[];
 return {calls,from(table){
   const call={table};calls.push(call);const query={};
   for(const key of ['select','order','range','lte','gte','or'])query[key]=(...args)=>{(call[key]??=[]).push(args);return query;};
   query.then=(resolve,reject)=>Promise.resolve().then(()=>{
     const [lo,hi]=call.range[0];
     return failSecond&&lo>0?{error:{message:'synthetic second-page failure'}}:{data:rows.slice(lo,hi+1),error:null};
   }).then(resolve,reject);
   return query;
 }};
}
const savingCode=html.match(/const loadSavings=(async function\(\)\{[^\r\n]+\});/)[1];
const feedLine=html.split(/\r?\n/).find(line=>line.includes("'операції рахунків'")&&line.includes('for(let page=0;page<100;page++)'));
const feedCode=feedLine.slice(feedLine.indexOf('async function(){'),feedLine.indexOf('})(),function(r)')+1);
test('saved balance includes all contributions beyond the old 20 and server 1000 limits',async()=>{
 const rows=Array.from({length:1001},(_,id)=>({id,amount:1}));const sb=paged(rows);let saved;
 const load=new Function('sb','setSavingsLog','return '+savingCode)(sb,value=>saved=value);
 await load();assert.equal(saved.length,1001);assert.equal(saved.reduce((s,r)=>s+r.amount,0),1001);
 assert.deepEqual(sb.calls.map(c=>c.range[0]),[[0,999],[1000,1999]]);
});
test('canonical frontend feed retains prior-month facts, unassigned rows and stable pages',async()=>{
 const rows=Array.from({length:1001},(_,id)=>({id,account_id:null,date:'2026-09-22',amount:1}));const sb=paged(rows);
 const run=new Function('sb','pbIso','now','accSince','financeFrom','return ('+feedCode+')()');
 const out=await run(sb,d=>d.toISOString().slice(0,10),new Date('2026-10-03T12:00:00Z'),'2026-10-01T00:00:00Z','2026-08-04');
 assert.equal(out.data.length,1001);
 for(const q of sb.calls){assert.deepEqual(q.order[0],['id']);assert.ok(q.or[0][0].includes('date.gte.2026-08-04'));assert.ok(q.or[0][0].includes('created_at.gt.2026-10-01T00:00:00Z'));assert.deepEqual(q.lte[0],['date','2026-10-03']);}
});
test('failed second page never publishes partial savings or financial transactions',async()=>{
 const rows=Array.from({length:1001},(_,id)=>({id,amount:1}));let saved=false;
 const load=new Function('sb','setSavingsLog','return '+savingCode)(paged(rows,true),()=>saved=true);
 await assert.rejects(load());assert.equal(saved,false);
 const run=new Function('sb','pbIso','now','accSince','financeFrom','return ('+feedCode+')()');
 const result=await run(paged(rows,true),d=>d.toISOString().slice(0,10),new Date('2026-10-03T12:00:00Z'),null,'2026-08-04');
 assert.ok(result.error);assert.ok(!result.data);
});

const functionCode=name=>html.split(/\r?\n/).find(line=>line.startsWith('const '+name+'=')).slice(('const '+name+'=').length,-1);
const categoryRow=new Function('return '+functionCode('categoryRow'))();
function categoryContext(fail=false,absLims={}){
 const records=[{id:1,name:'A',budget_limit:40},{id:2,name:'B',budget_limit:60}];
 const state={cats:records.map(categoryRow),limits:{1:40,2:60},error:'',closed:false,name:'Leisure'};
 const sb={from(table){assert.equal(table,'categories');let operation='select',payload,which;
  const q={update(v){operation='update';payload=v;return q},insert(v){operation='insert';payload=v;return q},eq(k,id){which=id;return q},select(){return q},single(){return q},order(){return q},
   then(resolve,reject){return Promise.resolve().then(()=>{
    if(fail&&(operation==='insert'||which===2))return {error:{message:'synthetic failure'}};
    if(operation==='update'){Object.assign(records.find(r=>r.id===which),payload);return {error:null};}
    if(operation==='insert'){const row={...payload,id:3};records.push(row);return {data:row,error:null};}
    return {data:records.map(r=>({...r})),error:null};
   }).then(resolve,reject)}};return q;}};
 const context={sb,categoryRow,activeCats:state.cats,wCats:state.cats,allCats:state.cats,budgetLimits:{1:25,2:75},lockedCats:{},absLims,budgetSaveLock:{current:false},
  setBudgetBusy:()=>{},setBudgetError:v=>state.error=v,setShowBudgetEdit:v=>state.closed=!v,
  setDbCats:v=>state.cats=typeof v==='function'?v(state.cats):v,
  newCatName:state.name,newCatPct:20,PALETTE:['#888'],session:{user:{id:'synthetic-user'}},
  setBudgetLimits:v=>state.limits=typeof v==='function'?v(state.limits):v,setNewCatName:v=>state.name=v,setNewCatPct:()=>{}};
 return {state,records,context,run(name){return new Function(...Object.keys(context),'return '+functionCode(name))(...Object.values(context))();}};
}
test('weight save persists refreshed values and stays open on partial server failure',async()=>{
 let x=categoryContext();await x.run('saveBudgetWeights');assert.equal(x.state.closed,true);assert.deepEqual(x.state.cats.map(c=>c.limit),[25,75]);assert.equal(x.context.budgetSaveLock.current,false);
 x=categoryContext(true);await x.run('saveBudgetWeights');assert.equal(x.state.closed,false);assert.ok(x.state.error);assert.deepEqual(x.state.cats.map(c=>c.limit),[25,60]);assert.equal(x.context.budgetSaveLock.current,false);
});
test('v148: a category switched to UAH saves limit_abs with zero weight, a percent category clears limit_abs',async()=>{
 const x=categoryContext(false,{2:8000});await x.run('saveBudgetWeights');assert.equal(x.state.closed,true);
 assert.deepEqual(x.state.cats.map(c=>[c.limit,c.limitAbs]),[[25,null],[0,8000]]);
});
test('category creation writes the requested relative weight and retains the draft on error',async()=>{
 let x=categoryContext();await x.run('createBudgetCategory');assert.equal(x.records.length,3);assert.equal(x.records[2].budget_limit,25);assert.equal(x.records[2].user_id,'synthetic-user');assert.equal(x.state.cats[2].name,'Leisure');assert.equal(x.state.name,'');assert.equal(Object.values(x.state.limits).reduce((a,b)=>a+b,0),100);
 x=categoryContext(true);await x.run('createBudgetCategory');assert.equal(x.records.length,2);assert.equal(x.state.name,'Leisure');assert.ok(x.state.error);assert.equal(x.context.budgetSaveLock.current,false);
});

const accountDraft=new Function('return '+functionCode('accDraft'))();
const openAccountCode=functionCode('openAcc');
const saveAccountCode=html.slice(html.indexOf('const saveAccount=')+18,html.indexOf('\nconst deleteAccount=')).trim().replace(/;$/,'');
async function editAccount(raw,derived,changes){
 let draft,rows=[{...raw}],payload,error;
 const open=new Function('setAccErr','setAccBusy','setAccEdit','accDraft','return '+openAccountCode)(()=>{},()=>{},v=>draft=v,accountDraft);
 open(derived);Object.assign(draft,changes);
 const sb={from(){return {update(v){payload=v;return {eq(){return Promise.resolve({error:null})}}}}}};
 const ctx={accEdit:draft,accBusy:false,sb,accounts:rows,setAccErr:v=>error=v,setAccBusy:()=>{},setAccEdit:()=>{},setAccounts:fn=>rows=fn(rows),loadAccounts:()=>{},session:{user:{id:'synthetic'}}};
 await new Function(...Object.keys(ctx),'return '+saveAccountCode)(...Object.values(ctx))();
 assert.ok(!error);return {row:rows[0],payload};
}
test('metadata-only account edits preserve raw debit and credit snapshots without replaying transactions',async()=>{
 for(const raw of [{id:'d',kind:'debit',balance:5000,debt:0},{id:'c',kind:'credit',balance:500,debt:3000,debt_month:'2026-09-01'}]){
  raw.balance_updated_at='2026-10-01T00:00:00Z';
  const derived={...raw,balance:raw.kind==='debit'?4000:0,debt:raw.kind==='credit'?3500:0};
  const out=await editAccount(raw,derived,{name:'Renamed'});
  assert.equal(out.row.name,'Renamed');
  for(const key of ['balance','debt','debt_month','balance_updated_at'])assert.equal(out.row[key],raw[key]);
  for(const key of ['balance','debt','debt_month','balance_updated_at'])assert.ok(!Object.hasOwn(out.payload,key));
 }
});
test('deliberate account adjustment saves both displayed balances with a fresh reconciliation timestamp',async()=>{
 const raw={id:'c',kind:'credit',balance:500,debt:3000,debt_month:'2026-09-01',balance_updated_at:'2026-10-01T00:00:00Z'};
 const out=await editAccount(raw,{...raw,balance:0,debt:3500},{name:'Credit',debt:3200});
 assert.equal(out.payload.balance,0);assert.equal(out.payload.debt,3200);assert.equal(out.payload.debt_month,'2026-09-01');
 assert.ok(Date.parse(out.payload.balance_updated_at)>Date.parse(raw.balance_updated_at));
});
// v145: «Гроші в часі»: минула крива власних = власні сьогодні мінус підписані операції власних рахунків після дня
const pastLine=html.split(/\r?\n/).find(line=>line.startsWith('function pastOwnSeries('));
const pastOwnSeries=new Function(pastLine+'\nreturn pastOwnSeries;')();
test('past own curve: today is the anchor, later operations are reversed day by day',()=>{
 const txs=[
  {id:1,account_id:1,type:'expense',amount:100,date:'2026-10-12'},
  {id:2,account_id:1,type:'income',amount:1000,date:'2026-10-11'},
  {id:3,account_id:2,type:'expense',amount:50.5,date:'2026-10-11'},
  {id:4,account_id:9,type:'expense',amount:700,date:'2026-10-11'},
  {id:5,account_id:null,type:'expense',amount:30,date:'2026-10-10'},
  {id:6,account_id:1,type:'expense',amount:999,date:'2026-10-09'},
  {id:7,account_id:1,type:'expense',amount:5,date:'2026-10-13'},
 ];
 const r=pastOwnSeries(txs,['1','2',''],251900,'2026-10-09','2026-10-12');
 assert.deepEqual(r.map(x=>x.date),['2026-10-09','2026-10-10','2026-10-11','2026-10-12']);
 // 12.10: якір; 11.10: мінус сьогоднішня витрата 100 повертається (+100); 10.10: мінус дохід 1000 і плюс витрата 50,50 (рахунок 9 кредитний, не власний); 09.10: плюс 30 без рахунку
 assert.deepEqual(r.map(x=>x.cents),[251900-100000+5050+10000+3000,251900-100000+5050+10000,251900+10000,251900]);
 // операція в перший день діапазону і після сьогодні не впливає
 assert.equal(r[0].cents,r[1].cents+3000);
});
test('past own curve: without unassigned key operations without account are ignored; empty range',()=>{
 const txs=[{id:1,account_id:null,type:'expense',amount:30,date:'2026-10-12'},{id:2,account_id:'a',type:'expense',amount:10,date:'2026-10-12'}];
 assert.deepEqual(pastOwnSeries(txs,['a'],0,'2026-10-11','2026-10-12').map(x=>x.cents),[1000,0]);
 assert.deepEqual(pastOwnSeries(txs,['a'],0,'2026-10-13','2026-10-12'),[]);
 assert.equal(pastOwnSeries([],['a'],5,'2024-01-01','2026-10-12').length,1016);
});
// v145: кільце бюджету: частки менше 3 % (дві й більше) в «Інші», відсотки разом 100, перевищення плану
const donutLine=html.split(/\r?\n/).find(line=>line.startsWith('function budDonutData('));
const budDonutData=new Function(donutLine+'\nreturn budDonutData;')();
test('budget donut: small shares merge into Others, percents sum to 100, over-plan flags',()=>{
 const rows=[{id:'a',name:'A',fact:600,plan:500},{id:'b',name:'B',fact:333.33,plan:400},{id:'c',name:'C',fact:20,plan:10},{id:'d',name:'D',fact:15,plan:50},{id:'e',name:'E',fact:0,plan:100},{id:'n',name:'Без категорії',fact:31.67,plan:0,noPlan:true}];
 const d=budDonutData(rows);
 assert.equal(Math.round(d.total*100),100000);
 assert.deepEqual(d.segs.map(s=>s.id),['a','b','n','__other']);
 assert.deepEqual(d.segs.find(s=>s.id==='__other').members.map(m=>m.id),['c','d']);
 assert.equal(d.segs.reduce((s,x)=>s+x.pct,0),100);
 assert.deepEqual(d.segs.map(s=>s.pct),[60,33,3,4]);
 assert.deepEqual(d.segs.map(s=>s.over),[true,false,false,true]);
 // одна мала частка не зливається
 assert.deepEqual(budDonutData([{id:'a',fact:98,plan:0},{id:'b',fact:2,plan:5}]).segs.map(s=>[s.id,s.pct]),[['a',98],['b',2]]);
 assert.deepEqual(budDonutData([{id:'a',fact:0,plan:5}]).segs,[]);
});
