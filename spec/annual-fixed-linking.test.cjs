const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {stripTypeScriptTypes}=require('node:module');
const src=fs.readFileSync('supabase/functions/telegram-webhook/index.ts','utf8');
const pure=stripTypeScriptTypes(fs.readFileSync('supabase/functions/_shared/fixedmatch.ts','utf8')).replaceAll('export ','');
const {fixedCandidates,fixedOccurrence,fixedOccurrenceKey,fixedNameMatches}=new Function(pure+';return {fixedCandidates,fixedOccurrence,fixedOccurrenceKey,fixedNameMatches};')();
const claude={id:1,name:'Підписка Claude',period:'month',day_of_month:19,active:true,type:'payment'};
const helper=stripTypeScriptTypes(src.slice(src.indexOf('async function matchFixed('),src.indexOf('const addDays =',src.indexOf('async function matchFixed('))));
function matcher(fixed=[claude],paid=new Set()){
 return new Function('fixedContext','fixedCandidates','fixedOccurrenceKey',helper+';return {matchFixed,linkReceiptRows};')(async()=>({fixed,paid:new Set(paid)}),fixedCandidates,fixedOccurrenceKey);
}
test('Claude Ukrainian and merchant aliases match whole words; generic or Internet-store never match',async()=>{
 for(const desc of ['Оплата Клод','ANTHROPIC subscription','Claude Pro'])assert.equal((await matcher().matchFixed(desc,'2026-10-21')).id,1);
 for(const desc of ['Claudeberry','підписка','магазин'])assert.equal(await matcher().matchFixed(desc,'2026-10-21'),null);
 assert.equal(fixedNameMatches('Інтернет','Інтернет-магазин'),false);
 assert.equal(fixedNameMatches('Internet','Internet-store'),false);
 assert.equal(fixedNameMatches('Підписка','Підписка'),false);
});
test('text and receipt use same matcher; batch reserves occurrence; ambiguity remains explicit',async()=>{
 const m=matcher(),rows=[{description:'Клод',date:'2026-10-21',type:'expense'},{description:'Anthropic',date:'2026-10-21',type:'expense'},{description:'Claude',date:'2026-10-21',type:'income'}];
 await m.linkReceiptRows(rows);assert.equal(rows[0].fixed_id,1);assert.equal(rows[0].payment_due_date,'2026-10-19');assert.equal(rows[1].fixed_id,undefined);assert.equal(rows[2].fixed_id,undefined);
 assert.equal(await m.matchFixed('Claude за січень','2026-12-21'),null);
 for(const description of ['Claude за 2026-11-01','Claude за 01.11.2026','Claude на 1/11/2026','Claude за 01.11'])assert.equal(await m.matchFixed(description,'2026-10-21'),null,description);
 assert.equal(await matcher([claude,{...claude,id:2}],new Set(['1|2026-10'])).matchFixed('Claude','2026-10-21'),null);
 const two=matcher([claude,{...claude,id:2}]);assert.equal(await two.matchFixed('Клод','2026-10-21'),null);const ambiguous=[{...rows[1]}];await two.linkReceiptRows(ambiguous);assert.equal(ambiguous[0].fixed_id,undefined);
 assert.equal(await matcher([claude],new Set(['1|2026-10'])).matchFixed('Claude','2026-10-21'),null);
});
test('annual valid month, leap clamp, end dates and week/year rollover',()=>{
 const f={...claude,period:'year',month_of_year:2,day_of_month:29};
 assert.equal(fixedOccurrence(f,'2027-02-01'),'2027-02-28');assert.equal(fixedOccurrence(f,'2028-02-01'),'2028-02-29');
 assert.equal(fixedOccurrence(f,'2027-01-01'),null);assert.equal(fixedOccurrence({...f,end_date:'2027-02-27'},'2027-02-01'),null);
 assert.equal(fixedOccurrence({...claude,active:false},'2027-01-01'),null);assert.equal(fixedOccurrence(claude,'2027-02-30'),null);
 const w={...claude,period:'week',weekday:1};assert.equal(fixedOccurrence(w,'2027-01-01'),'2026-12-28');assert.equal(fixedOccurrenceKey(w,'2027-01-01'),'1|W2026-12-28');
});
function linkHarness({owner='u',fixed=[claude],paid=[],linked=false}={}){
 const row={id:7,user_id:owner,type:'expense',fixed_id:linked?1:null,credit_id:null,date:'2026-12-20',amount:10800,account_id:3};const updates=[],answers=[];
 const sb={from(){const q={filters:[],payload:null};for(const key of ['eq','is'])q[key]=(a,b)=>{q.filters.push([a,b]);return q};q.select=q.maybeSingle=()=>q;q.update=p=>{q.payload=p;return q};q.then=resolve=>{const ok=q.filters.every(([k,v])=>row[k]===v);if(q.payload&&ok){updates.push(q.payload);Object.assign(row,q.payload)}return Promise.resolve({data:ok?(q.payload?[row]:row):null,error:null}).then(resolve)};return q}};
 const fn=stripTypeScriptTypes(src.slice(src.indexOf('async function confirmFixedLink('),src.indexOf('async function onCallback(')));
 const run=new Function('sb','fixedContext','fixedOccurrence','fixedOccurrenceKey','reply',fn+';return confirmFixedLink;')(sb,async()=>({fixed,paid:new Set(paid)}),fixedOccurrence,fixedOccurrenceKey,async()=>{});
 return {row,updates,answers,run:(due='2027-01-19')=>run(1,'u',7,1,due,async t=>answers.push(t))};
}
test('explicit link closes future obligation without changing actual date/amount/account; retry safe',async()=>{
 const h=linkHarness();await h.run();assert.deepEqual(h.updates,[{fixed_id:1,payment_due_date:'2027-01-19'}]);assert.equal(h.row.date,'2026-12-20');assert.equal(h.row.amount,10800);assert.equal(h.row.account_id,3);await h.run();assert.equal(h.updates.length,1);
});
test('explicit callback rejects other owner, invalid day, paid occurrence and inactive item',async()=>{
 for(const options of [{owner:'other'},{paid:['1|2027-01']},{fixed:[{...claude,active:false}]},{linked:true}]){const h=linkHarness(options);await h.run();assert.equal(h.updates.length,0)}
 const h=linkHarness();await h.run('2027-01-20');assert.equal(h.updates.length,0);
 assert.match(src,/if \(!prof\) return answer\('Доступ закритий'\)/);
});
test('all receipt save paths invoke common linking before insert; source-id unique retry preserved',()=>{
 assert.equal((src.match(/await linkReceiptRows\(/g)||[]).length,3);
 assert.match(src,/if \(error.code === '23505'\) return true/);
 assert.match(src,/callback_data:`flpick:\$\{txId\}`/);
 assert.match(src,/linkCommand=text.match/);
});
