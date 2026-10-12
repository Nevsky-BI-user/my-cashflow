// v143: щотижневі постійні платежі, розстрочки за планом і з credit_id, untilPayout, борг усіх карток.
// Кожен випадок проганяється в TS і Python (повний паритет) плюс перевірка каси й боргу по днях.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const fixture=()=>({accounts:[{id:1,kind:'debit',balance:2800,debt:0},{id:2,kind:'credit',balance:0,debt:16000,credit_limit:20000}],fixed:[{id:1,name:'Payment',type:'expense',amount:28000,day_of_month:25,credit_ok:true}],credits:[],salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:50000},categories:[40,20,15,10,10,5].map((w,i)=>({id:String(i+1),name:'Category '+i,type:'expense',budget_limit:w})),transactions:[]});
const cleaning=(extra={})=>({id:7,name:'Прибирання',type:'expense',amount:500,day_of_month:1,period:'week',weekday:1,credit_ok:false,...extra});
const laptop=(extra={})=>({id:3,name:'Ноутбук',monthly_amount:1000,payment_day:20,start_year:2026,start_month:0,total_payments:12,source:'privat',credit_ok:false,...extra});
const tx=(id,date,extra={})=>({id,account_id:1,type:'expense',amount:500,date,created_at:date+'T08:00:00Z',...extra});
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(data,opts={}){
 const input=JSON.stringify([{data,asof:'2026-10-10',through:'2026-12-31',...opts}]);
 const ts=run(process.execPath,['spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 assert.deepEqual(ts,py,'full TS/Python parity');
 assert.equal(new Set(ts.events.map(e=>e.id)).size,ts.events.length);
 let cash=ts.snapshot.cashCents,debt=ts.snapshot.creditDebtCents;
 for(const d of ts.days){assert.equal(d.openingCashCents,cash);for(const e of ts.events.filter(e=>e.date===d.date)){cash+=e.cashDeltaCents;debt+=e.debtDeltaCents;assert.equal(e.cashAfterCents,cash);assert.equal(e.debtAfterCents,debt);}assert.equal(d.closingCashCents,cash);assert.equal(d.debtCents,debt);}
 return ts;
}
const isoDay=d=>(new Date(d+'T00:00:00Z').getUTCDay()+6)%7+1;
const ids=(r,prefix)=>r.events.filter(e=>e.id.startsWith(prefix)).map(e=>e.id);

test('weekly payment: event on every matching weekday, dated id, monthly ids unchanged',()=>{
 const d=fixture();d.fixed.push(cleaning());const r=both(d);
 const weekly=r.events.filter(e=>e.id.startsWith('fixed:7:'));
 assert.ok(weekly.length>=11);
 for(const e of weekly){assert.equal(isoDay(e.date),1);assert.equal(e.id,'fixed:7:'+e.date);assert.equal(e.kind,'mandatory');assert.equal(e.amountCents,50000);assert.ok(e.date>='2026-10-10');}
 assert.equal(weekly[0].date,'2026-10-12');
 for(let i=1;i<weekly.length;i++)assert.equal((Date.parse(weekly[i].date)-Date.parse(weekly[i-1].date))/86400000,7);
 assert.deepEqual(ids(r,'fixed:1:'),['fixed:1:2026-10','fixed:1:2026-11','fixed:1:2026-12']);
});

test('weekly payment closes by a fact in the same Monday-Sunday week and is not variable actual',()=>{
 const d=fixture();d.fixed.push(cleaning({weekday:5}));d.transactions=[tx(1,'2026-10-12',{fixed_id:7})];
 const r=both(d,{asof:'2026-10-12'});
 assert.ok(!ids(r,'fixed:7:').includes('fixed:7:2026-10-16'),'paid week has no event');
 assert.ok(ids(r,'fixed:7:').includes('fixed:7:2026-10-23'),'next week stays planned');
 assert.equal(r.currentPeriod.actualVariableCents,0);
});

test('weekly week spans a month boundary: Monday fact closes the Wednesday of the next month',()=>{
 const d=fixture();d.fixed.push(cleaning({weekday:3}));d.transactions=[tx(1,'2026-11-30',{fixed_id:7})];
 const r=both(d,{asof:'2026-11-30'});
 assert.ok(!ids(r,'fixed:7:').includes('fixed:7:2026-12-02'));
 assert.ok(ids(r,'fixed:7:').includes('fixed:7:2026-12-09'));
});

test('past unpaid week has no event, today unpaid stays an event like monthly',()=>{
 const d=fixture();d.fixed.push(cleaning());
 assert.equal(ids(both(d,{asof:'2026-10-14'}),'fixed:7:')[0],'fixed:7:2026-10-19');
 assert.equal(ids(both(d,{asof:'2026-10-12'}),'fixed:7:')[0],'fixed:7:2026-10-12');
});

test('weekly without a valid weekday has no events; missing period means monthly',()=>{
 const d=fixture();d.fixed.push(cleaning({weekday:null}),cleaning({id:8,weekday:9}),{id:9,name:'Старий',type:'expense',amount:100,day_of_month:15});
 const r=both(d);
 assert.equal(ids(r,'fixed:7:').length,0);assert.equal(ids(r,'fixed:8:').length,0);
 assert.deepEqual(ids(r,'fixed:9:'),['fixed:9:2026-10','fixed:9:2026-11','fixed:9:2026-12']);
});

test('installment due today or earlier is paid by plan, future months stay',()=>{
 const d=fixture();d.credits=[laptop({payment_day:10})];
 const r=both(d);
 assert.ok(!ids(r,'installment:3:').includes('installment:3:2026-10'));
 assert.deepEqual(ids(r,'installment:3:'),['installment:3:2026-11','installment:3:2026-12']);
});

test('expense with credit_id closes its month installment even before the due date and is not variable',()=>{
 const d=fixture();d.credits=[laptop()];d.transactions=[tx(1,'2026-10-08',{amount:1000,credit_id:3})];
 const r=both(d);
 assert.deepEqual(ids(r,'installment:3:'),['installment:3:2026-11','installment:3:2026-12']);
 assert.equal(r.currentPeriod.actualVariableCents,0);
 // та сама витрата без привʼязки: змінна, а платіж місяця лишається
 const open=both(Object.assign(fixture(),{credits:[laptop()],transactions:[tx(1,'2026-10-08',{amount:1000})]}));
 assert.ok(ids(open,'installment:3:').includes('installment:3:2026-10'));
 assert.equal(open.currentPeriod.actualVariableCents,100000);
});

test('untilPayout: own cash minus mandatory and fees before the next payout, card debt not subtracted',()=>{
 let r=both(fixture());
 assert.deepEqual(r.untilPayout,{end:'2026-10-21',days:11,cents:280000,dailyCents:Math.floor(280000/11)});
 const d=fixture();d.fixed.push(cleaning());r=both(d);
 assert.equal(r.untilPayout.cents,280000-2*50000);
 assert.equal(r.untilPayout.dailyCents,Math.floor((280000-2*50000)/11));
 const poor=fixture();poor.fixed.push(cleaning({amount:5000}));r=both(poor);
 assert.equal(r.untilPayout.cents,280000-2*500000);assert.equal(r.untilPayout.dailyCents,0);
 const none=fixture();delete none.salary;assert.equal(both(none).untilPayout,null);
});

test('current period keeps actual cash minus mandatory, without the card debt',()=>{
 const r=both(fixture());const cur=r.periods.find(p=>p.basis==='current');
 assert.equal(cur.debtReserveCents,0);
 assert.equal(cur.availableCents,r.snapshot.cashCents-cur.mandatoryCents);
 assert.equal(r.nextPlan.debtCents,1600000);
});

test('creditDebtCents sums every account debt and a debit card with debt is repaid once',()=>{
 const d=fixture();d.accounts.push({id:3,kind:'debit',balance:1000,debt:500,credit_limit:30000,mono_account_id:'m',debt_month:'2026-10'});
 const r=both(d);
 assert.equal(r.snapshot.creditDebtCents,r.snapshot.accounts.reduce((s,a)=>s+a.debtCents,0));
 assert.equal(r.snapshot.creditDebtCents,1650000);
 const repay=r.events.filter(e=>e.kind==='repay'&&e.accountId===3);
 assert.equal(repay.length,1);assert.equal(repay[0].amountCents,50000);/* v146: борг жовтня гаситься з виплати 21.11 (субота, виплата 20.11) */assert.equal(repay[0].date,'2026-11-20');
 assert.equal(r.days[r.days.length-1].debtCents,0);
 assert.equal(r.nextPlan.debtCents,1650000);
});

test('legacy nextPeriodPlan and fixedPaid know weekly payments (TS/Python parity)',async()=>{
 const d=fixture();d.fixed.push(cleaning());d.transactions=[tx(1,'2026-10-27',{fixed_id:7})];
 const input=JSON.stringify([{data:d,asof:'2026-10-26'}]);
 const ts=run(process.execPath,['spec/ts_next_period.mts'],input),py=run(python,['scripts/budget_pool.py','--next-period'],input);
 assert.deepEqual(ts,py);
 // оплата 27.10 закриває лише тиждень 26.10; у вікні плану всі понеділки не оплачені
 let mondays=0;for(let t=Date.parse(ts.start+'T00:00:00Z');t<Date.parse(ts.end+'T00:00:00Z');t+=86400000)if(new Date(t).getUTCDay()===1)mondays++;
 assert.ok(mondays>=2);
 assert.equal(ts.mandatoryCents,mondays*50000);
 const {fixedPaid}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 assert.deepEqual(fixedPaid(d.transactions),['7|2026-10','7|W2026-10-26']);
});

// Темп щоденних витрат поточного періоду: більше з 15 000 ₴ на весь період і untilPayout на дні від завтра до дня перед виплатою.
test('current period tempo: max of the 15 000 floor over the whole period and untilPayout over the days left',()=>{
 const sumVar=(r,a,b)=>r.events.filter(e=>e.kind==='variable'&&e.date>=a&&e.date<=b).reduce((s,e)=>s+e.amountCents,0);
 // підлога: 06.10-20.10 = 15 дн., від 11.10 лишається 10 дн., untilPayout 2 800 ₴ менше
 let r=both(fixture());
 assert.equal(r.currentPeriod.start,'2026-10-06');assert.equal(r.currentPeriod.periodDays,15);assert.equal(r.currentPeriod.leftDays,10);
 assert.equal(r.currentPeriod.remainingTargetCents,1000000);assert.equal(r.currentPeriod.dailyCents,100000);
 assert.equal(r.currentPeriod.targetCents,r.currentPeriod.actualVariableCents+1000000);
 assert.equal(sumVar(r,'2026-10-11','2026-10-20'),1000000);assert.equal(sumVar(r,'2026-10-10','2026-10-10'),0);
 assert.ok(r.days.filter(d=>d.date>='2026-10-11'&&d.date<='2026-10-20').every(d=>d.variableCents===100000));
 // факт періоду не зменшує темп
 const spent=fixture();spent.transactions=[tx(1,'2026-10-08',{amount:3000})];r=both(spent);
 assert.equal(r.currentPeriod.actualVariableCents,300000);assert.equal(r.currentPeriod.remainingTargetCents,1000000);
 // вільних коштів більше за підлогу: темп = untilPayout на 10 дн., копійки без втрат
 const rich=fixture();rich.accounts[0].balance=50000.07;r=both(rich);
 assert.equal(r.untilPayout.cents,5000007);assert.equal(r.currentPeriod.remainingTargetCents,5000007);
 assert.equal(sumVar(r,'2026-10-11','2026-10-20'),5000007);assert.equal(r.currentPeriod.dailyCents,500000.7);
 // останній день перед виплатою: днів не лишилось, подій variable поточного періоду немає
 r=both(fixture(),{asof:'2026-10-20'});
 assert.equal(r.currentPeriod.leftDays,0);assert.equal(r.currentPeriod.remainingTargetCents,0);assert.equal(r.currentPeriod.dailyCents,0);
 assert.equal(sumVar(r,'2026-10-20','2026-10-20'),0);
});

// v144: ліміти категорій у гривнях (limit_abs). Сума в гривнях іде по черзі sort_order (null в кінці, рівність: id),
// кожна min(ліміт, що лишилось); залишок ділиться за вагами; ваг немає: «Не розподілено». budget_limit ₴-категорії ігнорується.
const absCat=(id,limit_abs,sort_order=null,extra={})=>({id,name:'Category '+id,type:'expense',budget_limit:99,limit_abs,sort_order,...extra});
const weightCat=(id,w)=>({id,name:'Category '+id,type:'expense',budget_limit:w});
const total=(p,id)=>(p.categories.find(c=>c.id===id)||{}).totalCents;
// Еталон черги: [[id, ліміт у копійках]] уже в порядку sort_order.
const queue=(T,list)=>{let left=T;return Object.fromEntries(list.map(([id,cap])=>{const n=Math.min(cap,left);left-=n;return [id,n];}).concat([['__left',left]]));};
// Суми категорій дорівнюють цілі періоду, розклад по днях сходиться з totalCents, порядок рядків за id (unallocated в кінці).
const checkTotals=r=>{for(const p of r.periods){
 const T=p.schedule.length?(p.basis==='current'?r.currentPeriod.remainingTargetCents:p.targetCents):0;
 assert.equal(p.categories.reduce((s,c)=>s+c.totalCents,0),T,p.basis+' totals = target');
 for(const c of p.categories)assert.equal(p.schedule.reduce((s,d)=>s+d.byCategory.find(x=>x.id===c.id).amountCents,0),c.totalCents,p.basis+' schedule '+c.id);
 const ids=p.categories.map(c=>c.id).filter(id=>id!=='unallocated');assert.deepEqual(ids,ids.slice().sort());
 if(p.categories.some(c=>c.id==='unallocated'))assert.equal(p.categories[p.categories.length-1].id,'unallocated');
}};

test('limit_abs only: each category gets its sum, the rest goes to Не розподілено',()=>{
 const d=fixture();d.categories=[absCat('1',3000,2),absCat('2',2000,1)];
 const r=both(d);checkTotals(r);
 const cur=r.periods.find(p=>p.basis==='current'),head=r.periods.find(p=>p.basis==='headline');
 assert.deepEqual(cur.categories,[{id:'1',name:'Category 1',weight:0,limitAbsCents:300000,totalCents:300000},{id:'2',name:'Category 2',weight:0,limitAbsCents:200000,totalCents:200000},{id:'unallocated',name:'Не розподілено',weight:1,totalCents:1000000-500000}]);
 assert.equal(total(head,'1'),300000);assert.equal(total(head,'2'),200000);assert.equal(total(head,'unallocated'),head.targetCents-500000);
 assert.ok(r.events.some(e=>e.id.endsWith(':unallocated')&&e.kind==='variable'));
});

test('limit_abs plus weights: the sum first, the rest by weights without loss, no Не розподілено',()=>{
 const d=fixture();d.categories=[absCat('1',3000),...[20,15,10,10,5].map((w,i)=>weightCat(String(i+2),w))];
 const r=both(d);checkTotals(r);
 for(const p of r.periods){const T=p.basis==='current'?r.currentPeriod.remainingTargetCents:p.targetCents,R=T-300000;
  assert.equal(total(p,'1'),300000);assert.ok(!p.categories.some(c=>c.id==='unallocated'));
  [20,15,10,10,5].forEach((w,i)=>assert.ok(Math.abs(total(p,String(i+2))-R*w/60)<1,p.basis+' weight share'));}
});

test('limit_abs above the budget: queue by sort_order (null last, ties by id), partial then zero',()=>{
 const d=fixture();d.categories=[absCat('1',5000,2),absCat('2',5000,null),absCat('3',8000,1),absCat('4',1000,2),weightCat('5',10)];
 const r=both(d);checkTotals(r);
 for(const p of r.periods){const T=p.basis==='current'?r.currentPeriod.remainingTargetCents:p.targetCents;
  const q=queue(T,[['3',800000],['1',500000],['4',100000],['2',500000]]);
  for(const id of ['1','2','3','4'])assert.equal(total(p,id),q[id],p.basis+' '+id);
  assert.equal(total(p,'5'),q.__left);}
 // поточний період: 10 000 ₴ = 8 000 (sort 1) + 2 000 частково (sort 2, id 1), далі по 0
 const cur=r.periods.find(p=>p.basis==='current');
 assert.deepEqual(cur.categories.map(c=>c.totalCents),[200000,0,800000,0,0]);
});

test('limit_abs = 0 gives zero and keeps the weights for the others',()=>{
 const d=fixture();d.categories[0]=absCat('1',0,1);
 const z=fixture();z.categories[0].budget_limit=0;
 const r=both(d),w=both(z);checkTotals(r);
 r.periods.forEach((p,i)=>{assert.equal(total(p,'1'),0);assert.deepEqual(p.categories.map(c=>c.totalCents),w.periods[i].categories.map(c=>c.totalCents));});
});

test('current period: the sum share is the limit minus the category fact since the period start, not below 0',()=>{
 const d=fixture();d.categories=[absCat('1',3000,1),...[20,15,10,10,5].map((w,i)=>weightCat(String(i+2),w))];
 d.transactions=[tx(1,'2026-10-08',{amount:1200,category_id:'1'}),
  tx(2,'2026-10-09',{amount:700,category_id:1}),
  tx(3,'2026-10-08',{amount:900,category_id:'1',fixed_id:1}),
  tx(4,'2026-10-08',{amount:800,category_id:'1',credit_id:99}),
  tx(5,'2026-10-05',{amount:600,category_id:'1'}),
  tx(6,'2026-10-08',{amount:500,category_id:'2'}),
  tx(7,'2026-10-08',{amount:400})];
 let r=both(d);checkTotals(r);
 const cur=r.periods.find(p=>p.basis==='current');
 assert.equal(total(cur,'1'),300000-120000-70000);
 assert.equal(cur.categories.find(c=>c.id==='1').limitAbsCents,300000);
 for(const p of r.periods.filter(p=>p.basis!=='current'))assert.equal(total(p,'1'),300000);
 // факт більший за ліміт: частка 0, усе від завтра за вагами
 d.transactions.push(tx(8,'2026-10-09',{amount:5000,category_id:'1'}));r=both(d);checkTotals(r);
 assert.equal(total(r.periods.find(p=>p.basis==='current'),'1'),0);
 assert.equal(total(r.periods.find(p=>p.basis==='headline'),'1'),300000);
});

test('limit_abs and sort_order as strings from numeric columns: same rounding and order in TS and Python',()=>{
 const d=fixture();d.categories=[absCat('1','1234.565','2'),absCat('2','99.994','1'),weightCat('3',10)];
 const r=both(d);checkTotals(r);
 const head=r.periods.find(p=>p.basis==='headline');
 assert.equal(head.categories.find(c=>c.id==='1').limitAbsCents,123457);assert.equal(head.categories.find(c=>c.id==='2').limitAbsCents,9999);
 const cur=r.periods.find(p=>p.basis==='current');
 assert.deepEqual(cur.categories.map(c=>c.totalCents),[123457,9999,1000000-123457-9999]);
});

test('null limit_abs and any sort_order: output identical to the weights-only plan',()=>{
 const d=fixture();d.categories=d.categories.map((c,i)=>({...c,limit_abs:null,sort_order:[3,null,1][i%3]}));
 assert.deepEqual(both(d),both(fixture()));
});

test('legacy nextPeriodPlan applies limit_abs the same way (TS/Python parity)',()=>{
 const plan=d=>{const input=JSON.stringify([{data:d,asof:'2026-10-10'}]);
  const ts=run(process.execPath,['spec/ts_next_period.mts'],input),py=run(python,['scripts/budget_pool.py','--next-period'],input);
  assert.deepEqual(ts,py);assert.equal(ts.categories.reduce((s,c)=>s+c.totalCents,0),ts.targetCents);
  for(const c of ts.categories)assert.equal(ts.schedule.reduce((s,x)=>s+x.byCategory.find(y=>y.id===c.id).amountCents,0),c.totalCents);
  return ts;};
 const d=fixture();d.categories=[absCat('1',3000,2),absCat('2',2000,1),...[10,5].map((w,i)=>weightCat(String(i+3),w))];
 let p=plan(d);
 assert.equal(p.categories.find(c=>c.id==='1').totalCents,300000);assert.equal(p.categories.find(c=>c.id==='2').totalCents,200000);
 assert.ok(!p.categories.some(c=>c.id==='unallocated'));
 // лише суми в гривнях і більше за бюджет: черга sort_order, без ваг залишок у «Не розподілено»
 const only=fixture();only.categories=[absCat('1',3000,2),absCat('2',2000,1)];p=plan(only);
 assert.deepEqual(p.categories.map(c=>c.id),['1','2','unallocated']);
 assert.equal(p.categories[2].totalCents,p.targetCents-500000);
 const big=fixture();big.categories=[absCat('1',1e6,2),absCat('2',1e6,1)];p=plan(big);
 const q=queue(p.targetCents,[['2',1e8],['1',1e8]]);
 assert.deepEqual(p.categories.map(c=>[c.id,c.totalCents]),[['1',q['1']],['2',q['2']]]);
 // null limit_abs: як раніше
 const legacy=fixture();legacy.categories=legacy.categories.map(c=>({...c,limit_abs:null,sort_order:1}));
 assert.deepEqual(plan(legacy),plan(fixture()));
});

// v145: budget_limit null при заданому limit: Python бере limit, як TS (budget_limit ?? limit), в обох режимах
test('budget_limit null falls back to limit in TS and Python (finance and next period)',()=>{
 const d=fixture();d.categories=d.categories.map((c,i)=>i<3?{id:c.id,name:c.name,type:c.type,budget_limit:null,limit:c.budget_limit}:c);
 const r=both(d),ref=both(fixture());
 assert.deepEqual(r.currentPeriod,ref.currentPeriod);assert.deepEqual(r.nextPlan,ref.nextPlan);
 const input=JSON.stringify([{data:d,asof:'2026-10-10'}]);
 const ts=run(process.execPath,['spec/ts_next_period.mts'],input),py=run(python,['scripts/budget_pool.py','--next-period'],input);
 assert.deepEqual(ts,py);
 assert.ok(ts.categories.filter(c=>['1','2','3'].includes(c.id)).every(c=>c.totalCents>0));
});

// v149 (міграція 29): end_date включно; після неї подій немає, щомісяця і щотижня; постійний дохід type 'income'
test('fixed end_date: monthly events stop after the last date (inclusive)',()=>{
 let d=fixture();d.fixed[0].end_date='2026-11-25';let r=both(d);
 assert.deepEqual(ids(r,'fixed:1:'),['fixed:1:2026-10','fixed:1:2026-11']);
 d=fixture();d.fixed[0].end_date='2026-11-24';r=both(d);
 assert.deepEqual(ids(r,'fixed:1:'),['fixed:1:2026-10']);
 assert.ok(r.events.every(e=>!e.id.startsWith('fixed:1:')||e.date<='2026-11-24'));
});

test('fixed end_date: weekly events stop after the last date (inclusive)',()=>{
 const d=fixture();d.fixed.push(cleaning({end_date:'2026-10-26'}));const r=both(d);
 assert.deepEqual(ids(r,'fixed:7:'),['fixed:7:2026-10-12','fixed:7:2026-10-19','fixed:7:2026-10-26']);
 const e=fixture();e.fixed.push(cleaning({end_date:'2026-10-25'}));
 assert.deepEqual(ids(both(e),'fixed:7:'),['fixed:7:2026-10-12','fixed:7:2026-10-19']);
});

test('fixed income raises cash on its date, is not mandatory and ends with end_date',()=>{
 const plain=both(fixture());
 const d=fixture();d.fixed.push({id:9,name:'Оренда гаража',type:'income',amount:900,day_of_month:15,end_date:'2026-11-14'});
 const r=both(d);
 const inc=r.events.filter(e=>e.id.startsWith('fixed:9:'));
 assert.deepEqual(inc.map(e=>e.id),['fixed:9:2026-10']);
 assert.equal(inc[0].kind,'income');assert.equal(inc[0].cashDeltaCents,90000);assert.equal(inc[0].creditEligible,false);
 const day=(x,iso)=>x.days.find(v=>v.date===iso);
 assert.equal(day(r,'2026-10-14').closingCashCents,day(plain,'2026-10-14').closingCashCents);
 assert.equal(day(r,'2026-10-15').closingCashCents-day(plain,'2026-10-15').closingCashCents,90000);
 assert.equal(r.nextPlan.mandatoryCents,plain.nextPlan.mandatoryCents,'income is not mandatory');
 assert.ok(r.events.filter(e=>e.kind==='mandatory').every(e=>!e.id.startsWith('fixed:9:')));
});
