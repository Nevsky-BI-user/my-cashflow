const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('index.html','utf8');
const names=['savingsAtCents','spendableFunds','kpiFunds','balanceNowCents'];
const functions=names.map(name=>html.split(/\r?\n/).find(line=>line.startsWith('function '+name+'(')));
assert.ok(functions.every(Boolean),'available funds helpers missing');
const {savingsAtCents,spendableFunds,kpiFunds}=new Function(functions.join('\n')+';return {savingsAtCents,spendableFunds,kpiFunds}')();

test('earmarked savings reduce own available money and preserve unused credit',()=>{
 assert.deepEqual(spendableFunds(1000000,200000,300000),{deduction:300000,total:900000});
 assert.deepEqual(spendableFunds(100000,200000,300000),{deduction:100000,total:200000});
 assert.deepEqual(spendableFunds(100000,200000,0),{deduction:0,total:300000});
 assert.deepEqual(spendableFunds(-100000,200000,0),{deduction:0,total:100000});
 assert.deepEqual(spendableFunds(-100000,200000,300000),{deduction:0,total:100000});
 assert.deepEqual(spendableFunds(100000,200000,-300000),{deduction:0,total:300000});
});

test('savings valuation uses ledger currencies and only records at the displayed date',()=>{
 const rows=[{amount:100,currency:'UAH',date:'2026-10-01'},
  {amount:10,currency:'USD',date:'2026-10-21'},{amount:5,currency:'EUR',date:'2026-10-25'},
  {amount:9000,currency:'UAH',date:'2026-11-01'},
  {amount:'invalid',date:'2026-10-01'},{amount:9000,date:''}];
 assert.equal(savingsAtCents(rows,41.2,47.9,'2026-10-20'),10000);
 assert.equal(savingsAtCents(rows,41.2,47.9,'2026-10-24'),51200);
 assert.equal(savingsAtCents(rows,41.2,47.9,'2026-10-25'),75150);
 assert.equal(savingsAtCents(rows,41.2,47.9,'2026-11-01'),975150);
});

test('legacy withdrawals release reserved money without creating negative savings',()=>{
 const rows=[{amount:1000,date:'2026-10-01'}, {amount:-250,date:'2026-10-20'}];
 assert.equal(savingsAtCents(rows,40,45,'2026-10-25'),75000);
 rows.push({amount:-900,date:'2026-10-25'});
 assert.equal(savingsAtCents(rows,40,45,'2026-10-25'),0);
});

test('cash, cards, credit, balance and projection remain intact after funds-only exclusion',()=>{
 const projection={snapshot:{positiveOwnCents:1000000,creditDebtCents:300000,
  accounts:[{id:1,kind:'cash',balanceCents:100000},{id:2,kind:'debit',balanceCents:900000},
   {id:3,kind:'credit',credit_limit:5000,debtCents:300000,balanceCents:0}]}};
 const original=structuredClone(projection),before=kpiFunds(projection),after=kpiFunds(projection,300000);
 assert.equal(before.total,1200000);
 assert.equal(after.total,900000);
 assert.equal(after.deduction,300000);
 for(const name of ['cash','cards','credit','own','debt','balance'])assert.equal(after[name],before[name],name);
 assert.deepEqual(projection,original);
 assert.equal(kpiFunds(projection,2000000).total,200000);
});
