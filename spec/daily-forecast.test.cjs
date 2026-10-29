const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const fixture=()=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/daily-forecast.json'),'utf8'));
const options={asof:'2026-10-29',through:'2026-11-22'};
const backend=()=>import('../supabase/functions/_shared/budget.ts');
function dailyInvariant(p){
 const c=p.currentPeriod,period=p.periods.find(p=>p.basis==='current');
 assert.equal(c.futureSchedule.length,8);
 assert.equal(c.futureSchedule[0].date,options.asof,'today has an allowance in the daily plan');
 assert.equal(c.futureSchedule.reduce((n,d)=>n+d.spendCents,0),c.spendableRemainingCents);
 for(const day of c.futureSchedule){assert.ok(Math.abs(day.spendCents-c.dailyCents)<1,day.date);assert.equal(day.byCategory.reduce((n,c)=>n+c.amountCents,0),day.spendCents);}
 assert.equal(period.categories.reduce((n,c)=>n+c.totalCents,0),c.spendableRemainingCents);
 assert.equal(p.events.filter(e=>(e.kind==='variable'||e.budgetSavings)&&e.date===options.asof).length,0,'today snapshot must not include fictional planned spending');
 for(const day of c.futureSchedule.slice(1))assert.equal(p.events.filter(e=>e.kind==='variable'&&e.date===day.date).reduce((n,e)=>n+e.amountCents,0),day.spendCents,day.date);
 assert.equal(p.days[0].closingCashCents,p.snapshot.positiveOwnCents);
}
test('cross-month overspend: 2396 forecast becomes the same 256.93 daily plan',async()=>{
 const {financeProjection}=await backend(),p=financeProjection(fixture(),options);
 assert.equal(p.currentPeriod.spendableRemainingCents,205542);assert.equal(p.currentPeriod.dailyCents,25692.75);dailyInvariant(p);
 assert.equal(p.events.filter(e=>e.kind==='variable'&&e.date==='2026-11-02').reduce((n,e)=>n+e.amountCents,0),25693);
 const next=p.periods.find(p=>p.basis!=='current');assert.ok(next.schedule.some(d=>d.spendCents>p.currentPeriod.dailyCents),'later payout periods retain their own budgets');
});
test('new spending, edited budget and exhausted shared balance dynamically update all future days',async()=>{
 const {financeProjection}=await backend();
 for(const change of ['expense','budget','exhausted']){const d=fixture();if(change==='budget'){d.monthly_budgets[1].total_cents+=60000;d.monthly_budgets[1].allocations.food+=60000;}else d.transactions.push({...d.transactions[0],id:2,amount:change==='expense'?80:3000,date:'2026-10-29',created_at:'2026-10-29T10:00:00Z'});
  const p=financeProjection(d,options);dailyInvariant(p);assert.equal(p.currentPeriod.spendableRemainingCents,change==='expense'?197542:change==='budget'?215542:0);}
});
test('uniform current daily cap preserves category totals without including savings or debt reserves',async()=>{
 const {financeProjection}=await backend(),d=fixture();d.categories.push({id:'other',name:'Other',type:'expense'},{id:'savings',name:'Заощадження',type:'expense'},{id:'debt',name:'Debt',type:'expense',budget_role:'debt_card'});
 d.monthly_budgets[1].allocations={food:4000000,other:3188000};const p=financeProjection(d,options);dailyInvariant(p);
 assert.equal(p.periods[0].categories.reduce((n,c)=>n+c.totalCents,0),p.currentPeriod.spendableRemainingCents);
 for(const day of p.currentPeriod.futureSchedule)assert.ok(day.byCategory.every(c=>c.id!=='debt'&&c.id!=='savings'));
});
test('current daily forecast has complete TS, inline browser and Python parity',async()=>{
 const {financeProjection}=await backend(),cases=[];for(const amount of [20924.58,21004.58,23924.58]){const data=fixture();data.transactions[0].amount=amount;cases.push({data,options});}
 const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8'),inline=new Function(html.split('/* CANONICAL MONTHLY PERIOD BUDGET */')[1].split('/* END CANONICAL MONTHLY PERIOD BUDGET */')[0]+html.split('/* CANONICAL FINANCE PROJECTION */')[1].split('/* END CANONICAL FINANCE PROJECTION */')[0]+';return financeProjection')();
 const py=spawnSync(path.resolve('.venv/Scripts/python.exe'),['scripts/budget_pool.py','--finance'],{input:JSON.stringify(cases),encoding:'utf8',maxBuffer:16*1024*1024,env:{...process.env,PYTHONUTF8:'1'}});assert.equal(py.status,0,py.stderr);const oracle=JSON.parse(py.stdout);
 cases.forEach((c,i)=>{const p=financeProjection(c.data,c.options);assert.deepEqual(p,inline(c.data,c.options));assert.deepEqual(p,oracle[i]);});
});
