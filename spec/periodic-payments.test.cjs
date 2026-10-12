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
 assert.equal(repay.length,1);assert.equal(repay[0].amountCents,50000);assert.equal(repay[0].date,'2026-10-21');
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
