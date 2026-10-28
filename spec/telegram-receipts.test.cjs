const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(path.join(__dirname,'../supabase/functions/telegram-webhook/index.ts'),'utf8');
const receiptSystem=new Function(source.slice(source.indexOf('const RECEIPT_SYSTEM ='),source.indexOf('const SUPABASE_URL ='))+';return RECEIPT_SYSTEM;')();
const fixedPure=stripTypeScriptTypes(fs.readFileSync(path.join(__dirname,'../supabase/functions/_shared/fixedmatch.ts'),'utf8')).replaceAll('export ','');
const fixedApi=new Function(fixedPure+';return {fixedCandidates,fixedOccurrenceKey};')();
const receiptLinkCode=stripTypeScriptTypes(source.slice(source.indexOf('async function linkReceiptRows('),source.indexOf('const addDays =',source.indexOf('async function linkReceiptRows('))));
const isolated=stripTypeScriptTypes(source.slice(source.indexOf('const tgSourceId ='),source.indexOf('type Pending =')));
const confirmSource=stripTypeScriptTypes(source.slice(source.indexOf('async function confirmPending('),source.indexOf('// Посилання на застосунок у відповідь на /app')));
const transaction=(overrides={})=>({amount:120.5,type:'expense',currency:'UAH',description:'Магазин',date:'2026-10-19',...overrides});
const batch=(transactions=[transaction(),transaction({amount:200,type:'income',description:'Повернення',date:'2026-10-20'})])=>
  ({kind:'transactions',complete:true,readable:'good',transactions});
const single={has_total:true,amount:250,items_sum:250,description:'Чек',date:'2026-10-19',readable:'good'};
test('Oschad purchase detail date with time imports automatically',async()=>{
  const h=harness([batch([transaction({amount:321.45,description:'Тестова покупка',date_text:'28 жовтня 2026 09:39',time:'09:39',bank:'oschad'})])],
    {today:'2026-10-28',accounts:[{id:13,name:'Ощадбанк',bank:'oschad'}]});
  await h.run();
  assert.equal(h.state.rows[0]?.date,'2026-10-28');
  assert.equal(h.state.rows[0]?.amount,321.45);
  assert.equal(h.state.rows[0]?.account_id,13);
  assert.equal(h.state.pending,null);
});
test('date-time suffixes preserve the calendar date and invalid clocks remain unresolved',async()=>{
  for(const date_text of ['28 жовтня 2026 09:39','28 жовтня 2026, 09:39','28.10.2026 о 09:39:15','2026-10-28T09:39','Ср, 28 жовтня 2026 9:39']){
    const h=harness([{...single,date_text}],{today:'2026-10-28'});await h.run();
    assert.equal(h.state.rows[0]?.date,'2026-10-28',date_text);assert.equal(h.state.requests.length,1);
  }
  for(const date_text of ['28 жовтня 2026 25:39','28 жовтня 2026 09:60','31 жовтня 2026 09:39','31 лютого 2026 09:39','28 жовтня 2026 невідомо']){
    const h=harness([{...single,date_text}],{today:'2026-10-28'});await h.run();
    assert.equal(h.state.rows.length,0,date_text);assert.equal(h.state.pending?.kind,'receipt_date');
  }
});
test('purchase detail prompt recognises coherent Oschad cues and always treats bank purchases as transactions',()=>{
  for(const cue of ['ОДНУ банківську покупку','document_type:"bank"','«Деталі операції»','«Отримати квитанцію»','«Успішно»','дата й час під сумою','Один колір'])assert.ok(receiptSystem.includes(cue),cue);
});
test('unknown bank on a bank detail is reread automatically, while ordinary receipt stays cheap',async()=>{
  const h=harness([{...single,document_type:'bank',bank:null},{...single,document_type:'bank',bank:'oschad'}],{accounts:[{id:13,name:'Ощадбанк',bank:'oschad'}]});
  await h.run();assert.equal(h.state.requests.length,2);assert.equal(h.state.rows[0]?.account_id,13);assert.equal(h.state.pending,null);
});
test('failed date reread defers, then resumes only missing dates and retains sources, account, direction and time',async()=>{
  const result=batch([transaction({date_text:'17 жовтня 2026',amount:1}),transaction({date_text:'нерозбірливо',amount:2,type:'income',time:'09:39'}),transaction({date_text:'невідомо',amount:3})]);
  const h=harness([result],{accounts:[{id:13,name:'Ощадбанк',bank:'oschad'}]});
  await h.run(123,'ощад');assert.equal(h.state.requests.length,2);assert.equal(h.state.inserts.length,0);assert.equal(h.state.pending.kind,'receipt_date');
  await h.api.answerReceiptDate(1,'u','18.10.2026',h.state.pending);
  assert.equal(h.state.inserts.length,0);assert.equal(h.state.pending.kind,'receipt_date');
  await h.api.answerReceiptDate(1,'u','2026-10-19',h.state.pending);
  assert.deepEqual(h.state.rows.map(r=>[r.date,r.amount,r.type,r.account_id,r.source_id]),[
    ['2026-10-17',1,'expense',13,'tg:123'],['2026-10-18',2,'income',13,'tg:123:1'],['2026-10-19',3,'expense',13,'tg:123:2']]);
  assert.match(h.state.rows[1].description,/09:39/);assert.equal(h.state.requests.length,2);assert.equal(h.state.pending,null);
});
test('clarification retains multipart photos and original chosen account',async()=>{
  const old={kind:'receipt',parts:[{path:'u/first.jpg',update_id:40}],expires:new Date(Date.now()+600000).toISOString(),date:'2026-10-18',account_id:13,account_name:'Ощадбанк',account_resolved:true};
  const h=harness([{...single,date_text:'нерозбірливо',bank:'privat'}],{pending:old,accounts:[{id:13,name:'Ощадбанк',bank:'oschad'}]});
  await h.run(41);assert.equal(h.state.pending.kind,'receipt_date');
  await h.api.answerReceiptDate(1,'u','19.10.2026',h.state.pending);
  assert.equal(h.state.rows[0]?.source_id,'tg:41');assert.equal(h.state.rows[0]?.receipt_url,'u/first.jpg');
  assert.equal(h.state.rows[0]?.receipt_parts.length,2);assert.equal(h.state.rows[0]?.account_id,13);assert.equal(h.state.pending,null);
});
test('clarification rechecks duplicates and does not accept stale or expired pending state',async()=>{
  const h=harness([{...single,date_text:'нерозбірливо'}]);await h.run();
  const pending=h.state.pending;
  h.state.rows.push({id:1,amount:250,type:'expense',date:'2026-10-19',description:'Чек',account_id:null});
  await h.api.answerReceiptDate(1,'u','19.10.2026',pending);assert.equal(h.state.inserts.length,0);assert.match(h.state.replies.at(-1)[1],/дубл|схож/i);
  const stale=harness([{...single,date_text:'нерозбірливо'}]);await stale.run();const stalePending=stale.state.pending;
  stale.state.pending={kind:'entry',input:'text',type:'income',expires:'2099-01-01'};
  await stale.api.answerReceiptDate(1,'u','19.10.2026',stalePending);assert.equal(stale.state.inserts.length,0);assert.equal(stale.state.pending.kind,'entry');
  const expired=harness([{...single,date_text:'нерозбірливо'}]);await expired.run();expired.state.pending.expires='2000-01-01';
  await expired.api.answerReceiptDate(1,'u','19.10.2026',expired.state.pending);assert.equal(expired.state.inserts.length,0);assert.equal(expired.state.pending,null);
});
test('date clarification failure cannot overwrite existing pending or import any rows',async()=>{
  const h=harness([{...single,date_text:'нерозбірливо'}],{pendingSaveError:true});await h.run();
  assert.equal(h.state.inserts.length,0);assert.equal(h.state.pending,null);assert.match(h.state.replies.at(-1)[1],/Не вдалося зберегти уточнення/);
});
test('date fallback cannot downgrade a bank batch to one retail receipt',async()=>{
  const h=harness([batch(),{...single,date_text:'нерозбірливо'}]);await h.run();
  assert.equal(h.state.rows.length,0);assert.equal(h.state.pending,null);
});
test('clarification survives duplicate lookup failure and retries with the saved date',async()=>{
  const options={lookupError:false};
  const h=harness([batch([transaction({date_text:'нерозбірливо'})])],options);await h.run();
  options.lookupError=true;await h.api.answerReceiptDate(1,'u','18.10.2026',h.state.pending);
  assert.equal(h.state.inserts.length,0);assert.equal(h.state.pending.kind,'receipt_date');
  options.lookupError=false;await h.api.answerReceiptDate(1,'u','/yes',h.state.pending);
  assert.equal(h.state.rows[0]?.date,'2026-10-18');assert.equal(h.state.pending,null);assert.equal(h.state.requests.length,2);
});

