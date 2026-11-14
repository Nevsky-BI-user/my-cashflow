// Відповіді бота на питання (_shared/bot-agent.ts): модель лише обирає інструменти, числа й речення від коду,
// власний текст моделі з цифрами не показується, період і категорія перевіряються, відмови без вигаданих відповідей.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=f=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/'+f)).href);
const norm=s=>String(s).replace(/[  ]/g,' ');
const TODAY='2026-11-14';
const CATS=['Продукти','Кафе','Пальне','Зарплата'];

function fakeTools(log){
 return {
  balance:async(s)=>{log.push(['balance',s]);return 'Бюджет до 20.11: лишилось 5 000 ₴';},
  spending:async(q)=>{log.push(['spending',q]);return 'Продукти за жовтень: 8 200 ₴, 25 операцій.';},
  budget:async(c)=>{log.push(['budget',c]);return 'Бюджет періоду 06.11-20.11: 30 000 ₴, витрачено 12 000 ₴, лишилось 18 000 ₴.';},
 };
}
const claude=(content,status=200)=>async(url,init)=>{
 const body=JSON.parse(init.body);
 claude.last=body;
 return {ok:status===200,status,json:async()=>status===200?{content,stop_reason:'tool_use'}:{error:{type:'overloaded_error'}}};
};

test('один виклик моделі: інструменти з переліку категорій, tool_choice any, відповідь лише з тексту коду',async()=>{
 const {askAgent}=await mod('bot-agent.ts');
 const log=[];
 const r=await askAgent('скільки витратили на їжу в жовтні?',{apiKey:'k',today:TODAY,categories:CATS,
  fetchImpl:claude([{type:'text',text:'Ви витратили 99 999 гривень'},{type:'tool_use',name:'spending',input:{type:'expense',from:'2026-10-01',to:'2026-10-31',category:'Продукти'}}])},fakeTools(log));
 assert.equal(r.kind,'answer');
 assert.equal(norm(r.text),'Продукти за жовтень: 8 200 ₴, 25 операцій.');
 assert.ok(!r.text.includes('99 999'),'текст моделі з числом не потрапляє у відповідь');
 assert.deepEqual(log,[['spending',{type:'expense',from:'2026-10-01',to:'2026-10-31',category:'Продукти',search:null}]]);
 assert.deepEqual(claude.last.tool_choice,{type:'any'});
 assert.deepEqual(claude.last.tools.find(t=>t.name==='spending').input_schema.properties.category.enum,CATS);
 assert.ok(claude.last.system.includes('Сьогодні 2026-11-14, субота'));
});

test('кілька питань: кілька інструментів по черзі, не більше чотирьох',async()=>{
 const {runCalls}=await mod('bot-agent.ts');
 const log=[];
 const calls=[{name:'balance',input:{section:'cards'}},{name:'budget',input:{category:'кафе'}},
  ...Array.from({length:3},()=>({name:'balance',input:{section:'хтозна'}}))];
 const r=await runCalls(calls.slice(0,4),{today:TODAY,categories:CATS},fakeTools(log));
 assert.equal(r.kind,'answer');
 assert.deepEqual(log,[['balance','cards'],['budget','Кафе'],['balance','balance'],['balance','balance']],'невідомий розділ: основний статус; категорія за назвою з переліку');
});

test('період і категорія перевіряються кодом: майбутнє обрізається, вигадана категорія не рахується',async()=>{
 const {runCalls}=await mod('bot-agent.ts');
 const log=[];
 const r1=await runCalls([{name:'spending',input:{type:'expense',from:'2026-11-01',to:'2026-11-30'}}],{today:TODAY,categories:CATS},fakeTools(log));
 assert.equal(log[0][1].to,'2026-11-14');
 const r2=await runCalls([{name:'spending',input:{type:'expense',from:'2026-11-01',to:'2026-11-14',category:'Котики'}}],{today:TODAY,categories:CATS},fakeTools(log));
 assert.equal(r2.text,'Категорії «Котики» немає.');
 const r3=await runCalls([{name:'spending',input:{type:'expense',from:'вчора',to:'сьогодні'}}],{today:TODAY,categories:CATS},fakeTools(log));
 assert.equal(r3.text,'Не зрозумів період. Назвіть місяць, тиждень або дати.');
 assert.equal(log.length,1);
 const r4=await runCalls([{name:'spending',input:{type:'expense',from:'2026-11-01',to:'2026-11-14',search:'«АТБ»'}}],{today:TODAY,categories:CATS},fakeTools(log));
 assert.equal(log[1][1].search,'АТБ');
});

