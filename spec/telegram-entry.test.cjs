const {test,before}=require('node:test');
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
let todayReports;
before(async()=>{todayReports=await import(require('node:url').pathToFileURL(path.join(root,'_shared/bot-reports.ts')).href)});
const code=stripTypeScriptTypes(source.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];\r?\n/gm,''));
const NOW=Date.parse('2026-10-21T10:00:00Z');
class Clock extends Date{constructor(...args){super(...(args.length?args:[NOW]))}static now(){return NOW}}
const entry=(type='income',input='text')=>({kind:'entry',type,input,expires:new Date(NOW+600000).toISOString()});
const receipt=(transactions=[{amount:150,type:'income',currency:'UAH',description:'Переказ',date:'2026-10-20'}])=>({kind:'transactions',complete:true,readable:'good',transactions});
function harness(options={}){
  const state={pending:options.pending??null,rows:[...(options.rows??[])],messages:[],photos:[],requests:[],reports:[],events:[],reportEvents:[],delays:[],writes:0,edits:[]};
  let handler;
  let reportResponse=0;
  const sb={storage:{from:()=>({upload:async()=>({error:options.uploadError?{message:'synthetic'}:null}),download:async()=>({data:{arrayBuffer:async()=>new Uint8Array([1]).buffer}})})},
    from(table){
      const q={filters:[],one:false,mode:'read'};
      for(const name of ['select','order','limit','range','not','or'])q[name]=()=>q;
      q.eq=(k,v)=>{q.filters.push([k,v]);return q};q.is=q.eq;
      q.in=(k,vs)=>{(q.ins??=[]).push([k,vs]);return q};
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
        if(table==='categories')return {data:options.refundCategories??[],error:null};
        if(table==='accounts')return {data:options.accounts??[{id:7,name:'Картка',kind:'debit',bank:'privat',is_salary:true,active:true,card_last4:'1234'}],error:null};
        if(table==='transactions'){
          if(q.mode==='update' && q.payload.category_id != null && options.concurrentManualCategory){
            const current=state.rows.find(r=>q.filters.some(([k,v])=>k==='id'&&r.id===v));
            if(current){current.category_id=999;current.auto_categorized=false;}
          }
          if(q.mode==='insert'){
            if(options.insertError)return {data:null,error:{message:'synthetic'}};
            const rows=(Array.isArray(q.payload)?q.payload:[q.payload]).map((r,i)=>({...r,id:state.rows.length+i+1}));
            if(rows.some(r=>state.rows.some(old=>r.source_id===old.source_id)))return {data:null,error:{code:'23505'}};
            state.rows.push(...rows);state.events.push('insert');return {data:q.one?rows[0]:rows,error:null};
          }
          const rows=state.rows.filter(r=>q.filters.every(([k,v])=>v==null?r[k]==null:r[k]===v)&&(!q.ins||q.ins.every(([k,vs])=>vs.includes(r[k])))&&(!q.min||r[q.min[0]]>=q.min[1])&&(!q.max||r[q.max[0]]<=q.max[1]));
          if(q.mode==='update'){
            if(q.payload.category_id != null && options.refundUpdateError)return {data:null,error:{message:'synthetic'}};
            for(const row of rows)Object.assign(row,q.payload);
          }
          return {data:q.one?rows[0]??null:rows,error:null};
        }
        return {data:q.one?null:[],error:null};
      }).then(resolve,reject);return q;
    }};
  const fetch=async(url,init)=>{
    if(url.includes('anthropic')){state.requests.push(JSON.parse(init.body));return {ok:!options.ocrError,json:async()=>({stop_reason:'end_turn',content:[{type:'text',text:JSON.stringify(options.ocr??receipt())}]})};}
    if(url.includes('/getFile'))return {json:async()=>({ok:true,result:{file_path:'photo.jpg'}})};
    if(url.includes('/file/'))return {ok:true,arrayBuffer:async()=>new Uint8Array(options.imageBytes??[1]).buffer};
    if(url.includes('/sendMessage')){
      const message=JSON.parse(init.body);state.messages.push(message);
      if(message.text.startsWith('🧾')||message.text.startsWith('⚠️ Звіт')){
        state.reportEvents.push(message.text);
        const response=options.reportResponses?.[reportResponse++]??{status:200,body:{ok:true}};
        if(response.network)throw new Error('synthetic transport failure');
        return {ok:response.status>=200&&response.status<300,status:response.status,json:async()=>response.body};
      }
      if(message.text.startsWith('⚠️')){
        state.events.push('warning');
        if(options.warningError==='network')throw new Error('synthetic');
        return {ok:options.warningError!=='http',json:async()=>({ok:options.warningError!=='api'})};
      }
    }
    if(url.includes('/sendPhoto'))state.photos.push(init.body);
    if(url.includes('/editMessageText'))state.edits.push(JSON.parse(init.body));
    return {ok:true,json:async()=>({ok:true})};
  };
  const bindings={salaryOptions:async()=>({choices:[]}),...kb,...fixedApi,createClient:()=>sb,fetch,Date:Clock,Deno:{env:{get:n=>n==='TELEGRAM_ALLOWED_IDS'?'1':'test'},serve:fn=>{handler=fn}},
    creditPaid:()=>[],matchCredit:()=>null,parsePaidCallback:todayReports.parsePaidCallback,__track:(name)=>state.reports.push(name),console:{log(){},error(){}},
    todayExpensesModel:todayReports.todayExpensesModel,formatTodayExpenses:m=>options.todayPages??todayReports.formatTodayExpenses(m),
    setTimeout:(fn,ms)=>{state.delays.push(ms);state.reportEvents.push('pause:'+ms);fn();return 0},
    __finance:()=>({projection:{},today:options.reportToday??'2026-10-21',txs:state.rows,cats:options.categories??[],accounts:options.accounts??[]}),
    formatWeek:()=>'',weekModel:()=>({}),formatMonth:()=>'',monthModel:()=>({})};
  // Підставляємо лише фінансовий вміст: реальні reply/sendPhoto формують Telegram payload.
  new Function(...Object.keys(bindings),code+`;balance=async(chat)=>reply(chat,'Баланс');last=async(chat)=>reply(chat,'Останні');chartReport=async(chat)=>sendPhoto(chat,new Uint8Array([1]),'Графік','chart.png');budgetReport=async(chat)=>sendPhoto(chat,new Uint8Array([1]),'Бюджет','budget.png');withFinance=async(chat,fn)=>{__track('finance');await fn(chat,__finance())};`)(...Object.values(bindings));
  let next=1;
  const send=async(text,extra={})=>{
    const update={update_id:extra.update_id??next++,message:{chat:{id:1,type:'private'},from:{id:1},date:NOW/1000,...(text?{text}:{}),...extra}};
    return handler(new Request('https://local/webhook',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':extra.secret??'test'},body:JSON.stringify(update)}));
  };
  const callback=async(data)=>handler(new Request('https://local/webhook',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'test'},
    body:JSON.stringify({update_id:next++,callback_query:{id:'callback',from:{id:1},data,message:{message_id:1,chat:{id:1,type:'private'}}}})}));
  return {state,send,photo:(extra={})=>send(null,{photo:[{file_id:'photo'}],...extra}),callback,options};
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
test('image income uses today for missing dates and keeps mode after invalid dates, direction or retail receipts',async()=>{
  const h=harness();await h.send(kb.KB_BTN.income);await h.send(kb.KB_BTN.image);await h.photo();
  assert.equal(h.state.rows[0]?.type,'income');assert.equal(h.state.pending,null);
  const undated=harness({pending:entry('income','image'),ocr:receipt([{amount:10,type:'income',currency:'UAH',description:'Переказ',date:null}])});
  await undated.photo();assert.equal(undated.state.rows[0]?.type,'income');
  assert.equal(undated.state.rows[0]?.date,'2026-10-21');assert.equal(undated.state.pending,null);
  for(const ocr of [receipt([{amount:10,type:'income',currency:'UAH',description:'Переказ',date:'2026-02-30'}]),
    receipt([{amount:10,type:'income',currency:'UAH',description:'Переказ',date:'2026-10-22'}]),
    receipt([{amount:10,type:null,currency:'UAH',description:'Переказ',date:'2026-10-20'}]),
    {has_total:true,amount:150,items_sum:150,date:'2026-10-20',readable:'good'}]){
    const bad=harness({pending:entry('income','image'),ocr});await bad.photo();
    assert.equal(bad.state.rows.length,0);
    if(ocr.transactions?.[0]?.type==='income')assert.equal(bad.state.pending.kind,'receipt_date');
    else assert.equal(bad.state.pending.input,'image');
    assert.deepEqual(bad.state.messages.at(-1).reply_markup,kb.ENTRY_INPUT_KB);
  }
});

