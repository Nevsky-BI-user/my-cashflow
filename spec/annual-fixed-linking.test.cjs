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
const pickerPure=stripTypeScriptTypes(fs.readFileSync('supabase/functions/_shared/payment-picker.ts','utf8')).replace(/^import .*;\r?\n/gm,'').replaceAll('export ','');
const {paymentDates,paymentPage}=new Function('fixedOccurrence','fixedOccurrenceKey',pickerPure+';return {paymentDates,paymentPage};')(fixedOccurrence,fixedOccurrenceKey);
const sampleCredit={id:9,name:'Device',start_year:2026,start_month:0,total_payments:80,payment_day:31};
test('picker pages reach every fixed payment and credit including beyond sixty',()=>{
 for(const count of [61,81,107]){
  const items=Array.from({length:count},(_,id)=>({id,name:'Payment '+id})),seen=[];
  for(let page=0;page<paymentPage(items,0).pages;page++)seen.push(...paymentPage(items,page).items);
  assert.deepEqual(seen,items);assert.ok(paymentPage(items,999).items.some(x=>x.id===count-1));
 }
 const dates=paymentDates('c',sampleCredit,'2026-10-01','2026-10-25',new Set());assert.equal(dates.length,80);assert.ok(dates.includes('2026-02-28'));assert.equal(dates[0],'2026-09-30');
 assert.deepEqual(paymentPage(dates,9).items,dates.slice(72,80));
});
test('picker excludes paid periods; archived future dates forbidden; weekly and annual schedules valid',()=>{
 const creditDates=paymentDates('c',sampleCredit,'2026-10-01','2026-10-25',new Set());
 assert.deepEqual(paymentDates('c',sampleCredit,'2026-10-01','2026-10-25',new Set(creditDates.map(d=>'9|'+d.slice(0,7)))),[]);
 assert.deepEqual(paymentDates('c',{...sampleCredit,total_payments:0},'2026-10-01','2026-10-25',new Set()),[]);
 const annual={...claude,period:'year',month_of_year:2,day_of_month:29};
 assert.deepEqual(paymentDates('f',annual,'2026-10-01','2026-10-25',new Set(['1|2026-02'])),['2027-02-28','2028-02-29','2025-02-28']);
 const weekly={...claude,period:'week',weekday:1,active:false,end_date:'2026-04-12'};
 const dates=paymentDates('a',weekly,'2026-10-01','2026-03-15',new Set(['1|W2026-03-09']));
 assert.ok(dates.length>0);assert.ok(dates.every(d=>d<='2026-03-15'&&new Date(d).getUTCDay()===1));assert.ok(!dates.includes('2026-03-09'));
 assert.deepEqual(paymentDates('f',weekly,'2026-10-01','2026-10-25',new Set()),[]);
});
function pickerHarness({owner='u',linked=false,kind='c',items=[sampleCredit],paid=[]}={}){
 const row={id:7,user_id:owner,type:'expense',fixed_id:linked?1:null,credit_id:null,date:'2026-10-20',amount:432,account_id:3},updates=[],messages=[],answers=[];
 const sb={from(){const q={filters:[],payload:null};for(const key of ['eq','is'])q[key]=(a,b)=>{q.filters.push([a,b]);return q};q.select=q.maybeSingle=()=>q;q.update=p=>{q.payload=p;return q};q.then=resolve=>{const ok=q.filters.every(([k,v])=>row[k]===v);if(q.payload&&ok){updates.push(q.payload);Object.assign(row,q.payload)}return Promise.resolve({data:ok?(q.payload?[row]:row):null,error:null}).then(resolve)};return q}};
 const code=stripTypeScriptTypes(src.slice(src.indexOf('async function paymentTransaction('),src.indexOf('async function offerFixedLink(')));
 const api=new Function('sb','paymentContext','paymentDates','paymentPage','todayKyiv','reply',code+';return {offerPaymentPage,confirmPaymentLink};')(sb,async()=>({items,paid:new Set(paid)}),paymentDates,paymentPage,()=> '2026-10-25',async(...args)=>messages.push(args));
 return {row,updates,messages,answers,list:(page=0,id)=>api.offerPaymentPage(1,'u',7,kind,page,id),confirm:(due='2026-10-31',id=9)=>api.confirmPaymentLink(1,'u',7,kind,id,due,async t=>answers.push(t))};
}
test('credit binding preserves actual transaction fields and rejects foreign, paid, linked, invalid callbacks',async()=>{
 const h=pickerHarness();await h.confirm();assert.deepEqual(h.updates,[{credit_id:9,fixed_id:null,payment_due_date:'2026-10-31'}]);assert.equal(h.row.date,'2026-10-20');assert.equal(h.row.amount,432);assert.equal(h.row.account_id,3);await h.confirm();assert.equal(h.updates.length,1);
 for(const options of [{owner:'other'},{linked:true},{paid:['9|2026-10']}]){const h=pickerHarness(options);await h.confirm();assert.equal(h.updates.length,0)}
 for(const due of ['2026-02-31','2035-10-31','2026-10-30']){const h=pickerHarness();await h.confirm(due);assert.equal(h.updates.length,0)}
 const invalid=pickerHarness();await invalid.confirm('2026-10-31',123);assert.equal(invalid.updates.length,0);
 const archive=pickerHarness({kind:'a',items:[{...claude,id:9,active:false}]});await archive.confirm('2026-11-19');assert.equal(archive.updates.length,0);await archive.confirm('2026-10-19');assert.equal(archive.updates.length,1);
});
test('real picker keyboard reaches last item and date and every callback fits Telegram',async()=>{
 for(const kind of ['f','c','a']){
 const items=Array.from({length:73},(_,i)=>({...sampleCredit,id:i+1,name:'Item '+i})),h=pickerHarness({kind,items});await h.list(9);
 const keyboard=h.messages.at(-1)[2].inline_keyboard.flat();assert.ok(keyboard.some(b=>b.callback_data==='po:7:'+kind+':73:0'));
 for(const b of keyboard)assert.ok(Buffer.byteLength(b.callback_data)<=64);
 }
 const h=pickerHarness();await h.list(9,9);const keyboard=h.messages.at(-1)[2].inline_keyboard.flat();assert.ok(keyboard.some(b=>b.callback_data==='pc:7:c:9:2032-08-31'));for(const b of keyboard)assert.ok(Buffer.byteLength(b.callback_data)<=64);
 const noAccess=pickerHarness({owner:'other'});await noAccess.list();assert.equal(noAccess.messages[0][2],undefined);
});
test('nearest actual transaction period is first and all periods remain reachable',()=>{
 const reference='2026-10-20',today='2026-10-25';
 const monthly=paymentDates('f',claude,reference,today,new Set());assert.equal(monthly[0],'2026-10-19');
 const credits=paymentDates('c',sampleCredit,reference,today,new Set());assert.equal(credits[0],'2026-10-31');
 const seen=[];for(let page=0;page<paymentPage(credits,0).pages;page++)seen.push(...paymentPage(credits,page).items);
 assert.equal(new Set(seen).size,80);assert.ok(seen.includes('2026-01-31'));assert.ok(seen.includes('2032-08-31'));
 const tie=paymentDates('c',{...sampleCredit,payment_day:1},'2026-10-16T12:00:00Z',today,new Set());assert.deepEqual(tie.slice(0,2),['2026-10-01','2026-11-01']);
 const exactTie=paymentDates('c',{...sampleCredit,payment_day:1},'2026-09-16',today,new Set());assert.deepEqual(exactTie.slice(0,2),['2026-09-01','2026-10-01']);
});
test('January expense can link the previous December and ended archived obligations',()=>{
 const fixed={...claude,day_of_month:31};
 const dates=paymentDates('f',fixed,'2027-01-02','2027-01-03',new Set());
 assert.equal(dates[0],'2026-12-31');assert.ok(dates.includes('2026-01-31'));assert.ok(dates.includes('2029-12-31'));assert.ok(!dates.some(d=>d>='2030-01-01'||d<'2026-01-01'));
 const archived=paymentDates('a',{...fixed,active:false,end_date:'2026-12-31'},'2027-01-02','2027-01-03',new Set());
 assert.equal(archived[0],'2026-12-31');assert.ok(archived.every(d=>d<='2026-12-31'));
});
