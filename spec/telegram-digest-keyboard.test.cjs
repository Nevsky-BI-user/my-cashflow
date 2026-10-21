const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(path.join(__dirname,'../supabase/functions/telegram-digest/index.ts'),'utf8');

test('scheduled digest preserves the hidden panel and reminder payment action',async()=>{
 const payloads=[];
 let handler;
 const body=stripTypeScriptTypes(source.replace(/^import .*;\r?\n/gm,''));
 const allowedEmail=source.match(/const ALLOWED_EMAILS\s*=\s*\[\s*'([^']+)'/)[1];
 const sb={auth:{admin:{getUserById:async()=>({data:{user:{email:allowedEmail}}})}},from(){return {select(){return this},not(){return this},then(resolve){return Promise.resolve({data:[{id:'test',telegram_chat_id:7}],error:null}).then(resolve)}}}};
 const kb={inline_keyboard:[[{text:'Оплачено',callback_data:'paid:test'}]]};
 const Deno={env:{get:key=>key==='DIGEST_SECRET'?'test-secret':'test'},serve:fn=>{handler=fn}};
 const fetch=async(url,options)=>{payloads.push(JSON.parse(options.body));return {ok:true}};
 const loadFinance=async()=>({projection:{},credits:[],transactions:[],today:'2026-10-21'});
 const kyivNow=()=>({hour:9,today:'2026-10-21'});
 new Function('Deno','createClient','fetch','loadFinance','dueTomorrow','formatDigest','formatReminder','kyivNow','paidKb',body)(
  Deno,()=>sb,fetch,loadFinance,()=>[{callback:'paid:test'}],()=> 'Підсумок',()=> 'Нагадування',kyivNow,()=>kb);
 const response=await handler(new Request('https://local.test',{method:'POST',headers:{'x-digest-secret':'test-secret'},body:'{}'}));
 assert.equal(response.status,200);
 assert.equal(payloads.length,2);
 assert.equal(payloads[0].text,'Підсумок');
 assert.equal(Object.hasOwn(payloads[0],'reply_markup'),false);
 assert.deepEqual(payloads[1].reply_markup,kb);
});
