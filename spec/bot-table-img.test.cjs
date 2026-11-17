// v234 (власник 17.11.2026: «сітки немає», «тотал не виділено», «навіщо рядок з одним значенням грн»): таблиці бота картинкою
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=f=>import(pathToFileURL(path.join(__dirname,'../supabase/functions/_shared',f)).href);

const sample=()=>({snapshot:{positiveOwnCents:280000,creditDebtCents:1000000,accounts:[
  {id:1,name:'Ощад',kind:'debit',owner:'Віталік',balanceCents:280000,debtCents:0},
  {id:2,name:'Приват <Універсальна>',kind:'credit',owner:null,balanceCents:0,debtCents:1000000,credit_limit:300}]},
  nextPlan:{start:'2026-10-21',end:'2026-11-06',targetCents:1500000,averageDailyCents:93750},events:[],minSpend:[],untilPayout:null});

test('картки: окремі колонки Хто і Тип, порожній власник лишається порожнім, «Разом» жирний із заливкою',async()=>{
  const {financeSections}=await mod('finance-message.ts');const {richReport}=await mod('rich-send.ts');const bt=await mod('bot-table.ts');
  const s=financeSections(sample());
  const sp=bt.tableSpecOf(s.cards[1]);
  assert.deepEqual(sp.head,['Рахунок','Хто','Тип','Власні','Борг','Доступно']);
  assert.deepEqual(sp.rows[0],['Ощад','Віталік','дебетова','2 800','','']);
  assert.deepEqual(sp.rows[1].slice(0,3),['Приват <Універсальна>','','кредитна']);
  assert.equal(sp.kinds.at(-1),'total');assert.equal(sp.rows.at(-1)[0],'Разом');
  const r=richReport(s.cards.join('\n'));
  assert.ok(r,'картинка є');assert.equal(r.caption,'Суми в ₴');
  assert.ok(r.svg.includes('>Хто<')&&r.svg.includes('font-weight="700"'),'шапка і жирний підсумок');
  assert.ok(r.svg.includes('Приват &lt;Універсальна&gt;'),'назва екранована в SVG');
  assert.ok(r.svg.includes('fill="#ECECF1"'),'заливка рядка «Разом»');
});

test('баланс: без шапки з одним ₴, «На день» без відступу, рядок Баланс підсумковий',async()=>{
  const {financeSections}=await mod('finance-message.ts');const bt=await mod('bot-table.ts');
  const s=financeSections(sample());
  assert.equal(s.top[0],'Суми в ₴');
  assert.ok(!/^\s+₴\s*$/m.test(s.top[1]),'рядка з одним ₴ немає');
  const sp=bt.tableSpecOf(s.top[1]);
  assert.deepEqual(sp.head,[]);
  assert.ok(sp.rows.some(r=>r[0]==='На день'));
  assert.equal(sp.kinds[sp.rows.findIndex(r=>r[0]==='Баланс')],'total');
});

test('перевитрата за оціненим місячним планом підписана як прогноз, інакше як факт',async()=>{
  const {financeSections}=await mod('finance-message.ts');
  const b={end:'2026-11-20',leftCents:-1234500,dailyCents:0,leftDays:3};
  assert.ok(financeSections(sample(),undefined,[],{...b,monthlyBudgetEstimated:true}).top[1].includes('Прогноз перевитрати до 20.11'));
  const fact=financeSections(sample(),undefined,[],b).top[1];
  assert.ok(fact.includes('Перевитрата до 20.11')&&!fact.includes('Прогноз'));
});

test('звіт із незареєстрованою таблицею або задовгим підписом лишається текстом',async()=>{
  const {richReport}=await mod('rich-send.ts');const {preTable}=await mod('bot-table.ts');
  assert.equal(richReport('<pre>вручну</pre>'),null);
  assert.equal(richReport('лише текст'),null);
  const t=preTable(['Назва','Сума'],[['А','1'],['Разом','1']]);
  assert.equal(richReport('x'.repeat(1100)+'\n'+t),null);
  assert.ok(richReport('Підпис\n'+t));
});

test('стос таблиць з однаковою кількістю колонок має спільні межі колонок',async()=>{
  const {tablesSvg}=await mod('bot-table-svg.ts');
  const a={head:[],rows:[['Коротко','1']],kinds:['row'],aligns:['l','r']};
  const b={head:['Платежі','Сума'],rows:[['Дуже довга назва платежу','1 234 567']],kinds:['row'],aligns:['l','r']};
  const svg=tablesSvg([a,b]);
  const xs=[...svg.matchAll(/<line x1="([\d.]+)" y1="[\d.]+" x2="\1"/g)].map(m=>m[1]);
  assert.equal(new Set(xs).size,1,'вертикальні межі збігаються: '+xs.join(','));
});