test('unreadable receipt date is asked only after automatic reread and resumed through webhook',async()=>{
  const ocr=receipt([{amount:321.45,type:'expense',currency:'UAH',description:'Тестова покупка',date_text:'нерозбірливо',bank:'oschad',time:'09:39'}]);
  const h=harness({ocr,accounts:[{id:13,name:'Ощадбанк',kind:'debit',bank:'oschad',active:true}]});
  await h.photo({update_id:80});assert.equal(h.state.requests.length,2);assert.equal(h.state.rows.length,0);assert.equal(h.state.pending.kind,'receipt_date');
  for(const invalid of ['/yes','31.02.2026','22.10.2026','не дата']){
    await h.send(invalid);assert.equal(h.state.rows.length,0);assert.equal(h.state.pending.kind,'receipt_date');
  }
  await h.send('20.10.2026');assert.equal(h.state.rows.length,1);assert.equal(h.state.pending,null);
  assert.equal(h.state.rows[0].date,'2026-10-20');assert.equal(h.state.rows[0].account_id,13);assert.equal(h.state.rows[0].source_id,'tg:80');
  assert.equal(h.state.requests.length,2);
  await h.photo({update_id:80});assert.equal(h.state.rows.length,1);assert.equal(h.state.requests.length,2);
});

test('date fallback cancellation, expiry and concurrent state preserve no-write behavior',async()=>{
  const ocr=receipt([{amount:10,type:'income',currency:'UAH',description:'Тестове надходження',date_text:'нерозбірливо'}]);
  const canceled=harness({ocr});await canceled.photo();await canceled.send('/no');
  assert.equal(canceled.state.pending,null);assert.equal(canceled.state.rows.length,0);
  const expired=harness({ocr});await expired.photo();expired.state.pending.expires='2000-01-01T00:00:00Z';await expired.send('20.10.2026');
  assert.equal(expired.state.pending,null);assert.equal(expired.state.rows.length,0);assert.match(expired.state.messages.at(-1).text,/Час уточнення минув/);
  const concurrent=harness({ocr});await concurrent.photo();concurrent.options.concurrentPending=entry('income','text');await concurrent.send('20.10.2026');
  assert.equal(concurrent.state.pending.kind,'entry');assert.equal(concurrent.state.rows.length,0);
});

