const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(path.join(__dirname,'../supabase/functions/telegram-webhook/index.ts'),'utf8');
const receiptSystem=new Function(source.slice(source.indexOf('const RECEIPT_SYSTEM ='),source.indexOf('const SUPABASE_URL ='))+';return RECEIPT_SYSTEM;')();
const isolated=stripTypeScriptTypes(source.slice(source.indexOf('const tgSourceId ='),source.indexOf('type Pending =')));
const confirmSource=stripTypeScriptTypes(source.slice(source.indexOf('async function confirmPending('),source.indexOf('// Посилання на застосунок під статусом;')));
const transaction=(overrides={})=>({amount:120.5,type:'expense',currency:'UAH',description:'Магазин',date:'2026-10-19',...overrides});
const batch=(transactions=[transaction(),transaction({amount:200,type:'income',description:'Повернення',date:'2026-10-20'})])=>
  ({kind:'transactions',complete:true,readable:'good',transactions});
const single={has_total:true,amount:250,items_sum:250,description:'Чек',date:'2026-10-19',readable:'good'};
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
test('calendar centuries and leap years remain bounded by message date',async()=>{
  const options={today:'2027-02-01',messageDate:Date.parse('2026-10-20T12:00:00Z')/1000};
  for(const [raw,expected] of [['29.02.24','2024-02-29'],['29 лютого','2024-02-29'],['29.02.2000','2000-02-29'],['31.12','2025-12-31'],['1 січня 00','2000-01-01']]){
    const h=harness([{...single,date_text:raw}],options);await h.run();assert.equal(h.state.rows[0]?.date,expected,raw);
  }
  for(const raw of ['29.02.1900','29.02.2025','31.04.2026','01.01.27','2026-10-21','20/10.2026','03/04/05/06','пн 2026-10-20',null,'']){
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
    [{...card,name:'12345678',card_last4:null}],[{...card,name:'1234',card_last4:'bad'}],[{...card,bank:'mono'}]];
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
  const state={rows:[...(options.existing??[])],inserts:[],replies:[],txReplies:[],categories:[],requests:[],accountLoads:[],pending:options.pending??null};
  const sb={
    storage:{from:()=>({upload:async()=>({error:null}),download:async()=>({data:{arrayBuffer:async()=>new Uint8Array([1]).buffer}})})},
    from(table) {
      const q={filters:[],payload:null,mode:'read',one:false};
      q.select=()=>q;
      q.eq=(key,value)=>{q.filters.push([key,value]);return q};
      q.gte=(key,value)=>{q.min=[key,value];return q};
      q.lte=(key,value)=>{q.max=[key,value];return q};
      q.order=()=>q;
      q.range=(lo,hi)=>{q.page=[lo,hi];return q};
      q.is=q.eq;
      q.single=q.maybeSingle=()=>{q.one=true;return q};
      q.insert=payload=>{q.mode='insert';q.payload=payload;return q};
      q.update=payload=>{q.mode='update';q.payload=payload;return q};
      q.then=(resolve,reject)=>Promise.resolve().then(()=>{
        if(table==='profiles'){
          if(q.mode==='update') {state.pending=q.payload.telegram_pending;return {data:[{id:'u'}],error:null};}
          return {data:{telegram_pending:state.pending},error:null};
        }
        if(q.mode==='insert'){
          state.inserts.push(q.payload);
          if(options.insertError)return {data:null,error:options.insertError};
          const rows=(Array.isArray(q.payload)?q.payload:[q.payload]).map((r,i)=>({...r,id:state.rows.length+i+1}));
          if(rows.some(r=>state.rows.some(old=>old.source_id===r.source_id)))return {data:null,error:{code:'23505'}};
          state.rows.push(...rows);
          // PostgreSQL's RETURNING order is not a mapping contract.
          return {data:q.one?rows[0]:[...rows].reverse(),error:null};
        }
        if(q.page && options.lookupError)return {data:null,error:{message:'synthetic'}};
        if(q.page && options.incompletePages)return {data:Array.from({length:1000},(_,id)=>({id,amount:999999,type:'income',date:'2026-10-20'})),error:null};
        let rows=state.rows.filter(r=>q.filters.every(([k,v])=>r[k]===v) &&
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
    if(url.includes('getFile'))return {json:async()=>({ok:true,result:{file_path:'photo.jpg'}})};
    return {ok:true,arrayBuffer:async()=>new Uint8Array([1,2]).buffer};
  };
  const accs=options.accounts??[{id:7,name:'Готівка'}];
  const bindings={sb,fetch,BOT_TOKEN:'test',CLAUDE_API_KEY:'test',RECEIPT_MODEL:'fast',RECEIPT_MODEL_STRONG:'strong',RECEIPT_SYSTEM:receiptSystem,
    todayKyiv:()=> options.today??'2026-10-20',reply:async(...args)=>state.replies.push(args),
    replyTx:async(...args)=>state.txReplies.push(args),categorizeLater:id=>state.categories.push(id),
    activeAccounts:async(includeMono)=>{state.accountLoads.push(includeMono);return accs},
    pickAccount:()=>({matched:true,acc:options.captionAccount??accs[0]}),fmtMoney:String,
    console:{log(){},error(){}}};
  const api=new Function(...Object.keys(bindings),isolated+confirmSource+';return {addReceipt,receiptBatch,recognizeReceipt,receiptDate,confirmPending};')(...Object.values(bindings));
  return {state,api,run:(update=42,caption)=>api.addReceipt(1,'u',update,[{file_id:'photo'}],undefined,caption,options.messageDate)};
}

test('visible date groups use Telegram Kyiv date and inherit selected card header',async()=>{
  const response={...batch([
    transaction({amount:1,date:null,date_text:'сьогодні'}),
    transaction({amount:2,date:null,date_text:'вчора'}),
    transaction({amount:3,date:null,date_text:'пн 19 жовтня'}),
  ]),bank:'privat',card_last4:'0882'};
  const h=harness([response],{today:'2026-10-22',messageDate:Date.parse('2026-10-20T21:30:00Z')/1000,
    accounts:[{id:88,bank:'privat',name:'Картка 0882',card_last4:'0882'},{id:89,bank:'privat',name:'Інша'}]});
  await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.date),['2026-10-21','2026-10-20','2026-10-19']);
  assert.deepEqual(h.state.rows.map(r=>r.account_id),[88,88,88]);
  assert.match(h.state.requests[0].system,/2026-10-21/);
});

test('yearless and relative dates roll back at New Year, preserving full historical dates',async()=>{
  const h=harness([batch([
    transaction({amount:1,date:'вчора'}),transaction({amount:2,date:'31 грудня'}),
    transaction({amount:3,date:'31.12'}),transaction({amount:4,date:'12.01.2025'}),
  ])],{today:'2027-01-03',messageDate:Date.parse('2026-12-31T22:30:00Z')/1000});
  await h.run();
  assert.deepEqual(h.state.rows.map(r=>r.date),['2026-12-31','2026-12-31','2026-12-31','2025-01-12']);
});

test('unresolved date or wrong weekday rejects entire batch despite model ISO guess',async()=>{
  for(const raw of ['вт 19 жовтня','31 лютого','невідомо',null]){
    const h=harness([batch([transaction(),transaction({amount:2,date:raw===null?null:'2026-10-19',date_text:raw})])],
      {messageDate:Date.parse('2026-10-20T12:00:00Z')/1000});
    await h.run();assert.equal(h.state.inserts.length,0,String(raw));
  }
  for(const raw of ['сьогодні','вчора','19 жовтня']){
    const h=harness([{...single,date:raw}]);await h.run();assert.equal(h.state.inserts.length,0,raw);
  }
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

test('explicit empty visible date rejects a model ISO guess for whole batch',async()=>{
  for(const date_text of [null,'','   ']){
    const h=harness([batch([transaction(),transaction({amount:2,date:'2026-10-19',date_text})])],
      {messageDate:Date.parse('2026-10-20T12:00:00Z')/1000});
    await h.run();assert.equal(h.state.inserts.length,0,JSON.stringify(date_text));
  }
});

test('multipart relative date retains first message reference across Kyiv midnight',async()=>{
  const options={today:'2026-10-21',messageDate:Date.parse('2026-10-20T20:59:00Z')/1000};
  const h=harness([{...single,has_total:false,amount:null,date_text:'сьогодні'},{...single,date_text:'сьогодні'}],options);
  await h.run(40);
  options.messageDate=Date.parse('2026-10-20T21:01:00Z')/1000;
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
  assert.equal(h.state.inserts.length,1);assert.equal(h.state.requests.length,1);
});
test('invalid member or incomplete list rejects whole batch without pending writes',async()=>{
  const cases=[
    batch([transaction(),transaction({amount:-1})]),batch([transaction({amount:true})]),
    batch([transaction({currency:'USD'})]),batch([transaction({type:'transfer'})]),
    batch([transaction({date:'2026-02-30'})]),batch([]),
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

test('one missing, invalid, or future screenshot date rejects the whole batch after retry',async()=>{
  for(const date of [null,undefined,'2026-02-30','2026-10-21']){
    const h=harness([batch([transaction(),transaction({date})])]);await h.run();
    assert.equal(h.state.inserts.length,0);
    assert.equal(h.state.requests.length,2);
    assert.match(h.state.replies.at(-1)[1],/дату операції.*Нічого не записано/);
  }
});

test('strong model may recover the screenshot date but missing single date never inserts',async()=>{
  const repaired=harness([{...single,date:null},single]);await repaired.run();
  assert.equal(repaired.state.rows[0].date,'2026-10-19');
  assert.equal(repaired.state.requests.length,2);
  for(const date of [null,undefined,'2026-02-30','2026-10-21']){
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
  assert.equal(h.state.rows.length,2);assert.equal(h.state.pending,pending);
});

const bankAccounts=[
  {id:11,name:'Особиста 0882',bank:'privat',card_last4:'0882'},
  {id:12,name:'Картка для покупок',bank:'mono'},
  {id:13,name:'Для платежів',bank:'oschad'},
];
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
