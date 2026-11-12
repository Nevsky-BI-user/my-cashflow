const test = require('node:test');
const assert = require('node:assert/strict');
const { selectMonoAccount, monoBalancePatch, exactMonoAccount, registrationTarget, allowedMonoOwner, migratedMonoAccount, statementRows, isMonoMigrationEntry } = require('../supabase/functions/_shared/mono-accounts.ts');
const husband = { id: 1, user_id: 'husband', bank: 'mono', mono_account_id: 'h', card_last4: '2674' };
const wife = { id: 2, user_id: 'wife', bank: 'mono', mono_account_id: 'w', card_last4: '2674' };
const card = { id: 'w', currencyCode: 980, type: 'black', maskedPan: ['4444******2674'], balance: 120000, creditLimit: 200000 };
test('explicit suffix picks one provider card and rejects same suffix collision', () => {
 assert.equal(selectMonoAccount([card,{...card,id:'other',maskedPan:['4444******9999']}], [], '2674').id, 'w');
 assert.throws(() => selectMonoAccount([card,{...card,id:'other'}], [], '2674'), /ambiguous/);
 assert.throws(() => selectMonoAccount([card], [], '0000'), /no_uah/);
});
test('multiple black UAH cards never choose first; established mapping wins', () => {
 const cards=[card,{...card,id:'h'}];
 assert.throws(() => selectMonoAccount(cards, []), /ambiguous/);
 assert.equal(selectMonoAccount(cards,[wife]).id,'w');
});
test('webhook resolves exact owner, rejecting unknown and duplicate mappings', () => {
 assert.equal(exactMonoAccount([husband,wife],'w').user_id,'wife');
 assert.equal(exactMonoAccount([husband,wife],'unknown'),null);
 assert.equal(exactMonoAccount([wife,{...wife,id:3}],'w'),null);
 assert.equal(exactMonoAccount([husband,wife],undefined),null);
 assert.equal(allowedMonoOwner('stranger@example.test'),false);
});
test('registration idempotent within owner; suffix collision never overwrites husband', () => {
 const before=JSON.stringify(husband);
 assert.equal(registrationTarget([husband],'wife',card,'2674'),null);
 assert.equal(registrationTarget([husband,wife],'wife',card,'2674').id,2);
 assert.throws(() => registrationTarget([husband,wife],'husband',card,'2674'), /owner_conflict/);
 assert.equal(JSON.stringify(husband),before);
});
test('provider values preserve cents and clear old debt/limit, missing values never fabricate zero', () => {
 assert.equal(monoBalancePatch(card).debt,800);
 assert.equal(monoBalancePatch(card).balance,0);
 assert.equal(monoBalancePatch({...card,balance:230000}).balance,300);
 assert.equal(monoBalancePatch({...card,balance:2000,creditLimit:0}).debt,0);
 assert.equal(monoBalancePatch({...card,balance:-2000,creditLimit:0}).balance,-20);
 assert.equal(monoBalancePatch({...card,balance:-2000,creditLimit:0}).debt,0);
 assert.throws(() => monoBalancePatch({...card,balance:undefined}), /invalid/);
 const patch=monoBalancePatch({...card,mono_token:'secret',token:'secret'});
 assert.equal(JSON.stringify(patch).includes('secret'),false);
});
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
function endpoint(name, rows, current='wife') {
 const db=structuredClone(rows), calls=[];
 const users={husband:{id:'husband',email:'gotnewmess@gmail.com'},wife:{id:'wife',email:'kovtunenko.yulchik@gmail.com'}};
 const sb={auth:{getUser:async()=>({data:{user:users[current]}}),admin:{getUserById:async id=>({data:{user:users[id]}})}},from(table){
  const filters=[];let write,mode='read',single=false,limit=Infinity;
  const q={select(){return q},eq(k,v){filters.push(r=>r[k]===v);return q},neq(k,v){filters.push(r=>r[k]!==v);return q},not(k,op,v){filters.push(r=>r[k]!=v);return q},order(){return q},limit(v){limit=v;return q},maybeSingle(){single=true;return q},single(){single=true;return q},insert(v){mode='insert';write=v;return q},update(v){mode='update';write=v;return q},then(resolve,reject){try{
   db[table] ||= [];let result=db[table].filter(r=>filters.every(f=>f(r))).slice(0,limit);
   if(mode==='insert'){result=[{id:db[table].length+10,...write}];db[table].push(...result)}
   if(mode==='update')for(const r of result)Object.assign(r,write);
   return Promise.resolve({data:single?(result[0]||null):result,error:null}).then(resolve,reject);
  }catch(e){return Promise.reject(e).then(resolve,reject)}}};return q;
 }};
 let handler;
 let source=fs.readFileSync(path.join(__dirname,`../supabase/functions/${name}/index.ts`),'utf8');
 source=source.replace(/^import .*;\r?\n/gm,'');
 const helpers=require('../supabase/functions/_shared/mono-accounts.ts');
 const context={...helpers,createClient:()=>sb,Deno:{env:{get:k=>k==='MONO_WEBHOOK_SECRET'?'test-secret':'test'},serve:fn=>handler=fn},console,Response,Request,URL,setTimeout,fetch:async(url,options)=>{
  calls.push({url,options});
  if(url.endsWith('/client-info'))return Response.json({accounts:options.headers['X-Token']==='wife-token'?[card]:[{...card,id:'h',maskedPan:['4444******1234']}]});
  return Response.json({});
 },creditPaid:()=>[],matchCredit:()=>null};
 vm.runInNewContext(stripTypeScriptTypes(source),context,{filename:name});
 return {db,calls,run:async(body={})=>handler(new Request('https://example.test?secret=test-secret',{method:'POST',headers:{Authorization:'Bearer jwt','Content-Type':'application/json'},body:JSON.stringify(body)}))};
}
const profiles=[{id:'husband',mono_token:'husband-token'},{id:'wife',mono_token:'wife-token'}];
test('endpoint webhook routes exact wife account, deduplicates and ignores unknown account',async()=>{
 const body={type:'StatementItem',data:{account:'w',statementItem:{id:'event',amount:100,time:1793500000}}};
 const data={profiles,accounts:[husband,wife],transactions:[]};
 const fixed=endpoint('mono-webhook',data);assert.equal((await fixed.run(body)).status,200);
 assert.equal(fixed.db.transactions[0].user_id,'wife');assert.equal(fixed.db.transactions[0].account_id,2);
 await fixed.run(body);assert.equal(fixed.db.transactions.length,1);
 await fixed.run({...body,data:{...body.data,account:'unknown',statementItem:{...body.data.statementItem,id:'other'}}});assert.equal(fixed.db.transactions.length,1);
});
test('endpoint registration creates wife account, preserves husband and repeats idempotently without token leak',async()=>{
 const e=endpoint('mono-register',{profiles,accounts:[husband]});
 const first=await e.run({card_last4:'2674'});assert.equal(first.status,200);const json=await first.json();
 assert.equal(e.db.accounts.length,2);assert.deepEqual(e.db.accounts[0],husband);
 assert.equal(e.db.accounts[1].user_id,'wife');assert.equal(e.db.accounts[1].mono_account_id,'w');
 assert.equal(JSON.stringify(json).includes('token'),false);
 assert.equal((await e.run({card_last4:'2674'})).status,200);assert.equal(e.db.accounts.length,2);
});
test('endpoint balance refreshes both owners once, then uses cache even with force',async()=>{
 const e=endpoint('mono-balance',{profiles,accounts:[husband,wife]},'husband');
 const json=await(await e.run()).json();assert.equal(json.accounts.length,2);assert.equal(e.calls.length,2);
 assert.equal(json.accounts.find(a=>a.id===2).debt,800);
 assert.equal(JSON.stringify(json).includes('token'),false);
 await e.run({force:true});assert.equal(e.calls.length,2);
});
test('endpoint backfill rejects unlinked or another owners account before provider call',async()=>{
 const e=endpoint('mono-backfill',{profiles,accounts:[husband,wife]});
 assert.equal((await e.run({account:'h'})).status,400);assert.equal(e.calls.length,0);
 const missing=endpoint('mono-backfill',{profiles,accounts:[husband]});assert.equal((await missing.run()).status,400);assert.equal(missing.calls.length,0);
});

