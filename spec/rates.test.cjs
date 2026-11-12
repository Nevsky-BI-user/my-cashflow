// Курси НБУ / ПриватБанку і оцінка накопичень у валюті: розбір відповідей API (_shared/rates.ts)
// та вбудований у index.html блок CANONICAL SAVINGS RATES (рядки таблиці, собівартість, структура, смуга цілі).
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const load=()=>import('../supabase/functions/_shared/rates.ts');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const block=html.split('/* CANONICAL SAVINGS RATES */')[1].split('/* END CANONICAL SAVINGS RATES */')[0];
const R=new Function(block+';return{ratePos,ratesFromRows,ratesStale,savEntryCost,savingsMix,savingsCost,goalMixParts,RATE_STALE_MS}')();
const AT='2026-11-12T08:00:00.000Z';
const close=(a,b,msg)=>assert.ok(Math.abs(a-b)<1e-9,msg+': '+a+' != '+b);

test('NBU: USD/EUR rate becomes buy = sale, other currencies and bad values are skipped',async()=>{
 const {parseNbu}=await load();
 const rows=parseNbu([{cc:'AUD',rate:29.5},{r030:840,cc:'USD',rate:45.3222},{cc:'EUR',rate:50.4823}],AT);
 assert.deepEqual(rows,[{ccy:'USD',source:'nbu',buy:45.3222,sale:45.3222,updated_at:AT},{ccy:'EUR',source:'nbu',buy:50.4823,sale:50.4823,updated_at:AT}]);
 assert.deepEqual(parseNbu([{cc:'USD',rate:0},{cc:'EUR',rate:'abc'}],AT),[]);
 assert.deepEqual(parseNbu({error:'x'},AT),[]);
 assert.deepEqual(parseNbu([{cc:'USD',rate:-1},{cc:'EUR',rate:50.1}],AT).map(r=>r.ccy),['EUR']);
});

test('PrivatBank: string decimals parsed, only UAH base, inverted or empty pairs dropped',async()=>{
 const {parsePrivat}=await load();
 const rows=parsePrivat([{ccy:'EUR',base_ccy:'UAH',buy:'50.45000',sale:'51.45000'},{ccy:'USD',base_ccy:'UAH',buy:'45.35000',sale:'45.95000'}],AT);
 assert.deepEqual(rows,[{ccy:'USD',source:'privat',buy:45.35,sale:45.95,updated_at:AT},{ccy:'EUR',source:'privat',buy:50.45,sale:51.45,updated_at:AT}]);
 assert.deepEqual(parsePrivat([{ccy:'USD',base_ccy:'UAH',buy:'46',sale:'45'}],AT),[],'sale below buy');
 assert.deepEqual(parsePrivat([{ccy:'USD',base_ccy:'EUR',buy:'1',sale:'1.1'}],AT),[],'not UAH base');
 assert.deepEqual(parsePrivat([{ccy:'USD',base_ccy:'UAH',buy:'',sale:'45'}],AT),[]);
 assert.deepEqual(parsePrivat(null,AT),[]);
});

test('inline ratePos accepts Ukrainian comma input and rejects zero, negatives and junk',()=>{
 assert.equal(R.ratePos('42,10'),42.1);assert.equal(R.ratePos(' 45.95 '),45.95);assert.equal(R.ratePos(41),41);
 for(const v of [0,'0',-3,'','abc',null,undefined,true,NaN,Infinity])assert.equal(R.ratePos(v),null,String(v));
});

test('rows split by source; rows without source are PrivatBank; staleness by the oldest row and completeness',()=>{
 const legacy=R.ratesFromRows([{ccy:'USD',buy:'43.85',sale:'44.25',updated_at:'2026-04-17T10:00:00Z'},{ccy:'EUR',buy:'51.70',sale:'52.63',updated_at:'2026-04-17T10:00:00Z'}]);
 assert.deepEqual(legacy.privat,{USD:{buy:43.85,sale:44.25},EUR:{buy:51.7,sale:52.63}});assert.deepEqual(legacy.nbu,{});
 assert.equal(legacy.complete,false);assert.equal(R.ratesStale(legacy,Date.parse(AT)),true);
 const t0=Date.parse(AT),iso=ms=>new Date(ms).toISOString();
 const rows=[['USD','privat',45.35,45.95,0],['EUR','privat',50.45,51.45,0],['USD','nbu',45.3222,45.3222,-3600e3],['EUR','nbu',50.4823,50.4823,0]].map(([ccy,source,buy,sale,d])=>({ccy,source,buy,sale,updated_at:iso(t0+d)}));
 const p=R.ratesFromRows(rows);
 assert.deepEqual(p.nbu.USD,{buy:45.3222,sale:45.3222});assert.deepEqual(p.privat.USD,{buy:45.35,sale:45.95},'NBU row must not overwrite PrivatBank');
 assert.equal(p.complete,true);assert.equal(p.oldest,t0-3600e3);
 assert.equal(R.ratesStale(p,t0),false);assert.equal(R.ratesStale(p,t0-3600e3+R.RATE_STALE_MS+1),true);assert.equal(R.ratesStale(p,t0-3600e3+R.RATE_STALE_MS),false);
 assert.equal(R.ratesStale(null,t0),true);
 assert.deepEqual(R.ratesFromRows([{ccy:'GBP',source:'nbu',buy:1,sale:1},{ccy:'USD',source:'x',buy:1,sale:1},{ccy:'USD',source:'nbu',buy:0,sale:0}]).nbu,{});
});

