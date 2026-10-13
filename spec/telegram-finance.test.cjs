const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'supabase/functions/telegram-webhook/index.ts'),'utf8');
// Виконуємо лише читання плану з фальшивим Supabase. Webhook/reply/fetch не запускаються.
const isolated=stripTypeScriptTypes(source.slice(source.indexOf('async function financeTransactions('),source.indexOf('async function last(chatId')));
function mock(tables,failTable=null){
 const calls=[];
 return {calls,from(table){
  const call={table};calls.push(call);const query={};
  for(const name of ['select','lte','gte','or','eq','order','range','limit','maybeSingle'])query[name]=(...args)=>{(call[name]??=[]).push(args);return query;};
  query.then=(resolve,reject)=>Promise.resolve().then(()=>{
    if(table===failTable)return {data:null,error:{message:'synthetic failure'}};
    let data=tables[table]??[];
    if(call.range){const [lo,hi]=call.range[0];data=data.slice(lo,hi+1);}
    if(call.maybeSingle)data=data[0]??null;
    return {data,error:null};
  }).then(resolve,reject);
  return query;
 }};
}
async function block(sb,capture){
 const core=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 const {formatFinanceMessage}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/finance-message.ts')).href);
 const factory=new Function('sb','financeProjection','lastPayout','formatFinanceMessage','shiftDate',isolated+';return freeBlock;');
 return factory(sb,(data,options)=>{capture.data=data;capture.options=options;return core.financeProjection(data,options);},core.lastPayout,formatFinanceMessage,
   (day,n)=>new Date(Date.parse(day+'T00:00:00Z')+n*86400000).toISOString().slice(0,10));
}
test('real Telegram consumer loads every page and maps categories into the canonical engine',async()=>{
 const sb=mock({accounts:[{id:1,kind:'debit',balance:2800,debt:0},{id:2,kind:'credit',balance:0,debt:16000,credit_limit:20000}],
 fixed_payments:[{id:1,name:'Платіж',type:'expense',amount:28000,day_of_month:25,credit_ok:true}],credits:[],
 salary_config:[{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000}],
 categories:[{id:1,name:'Їжа',is_income:false,budget_limit:100},{id:2,name:'Зарплата',is_income:true,budget_limit:0}],
 transactions:Array.from({length:1001},(_,i)=>({id:i,account_id:null,type:'expense',amount:1,date:'2026-10-10',created_at:'2026-10-10T00:00:00Z',source:'mono'}))});
 const capture={};const run=await block(sb,capture);const text=(await run('2026-10-10')).replace(/[\u00a0\u202f]/g,' ');
 assert.equal(capture.data.transactions.length,1001);assert.equal(capture.data.categories[0].type,'expense');assert.equal(capture.data.categories[1].type,'income');
 assert.equal(capture.data.accounts[1].credit_limit,20000);assert.equal(capture.options.through,'2027-01-08');
 assert.ok(text.includes('Власні кошти:'),text);// v150: бюджет наступного періоду за правилом рушія: min(20 000, A), якщо A (власні після резерву й погашення) > 15 000, інакше 15 000
 const core=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);const plan=core.financeProjection(capture.data,capture.options).nextPlan;
 assert.equal(plan.targetCents,plan.baseAvailableCents>1500000?Math.min(2000000,plan.baseAvailableCents):1500000);/* v153 (А): платіж 28 000 25.10 credit_ok резервувався з виплати 21.10, A нижче 15 000, бюджет 15 000; v154: credit_ok не резервується, A понад 20 000, бюджет 20 000 */assert.equal(plan.targetCents,2000000);
 assert.ok(text.includes('Бюджет на початок періоду: 20 000 ₴'),text);assert.ok(text.includes('1 250 ₴/день (21.10-06.11)'),text);assert.ok(text.includes('Картки:'),text);
 const tx=sb.calls.filter(c=>c.table==='transactions'&&c.range);assert.equal(tx.length,2);assert.deepEqual(tx.map(c=>c.range[0]),[[0,999],[1000,1999]]);
 for(const q of tx){assert.deepEqual(q.order[0],['id',{ascending:true}]);assert.deepEqual(q.lte[0],['date','2026-10-10']);}
});
test('query failure cannot produce a plausible but incomplete finance total',async()=>{
 const sb=mock({salary_config:[]},'transactions');const run=await block(sb,{});
 await assert.rejects(run('2026-10-10'),/transactions lookup failed/);
 assert.ok(!source.includes('freeToPayout('));
});
