// Підпис запитів мовного сервісу (_shared/voice-auth.ts): той самий вектор перевіряє Python-клієнт voice-service
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/voice-auth.ts')).href);
const SECRET='0123456789abcdef0123456789abcdef-test-secret';
const BODY='{"op":"claim","wait":50}';

test('контрольний вектор HMAC збігається з Python (hmac.new(secret, f"{ts}\n"+body, sha256))',async()=>{
 const {voiceSign}=await mod();
 assert.equal(await voiceSign(SECRET,1794600000,BODY),'adbf98413f862dbc6a3cc4990d70ad696f1df493b3c4ad440d25a0e10cd7341c');
});

test('підпис приймається, підробка, чуже тіло, стара мітка і короткий секрет відхиляються',async()=>{
 const {voiceSign,voiceVerify}=await mod();
 const ts=1794600000, sig=await voiceSign(SECRET,ts,BODY);
 assert.equal(await voiceVerify(SECRET,String(ts),sig,BODY,ts+5),true);
 assert.equal(await voiceVerify(SECRET,String(ts),sig,BODY.replace('50','49'),ts),false);
 assert.equal(await voiceVerify(SECRET,String(ts),sig.replace(/^./,c=>c==='0'?'1':'0'),BODY,ts),false);
 assert.equal(await voiceVerify(SECRET,String(ts),sig,BODY,ts+121),false);
 assert.equal(await voiceVerify(SECRET,String(ts),sig,BODY,ts-121),false);
 assert.equal(await voiceVerify('short',String(ts),await voiceSign('short',ts,BODY),BODY,ts),false);
 assert.equal(await voiceVerify(SECRET,null,sig,BODY,ts),false);
 assert.equal(await voiceVerify(SECRET,String(ts),sig.toUpperCase(),BODY,ts),false);
});
