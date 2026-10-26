const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const code=html.split('/* PERIOD ALLOCATION VIEW */')[1].split('/* END PERIOD ALLOCATION VIEW */')[0];
const view=new Function('isSavingsCategory',code+';return budgetPurposeData')(c=>c.id==='saved');
const cats=[{id:'food'},{id:'card',budget_role:'debt_card'},{id:'inst',budget_role:'debt_installment'},{id:'saved'}];
const plan=()=>({covered:true,targetCents:100000,unallocatedCents:10000,savingsCategoryIds:['saved'],debtCategoryIds:['card','inst'],categories:[{id:'food',totalCents:40000},{id:'card',totalCents:20000},{id:'inst',totalCents:15000},{id:'saved',totalCents:15000}]});
test('selected saved allocation conserves cents and distinguishes installments from credit cards',()=>{
 const p=plan(),before=JSON.stringify(p),v=view(p,cats);
 assert.equal(v.status,'available');assert.equal(v.total,100000);
 assert.deepEqual(v.amounts,{daily:40000,card:20000,installment:15000,savings:15000,unallocated:10000});
 assert.equal(JSON.stringify(p),before);
});
test('uncovered and inconsistent plans never fabricate an allocation graphic',()=>{
 assert.equal(view({covered:false},cats).status,'unavailable');
 for(const mutate of [p=>p.targetCents++,p=>p.categories[0].totalCents=-1,p=>p.unallocatedCents=NaN,p=>p.categories[0].totalCents=1.5]){const p=plan();mutate(p);assert.equal(view(p,cats).status,'unavailable');}
 assert.equal(view(plan(),cats.filter(c=>c.id!=='card')).status,'unavailable');
});
test('zero plan and estimated period remain valid without division or invented money',()=>{
 const v=view({covered:true,targetCents:0,unallocatedCents:0,categories:[],estimated:true},cats);
 assert.equal(v.status,'available');assert.equal(v.total,0);assert.equal(v.estimated,true);
 assert(Object.values(v.amounts).every(n=>n===0));
});
