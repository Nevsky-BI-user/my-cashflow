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
test('Telegram status: balance, own funds, living budget, cards line by line, installments, no dashes',async()=>{
 const {formatFinanceMessage}=await load();const p=sample();
 p.snapshot.accounts=[{id:1,name:'Ощад',balanceCents:280000,debtCents:0},{id:2,name:'Приват',balanceCents:0,debtCents:1000000,credit_limit:null},{id:3,name:'Mono',balanceCents:0,debtCents:600000,credit_limit:30000}];
 p.events=[{id:'repay:2:2026-09',date:'2026-10-21',kind:'repay',cashDeltaCents:-1000000,certainty:'planned',name:'Приват'},{date:'2026-10-22',kind:'mandatory',cashDeltaCents:-964000,certainty:'planned',name:'Садочок'}];
 p.untilPayout={end:'2026-10-21',days:9,cents:280000,dailyCents:31111};
 const text=normalize(formatFinanceMessage(p,undefined,[{name:'Ecoflow',n:2,amountCents:464300,lastDate:'2027-09-12'}]));
 for(const expected of ['Баланс: -13 200 ₴','Доступно до 21.10: 2 800 ₴ · 311,11 ₴/день (9 дн.)','Власні кошти: 2 800 ₴','Бюджет на початок періоду: 15 000 ₴ · 937,5 ₴/день (21.10-06.11)','Ощад: 2 800 ₴','Приват: 0 ₴ · борг 10 000 ₴ до 21.10','Mono: 0 ₴ · борг 6 000 ₴ · доступно 24 000 ₴','Розстрочки: 9 286 ₴','Ecoflow: 2 × 4 643 ₴ = 9 286 ₴ · до 12.09.2027','22.10 · Садочок: 9 640 ₴']) assert.ok(text.includes(expected),expected+'\n'+text);
 assert.ok(/^Бюджет на початок періоду.*\nДоступно до .*\nВласні кошти: .*\nБаланс: /.test(text),'порядок\n'+text);
 for(const gone of ['Бюджет на життя','Ecoflow сьогодні','Власні кошти сьогодні','Доступні кошти','бракує','Прогноз','План погашення','\u2014','\u2013']) assert.ok(!text.includes(gone),gone+'\n'+text);
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
   const text=normalize(formatFinanceMessage(p,{count:n,amountCents:10000}));
   assert.ok(text.includes(`Без рахунку: ${n} ${word} на 100 ₴`));
   assert.ok(text.includes('Рахунок: 0 ₴ · мін. витрати 1 000 ₴ з 15 000 ₴'),text);
   assert.ok(text.includes('Комісія: 400 ₴ (умовно)'));
 }
});
