const {test}=require('node:test');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const load=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/finance-message.ts')).href);
const normalize=s=>s.replace(/[\u00a0\u202f]/g,' ');
const sample=()=>({
 snapshot:{positiveOwnCents:280000,creditDebtCents:1600000,accounts:[]},
 nextPlan:{start:'2026-10-21',end:'2026-11-06',days:16,baseAvailableCents:880000,targetCents:1500000,gapCents:620000,averageDailyCents:93750},
 days:[{date:'2026-10-20',closingCashCents:-620000,shortfallCents:620000}],
 events:[{date:'2026-10-21',kind:'repay',cashDeltaCents:-1600000,certainty:'planned',name:'Card'}],minSpend:[]
});
// v233: розділи таблицями <pre>; рядки таблиці без HTML для перевірок
const unesc=s=>s.replace(/<\/?pre>/g,'').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
const tables=text=>[...text.matchAll(/<pre>([\s\S]*?)<\/pre>/g)].map(m=>unesc(normalize(m[1])).split('\n'));
const num=v=>v===''?0:Math.round(Number(v.replace(/ /g,'').replace(',','.'))*100);
// Число, що закінчується рівно на позиції end (колонки вирівняні праворуч під кінцем підпису шапки)
const cellAt=(l,end)=>{if(l.length<end||(l[end]!==undefined&&l[end]!==' '))return '';const m=l.slice(0,end).match(/(?:^|\s)([-+]?\d{1,3}(?: \d{3})*(?:,\d{2})?)$/);return m?m[1]:''};
// «Разом» кожної таблиці = сума показаних рядків над ним у кожній колонці
function assertTotals(text){
 let checked=0;
 for(const t of tables(text)){
  const k=t.findIndex(l=>/^Разом\s/.test(l));if(k<0)continue;
  const ends=[...t[0].trimEnd().matchAll(/\S+/g)].map(m=>m.index+m[0].length);
  for(const end of ends.slice(1)){
   const shown=cellAt(t[k],end);if(shown==='')continue;
   const sum=t.slice(1,k).map(l=>num(cellAt(l,end))).reduce((a,b)=>a+b,0);
   assert.equal(num(shown),sum,'Разом за колонкою до '+end+'\n'+t.join('\n'));checked++;
  }
 }
 return checked;
}
test('Telegram status: tables with totals, own and credit totals in cards, no dashes',async()=>{
 const {formatFinanceMessage}=await load();const p=sample();
 p.snapshot.accounts=[{id:1,name:'Ощад',balanceCents:280000,debtCents:0},{id:2,name:'Приват',balanceCents:0,debtCents:1000000,credit_limit:null},{id:3,name:'Mono',balanceCents:0,debtCents:600000,credit_limit:30000}];
 p.events=[{id:'repay:2:2026-09',date:'2026-10-21',kind:'repay',cashDeltaCents:-1000000,certainty:'planned',name:'Приват'},{date:'2026-10-22',kind:'mandatory',cashDeltaCents:-964000,certainty:'planned',name:'Садочок'}];
 p.untilPayout={end:'2026-10-21',days:9,cents:280000,dailyCents:31111};
 const html=formatFinanceMessage(p,undefined,[{name:'Ecoflow',n:2,amountCents:464300,lastDate:'2027-09-12'}],{end:'2026-10-21',leftCents:280000,dailyCents:31111,leftDays:9});
 const text=unesc(normalize(html));
 for(const re of [/^Бюджет 21\.10-06\.11\s+15 000$/m,/^  на день\s+938$/m,/^Лишилось до 21\.10\s+2 800$/m,/^  на день, 9 дн\.\s+311$/m,/^Власні\s+2 800$/m,/^Кредитні\s+16 000$/m,/^Баланс\s+-13 200$/m,
  /^₴\s+Власні\s+Борг\s+Доступно\s*$/m,/^Ощад\s+2 800$/m,/^Приват\s+0\s+10 000$/m,/^Mono\s+0\s+6 000\s+24 000$/m,/^Разом\s+2 800\s+16 000\s+24 000$/m,/^Приват: план погашення 21\.10$/m,
  /^Ecoflow\s+2\s+4 643\s+9 286\s+09\.27$/m,/^Разом\s+4 643\s+9 286$/m,/^22\.10 Садочок\s+9 640$/m]) assert.match(text,re);
 assert.match(text,/^Бюджет 21\.10[^\n]*\n  на день[^\n]*\nЛишилось[^\n]*\n  на день[^\n]*\nВласні[^\n]*\nКредитні[^\n]*\nБаланс/m,'порядок');
 assert.ok(assertTotals(html)>=4,'перевірено колонки «Разом»');
 for(const gone of ['Доступно до','Бюджет на життя','Ecoflow сьогодні','Власні кошти сьогодні','Доступні кошти','бракує','Прогноз','План погашення','—','–']) assert.ok(!text.includes(gone),gone+'\n'+text);
 // Таблиця вміщується на екрані телефона: рядок не ширший за 40 знаків
 for(const t of tables(html))for(const l of t)assert.ok(l.trimEnd().length<=40,l);
});
test('cards: kopecks round per row and Разом equals the shown rows; unassigned adjustment row; HTML-safe names',async()=>{
 const {financeSections}=await load();const p=sample();
 p.snapshot.accounts=[{id:1,name:'Ощад <зарплатна> & Ко',balanceCents:100050,debtCents:0},{id:2,name:'Готівка',balanceCents:20049,debtCents:0},{id:3,name:'Mono',balanceCents:150,debtCents:250050,credit_limit:5000}];
 p.snapshot.unassignedAdjustmentCents=-3060;p.snapshot.positiveOwnCents=100050+20049+150-3060;
 const s=financeSections(p);const html=s.cards.join('\n');
 assert.ok(html.includes('Ощад &lt;зарплатна&gt; &amp; Ко')&&!html.includes('<зарплатна>'),html);
 const t=unesc(normalize(html));
 assert.match(t,/^Без рахунку\s+-31$/m);assert.match(t,/^Разом\s+1 172\s+2 501\s+2 500$/m);
 assert.equal(assertTotals(html),3);
 const top=unesc(normalize(s.top.join('\n')));assert.match(top,/^Власні\s+1 172$/m);assert.match(top,/^Кредитні\s+2 501$/m);assert.match(top,/^Баланс\s+-1 329$/m);
});
test('no payout gives setup explanation',async()=>{
 const {formatFinanceMessage}=await load();const p=sample();
 p.nextPlan=null;const text=formatFinanceMessage(p);assert.ok(text.includes('Бюджет недоступний'));assert.ok(!text.includes('Бюджет на початок періоду'));
});
test('unassigned operations use Ukrainian plurals and conditional fees retain account meaning',async()=>{
 const {formatFinanceMessage}=await load();const p=sample();p.snapshot.accounts=[{id:7,name:'Рахунок'}];
 p.minSpend=[{accountId:7,month:'2026-10',spent:1000,min:15000,fee:400,left:14000}];
 p.events.push({date:'2026-11-01',kind:'fee',cashDeltaCents:-40000,certainty:'conditional',name:'Комісія'});
 for(const [n,word] of [[1,'операція'],[2,'операції'],[5,'операцій'],[11,'операцій'],[21,'операція'],[22,'операції'],[112,'операцій']]) {
   const text=unesc(normalize(formatFinanceMessage(p,{count:n,amountCents:10000})));
   assert.ok(text.includes(`Без рахунку: ${n} ${word} на 100 ₴`));
   assert.ok(text.includes('Рахунок: мін. витрати 1 000 ₴ з 15 000 ₴'),text);
   assert.match(text,/^01\.11 Комісія \(умовно\)\s+400$/m);
 }
});
// v183: відʼємний залишок до виплати і бюджету звучить як нестача чи перевитрата, сума без мінуса
test('negative until-payout and budget remainder read as shortage and overspend without minus',async()=>{
 const {formatFinanceMessage,untilPayoutLine,leftOrOver}=await load();
 assert.equal(normalize(untilPayoutLine({end:'2026-10-21',days:9,cents:-125050,dailyCents:0})),'Не вистачає до 21.10: 1 250,5 ₴');
 // v186: власні мінус обовʼязкові не ліміт витрат, без нестачі рядка немає
 assert.equal(untilPayoutLine({end:'2026-10-21',days:9,cents:280000,dailyCents:31111}),null);
 assert.equal(normalize(leftOrOver(-50000)),'перевитрата 500 ₴');
 assert.equal(normalize(leftOrOver(50000)),'лишилось 500 ₴');
 assert.equal(normalize(leftOrOver(50000,'залишок')),'залишок 500 ₴');
 const p=sample();p.untilPayout={end:'2026-10-21',days:9,cents:-125050,dailyCents:0};
 const text=unesc(normalize(formatFinanceMessage(p)));
 assert.match(text,/^Не вистачає до 21\.10\s+1 251$/m);
 assert.ok(!/Доступно до 21\.10: -/.test(text),text);
});
// v186: єдине число на день у боті: залишок бюджету періоду; перевитрата без «на день»
test('budget left line: remainder per day, overspend without daily part',async()=>{
 const {budgetLeftLine,formatFinanceMessage}=await load();
 assert.equal(normalize(budgetLeftLine({end:'2026-11-06',leftCents:139800,dailyCents:9985,leftDays:14})),'Бюджет до 06.11: лишилось 1 398 ₴ · 99,85 ₴/день (14 дн.)');
 assert.equal(normalize(budgetLeftLine({end:'2026-11-06',leftCents:-50000,dailyCents:0,leftDays:14})),'Бюджет до 06.11: перевитрата 500 ₴');
 const p=sample();p.untilPayout={end:'2026-10-21',days:9,cents:280000,dailyCents:31111};
 const text=normalize(formatFinanceMessage(p));
 assert.ok(!text.includes('Доступно до')&&!text.includes('311,11'),'власні мінус обовʼязкові не показуються як ліміт на день\n'+text);
});

