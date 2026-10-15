const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
function source(name,next){const start=html.indexOf('const '+name+'=')+name.length+7;assert.ok(start>name.length+7);return html.slice(start,html.indexOf(next,start)).trim().replace(/;$/,'');}
function run(name,next,ctx){return new Function(...Object.keys(ctx),'return '+source(name,next))(...Object.values(ctx));}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function mockDb(){const pending=[],calls=[];return {pending,calls,from(table){const call={table};const q={};for(const method of ['insert','update','delete','eq','select','single','order'])q[method]=(...args)=>{call[method]=args;return q;};q.then=(a,b)=>{calls.push(call);const d=deferred();pending.push(d);return d.promise.then(a,b)};return q;}};}
const limits={saveGoal:'\nconst deleteGoal=',deleteGoal:'\n// порядок:',savePay:';const delPay=',delPay:';const togglePay=',saveSalary:';const salPrevM=',saveCatLimit:'\n'};
function editor(kind){
 const db=mockDb(),state={draft:kind==='goal'?{id:null,name:'Trip',target:1000,sort:0}:kind==='pay'?{id:null,name:'Rent',amount:'2500',day:12,kind:'fixed'}:{rate:10000},busy:false,error:'',closed:false,reloads:0};
 const editorRef={current:state.draft},draftKey={current:Symbol()};
 const setDraft=v=>{state.draft=typeof v==='function'?v(state.draft):v;editorRef.current=state.draft;};
 const lock={current:false},saved={current:null};let failReload=false;
 const reload=async strict=>{assert.equal(strict,true);state.reloads++;if(failReload)throw Error('refresh offline')};
 const ctx={sb:db,syncAuth:{current:'synthetic'},syncController:{current:{}},requestFinance:()=>{state.financeRequests=(state.financeRequests||0)+1;return Promise.resolve({status:'updated'})},session:{user:{id:'synthetic'}},confirm:()=>true};
 Object.assign(ctx,{[kind==='salary'?'salEditor':kind+'Editor']:editorRef,[kind==='salary'?'salDraftKey':kind+'DraftKey']:draftKey});
 const setBusy=v=>state.busy=v,setError=v=>state.error=v;
 if(kind==='goal')Object.assign(ctx,{goalEdit:state.draft,goalSaveLock:lock,goalSavedDraft:saved,goalPhotoPending:{current:null},goalBusy:'',goalLocal:false,setGoalErr:setError,setGoalBusy:setBusy,setGoalEdit:setDraft,loadGoals:reload});
 if(kind==='pay')Object.assign(ctx,{payEdit:state.draft,paySaveLock:lock,paySavedDraft:saved,paySaving:false,setPayErr:setError,setPaySaving:setBusy,setPayEdit:setDraft,loadCredits:reload,loadFixed:reload,payDone:(e,id)=>{state.closed=true;setDraft({...e,id})}});
 if(kind==='salary')Object.assign(ctx,{salDraft:state.draft,salSaveLock:lock,salSavedId:saved,salCfg:null,salNow:{},salParse:d=>({fields:d}),setSalErr:setError,setSalSaving:setBusy,setSalCfg:v=>state.cfg=v,setShowSalary:v=>state.closed=!v});
 const name=kind==='goal'?'saveGoal':kind==='pay'?'savePay':'saveSalary';
 return {db,state,lock,ctx,save:run(name,limits[name],ctx),switchDraft:setDraft,failReload:v=>failReload=v};
}
for(const kind of ['goal','pay','salary']){
 test(kind+': same-render duplicate submit makes one insert',async()=>{const x=editor(kind);const a=x.save(),b=x.save();await tick();assert.equal(x.db.calls.length,1);x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await Promise.all([a,b]);assert.equal(x.lock.current,false);assert.equal(x.state.busy,kind==='goal'?'':false);});
 test(kind+': rejection retains draft, unlocks and permits retry',async()=>{const x=editor(kind),draft=x.state.draft;const a=x.save();await tick();x.db.pending.shift().reject(Error('network offline'));await a;assert.equal(x.state.draft,draft);assert.match(x.state.error,/network offline/);assert.equal(x.lock.current,false);const b=x.save();await tick();assert.equal(x.db.calls.length,2);x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await b;assert.equal(x.state.error,'');});
}
for(const kind of ['goal','pay']){
 test(kind+': insert followed by failed refresh preserves id and retries as update',async()=>{const x=editor(kind);x.failReload(true);const a=x.save();await tick();x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await a;assert.equal(x.state.draft.id,7);assert.match(x.state.error,/Збережено.*оновити/);assert.equal(x.lock.current,false);x.failReload(false);const b=x.save();await tick();assert.ok(x.db.calls[1].update);assert.equal(x.db.calls.filter(c=>c.insert).length,1);x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await b;});
 test(kind+': delete rejection unlocks and retains editor',async()=>{const x=editor(kind);x.ctx[kind==='goal'?'goalEdit':'payEdit'].id=7;const name=kind==='goal'?'deleteGoal':'delPay';const remove=run(name,limits[name],x.ctx);const a=remove(),b=remove();await tick();assert.equal(x.db.calls.length,1);x.db.pending.shift().reject(Error('delete offline'));await Promise.all([a,b]);assert.match(x.state.error,/delete offline/);assert.equal(x.state.draft.id,7);assert.equal(x.lock.current,false);});
}
for(const kind of ['goal','pay','salary']){
 test(kind+': pending editor A resolve/reject never patches or closes editor B',async()=>{for(const outcome of ['reject','resolve','refresh']){const x=editor(kind),a=x.save();await tick();const b=kind==='salary'?{rate:9000}:{id:null,name:'New editor B',target:9000,kind:'fixed',amount:'9000',day:19};x.switchDraft(b);if(outcome==='refresh')x.failReload(true);if(outcome==='reject')x.db.pending.shift().reject(Error('A failure'));else x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await a;assert.equal(x.state.draft,b);assert.equal(b.id,kind==='salary'?undefined:null);assert.equal(x.state.closed,false);assert.equal(x.state.error,'');assert.equal(x.lock.current,false);if(kind!=='salary'&&outcome!=='reject')assert.equal(x.ctx[kind+'SavedDraft'].current.id,7);}});
}
for(const kind of ['goal','pay'])test(kind+': pending delete cannot close or show errors in editor B',async()=>{for(const rejected of [false,true]){const x=editor(kind);x.state.draft.id=7;const name=kind==='goal'?'deleteGoal':'delPay',a=run(name,limits[name],x.ctx)();await tick();const b={id:19,name:'Editor B'};x.switchDraft(b);if(rejected)x.db.pending.shift().reject(Error('delete A failed'));else x.db.pending.shift().resolve({});await a;assert.equal(x.state.draft,b);assert.equal(x.state.error,'');assert.equal(x.lock.current,false);}});
test('goal: upload failure retains created id; retry updates original row and uploads again',async()=>{
 const x=editor('goal'),uploads=[];x.state.draft.blob={synthetic:true};x.db.storage={from(){return {upload(){const p=deferred();uploads.push(p);return p.promise},remove(){return Promise.resolve({})}}}};
 const a=x.save();await tick();x.db.pending.shift().resolve({data:{id:7}});await tick();uploads.shift().reject(Error('upload offline'));await a;assert.equal(x.state.draft.id,7);assert.ok(x.state.draft.blob);assert.match(x.state.error,/upload offline/);
 x.ctx.goalEdit=x.state.draft;const b=run('saveGoal',limits.saveGoal,x.ctx)();await tick();assert.ok(x.db.calls[1].update);x.db.pending.shift().resolve({});await tick();uploads.shift().resolve({});await tick();assert.deepEqual(x.db.calls[2].eq,['id',7]);x.db.pending.shift().resolve({});await b;assert.equal(x.db.calls.filter(c=>c.insert).length,1);assert.equal(x.state.draft,null);
});
test('goal: stale image upload and photo compression never patch editor B',async()=>{
 const x=editor('goal'),upload=deferred();x.state.draft.blob={synthetic:true};x.db.storage={from(){return {upload:()=>upload.promise,remove:()=>Promise.resolve({})}}};const a=x.save();await tick();x.db.pending.shift().resolve({data:{id:7}});await tick();const b={id:22,name:'B',target:2000,image:'B.jpg'};x.switchDraft(b);upload.resolve({});await tick();x.db.pending.shift().resolve({});await a;assert.equal(x.state.draft,b);assert.equal(b.image,'B.jpg');assert.equal(x.state.error,'');
 for(const rejected of [false,true]){const y=editor('goal'),photo=deferred();y.ctx.compressImage=()=>photo.promise;y.ctx.URL={createObjectURL:()=>{throw Error('stale photo must not create URL')}};const pick=run('pickGoalPhoto','\n',y.ctx);pick({target:{files:[{}],value:'photo'}});const other={id:33,name:'Other',image:'other.jpg'};y.switchDraft(other);if(rejected)photo.reject(Error('old photo fail'));else photo.resolve({size:30});await tick();assert.equal(y.state.draft,other);assert.equal(y.state.error,'');}
});
function traceEffects(ctx){const calls=[];for(const key of Object.keys(ctx)){if(!key.startsWith('set')&&!['requestFinance','loadGoals','loadCredits','loadFixed','payDone'].includes(key))continue;const fn=ctx[key];ctx[key]=(...args)=>{calls.push(key);return fn(...args)}}return calls;}
for(const kind of ['goal','pay','salary'])test(kind+': logout or same-user controller replacement suppresses pending write effects',async()=>{
 for(const changed of ['logout','same-user-controller'])for(const rejected of [false,true]){
  const x=editor(kind),effects=traceEffects(x.ctx),name=kind==='goal'?'saveGoal':kind==='pay'?'savePay':'saveSalary';
  if(kind==='goal'){x.state.draft.blob={synthetic:true};x.db.storage={from(){throw Error('old auth must not upload')}};}
  const a=run(name,limits[name],x.ctx)();await tick();effects.length=0;x.ctx.syncController.current={};if(changed==='logout')x.ctx.syncAuth.current=null;
  if(rejected)x.db.pending.shift().reject(Error('old auth rejected'));else x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});
  await a;assert.deepEqual(effects,[]);assert.equal(x.ctx[kind==='salary'?'salSavedId':kind+'SavedDraft'].current,null);assert.equal(x.db.calls.length,1);assert.equal(x.lock.current,false);
 }
});
test('goal: auth change during existing-row update prevents upload, image removal and reload',async()=>{
 for(const change of ['logout','same-user-controller'])for(const image of ['blob','dropImg']){
  const x=editor('goal'),effects=traceEffects(x.ctx);x.state.draft.id=7;x.state.draft.image='old.jpg';x.state.draft[image]=image==='blob'?{synthetic:true}:true;
  x.db.storage={from(){throw Error('old auth must not access storage')}};
  const a=run('saveGoal',limits.saveGoal,x.ctx)();await tick();assert.ok(x.db.calls[0].update);effects.length=0;
  x.ctx.syncController.current={};if(change==='logout')x.ctx.syncAuth.current=null;
  x.db.pending.shift().resolve({});await a;assert.deepEqual(effects,[]);assert.equal(x.db.calls.length,1);assert.equal(x.lock.current,false);
 }
});
for(const kind of ['goal','pay'])test(kind+': logout suppresses pending deletion reload, storage removal and UI writes',async()=>{
 for(const rejected of [false,true]){const x=editor(kind),effects=traceEffects(x.ctx);x.state.draft.id=7;x.state.draft.image='old.jpg';x.db.storage={from(){throw Error('old auth must not remove image')}};const name=kind==='goal'?'deleteGoal':'delPay',a=run(name,limits[name],x.ctx)();await tick();effects.length=0;x.ctx.syncAuth.current=null;x.ctx.syncController.current=null;if(rejected)x.db.pending.shift().reject(Error('old auth'));else x.db.pending.shift().resolve({});await a;assert.deepEqual(effects,[]);assert.equal(x.db.calls.length,1);assert.equal(x.lock.current,false);}
});
test('goal: auth change during upload or image-path write prevents later writes, remove and reload',async()=>{
 for(const stage of ['upload','image-path'])for(const rejected of [false,true]){
  const x=editor('goal'),upload=deferred(),effects=traceEffects(x.ctx);x.state.draft.id=7;x.state.draft.image='old.jpg';x.state.draft.blob={synthetic:true};x.db.storage={from(){return {upload:()=>upload.promise,remove:()=>{effects.push('remove');return Promise.resolve({})}}}};
  const a=run('saveGoal',limits.saveGoal,x.ctx)();await tick();x.db.pending.shift().resolve({});await tick();if(stage==='image-path'){upload.resolve({});await tick();assert.equal(x.db.calls.length,2);}
  effects.length=0;x.ctx.syncController.current={};const response=stage==='upload'?upload:x.db.pending.shift();if(rejected)response.reject(Error('old storage auth'));else response.resolve({});await a;assert.deepEqual(effects,[]);assert.equal(x.db.calls.length,stage==='upload'?1:2);assert.ok(x.state.draft.blob);
 }
});
test('goal: auth change during image removal write or compression suppresses late effects',async()=>{
 const x=editor('goal'),effects=traceEffects(x.ctx);x.state.draft.id=7;x.state.draft.image='old.jpg';x.state.draft.dropImg=true;x.db.storage={from(){throw Error('old auth must not remove')}};const a=run('saveGoal',limits.saveGoal,x.ctx)();await tick();x.db.pending.shift().resolve({});await tick();assert.equal(x.db.calls.length,2);effects.length=0;x.ctx.syncAuth.current=null;x.db.pending.shift().resolve({});await a;assert.deepEqual(effects,[]);
 for(const rejected of [false,true]){const y=editor('goal'),photo=deferred(),late=traceEffects(y.ctx);y.ctx.compressImage=()=>photo.promise;y.ctx.URL={createObjectURL:()=>{throw Error('old auth must not create URL')}};run('pickGoalPhoto','\n',y.ctx)({target:{files:[{}],value:'photo'}});late.length=0;y.ctx.syncController.current={};if(rejected)photo.reject(Error('old auth'));else photo.resolve({size:3});await tick();assert.deepEqual(late,[]);}
});
test('old auth completion cannot release a newer session write lock',async()=>{for(const kind of ['goal','pay','salary']){const x=editor(kind),a=x.save();await tick();x.ctx.syncController.current={};const newerLock={newSession:true};x.lock.current=newerLock;x.db.pending.shift().resolve({data:kind==='pay'?[{id:7}]:{id:7}});await a;assert.equal(x.lock.current,newerLock);}});
function categories(){const db=mockDb();const state={cats:[{id:1,limit:20,limitAbs:100},{id:2,limit:80,limitAbs:null}]};const ctx={sb:db,requestFinance:()=>Promise.resolve({status:'updated'}),dbCats:state.cats,allCats:state.cats,wCats:state.cats,catLimitRevision:{current:{}},catLimitQueue:{current:{}},catLimitConfirmed:{current:{}},setDbCats:v=>state.cats=typeof v==='function'?v(state.cats):v};return {db,state,save:run('saveCatLimit','\n',ctx)};}
test('category requests serialize per id; late old failure cannot undo newer success',async()=>{const x=categories(),a=x.save({id:1},'abs',200);await tick();const b=x.save({id:1},'abs',300);await tick();assert.equal(x.db.calls.length,1);assert.equal(x.state.cats[0].limitAbs,300);x.db.pending.shift().reject(Error('old failure'));assert.equal(await a,'');await tick();assert.equal(x.db.calls.length,2);x.db.pending.shift().resolve({});assert.equal(await b,'');assert.equal(x.state.cats[0].limitAbs,300);});
test('category writes execute in edit order, so latest successful edit persists',async()=>{const x=categories(),a=x.save({id:1},'abs',200),b=x.save({id:1},'abs',300);await tick();assert.equal(x.db.calls.length,1);let persisted=x.db.calls[0].update[0].limit_abs;x.db.pending.shift().resolve({});await a;await tick();assert.equal(x.db.calls.length,2);persisted=x.db.calls[1].update[0].limit_abs;x.db.pending.shift().resolve({});await b;assert.equal(persisted,300);assert.equal(x.state.cats[0].limitAbs,300);});
test('category latest failure rolls back to confirmed server value, including two consecutive failures',async()=>{for(const oldSucceeds of [false,true]){const x=categories(),a=x.save({id:1},'abs',200),b=x.save({id:1},'abs',300);await tick();if(oldSucceeds)x.db.pending.shift().resolve({});else x.db.pending.shift().reject(Error('first fail'));await a;await tick();x.db.pending.shift().reject(Error('latest fail'));assert.match(await b,/latest fail/);assert.equal(x.state.cats[0].limitAbs,oldSucceeds?200:100);}});
test('strict loader queue facades reject unsuccessful batches and never directly seed goals',async()=>{
 for(const [name,resource] of [['loadGoals','goals'],['loadCredits','credits'],['loadFixed','fixed_payments']]){
  for(const mode of ['reject','error','stale','updated']){
   const calls=[],ctx={sb:{},syncEpoch:{current:0},syncController:{current:{request(resources,reason){calls.push({resources,reason});return mode==='reject'?Promise.reject(Error('offline')):Promise.resolve({status:mode})}}}};
   ctx.requestFinance=run('requestFinance','\n',ctx);
   const load=run(name,'\n',ctx),request=load(true);
   if(mode==='updated')assert.equal((await request).status,'updated');else await assert.rejects(request);
   assert.deepEqual(calls,[{resources:[resource],reason:'mutation'}]);assert.equal(ctx.syncEpoch.current,1);
  }
 }
});
