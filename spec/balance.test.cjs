// v148: баланс = власні мінус борг кредиток, одна формула для плитки «Баланс» і графіка «Гроші в часі»
// (далі календар і операції). Функції беруться з index.html рівно так, як вони там лежать.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const line=name=>{const l=html.split(/\r?\n/).find(l=>l.startsWith('function '+name+'('));assert.ok(l,'немає '+name);return l;};
const F=new Function([...['pastOwnSeries','balShift','balanceNowCents','balanceAfterCents','balancePast','kpiFunds'].map(line),
 'return {pastOwnSeries,balShift,balanceNowCents,balanceAfterCents,balancePast,kpiFunds};'].join('\n'))();
const stamp='2026-10-12T07:00:00Z',ASOF='2026-10-12';
const salary={rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:51000,salary_amount:51000};
const accounts=()=>[{id:1,name:'Ощадбанк',kind:'debit',balance:2519,debt:0,balance_updated_at:stamp},
 {id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:29070.45,credit_limit:50000,debt_month:'2026-10-01',balance_updated_at:stamp},
 {id:4,name:'ПриватБанк',kind:'credit',balance:0,debt:9256.55,credit_limit:30000,debt_month:'2026-09-01',balance_updated_at:stamp}];
// історія до мітки балансу: витрата з кредитки 10.10, погашення кредитки з дебетової 09.10 (пара), дохід 08.10, витрата з дебетової 11.10
const tx=(id,account_id,type,amount,date)=>({id,account_id,type,amount,date,created_at:date+'T06:00:00Z',source:'manual'});
const history=[tx(1,1,'income',5000,'2026-10-08'),tx(2,1,'expense',3000,'2026-10-09'),tx(3,4,'income',3000,'2026-10-09'),tx(4,3,'expense',1200,'2026-10-10'),tx(5,1,'expense',400,'2026-10-11')];
const engine=async()=>(await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href)).financeProjection;

test('today balance on the chart equals the Balance tile; history moves it by the owner rules',async()=>{
 const financeProjection=await engine();
 const pr=financeProjection({accounts:accounts(),salary,fixed:[],credits:[],categories:[],transactions:history},{asof:ASOF,through:'2027-01-10'});
 const tile=F.kpiFunds(pr).balance;
 assert.equal(tile,251900-3832700);assert.equal(F.balanceNowCents(pr),tile);
 const past=F.balancePast(pr,history,['1','3','4',''],['1',''],'2026-10-07','2026-10-12');
 const by=Object.fromEntries(past.map(x=>[x.date,x]));
 assert.equal(past[past.length-1].cents,tile,'остання точка минулого = плитка «Баланс»');
 assert.equal(past[past.length-1].own,251900,'власні сьогодні = плитка «Власні»');
 assert.equal(by['2026-10-11'].cents-by['2026-10-10'].cents,-40000,'витрата з дебетової');
 assert.equal(by['2026-10-10'].cents-by['2026-10-09'].cents,-120000,'витрата з кредитки зменшує баланс у свій день');
 assert.equal(by['2026-10-10'].own-by['2026-10-09'].own,0,'а власні не змінює');
 assert.equal(by['2026-10-09'].cents-by['2026-10-08'].cents,0,'погашення кредитки баланс не змінює');
 assert.equal(by['2026-10-09'].own-by['2026-10-08'].own,-300000,'а власні зменшує');
 assert.equal(by['2026-10-08'].cents-by['2026-10-07'].cents,500000,'дохід збільшує');
});

test('forecast continues today balance without a jump, also with a negative own account',async()=>{
 const financeProjection=await engine();
 for(const bal of [2519,-3000]){
  const acc=accounts();acc.push({id:2,name:'monobank',kind:'debit',mono_account_id:'m2',balance:bal,debt:0,balance_updated_at:stamp});
  const pr=financeProjection({accounts:acc,salary,fixed:[],credits:[],categories:[],transactions:[]},{asof:ASOF,through:'2027-01-10'});
  const d0=pr.days[0];assert.equal(d0.date,ASOF);
  assert.equal(F.balanceAfterCents(pr,d0.closingCashCents,d0.debtCents,d0.arrearsCents),F.balanceNowCents(pr),'сьогодні без подій: прогноз = плитка');
  // v150: рушій стартує з власних, мінусовий рахунок стає нестачею; власні дня не мінусові
  assert.equal(d0.closingCashCents,pr.snapshot.positiveOwnCents);assert.ok(pr.days.every(d=>d.closingCashCents>=0));
  if(bal<0)assert.notEqual(pr.snapshot.cashCents,pr.snapshot.positiveOwnCents,'фікстура з мінусовим рахунком');
  // погашення кредитки баланс не змінює: день погашення Привату 21.10 без змін від погашення
  const rep=pr.events.find(e=>e.kind==='repay'&&e.id.startsWith('repay:4:'));
  assert.equal(rep.date,'2026-10-21');assert.equal(rep.cashDeltaCents,rep.debtDeltaCents,'каса і борг зменшуються на ту саму суму');
 }
});