test('v215: розділи статусу окремо, разом дають той самий повний текст',async()=>{
 const {financeSections,formatFinanceMessage}=await load();const p=sample();
 p.snapshot.accounts=[{id:1,name:'Ощад',balanceCents:280000,debtCents:0},{id:2,name:'Приват',balanceCents:0,debtCents:1000000,credit_limit:null}];
 p.events=[{id:'repay:2:2026-09',date:'2026-10-21',kind:'repay',cashDeltaCents:-1000000,certainty:'planned',name:'Приват'},{date:'2026-10-22',kind:'mandatory',cashDeltaCents:-964000,certainty:'planned',name:'Садочок'}];
 const inst=[{name:'Ecoflow',n:2,amountCents:464300,lastDate:'2027-09-12'}],lost={count:2,amountCents:10000},budget={end:'2026-10-21',leftCents:280000,dailyCents:31111,leftDays:9};
 const s=financeSections(p,lost,inst,budget);
 assert.deepEqual(Object.keys(s),['top','cards','installments','due','unassigned','totals']);
 // totals для голосу (voice-say.ts): ті самі числа, що в тексті розділів
 const bal=tables(s.top[0])[0].find(l=>/^Баланс\s/.test(l)),instT=tables(s.installments[0])[0];
 assert.equal(s.totals.balanceCents,num(bal.replace(/^Баланс\s+/,'')));
 assert.equal(s.totals.installmentsCents,num(cellAt(instT.find(l=>/^Разом\s/.test(l)),[...instT[0].trimEnd().matchAll(/\S+/g)][3].index+4)));
 assert.equal(s.totals.cardDebtCents,1000000);assert.deepEqual(s.totals.next,{date:'2026-10-22',name:'Садочок',cents:964000});
 assert.equal(s.top.length,1);assert.ok(/^<pre>[^\n]*\nБюджет 21\.10/.test(s.top[0]));assert.ok(/\nБаланс\s+\S[^\n]*<\/pre>$/.test(s.top[0]));
 assert.equal(s.cards.length,2);assert.ok(s.cards[0].startsWith('<pre>₴'));assert.equal(s.cards[1],'Приват: план погашення 21.10');
 assert.equal(s.installments.length,1);assert.ok(s.due[0].startsWith('<pre>Найближчі платежі'));assert.ok(/^⚠️ Без рахунку: 2 операції/.test(s.unassigned[0]));
 for(const part of [s.top,s.cards,s.installments,s.due,s.unassigned])assert.ok(part.every(line=>line!==''));
 assert.equal(formatFinanceMessage(p,lost,inst,budget),[s.top,s.cards,s.installments,s.due,s.unassigned].map(x=>x.join('\n')).join('\n\n'));
 const bare=sample();bare.events=[];const e=financeSections(bare);
 assert.deepEqual([e.cards,e.installments,e.due,e.unassigned],[[],[],[],[]]);assert.equal(formatFinanceMessage(bare),e.top.join('\n'));
});
