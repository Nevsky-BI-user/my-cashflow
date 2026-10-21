const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const root=path.join(__dirname,'../supabase/functions');
const source=fs.readFileSync(path.join(root,'telegram-webhook/index.ts'),'utf8');
const kbCode=stripTypeScriptTypes(fs.readFileSync(path.join(root,'_shared/bot-kb.ts'),'utf8').replace(/^export /gm,''));
const kb=new Function(kbCode+';return {KB_BTN,MAIN_KB,ENTRY_KB,ENTRY_INPUT_KB,APP_URL};')();
const fixedCode=stripTypeScriptTypes(fs.readFileSync(path.join(root,'_shared/fixedmatch.ts'),'utf8').replace(/^export /gm,''));
const fixedApi=new Function(fixedCode+';return {fixedCandidates,fixedOccurrence,fixedOccurrenceKey};')();
const code=stripTypeScriptTypes(source.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];\r?\n/gm,''));
const NOW=Date.parse('2026-10-21T10:00:00Z');
class Clock extends Date{constructor(...args){super(...(args.length?args:[NOW]))}static now(){return NOW}}
const entry=(type='income',input='text')=>({kind:'entry',type,input,expires:new Date(NOW+600000).toISOString()});
const receipt=(transactions=[{amount:150,type:'income',currency:'UAH',description:'Переказ',date:'2026-10-20'}])=>({kind:'transactions',complete:true,readable:'good',transactions});
function harness(options={}){
  const state={pending:options.pending??null,rows:[...(options.rows??[])],messages:[],requests:[],reports:[],writes:0};
  let handler;
  const sb={storage:{from:()=>({upload:async()=>({error:options.uploadError?{message:'synthetic'}:null}),download:async()=>({data:{arrayBuffer:async()=>new Uint8Array([1]).buffer}})})},
    from(table){
      const q={filters:[],one:false,mode:'read'};
      for(const name of ['select','order','limit','range','not','or'])q[name]=()=>q;
      q.eq=(k,v)=>{q.filters.push([k,v]);return q};q.is=q.eq;
      q.gte=(k,v)=>{q.min=[k,v];return q};q.lte=(k,v)=>{q.max=[k,v];return q};q.lt=q.lte;
      q.single=q.maybeSingle=()=>{q.one=true;return q};
      q.update=p=>{q.mode='update';q.payload=p;return q};q.insert=p=>{q.mode='insert';q.payload=p;return q};
      q.then=(resolve,reject)=>Promise.resolve().then(()=>{
        if(table==='profiles'){
          if(q.mode==='update'){
            if(options.profileWriteError)return {data:null,error:{message:'synthetic'}};
            if(options.concurrentPending)state.pending=options.concurrentPending;
            const expected=q.filters.find(([k])=>k==='telegram_pending');
            if(expected && JSON.stringify(state.pending)!==JSON.stringify(typeof expected[1]==='string'?JSON.parse(expected[1]):expected[1]))return {data:[],error:null};
            state.pending=q.payload.telegram_pending;state.writes++;return {data:[{id:'u'}],error:null};
          }
          if(options.profileReadError)return {data:null,error:{message:'synthetic'}};
          return {data:options.unlinked?null:{id:'u',telegram_pending:state.pending},error:null};
        }
        if(table==='accounts')return {data:[{id:7,name:'Картка',kind:'debit',bank:'privat',is_salary:true,active:true,card_last4:'1234'}],error:null};
        if(table==='transactions'){
          if(q.mode==='insert'){
            if(options.insertError)return {data:null,error:{message:'synthetic'}};
            const rows=(Array.isArray(q.payload)?q.payload:[q.payload]).map((r,i)=>({...r,id:state.rows.length+i+1}));
            if(rows.some(r=>state.rows.some(old=>r.source_id===old.source_id)))return {data:null,error:{code:'23505'}};
            state.rows.push(...rows);return {data:q.one?rows[0]:rows,error:null};
          }
          const rows=state.rows.filter(r=>q.filters.every(([k,v])=>r[k]===v)&&(!q.min||r[q.min[0]]>=q.min[1])&&(!q.max||r[q.max[0]]<=q.max[1]));
          return {data:q.one?rows[0]??null:rows,error:null};
        }
        return {data:q.one?null:[],error:null};
      }).then(resolve,reject);return q;
    }};
  const fetch=async(url,init)=>{
    if(url.includes('anthropic')){state.requests.push(JSON.parse(init.body));return {ok:!options.ocrError,json:async()=>({stop_reason:'end_turn',content:[{type:'text',text:JSON.stringify(options.ocr??receipt())}]})};}
    if(url.includes('/getFile'))return {json:async()=>({ok:true,result:{file_path:'photo.jpg'}})};
    if(url.includes('/file/'))return {ok:true,arrayBuffer:async()=>new Uint8Array([1]).buffer};
    if(url.includes('/sendMessage'))state.messages.push(JSON.parse(init.body));
    return {ok:true,json:async()=>({ok:true})};
  };
  const bindings={...kb,...fixedApi,createClient:()=>sb,fetch,Date:Clock,Deno:{env:{get:n=>n==='TELEGRAM_ALLOWED_IDS'?'1':'test'},serve:fn=>{handler=fn}},
    creditPaid:()=>[],matchCredit:()=>null,__track:(name)=>state.reports.push(name),console:{log(){},error(){}},
    formatWeek:()=>'',weekModel:()=>({}),formatMonth:()=>'',monthModel:()=>({})};
  new Function(...Object.keys(bindings),code+`;balance=async()=>{__track('balance')};last=async()=>{__track('last')};withFinance=async()=>{__track('finance')};`)(...Object.values(bindings));
  let next=1;
  const send=async(text,extra={})=>{
    const update={update_id:extra.update_id??next++,message:{chat:{id:1,type:'private'},from:{id:1},date:NOW/1000,...(text?{text}:{}),...extra}};
    return handler(new Request('https://local/webhook',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':extra.secret??'test'},body:JSON.stringify(update)}));
  };
  return {state,send,photo:(extra={})=>send(null,{photo:[{file_id:'photo'}],...extra}),options};
}

test('income and expense buttons guide text entry and preserve legacy direct commands',async()=>{
  for(const type of ['income','expense']){
    const h=harness();await h.send(kb.KB_BTN[type]);assert.equal(h.state.pending.input,'choose');
    await h.send(kb.KB_BTN.text);assert.equal(h.state.pending.input,'text');
    await h.send('150 кава');assert.equal(h.state.rows[0].type,type);assert.equal(h.state.pending,null);
  }
  for(const [text,type] of [['+150 подарунок','income'],['150 кава','expense'],['/income 150 подарунок','income'],['/дохід 150 подарунок','income'],['/expense 150 кава','expense']]){
    const h=harness();await h.send(text);assert.equal(h.state.rows[0]?.type,type,text);
  }
});
test('wrong method, contradictory sign and /yes cannot write an entry',async()=>{
  for(const text of ['-150 помилка','/yes','не число']){
    const h=harness({pending:entry()});await h.send(text);assert.equal(h.state.rows.length,0);assert.equal(h.state.pending.kind,'entry');
    assert.ok(h.state.messages.at(-1).reply_markup.keyboard);
  }
  const h=harness({pending:entry()});await h.photo();await h.send(null,{document:{file_id:'x'}});
  assert.equal(h.state.rows.length,0);assert.equal(h.state.requests.length,0);
});

test('wizard accepts grouped thousands and decimals without truncating the amount',async()=>{
  for(const [text,amount] of [['1 500 зарплата',1500],['12 345,67 зарплата',12345.67],['1\u00a0500 зарплата',1500],['1\u202f500.50 зарплата',1500.5],['+1 234 567,89 зарплата',1234567.89],['1500 зарплата',1500]]){
    const h=harness({pending:entry()});await h.send(text);
    assert.equal(h.state.rows[0]?.amount,amount,text);assert.equal(h.state.rows[0]?.description,'зарплата');assert.equal(h.state.pending,null);
  }
  for(const text of ['1 50 зарплата','12 34,67 зарплата','1234 567 зарплата','1 500 50 зарплата','1  500 зарплата','1 234,567 зарплата','-1 500 зарплата']){
    const h=harness({pending:entry()});await h.send(text);
    assert.equal(h.state.rows.length,0,text);assert.equal(h.state.pending.kind,'entry');
  }
});
test('image income requires all valid income rows and keeps mode after rejection',async()=>{
  const h=harness();await h.send(kb.KB_BTN.income);await h.send(kb.KB_BTN.image);await h.photo();
  assert.equal(h.state.rows[0]?.type,'income');assert.equal(h.state.pending,null);
  for(const ocr of [receipt([{amount:10,type:'expense',currency:'UAH',description:'Кава',date:'2026-10-20'}]),
    receipt([{amount:10,type:'income',currency:'UAH',description:'Переказ',date:null}]),
    {...receipt(),transactions:[...receipt().transactions,{amount:20,type:'expense',currency:'UAH',description:'Кава',date:'2026-10-20'}]},
    {has_total:true,amount:150,items_sum:150,date:'2026-10-20',readable:'good'}]){
    const bad=harness({pending:entry('income','image'),ocr});await bad.photo();
    assert.equal(bad.state.rows.length,0);assert.equal(bad.state.pending.input,'image');assert.deepEqual(bad.state.messages.at(-1).reply_markup,kb.ENTRY_INPUT_KB);
  }
});
test('storage state and insert failures retain wizard, expired or malformed entries never become expenses',async()=>{
  for(const option of ['profileReadError','profileWriteError','insertError']){
    const h=harness({[option]:true,pending:entry()});await h.send('150 кава');
    if(option!=='profileWriteError')assert.equal(h.state.rows.length,0);
    assert.equal(h.state.pending.kind,'entry');
  }
  for(const pending of [{...entry(),expires:'2000-01-01'}, {...entry(),type:'wrong'}, {...entry(),expires:'nonsense'}]){
    const h=harness({pending});await h.send('150 кава');assert.equal(h.state.rows.length,0);assert.equal(h.state.pending,null);
  }
});
test('menu, help and app leave no hidden entry; cancel failure cannot claim success',async()=>{
  for(const text of [kb.KB_BTN.menu,'/menu','меню','/start',kb.KB_BTN.help,kb.KB_BTN.app]){
    const h=harness({pending:entry()});await h.send(text);assert.equal(h.state.pending,null);assert.equal(h.state.rows.length,0);
  }
  const h=harness({pending:entry(),profileWriteError:true});await h.send(kb.KB_BTN.cancel);
  assert.ok(h.state.pending);assert.match(h.state.messages.at(-1).text,/Не вдалося/);
});
test('occupied financial pending cannot be overwritten and confirmation survives navigation',async()=>{
  const pending={amount:150,type:'income',description:'Дохід',date:'2026-10-21',source_id:'tg:99',expires:new Date(NOW+600000).toISOString()};
  for(const text of [kb.KB_BTN.income,kb.KB_BTN.expense,'+150 нове','/menu']){
    const h=harness({pending});await h.send(text);assert.deepEqual(h.state.pending,pending);assert.equal(h.state.rows.length,0);
  }
  const h=harness({pending});await h.photo();assert.deepEqual(h.state.pending,pending);assert.equal(h.state.requests.length,0);
});
test('Monobank matching income becomes confirmation and replay does not insert twice',async()=>{
  const h=harness({pending:entry(),rows:[{id:1,source:'mono',amount:150,type:'income',date:'2026-10-21'}]});
  await h.send('150 подарунок');assert.equal(h.state.pending.type,'income');assert.notEqual(h.state.pending.kind,'entry');assert.equal(h.state.rows.length,1);
  await h.send(kb.KB_BTN.yes);assert.equal(h.state.rows.length,2);assert.equal(h.state.pending,null);
  const replay=harness();await replay.send('+150 подарунок',{update_id:10});await replay.send('+150 подарунок',{update_id:10});assert.equal(replay.state.rows.length,1);
});
test('unauthorized messages perform no financial action',async()=>{
  const h=harness({unlinked:true});await h.send('+150 x',{from:{id:2},chat:{id:2,type:'private'}});
  await h.send('+150 x',{secret:'wrong'});assert.equal(h.state.rows.length,0);assert.equal(h.state.writes,0);
});

test('all navigation buttons preserve confirmations but clear entry and app uses an ordinary URL',async()=>{
  for(const key of ['balance','chart','budget','week','month','last','help','app','menu']){
    const h=harness({pending:entry()});await h.send(kb.KB_BTN[key]);
    assert.equal(h.state.pending,null,key);assert.equal(h.state.rows.length,0,key);
    if(key==='app')assert.equal(h.state.messages.at(-1).reply_markup.inline_keyboard[0][0].url,kb.APP_URL);
  }
  for(const cancel of [kb.KB_BTN.cancel,'/no','/cancel']){
    const h=harness({pending:entry()});await h.send(cancel);assert.equal(h.state.pending,null);
  }
  const start=harness();await start.send('/start');assert.deepEqual(start.state.messages.at(-1).reply_markup,kb.MAIN_KB);
});
test('expense images allow complete retail receipts and reject income without coercion',async()=>{
  const h=harness({pending:entry('expense','image'),ocr:{has_total:true,amount:50,items_sum:50,date:'2026-10-20',readable:'good'}});
  await h.photo();assert.equal(h.state.rows[0]?.type,'expense');assert.equal(h.state.pending,null);
  for(const ocr of [receipt(),{has_total:false,amount:null,items_sum:50,date:'2026-10-20',readable:'good'}]){
    const bad=harness({pending:entry('expense','image'),ocr});await bad.photo();assert.equal(bad.state.rows.length,0);assert.equal(bad.state.pending.kind,'entry');
  }
});
test('OCR, storage and insert failures keep image mode with retry keyboard',async()=>{
  for(const option of ['ocrError','uploadError','insertError']){
    const h=harness({pending:entry('income','image'),[option]:true});await h.photo();
    assert.equal(h.state.rows.length,0);assert.equal(h.state.pending.input,'image');assert.deepEqual(h.state.messages.at(-1).reply_markup,kb.ENTRY_INPUT_KB);
  }
});
test('partial receipt CAS collision cannot overwrite a newer income confirmation',async()=>{
  const other={amount:5,type:'income',source_id:'tg:123',expires:new Date(NOW+600000).toISOString()};
  const h=harness({concurrentPending:other,ocr:{has_total:false,amount:null,items_sum:50,date:'2026-10-20',readable:'good'}});
  await h.photo();assert.deepEqual(h.state.pending,other);assert.equal(h.state.rows.length,0);
});
test('receipt continuation keeps confirmation buttons and supports confirmation without typed commands',async()=>{
  const options={ocr:{has_total:false,amount:null,items_sum:50,date:'2026-10-20',readable:'good'}};
  const h=harness(options);await h.photo();assert.equal(h.state.pending.kind,'receipt');
  assert.ok(h.state.messages.at(-1).reply_markup.keyboard.flat().some(b=>b.text===kb.KB_BTN.yes));
  await h.send(kb.KB_BTN.yes);assert.equal(h.state.rows.length,1);assert.equal(h.state.pending,null);
});
test('duplicate image update does not call OCR again or add another row',async()=>{
  const h=harness({pending:entry('income','image')});await h.photo({update_id:99});await h.photo({update_id:99});
  assert.equal(h.state.rows.length,1);assert.equal(h.state.requests.length,1);
});
