const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createRefreshController}=(()=>{const s=require('node:fs').readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');const m={exports:{}};new Function('module',s.split('/* LIVE REFRESH CONTROLLER */')[1].split('/* END LIVE REFRESH CONTROLLER */')[0])(m);return m.exports})();
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve()};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
function harness(extra={}){
 let time=0,seq=0,visible=true,online=true,subscription,removed=0,max=0,count=0;
 const timers=new Map(),listeners=new Map(),calls=[],status=[],jobs=[];
 const controller=createRefreshController({enabled:true,resources:['accounts','transactions'],now:()=>time,
  setTimeout:(fn,ms)=>{const id=++seq;timers.set(id,{at:time+ms,fn});return id},clearTimeout:id=>timers.delete(id),
  isVisible:()=>visible,isOnline:()=>online,addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:(k,f)=>{assert.equal(listeners.get(k),f);listeners.delete(k)},
  subscribe:cb=>{subscription=cb;return()=>{removed++}},onStatus:s=>status.push(s),
  refresh:(resources,ctx)=>{count++;max=Math.max(max,count);const d=deferred();jobs.push(d);calls.push({resources,ctx});return d.promise.finally(()=>count--)},...extra});
 return {controller,calls,status,jobs,timers,listeners,get sub(){return subscription},get removed(){return removed},get max(){return max},
  setVisible:v=>visible=v,setOnline:v=>online=v,
  event:k=>{const fn=listeners.get(k);if(fn)fn()},
  tick:async ms=>{const end=time+ms;for(let n=0;n<100;n++){const next=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];if(!next||next[1].at>end)break;time=next[1].at;timers.delete(next[0]);next[1].fn();await flush()}time=end;await flush()},
  finish:async(i=jobs.length-1,result)=>{jobs[i].resolve(result);await flush()},
  start:async()=>{const p=controller.start();await flush();return{promise:p}}
 };
}