test('уточнення без цифр, відмови: не про гроші, не питання, зміна запису; збій моделі',async()=>{
 const {runCalls,askAgent,OFF_TOPIC,CHANGE_REQUEST,ADD_HINT}=await mod('bot-agent.ts');
 const ctx={today:TODAY,categories:CATS},tools=fakeTools([]);
 assert.deepEqual(await runCalls([{name:'clarify',input:{question:'За який місяць?'}}],ctx,tools),{kind:'clarify',text:'За який місяць?'});
 assert.equal((await runCalls([{name:'clarify',input:{question:'Ви витратили 500?'}}],ctx,tools)).text,'Уточніть, будь ласка: за який період або яку категорію?');
 assert.deepEqual(await runCalls([{name:'not_supported',input:{kind:'off_topic'}}],ctx,tools),{kind:'off_topic',text:OFF_TOPIC});
 assert.deepEqual(await runCalls([{name:'not_supported',input:{kind:'not_a_question'}}],ctx,tools),{kind:'not_question'});
 assert.deepEqual(await runCalls([{name:'not_supported',input:{kind:'change_request'}}],ctx,tools),{kind:'off_topic',text:CHANGE_REQUEST});
 assert.deepEqual(await runCalls([{name:'not_supported',input:{kind:'add_request'}}],ctx,tools),{kind:'off_topic',text:ADD_HINT},'прохання записати: підказка формату, не «змінювати не вмію»');
 assert.deepEqual(await askAgent('баланс?',{apiKey:'k',...ctx,fetchImpl:claude([],529)},tools),{kind:'error'});
 assert.deepEqual(await askAgent('баланс?',{apiKey:'k',...ctx,fetchImpl:claude([{type:'text',text:'Баланс 100'}])},tools),{kind:'error'},'без інструмента відповіді немає');
 assert.deepEqual(await askAgent('баланс?',{apiKey:'',...ctx},tools),{kind:'error'});
});

test('бюджет періоду: загалом і на категорію з моделі звіту «Бюджет»',async()=>{
 const {budgetAnswer}=await mod('bot-agent.ts');
 const m={start:'2026-11-06',end:'2026-11-20',poolCents:3000000,spentCents:1200000,leftCents:1800000,dailyCents:300000,leftDays:6,
  rows:[{id:'1',name:'Продукти',fact:820000,plan:1000000,over:false,near:false},{id:'2',name:'Кафе',fact:310000,plan:200000,over:true,near:false},
   {id:'__none',name:'Без категорії',fact:5000,plan:0,over:false,near:false,noPlan:true}],topOver:[]};
 assert.equal(norm(budgetAnswer(m,null)),'Бюджет періоду 06.11-20.11: 30 000 ₴, витрачено 12 000 ₴, лишилось 18 000 ₴. До 20.11: 3 000 ₴/день (6 дн.).');
 assert.equal(norm(budgetAnswer(m,'продукти')),'Продукти у періоді 06.11-20.11: план 10 000 ₴, витрачено 8 200 ₴, лишилось 1 800 ₴.');
 assert.equal(norm(budgetAnswer(m,'Кафе')),'Кафе у періоді 06.11-20.11: план 2 000 ₴, витрачено 3 100 ₴, перевитрата 1 100 ₴.');
 assert.equal(norm(budgetAnswer(m,'Без категорії')),'Без категорії у періоді 06.11-20.11: витрачено 50 ₴, плану немає.');
 assert.equal(norm(budgetAnswer(m,'Пальне')),'Пальне у періоді 06.11-20.11: ні плану, ні витрат немає.');
 assert.equal(budgetAnswer(null,null),'Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
});
