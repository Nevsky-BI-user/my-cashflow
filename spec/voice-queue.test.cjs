// Черга мовного сервісу (_shared/voice-queue.ts): підпис перед базою, claim з очікуванням, done лише для взятого,
// бот чекає обмежений час і завжди видаляє запис. База: імітація в памʼяті з тими самими правилами, що й SQL міграції 54.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const imp=(f)=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/'+f)).href);
const SECRET='0123456789abcdef0123456789abcdef-test-secret';

function fakeDb(){
 const db={jobs:new Map(),seq:0,worker:null,calls:[],now:Date.parse('2026-11-14T10:00:00Z')};
 const q=(table)=>{
  const st={table,op:'select',filters:{},payload:null};
  const run=()=>{
   db.calls.push(st.op+':'+table);
   if(table==='voice_jobs'){
    if(st.op==='insert'){const id=++db.seq;db.jobs.set(id,{id,...st.payload,status:'queued',created_at:db.now});return {data:{id},error:null};}
    if(st.op==='delete'){db.jobs.delete(st.filters.id);return {data:null,error:null};}
    const j=db.jobs.get(st.filters.id);return {data:j?{status:j.status,output:j.output,kind:j.kind}:null,error:null};
   }
   if(table==='voice_worker')return {data:db.worker,error:null};
   throw new Error('table '+table);
  };
  const b={
   insert(p){st.op='insert';st.payload=p;return b;}, delete(){st.op='delete';return b;},
   select(){return b;}, eq(k,v){st.filters[k]=v;return b;},
   single(){return Promise.resolve(run());}, maybeSingle(){return Promise.resolve(run());},
   then(res,rej){return Promise.resolve(run()).then(res,rej);},
  };
  return b;
 };
 db.sb={
  from:q,
  async rpc(name,args){
   db.calls.push('rpc:'+name);
   if(name==='voice_heartbeat'){db.worker={last_seen:new Date(db.now).toISOString(),info:args.p_info};return {data:null,error:null};}
   if(name==='voice_claim'){
    const j=[...db.jobs.values()].find(x=>x.status==='queued'&&db.now-x.created_at<args.p_max_age_s*1000);
    if(!j)return {data:[],error:null};
    j.status='claimed';return {data:[{id:j.id,kind:j.kind,input:j.input}],error:null};
   }
   if(name==='voice_done'){
    const j=db.jobs.get(args.p_id);
    if(!j||j.status!=='claimed')return {data:false,error:null};
    j.status=args.p_ok?'done':'failed';j.output=args.p_output;return {data:true,error:null};
   }
   throw new Error('rpc '+name);
  },
 };
 return db;
}

async function signed(body,{ts,secret=SECRET}={}){
 const {voiceSign,nowTs}=await imp('voice-auth.ts');
 const t=ts??nowTs();
 return new Request('http://x/voice-jobs',{method:'POST',body,headers:{'X-Voice-Ts':String(t),'X-Voice-Sig':await voiceSign(secret,t,body)}});
}

test('без правильного підпису жодного звернення до бази',async()=>{
 const {handleVoiceJobs}=await imp('voice-queue.ts');
 const db=fakeDb();
 const bad=await handleVoiceJobs(await signed('{"op":"claim","wait":0}',{secret:SECRET+'x'}),{sb:db.sb,secret:SECRET});
 assert.equal(bad.status,401);
 const old=await handleVoiceJobs(await signed('{"op":"claim","wait":0}',{ts:1000}),{sb:db.sb,secret:SECRET});
 assert.equal(old.status,401);
 const noSecret=await handleVoiceJobs(await signed('{"op":"claim","wait":0}'),{sb:db.sb,secret:''});
 assert.equal(noSecret.status,401);
 assert.deepEqual(db.calls,[]);
});