test('disabled is inert even when started, requested, stopped',async()=>{
 let touched=0;const hit=()=>{touched++;throw Error('disabled work')};
 const c=createRefreshController({enabled:false,refresh:hit,subscribe:hit,setTimeout:hit,addEventListener:hit,onStatus:hit});
 assert.equal((await c.start()).status,'disabled');assert.equal((await c.request(['x'],'manual')).status,'disabled');c.stop();assert.equal(touched,0);
 const implicit=createRefreshController({refresh:hit});assert.equal((await implicit.start()).status,'disabled');
});
test('start has one actual initial batch; SUBSCRIBED is not freshness',async()=>{
 const h=harness();const first=await h.start();assert.equal(h.calls.length,1);assert.equal(h.calls[0].ctx.mono,true);
 h.sub.onStatus('SUBSCRIBED');assert.equal(h.status.filter(s=>s.updatedAt!==undefined).length,0);
 await h.finish();assert.equal((await first.promise).status,'updated');assert.equal(h.status.at(-1).state,'updated');
 assert.equal((await h.controller.start()).status,'started');assert.equal(h.calls.length,1);h.controller.stop();
});
test('20 DB signals in 399ms form one trailing 400ms union; never Mono',async()=>{
 const h=harness();await h.start();await h.finish();
 for(let i=0;i<20;i++){h.sub.onChange(['r'+i%3]);await h.tick(21)}
 await h.tick(378);assert.equal(h.calls.length,1);await h.tick(1);assert.equal(h.calls.length,2);
 assert.deepEqual(h.calls[1].resources.sort(),['r0','r1','r2']);assert.equal(h.calls[1].ctx.mono,false);
 await h.finish();h.controller.stop();assert.equal(h.timers.size,0);
});
test('signals during active batch union into one followup; waiters belong to followup',async()=>{
 const h=harness();const initial=await h.start();let nextDone=false;
 const next=h.controller.request(['categories'],'mutation').then(x=>{nextDone=true;return x});
 h.sub.onChange(['salary']);h.sub.onChange(['categories']);await h.tick(1000);assert.equal(h.calls.length,1);
 await h.finish(0);assert.equal((await initial.promise).status,'updated');assert.equal(nextDone,false);assert.equal(h.calls.length,2);
 assert.deepEqual(h.calls[1].resources.sort(),['categories','salary']);assert.equal(h.max,1);
 await h.finish(1);assert.equal((await next).status,'updated');assert.equal(h.calls.length,2);h.controller.stop();
});
test('DB arriving during batch retains trailing debounce before followup',async()=>{
 const h=harness();await h.start();h.sub.onChange(['goals']);await h.tick(100);await h.finish(0);
 assert.equal(h.calls.length,1);await h.tick(299);assert.equal(h.calls.length,1);await h.tick(1);assert.equal(h.calls.length,2);await h.finish();h.controller.stop();
});
test('resume throttle is shared across focus visibility and online; Mono 60 seconds',async()=>{
 const h=harness();await h.start();await h.finish();h.event('focus');await flush();assert.equal(h.calls.length,2);assert.equal(h.calls[1].ctx.mono,false);await h.finish();
 await h.tick(14999);h.event('visibilitychange');h.event('online');await flush();assert.equal(h.calls.length,2);
 await h.tick(1);h.event('online');await flush();assert.equal(h.calls.length,3);assert.equal(h.calls[2].ctx.mono,false);await h.finish();
 await h.tick(45000);h.event('focus');await flush();assert.equal(h.calls.length,4);assert.equal(h.calls[3].ctx.mono,true);await h.finish();h.controller.stop();
});
test('failed Mono attempt consumes cooldown; manual forces but remains singleflight',async()=>{
 const h=harness();const a=await h.start();h.jobs[0].reject(Error('offline'));await flush();assert.equal((await a.promise).status,'error');assert.equal(h.status.at(-1).state,'degraded');
 const retry=h.controller.request(null,'retry');await flush();assert.equal(h.calls[1].ctx.mono,false);
 const manual=h.controller.request(null,'manual');await flush();assert.equal(h.calls.length,2);await h.finish(1);await retry;
 assert.equal(h.calls[2].ctx.mono,true);assert.equal(h.calls[2].ctx.forceMono,true);await h.finish(2);await manual;assert.equal(h.max,1);h.controller.stop();
});
test('hidden and offline signals stay pending and resume as one batch',async()=>{
 const h=harness();h.setVisible(false);const a=await h.start();h.sub.onChange(['goals']);await h.tick(1000);assert.equal(h.calls.length,0);assert.equal(h.timers.size,0);
 h.setVisible(true);h.setOnline(false);h.event('visibilitychange');await flush();assert.equal(h.calls.length,0);
 h.setOnline(true);h.event('online');await flush();assert.equal(h.calls.length,1);assert.ok(h.calls[0].resources.includes('goals'));await h.finish();await a.promise;h.controller.stop();
});
test('stop invalidates setters immediately, resolves all awaiters, drops callbacks and cleanup',async()=>{
 const h=harness();const initial=await h.start();const pending=h.controller.request(['goals'],'db');const old=h.sub;
 h.controller.stop();assert.equal(h.calls[0].ctx.isCurrent(),false);assert.equal((await initial.promise).status,'stale');assert.equal((await pending).status,'stale');
 assert.equal(h.listeners.size,0);assert.equal(h.timers.size,0);assert.equal(h.removed,1);const statuses=h.status.length;
 old.onChange(['accounts']);old.onStatus('CHANNEL_ERROR');await h.finish();await h.tick(50000);
 assert.equal(h.status.length,statuses);assert.equal(h.calls.length,1);h.controller.stop();assert.equal(h.removed,1);
});
test('restart waits for old active read, never publishes its outcome',async()=>{
 const h=harness();await h.start();const old=h.calls[0].ctx;h.controller.stop();const again=await h.start();assert.equal(h.calls.length,1);
 await h.finish(0);assert.equal(old.isCurrent(),false);assert.equal(h.calls.length,2);assert.equal(h.max,1);assert.equal(h.status.filter(s=>s.updatedAt!==undefined).length,0);
 await h.finish(1);assert.equal((await again.promise).status,'updated');h.controller.stop();
});
test('channel errors degrade, reconnection catches up once without fake freshness',async()=>{
 const h=harness();await h.start();await h.finish();
 for(const s of ['CHANNEL_ERROR','TIMED_OUT','CLOSED'])h.sub.onStatus(s);
 assert.equal(h.status.at(-1).state,'degraded');const updated=h.status.filter(s=>s.updatedAt!==undefined).length;
 h.sub.onStatus('SUBSCRIBED');h.sub.onStatus('SUBSCRIBED');await flush();assert.equal(h.calls.length,2);assert.equal(h.status.filter(s=>s.updatedAt!==undefined).length,updated);
 await h.finish();assert.equal(h.status.at(-1).state,'updated');h.controller.stop();
});
test('subscription throws and explicit unsuccessful result resolve errors without retry loops',async()=>{
 const h=harness({subscribe:()=>{throw Error('unavailable')}});const a=await h.start();assert.ok(h.status.some(s=>s.reason==='subscription'));
 await h.finish(0,{ok:false});assert.equal((await a.promise).status,'error');await h.tick(100000);assert.equal(h.calls.length,1);assert.equal(h.timers.size,0);h.controller.stop();
});