// v148 «Бюджет періоду» на старт періоду: власні на початок дня виплати + надходження цього дня.
// v151 (знахідка 2): далі той самий розподіл виплати, що в рушії (payoutBudget): резерв дебетових обовʼязкових періоду; v152: погашення на кожній виплаті, належне лише в день погашення
// (21-го) погашення спершу належного, далі максимум, лишаючи 15 000 ₴; A = власні − резерв − погашення; бюджет min(20 000, A), якщо A > 15 000,
// інакше 15 000. Щоденні = Доступно / днів до кінця періоду включно з сьогодні (знахідка 4).
const rule=a=>a>1500000?Math.min(2000000,a):1500000;
test('period budget at period start: payout day income, debit-only mandatory reserved, every payout repays (due only on the 21st), engine rule 15/20',async()=>{
 const E=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href),financeProjection=E.financeProjection;
 const lines=html.split(/\r?\n/),L=lines.find(l=>l.includes('const pbIso='));
 const pb=L.slice(L.indexOf('const pbIso='),L.indexOf('/*',L.indexOf('const pbIso=')));
 const G=new Function('financeProjection','payoutBudget','repayDate',[pb,...['pastOwnSeries','balShift','balanceNowCents','balancePast','periodBudgetStart','perDayOf'].map(line),'return {periodBudgetStart};'].join('\n'))(financeProjection,E.payoutBudget,E.repayDate);
 const acc=accounts();acc[0].balance=60000;
 const fixed=[{id:'f1',name:'Інтернет',amount:300,day_of_month:8,type:'expense',active:true}];
 const credits=[{id:7,name:'Телефон',monthly_amount:4643,payment_day:12,start_year:2026,start_month:9,total_payments:12}];
 // зарплата 06.10 (v152: кожна виплата гасить борг максимум, як рушій): належного немає (не день погашення), але борг гаситься, лишаючи 15 000
 const txs=[tx(11,1,'income',51000,'2026-10-06'),{...tx(12,1,'expense',300,'2026-10-08'),fixed_id:'f1'},tx(13,3,'expense',1200,'2026-10-10')];
 const fi={accounts:acc,salary,fixed,credits,categories:[],transactions:txs};
 const pr=financeProjection(fi,{asof:ASOF,through:'2027-01-10'});
 assert.equal(pr.currentPeriod.start,'2026-10-06');
 const r=G.periodBudgetStart(pr,fi,txs,['1','3','4',''],['1',''],ASOF);
 const ownStart=6000000-5100000+30000,debtStart=3832700-120000,reserve=30000+464300;
 assert.equal(r.own,ownStart,'власні на початок 06.10');assert.equal(r.income,5100000,'надходження 06.10');assert.equal(r.ownAt,ownStart+5100000);
 assert.equal(r.reserve,reserve,'резерв дебетових обовʼязкових періоду, разом зі сплаченим 08.10');assert.equal(r.debt,debtStart,'борг кредиток на 06.10');
 assert.equal(r.repayDay,false);assert.equal(r.due,0);assert.equal(r.repay,Math.min(debtStart,Math.max(0,r.ownAt-reserve-1500000)));assert.equal(r.repay,debtStart,'увесь борг на 06.10');assert.equal(r.A,r.ownAt-reserve-r.repay);assert.equal(r.budget,rule(r.A));assert.equal(r.budget,1823000);
 assert.equal(r.days,15);assert.equal(r.avail,r.budget-pr.currentPeriod.actualVariableCents);assert.equal(r.daily,Math.round(r.avail/9),'доступно / 9 днів 12.10-20.10');
 // аванс 21.10 (день погашення): належне = борг на 20.10 мінус кредитні витрати жовтня до 20.10; гаситься максимум, лишаючи 15 000
 const acc2=accounts().map(a=>({...a,balance_updated_at:'2026-10-25T07:00:00Z'}));acc2[0].balance=60000;
 const txs2=[tx(21,1,'income',51000,'2026-10-21'),tx(22,3,'expense',2000,'2026-10-05'),tx(23,3,'expense',500,'2026-10-15'),tx(24,4,'expense',700,'2026-10-22')];
 const fi2={accounts:acc2,salary,fixed,credits,categories:[],transactions:txs2},pr2=financeProjection(fi2,{asof:'2026-10-25',through:'2027-01-10'});
 assert.equal(pr2.currentPeriod.start,'2026-10-21');
 const r2=G.periodBudgetStart(pr2,fi2,txs2,['1','3','4',''],['1',''],'2026-10-25');
 const debt2=3832700-70000;
 assert.equal(r2.repayDay,true);assert.equal(r2.ownAt,6000000);assert.equal(r2.reserve,0);assert.equal(r2.debt,debt2);assert.equal(r2.due,debt2-250000);
 assert.deepEqual(E.payoutBudget(r2.ownAt,r2.reserve,r2.debt,r2.due,true),{repayCents:r2.repay,availableCents:r2.A,targetCents:r2.budget});
 assert.equal(r2.repay,debt2,'увесь борг: власних вистачає, лишаючи 15 000');assert.equal(r2.A,6000000-debt2);assert.equal(r2.budget,rule(r2.A));
 assert.equal(r2.daily,Math.round(r2.avail/12),'доступно / 12 днів 25.10-05.11');
 // без власних грошей: підлога 15 000 ₴
 const fi0={...fi,accounts:accounts(),transactions:[]},pr0=financeProjection(fi0,{asof:ASOF,through:'2027-01-10'});
 assert.equal(G.periodBudgetStart(pr0,fi0,[],['1','3','4',''],['1',''],ASOF).budget,1500000);
});
