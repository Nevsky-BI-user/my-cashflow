// Функція family-status (_shared/family-status.ts): підпис, лише GET без записів, числа ті самі, що в розділах бота
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const shared=p=>import(pathToFileURL(path.join(root,'supabase/functions/_shared',p)).href);
const fixture=()=>import(pathToFileURL(path.join(__dirname,'family-status-fixture.mjs')).href);
const SECRET='0123456789abcdef0123456789abcdef-test-secret';

test('контрольний вектор підпису збігається з Python (hmac.new(secret, f"{ts}\\nGET /family-status", sha256))',async()=>{
 const {voiceSign}=await shared('voice-auth.ts');const {TWIN_SIGNED}=await shared('family-status.ts');
 assert.equal(TWIN_SIGNED,'GET /family-status');
 assert.equal(await voiceSign(SECRET,1794600000,TWIN_SIGNED),'ac3409fcf3fa86d870ab41c6256e265d9b8837f4cd55f9ef6ad1347cdd1d7ea0');
});

test('без підпису, зі старою міткою, чужим підписом, коротким секретом чи не GET: відмова без звернення до бази',async()=>{
 const {handleFamilyStatus,TWIN_SIGNED}=await shared('family-status.ts');const {voiceSign}=await shared('voice-auth.ts');
 const touched=[];const sb={from(t){touched.push(t);throw new Error('db touched')}};
 const ts=Math.floor(Date.now()/1000),sig=await voiceSign(SECRET,ts,TWIN_SIGNED);
 const req=(headers,method='GET')=>new Request('https://x.test/functions/v1/family-status',{method,headers});
 assert.equal((await handleFamilyStatus(req({}),{sb,secret:SECRET})).status,401);
 assert.equal((await handleFamilyStatus(req({'X-Twin-Ts':String(ts-121),'X-Twin-Sig':await voiceSign(SECRET,ts-121,TWIN_SIGNED)}),{sb,secret:SECRET})).status,401);
 assert.equal((await handleFamilyStatus(req({'X-Twin-Ts':String(ts),'X-Twin-Sig':await voiceSign(SECRET,ts,'GET /other')}),{sb,secret:SECRET})).status,401);
 assert.equal((await handleFamilyStatus(req({'X-Twin-Ts':String(ts),'X-Twin-Sig':sig}),{sb,secret:''})).status,401);
 assert.equal((await handleFamilyStatus(req({'X-Twin-Ts':String(ts),'X-Twin-Sig':await voiceSign('short',ts,TWIN_SIGNED)}),{sb,secret:'short'})).status,401);
 assert.equal((await handleFamilyStatus(req({'X-Twin-Ts':String(ts),'X-Twin-Sig':sig},'POST'),{sb,secret:SECRET})).status,405);
 assert.deepEqual(touched,[]);
});

test('підписаний GET: ті самі числа, що «Баланс» і «Картки» бота, підсумки сходяться з рядками',async()=>{
 const {both}=await fixture();const r=await both();const s=r.status;
 assert.equal(r.httpStatus,200);
 // Бот: розділи з тих самих даних статусу; Власні, Кредитні, Баланс і «Разом» з тексту таблиць
 const plain=t=>t.replace(/<\/?pre>/g,'').replace(/[  ]/g,' ');
 const top=plain(r.sections.top.join('\n')),cards=plain(r.sections.cards.join('\n'));
 const val=(text,label)=>{const m=text.match(new RegExp('^'+label+'\\s+(-?[\\d ]+)$','m'));assert.ok(m,label+' немає в тексті бота');return Number(m[1].replace(/ /g,''));};
 assert.equal(s.own_total,val(top,'Власні'));assert.equal(s.credit_debt_total,val(top,'Кредитні'));assert.equal(s.balance,val(top,'Баланс'));
 assert.ok(s.budget,'бюджет періоду є');assert.equal(s.budget.left,val(top,'Лишилось до \\d\\d\\.\\d\\d'));assert.equal(s.budget.daily,val(top,'На день, \\d+ дн\\.'));
 const total=cards.match(/^Разом\s+(-?[\d ]+?)\s{2,}(-?[\d ]+?)\s{2,}(-?[\d ]+)$/m);assert.ok(total);
 assert.deepEqual([s.accounts_total.own,s.accounts_total.debt,s.accounts_total.available],total.slice(1).map(x=>Number(x.replace(/ /g,''))));
 // Калькулятор над показаними числами
 const sum=xs=>xs.reduce((n,x)=>n+x,0);
 assert.equal(s.accounts_total.own,sum(s.accounts.map(a=>a.own))+(s.unassigned_own||0));
 assert.equal(s.accounts_total.debt,sum(s.accounts.map(a=>a.debt)));
 assert.equal(s.accounts_total.available,sum(s.accounts.filter(a=>a.available!=null).map(a=>a.available)));
 assert.equal(s.payments_until_payday_total,sum(s.payments_until_payday.map(p=>p.amount)));
 assert.equal(s.balance,s.own_total-s.credit_debt_total);
 // «Вільні до виплати» рушія = власні мінус перелічені платежі (у копійках, до округлення показу)
 const p=r.statusData.projection,u=p.untilPayout;
 const cents=p.events.filter(e=>(e.kind==='mandatory'||e.kind==='fee')&&e.date>=s.today&&e.date<u.end).reduce((n,e)=>n+e.amountCents,0);
 assert.equal(u.cents,p.snapshot.positiveOwnCents-cents);assert.equal(s.next_payday,u.end);
 assert.equal(s.payments_until_payday.length,p.events.filter(e=>(e.kind==='mandatory'||e.kind==='fee')&&e.date>=s.today&&e.date<u.end).length);
 // Свіжість: мітка кожного рахунку і остання операція загалом
 assert.ok(s.accounts.every(a=>a.balance_updated_at&&['mono','manual'].includes(a.source)));
 assert.equal(s.freshness.latest_transaction_at,'2026-10-12T10:00:00Z');
 // Нічого зайвого: ні токенів, ні id, ні операцій
 const text=JSON.stringify(s);
 for(const bad of ['token','mono_token','user_id','mono_account_id','description','"id"','transactions'])assert.ok(!text.includes(bad),bad);
 assert.deepEqual(Object.keys(s.accounts[0]).sort(),['available','balance_updated_at','bank','debt','kind','name','own','owner','source']);
});

test('функція лише читає: жодних записів у базу, і config.toml вимикає JWT лише для неї з підписом',async()=>{
 const {both}=await fixture();const r=await both();
 assert.ok(r.sbCalls.length>0);
 for(const c of r.sbCalls)for(const [op] of c.ops)assert.ok(!['insert','update','upsert','delete','rpc'].includes(op),op);
 const src=fs.readFileSync(path.join(root,'supabase/functions/_shared/family-status.ts'),'utf8')+fs.readFileSync(path.join(root,'supabase/functions/family-status/index.ts'),'utf8');
 assert.ok(!/\.(insert|update|upsert|delete|rpc)\(/.test(src));
 assert.match(src,/Deno\.env\.get\('TWIN_SECRET'\)/);
 const toml=fs.readFileSync(path.join(root,'supabase/config.toml'),'utf8');
 assert.match(toml,/\[functions\.family-status\]\r?\nverify_jwt = false/);
});