const VAL=c=>c==='USD'?45.35:c==='EUR'?50.45:1;
const LOG=[{amount:42000,currency:'UAH'},{amount:300,currency:'USD',rate:41.75},{amount:200,currency:'USD',rate:'45,95'},{amount:100,currency:'EUR'},{amount:1000,currency:null}];

test('entry cost: UAH as is, foreign only by its stored rate, never by another rate',()=>{
 assert.equal(R.savEntryCost(LOG[0]),42000);close(R.savEntryCost(LOG[1]),300*41.75,'USD');close(R.savEntryCost(LOG[2]),200*45.95,'comma');
 assert.equal(R.savEntryCost(LOG[3]),null);assert.equal(R.savEntryCost(LOG[4]),1000,'null currency is UAH');
});

test('invested vs current valuation over the same entries, missing-rate count reported',()=>{
 const c=R.savingsCost(LOG,VAL);
 assert.equal(c.foreign,3);assert.equal(c.missing,1);assert.equal(c.known,4);
 close(c.invested,42000+300*41.75+200*45.95+1000,'invested');
 close(c.now,42000+500*45.35+1000,'now same set');
 const only=R.savingsCost([{amount:300,currency:'USD'}],VAL);
 assert.deepEqual(only,{foreign:1,missing:1,known:0,invested:0,now:0});
 assert.equal(R.savingsCost([{amount:5000,currency:'UAH'}],VAL).foreign,0);
});

test('currency mix: amounts per currency, UAH valuation, shares sum to 1, empty currencies dropped',()=>{
 const m=R.savingsMix(LOG,VAL);
 assert.deepEqual(m.parts.map(p=>p.ccy),['UAH','USD','EUR']);
 assert.deepEqual(m.parts.map(p=>p.amt),[43000,500,100]);
 close(m.total,43000+500*45.35+100*50.45,'total');
 close(m.parts.reduce((s,p)=>s+p.share,0),1,'shares');
 close(m.parts[1].share,500*45.35/m.total,'USD share');
 assert.deepEqual(R.savingsMix([],VAL),{parts:[],total:0});
 assert.deepEqual(R.savingsMix([{amount:300,currency:'USD'}],VAL).parts.map(p=>[p.ccy,p.share]),[['USD',1]]);
});

test('goal bar split: same shares as the pool, segment UAH sums to goal fill, currency amount converts back',()=>{
 const m=R.savingsMix(LOG,VAL),acc=30000,g=R.goalMixParts(acc,m,VAL);
 assert.deepEqual(g.map(p=>p.ccy),['UAH','USD','EUR']);
 close(g.reduce((s,p)=>s+p.uah,0),acc,'segments sum to fill');
 g.forEach((p,i)=>{close(p.share,m.parts[i].share,'share '+p.ccy);close(p.amt*VAL(p.ccy),p.uah,'amount '+p.ccy)});
 const full=R.goalMixParts(m.total,m,VAL);full.forEach((p,i)=>close(p.amt,m.parts[i].amt,'whole pool returns real amount '+p.ccy));
 assert.deepEqual(R.goalMixParts(0,m,VAL),[]);
 assert.deepEqual(R.goalMixParts(1000,R.savingsMix([{amount:1,currency:'USD'}],VAL),VAL),[],'single currency keeps the plain bar');
});

test('migration keeps secrets out of git and makes rates read-only for clients',()=>{
 const sql=fs.readFileSync(path.join(root,'supabase/migrations/20261112130000_exchange_rates_sources.sql'),'utf8');
 assert.equal(sql,fs.readFileSync(path.join(root,'52-exchange-rates-sources.sql'),'utf8'),'root copy identical');
 assert.doesNotMatch(sql,/vault\.|cron\.schedule/,'no cron job and no service key in Vault');
 assert.doesNotMatch(sql,/eyJ[A-Za-z0-9_-]{10,}/,'no JWT in migration');
 assert.match(sql,/create policy "family read" on public\.exchange_rates for select using \(public\.is_family_member\(\)\)/);
 assert.match(sql,/drop policy if exists "family full" on public\.exchange_rates/);
 assert.match(sql,/unique \(ccy, source\)/);
 assert.match(sql,/rate_source in \('privat', 'nbu', 'manual'\)/);
 assert.doesNotMatch(sql,/update public\.savings_log/,'old entries are never back-filled with a rate');
 const toml=fs.readFileSync(path.join(root,'supabase/config.toml'),'utf8');assert.match(toml,/\[functions\.rates-refresh\]\r?\nverify_jwt = true/);
});