test('registration rejects a stale frontend profile before provider or account changes',async()=>{
 const h=endpoint('mono-register'),before=JSON.stringify(h.db),res=await h.run({profile_id:'husband',card_last4:'2674'});assert.equal(res.status,403);assert.equal((await res.json()).error,'profile_changed');assert.equal(h.calls.length,0);assert.equal(JSON.stringify(h.db),before);
});

test('registration rejects non-object request before provider access',async()=>{for(const body of [null,[],123]){const h=endpoint('mono-register'),res=await h.run(body);assert.equal(res.status,400);assert.equal(h.calls.length,0);}});

test('migrated Monobank account rebinds only to one unambiguous free card of the same limit kind', () => {
 const acc={id:6,bank:'mono',mono_account_id:'old',credit_limit:10000};
 const fresh={id:'new',currencyCode:980,type:'black',creditLimit:1000000,balance:268852};
 assert.equal(migratedMonoAccount([fresh,{...fresh,id:'h'}],acc,['h','old']).id,'new');
 assert.equal(migratedMonoAccount([{...fresh,id:'old'},fresh],acc,['old']),null);
 assert.equal(migratedMonoAccount([fresh,{...fresh,id:'x'}],acc,['old']),null);
 assert.equal(migratedMonoAccount([{...fresh,creditLimit:0}],acc,['old']),null);
 assert.equal(migratedMonoAccount([{...fresh,type:'fop'}],acc,['old']),null);
 assert.equal(migratedMonoAccount([{...fresh,currencyCode:840}],acc,['old']),null);
 assert.equal(migratedMonoAccount([fresh],{...acc,mono_account_id:null},[]),null);
});
test('statement rows keep webhook shape and sign', () => {
 assert.deepEqual(statementRows([{id:'s1',amount:-12345,description:'АТБ',mcc:5411,time:1762851600},{amount:1}],'u',6),
  [{user_id:'u',amount:123.45,type:'expense',description:'АТБ',source:'mono',source_id:'s1',mcc:5411,date:'2025-11-11',account_id:6}]);
});

test('технічна пара міграції рахунку Monobank не імпортується', () => {
 const out = 'Списання коштів в рамках міграції рахунку\n', inc = 'Зарахування коштів в рамках міграції рахунку ';
 assert.equal(isMonoMigrationEntry(out), true);
 assert.equal(isMonoMigrationEntry(inc), true);
 assert.equal(isMonoMigrationEntry('АТБ'), false);
 assert.equal(isMonoMigrationEntry(null), false);
 const rows = statementRows([{id:'m1',amount:-731148,description:out,time:1762851600},{id:'m2',amount:731148,description:inc,time:1762851600},{id:'a',amount:-100,description:'АТБ',time:1762851600}],'u',6);
 assert.deepEqual(rows.map(r => r.source_id), ['a']);
});