test('resume throttle cannot strand a pending manual request after hidden interval',async()=>{
 const h=harness();await h.start();await h.finish();h.event('focus');await flush();await h.finish();
 h.setVisible(false);const manual=h.controller.request(['goals'],'manual');await h.tick(2000);assert.equal(h.calls.length,2);
 h.setVisible(true);h.event('visibilitychange');await flush();assert.equal(h.calls.length,3);await h.finish();assert.equal((await manual).status,'updated');h.controller.stop();
});
test('synchronous refresh throw and explicit stale results never advertise freshness',async()=>{
 const h=harness({refresh:()=>{throw Error('read failed')}});assert.equal((await h.controller.start()).status,'error');assert.equal(h.status.some(s=>s.updatedAt!==undefined),false);h.controller.stop();
 const s=harness({refresh:()=>Promise.resolve({status:'stale'})});assert.equal((await s.controller.start()).status,'stale');assert.equal(s.status.some(x=>x.updatedAt!==undefined),false);s.controller.stop();
});

test('first late subscription emits connection-only transition after initial data success',async()=>{
 const h=harness();await h.start();await h.finish();const dataStatus=h.status.at(-1);
 assert.equal(dataStatus.state,'updated');assert.equal(dataStatus.connection,'connecting');
 await h.tick(5000);h.sub.onStatus('SUBSCRIBED');
 assert.deepEqual(h.status.at(-1),{state:'connection',connection:'subscribed',reason:'subscription'});
 assert.equal(h.status.filter(s=>s.updatedAt!==undefined).length,1);assert.equal(h.calls.length,1);
 const count=h.status.length;h.sub.onStatus('SUBSCRIBED');assert.equal(h.status.length,count);h.controller.stop();
});
test('unknown subscription status is degraded, then catches up on reconnection',async()=>{
 const h=harness();await h.start();await h.finish();h.sub.onStatus('UNRECOGNIZED');
 assert.deepEqual(h.status.at(-1),{state:'degraded',connection:'unknown',reason:'subscription'});
 const p=h.controller.request(null,'manual');await flush();await h.finish();await p;
 assert.equal(h.status.at(-1).state,'degraded');assert.equal(h.status.at(-1).connection,'unknown');
 h.sub.onStatus('SUBSCRIBED');await flush();assert.equal(h.calls.length,3);await h.finish();h.controller.stop();
});
test('a stale loader outcome exits refreshing even with no following request',async()=>{
 const h=harness();const a=await h.start();await h.finish(0,{status:'stale'});
 assert.equal((await a.promise).status,'stale');assert.deepEqual(h.status.at(-1),{state:'stale',connection:'connecting',reason:'initial'});
 assert.equal(h.status.some(s=>s.updatedAt!==undefined),false);assert.equal(h.timers.size,0);assert.equal(h.calls.length,1);h.controller.stop();
});

test('mutation/view after cooldown never pull bank; resume does',async()=>{
 const h=harness();await h.start();await h.finish();await h.tick(61000);
 for(const reason of ['mutation','view','db']){const p=h.controller.request(['accounts'],reason);await h.tick(400);assert.equal(h.calls.at(-1).ctx.mono,false);await h.finish();await p;}
 h.event('focus');await flush();assert.equal(h.calls.at(-1).ctx.mono,true);await h.finish();h.controller.stop();
});
