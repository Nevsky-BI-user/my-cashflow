// v153 (власник обрав А+Б після «тут одразу має закритись кредитки з власних коштів»):
// А. кожна виплата резервувала до наступної виплати не лише дебетові обовʼязкові й комісії, а й обовʼязкові з кредитки (credit_ok).
// v154 (власник: «приват тут буде погашено повністю, а монобанк частково, але точно кредитні одразу мають зменшуватися і пройти 2 транзакції
//    погашення заборгованості»): А скасовано, тепер навпаки. Резерв виплати = лише білі (credit_ok=false) обовʼязкові й комісії до наступної виплати;
//    разом із бюджетом періоду це все, що тримається з виплати. Решта одразу в день виплати гасить кредитки: належне, далі не-Mono (Приват) до 0,
//    далі Mono скільки вистачить, окрема подія на кожен рахунок. Обовʼязкові credit_ok не резервуються: вільні власні, далі кредитка (як до v153).
// Б. накопичення лише із залишку попереднього періоду в день наступної виплати і лише без боргів (доповнення 7 v153 без змін).
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const python=path.join(root,'.venv','Scripts','python.exe');
const stamp='2026-10-12T07:00:00Z';
const ASOF='2026-10-12',THROUGH='2027-01-31';
const run=(exe,args,input)=>{const p=spawnSync(exe,args,{cwd:root,input,encoding:'utf8',timeout:30000,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout)[0];};
function both(d,asof=ASOF){
 const input=JSON.stringify([{data:d,asof,through:THROUGH}]);
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
const debtBefore=(r,d)=>r.days.filter(x=>x.date<d).pop().debtCents;

test('each payout protects both debit-only and credit-eligible mandatory payments and fees',()=>{
 const r=both(covered());
 const pays=r.periods.filter(p=>p.payoutCents>0);
 assert.ok(pays.length>=6,'виплат '+pays.length);
 let withOk=0;
 for(const p of pays){
  assert.equal(p.reserveCents,Math.min(p.ownCents,sumOf(r,p.start,p.end,e=>debitEv(e)||okEv(e))),p.start+': резерв лише білих');
  if(sumOf(r,p.start,p.end,okEv)>0)withOk++;
 }
 assert.ok(withOk>=4,'періодів з credit_ok '+withOk+', перевірка не показова');
 // білі платежі ніколи не йдуть у кредит; власні не мінусові
 for(const e of r.events.filter(debitEv))assert.equal(e.debtDeltaCents,0,e.id+' білий платіж у кредит');
 for(const d of r.days)assert.ok(d.closingCashCents>=0&&d.minCashCents>=0&&d.arrearsCents===0,d.date);
});

test('surplus after all mandatory and living repays cards on the payout day',()=>{
 const r=both(covered());
 const p=r.periods.find(p=>p.start==='2026-10-21'),before=debtBefore(r,p.start);
 assert.ok(before>0,'боргу перед 21.10 немає, перевірка не показова');
 // бюджет авто 15 000 як база розподілу: погашення = min(борг, власні − білий резерв − 15 000)
 assert.equal(p.payoutRepayCents,Math.min(before,Math.max(0,p.ownCents-p.reserveCents-1500000)));
 assert.equal(r.days.find(d=>d.date===p.start).debtCents,before-p.repayCents,'кредитні в день виплати');
 assert.equal(sumOf(r,p.start,p.end,e=>e.kind==='repay'&&e.date===p.start),p.repayCents);
});

test('cards repay in priority order only after all upcoming mandatory payments are protected',()=>{
 // як у власника 21.10: Приват (не Mono) 9 257 належний 21.10, Mono 29 722; аванс 65 450; білі до 06.11: оренда 16 500 і комісія 400;
 // credit_ok до 06.11: садочок 9 640 (22-го) і підписка 10 800 (25-го)
 const d={accounts:[{id:1,name:'Ощадбанк',kind:'debit',balance:0,debt:0,min_spend:0,balance_updated_at:stamp},
   {id:2,name:'ПриватБанк кредитна',kind:'credit',balance:0,debt:9257,credit_limit:20000,debt_month:'2026-09-01',balance_updated_at:stamp},
   {id:3,name:'Monobank',kind:'credit',mono_account_id:'m1',balance:0,debt:29722,credit_limit:60000,debt_month:'2026-10-01',balance_updated_at:stamp}],
  salary:{rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:65450,salary_amount:65450},
  fixed:[{id:1,name:'Оренда',type:'expense',amount:16500,day_of_month:1,credit_ok:false,active:true},
   {id:2,name:'Комісія',type:'expense',amount:400,day_of_month:1,credit_ok:false,active:true},
   {id:3,name:'Дитячий садочок',type:'expense',amount:9640,day_of_month:22,credit_ok:true,active:true},
   {id:4,name:'Підписка',type:'expense',amount:10800,day_of_month:25,credit_ok:true,active:true}],
  credits:[],categories:[{id:'1',name:'Їжа',type:'expense',budget_limit:100}],transactions:[]};
 const r=both(d,'2026-10-20');
 const p=r.periods.find(p=>p.start==='2026-10-21');
 assert.equal(p.reserveCents,3734000,'резерв усіх: 16 500+400+9 640+10 800');
 const ev=r.events.filter(e=>e.date==='2026-10-21'&&e.kind==='repay'),by=id=>ev.filter(e=>String(e.accountId)===id).reduce((n,e)=>n+e.amountCents,0);
 const privBefore=925700,monoBefore=debtBefore(r,'2026-10-21')-privBefore;
 assert.equal(p.repayCents,6545000-3734000-1500000,'погашення = виплата − білий резерв − бюджет');
 assert.equal(by('2'),privBefore,'Приват повністю');
 assert.equal(by('3'),p.repayCents-privBefore,'Mono на решту');
 assert.ok(by('3')>0&&by('3')<monoBefore,'Mono частково');
 assert.ok(ev.some(e=>String(e.accountId)==='2')&&ev.some(e=>String(e.accountId)==='3'),'окремі погашення Привату і Mono');
 const day=r.days.find(x=>x.date==='2026-10-21');
 assert.equal(day.debtCents,monoBefore-by('3'),'кредитні одразу зменшились');
 // власні після розподілу = білий резерв + бюджет 15 000 мінус змінні дня; credit_ok беруть вільні власні, решту з кредитки; білі не в кредит
 const kids=r.events.find(e=>e.id==='fixed:3:2026-10'),rent=r.events.find(e=>e.id==='fixed:1:2026-11');
 assert.equal(-kids.cashDeltaCents+kids.debtDeltaCents,964000);
 assert.equal(rent.debtDeltaCents,0);assert.equal(rent.cashDeltaCents,-1650000);assert.ok(!rent.shortCents);
 for(const x of r.days)assert.ok(x.closingCashCents>=0,x.date);
});

test('savings is the combined own residual after all mandatory, living and debts',()=>{const r=both(covered());let saved=0;for(const p of r.periods.filter(p=>p.payoutCents>0)){assert.equal(p.leftoverSavingsCents,0);assert.equal(p.savingsCents,Math.max(0,p.availableCents-p.targetCents-p.prepayCents));assert.equal(p.ownCents,p.reserveCents+p.repayCents+p.prepayCents+p.savingsCents+p.cashOutCents+p.toMonoCents);saved+=p.savingsCents;}assert.ok(saved>0);});
test('both mandatory kinds retain own funding despite an underfunded living budget',()=>{
 const d=covered();
 d.salary.advance_amount=24000;d.salary.salary_amount=24000;
 d.accounts[1].debt=0;d.accounts[1].debt_month=null;
 // з 06.11 до 21.11: credit_ok 5 000 (08-го) раніше за білу оренду 18 000 (10-го); власні на виплату 24 000
 d.fixed=[{id:1,name:'Оренда',type:'expense',amount:18000,day_of_month:10,credit_ok:false,active:true},{id:2,name:'Сервіс',type:'expense',amount:5000,day_of_month:8,credit_ok:true,active:true}];
 const r=both(d);
 const p=r.periods.find(p=>p.start==='2026-11-06');
 assert.equal(p.reserveCents,2300000,'резерв оренди та сервісу');
 const svc=r.events.find(e=>e.id==='fixed:2:2026-11'),rent=r.events.find(e=>e.id==='fixed:1:2026-11');
 // власні понад білий резерв на 08.11 (після змінних 06-07.11) ідуть на сервіс, решта з кредитки; оренда покрита повністю з резерву
 assert.equal(svc.cashDeltaCents,-500000);assert.equal(svc.debtDeltaCents,0);
 assert.equal(rent.cashDeltaCents,-1800000);
 assert.equal(rent.debtDeltaCents,0);
 assert.ok(!rent.shortCents,'білий платіж з нестачею');
 assert.ok(!r.snapshot.warnings.some(w=>w.kind==='shortage'&&w.eventId===rent.id),'попередження про нестачу оренди');
});