test('date clarification inside income wizard preserves intended type and clears pending after saving',async()=>{
  const h=harness({pending:entry('income','image'),ocr:receipt([{amount:10,type:'income',currency:'UAH',description:'Тестове надходження',date_text:'нерозбірливо'}])});
  await h.photo();assert.equal(h.state.pending.kind,'receipt_date');assert.equal(h.state.rows.length,0);
  await h.send('2026-10-20');assert.equal(h.state.rows[0]?.type,'income');assert.equal(h.state.pending,null);
});

test('transient insert failure after date clarification can retry without rereading or rewriting dates',async()=>{
  for(const ocr of [receipt([{amount:10,type:'income',currency:'UAH',description:'Тестове надходження',date_text:'нерозбірливо'}]),
    {has_total:true,amount:10,items_sum:10,description:'Тестовий чек',date_text:'нерозбірливо',readable:'good'}]){
    const h=harness({ocr});await h.photo({update_id:80});h.options.insertError=true;await h.send('19.10.2026');
    assert.equal(h.state.rows.length,0);assert.equal(h.state.pending.kind,'receipt_date');
    h.options.insertError=false;await h.send('20.10.2026');
    assert.equal(h.state.rows[0]?.date,'2026-10-19');assert.equal(h.state.rows[0]?.source_id,'tg:80');assert.equal(h.state.pending,null);assert.equal(h.state.requests.length,2);
  }
});

