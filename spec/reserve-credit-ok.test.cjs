// v153 (власник обрав А+Б після «тут одразу має закритись кредитки з власних коштів»):
// А. кожна виплата резервує до наступної виплати не лише дебетові обовʼязкові й комісії, а й обовʼязкові з кредитки (credit_ok):
//    вони платяться з власних, кредитка під них не наростає; дебетовий платіж має пріоритет над credit_ok у межах резерву.
// Б. накопичення = max(0, надлишок − нестача до наступної виплати); після А нестача за подіями періоду дорівнює 0, тож накопичення = надлишок.
// v153 доповнення 7: накопичення відкладаються не з нової виплати, а з залишку попереднього періоду в день наступної виплати;
//    без нестачі залишок дорівнює надлишку попередньої виплати понад бюджет (поріг 10 000 більше не діє).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const stamp='2026-10-12T07:00:00Z';
const ASOF='2026-10-12',THROUGH='2027-01-31';
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(d){
 const input=JSON.stringify([{data:d,asof:ASOF,through:THROUGH}]);
 const ts=run(process.execPath,[process.env.TS_FINANCE||'spec/ts_finance.mts'],input),py=run(python,['scripts/budget_pool.py','--finance'],input);
 if(!process.env.TS_FINANCE)assert.deepEqual(ts,py,'full TS/Python parity');
 return ts;
}
// дохід покриває все: 60 000 двічі на місяць; обовʼязкові з кредитки 10 800 (25-го) і 1 400 (15-го), дебетова оренда 7 000 (10-го)
const covered=()=>({
 accounts:[{id:1,name:'Ощадбанк',kind:'debit',balance:3000,debt:0,balance_updated_at:stamp},
  {id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:5000,credit_limit:50000,debt_month:'2026-10-01',balance_updated_at:stamp}],
 salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:60000,salary_amount:60000},
 fixed:[{id:1,name:'Оренда',type:'expense',amount:7000,day_of_month:10,credit_ok:false,active:true},
  {id:2,name:'Звʼязок',type:'expense',amount:1400,day_of_month:15,credit_ok:true,active:true},
  {id:3,name:'Підписка',type:'expense',amount:10800,day_of_month:25,credit_ok:true,active:true}],
 credits:[],categories:[{id:'1',name:'Їжа',type:'expense',budget_limit:70},{id:'2',name:'Інше',type:'expense',budget_limit:30}],transactions:[]});
const sumOf=(r,a,b,f)=>r.events.filter(e=>e.date>=a&&e.date<b&&f(e)).reduce((n,e)=>n+e.amountCents,0);
const okEv=e=>e.kind==='mandatory'&&e.creditEligible===true&&e.funding!=='credit';
const debitEv=e=>e.kind==='fee'||(e.kind==='mandatory'&&e.creditEligible!==true&&e.funding!=='credit');

test('A: credit_ok mandatory payments are reserved at each payout and paid from own funds, card debt does not regrow between payouts',()=>{
 const r=both(covered());
 const pays=r.periods.filter(p=>p.payoutCents>0);
 assert.ok(pays.length>=6,'виплат '+pays.length);
 for(const p of pays){
  const want=Math.min(p.ownCents,sumOf(r,p.start,p.end,debitEv)+sumOf(r,p.start,p.end,okEv));
  assert.equal(p.reserveCents,want,p.start+': резерв без credit_ok');
 }
 const ok=r.events.filter(e=>okEv(e)&&e.date>pays[0].start);
 assert.ok(ok.length>=4,'обовʼязкових з кредитки '+ok.length);
 for(const e of ok){assert.equal(e.debtDeltaCents,0,e.id+' пішов у борг');assert.equal(e.cashDeltaCents,-e.amountCents,e.id+' не з власних');}
 // перед кожною наступною виплатою кредитні 0: між виплатами борг не наростає
 for(const p of pays.slice(1)){const prev=r.days.filter(d=>d.date<p.start).pop();assert.equal(prev.debtCents,0,'кредитні перед '+p.start+': '+prev.debtCents);}
 for(const d of r.days)assert.ok(d.closingCashCents>=0&&d.minCashCents>=0&&d.arrearsCents===0,d.date);
});

test('B: savings are the surplus over the budget minus the projected shortfall until the next payout (zero shortfall once A reserves everything)',()=>{
 const r=both(covered());
 let saved=0,prev=null;
 for(const p of r.periods.filter(p=>p.payoutCents>0)){
  // нестача: найглибший мінус власних після розподілу за подіями періоду (як у рушії, але з готового прогнозу)
  const after=r.events.filter(e=>e.date===p.start&&['payout','income','arrears','repay','savings'].includes(e.kind)).pop().cashAfterCents;
  let run=after,low=0;
  for(const e of r.events.filter(e=>e.date>=p.start&&e.date<p.end&&!['payout','income','arrears','repay','savings'].includes(e.kind)||(e.kind==='income'&&e.date>p.start&&e.date<p.end))){run+=e.cashDeltaCents;low=Math.min(low,run);}
  assert.equal(low,0,p.start+': нестача '+(-low));
  // з нової виплати нічого; залишок періоду = власні на початок дня = надлишок попередньої виплати понад бюджет
  assert.equal(p.savingsCents,p.leftoverSavingsCents,p.start+': накопичення лише із залишку');
  assert.equal(p.leftoverCents,p.openingCashCents,p.start+': залишок = власні на початок дня');
  assert.equal(p.savingsCents,prev?Math.max(0,prev.availableCents-prev.targetCents):0,p.start+': накопичення');
  saved+=p.savingsCents;prev=p;
 }
 assert.ok(saved>0,'накопичень немає, перевірка не показова');
});

test('A: a debit-only payment keeps priority over a credit_ok payment when own funds cannot cover both',()=>{
 const d=covered();
 d.salary.advance_amount=20000;d.salary.salary_amount=20000;
 d.accounts[1].debt=0;d.accounts[1].debt_month=null;
 // з 06.11 до 21.11: credit_ok 5 000 (08-го) раніше за дебетові 18 000 (10-го); власні на виплату 20 000
 d.fixed=[{id:1,name:'Оренда',type:'expense',amount:18000,day_of_month:10,credit_ok:false,active:true},{id:2,name:'Сервіс',type:'expense',amount:5000,day_of_month:8,credit_ok:true,active:true}];
 const r=both(d);
 const p=r.periods.find(p=>p.start==='2026-11-06');
 assert.equal(p.reserveCents,p.ownCents,'весь власний залишок у резерві');
 const svc=r.events.find(e=>e.id==='fixed:2:2026-11'),rent=r.events.find(e=>e.id==='fixed:1:2026-11');
 // credit_ok бере свою частку резерву (власні мінус дебетові), решту з кредитки; дебетовий платіж покритий повністю
 assert.equal(svc.cashDeltaCents,-(p.ownCents-1800000));
 assert.equal(svc.debtDeltaCents,svc.amountCents+svc.cashDeltaCents);
 assert.equal(rent.cashDeltaCents,-1800000);
 assert.ok(!rent.shortCents,'дебетовий платіж з нестачею');
 assert.ok(!r.snapshot.warnings.some(w=>w.kind==='shortage'&&w.eventId===rent.id),'попередження про нестачу оренди');
});
