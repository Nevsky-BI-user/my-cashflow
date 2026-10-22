const {test}=require('node:test'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'),path=require('node:path');
const load=n=>import(pathToFileURL(path.resolve('supabase/functions/_shared/'+n+'.ts')).href);
const salary={rate:0,advance_amount:10000,salary_amount:20000,advance_day:6,salary_day:21,split_day:15,budget_manual:5000};
const accounts=[{id:1,name:'Source',kind:'debit',active:true,is_salary:true,balance:20000,debt:0,balance_updated_at:'2026-10-01T00:00:00Z'},{id:2,name:'Credit',kind:'credit',active:true,balance:0,debt:10000,debt_month:'2026-09-01',balance_updated_at:'2026-10-01T00:00:00Z'}];
const transfer=[{id:11,account_id:1,type:'expense',amount:7000,date:'2026-10-21',created_at:'2026-10-21T10:00:00Z',transfer_id:'a'},{id:12,account_id:2,type:'income',amount:7000,date:'2026-10-21',created_at:'2026-10-21T10:00:00Z',transfer_id:'a'}];
test('transfer moves own funds into credit debt, without variable spend or qualifying purchases',async()=>{
 const {financeProjection}=await load('budget'),data={accounts:accounts.map(a=>({...a,min_spend:1000,min_spend_fee:100})),transactions:transfer,fixed:[],credits:[],categories:[],salary};
 const p=financeProjection(data,{asof:'2026-10-21',through:'2026-11-01'});
 assert.equal(p.snapshot.accounts[0].balanceCents,1300000);assert.equal(p.snapshot.accounts[1].debtCents,300000);
 assert.equal(p.currentPeriod.actualVariableCents,0);assert.equal(p.minSpend[0].spent,0);
 const {monthModel}=await load('bot-reports'),m=monthModel(transfer,[],accounts,'2026-10-21');assert.equal(m.curSpent,0);assert.equal(JSON.stringify(m).includes('700000'),false);
});
test('credit overpayment retains own balance and transfer pairing preserves net position',async()=>{
 const {financeProjection}=await load('budget'),tx=transfer.map(t=>({...t,amount:12000}));
 const p=financeProjection({accounts,transactions:tx,fixed:[],credits:[],categories:[],salary},{asof:'2026-10-21',through:'2026-10-22'});
 assert.equal(p.snapshot.accounts[1].debtCents,0);assert.equal(p.snapshot.accounts[1].balanceCents,200000);assert.equal(p.snapshot.positiveOwnCents-p.snapshot.creditDebtCents,1000000);
});
test('advice only on salary date, from actual source cash, reserve and configured budget',async()=>{
 const {financeProjection}=await load('budget'),{repaymentAdvice}=await load('repayment');const data={accounts,transactions:[],fixed:[{id:1,name:'Rent',amount:3000,day_of_month:25,type:'payment'}],credits:[],categories:[],salary};
 const p=financeProjection(data,{asof:'2026-10-21',through:'2026-11-07'}),a=repaymentAdvice(data,p,1,'2026-10-21');
 assert.equal(a.availableCents,1000000);assert.equal(a.items.reduce((s,i)=>s+i.amountCents,0),a.availableCents);
 assert.equal(repaymentAdvice(data,p,1,'2026-10-22').items.length,0);
 const poor={...p,snapshot:{...p.snapshot,positiveOwnCents:200000,accounts:p.snapshot.accounts.map(a=>({...a,balanceCents:a.id===1?200000:a.balanceCents}))}};
 assert.equal(repaymentAdvice(data,poor,1,'2026-10-21').availableCents,0);
});
test('salary calculator uses canonical workdays/fixed override and rejects future callback',async()=>{
 const {salaryChoices,salaryOccurrence}=await load('salary-payout');assert.equal(salaryChoices(salary,accounts,'2026-10-21')[0].amount,20000);
 assert.equal(salaryOccurrence(salary,accounts,'2026-10-20','salary','2026-10-21',1),null);
 assert.equal(salaryOccurrence(salary,accounts,'2026-10-21','salary','2026-10-21',2),null);
 assert.equal(salaryChoices({...salary,rate:60000},accounts,'2026-10-21')[0].amount,30000);
});
function sbMock({mono=false,rows=[],paid=null,cfg=salary}={}){
 const calls=[],state={writes:0,paid},occurrences=[];return {state,calls,from(table){const q={filters:[],one:false};q.select=q.order=q.limit=()=>q;for(const n of ['eq','is','gte','lte'])q[n]=(k,v)=>{q.filters.push([n,k,v]);return q};q.maybeSingle=()=>{q.one=true;return q};const matches=r=>q.filters.every(([n,k,v])=>n==='gte'?r[k]>=v:n==='lte'?r[k]<=v:r[k]===v);q.then=fn=>Promise.resolve({data:table==='salary_config'?cfg:table==='accounts'?[{...accounts[0],mono_account_id:mono?'m':null}]:table==='salary_payouts'?(occurrences.find(matches)||paid):rows.filter(matches).map(r=>({...r,salary_payouts:occurrences.filter(o=>o.transaction_id===r.id).length?occurrences.filter(o=>o.transaction_id===r.id):r.salary_payouts})),error:null}).then(fn);return q},async rpc(name,args){calls.push([name,args]);let done=occurrences.find(o=>o.account_id===args.p_account_id&&o.kind===args.p_kind&&o.due_date===args.p_due_date);if(!done){state.writes++;done={account_id:args.p_account_id,kind:args.p_kind,due_date:args.p_due_date,transaction_id:args.p_existing_tx_id||88+state.writes};occurrences.push(done);state.paid=done;}return {data:done.transaction_id,error:null}}};
}
test('salary one click is occurrence-idempotent across family actors and amount stays server-computed',async()=>{
 const {recordSalary}=await load('salary-bot'),sb=sbMock();assert.equal((await recordSalary(sb,'u1','2026-10-21','salary','2026-10-21',1)).status,'saved');assert.equal((await recordSalary(sb,'u2','2026-10-21','salary','2026-10-21',1)).status,'already');assert.equal(sb.state.writes,1);assert.equal(sb.calls[0][1].p_amount,20000);
});
test('salary Mono waits for bank import; ambiguity requests choice; candidates scoped account/date',async()=>{
 const {recordSalary}=await load('salary-bot');const empty=sbMock({mono:true});assert.equal((await recordSalary(empty,'u','2026-10-21','salary','2026-10-21',1)).status,'awaiting');assert.equal(empty.state.writes,0);
 const r={id:2,account_id:1,type:'income',amount:20000,date:'2026-10-20',source:'mono',transfer_id:null},sb=sbMock({mono:true,rows:[r,{...r,id:3}]});assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1)).status,'choose');assert.equal(sb.state.writes,0);assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1,3)).status,'saved');assert.equal(sb.calls[0][1].p_existing_tx_id,3);
 const other=sbMock({rows:[{...r,account_id:2}]});await recordSalary(other,'u','2026-10-21','salary','2026-10-21',1);assert.equal(other.calls[0][1].p_existing_tx_id,null);
});
test('source bank rent and fees stay on source card even with own funds elsewhere',async()=>{
 const {repaymentAdvice}=await load('repayment');
 const data={salary,fixed:[{id:1,bank:'oschad'}],credits:[]};
 const p={snapshot:{positiveOwnCents:2300000,accounts:[{id:1,name:'Oschad',bank:'oschad',balanceCents:300000},{id:2,name:'Other',bank:'privat',balanceCents:2000000},{id:3,name:'Credit',kind:'credit',debtCents:1000000,balanceCents:0}]},periods:[{basis:'current',end:'2026-11-06',mandatoryCents:300000}],events:[{kind:'mandatory',date:'2026-10-25',occurrenceId:'fixed:1:2026-10',amountCents:300000}]};
 assert.equal(repaymentAdvice(data,p,1,'2026-10-21').availableCents,0);
 p.snapshot.accounts[0].balanceCents=350000;p.snapshot.positiveOwnCents=2350000;p.events.push({kind:'fee',date:'2026-10-25',accountId:1,amountCents:10000});p.periods[0].mandatoryCents=310000;
 assert.equal(repaymentAdvice(data,p,1,'2026-10-21').availableCents,40000);
});
test('nominal next-month salary shifted to prior month and simultaneous payouts are recognized',async()=>{
 const {salaryChoices,salaryOccurrence}=await load('salary-payout'),{repaymentAdvice}=await load('repayment');
 const cfg={...salary,salary_day:1,advance_day:15};
 const choices=salaryChoices(cfg,accounts,'2026-07-31');assert.equal(choices.length,1);assert.equal(choices[0].kind,'salary');assert.equal(choices[0].date,'2026-07-31');
 assert.equal(salaryOccurrence(cfg,accounts,'2026-07-31','salary','2026-07-31',1).amount,20000);
 const both=salaryChoices({...cfg,advance_day:1},accounts,'2026-07-31');assert.deepEqual(both.map(p=>p.kind).sort(),['advance','salary']);
 const p={snapshot:{positiveOwnCents:2000000,accounts:[{id:1,balanceCents:2000000},{id:2,name:'Credit',kind:'credit',debtCents:500000}]},periods:[{basis:'current',end:'2026-08-14',mandatoryCents:0}],events:[]};
 assert.equal(repaymentAdvice({salary:cfg},p,1,'2026-07-31').reason,null);
});
test('late salary income requires explicit linking and stale prior occurrence cannot create new income',async()=>{
 const {recordSalary}=await load('salary-bot');const row={id:9,account_id:1,type:'income',amount:20000,date:'2026-10-25',source:'manual',transfer_id:null};
 const sb=sbMock({rows:[row]});assert.equal((await recordSalary(sb,'u','2026-10-25','salary','2026-10-21',1)).status,'choose');assert.equal(sb.state.writes,0);
 assert.equal((await recordSalary(sb,'u','2026-10-25','salary','2026-10-21',1,9)).status,'saved');assert.equal(sb.calls[0][1].p_existing_tx_id,9);
 const stale=sbMock();assert.equal((await recordSalary(stale,'u','2026-11-07','salary','2026-10-21',1)).status,'invalid');assert.equal(stale.state.writes,0);
});
test('claimed salary income is excluded from both automatic and explicit candidates',async()=>{
 const {recordSalary}=await load('salary-bot'),r={id:41,account_id:1,type:'income',amount:20000,date:'2026-10-20',source:'mono',transfer_id:null,salary_payouts:[{transaction_id:41}]};
 const sb=sbMock({mono:true,rows:[r]});assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1)).status,'awaiting');assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1,41)).status,'invalid');assert.equal(sb.calls.length,0);
});
test('same day equal salary and advance claim different imported incomes sequentially',async()=>{
 const {recordSalary}=await load('salary-bot'),r={id:51,account_id:1,type:'income',amount:20000,date:'2026-10-21',source:'mono',transfer_id:null};const sb=sbMock({mono:true,cfg:{...salary,advance_amount:20000,advance_day:21},rows:[r,{...r,id:52}]});
 assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1)).status,'choose');assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1,51)).id,51);assert.equal((await recordSalary(sb,'u2','2026-10-21','advance','2026-10-21',1)).id,52);assert.equal(sb.state.writes,2);
});
test('neighbor payout date windows cannot reuse a previously claimed income',async()=>{
 const {recordSalary}=await load('salary-bot'),r={id:61,account_id:1,type:'income',amount:20000,date:'2026-10-21',source:'mono',transfer_id:null};const sb=sbMock({mono:true,cfg:{...salary,advance_amount:20000,advance_day:22},rows:[r,{...r,id:62,date:'2026-10-22'}]});
 assert.equal((await recordSalary(sb,'u','2026-10-21','salary','2026-10-21',1)).id,61);assert.equal((await recordSalary(sb,'u2','2026-10-22','advance','2026-10-22',1)).id,62);assert.equal(sb.state.writes,2);
});
