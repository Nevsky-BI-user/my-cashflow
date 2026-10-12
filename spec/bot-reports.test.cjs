// Звіти Telegram-бота: Бюджет, Тиждень, Місяць, графік балансу, ранкова година за Києвом і кнопка «Оплачено».
// Чисті модулі (bot-reports.ts, bot-charts.ts) на синтетичній фікстурі; рендер PNG і мережа не запускаються.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {botFixture}=require('./bot-fixture.cjs');
const mod=f=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/'+f)).href);
const norm=s=>String(s).replace(/[  ]/g,' ');
const cents=v=>Math.round((Number(v)||0)*100);

async function setup(){
 const [{financeProjection},rep,ch,fm]=await Promise.all([mod('budget.ts'),mod('bot-reports.ts'),mod('bot-charts.ts'),mod('finance-message.ts')]);
 const fx=botFixture();
 const through=rep.plusDays(fx.today,120);
 const pr=financeProjection({accounts:fx.accounts,fixed:fx.fixed,credits:fx.credits,salary:fx.salary,categories:fx.categories,transactions:fx.transactions},{asof:fx.today,through});
 return {pr,rep,ch,fm,fx};
}

test('Бюджет: суми з проєкції застосунку, факт категорій сходиться з витраченим, перевитрати позначено',async()=>{
 const {pr,rep,fx}=await setup();
 const m=rep.budgetModel(pr,fx.transactions,fx.categories,fx.today);
 const cp=pr.currentPeriod;
 assert.equal(m.poolCents,cp.targetCents);
 assert.equal(m.spentCents,cp.actualVariableCents);
 assert.equal(m.leftCents,cp.targetCents-cp.actualVariableCents);
 assert.equal(m.dailyCents,Math.floor(cp.dailyCents));
 assert.equal(m.rows.reduce((n,r)=>n+r.fact,0),m.spentCents,'факт категорій = витрачено за періодом');
 for(const r of m.rows){
  if(r.noPlan)continue;
  assert.equal(r.over,r.fact>r.plan,r.name);
  assert.equal(r.near,!r.over&&r.plan>0&&r.fact*10>=r.plan*9,r.name);
 }
 assert.ok(m.topOver.length<=3);
 for(let i=1;i<m.topOver.length;i++)assert.ok(m.topOver[i-1].fact-m.topOver[i-1].plan>=m.topOver[i].fact-m.topOver[i].plan);
 const t=norm(rep.formatBudget(m));
 assert.match(t,/^📊 Бюджет періоду 06\.10-21\.10\n/);
 assert.ok(t.includes('Бюджет: 20 373,94 ₴ · витрачено 12 373,94 ₴ (61%) · лишилось 8 000 ₴'),t);
 assert.ok(t.includes('До 21.10: 1 000 ₴/день (8 дн.)'),t);
 for(const gone of ['Категорії, факт','Найбільші перевитрати','⚠️'])assert.ok(!t.includes(gone),gone+'\n'+t);
 assert.equal(rep.formatBudget(null),'Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
});

test('Бюджет: позначки понад план і від 90% плану в моделі, текст без категорій',async()=>{
 const {rep}=await setup();
 const pr={currentPeriod:{start:'2026-10-06',end:'2026-10-21',targetCents:100000,actualVariableCents:19000,dailyCents:9000.7,leftDays:9},
  periods:[{basis:'current',categories:[{id:1,totalCents:10000},{id:2,totalCents:10000}]}]};
 const cats=[{id:1,name:'А',is_income:false},{id:2,name:'Б',is_income:false}];
 const txs=[{id:1,type:'expense',amount:90,date:'2026-10-07',category_id:1},{id:2,type:'expense',amount:100.01,date:'2026-10-08',category_id:2},
  {id:3,type:'expense',amount:500,date:'2026-10-08',category_id:2,fixed_id:5},{id:4,type:'expense',amount:70,date:'2026-10-05',category_id:1}];
 const m=rep.budgetModel(pr,txs,cats,'2026-10-12');
 const t=norm(rep.formatBudget(m));
 // Позначки лишаються в моделі (кільце на картинці), текст звіту лише з підсумком
 const row=name=>m.rows.find(r=>r.name===name);
 assert.ok(row('А').near&&!row('А').over);
 assert.ok(row('Б').over);
 assert.ok(!t.includes('⚠️')&&!t.includes('🟠'),t);
 assert.equal(m.dailyCents,9000);
});

test('Тиждень: події 7 днів, баланс на кінець за формулою застосунку і попередження про нестачу',async()=>{
 const {pr,rep,fx}=await setup();
 const w=rep.weekModel(pr,fx.today);
 assert.equal(w.to,'2026-10-18');
 const last=pr.days.find(d=>d.date==='2026-10-18');
 // v150 (модель «власні ≥ 0»): баланс = власні мінус борг кредиток мінус нестача плюс зсув власних, як «Баланс після» у Платежах
 const bal=d=>d.closingCashCents-d.debtCents-d.arrearsCents+pr.snapshot.positiveOwnCents-pr.snapshot.cashCents;
 assert.equal(w.endBalanceCents,bal(last));
 // власні не мінус; попередження лише про нестачу (платіж без права на кредит не покрито)
 assert.ok(pr.days.every(d=>d.closingCashCents>=0),'власні мінус');
 const short=pr.days.find(d=>d.date>=fx.today&&d.date<='2026-10-18'&&d.arrearsCents>0);
 assert.deepEqual(w.gap,short?{date:short.date,cents:short.arrearsCents}:null);
 const t=norm(rep.formatWeek(w));
 assert.ok(t.startsWith('📅 Тиждень 12.10-18.10\n'),t);
 for(const l of['Разом витрати за тиждень: 8 300 ₴','· щоденні витрати: 6 000 ₴','· 12.10 Прибирання: 500 ₴','· 13.10 Інтернет: 300 ₴','· 13.10 Телефон (розстрочка): 1 500 ₴'])assert.ok(t.includes(l),l+'\n'+t);
 assert.ok(!t.includes('Щоденні витрати за бюджетом'),t);
 assert.ok(!t.includes('Баланс на кінець 18.10'),'рядка балансу на кінець немає');
 assert.ok(!t.includes('Каса'),'рядка про касу немає\n'+t);
 // Таблиця: 7 днів з днем тижня, сьогодні ▸, баланс кінця дня за формулою застосунку
 const pre=t.slice(t.indexOf('<pre>')+5,t.indexOf('</pre>')).split('\n');
 assert.equal(pre.length,8,t);
 assert.ok(pre[1].startsWith('▸Пн 12.10'),pre[1]);
 assert.ok(pre[7].startsWith(' Нд 18.10'),pre[7]);
 assert.equal(w.days.length,7);
 for(const d of w.days){const x=pr.days.find(q=>q.date===d.date);assert.equal(d.balanceCents,bal(x));const ev=w.events.filter(e=>e.date===d.date&&(e.kind==='mandatory'||e.kind==='fee')&&e.cents<0).reduce((n,e)=>n-e.cents,0);assert.equal(d.spendCents,(x.variableCents||0)+ev)}
 // 13.10: щоденні 1 000 + Інтернет 300 + Телефон 1 500 = 2 800; «Разом» текстом під таблицею, не в ній
 assert.equal(w.days[1].spendCents,280000);
 assert.ok(!pre.some(r=>r.includes('Разом')),pre.join('\n'));
 assert.equal(w.days[6].balanceCents,w.endBalanceCents);
 const empty=norm(rep.formatWeek({from:'2026-10-12',to:'2026-10-18',events:[],variableCents:0,endBalanceCents:100,endCashCents:100,gap:null}));
 assert.ok(!empty.includes('мінус'));
});

test('Місяць: той самий відрізок минулого місяця, погашення кредитки не витрата, топ-5 місць',async()=>{
 const {rep,fx}=await setup();
 const m=rep.monthModel(fx.transactions,fx.categories,fx.accounts,fx.today);
 assert.deepEqual([m.curFrom,m.curTo,m.prevFrom,m.prevTo,m.prevFullTo],['2026-10-01','2026-10-12','2026-09-01','2026-09-12','2026-09-30']);
 // Незалежний підрахунок: витрати жовтня без пари погашення (3000 з Ощаду 08.10 + 3000 доходу на Приват)
 const exp=(a,b)=>fx.transactions.filter(t=>t.type==='expense'&&t.date>=a&&t.date<=b&&t.description!=='Погашення Приват').reduce((n,t)=>n+cents(t.amount),0);
 assert.equal(m.curSpent,exp('2026-10-01','2026-10-12'));
 assert.equal(m.prevSpent,exp('2026-09-01','2026-09-12'));
 assert.equal(m.prevFullSpent,exp('2026-09-01','2026-09-30'));
 assert.equal(m.curIncome,6970000,'дохід жовтня без доходу-погашення на кредитку');
 assert.equal(m.cats.reduce((n,c)=>n+c.cur,0),m.curSpent);
 assert.equal(m.places.length,5);
 const t=norm(rep.formatMonth(m));
 assert.ok(t.startsWith('🔍 Жовтень: 01.10-12.10 проти 01.09-12.09\n'),t);
 for(const l of['Доходи: 69 700 ₴ (було 65 450 ₴)','Топ-5 місць:\n1. Фора: 3 462,52 ₴ (5 разів)','4. Сільпо: 1 368,13 ₴ (2 рази)',
  'Здоровʼя: 684,81 ₴ · ↑ 684,81 ₴ (нова)','Розстрочки: 2 083 ₴ · = 0 ₴'])assert.ok(t.includes(l),l+'\n'+t);
 assert.ok(!t.includes('Погашення'),'погашення кредитки не потрапляє в місця');
 assert.equal(norm(rep.delta(15000,10000)),'↑ 50 ₴ (+50%)');
 assert.equal(norm(rep.delta(5000,10000)),'↓ 50 ₴ (-50%)');
 // Січень порівнюється з груднем попереднього року, 31.03 з 28.02 (обрізання до кінця місяця)
 const j=rep.monthModel([],[],[],'2027-01-05');
 assert.deepEqual([j.prevFrom,j.prevTo],['2026-12-01','2026-12-05']);
 const mar=rep.monthModel([],[],[],'2027-03-31');
 assert.deepEqual([mar.prevTo,mar.prevFullTo],['2027-02-28','2027-02-28']);
});

test('Графік: лінія = власні кошти (v150), точка «сьогодні» = власні, мінімум є на графіку й у підписі',async()=>{
 const {pr,rep,ch,fm,fx}=await setup();
 const s=rep.balanceSeries(pr,fx.transactions,fx.accounts,fx.today,{salary:fx.salary,firstOwnDate:'2026-09-01'});
 assert.equal(s.today.date,fx.today);
 assert.equal(s.today.cents,pr.snapshot.positiveOwnCents);
 assert.equal(s.from,'2026-09-12');
 assert.equal(s.to,'2026-11-12');
 const all=[...s.past,...s.future];
 assert.equal(s.min.cents,Math.min(...all.map(p=>p.cents)));
 assert.ok(all.some(p=>p.date===s.min.date&&p.cents===s.min.cents));
 // Як «мін.» застосунку: за весь видимий відрізок, за рівності перша дата
 assert.equal(s.min.date,all.find(p=>p.cents===s.min.cents).date);
 // Майбутнє: власні на кінець дня рушія, не мінус
 for(const p of s.future){const d=pr.days.find(x=>x.date===p.date);assert.equal(p.cents,d.closingCashCents,p.date);assert.ok(p.cents>=0,p.date);}
 assert.equal(s.afterPayout.cents,pr.days.find(d=>d.date===s.afterPayout.date).closingCashCents,'після виплати у власних');
 assert.ok(s.payouts.length>=2,'виплати в межах графіка');
 const c=ch.balanceChartSvg(s);
 assert.match(c.svg,/^<svg [^>]*width="1080" height="720"/);
 assert.ok(!c.svg.includes('>мінімум '+fm.day(s.min.date)+'<'),'мінімум лише числом');
 const all2=[...s.past,...s.future];assert.equal(s.max.cents,Math.max(...all2.map(p=>p.cents)));
 if(s.max.date!==s.today.date&&s.max.date!==s.min.date)assert.ok(c.svg.includes('>'+fm.money(s.max.cents)+'<'),'максимум числом');
 for(const p of s.payouts)if(p.date>s.today.date&&p.date!==s.min.date)assert.ok(c.svg.includes('>'+fm.money(p.cents)+'<'),'пік виплати числом '+p.date);
 assert.ok(norm(c.svg).includes(norm(fm.money(s.today.cents))),'сума сьогодні на графіку');
 assert.ok(c.svg.includes(`cx="${Math.round(c.todayXY[0]*10)/10}" cy="${Math.round(c.todayXY[1]*10)/10}" r="12"`),'точка сьогодні');
 assert.ok(c.svg.includes('stroke-dasharray'),'прогноз пунктиром');
 // Одна шкала: нуль, сьогодні і мінімум лежать на одній прямій y(cents)
 assert.ok(c.yZero!=null);
 const k1=(c.todayXY[1]-c.yZero)/s.today.cents,k2=(c.minXY[1]-c.yZero)/s.min.cents;
 assert.ok(Math.abs(k1-k2)<1e-9,`${k1} ${k2}`);
 // мінімум у минулому: відновлення власних назад від сьогодні за операціями власних рахунків (синтетична історія фікстури не узгоджена з балансами)
 assert.equal(norm(rep.chartCaption(s)),'Власні сьогодні 4 899 ₴ · мінімум -105 134,37 ₴ 20.09 · після виплати 21.10: 17 670,62 ₴');
 // Історія не раніше першої операції
 const late=rep.balanceSeries(pr,fx.transactions.filter(t=>t.date>='2026-10-01'),fx.accounts,fx.today,{salary:fx.salary,firstOwnDate:'2026-10-01'});
 assert.equal(late.from,'2026-10-01');
 assert.ok(late.past.every(p=>p.date>='2026-10-01'));
});

test('Ранковий підсумок: 9-та година за Києвом влітку і взимку, дата за Києвом',async()=>{
 const {rep}=await setup();
 const h=iso=>rep.kyivNow(new Date(iso));
 assert.deepEqual(h('2026-07-15T06:00:00Z'),{date:'2026-07-15',hour:9});
 assert.equal(h('2026-07-15T07:00:00Z').hour,10);
 assert.deepEqual(h('2026-12-15T07:00:00Z'),{date:'2026-12-15',hour:9});
 assert.equal(h('2026-12-15T06:00:00Z').hour,8);
 // Переходи 2026: 29.03 на літній (UTC+3), 25.10 на зимовий (UTC+2)
 assert.equal(h('2026-03-28T07:00:00Z').hour,9);
 assert.equal(h('2026-03-29T06:00:00Z').hour,9);
 assert.equal(h('2026-10-24T06:00:00Z').hour,9);
 assert.equal(h('2026-10-25T06:00:00Z').hour,8);
 assert.equal(h('2026-10-25T07:00:00Z').hour,9);
 assert.deepEqual(h('2026-10-11T22:30:00Z'),{date:'2026-10-12',hour:1});
 assert.deepEqual(h('2026-12-31T22:00:00Z'),{date:'2027-01-01',hour:0});
 // Щогодинний cron дає рівно один запуск о 9-й за київським часом на кожну добу року
 for(let d=Date.UTC(2026,0,1);d<Date.UTC(2027,0,1);d+=86400000){
  const hits=[];for(let i=0;i<24;i++)if(rep.isKyivHour(new Date(d+i*3600000-3*3600000),9))hits.push(i);
  assert.equal(hits.length,1,new Date(d).toISOString());
 }
});

test('Ранковий підсумок і нагадування з фікстури',async()=>{
 const {pr,rep,fx}=await setup();
 const t=norm(rep.formatDigest(pr,fx.credits,fx.transactions,fx.today));
 assert.ok(t.startsWith('☀️ Доброго ранку! 12.10\nБаланс: -33 428 ₴\n'),t);
 assert.ok(t.includes('Спишеться сьогодні: 500 ₴\n· Прибирання: 500 ₴'),t);
 assert.ok(t.includes('Завтра, 13.10: 1 800 ₴\n· Інтернет: 300 ₴\n· Телефон (розстрочка): 1 500 ₴'),t);
 assert.ok(!t.includes('Ecoflow'),'сьогоднішня розстрочка вже оплачена операцією');
 const due=rep.dueTomorrow(pr,fx.fixed,fx.credits,fx.today);
 assert.deepEqual(due.map(d=>d.callback),['pd:f:11:2026-10-13','pd:c:22:2026-10-13']);
 assert.ok(due.every(d=>Buffer.byteLength(d.callback)<=64),'callback_data до 64 байт');
});

test('Нагадування: без кнопки для погашення кредитки і списань Monobank',async()=>{
 const {rep}=await setup();
 const pr={events:[
  {date:'2026-10-25',kind:'mandatory',occurrenceId:'fixed:14:2026-10',name:'Спортзал',cashDeltaCents:-90000},
  {date:'2026-10-25',kind:'repay',accountId:4,name:'ПриватБанк',cashDeltaCents:-925655},
  {date:'2026-10-25',kind:'mandatory',occurrenceId:'fixed:13:2026-10-25',name:'Прибирання',cashDeltaCents:-50000},
  {date:'2026-10-25',kind:'variable',name:'Щоденні',cashDeltaCents:-100000},
  {date:'2026-10-26',kind:'mandatory',occurrenceId:'fixed:12:2026-10',name:'Інше число',cashDeltaCents:-1}]};
 const fixed=[{id:14,bank:'mono'},{id:13,bank:'cash',period:'week'}];
 const due=rep.dueTomorrow(pr,fixed,[],'2026-10-24');
 assert.deepEqual(due.map(d=>[d.kind,d.id,d.button,d.callback]),[['f','14',false,null],['r','4',false,null],['f','13',true,'pd:f:13:2026-10-25']]);
 assert.ok(norm(rep.formatReminder(due[0])).includes('Спишеться з Monobank'));
 assert.ok(norm(rep.formatReminder(due[1])).startsWith('⏰ Завтра, 25.10: Погашення кредитки ПриватБанк, 9 256,55 ₴'));
});

test('«Оплачено»: розбір callback лише з id, повторне натискання не дає другого запису',async()=>{
 const {rep,fx}=await setup();
 assert.deepEqual(rep.parsePaidCallback('pd:f:11:2026-10-13'),{kind:'f',id:'11',date:'2026-10-13'});
 for(const bad of['pd:r:4:2026-10-13','pd:f:11:2026-10-13x','pd:f:abc:2026-10-13','acc:1:2','pd:f:11:2026-10',' pd:f:11:2026-10-13'])assert.equal(rep.parsePaidCallback(bad),null,bad);
 const item=fx.fixed.find(f=>f.id===11);
 const history=fx.transactions.filter(t=>t.fixed_id===11);
 const first=rep.payPlan({kind:'f',item,eventDate:'2026-10-13',today:'2026-10-12',history,cats:fx.categories});
 assert.equal(first.status,'insert');
 assert.deepEqual(first.row,{amount:300,type:'expense',description:'Інтернет',source:'telegram',source_id:'tgpaid:f:11:2026-10',date:'2026-10-12',
  fixed_id:11,credit_id:null,category_id:7});
 // Друге натискання (або другий член сімʼї): запис уже в історії, вставки немає
 const again=rep.payPlan({kind:'f',item,eventDate:'2026-10-13',today:'2026-10-12',history:[...history,{id:999,...first.row}],cats:fx.categories});
 assert.deepEqual(again,{status:'already',date:'2026-10-12'});
 // Оплату внесли в застосунку (будь-яка витрата з fixed_id у тому самому місяці)
 const app=rep.payPlan({kind:'f',item,eventDate:'2026-10-13',today:'2026-10-13',history:[{id:5,type:'expense',fixed_id:11,date:'2026-10-02',amount:300}],cats:fx.categories});
 assert.deepEqual(app,{status:'already',date:'2026-10-02'});
 // Гонка двох натискань: source_id однаковий незалежно від дня натискання, унікальний індекс відсікає дубль
 const later=rep.payPlan({kind:'f',item,eventDate:'2026-10-13',today:'2026-10-20',history,cats:fx.categories});
 assert.equal(later.row.source_id,first.row.source_id);
 // Розстрочка: категорія з попередньої оплати, сума платежу
 const cr=rep.payPlan({kind:'c',item:fx.credits.find(c=>c.id===22),eventDate:'2026-10-13',today:'2026-10-12',history:fx.transactions.filter(t=>t.credit_id===22),cats:fx.categories});
 assert.equal(cr.status,'insert');
 assert.equal(cr.row.credit_id,22);assert.equal(cr.row.fixed_id,null);assert.equal(cr.row.amount,1500);assert.equal(cr.row.category_id,8);
 assert.equal(cr.row.source_id,'tgpaid:c:22:2026-10');
 // Щотижневий платіж: період пн-нд, ключ за понеділком
 const wk=fx.fixed.find(f=>f.id===13);
 const w=rep.payPlan({kind:'f',item:wk,eventDate:'2026-10-19',today:'2026-10-18',history:[],cats:fx.categories});
 assert.equal(w.row.source_id,'tgpaid:f:13:W2026-10-19');
 assert.equal(w.row.date,'2026-10-19','нагадування в неділю про понеділок: оплата закриває тиждень події');
 assert.equal(rep.payPlan({kind:'f',item:wk,eventDate:'2026-10-12',today:'2026-10-12',history:fx.transactions.filter(t=>t.fixed_id===13),cats:fx.categories}).status,'insert');
 assert.equal(rep.payPlan({kind:'f',item:wk,eventDate:'2026-10-11',today:'2026-10-12',history:fx.transactions.filter(t=>t.fixed_id===13),cats:fx.categories}).status,'already');
 // Дата запису на межі місяця: подія 01.11, натиснули 31.10, запис закриває листопад
 assert.equal(rep.payDate('2026-10-31','2026-11-01',false),'2026-11-01');
 assert.equal(rep.payDate('2026-11-03','2026-11-01',false),'2026-11-03');
 assert.deepEqual(rep.payRange(false,'2026-12-05'),['2026-12-01','2027-01-01']);
});
