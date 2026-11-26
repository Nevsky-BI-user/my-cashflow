// Оновлення Monobank без застосунку (функція mono-refresh, _shared/mono-refresh.ts) і задача pg_cron (міграція 56)
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const mod=()=>import(pathToFileURL(path.join(root,'supabase/functions/_shared/mono-refresh.ts')).href);
const SECRET='mono-refresh-test-secret-0123456789';
const users={husband:{id:'husband',email:'gotnewmess@gmail.com'},stranger:{id:'stranger',email:'x@example.test'}};
const allowed=e=>['gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com'].includes(String(e||'').toLowerCase());

function world({stamp='2026-11-26T08:00:00Z',status=200}={}){
 const db={profiles:[{id:'husband',mono_token:'husband-token'},{id:'stranger',mono_token:'stranger-token'}],
  accounts:[{id:7,user_id:'husband',bank:'mono',name:'Чорна',mono_account_id:'m7',balance:100,debt:0,credit_limit:0,balance_updated_at:stamp},
   {id:8,user_id:'stranger',bank:'mono',name:'Чужа',mono_account_id:'s8',balance:5,debt:0,credit_limit:0,balance_updated_at:stamp}]};
 const updates=[],calls=[];let touched=0;
 const sb={auth:{admin:{getUserById:async id=>({data:{user:users[id]}})}},from(table){touched++;
  const f=[];let patch=null,single=false;
  const q={select(){return q},eq(k,v){f.push(r=>r[k]===v);return q},not(k,o,v){f.push(r=>r[k]!=v);return q},order(){return q},single(){single=true;return q},
   update(p){patch=p;return q},then(res,rej){const rows=(db[table]||[]).filter(r=>f.every(x=>x(r)));
    if(patch){for(const r of rows)Object.assign(r,patch);updates.push({table,patch});}
    return Promise.resolve({data:single?rows[0]:rows,error:null}).then(res,rej);}};return q;}};
 const fetch=async(url,init)=>{calls.push({url,token:init?.headers?.['X-Token']});
  if(status!==200)return new Response('{}',{status});
  return Response.json({accounts:[{id:'m7',currencyCode:980,balance:123456,creditLimit:0}]});};
 return {db,updates,calls,sb,fetch,touched:()=>touched};
}
const req=(headers={},method='POST')=>new Request('https://x.test/functions/v1/mono-refresh',{method,headers,body:method==='POST'?'{}':undefined});

test('без секрету, з чужим секретом чи не POST: 403/405 і жодного звернення до бази чи Monobank',async()=>{
 const {handleMonoRefresh}=await mod();const w=world();
 const deps={sb:w.sb,fetch:w.fetch,supabaseUrl:'https://x.test',serviceRole:'sr',allowed};
 assert.equal((await handleMonoRefresh(req(),SECRET,deps)).status,403);
 assert.equal((await handleMonoRefresh(req({'x-mono-refresh-secret':SECRET+'x'}),SECRET,deps)).status,403);
 assert.equal((await handleMonoRefresh(req({'x-mono-refresh-secret':''}),'',deps)).status,403);
 assert.equal((await handleMonoRefresh(req({'x-mono-refresh-secret':SECRET},'GET'),SECRET,deps)).status,405);
 assert.equal(w.touched(),0);assert.equal(w.calls.length,0);
});

test('з секретом: оновлює лише власника з whitelist, відповідь без балансів, назв і токенів',async()=>{
 const {handleMonoRefresh}=await mod();const w=world();
 const res=await handleMonoRefresh(req({'x-mono-refresh-secret':SECRET}),SECRET,{sb:w.sb,fetch:w.fetch,supabaseUrl:'https://x.test',serviceRole:'sr',allowed,nowMs:()=>Date.parse('2026-11-26T09:00:00Z')});
 assert.equal(res.status,200);const body=await res.json();
 assert.deepEqual(body,{ok:true,cached:false,accounts:1,errors:[]});
 assert.deepEqual(w.calls.map(c=>c.token),['husband-token']);
 assert.equal(w.db.accounts[0].balance,1234.56);assert.equal(w.db.accounts[1].balance,5);
 const text=JSON.stringify(body);for(const bad of ['token','Чорна','1234','balance'])assert.ok(!text.includes(bad),bad);
});

test('ліміт Monobank: знімок свіжіший за 60 с не запитується, 429 нічого не пише',async()=>{
 const {refreshMonoAccounts,FRESH_MS}=await mod();assert.equal(FRESH_MS,60000);
 const fresh=world({stamp:'2026-11-26T08:59:30Z'});
 const r1=await refreshMonoAccounts({sb:fresh.sb,fetch:fresh.fetch,supabaseUrl:'',serviceRole:'',allowed,nowMs:()=>Date.parse('2026-11-26T09:00:00Z')});
 assert.equal(r1.cached,true);assert.equal(fresh.calls.length,0);assert.equal(fresh.updates.length,0);
 const limited=world({status:429});
 const r2=await refreshMonoAccounts({sb:limited.sb,fetch:limited.fetch,supabaseUrl:'',serviceRole:'',allowed,nowMs:()=>Date.parse('2026-11-26T09:00:00Z')});
 assert.deepEqual(r2.errors,[{account_id:7,reason:'rate_limited'}]);assert.equal(limited.updates.length,0);assert.equal(limited.db.accounts[0].balance,100);
});

test('міграція 56: копія для CLI точна, cron кожні 30 хв, секрет із Vault у заголовку, який перевіряє функція',()=>{
 const sql=fs.readFileSync(path.join(root,'56-mono-refresh-cron.sql'),'utf8');
 assert.equal(sql,fs.readFileSync(path.join(root,'supabase/migrations/20261126120000_mono_refresh_cron.sql'),'utf8'));
 assert.match(sql,/select cron\.unschedule\(jobid\) from cron\.job where jobname = 'mono-refresh';/);
 assert.match(sql,/cron\.schedule\(\s*'mono-refresh',\s*'\*\/30 \* \* \* \*'/);
 assert.match(sql,/'x-mono-refresh-secret', coalesce\(\(select decrypted_secret from vault\.decrypted_secrets where name = 'mono_refresh_secret'\), ''\)/);
 assert.ok(!/eyJ|service_role|sk-/.test(sql),'у міграції немає ключів');
 const src=fs.readFileSync(path.join(root,'supabase/functions/_shared/mono-refresh.ts'),'utf8');
 assert.match(src,/req\.headers\.get\('x-mono-refresh-secret'\)/);
 assert.ok(!/debt_month/.test(src),'оновлення Mono не перезаписує місяць боргу');
 assert.match(fs.readFileSync(path.join(root,'supabase/functions/mono-refresh/index.ts'),'utf8'),/Deno\.env\.get\('MONO_REFRESH_SECRET'\)/);
 const toml=fs.readFileSync(path.join(root,'supabase/config.toml'),'utf8');
 assert.match(toml,/\[functions\.mono-refresh\]\r?\nverify_jwt = false/);
 assert.match(toml,/\[functions\.mono-balance\]\r?\nverify_jwt = true/);
 assert.ok(!/pg_cron раз на день/.test(toml),'config.toml не обіцяє cron курсів, якого немає');
});
