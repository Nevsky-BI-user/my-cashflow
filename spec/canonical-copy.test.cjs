const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
// v147: вбудована копія = спільне правило погашення repayDate і financeProjection, саме в такому порядку
// v151: між ними payoutBudget, правило розподілу виплати, яким фронтенд рахує бюджет на старт періоду
test('deployed single-file finance function is the exact canonical TS implementation',async()=>{
 const root=path.resolve(__dirname,'..');
 const {financeProjection,repayDate,payoutBudget}=await import(pathToFileURL(path.join(root,'supabase/functions/_shared/budget.ts')).href);
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 const start='/* CANONICAL FINANCE PROJECTION */',end='/* END CANONICAL FINANCE PROJECTION */';
 assert.equal(html.split(start).length,2);assert.equal(html.split(end).length,2);
 const deployed=html.split(start)[1].split(end)[0];
 const normalize=s=>s.replaceAll('\r','').trim();
 assert.equal(normalize(deployed),normalize(repayDate.toString()+'\n'+payoutBudget.toString()+'\n'+financeProjection.toString()),'resync the inline copy after changing the canonical engine');
});
