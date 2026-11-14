// Витрати за довільний період (_shared/spending.ts) для питань до бота: ті самі правила, що у звіті «Місяць»,
// фільтр категорії й пошук за описом не змішуються, «Без категорії» лишається окремо, період від моделі обрізається.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {botFixture}=require('./bot-fixture.cjs');
const mod=f=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/'+f)).href);
const norm=s=>String(s).replace(/[  ]/g,' ');

test('паритет зі звітом «Місяць»: витрати й доходи цього і минулого відрізка, категорії до копійки',async()=>{
 const [rep,sp]=await Promise.all([mod('bot-reports.ts'),mod('spending.ts')]);
 const fx=botFixture();
 const m=rep.monthModel(fx.transactions,fx.categories,fx.accounts,fx.today);
 const run=(type,from,to)=>sp.spendingModel(fx.transactions,fx.categories,fx.accounts,{type,from,to});
 const cur=run('expense',m.curFrom,m.curTo), prev=run('expense',m.prevFrom,m.prevTo), full=run('expense',m.prevFrom,m.prevFullTo);
 assert.equal(cur.totalCents,m.curSpent);
 assert.equal(prev.totalCents,m.prevSpent);
 assert.equal(full.totalCents,m.prevFullSpent);
 assert.equal(run('income',m.curFrom,m.curTo).totalCents,m.curIncome);
 assert.equal(run('income',m.prevFrom,m.prevTo).totalCents,m.prevIncome);
 const curCats=Object.fromEntries(m.cats.filter(c=>c.cur).map(c=>[c.name,c.cur]));
 assert.deepEqual(Object.fromEntries(cur.byCategory.map(c=>[c.name,c.cents])),curCats);
 assert.equal(cur.byCategory.reduce((n,c)=>n+c.cents,0),cur.totalCents,'сума категорій = підсумок');
 for(const c of m.cats.filter(c=>c.cur)){
  assert.equal(sp.spendingModel(fx.transactions,fx.categories,fx.accounts,{type:'expense',from:m.curFrom,to:m.curTo,category:c.name}).totalCents,c.cur,c.name);
 }
});

const cats=[{id:1,name:'Продукти'},{id:2,name:'Кафе'},{id:3,name:'Пальне'}];
const accounts=[{id:10,kind:'debit'},{id:20,kind:'credit'}];
const tx=(id,amount,date,extra={})=>({id,type:'expense',amount,date,account_id:10,category_id:1,description:'',...extra});

test('категорія, пошук, без категорії, погашення через межу періоду, розподіл чека',async()=>{
 const sp=await mod('spending.ts');
 const txs=[
  tx(1,100,'2026-11-01',{description:'Сільпо'}), tx(2,50.5,'2026-11-02',{category_id:2,description:'Кава'}),
  tx(3,30,'2026-11-03',{category_id:null,description:'Сільпо пакет'}), tx(4,999,'2026-11-04',{transfer_id:'t1'}),
  // погашення кредитки: дохід на кредитку 31.10, витрата з дебетової 01.11 тієї ж суми: не витрата
  {id:5,type:'income',amount:700,date:'2026-10-31',account_id:20}, tx(6,700,'2026-11-01',{category_id:null,description:'Погашення'}),
  // чек на дві категорії
  tx(7,80,'2026-11-05',{description:'Ашан',expense_allocations:[{category_id:1,amount_cents:6000},{category_id:2,amount_cents:2000}]}),
  tx(8,40,'2026-11-20'), tx(1,100,'2026-11-01',{description:'Сільпо'}),
 ];
 const q=(o)=>sp.spendingModel(txs,cats,accounts,{type:'expense',from:'2026-11-01',to:'2026-11-14',...o});
 const all=q({});
 assert.equal(all.totalCents,10000+5050+3000+8000,'без переказу, погашення, дубля і операції після періоду');
 assert.equal(all.count,4);
 assert.deepEqual(all.byCategory.map(c=>[c.name,c.cents]),[['Продукти',16000],['Кафе',7050],['Без категорії',3000]]);
 assert.equal(q({category:'продукти'}).totalCents,16000,'регістр не важить, частина чека входить');
 assert.equal(q({category:'Кафе'}).count,2);
 assert.equal(q({search:'сільпо'}).totalCents,13000,'пошук бере і операцію без категорії');
 assert.deepEqual(q({search:'сільпо'}).byCategory.map(c=>c.name),['Продукти','Без категорії'],'пошук не дописує категорію');
 assert.equal(q({category:'Пальне'}).count,0);
});

test('текст відповіді: місяць словом, неповний місяць датами, порожньо, доходи',async()=>{
 const sp=await mod('spending.ts');
 const txs=[tx(1,100,'2026-10-01'),tx(2,50.5,'2026-10-31',{category_id:2}),{id:3,type:'income',amount:65459,date:'2026-11-05',account_id:10}];
 const f=(o)=>norm(sp.formatSpending(sp.spendingModel(txs,cats,accounts,{type:'expense',...o}),'2026-11-14'));
 assert.equal(f({from:'2026-10-01',to:'2026-10-31'}),'Витрати за жовтень: 150,5 ₴, 2 операції. Найбільше: Продукти 100 ₴, Кафе 50,5 ₴.');
 assert.equal(f({from:'2026-10-01',to:'2026-10-31',category:'Кафе'}),'Кафе за жовтень: 50,5 ₴, 1 операція.');
 assert.equal(f({from:'2026-11-01',to:'2026-11-14'}),'Витрат 01.11-14.11 немає.');
 assert.equal(f({from:'2026-11-01',to:'2026-11-14',search:'Сільпо'}),'«Сільпо» 01.11-14.11: витрат немає.');
 assert.equal(norm(sp.formatSpending(sp.spendingModel(txs,cats,accounts,{type:'income',from:'2026-11-01',to:'2026-11-14'}),'2026-11-14')),'Доходи 01.11-14.11: 65 459 ₴, 1 операція.');
 assert.equal(sp.periodLabel('2025-11-01','2025-11-30','2026-11-14'),'за листопад 2025');
 assert.equal(sp.periodLabel('2026-11-14','2026-11-14','2026-11-14'),'14.11');
});

test('межі періоду від моделі: майбутнє обрізається до сьогодні, биті й задовгі відхиляються',async()=>{
 const sp=await mod('spending.ts');
 assert.deepEqual(sp.clampPeriod('2026-11-01','2026-11-30','2026-11-14'),{from:'2026-11-01',to:'2026-11-14'});
 assert.equal(sp.clampPeriod('2026-11-20','2026-11-30','2026-11-14'),null);
 assert.equal(sp.clampPeriod('2024-01-01','2026-11-14','2026-11-14'),null);
 assert.equal(sp.clampPeriod('14.11.2026','2026-11-14','2026-11-14'),null);
 assert.equal(sp.clampPeriod('2026-02-30','2026-03-01','2026-11-14'),null);
});
