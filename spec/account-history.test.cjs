const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const source=html.slice(html.indexOf('function accountHistoryEvent('),html.indexOf('function AccountAmounts('));
function environment(extra={}){
  const ctx={...extra};
  vm.createContext(ctx);vm.runInContext(source,ctx);return ctx;
}
test('history maps recorded transactions to the existing detail contract',()=>{
  const ctx=environment();
  const ev=ctx.accountHistoryEvent({id:7,date:'2026-01-02',account_id:2,type:'income',amount:'120.50',description:'Test',category_id:3,source:'manual',receipt_url:'receipt',fixed_id:4,credit_id:5});
  assert.equal(ev.amount,120.5);assert.equal(ev.type,'in');assert.equal(ev.acc,2);
  assert.equal(ev.y,2026);assert.equal(ev.m,0);assert.equal(ev.day,2);
  assert.equal(ev.receipt,'receipt');assert.equal(ev.fixedId,4);assert.equal(ev.creditId,5);
  assert.equal(ev.planned,undefined);
});
test('demo history filters account, deduplicates and orders newest date/id first',()=>{
  const ctx=environment();
  const rows=ctx.accountHistoryDemo([{id:2,account_id:'a',date:'2026-01-01'},{id:10,account_id:'a',date:'2026-01-01'},{id:2,account_id:'a',date:'2026-01-01'},{id:3,account_id:'b',date:'2026-03-01'},{id:1,account_id:'a',date:'2026-02-01'}],'a');
  assert.deepEqual(Array.from(rows,t=>t.id),[1,10,2]);
});
test('database history paginates the whole account with deterministic descending order',async()=>{
  const ctx=environment(),calls=[];
  const query={select(v){calls.push(['select',v]);return this},eq(...v){calls.push(['eq',...v]);return this},order(...v){calls.push(['order',...v]);return this},range(a,b){calls.push(['range',a,b]);return Promise.resolve({data:[{id:a+1}],error:null})}};
  const client={from(v){assert.equal(v,'transactions');return query}};
  assert.equal((await ctx.accountHistoryPage(client,77,0))[0].id,1);
  assert.equal((await ctx.accountHistoryPage(client,77,100))[0].id,101);
  assert.deepEqual(calls.filter(x=>x[0]==='range'),[['range',0,99],['range',100,199]]);
  assert.equal(calls.filter(x=>x[0]==='eq').every(x=>x[1]==='account_id'&&x[2]===77),true);
  assert.deepEqual(calls.filter(x=>x[0]==='order').map(x=>[x[1],x[2].ascending]),[['date',false],['id',false],['date',false],['id',false]]);
});
test('database errors propagate for retry',async()=>{
  const ctx=environment(),q={select(){return this},eq(){return this},order(){return this},range(){return Promise.resolve({error:new Error('offline')})}};
  await assert.rejects(ctx.accountHistoryPage({from(){return q}},1,0),/offline/);
});
test('closing the history invalidates an in-flight response',async()=>{
  let resolve,updates=0;
  const cleanups=[],effects=[];
  const q={select(){return this},eq(){return this},order(){return this},range(){return new Promise(r=>{resolve=r})}};
  const ctx=environment({React:{useRef:value=>({current:value})},useState:value=>[value,()=>{updates++}],useEffect:fn=>effects.push(fn),h:()=>null,SheetGrip(){},AccountAmounts(){},document:{addEventListener(){},removeEventListener(){}}});
  ctx.AccountHistorySheet({a:{id:1,name:'Account'},client:{from(){return q}},onClose(){}});
  for(const effect of effects){const cleanup=effect();if(cleanup)cleanups.push(cleanup)}
  cleanups.forEach(fn=>fn());const before=updates;
  resolve({data:[{id:1}],error:null});await new Promise(r=>setImmediate(r));
  assert.equal(updates,before,'an old account response must not update an unmounted sheet');
});