const refundAccount={id:13,name:'Ощадбанк',bank:'oschad',active:true};
const returnCategory={id:104,name:'Повернення',is_income:true,user_id:'u'};
const refundPurchase=(overrides={})=>({id:900,amount:321.45,type:'expense',description:'Тестова покупка',date:'2026-10-18',account_id:13,...overrides});
const refundIncome=(overrides={})=>transaction({amount:321.45,type:'income',description:'Тестова покупка — повернення',date:'2026-10-19',bank:'oschad',...overrides});
test('refund matches exact cents, same account and merchant on or after purchase without altering expense',async()=>{
  for(const date of ['2026-10-18','2026-10-19','2026-10-20']){
    const expense=refundPurchase();const h=harness([batch([refundIncome({date})])],{existing:[expense],accounts:[refundAccount],refundCategories:[returnCategory]});
    await h.run();const row=h.state.rows.at(-1);
    assert.equal(row.category_id,104,date);assert.equal(row.auto_categorized,true);assert.equal(row.type,'income');assert.equal(row.amount,321.45);
    assert.equal(row.description,'Повернення: Тестова покупка — повернення');assert.deepEqual(h.state.rows[0],expense);
    assert.equal(h.state.pending,null);assert.equal(h.state.warnings.length,0);
    assert.deepEqual(h.state.lookups[0].ins,[['account_id',[13]],['amount',[321.45]]]);assert.deepEqual(h.state.lookups[0].max,['date',date]);
  }
});
test('refund requires matching merchant, known same account, exact amount and an earlier or equal expense date',async()=>{
  for(const change of [{date:'2026-10-20'},{amount:321.46},{account_id:14},{description:'Інший магазин'},{transfer_id:'transfer'},{type:'income',date:'2025-01-01'}]){
    const h=harness([batch([refundIncome()])],{existing:[refundPurchase(change)],accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
    const row=h.state.rows.at(-1);assert.equal(row.type,'income');assert.equal(row.category_id,undefined,JSON.stringify(change));assert.equal(row.description,'Тестова покупка — повернення');
  }
  for(const change of [{bank:null},{description:'Зарплата'},{description:'Тестова покупка інший відділ'},{description:'Повернення'}]){
    const h=harness([batch([refundIncome(change)])],{existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
    assert.equal(h.state.rows.at(-1).category_id,undefined,JSON.stringify(change));assert.equal(h.state.pending,null);
  }
});
test('refund merchant removes only explicit edge markers and keeps payment time',async()=>{
  for(const description of ['Повернення: Тестова покупка','ТЕСТОВА ПОКУПКА (refund)','Тестова покупка — повернення коштів','Refund: Тестова покупка']){
    const h=harness([batch([refundIncome({description,time:'09:39'})])],{existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
    assert.equal(h.state.rows.at(-1).category_id,104,description);assert.match(h.state.rows.at(-1).description,/ · 09:39$/);
    assert.ok(!h.state.rows.at(-1).description.startsWith('Повернення: Повернення: '));
  }
});
test('refund matches historical purchase beyond first page without a fixed lookback window',async()=>{
  const existing=Array.from({length:1000},(_,i)=>refundPurchase({id:i+1,description:'Інший магазин '+i,date:'2025-01-01'}));
  existing.push(refundPurchase({id:1001,date:'2025-01-01'}));
  const h=harness([batch([refundIncome()])],{existing,accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
  assert.equal(h.state.rows.at(-1).category_id,104);assert.equal(h.state.lookups.length,2);
  assert.deepEqual(h.state.lookups.map(q=>q.page),[[0,999],[1000,1999]]);
});
test('refund can match earlier purchase in same atomic batch but does not use later rows',async()=>{
  const purchase=transaction({amount:321.45,description:'Тестова покупка',bank:'oschad',date:'2026-10-18'});
  for(const [rows,expected] of [[[purchase,refundIncome()],104],[[refundIncome(),purchase],undefined]]){
    const h=harness([batch(rows)],{accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
    assert.equal(h.state.rows.find(r=>r.type==='income').category_id,expected);assert.equal(h.state.inserts.length,1);
    assert.equal(h.state.rows.find(r=>r.type==='expense').amount,321.45);
  }
});
test('several eligible purchases still classify refund and own category wins over another family category',async()=>{
  const categories=[{...returnCategory,id:105,user_id:'other'},returnCategory];
  const h=harness([batch([refundIncome()])],{existing:[refundPurchase(),refundPurchase({id:901,date:'2026-10-17'})],accounts:[refundAccount],refundCategories:categories});
  await h.run();assert.equal(h.state.rows.at(-1).category_id,104);assert.equal(h.state.pending,null);
  const shared=harness([batch([refundIncome()])],{existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[{...returnCategory,user_id:'other'}]});
  await shared.run();assert.equal(shared.state.rows.at(-1).category_id,104);
});
test('refund category absence, ambiguity, lookup errors and incomplete pages preserve ordinary income without prompts',async()=>{
  const cases=[{refundCategories:[]},{refundCategories:[{...returnCategory,is_income:false}]},
    {refundCategories:[returnCategory,{...returnCategory,id:105}]},
    {refundCategories:[{...returnCategory,user_id:'other'},{...returnCategory,id:105,user_id:'another'}]},
    {refundCategoryError:true},{refundLookupError:true},{refundIncomplete:true}];
  for(const changes of cases){
    const h=harness([batch([refundIncome()])],{existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[returnCategory],...changes});await h.run();
    assert.equal(h.state.rows.at(-1).category_id,undefined,JSON.stringify(changes));assert.equal(h.state.rows.at(-1).type,'income');
    assert.equal(h.state.rows.at(-1).description,'Тестова покупка — повернення');assert.equal(h.state.pending,null);assert.equal(h.state.warnings.length,0);
    assert.ok(h.state.lookups.length<=10);
  }
});
test('refund category preserves duplicate protection across repeated import and canonical description',async()=>{
  const h=harness([batch([refundIncome()])],{existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[returnCategory]});
  await h.run(40);await h.run(41);assert.equal(h.state.inserts.length,1);assert.equal(h.state.rows.length,2);assert.match(h.state.replies.at(-1)[1],/Схожа операція/);
  const unresolved=harness([batch([refundIncome({bank:null})])],{existing:[h.state.rows.at(-1)],accounts:[refundAccount],refundCategories:[returnCategory]});
  await unresolved.run(42);assert.equal(unresolved.state.inserts.length,0);assert.match(unresolved.state.replies.at(-1)[1],/Схожа операція/);
});
test('generic purchase or refund labels without merchant never classify a refund',async()=>{
  for(const description of ['Покупка','Переказ','Магазин','Невідомо','Повернення коштів']){
    const h=harness([batch([refundIncome({description})])],{existing:[refundPurchase({description})],accounts:[refundAccount],refundCategories:[returnCategory]});await h.run();
    assert.equal(h.state.rows.at(-1).category_id,undefined,description);assert.equal(h.state.lookups.length,0);
  }
});
test('sub-cent bank OCR is reread before saving and cannot be rounded into a matching refund',async()=>{
  const options={existing:[refundPurchase()],accounts:[refundAccount],refundCategories:[returnCategory]};
  const bad=batch([refundIncome({amount:321.451})]);
  const rejected=harness([bad],options);await rejected.run();
  assert.equal(rejected.state.requests.length,2);assert.equal(rejected.state.inserts.length,0);assert.equal(rejected.state.pending,null);
  const invalidStrong=harness([batch([refundIncome()]),bad],options);await invalidStrong.run();assert.equal(invalidStrong.state.inserts.length,0);
  const repaired=harness([bad,batch([refundIncome()])],options);await repaired.run();
  assert.equal(repaired.state.requests.length,2);assert.equal(repaired.state.rows.at(-1).amount,321.45);assert.equal(repaired.state.rows.at(-1).category_id,104);
  const binary=harness([batch([refundIncome({amount:0.1+0.2})])],{...options,existing:[refundPurchase({amount:0.3})]});await binary.run();
  assert.equal(binary.state.rows.at(-1).amount,0.3);assert.equal(binary.state.rows.at(-1).category_id,104);
});
test('refund OCR direction follows visible positive sign even when the detail header says purchase',()=>{
  assert.ok(receiptSystem.includes('знаком «+»'));assert.ok(receiptSystem.includes('навіть якщо заголовок екрана «Покупка»'));assert.ok(receiptSystem.includes('заголовок не змінює знак'));
});
test('all month forms and weekdays work independently of date format',async()=>{
  const months=['січень|січня|січ','лютий|лютого|лют','березень|березня|бер','квітень|квітня|квіт','травень|травня|трав','червень|червня|черв','липень|липня|лип','серпень|серпня|серп','вересень|вересня|вер','жовтень|жовтня|жовт','листопад|листопада|лист','грудень|грудня|груд'];
  const options={today:'2027-01-01',messageDate:Date.parse('2026-12-31T12:00:00Z')/1000};
  for(let i=0;i<12;i++)for(const name of months[i].split('|')){
    const h=harness([{...single,date_text:`15 ${name} 2026`}],options);await h.run();
    assert.equal(h.state.rows[0]?.date,`2026-${String(i+1).padStart(2,'0')}-15`,name);
  }
  const weekdays=['нд|неділя','пн|понеділок','вт|вівторок','ср|середа','чт|четвер',"пт|п'ятниця",'сб|субота'];
  for(let day=1;day<=7;day++)for(const prefix of weekdays[new Date(`2026-06-0${day}T00:00:00Z`).getUTCDay()].split('|')){
    for(const text of [`2026-06-0${day}`,`${day}.06.2026`,`${day}/06/2026`,`${day} червня 2026`]){
      const h=harness([{...single,date_text:`${prefix}, ${text}`}],options);await h.run();
      assert.equal(h.state.rows[0]?.date,`2026-06-0${day}`,`${prefix} ${text}`);
    }
  }
});
test('calendar centuries and leap years remain bounded by current Kyiv date',async()=>{
  const options={today:'2027-02-01',messageDate:Date.parse('2026-10-20T12:00:00Z')/1000};
  for(const [raw,expected] of [['29.02.24','2024-02-29'],['29 лютого','2024-02-29'],['29.02.2000','2000-02-29'],['31.12','2026-12-31'],['1 січня 00','2000-01-01']]){
    const h=harness([{...single,date_text:raw}],options);await h.run();assert.equal(h.state.rows[0]?.date,expected,raw);
  }
  for(const raw of ['29.02.1900','29.02.2025','31.04.2026','01.01.28','2027-02-02','20/10.2026','03/04/05/06','пн 2026-10-20']){
    const h=harness([batch([transaction(),transaction({amount:2,date_text:raw})])],options);await h.run();assert.equal(h.state.inserts.length,0,String(raw));
  }
  const h=harness([{...single,date_text:'01.01.00'}],{today:'2100-06-01',messageDate:Date.parse('2100-06-01T00:00:00Z')/1000});
  await h.run();assert.equal(h.state.rows[0]?.date,'2100-01-01');
});
test('arbitrary suffixes match metadata independently of bank and network',async()=>{
  for(const card_last4 of ['0001','1234','9999'])for(const bank of ['privat','mono','oschad',null]){
    const h=harness([batch([transaction({bank,card_last4,card_network:'mastercard'})])],{accounts:[
      {id:1,name:'Покупки',bank:bank??'other',card_last4:'2222'},
      {id:2,name:'Моя картка',bank:bank??'other',card_last4,kind:'debit',active:true}]});
    await h.run();assert.equal(h.state.rows[0]?.account_id,2,`${bank} ${card_last4}`);
  }
});
test('collisions, cash, inactive and conflicting metadata remain manual',async()=>{
  const card={id:1,name:'Картка',bank:'privat',card_last4:'1234',kind:'debit',active:true};
  const cases=[[card,{...card,id:2}],[{...card,active:false}],[{...card,kind:'cash'}],[{...card,bank:'cash'}],
    [{...card,name:'1234',card_last4:'9999'}],[{...card,name:'1234 9999',card_last4:null}],
    [{...card,name:'12345678',card_last4:null}],[{...card,name:'1234',card_last4:'bad'}]];
  for(const accounts of cases){
    const h=harness([batch([transaction({bank:'privat',card_last4:'1234'})])],{accounts});await h.run();
    assert.equal(h.state.rows[0]?.account_id,null,JSON.stringify(accounts));
  }
  for(const [name,card_last4] of [['Картка 1234','1234'],['Budget2026','2026'],['1234567890121234','1234']]){
    const legacy=harness([batch([transaction({card_last4})])],{accounts:[{...card,card_last4:null,name}]});
    await legacy.run();assert.equal(legacy.state.rows[0]?.account_id,null,name);
  }
  for(const invalid of ['123',1234,'12345']){
    const h=harness([batch([transaction({bank:'privat',card_last4:invalid})])],{accounts:[card]});await h.run();assert.equal(h.state.rows[0]?.account_id,null);
  }
});
test('active account query selects card suffix and filters active accounts',async()=>{
  let columns,active;
  const q={select(s){columns=s;return q},eq(k,v){if(k==='active')active=v;return q},order(){return q},then(resolve){resolve({data:[]})}};
  const code=stripTypeScriptTypes(source.slice(source.indexOf('async function activeAccounts('),source.indexOf('// Лише для доходів:')));
  await new Function('sb',code+';return activeAccounts(true);')({from:()=>q});
  assert.ok(columns.split(',').includes('card_last4'));assert.equal(active,true);
});
function harness(responses, options={}) {
  const state={rows:[...(options.existing??[])],inserts:[],replies:[],txReplies:[],categories:[],requests:[],accountLoads:[],uploads:[],warnings:[],events:[],lookups:[],pending:options.pending??null};
  const sb={
    storage:{from:()=>({upload:async(...args)=>{state.uploads.push(args);return {error:null}},download:async()=>({data:{arrayBuffer:async()=>new Uint8Array([1]).buffer}})})},
    from(table) {
      const q={filters:[],payload:null,mode:'read',one:false};
      q.select=()=>q;
      q.eq=(key,value)=>{q.filters.push([key,value]);return q};
      q.in=(key,values)=>{(q.ins??=[]).push([key,values]);return q};
      q.gte=(key,value)=>{q.min=[key,value];return q};
      q.lte=(key,value)=>{q.max=[key,value];return q};
      q.order=()=>q;
      q.range=(lo,hi)=>{q.page=[lo,hi];return q};
      q.is=q.eq;
      q.single=q.maybeSingle=()=>{q.one=true;return q};
      q.insert=payload=>{q.mode='insert';q.payload=payload;return q};
      q.update=payload=>{q.mode='update';q.payload=payload;return q};
      q.then=(resolve,reject)=>Promise.resolve().then(()=>{
        if(table==='categories')return {data:options.refundCategories??[],error:options.refundCategoryError?{message:'synthetic'}:null};
        if(table==='profiles'){
          if(q.mode==='update') {
            const expected=q.filters.find(([k])=>k==='telegram_pending');
            if(options.pendingSaveError)return {data:null,error:{message:'synthetic'}};
            if(expected && expected[1] !== (state.pending == null ? null : JSON.stringify(state.pending)))return {data:[],error:null};
            state.pending=q.payload.telegram_pending;return {data:[{id:'u'}],error:null};
          }
          return {data:{telegram_pending:state.pending},error:null};
        }
        if(q.mode==='insert'){
          state.inserts.push(q.payload);state.events.push('insert');
          if(options.insertError)return {data:null,error:options.insertError};
          const rows=(Array.isArray(q.payload)?q.payload:[q.payload]).map((r,i)=>({...r,id:state.rows.length+i+1}));
          if(rows.some(r=>state.rows.some(old=>old.source_id===r.source_id)))return {data:null,error:{code:'23505'}};
          state.rows.push(...rows);
          // PostgreSQL's RETURNING order is not a mapping contract.
          return {data:q.one?rows[0]:[...rows].reverse(),error:null};
        }
        if(q.ins){
          state.lookups.push({filters:q.filters,ins:q.ins,max:q.max,page:q.page});
          if(options.refundLookupError)return {data:null,error:{message:'synthetic'}};
          if(options.refundIncomplete)return {data:Array.from({length:1000},(_,id)=>({id,type:'expense',amount:321.45,date:'2025-01-01',account_id:13,description:'Тестова покупка'})),error:null};
        }
        if(q.page && options.lookupError)return {data:null,error:{message:'synthetic'}};
        if(q.page && options.incompletePages)return {data:Array.from({length:1000},(_,id)=>({id,amount:999999,type:'income',date:'2026-10-20'})),error:null};
        let rows=state.rows.filter(r=>q.filters.every(([k,v])=>r[k]===v) &&
          (!q.ins||q.ins.every(([k,vs])=>vs.includes(r[k]))) &&
          (!q.min||r[q.min[0]]>=q.min[1]) && (!q.max||r[q.max[0]]<=q.max[1]));
        if(q.page)rows=rows.slice(q.page[0],q.page[1]+1);
        return {data:q.one?rows[0]??null:rows,error:null};
      }).then(resolve,reject);
      return q;
    }
  };
  let next=0;
  const fetch=async(url,init)=>{
    if(url.includes('anthropic')){
      state.requests.push(JSON.parse(init.body));
      const response=responses[Math.min(next++,responses.length-1)];
      return {ok:true,json:async()=>({stop_reason:options.stopReason??'end_turn',content:[{type:'text',text:JSON.stringify(response)}]})};
    }
    if(url.includes('sendMessage')){
      state.warnings.push(JSON.parse(init.body));state.events.push('warning');
      if(options.warningError==='network')throw new Error('synthetic');
      return {ok:options.warningError!=='http',json:async()=>({ok:options.warningError!=='api'})};
    }
    if(url.includes('getFile'))return {json:async()=>({ok:true,result:{file_path:'photo.jpg'}})};
    return {ok:true,arrayBuffer:async()=>new Uint8Array(options.imageBytes??[1,2]).buffer};
  };
  const accs=options.accounts??[{id:7,name:'Готівка'}];
  const linkReceiptRows=new Function('fixedContext','fixedCandidates','fixedOccurrenceKey',receiptLinkCode+';return linkReceiptRows;')(
    async()=>({fixed:options.fixed||[],paid:new Set(state.rows.filter(t=>t.fixed_id!=null).map(t=>{const f=(options.fixed||[]).find(f=>f.id===t.fixed_id);return f?fixedApi.fixedOccurrenceKey(f,t.payment_due_date??t.date):''}))}),fixedApi.fixedCandidates,fixedApi.fixedOccurrenceKey);
  const bindings={linkReceiptRows,sb,fetch,BOT_TOKEN:'test',CLAUDE_API_KEY:'test',RECEIPT_MODEL:'fast',RECEIPT_MODEL_STRONG:'strong',RECEIPT_SYSTEM:receiptSystem,CONFIRM_KB:{keyboard:[]},ENTRY_INPUT_KB:{keyboard:[]},MAIN_KB:{keyboard:[]},
    todayKyiv:()=> options.today??'2026-10-20',reply:async(...args)=>state.replies.push(args),
    replyTx:async(...args)=>state.txReplies.push(args),categorizeLater:id=>state.categories.push(id),
    activeAccounts:async(includeMono)=>{state.accountLoads.push(includeMono);return accs},
    pickAccount:()=>({matched:true,acc:options.captionAccount??accs[0]}),fmtMoney:String,
    console:{log(){},error(){}}};
  const api=new Function(...Object.keys(bindings),isolated+confirmSource+';return {addReceipt,receiptBatch,recognizeReceipt,receiptDate,confirmPending,answerReceiptDate};')(...Object.values(bindings));
  return {state,api,run:(update=42,caption)=>api.addReceipt(1,'u',update,[{file_id:'photo'}],undefined,caption,options.messageDate)};
}

test('visible date groups call current Kyiv date despite an older Telegram message and inherit selected card header',async()=>{
  const response={...batch([
    transaction({amount:1,date:null,date_text:'сьогодні'}),
    transaction({amount:2,date:null,date_text:'вчора'}),
    transaction({amount:3,date:null,date_text:'пн 19 жовтня'}),
  ]),bank:'privat',card_last4:'0882'};
  const h=harness([response],{today:'2026-10-22',messageDate:Date.parse('2026-10-20T21:30:00Z')/1000,
    accounts:[{id:88,bank:'privat',name:'Картка 0882',card_last4:'0882'},{id:89,bank:'privat',name:'Інша'}]});
  await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.date),['2026-10-22','2026-10-21','2026-10-19']);
  assert.deepEqual(h.state.rows.map(r=>r.account_id),[88,88,88]);
  assert.match(h.state.requests[0].system,/2026-10-22/);
});

test('yearless and relative dates roll back at New Year, preserving full historical dates',async()=>{
  const h=harness([batch([
    transaction({amount:1,date:'вчора'}),transaction({amount:2,date:'31 грудня'}),
    transaction({amount:3,date:'31.12'}),transaction({amount:4,date:'12.01.2025'}),
  ])],{today:'2027-01-01',messageDate:Date.parse('2026-12-31T12:30:00Z')/1000});
  await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.date),['2026-12-31','2026-12-31','2026-12-31','2025-01-12']);
});

test('unresolved date or wrong weekday rejects entire batch despite model ISO guess',async()=>{
  for(const raw of ['вт 19 жовтня','31 лютого','невідомо']){
    const h=harness([batch([transaction(),transaction({amount:2,date:'2026-10-19',date_text:raw})])],
      {messageDate:Date.parse('2026-10-20T12:00:00Z')/1000});
    await h.run();assert.equal(h.state.inserts.length,0,String(raw));
  }
});

test('runtime today function drives today and yesterday without a Telegram date or fixed calendar constant',async()=>{
  const options={today:'2026-10-24'};
  for(const [today,yesterday] of [['2026-10-24','2026-10-23'],['2026-11-01','2026-10-31'],['2027-01-01','2026-12-31']]){
    options.today=today;
    const h=harness([batch([transaction({amount:1,date_text:'сьогодні'}),transaction({amount:2,date_text:'вчора'})])],options);
    await h.run();assert.deepEqual(h.state.rows.map(r=>r.date),[today,yesterday]);
    assert.match(h.state.requests[0].system,new RegExp(today));
  }
  for(const [raw,date] of [['сьогодні','2026-10-20'],['вчора','2026-10-19'],['19 жовтня','2026-10-19']]){
    const h=harness([{...single,date:raw}]);await h.run();assert.equal(h.state.rows[0]?.date,date,raw);
  }
});

test('actual todayKyiv function changes at Kyiv midnight before UTC midnight',()=>{
  let now=Date.parse('2026-10-23T20:59:00Z');
  class Clock extends Date { constructor(...args){super(...(args.length?args:[now]));} }
  const code=source.slice(source.indexOf('function todayKyiv('),source.indexOf('// Невдалі спроби коду'));
  const today=new Function('Date',stripTypeScriptTypes(code)+';return todayKyiv;')(Clock);
  assert.equal(today(),'2026-10-23');
  now=Date.parse('2026-10-23T21:01:00Z');assert.equal(today(),'2026-10-24');
});

test('conflicting per-operation card hints do not inherit selected header',async()=>{
  const response={...batch([transaction({bank:'mono',card_network:'visa'}),transaction({amount:2})]),bank:'privat',card_last4:'0882'};
  const h=harness([response],{accounts:[{id:8,bank:'mono',name:'Visa'},{id:9,bank:'privat',name:'0882',card_last4:'0882'}]});
  await h.run();assert.deepEqual(h.state.rows.map(r=>r.account_id),[8,9]);
});

test('invalid visible date cannot borrow an earlier multipart date',async()=>{
  const h=harness([{...single,has_total:false,amount:null}, {...single,date_text:'31 лютого'}],
    {messageDate:Date.parse('2026-10-20T12:00:00Z')/1000});
  await h.run(40);await h.run(41);
  assert.equal(h.state.inserts.length,0);
});

test('missing visible date uses current Kyiv day instead of a model ISO guess',async()=>{
  for(const date_text of [null,'','   ']){
    const h=harness([batch([transaction(),transaction({amount:2,date:'2026-10-19',date_text})])],
      {messageDate:Date.parse('2026-10-20T12:00:00Z')/1000});
    await h.run();assert.deepEqual(h.state.rows.map(r=>r.date),['2026-10-19','2026-10-20'],JSON.stringify(date_text));
  }
});

test('multipart relative date retains initial runtime reference across Kyiv midnight',async()=>{
  const options={today:'2026-10-20',messageDate:Date.parse('2026-10-19T20:59:00Z')/1000};
  const h=harness([{...single,has_total:false,amount:null,date_text:'сьогодні'},{...single,date_text:'сьогодні'}],options);
  await h.run(40);
  options.today='2026-10-21';options.messageDate=Date.parse('2026-10-20T21:01:00Z')/1000;
  await h.run(41);
  assert.equal(h.state.rows[0].date,'2026-10-20');
  assert.ok(h.state.requests.every(r=>r.system.includes('Europe/Kyiv): 2026-10-20')));
});
test('one screenshot atomically inserts all operations and maps dates/types/buttons by source id',async()=>{
  const h=harness([batch()]);await h.run();
  assert.equal(h.state.inserts.length,1);
  assert.ok(Array.isArray(h.state.inserts[0]));
  assert.deepEqual(h.state.rows.map(r=>[r.amount,r.type,r.date,r.source_id,r.account_id]),
    [[120.5,'expense','2026-10-19','tg:42',null],[200,'income','2026-10-20','tg:42:1',null]]);
  assert.equal(h.state.rows[0].receipt_url,h.state.rows[1].receipt_url);
  assert.deepEqual(h.state.categories,[1,2]);
  assert.deepEqual(h.state.txReplies.map(r=>[r[1],r[2].amount,r[3]]),[[1,120.5,null],[2,200,null]]);
  assert.equal(h.state.pending,null);
});
test('caption selects an explicit account for each operation',async()=>{
  const h=harness([batch()]);await h.run(42,'готівка');
  assert.deepEqual(h.state.rows.map(r=>r.account_id),[7,7]);
});
test('replaying the same Telegram update neither inserts nor calls vision twice',async()=>{
  const h=harness([batch()]);await h.run();await h.run();
  assert.equal(h.state.inserts.length,1);assert.equal(h.state.requests.length,2);
});
test('invalid member or incomplete list rejects whole batch without pending writes',async()=>{
  const cases=[
    batch([transaction(),transaction({amount:-1})]),batch([transaction({amount:true})]),
    batch([transaction({currency:'USD'})]),batch([transaction({type:'transfer'})]),
    batch([]),
    batch(Array.from({length:21},()=>transaction())),{...batch(),complete:false},
    {...batch(),readable:'poor'},{transactions:batch().transactions},
  ];
  for(const candidate of cases){
    const h=harness([candidate]);await h.run();
    assert.equal(h.state.inserts.length,0,JSON.stringify(candidate));
    assert.equal(h.state.pending,null);
  }
});
test('invalid batch cannot fall back to one receipt from stronger model',async()=>{
  const h=harness([{...batch(),complete:false},single]);await h.run();
  assert.equal(h.state.inserts.length,0);
  assert.equal(h.state.requests.length,2);
});
test('stronger model can repair complete batch',async()=>{
  const h=harness([{...batch(),readable:'poor'},batch()]);await h.run();
  assert.equal(h.state.rows.length,2);
});
test('failed atomic insert has no successful confirmations or category calls',async()=>{
  const h=harness([batch()],{insertError:{code:'XX000'}});await h.run();
  assert.equal(h.state.rows.length,0);assert.equal(h.state.txReplies.length,0);
  assert.equal(h.state.categories.length,0);assert.match(h.state.replies.at(-1)[1],/Нічого не записано/);
});
test('concurrent replay unique violation is silent',async()=>{
  const h=harness([batch()],{insertError:{code:'23505'}});await h.run();
  assert.equal(h.state.replies.length,0);assert.equal(h.state.categories.length,0);
});
test('even valid JSON from truncated API output cannot insert',async()=>{
  const h=harness([batch()],{stopReason:'max_tokens'});await h.run();
  assert.equal(h.state.rows.length,0);assert.equal(h.state.requests.length,2);
  assert.ok(h.state.requests[0].max_tokens>=4000);
});
test('single receipt remains one expense and supports caption',async()=>{
  const h=harness([single]);await h.run(42,'готівка');
  assert.equal(h.state.rows.length,1);assert.equal(h.state.rows[0].amount,250);
  assert.equal(h.state.rows[0].account_id,7);assert.equal(h.state.rows[0].source_id,'tg:42');
});

test('historical screenshot dates are retained and never derived from send time',async()=>{
  const h=harness([batch([transaction({date:'2025-01-12'})])]);await h.run(999999);
  assert.equal(h.state.rows[0].date,'2025-01-12');
  for(const raw of [null,undefined,'','2026-02-30','2026-10-21','19.10.2026'])assert.equal(h.api.receiptDate(raw),null);
  assert.equal(h.api.receiptDate('2024-02-29'),'2024-02-29');
  const singleOld=harness([{...single,date:'2025-01-12'}]);await singleOld.run();
  assert.equal(singleOld.state.rows[0].date,'2025-01-12');
});

test('one invalid or future screenshot date rejects the whole batch after retry',async()=>{
  for(const date of ['2026-02-30','2026-10-21']){
    const h=harness([batch([transaction(),transaction({date})])]);await h.run();
    assert.equal(h.state.inserts.length,0);
    assert.equal(h.state.requests.length,2);
    assert.match(h.state.replies.at(-1)[1],/дату операції.*Нічого не записано/);
  }
});

test('strong model may recover an invalid screenshot date but cannot save invalid final dates',async()=>{
  const repaired=harness([{...single,date:'31 лютого'},single]);await repaired.run();
  assert.equal(repaired.state.rows[0].date,'2026-10-19');
  assert.equal(repaired.state.requests.length,2);
  for(const date of ['2026-02-30','2026-10-21']){
    const h=harness([{...single,date}]);await h.run();
    assert.equal(h.state.inserts.length,0);
    assert.match(h.state.replies.at(-1)[1],/дату операції/);
  }
});

test('multipart retains an earlier screenshot date when the final part omits it',async()=>{
  const h=harness([{...single,has_total:false,amount:null,date:'2025-01-12'}, {...single,date:null}]);
  await h.run(41);await h.run(42);
  assert.equal(h.state.rows.length,1);
  assert.equal(h.state.rows[0].date,'2025-01-12');
});

test('undated single receipts and screenshot operations use current Kyiv day',async()=>{
  for(const date of [null,undefined,'','   ']){
    const options={today:'2026-10-24',messageDate:Date.parse('2026-10-23T20:59:00Z')/1000};
    const receipt=harness([{...single,date}],options);await receipt.run();
    assert.equal(receipt.state.rows[0]?.date,'2026-10-24');
    assert.equal(receipt.state.requests.length,1);
    const screenshot=harness([batch([transaction({date}),transaction({amount:2,date:'2025-01-12'})])],options);
    await screenshot.run();assert.deepEqual(screenshot.state.rows.map(r=>r.date),['2026-10-24','2025-01-12']);
  }
  const undated={...single};delete undated.date;
  const receipt=harness([undated]);await receipt.run();assert.equal(receipt.state.rows[0]?.date,'2026-10-20');
});

test('undated multipart fallback stays fixed through midnight and pending confirmation',async()=>{
  const options={today:'2026-10-20'};
  const h=harness([{...single,has_total:false,amount:null,date:null},{...single,date:null}],options);
  await h.run(40);assert.equal(h.state.pending.date,'2026-10-20');
  options.today='2026-10-21';await h.run(41);
  assert.equal(h.state.rows[0]?.date,'2026-10-20');
  const confirmed=harness([{...single,has_total:false,amount:null,date_text:null}],options);
  await confirmed.run(50);options.today='2026-10-22';await confirmed.api.confirmPending(1,'u');
  assert.equal(confirmed.state.rows[0]?.date,'2026-10-21');
});

test('undated receipt duplicate checks use fallback date before insertion',async()=>{
  const h=harness([{...single,date:null}]);await h.run(40);await h.run(41);
  assert.equal(h.state.rows.length,1);assert.equal(h.state.inserts.length,1);
  assert.match(h.state.replies.at(-1)[1],/Схожа операція вже записана: 20.10.2026/);
  const screenshot=harness([batch([transaction({date_text:null})])]);
  await screenshot.run(40);await screenshot.run(41);
  assert.equal(screenshot.state.rows.length,1);assert.equal(screenshot.state.inserts.length,1);
});

test('/yes cannot confirm a receipt with missing or invalid screenshot date',async()=>{
  for(const date of [null,'2026-02-30','2026-10-21']){
    const pending={kind:'receipt',parts:[{path:'u/old.jpg',update_id:40}],expires:'2099-01-01T00:00:00Z',items_sum:250,date};
    const h=harness([],{pending});await h.api.confirmPending(1,'u');
    assert.equal(h.state.inserts.length,0);
    assert.equal(h.state.pending,pending);
    assert.match(h.state.replies.at(-1)[1],/дату операції/);
  }
});

test('/yes keeps historical screenshot date and checks it for duplicates',async()=>{
  const pending={kind:'receipt',parts:[{path:'u/old.jpg',update_id:40}],expires:'2099-01-01T00:00:00Z',items_sum:250,date:'2025-01-12',description:'Чек'};
  const h=harness([],{pending});await h.api.confirmPending(1,'u');
  assert.equal(h.state.rows[0].date,'2025-01-12');
  const duplicate=harness([],{pending,existing:[{id:1,amount:250,type:'expense',date:'2025-01-12',description:'Чек',account_id:null}]});
  await duplicate.api.confirmPending(1,'u');
  assert.equal(duplicate.state.inserts.length,0);
  assert.match(duplicate.state.replies.at(-1)[1],/Схожа операція вже записана: 12.01.2025/);
});

test('same historical operation from another update is blocked by screenshot date and amount',async()=>{
  const h=harness([batch([transaction({date:'2025-01-12'})])]);
  await h.run(40);await h.run(999999);
  assert.equal(h.state.rows.length,1);
  assert.equal(h.state.inserts.length,1);
  assert.match(h.state.replies.at(-1)[1],/Схожа операція вже записана: 12.01.2025/);
});
test('multipart receipt keeps one final total and its original account',async()=>{
  const h=harness([{...single,has_total:false,amount:null},single]);
  await h.run(41,'готівка');assert.equal(h.state.rows.length,0);
  assert.equal(h.state.pending.kind,'receipt');
  await h.run(42);
  assert.equal(h.state.rows.length,1);assert.equal(h.state.rows[0].amount,250);
  assert.equal(h.state.rows[0].receipt_parts.length,2);assert.equal(h.state.rows[0].account_id,7);
  assert.equal(h.state.pending,null);
});
test('batch is rejected during multipart collection without clearing its context',async()=>{
  const pending={kind:'receipt',parts:[{path:'u/old.jpg',update_id:40}],expires:'2099-01-01T00:00:00Z',account_id:7};
  const h=harness([batch()],{pending});await h.run();
  assert.equal(h.state.rows.length,0);assert.equal(h.state.pending,pending);
});
test('independent batch does not erase an existing income confirmation',async()=>{
  const pending={amount:100,type:'income',source_id:'tg:1'};
  const h=harness([batch()],{pending});await h.run();
  assert.equal(h.state.rows.length,0);assert.equal(h.state.pending,pending);
});

const bankAccounts=[
  {id:11,name:'Особиста 0882',bank:'privat',card_last4:'0882'},
  {id:12,name:'Картка для покупок',bank:'mono'},
  {id:13,name:'Для платежів',bank:'oschad'},
];
test('prompt recognises the Oschad 24/7 history screen without bank name or card digits',()=>{
  for(const sign of ['Ощад 24/7','bank "oschad"','«Продукти», «Платежі», «Історія», «Ще»','Аналітика за','«Всі рахунки»','«Телефон»','підсумки місяця, не операції'])
    assert.ok(receiptSystem.includes(sign),sign);
});
test('Oschad screenshot without visible digits picks the only Oschad account with configured digits',async()=>{
  const accounts=[{id:1,name:'Ощадбанк',bank:'oschad',kind:'debit',active:true,card_last4:'4366'},
    {id:2,name:'ПриватБанк кредитна',bank:'privat',kind:'credit',active:true,card_last4:'0882'},
    {id:4,name:'Готівка',bank:'cash',kind:'cash',active:true},
    {id:5,name:'Приват Біла',bank:'privat',kind:'debit',active:true,card_last4:'8814'}];
  const h=harness([batch([transaction({bank:'oschad',amount:440,description:'YUR-AKVA'}),
    transaction({bank:'oschad',amount:190,description:'Melisa'}),transaction({bank:'oschad',amount:400,description:'RozetkaPay'})])],{accounts});
  await h.run();assert.deepEqual(h.state.rows.map(r=>r.account_id),[1,1,1]);
});
test('mixed bank screenshot picks Privat 0882, Mono Visa and Oschad independently',async()=>{
  const h=harness([batch([
    transaction({bank:'privat',card_last4:'0882'}),
    transaction({bank:'mono',card_network:'visa',amount:121}),
    transaction({bank:'oschad',amount:122}),
  ])],{accounts:bankAccounts});await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.account_id),[11,12,13]);
  assert.deepEqual(h.state.txReplies.map(r=>r[3]),[11,12,13]);
  assert.ok(h.state.accountLoads.every(Boolean));
  for(const args of h.state.txReplies)assert.ok(args[4].accs.find(a=>a.id===args[3])?.name);
  for(const row of h.state.rows)assert.equal(row.hint,undefined,'OCR metadata is not a database column');
});
test('Privat wrong card, unknown bank, VISA alone and invalid card number leave account open',async()=>{
  for(const hint of [
    {bank:'privat',card_last4:'9999'},{bank:'unknown',card_network:'visa'},
    {bank:null,card_network:'visa'},{bank:'privat',card_last4:'1234567890120882'},
  ]){
    const h=harness([batch([transaction(hint)])],{accounts:bankAccounts});await h.run();
    assert.equal(h.state.rows[0].account_id,null,JSON.stringify(hint));
  }
});
test('ambiguous accounts need choices; configured digits resolve them regardless of network',async()=>{
  const accounts=[...bankAccounts,{id:21,name:'Інша картка',bank:'privat'},{id:22,name:'Visa для витрат',bank:'mono'},{id:23,name:'Другий',bank:'oschad'}];
  const h=harness([batch([
    transaction({bank:'privat'}),transaction({bank:'privat',card_last4:'0882',amount:121}),
    transaction({bank:'mono',card_network:'visa',amount:122}),transaction({bank:'oschad',amount:123}),
  ])],{accounts});await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.account_id),[null,11,null,null]);
  const ambiguous=harness([batch([transaction({bank:'mono',card_network:'visa'})])],{
    accounts:[...accounts,{id:24,name:'Ще Visa',bank:'mono'}]});
  await ambiguous.run();assert.equal(ambiguous.state.rows[0].account_id,null);
});
test('unique Privat account works without a number in its configured name',async()=>{
  const h=harness([batch([transaction({bank:'privat',card_last4:'0882'})])],{
    accounts:[{id:1,name:'Моя картка',bank:'privat',card_last4:'0882'}]});
  await h.run();assert.equal(h.state.rows[0].account_id,1);
});
test('explicit caption overrides conflicting visual bank for entire batch',async()=>{
  const h=harness([batch([transaction({bank:'privat',card_last4:'0882'}),transaction({bank:'mono',card_network:'visa',amount:121})])],
    {accounts:bankAccounts,captionAccount:bankAccounts[2]});
  await h.run(42,'ощад');assert.deepEqual(h.state.rows.map(r=>r.account_id),[13,13]);
});
test('single receipt uses visual bank and multipart preserves first selected account',async()=>{
  const h=harness([{...single,bank:'mono',card_network:'visa'}],{accounts:bankAccounts});
  await h.run();assert.equal(h.state.rows[0].account_id,12);
  const multi=harness([{...single,has_total:false,amount:null,bank:'privat',card_last4:'0882'},
    {...single,bank:'oschad'}],{accounts:bankAccounts});
  await multi.run(41);await multi.run(42);assert.equal(multi.state.rows[0].account_id,11);
});
test('multipart caption overrides first-part account',async()=>{
  const h=harness([{...single,has_total:false,amount:null,bank:'privat',card_last4:'0882'},
    {...single,bank:'mono',card_network:'visa'}],{accounts:bankAccounts,captionAccount:bankAccounts[2]});
  await h.run(41);await h.run(42,'ощад');assert.equal(h.state.rows[0].account_id,13);
});
test('account callback permits Mono for photo transactions only',async()=>{
  const callback=stripTypeScriptTypes(source.slice(source.indexOf('async function onCallback('),source.indexOf('function todayKyiv(')));
  for(const receipt_url of [null,'u/photo.jpg']){
    let updated=false,includeMono=null;
    const calls=[];
    const sb={from(table){
      let update=false;
      const q={select(){return q},eq(){return q},maybeSingle(){return q},update(){update=true;return q},
        then(resolve,reject){return Promise.resolve().then(()=>{
          if(table==='profiles')return {data:{id:'u'}};
          if(update){updated=true;return {data:[{id:42,amount:1,type:'expense',description:'x'}]}};
          return {data:{receipt_url}};
        }).then(resolve,reject)}};
      return q;
    }};
    const run=new Function('sb','activeAccounts','parsePaidCallback','tgCall','accKeyboard','txText',callback+';return onCallback;')(
      sb,async flag=>{includeMono=flag;return flag?[bankAccounts[1]]:[]},()=>null,
      async(method,body)=>calls.push({method,body}),()=>null,(_row,name)=>name);
    await run({id:'cb',data:'acc:42:12',message:{chat:{id:1},message_id:2}});
    assert.equal(includeMono,!!receipt_url);
    assert.equal(updated,!!receipt_url);
    if(receipt_url){
      const edited=calls.find(c=>c.method==='editMessageText').body;
      assert.equal(edited.text,'Картка для покупок');
      assert.deepEqual(edited.reply_markup,{inline_keyboard:[]});
    }
    else assert.equal(calls[0].body.text,'Рахунок недоступний');
  }
});
test('manual account callback clears all buttons only after successful database update',async()=>{
  const callback=stripTypeScriptTypes(source.slice(source.indexOf('async function onCallback('),source.indexOf('function todayKyiv(')));
  for(const failed of [false,true]){
    const calls=[];
    const sb={from(table){
      let update=false;
      const q={select(){return q},eq(){return q},maybeSingle(){return q},update(){update=true;return q},
        then(resolve,reject){return Promise.resolve().then(()=>{
          if(table==='profiles')return {data:{id:'u'}};
          if(update)return failed?{error:{message:'synthetic'}}:{data:[{id:42,amount:1,type:'expense',description:'x'}]};
          return {data:{receipt_url:null}};
        }).then(resolve,reject)}};
      return q;
    }};
    const run=new Function('sb','activeAccounts','parsePaidCallback','tgCall','txText','console',callback+';return onCallback;')(
      sb,async()=>bankAccounts.filter(a=>a.bank!=='mono'),()=>null,async(method,body)=>calls.push({method,body}),
      (_row,name)=>name,{error(){}});
    await run({id:'cb',data:'acc:42:11',message:{chat:{id:1},message_id:2}});
    const edit=calls.find(c=>c.method==='editMessageText');
    if(failed){assert.equal(edit,undefined);assert.equal(calls[0].body.text,'Не вдалося змінити рахунок');}
    else {assert.equal(edit.body.text,'Особиста 0882');assert.deepEqual(edit.body.reply_markup,{inline_keyboard:[]});}
  }
});
test('Karabas Oct18 vs screenshot Oct20 same amount and account blocks whole batch across sources',async()=>{
  for(const source of ['mono','manual','telegram']){
    const existing=[{id:1,amount:786,type:'expense',date:'2026-10-18',account_id:2,description:'Інший опис банку',source}];
    const h=harness([batch([transaction({amount:786,date:'2026-10-20',description:'Карбас',bank:'privat',card_last4:'0882'}),transaction({amount:50})])],
      {existing,accounts:[{id:2,name:'Моя',bank:'privat',card_last4:'0882'}]});
    await h.run();
    assert.equal(h.state.inserts.length,0);assert.equal(h.state.rows.length,1);
    assert.match(h.state.replies.at(-1)[1],/18\.10\.2026, 786/);
  }
});
test('normalized description detects duplicate when no account is known',async()=>{
  const existing=[{id:1,amount:786,type:'expense',date:'2026-10-18',account_id:2,description:'КАР-БАС!'}];
  const h=harness([batch([transaction({amount:786,date:'2026-10-20',description:'кар бас'})])],{existing});
  await h.run();assert.equal(h.state.inserts.length,0);
});
test('same amount with distinct account/description, distant date, or different type is allowed',async()=>{
  const candidate=transaction({amount:786,date:'2026-10-20',description:'Карбас',bank:'oschad'});
  for(const different of [
    {account_id:3,description:'Кава'},{date:'2026-10-16'},{type:'income'},
  ]){
    const existing=[{id:1,amount:786,type:'expense',date:'2026-10-18',account_id:2,description:'Карбас',...different}];
    const h=harness([batch([candidate])],{existing,accounts:[{id:2,name:'Моя',bank:'oschad'}]});
    await h.run();assert.equal(h.state.inserts.length,1,JSON.stringify(different));
  }
});
test('duplicate inside screenshot rejects whole batch without any insert',async()=>{
  const h=harness([batch([transaction({date:'2026-10-18'}),transaction({date:'2026-10-20'})])]);
  await h.run();assert.equal(h.state.inserts.length,0);
  assert.match(h.state.replies.at(-1)[1],/На зображенні є схожі операції/);
});

test('Bank rows preserve separate payment times and dates when another row has a clipped required field',async()=>{
  const response={...batch([
    transaction({amount:147.23,description:'Тестовий сервіс',date_text:'Вчора',time:'14:42'}),
    transaction({amount:147.23,description:'Тестовий сервіс',date_text:'Вчора',time:'14:18'}),
    transaction({amount:312.4,description:'Автоплатіж',date_text:'Вчора',time:'10:25'}),
    transaction({amount:58.91,description:'Тестова крамниця',date_text:'Вчора',time:'01:08'}),
    transaction({amount:6300,type:'income',description:'Тестове надходження',date_text:'Ср, 17 червня',time:'17:35'}),
  ]),bank:'privat',card_last4:'2468',omitted:[{reason:'clipped',description:'Тестове надходження — обрізана сума'}]};
  const h=harness([response],{today:'2026-06-19',messageDate:Date.parse('2026-06-18T21:25:00Z')/1000,
    accounts:[{id:88,bank:'privat',name:'Картка',card_last4:'2468'}]});
  await h.run();
  assert.equal(h.state.rows.length,5);
  assert.deepEqual(h.state.rows.map(r=>r.date),['2026-06-18','2026-06-18','2026-06-18','2026-06-18','2026-06-17']);
  assert.deepEqual(h.state.rows.map(r=>r.amount),[147.23,147.23,312.4,58.91,6300]);
  assert.ok(h.state.rows.every(r=>r.account_id===88));
  assert.match(h.state.rows[0].description,/ · 14:42$/);assert.match(h.state.rows[1].description,/ · 14:18$/);
  assert.deepEqual(h.state.events,['warning','insert']);
  assert.match(h.state.warnings[0].text,/Обрізаних операцій пропущено: 1/);
  assert.match(h.state.replies[0][1],/Записано операцій: 5\. Обрізаних операцій пропущено: 1/);
  assert.equal(h.state.requests.length,2);
});

test('Oschad rows retain group dates and report another row only when its required amount is clipped',async()=>{
  const response={...batch([
    transaction({amount:75,description:'**1234',date_text:'18 червня'}),
    transaction({amount:125,description:'**5678',date_text:'18 червня'}),
    transaction({amount:260,description:'Тестова майстерня',date_text:'17 червня'}),
  ]),bank:'oschad',omitted:[{reason:'clipped',description:'Тестове кафе — обрізана сума'}]};
  const h=harness([response],{today:'2026-06-19',messageDate:Date.parse('2026-06-18T21:26:00Z')/1000,
    accounts:[{id:43,bank:'oschad',name:'Картка',card_last4:'1357'}]});
  await h.run();
  assert.deepEqual(h.state.rows.map(r=>[r.amount,r.date,r.account_id]),[[75,'2026-06-18',43],[125,'2026-06-18',43],[260,'2026-06-17',43]]);
  assert.match(h.state.warnings[0].text,/Тестове кафе/);
  assert.match(receiptSystem,/Суми картки «Аналітика» це підсумки місяця, не операції/);
  assert.match(receiptSystem,/Номер отримувача.*не є карткою власника/);
});

test('clipped decoration or optional time does not omit readable amounts and group dates',async()=>{
  assert.match(receiptSystem,/Обрізані іконка, категорія, спосіб оплати, необов’язковий час.*НЕ заважають включити операцію/);
  assert.match(receiptSystem,/обрізали саме обов’язкове поле операції\. Лише тоді пропусти рядок/);
  const options={today:'2026-06-19',messageDate:Date.parse('2026-06-18T21:26:00Z')/1000};
  const response={...batch([
    transaction({amount:75,description:'**1234',date_text:'18 червня'}),
    transaction({amount:125,description:'**5678',date_text:'18 червня'}),
    transaction({amount:260,description:'Тестова майстерня',date_text:'17 червня'}),
    transaction({amount:85,description:'Тестове кафе',date_text:'17 червня',time:null}),
  ]),bank:'oschad',omitted:[]};
  const h=harness([response],options);await h.run();
  assert.deepEqual(h.state.rows.map(r=>[r.amount,r.date]),[[75,'2026-06-18'],[125,'2026-06-18'],[260,'2026-06-17'],[85,'2026-06-17']]);
  assert.equal(h.state.warnings.length,0);
  const bottom=harness([{...batch([transaction({amount:2750,type:'income',description:'Тестове надходження',date_text:'Ср, 17 червня',time:null})]),omitted:[]}],options);
  await bottom.run();assert.equal(bottom.state.rows[0]?.amount,2750);assert.equal(bottom.state.rows[0]?.date,'2026-06-17');
  assert.equal(bottom.state.warnings.length,0);
});

test('explicit screenshot capture date anchors yesterday and yearless groups instead of resend day',async()=>{
  for(const caption of ['дата скриншота: 2026-06-17','ДАТА СКРИНШОТУ: 17.06.2026']){
    const h=harness([batch([transaction({amount:75,date_text:'Вчора'}),transaction({amount:125,date_text:'17 червня'})])],
      {today:'2026-06-19',messageDate:Date.parse('2026-06-18T21:01:00Z')/1000});
    await h.run(70,caption);
    assert.deepEqual(h.state.rows.map(r=>r.date),['2026-06-16','2026-06-17']);
    assert.match(h.state.requests[0].system,/2026-06-17/);
  }
  const unknown=harness([batch([transaction({date_text:null})])],{today:'2026-06-19',messageDate:Date.parse('2026-06-18T21:01:00Z')/1000});
  await unknown.run(70,'дата скриншота: 2026-06-17');assert.equal(unknown.state.rows[0]?.date,'2026-06-19');
});

test('invalid explicit capture date blocks before storage or OCR and arbitrary caption dates do not anchor',async()=>{
  const options={today:'2026-06-20',messageDate:Date.parse('2026-06-18T21:01:00Z')/1000};
  for(const caption of ['дата скриншота:','дата скриншота: невідомо','дата скриншота: 2026-02-30',
    'дата скриншота: 2026-06-21','дата скриншота: 2026-06-17abc','дата скриншота: 2026-06-17; дата скриншоту: 2026-06-18']){
    const h=harness([batch()],options);await h.run(70,caption);
    assert.equal(h.state.inserts.length,0);assert.equal(h.state.uploads.length,0);assert.equal(h.state.requests.length,0);
    assert.match(h.state.replies.at(-1)[1],/Некоректна дата скриншота/);
  }
  const h=harness([batch([transaction({date_text:'Вчора'})])],options);
  await h.run(70,'готівка, повернення за 2026-06-17');
  assert.equal(h.state.rows[0].date,'2026-06-19');assert.equal(h.state.rows[0].account_id,7);
  const later=harness([batch([transaction({date_text:'Сьогодні'})])],options);
  await later.run(71,'дата скриншота: 2026-06-20');assert.equal(later.state.rows[0]?.date,'2026-06-20');
});

test('multipart keeps first explicit capture reference across midnight and later valid captions',async()=>{
  const options={today:'2026-06-20',messageDate:Date.parse('2026-06-18T20:59:00Z')/1000};
  const h=harness([{...single,has_total:false,amount:null,date_text:'Вчора'},{...single,date_text:'Вчора'}],options);
  await h.run(70,'дата скриншота: 2026-06-17');
  assert.equal(h.state.pending.reference,'2026-06-17');
  options.messageDate=Date.parse('2026-06-18T21:01:00Z')/1000;
  await h.run(71,'дата скриншота: 2026-06-18');
  assert.equal(h.state.rows[0].date,'2026-06-16');
  assert.match(h.state.requests.at(-1).system,/2026-06-17/);
});

test('recipient suffix cannot select a source account even when OCR reports it as owner metadata',async()=>{
  for(const description of ['**1234','Переказ на картку **1234','Переказ на картку 1234','Отримувач •••• 1234',
    'Переказ на картку','Переказ на рахунок','Отримувач','Одержувач']){
    const response={...batch([transaction({description,bank:'oschad',card_last4:'1234',card_network:'visa'})]),bank:'oschad',card_last4:null};
    const h=harness([response],{accounts:[{id:3,name:'Джерело',bank:'oschad',card_last4:'2468'},{id:4,name:'Інша картка',bank:'oschad',card_last4:'1234'}]});
    await h.run();assert.equal(h.state.rows[0]?.account_id,null,description);
    const unique=harness([response],{accounts:[{id:3,name:'Джерело',bank:'oschad',card_last4:'2468'}]});
    await unique.run();assert.equal(unique.state.rows[0]?.account_id,3,description);
  }
  for(const owner of ['2468','1234']){
    const h=harness([{...batch([transaction({description:'Переказ на картку **1234',bank:'oschad',card_last4:'1234',card_network:'visa'})]),bank:'oschad',card_last4:owner}],
      {accounts:[{id:3,name:'Джерело',bank:'oschad',card_last4:'2468'},{id:4,name:'Інша картка',bank:'oschad',card_last4:'1234'}]});
    await h.run();assert.equal(h.state.rows[0]?.account_id,owner==='2468'?3:4);
  }
});

test('only explicit clipped omissions are accepted and a failed warning prevents every write',async()=>{
  for(const omitted of [null,{},[{reason:'unknown_date',description:'x'}],[{reason:'clipped',description:''}]]){
    const h=harness([{...batch(),omitted}]);await h.run();
    assert.equal(h.state.inserts.length,0);assert.equal(h.state.warnings.length,0);
  }
  for(const warningError of ['network','http','api']){
    const h=harness([{...batch(),omitted:[{reason:'clipped',description:'Обрізаний рядок'}]}],{warningError});await h.run();
    assert.equal(h.state.inserts.length,0);assert.equal(h.state.categories.length,0);
    assert.match(h.state.replies.at(-1)[1],/Нічого не записано/);
  }
});

test('time evidence only separates same-day rows and never disables existing-transaction checks',async()=>{
  for(const fields of [{time:null},{time:'14:42'},{time:'25:01'},{date:'2026-10-18',time:'14:18'}]){
    const h=harness([batch([transaction({time:'14:42'}),transaction(fields)])]);await h.run();
    assert.equal(h.state.inserts.length,0,JSON.stringify(fields));
  }
  for(const description of ['Магазин','Магазин · 14:42']){
    const h=harness([batch([transaction({time:'14:18'})])],{existing:[{id:1,amount:120.5,type:'expense',date:'2026-10-19',description,account_id:null}]});
    await h.run();assert.equal(h.state.inserts.length,0);
    assert.match(h.state.replies.at(-1)[1],/Схожа операція вже записана/);
  }
});

test('PNG and JPEG byte signatures retain matching vision and private-storage media types',async()=>{
  for(const [imageBytes,type,ext] of [[[137,80,78,71,13,10,26,10],'image/png','.png'],[[255,216,255,224],'image/jpeg','.jpg']]){
    const h=harness([single],{imageBytes});await h.run();
    assert.equal(h.state.rows.length,1);
    assert.equal(h.state.requests[0].messages[0].content[0].source.media_type,type);
    assert.equal(h.state.uploads[0][2].contentType,type);
    assert.ok(h.state.rows[0].receipt_url.endsWith(ext));
  }
});
test('single and multipart final receipt also check existing transactions',async()=>{
  const existing=[{id:1,amount:250,type:'expense',date:'2026-10-19',account_id:null,description:'Чек'}];
  const h=harness([single],{existing});await h.run();assert.equal(h.state.inserts.length,0);
  const multi=harness([{...single,has_total:false,amount:null},single],{existing});
  await multi.run(41);await multi.run(42);
  assert.equal(multi.state.inserts.length,0);assert.equal(multi.state.pending.kind,'receipt');
});
test('duplicate lookup failure or incomplete pagination blocks screenshot writes',async()=>{
  for(const options of [{lookupError:true},{incompletePages:true}]){
    const h=harness([batch()],options);await h.run();
    assert.equal(h.state.inserts.length,0);assert.match(h.state.replies.at(-1)[1],/Не вдалося перевірити/);
  }
});
test('duplicate beyond first page is found before saving',async()=>{
  const existing=Array.from({length:1000},(_,i)=>({id:i+1,amount:9999,type:'income',date:'2026-10-19',description:'x'}));
  existing.push({id:1001,amount:120.5,type:'expense',date:'2026-10-19',description:'Магазин',account_id:null});
  const h=harness([batch()],{existing});await h.run();assert.equal(h.state.inserts.length,0);
});

test('Claude receipt single, batch and confirmed receipt close the obligation without date rewrite',async()=>{
 const fixed=[{id:41,name:'Claude',period:'month',day_of_month:19,active:true,type:'payment'}];
 const one=harness([{...single,description:'Anthropic',date:'2026-10-18'}],{fixed});await one.run();
 assert.equal(one.state.rows[0].fixed_id,41);assert.equal(one.state.rows[0].payment_due_date,'2026-10-19');assert.equal(one.state.rows[0].date,'2026-10-18');
 const many=harness([batch([transaction({description:'Клод'}),transaction({description:'Anthropic',amount:20})])],{fixed});await many.run();
 assert.equal(many.state.rows[0].fixed_id,41);assert.equal(many.state.rows[1].fixed_id,undefined);
 const pending={kind:'receipt',parts:[{path:'u/a.jpg',update_id:42}],items_sum:250,description:'Claude',date:'2026-10-18',account_id:7,expires:'2099-01-01T00:00:00Z'};
 const confirmed=harness([],{fixed,pending});await confirmed.api.confirmPending(1,'u');
 assert.equal(confirmed.state.rows[0]?.fixed_id,41);assert.equal(confirmed.state.rows[0]?.payment_due_date,'2026-10-19');
});

 test('selected source applies to every row despite counterparty bank; exact card beats guessed bank',async()=>{
 const accounts=[{id:1,name:'Source',bank:'privat',card_last4:'0678',kind:'debit',active:true},{id:2,name:'Other',bank:'oschad',card_last4:'7654',kind:'debit',active:true}];
 const rows=Array.from({length:6},(_,i)=>transaction({amount:11+i,description:'Example '+i,bank:'oschad',card_last4:'7654'}));
 const h=harness([{...batch(rows),account_scope:'selected',selected_bank:'privat',selected_card_last4:'0678'}],{accounts});await h.run();assert.equal(h.state.rows.length,6);assert.ok(h.state.rows.every(r=>r.account_id===1));
 const exact=harness([batch([transaction({bank:'oschad',card_last4:'0678'})])],{accounts});await exact.run();assert.equal(exact.state.rows[0]?.account_id,1);
 });
 test('all-accounts screen cannot propagate an arbitrary top-level card',async()=>{
 const h=harness([{...batch([transaction()]),account_scope:'all',bank:'privat',card_last4:'0678'}],{accounts:[{id:1,name:'Source',bank:'privat',card_last4:'0678',kind:'debit',active:true}]});await h.run();assert.equal(h.state.rows[0]?.account_id,null);
 });
test('ambiguous identical suffix remains manual unless source bank distinguishes it',async()=>{
 const accounts=[{id:1,name:'First',bank:'privat',card_last4:'0678',kind:'debit',active:true},{id:2,name:'Second',bank:'mono',card_last4:'0678',kind:'debit',active:true}];
 const ambiguous=harness([batch([transaction({card_last4:'0678'})])],{accounts});await ambiguous.run();assert.equal(ambiguous.state.rows[0]?.account_id,null);
 const unique=harness([batch([transaction({card_last4:'0678',bank:'mono'})])],{accounts});await unique.run();assert.equal(unique.state.rows[0]?.account_id,2);
 const invalid=harness([{...batch([transaction({card_last4:'0678',bank:'privat'})]),account_scope:'selected',selected_card_last4:'678',selected_bank:'privat'}],{accounts});await invalid.run();assert.equal(invalid.state.rows[0]?.account_id,null);
});
test('all-accounts recipient suffix repeated in top-level OCR cannot select the recipient account',async()=>{
 const accounts=[{id:1,name:'Source',bank:'oschad',card_last4:'0678',kind:'debit',active:true},{id:2,name:'Recipient',bank:'privat',card_last4:'1234',kind:'debit',active:true}];
 const h=harness([{...batch([transaction({description:'**1234',bank:'privat',card_last4:'1234'})]),account_scope:'all',bank:'privat',card_last4:'1234'}],{accounts});
 await h.run();assert.equal(h.state.rows[0]?.account_id,null);
});
test('valid cheap batch must be verified; strong group dates are authoritative',async()=>{
 const first=batch([transaction({description:'Example service',date_text:'17 June 2026',date:'2026-06-17'})]);
 const verified=batch([transaction({description:'Example service',date_text:'18.06.2026',date:'2026-06-18'})]);
 // Use fully valid dates in both answers: structural validation alone cannot identify the wrong group.
 first.transactions[0].date_text='17.06.2026';
 const h=harness([first,verified],{today:'2026-06-19'});await h.run();
 assert.equal(h.state.requests.length,2);assert.notEqual(h.state.requests[0].model,h.state.requests[1].model);
 assert.equal(h.state.rows[0]?.date,'2026-06-18');
 await h.run();assert.equal(h.state.requests.length,2);assert.equal(h.state.inserts.length,1);
});
test('failed strong verification never saves an otherwise valid cheap batch or creates pending writes',async()=>{
 for(const strong of [null,{error:'unavailable'},single,{...batch(),complete:false},batch([transaction({amount:-1})])]){
  const h=harness([batch(),strong]);await h.run();
  assert.equal(h.state.requests.length,2);assert.equal(h.state.inserts.length,0);assert.equal(h.state.pending,null);assert.equal(h.state.txReplies.length,0);
 }
});
test('valid ordinary receipt still uses one cheap request',async()=>{
 const h=harness([single]);await h.run();assert.equal(h.state.requests.length,1);assert.equal(h.state.inserts.length,1);
});