test('claim: мітка звʼязку, порожня черга після очікування, потім завдання; done лише один раз',async()=>{
 const {handleVoiceJobs,voiceOnline}=await imp('voice-queue.ts');
 const db=fakeDb();
 let clock=db.now;const nowMs=()=>clock;const sleep=async(ms)=>{clock+=ms;};
 const empty=await handleVoiceJobs(await signed('{"op":"claim","wait":2,"info":{"v":"1"}}'),{sb:db.sb,secret:SECRET,nowMs,sleep});
 assert.deepEqual(await empty.json(),{job:null});
 assert.ok(clock-db.now>=1500&&clock-db.now<=2000,'очікування в межах wait');
 assert.equal(await voiceOnline(db.sb,db.now+60000),true);
 assert.equal(await voiceOnline(db.sb,db.now+91000),false);
 db.jobs.set(7,{id:7,kind:'stt',input:{audio_b64:'AAAA',mime:'audio/ogg'},status:'queued',created_at:db.now});
 const got=await (await handleVoiceJobs(await signed('{"op":"claim","wait":50}'),{sb:db.sb,secret:SECRET,nowMs,sleep})).json();
 assert.deepEqual(got,{job:{id:7,kind:'stt',input:{audio_b64:'AAAA',mime:'audio/ogg'}}});
 const again=await (await handleVoiceJobs(await signed('{"op":"claim","wait":0}'),{sb:db.sb,secret:SECRET,nowMs,sleep})).json();
 assert.deepEqual(again,{job:null},'взяте завдання вдруге не видається');
 const done=await (await handleVoiceJobs(await signed('{"op":"done","id":7,"ok":true,"output":{"text":"скільки на продукти","extra":1}}'),{sb:db.sb,secret:SECRET})).json();
 assert.deepEqual(done,{accepted:true});
 assert.deepEqual(db.jobs.get(7).output,{text:'скільки на продукти'},'зайві поля не зберігаються');
 const twice=await (await handleVoiceJobs(await signed('{"op":"done","id":7,"ok":true,"output":{"text":"інше"}}'),{sb:db.sb,secret:SECRET})).json();
 assert.deepEqual(twice,{accepted:false});
 assert.equal(db.jobs.get(7).output.text,'скільки на продукти');
});

test('done: биті дані озвучення = помилка завдання, невідоме завдання не приймається',async()=>{
 const {handleVoiceJobs}=await imp('voice-queue.ts');
 const db=fakeDb();
 db.jobs.set(3,{id:3,kind:'tts',input:{text:'т'},status:'claimed',created_at:db.now});
 const r=await (await handleVoiceJobs(await signed('{"op":"done","id":3,"ok":true,"output":{"audio_b64":"<script>"}}'),{sb:db.sb,secret:SECRET})).json();
 assert.deepEqual(r,{accepted:true});
 assert.equal(db.jobs.get(3).status,'failed');
 const unknown=await (await handleVoiceJobs(await signed('{"op":"done","id":99,"ok":true,"output":{"text":"x"}}'),{sb:db.sb,secret:SECRET})).json();
 assert.deepEqual(unknown,{accepted:false});
});

test('бот: результат вчасно, таймаут і помилка дають null; запис видаляється завжди',async()=>{
 const {voiceRun}=await imp('voice-queue.ts');
 for(const scenario of ['done','failed','timeout']){
  const db=fakeDb();
  let clock=0;const nowMs=()=>clock;
  const sleep=async(ms)=>{clock+=ms;const j=db.jobs.get(1);
   if(j&&clock>=600&&scenario!=='timeout'){j.status=scenario;j.output=scenario==='done'?{text:'привіт'}:{error:'x'};}};
  const out=await voiceRun(db.sb,'stt',{audio_b64:'AAAA'},5000,{nowMs,sleep,pollMs:300});
  assert.deepEqual(out,scenario==='done'?{text:'привіт'}:null,scenario);
  assert.equal(db.jobs.size,0,scenario+': запис видалено');
  if(scenario==='timeout')assert.ok(clock>=5000&&clock<5600);
 }
});
