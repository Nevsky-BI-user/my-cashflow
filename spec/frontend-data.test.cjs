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
function categoryContext(fail=false){
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
 const context={sb,categoryRow,activeCats:state.cats,wCats:state.cats,allCats:state.cats,budgetLimits:{1:25,2:75},lockedCats:{},budgetSaveLock:{current:false},
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
