const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const helperCode=html.split('/* REFRESH READ GUARDS */')[1].split('/* END REFRESH READ GUARDS */')[0];
const helpers=new Function(helperCode+';return{refreshRead,refreshPageRows,refreshCurrent,refreshViewRows,refreshSalaryData}')();
const pipeline=html.split('syncRun.current=')[1].split('\nuseEffect(function(){')[0].trim().replace(/;$/,'');
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
function env(extra={}){
 const data={categories:[{id:1,name:'Food'}],category_groups:[],salary_config:[{id:1,advance_day:12,salary_day:6,savings_pct:20}],accounts:[{id:1,kind:'debit',balance:1000,balance_updated_at:'2026-01-01T00:00:00Z'}],fixed_payments:[],credits:[],transactions:[{id:1,date:'2026-10-13',amount:5,type:'expense',account_id:1}],savings_log:[],goals:[{id:1,name:'Goal',target_amount:1000}]};
 const calls=[],commits={},ctx={...helpers};let hook=extra.hook||(()=>null),current=true;
 const sb={from(table){const q={table,filters:[],rangeValue:null};for(const method of ['select','order','eq','limit','gte','lte','or','in','insert'])q[method]=(...args)=>{q.filters.push([method,...args]);return q};q.range=(...a)=>{q.rangeValue=a;return q};q.then=(yes,no)=>{calls.push(q);return Promise.resolve().then(()=>hook(q)||{data:q.rangeValue?data[table].slice(q.rangeValue[0],q.rangeValue[1]+1):data[table]}).then(yes,no)};return q},storage:{from:()=>({createSignedUrls:paths=>extra.urls?extra.urls(paths):Promise.resolve({data:paths.map(path=>({path,signedUrl:'mock://'+path}))})})},functions:{invoke:()=>extra.mono?extra.mono():Promise.resolve({data:{ok:true,account:data.accounts[0]}})}};
 const ref=v=>({current:v});
 Object.assign(ctx,{sb,catLimitQueue:ref({}),syncLocalConfig:ref({budget:null,budgetPersisted:null,budgetDirty:false,savings:20,savingsPersisted:20,savingsDirty:false}),syncAuth:ref('u1'),syncView:ref({year:2026,month:9,history:'2026-07-20',today:'2026-10-20',key:'October'}),syncEpoch:ref(0),goalSeeded:ref(false),bmPersisted:ref(null),savPersisted:ref(20),ldDone:ref({}),LD_KEYS:['операції','рахунки','профіль'],GOALS:[{name:'Seed',target:10}],SAL_ADV_DAY:21,SAL_MAIN_DAY:6,SAL_RATE:0,SAL_SPLIT:15,SAL_ADV:0,SAL_MAIN:0,pbDate:s=>new Date(s+'T00:00:00'),pbIso:d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'),pbAdd:(d,n)=>new Date(d.getFullYear(),d.getMonth(),d.getDate()+n),pbOpen:(salary,day)=>({date:new Date(day.getFullYear(),day.getMonth(),salary.advance_day)}),mapGoal:r=>({id:r.id,name:r.name,image:r.image_path}),crMap:r=>r});
 for(const name of ['DbCats','DbGroups','SavingsPct','SalCfg','Accounts','FixedPay','DbCredits','DbTx','DbTxN','PrevTx','CurTx','AccTx','HistTx','HistOwnFirst','MsTx','FixTx','SavingsLog','DbGoals','GoalUrls','MonoBal','LoadErr','LdN'])ctx['set'+name]=v=>{commits[name]=v};
 const run=new Function('ctx','with(ctx){return ('+pipeline+')}')(ctx);
 return{data,calls,commits,ctx,setHook:f=>hook=f,run:(options={})=>run([],{isCurrent:()=>current,mono:false,forceMono:false,reason:'db',...options}),logout:()=>{current=false;ctx.syncAuth.current=null}};
}
test('paginated read rejects second-page failure without publishing partial rows',async()=>{
 let published=['old'],calls=0;const make=()=>({range(){calls++;return Promise.resolve(calls===1?{data:Array.from({length:1000},(_,id)=>({id}))}:{error:Error('page two failed')})}});
 await assert.rejects(helpers.refreshPageRows(make,()=>true).then(rows=>published=rows),/page two/);assert.deepEqual(published,['old']);assert.equal(calls,2);
});
test('pipeline uses loaded salary and account timestamps, commits all view slices together',async()=>{
 const x=env();x.data.transactions.push({id:2,date:'2026-01-03',created_at:'2026-02-01T00:00:00Z',amount:2,type:'expense',account_id:1});
 assert.deepEqual(await x.run(),{ok:true});assert.equal(x.commits.SalCfg.advance_day,12);assert.deepEqual(x.commits.CurTx.map(t=>t.id),[1]);assert.deepEqual(x.commits.AccTx.map(t=>t.id),[1,2]);
 const tx=x.calls.find(q=>q.table==='transactions'&&q.rangeValue);assert.ok(tx.filters.some(f=>f[0]==='or'&&f[1].includes('created_at.gt.2026-01-01')));assert.equal(x.commits.Accounts[0].balance,1000);assert.equal(x.calls.filter(q=>q.table==='transactions').length,2);assert.equal(x.calls.some(q=>q.filters.some(f=>f[0]==='insert')),false);
});
test('partial transaction failure leaves every financial dataset unchanged',async()=>{
 const x=env();x.data.transactions=Array.from({length:1000},(_,id)=>({id,date:'2026-10-13'}));x.setHook(q=>q.table==='transactions'&&q.rangeValue&&q.rangeValue[0]===1000?{error:Error('incomplete tx')}:null);
 await assert.rejects(x.run(),/incomplete tx/);assert.equal(x.commits.Accounts,undefined);assert.equal(x.commits.DbTx,undefined);assert.equal(x.commits.DbGoals,undefined);assert.ok(x.commits.LoadErr);
});
for(const change of ['logout','view','revision'])test('delayed page after '+change+' cannot publish old financial data',async()=>{
 const d=deferred(),x=env({hook:q=>q.table==='transactions'&&q.rangeValue?d.promise:null});const p=x.run();await flush();
 if(change==='logout')x.logout();else if(change==='view')x.ctx.syncView.current={...x.ctx.syncView.current,key:'November',month:10};else x.ctx.syncEpoch.current++;
 d.resolve({data:[{id:9,date:'2026-10-15'}]});assert.deepEqual(await p,{status:'stale'});assert.deepEqual(x.commits,{});
});
test('nested signed URL response after logout cannot publish goals or prior base rows',async()=>{
 const d=deferred(),x=env({urls:()=>d.promise});x.data.goals[0].image_path='private.jpg';const p=x.run();await flush();assert.ok(x.calls.some(q=>q.table==='goals'));x.logout();d.resolve({data:[{path:'private.jpg',signedUrl:'mock://private'}]});assert.deepEqual(await p,{status:'stale'});assert.deepEqual(x.commits,{});
});
test('Mono response after logout cannot change accounts or freshness',async()=>{
 const d=deferred(),x=env({mono:()=>d.promise});x.data.accounts[0].bank='mono';const p=x.run({mono:true});await flush();x.logout();d.resolve({data:{ok:true,account:{id:1,balance:9999}}});assert.deepEqual(await p,{status:'stale'});assert.equal(x.commits.Accounts,undefined);assert.deepEqual(x.commits.MonoBal,{busy:true,msg:''});
});
test('empty goals background read never seeds; initial seed runs at most once',async()=>{
 const x=env();x.data.goals=[];await x.run();assert.deepEqual(x.commits.DbGoals,[]);assert.equal(x.calls.some(q=>q.filters.some(f=>f[0]==='insert')),false);
 await x.run({reason:'initial'});await x.run({reason:'initial'});assert.equal(x.calls.filter(q=>q.filters.some(f=>f[0]==='insert')).length,1);
});
test('view slicing preserves crossmonth, future linked payments and excludes future actual totals',()=>{
 const b={start:'2026-10-01',next:'2026-11-01',end:'2026-12-01',prev:'2026-09-01',today:'2026-10-20',current:'2026-10-06',finance:'2026-08-20',accSince:null,history:'all',month:'2026-10-01',fixed:'2026-08-01'};
 const rows=[{id:1,date:'2026-10-21',type:'expense',account_id:1,fixed_id:3},{id:2,date:'2026-11-01'},{id:3,date:'2026-09-05'},{id:4,date:'2026-10-13',type:'expense',account_id:1}];const v=helpers.refreshViewRows(rows,b);
 assert.deepEqual(v.db.map(t=>t.id),[1,4]);assert.deepEqual(v.next.map(t=>t.id),[2]);assert.deepEqual(v.prev.map(t=>t.id),[3]);assert.deepEqual(v.current.map(t=>t.id),[4]);assert.deepEqual(v.month.map(t=>t.id),[4]);assert.deepEqual(v.fixed.map(t=>t.id),[1]);
});

test('Mono-only failure commits complete DB snapshot but controller never advertises Updated',async()=>{
 const {createRefreshController}=(()=>{const s=require('node:fs').readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');const m={exports:{}};new Function('module',s.split('/* LIVE REFRESH CONTROLLER */')[1].split('/* END LIVE REFRESH CONTROLLER */')[0])(m);return m.exports})();const x=env({mono:()=>Promise.reject(Error('bank offline'))});x.data.accounts[0].bank='mono';const statuses=[];
 const controller=createRefreshController({enabled:true,refresh:(r,c)=>x.run(c),onStatus:s=>statuses.push(s)});
 assert.equal((await controller.start()).status,'error');assert.equal(x.commits.Accounts[0].balance,1000);assert.deepEqual(x.commits.DbTx.map(t=>t.id),[1]);assert.match(x.commits.MonoBal.msg,/Monobank/);assert.equal(statuses.at(-1).state,'degraded');assert.equal(statuses.some(s=>s.updatedAt!==undefined),false);controller.stop();
});
test('cached successful bank response remains valid; incomplete goal URLs reject atomic commit',async()=>{
 const x=env({mono:()=>Promise.resolve({data:{ok:true,cached:true,account:{id:1,balance:2300}}})});x.data.accounts[0].bank='mono';assert.deepEqual(await x.run({mono:true}),{ok:true});assert.equal(x.commits.Accounts[0].balance,2300);
 const y=env({urls:()=>Promise.resolve({data:[]})});y.data.goals[0].image_path='goal.jpg';await assert.rejects(y.run(),/фото/);assert.equal(y.commits.DbGoals,undefined);assert.equal(y.commits.Accounts,undefined);
});

test('background snapshot preserves dirty manual budget and savings before debounce fires',async()=>{
 const x=env();x.data.salary_config[0].budget_manual=10000;x.data.salary_config[0].savings_pct=20;
 x.ctx.syncLocalConfig.current={budget:25000,budgetPersisted:10000,budgetDirty:true,savings:35,savingsPersisted:20,savingsDirty:true};
 assert.deepEqual(await x.run(),{ok:true});assert.equal(x.commits.SalCfg.budget_manual,25000);assert.equal(x.commits.SavingsPct,35);assert.equal(x.ctx.bmPersisted.current,10000);assert.equal(x.ctx.savPersisted.current,20);
});
test('earlier config acknowledgement cannot clear a later pending edit',async()=>{
 const x=env();x.data.salary_config[0].budget_manual=20000;x.data.salary_config[0].savings_pct=25;
 x.ctx.syncLocalConfig.current={budget:30000,budgetPersisted:20000,budgetDirty:true,savings:40,savingsPersisted:25,savingsDirty:true};
 await x.run();assert.equal(x.commits.SalCfg.budget_manual,30000);assert.equal(x.commits.SavingsPct,40);assert.equal(x.ctx.bmPersisted.current,20000);assert.equal(x.ctx.savPersisted.current,25);
});

for(const kind of ['budget','savings'])test(kind+' actual debounce effect persists undo-to-old-value while prior write is pending',async()=>{
 const line=html.split(/\r?\n/).find(l=>l.startsWith('useEffect(()=>{if(!sb||!salCfg||salCfg.id==null')&&l.includes('syncConfigWrites.current.'+kind));
 const effectCode=line.slice('useEffect('.length,line.lastIndexOf(',['));const timers=[],writes=[],pending=[];
 const ref=current=>({current});const c={sb:{from:()=>({update:row=>({eq:()=>{writes.push(row);const d=deferred();pending.push(d);return d.promise}})})},salCfg:{id:1,budget_manual:15000},savingsPct:20,bmPersisted:ref(15000),savPersisted:ref(20),syncAuth:ref('user'),syncController:ref({}),syncConfigWrites:ref({budget:Promise.resolve(),savings:Promise.resolve()}),syncConfigPending:ref({budget:0,savings:0}),setTimeout:fn=>{timers.push(fn);return timers.length},clearTimeout:()=>{},setBmErr:()=>{},setLoadErr:()=>{},setLdN:()=>{},requestFinance:()=>Promise.resolve({status:'updated'})};
 const effect=new Function('ctx','with(ctx){return ('+effectCode+')}')(c);
 if(kind==='budget')c.salCfg.budget_manual=20000;else c.savingsPct=30;
 effect();assert.equal(timers.length,1);timers.shift()();await flush();assert.equal(writes.length,1);assert.equal(c.syncConfigPending.current[kind],1);
 if(kind==='budget')c.salCfg.budget_manual=15000;else c.savingsPct=20;
 effect();assert.equal(timers.length,1,'undo must schedule even though it equals old persisted value');timers.shift()();await flush();assert.equal(writes.length,1,'writes must remain serialized');
 pending.shift().resolve({});await flush();assert.equal(writes.length,2);assert.deepEqual(writes[1],kind==='budget'?{budget_manual:15000}:{savings_pct:20});pending.shift().resolve({});await flush();assert.equal(c.syncConfigPending.current[kind],0);assert.equal(kind==='budget'?c.bmPersisted.current:c.savPersisted.current,kind==='budget'?15000:20);
 // A new controller with the same uid is a new auth lifetime.
 if(kind==='budget')c.salCfg.budget_manual=25000;else c.savingsPct=40;
 effect();timers.shift()();await flush();c.syncController.current={};c.syncConfigPending.current={budget:0,savings:0};pending.shift().resolve({});await flush();assert.equal(c.syncConfigPending.current[kind],0);assert.equal(kind==='budget'?c.bmPersisted.current:c.savPersisted.current,kind==='budget'?15000:20);
});
test('actual auth reset clears remembered ids, drafts and busy locks for next login',()=>{
 const start=html.indexOf('    if(syncAuth.current!==uid){'),end=html.indexOf('\n    if(s&&s.user)',start),code=html.slice(start,end);
 assert.ok(start>0&&end>start);const c={},calls={};
 for(const m of code.matchAll(/\b(\w+)\.current/g))c[m[1]]={current:{old:true}};
 for(const m of code.matchAll(/\b(set\w+)\(/g))c[m[1]]=v=>calls[m[1]]=v;
 c.syncAuth.current='old';c.syncEpoch.current=0;c.syncController.current={stop:()=>calls.stop=true};
 new Function('ctx','uid','with(ctx){'+code+'}')(c,'new');
 for(const name of ['salSavedId','paySavedDraft','goalSavedDraft','goalPhotoPending'])assert.equal(c[name].current,null);
 for(const name of ['salSaveLock','paySaveLock','goalSaveLock'])assert.equal(c[name].current,false);
 assert.equal(calls.setSalSaving,false);assert.equal(calls.setPaySaving,false);assert.equal(calls.setGoalBusy,'');assert.equal(calls.setGoalEdit,null);assert.equal(calls.setPayEdit,null);assert.equal(calls.stop,true);assert.deepEqual(c.syncConfigPending.current,{budget:0,savings:0});
});
