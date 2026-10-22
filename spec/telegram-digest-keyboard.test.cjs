const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(path.join(__dirname,'../supabase/functions/telegram-digest/index.ts'),'utf8');

async function runDigest(choices=[]){
 const payloads=[];
 let handler;
 const body=stripTypeScriptTypes(source.replace(/^import .*;\r?\n/gm,''));
 const allowedEmail=source.match(/const ALLOWED_EMAILS\s*=\s*\[\s*'([^']+)'/)[1];
 const sb={auth:{admin:{getUserById:async()=>({data:{user:{email:allowedEmail}}})}},from(){return {select(){return this},not(){return this},then(resolve){return Promise.resolve({data:[{id:'test',telegram_chat_id:7}],error:null}).then(resolve)}}}};
 const kb={inline_keyboard:[[{text:'Оплачено',callback_data:'paid:test'}]]};
 const Deno={env:{get:key=>key==='DIGEST_SECRET'?'test-secret':'test'},serve:fn=>{handler=fn}};
 const fetch=async(url,options)=>{payloads.push(JSON.parse(options.body));return {ok:true}};
 const loadFinance=async()=>({projection:{},input:{},credits:[],txs:[],transactions:[],today:'2026-10-21'});
 const kyivNow=()=>({hour:9,date:'2026-10-21',today:'2026-10-21'});
 const {salaryKeyboard}=await import(require('node:url').pathToFileURL(path.join(__dirname,'../supabase/functions/_shared/salary-bot.ts')).href);
 new Function('Deno','createClient','fetch','loadFinance','dueTomorrow','formatDigest','formatReminder','kyivNow','paidKb','salaryOptions','salaryKeyboard','repaymentAdvice','repaymentAdviceText',body)(
  Deno,()=>sb,fetch,loadFinance,()=>[{callback:'paid:test'}],()=> 'Підсумок',()=> 'Нагадування',kyivNow,()=>kb,async()=>({choices}),salaryKeyboard,()=>({}),()=>'');
 const response=await handler(new Request('https://local.test',{method:'POST',headers:{'x-digest-secret':'test-secret'},body:'{}'}));
 assert.equal(response.status,200);
 return {payloads,kb};
}

test('scheduled digest preserves the hidden panel and reminder payment action',async()=>{
 const {payloads,kb}=await runDigest();
 assert.equal(payloads.length,2);
 assert.equal(payloads[0].text,'Підсумок');
 assert.equal(Object.hasOwn(payloads[0],'reply_markup'),false);
 assert.deepEqual(payloads[1].reply_markup,kb);
});


test('payday digest adds a one-click salary action without reopening the native panel',async()=>{
 const {payloads}=await runDigest([{date:'2026-10-21',kind:'advance',amount:20000,accountId:7,accountName:'Salary card'}]);
 assert.equal(payloads.length,3);
 assert.equal(payloads[1].reply_markup.inline_keyboard[0][0].callback_data,'sal:a:2026-10-21:7');
 assert.ok(payloads.every(p=>!p.reply_markup?.keyboard));
});