test('positive screenshot refund is saved as income in Return category and shown with refund label',async()=>{
  const expense={id:900,type:'expense',amount:321.45,date:'2026-10-18',description:'Тестова покупка',account_id:13};
  const h=harness({rows:[expense],accounts:[{id:13,name:'Ощадбанк',kind:'debit',bank:'oschad',active:true}],
    refundCategories:[{id:104,name:'Повернення',is_income:true,user_id:'u'}],
    ocr:receipt([{amount:321.45,type:'income',currency:'UAH',description:'Тестова покупка',date:'2026-10-19',bank:'oschad'}])});
  await h.photo();const row=h.state.rows.at(-1);
  assert.equal(row.type,'income');assert.equal(row.category_id,104);assert.equal(row.auto_categorized,true);
  assert.equal(row.description,'Повернення: Тестова покупка');assert.deepEqual(h.state.rows[0],expense);
  assert.ok(h.state.messages.some(m=>m.text.startsWith('✅ Повернення: ')&&m.text.includes('Тестова покупка')));
  assert.ok(!h.state.messages.some(m=>m.text.includes('Повернення: Тестова покупка')));
  assert.equal(h.state.pending,null);
});

test('manual account selection classifies unresolved screenshot refund and respects manual category or concurrent edits',async()=>{
  for(const mode of ['uncategorized','auto','manual','concurrent','failure','text','canonical']){
    const h=harness({rows:[{id:900,type:'expense',amount:321.45,date:'2026-10-18',description:'Тестова покупка',account_id:13}],
      accounts:[{id:13,name:'Ощадбанк',kind:'debit',bank:'oschad',active:true}],
      refundCategories:[{id:104,name:'Повернення',is_income:true,user_id:'u'}],
      ocr:receipt([{amount:321.45,type:'income',currency:'UAH',description:'Тестова покупка',date:'2026-10-19',bank:null}])});
    await h.photo();const row=h.state.rows.at(-1);assert.equal(row.account_id,null);assert.equal(row.category_id,undefined);
    if(mode==='auto'||mode==='manual'){row.category_id=500;row.auto_categorized=mode==='auto';}
    if(mode==='concurrent')h.options.concurrentManualCategory=true;
    if(mode==='failure')h.options.refundUpdateError=true;
    if(mode==='text')row.receipt_url=null;
    if(mode==='canonical'){row.description='Повернення: Тестова покупка';row.category_id=104;row.auto_categorized=true;}
    await h.callback(`acc:${row.id}:13`);
    assert.equal(row.account_id,13,mode);assert.equal(row.type,'income');assert.equal(h.state.rows[0].type,'expense');
    if(['uncategorized','auto','canonical'].includes(mode)){
      assert.equal(row.category_id,104,mode);assert.equal(row.description,'Повернення: Тестова покупка');assert.match(h.state.edits.at(-1)?.text,/^✅ Повернення:/);
    }else{
      assert.equal(row.category_id,mode==='manual'?500:mode==='concurrent'?999:undefined,mode);
      assert.equal(row.description,'Тестова покупка',mode);assert.match(h.state.edits.at(-1)?.text,/^✅ Дохід:/);
    }
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
  for(const key of ['balance','chart','budget','week','month','today','last','help','app','menu']){
    const h=harness({pending:entry()});await h.send(kb.KB_BTN[key]);
    assert.equal(h.state.pending,null,key);assert.equal(h.state.rows.length,0,key);
    if(key==='app')assert.equal(h.state.messages.at(-1).reply_markup.inline_keyboard[0][0].url,kb.APP_URL);
  }
  for(const cancel of [kb.KB_BTN.cancel,'/no','/cancel']){
    const h=harness({pending:entry()});await h.send(cancel);assert.equal(h.state.pending,null);
  }
  const start=harness();await start.send('/start');assert.deepEqual(start.state.messages.at(-1).reply_markup,kb.MAIN_KB);
});

test('today button and command show the finance day expenses and refresh the keyboard without writes',async()=>{
 for(const text of [kb.KB_BTN.today,'/today']){
  const rows=[{id:1,type:'expense',amount:1.25,date:'2026-11-01',description:'<Покупка>&'},
   {id:2,type:'expense',amount:10,date:'2026-10-31',description:'Вчора'},
   {id:3,type:'income',amount:100,date:'2026-11-01',description:'Дохід'},
   {id:4,type:'expense',amount:50,date:'2026-11-01',transfer_id:'pair',description:'Переказ'}];
  const h=harness({pending:entry('expense','image'),rows,reportToday:'2026-11-01'});await h.send(text);
  assert.equal(h.state.pending,null);assert.deepEqual(h.state.rows,rows);assert.deepEqual(h.state.reports,['finance']);
  const report=h.state.messages.find(m=>m.text.startsWith('🧾 Витрати за сьогодні'));
  assert.ok(report);assert.match(report.text,/01\.11\.2026/);assert.match(report.text,/1,25 ₴/);assert.match(report.text,/Операцій: 1/);
  assert.match(report.text,/&lt;Покупка&gt;&amp;/);assert.ok(!report.text.includes('Вчора')&&!report.text.includes('Переказ'));
  assert.equal(report.parse_mode,'HTML');assert.deepEqual(report.reply_markup,kb.MAIN_KB);
  assert.ok(!report.reply_markup.keyboard.flat().some(b=>b.text===kb.KB_BTN.month));
 }
});

test('today report preserves a financial confirmation and cannot record a new transaction',async()=>{
 const pending={amount:150,type:'income',description:'Дохід',date:'2026-10-21',source_id:'tg:99',expires:new Date(NOW+600000).toISOString()};
 for(const text of [kb.KB_BTN.today,'/today']){
  const h=harness({pending});await h.send(text);assert.deepEqual(h.state.pending,pending);
  assert.equal(h.state.rows.length,0);assert.equal(h.state.writes,0);assert.deepEqual(h.state.reports,['finance']);
  assert.match(h.state.messages.at(-1).text,/Сьогодні витрат ще немає/);
  assert.deepEqual(h.state.messages.at(-1).reply_markup.keyboard,[[{text:kb.KB_BTN.yes},{text:'Ні, не додавати'}]]);
  await h.send(kb.KB_BTN.yes);assert.equal(h.state.rows.length,1);assert.equal(h.state.pending,null);
 }
});

test('today report paces pages and retries a rate-limited page before advancing',async()=>{
 const pages=['🧾 Перша сторінка','🧾 Друга сторінка','🧾 Третя сторінка'];
 const ok={status:200,body:{ok:true}};
 const limited={status:429,body:{ok:false,error_code:429,parameters:{retry_after:2}}};
 const h=harness({todayPages:pages,reportResponses:[ok,limited,ok,ok]});await h.send('/today');
 assert.deepEqual(h.state.reportEvents,[pages[0],'pause:1000',pages[1],'pause:2000',pages[1],'pause:1000',pages[2]]);
 assert.deepEqual(h.state.delays,[1000,2000,1000]);assert.equal(h.state.writes,0);
 const single=harness({todayPages:[pages[0]]});await single.send('/today');
 assert.deepEqual(single.state.delays,[]);assert.deepEqual(single.state.reportEvents,[pages[0]]);
});

test('today report aborts after permanent or exhausted delivery failure and explains incomplete output',async()=>{
 const pages=['🧾 Перша сторінка','🧾 Друга сторінка','🧾 Третя сторінка'];
 const ok={status:200,body:{ok:true}},limited={status:429,body:{ok:false,error_code:429,parameters:{retry_after:1}}};
 for(const failures of [[{status:200,body:{ok:false,error_code:400}}],[{status:500,body:{ok:false}}],[{network:true}],
   [{status:429,body:{ok:false,parameters:{retry_after:11}}}],[limited,limited]]){
  const h=harness({todayPages:pages,reportResponses:[ok,...failures]});await h.send(kb.KB_BTN.today);
  assert.ok(!h.state.messages.some(m=>m.text===pages[2]));assert.equal(h.state.writes,0);
  const error=h.state.messages.at(-1);assert.match(error.text,/Звіт про витрати надіслано не повністю/);
  assert.deepEqual(error.reply_markup,kb.MAIN_KB);assert.ok(h.state.delays.every(ms=>ms>=1000&&ms<=10000));
  assert.equal(h.state.messages.filter(m=>m.text===pages[1]).length,failures.length);
 }
});

test('today delivery bounds page count and rejects oversized messages without silent truncation',async()=>{
 const pages=Array.from({length:60},(_,i)=>'🧾 Сторінка '+i);
 const h=harness({todayPages:pages});await h.send('/today');
 assert.equal(h.state.messages.filter(m=>m.text.startsWith('🧾')).length,50);
 assert.match(h.state.messages.at(-1).text,/не повністю/);assert.equal(h.state.writes,0);
 const invalid=harness({todayPages:['🧾 Нормальна','🧾'+'x'.repeat(4096),'🧾 Не надсилати']});await invalid.send('/today');
 assert.equal(invalid.state.messages.filter(m=>m.text.startsWith('🧾')).length,1);
 assert.match(invalid.state.messages.at(-1).text,/не повністю/);
});
test('expense images allow complete retail receipts and reject missing totals',async()=>{
  const h=harness({pending:entry('expense','image'),ocr:{has_total:true,amount:50,items_sum:50,date:'2026-10-20',readable:'good'}});
  await h.photo();assert.equal(h.state.rows[0]?.type,'expense');assert.equal(h.state.pending,null);
  for(const ocr of [{has_total:false,amount:null,items_sum:50,date:'2026-10-20',readable:'good'}]){
    const bad=harness({pending:entry('expense','image'),ocr});await bad.photo();assert.equal(bad.state.rows.length,0);assert.equal(bad.state.pending.kind,'entry');
  }
});

test('both image entry modes preserve visible directions in mixed and opposite-type bank screenshots',async()=>{
  const income=receipt().transactions[0];
  const expense={amount:20,type:'expense',currency:'UAH',description:'Кава',date:'2026-10-20'};
  for(const type of ['income','expense']){
    for(const transactions of [[income,expense],type==='income'?[expense]:[income]]){
      const h=harness({pending:entry(type,'image'),ocr:receipt(transactions)});await h.photo();
      assert.deepEqual(h.state.rows.map(r=>r.type),transactions.map(t=>t.type));
      assert.equal(h.state.pending,null);assert.deepEqual(h.state.events,['warning','insert']);
      const warning=h.state.messages.find(m=>m.text.startsWith('⚠️')).text;
      assert.match(warning,/Доходів: \d\. Витрат: \d/);
      assert.match(warning,transactions.length===2?/На скриншоті є доходи й витрати/:/Тип операцій визначено за зображенням/);
    }
  }
});

test('type and clipping warning is combined and failed delivery keeps image entry without inserts',async()=>{
  const ocr={...receipt(),omitted:[{reason:'clipped',description:'Обрізаний рядок'}]};
  const h=harness({pending:entry('expense','image'),ocr});await h.photo();
  const warnings=h.state.messages.filter(m=>m.text.startsWith('⚠️'));
  assert.equal(warnings.length,1);assert.match(warnings[0].text,/Обрізаних операцій пропущено: 1/);
  assert.match(warnings[0].text,/Доходів: 1\. Витрат: 0/);assert.deepEqual(h.state.events,['warning','insert']);
  for(const warningError of ['network','http','api']){
    const bad=harness({pending:entry('expense','image'),ocr,warningError});await bad.photo();
    assert.equal(bad.state.rows.length,0);assert.equal(bad.state.pending.input,'image');
    assert.deepEqual(bad.state.events,['warning']);
    assert.match(bad.state.messages.at(-1).text,/Нічого не записано/);
  }
});

test('image entry hint describes automatic row directions without a single-type restriction',async()=>{
  for(const type of ['income','expense']){
    const h=harness();await h.send(kb.KB_BTN[type]);await h.send(kb.KB_BTN.image);
    assert.match(h.state.messages.at(-1).text,/доходи й витрати визначу окремо за знаком/);
    assert.doesNotMatch(h.state.messages.at(-1).text,/лише доходи|лише витрати/);
  }
});

test('PNG and JPEG documents use the photo OCR path in direct and guided image entry',async()=>{
  for(const [mime_type,imageBytes] of [['image/png',[137,80,78,71,13,10,26,10]],['image/jpeg',[255,216,255,224]]]){
    for(const pending of [null,entry('income','image')]){
      const h=harness({pending,imageBytes});
      await h.send(null,{document:{file_id:'image-document',mime_type,file_size:1024}});
      assert.equal(h.state.rows.length,1);assert.equal(h.state.pending,null);
      assert.equal(h.state.requests[0].messages[0].content[0].source.media_type,mime_type);
    }
  }
});

test('unrelated documents and invalid or oversized image files never call OCR or change pending state',async()=>{
  for(const document of [{file_id:'pdf',mime_type:'application/pdf',file_size:1024},
    {file_id:'image',mime_type:'image/png',file_size:20*1024*1024+1},
    {file_id:'image',mime_type:'image/jpeg'},{file_id:'image',mime_type:'image/png',file_size:-1}]){
    const pending=entry('income','image');const h=harness({pending});await h.send(null,{document});
    assert.equal(h.state.rows.length,0);assert.equal(h.state.requests.length,0);assert.deepEqual(h.state.pending,pending);
    if(document.mime_type==='application/pdf')assert.equal(h.state.messages.length,0);
    else assert.match(h.state.messages.at(-1).text,/до 20 МБ/);
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
  const h=harness({pending:entry('income','image')});await h.photo({update_id:99});
  const initialRequests=h.state.requests.length;assert.equal(initialRequests,2);
  await h.photo({update_id:99});
  assert.equal(h.state.rows.length,1);assert.equal(h.state.requests.length,initialRequests);
});

const accounts=[{id:7,name:'Основна',kind:'debit',bank:'privat',is_salary:true,active:true,card_last4:'1234'},
  {id:8,name:'Резерв',kind:'debit',bank:'oschad',active:true,card_last4:'5678'}];
const accountChoices=h=>h.state.messages.flatMap(m=>m.reply_markup?.inline_keyboard?.flat()??[]).filter(b=>b.callback_data?.startsWith('acc:'));
test('automatic text keeps choices only for unknown, ambiguous or default-only accounts',async()=>{
  const explicit=harness({accounts});await explicit.send('150 кава приват');
  assert.equal(explicit.state.rows[0]?.account_id,7);assert.equal(accountChoices(explicit).length,0);
  for(const text of ['150 кава','+150 зарплата']){
    const h=harness({accounts});await h.send(text);assert.ok(accountChoices(h).length>0,text);
  }
  const ambiguous=harness({accounts:[...accounts,{...accounts[0],id:9,name:'Друга',card_last4:'9999'}]});
  await ambiguous.send('150 кава приват');assert.equal(ambiguous.state.rows[0]?.account_id,null);assert.ok(accountChoices(ambiguous).length>0);
});
test('automatic images suppress choices for unique OCR and caption accounts only',async()=>{
  for(const hint of [{bank:'privat'},{card_last4:'1234'},{bank:'privat',card_last4:'1234'}]){
    const h=harness({accounts,ocr:receipt([{...receipt().transactions[0],...hint}])});await h.photo();
    assert.equal(h.state.rows[0]?.account_id,7);assert.equal(accountChoices(h).length,0,JSON.stringify(hint));
  }
  const caption=harness({accounts});await caption.photo({caption:'ощад'});
  assert.equal(caption.state.rows[0]?.account_id,8);assert.equal(accountChoices(caption).length,0);
  const unknown=harness({accounts});await unknown.photo();assert.ok(accountChoices(unknown).length>0);
  const single=harness({accounts,ocr:{has_total:true,amount:50,items_sum:50,date:'2026-10-20',readable:'good',bank:'privat'}});
  await single.photo();assert.equal(accountChoices(single).length,0);
});
test('financial confirmation keeps resolved account and has contextual decline without removed buttons',async()=>{
  const h=harness({accounts,rows:[{id:1,source:'mono',amount:150,type:'income',date:'2026-10-21'}]});
  await h.send('+150 зарплата приват');assert.equal(h.state.pending.account_resolved,true);
  const labels=h.state.messages.at(-1).reply_markup.keyboard.flat().map(b=>b.text);
  assert.deepEqual(labels,[kb.KB_BTN.yes,'Ні, не додавати']);
  await h.send(kb.KB_BTN.yes);assert.equal(accountChoices(h).length,0);
  const decline=harness({pending:{amount:10,type:'income',expires:new Date(NOW+100000).toISOString()}});
  await decline.send('Ні, не додавати');assert.equal(decline.state.pending,null);assert.equal(decline.state.rows.length,0);
});
test('partial receipt preserves confident account through confirmation',async()=>{
  const h=harness({accounts,ocr:{has_total:false,amount:null,items_sum:50,date:'2026-10-20',readable:'good',bank:'privat'}});
  await h.photo();assert.equal(h.state.pending.account_resolved,true);
  await h.send(kb.KB_BTN.yes);assert.equal(h.state.rows[0]?.account_id,7);assert.equal(accountChoices(h).length,0);
});

test('automatic messages and reports never reopen the native report keyboard',async()=>{
  for(const text of ['150 кава','150 кава приват','+150 зарплата','/week','/month',kb.KB_BTN.balance,kb.KB_BTN.last,kb.KB_BTN.app]){
    const h=harness({accounts});await h.send(text);
    assert.ok(h.state.messages.length,text);
    assert.ok(h.state.messages.every(m=>!m.reply_markup?.keyboard),text);
  }
  const h=harness({accounts});await h.photo();assert.ok(h.state.messages.every(m=>!m.reply_markup?.keyboard));
  for(const key of ['chart','budget']){
    const report=harness();await report.send(kb.KB_BTN[key]);assert.equal(report.state.photos.length,1);
    assert.equal(report.state.photos[0].has('reply_markup'),false);
  }
  for(const text of ['/menu','/start',kb.KB_BTN.help]){
    const menu=harness();await menu.send(text);assert.deepEqual(menu.state.messages.at(-1).reply_markup,kb.MAIN_KB);
  }
  const sendPhotoCode=stripTypeScriptTypes(source.slice(source.indexOf('async function sendPhoto('),source.indexOf('async function withFinance(')));
  let form;
  const send=new Function('fetch','BOT_TOKEN',sendPhotoCode+';return sendPhoto;')(async(_,init)=>{form=init.body;return {ok:true}},'test');
  assert.equal(await send(1,new Uint8Array([1]),'Звіт','report.png'),true);
  assert.equal(form.has('reply_markup'),false);
});
test('confirmation completion restores report keyboard even for a known account',async()=>{
  const h=harness({accounts,rows:[{id:1,source:'mono',amount:150,type:'income',date:'2026-10-21'}]});
  await h.send('+150 зарплата приват');h.state.messages.length=0;
  await h.send(kb.KB_BTN.yes);
  assert.ok(h.state.messages.some(m=>JSON.stringify(m.reply_markup)===JSON.stringify(kb.MAIN_KB)));
  assert.equal(accountChoices(h).length,0);
  const ordinary=harness({accounts});await ordinary.send('150 кава приват');
  assert.ok(ordinary.state.messages.every(m=>!m.reply_markup?.keyboard));
  assert.equal(accountChoices(ordinary).length,0);
  assert.ok(ordinary.state.messages.flatMap(m=>m.reply_markup?.inline_keyboard?.flat()||[]).every(b=>b.callback_data?.startsWith('flpick:')));
});
