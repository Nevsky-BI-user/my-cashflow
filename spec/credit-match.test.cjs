const {test}=require('node:test');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const load=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/creditmatch.ts')).href);
const credits=[
 {id:5,name:'Ecoflow Delta 3',monthly_amount:'4643.00',payment_day:12,start_year:2026,start_month:9,total_payments:12,source:'mono'},
 {id:3,name:'Lenovo Legion 5 Pro',monthly_amount:'6133.27',payment_day:24,start_year:2026,start_month:1,total_payments:15,source:'privat'},
];
test('Mono charge on the schedule day links to the installment',async()=>{
 const {matchCredit}=await load();
 assert.equal(matchCredit(credits,{amount:4642.79,date:'2026-10-12',bank:'mono',description:'Оплата частинами EcoFlow Ukraine'}),5);
});
test('charge before schedule start, wrong amount, far day or already paid month does not link',async()=>{
 const {matchCredit,creditPaid}=await load();
 assert.equal(matchCredit(credits,{amount:4642.79,date:'2026-09-12',bank:'mono'}),null);
 assert.equal(matchCredit(credits,{amount:4503.08,date:'2026-10-09',bank:'mono',description:'OpenAI'}),null);
 assert.equal(matchCredit(credits,{amount:4643,date:'2026-10-25',bank:'mono'}),null);
 assert.equal(matchCredit(credits,{amount:4643,date:'2026-10-12',bank:'mono'},creditPaid([{credit_id:5,date:'2026-10-12',type:'expense'}])),null);
});
test('manual expense links by name word when bank is unknown',async()=>{
 const {matchCredit}=await load();
 assert.equal(matchCredit(credits,{amount:6133.27,date:'2026-10-24',description:'lenovo розстрочка'}),3);
 assert.equal(matchCredit(credits,{amount:6133.27,date:'2026-10-24',description:'щось'}),null);
});
