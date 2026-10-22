const {test}=require('node:test'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url'),path=require('node:path');
const load=n=>import(pathToFileURL(path.resolve('supabase/functions/_shared/'+n+'.ts')).href);
const stamp='2026-12-30T00:00:00Z',account=(id,kind,balance,debt)=>({id,kind,balance,debt,balance_updated_at:stamp}),tx=(id,account_id,type,amount,date)=>({id,account_id,type,amount,date,created_at:date+'T12:00:00Z',transfer_id:'pair'});
test('credit overpayment reconstructs own cash before paired transfer exactly',async()=>{
 const {ownCashSeries}=await load('own-history');const raw=[account(1,'debit',5000,0),account(2,'credit',0,1000)],rows=[tx(1,1,'expense',1200,'2026-12-31'),tx(2,2,'income',1200,'2026-12-31')];const series=ownCashSeries(raw,rows,[],400000,'2026-12-30','2026-12-31');assert.deepEqual(series,[{date:'2026-12-30',cents:500000},{date:'2026-12-31',cents:400000}]);
});
test('source credit own cash and chained FIFO across year boundary preserve actual own deltas',async()=>{
 const {ownCashSeries}=await load('own-history');const raw=[account(1,'credit',5000,0),account(2,'credit',0,1000)],rows=[tx(1,1,'expense',1200,'2026-12-31'),tx(2,2,'income',1200,'2026-12-31'),tx(3,2,'expense',300,'2027-01-01'),tx(4,2,'income',150,'2027-01-02')];const series=ownCashSeries(raw,rows,[],385000,'2026-12-30','2027-01-02');assert.deepEqual(series.map(p=>p.cents),[500000,400000,380000,385000]);
});
test('known manual baseline excludes older/equal timestamp and future-dated operations',async()=>{
 const {ownCashDeltas}=await load('own-history');const raw=[account(1,'credit',0,1000)];const rows=[{...tx(1,1,'income',2000,'2026-12-29'),created_at:stamp},tx(2,1,'income',1200,'2026-12-31'),tx(3,1,'income',999,'2027-01-02')];assert.deepEqual(ownCashDeltas(raw,rows,[],'2026-12-31'),{'2026-12-31':20000});
});
test('Mono credit uses daily net transition, not full imported income as cash',async()=>{
 const {ownCashSeries}=await load('own-history');const raw=[{...account(1,'credit',200,0),mono_account_id:'bank'}],rows=[tx(1,1,'income',1200,'2026-12-31')];assert.deepEqual(ownCashSeries(raw,rows,[{id:1,balanceCents:20000,debtCents:0}],20000,'2026-12-30','2026-12-31').map(p=>p.cents),[0,20000]);
});
test('bot period budget uses shared own reconstruction for credit overpayment',async()=>{
 const {financeProjection}=await load('budget'),{periodBudgetStart,histOf}=await load('bot-reports');const accounts=[{...account(1,'debit',5000,0),balance_updated_at:'2026-10-01T00:00:00Z'},{...account(2,'credit',0,1000),balance_updated_at:'2026-10-01T00:00:00Z'}],transactions=[tx(1,1,'expense',1200,'2026-10-21'),tx(2,2,'income',1200,'2026-10-21')],data={accounts,transactions,fixed:[],credits:[],categories:[],salary:{rate:0,salary_amount:5000,advance_amount:5000,salary_day:21,advance_day:6,split_day:15,budget_manual:1000}};const p=financeProjection(data,{asof:'2026-10-21',through:'2026-11-07'}),h=histOf(transactions,accounts),b=periodBudgetStart(p,data,h.hist,h.allIds,h.ownIds,'2026-10-21');assert.equal(b.own,500000);assert.equal(p.snapshot.positiveOwnCents,400000);
});
