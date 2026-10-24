const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const lines=source.split(/\r?\n/);
const line=prefix=>{const found=lines.find(value=>value.startsWith(prefix));assert(found,prefix);return found};
const api=new Function([
  line('const BCAT='),line('const CAT_PALETTE='),line('function hexLab('),line('const CAT_LAB='),line('function paintColors('),line('function budgetPercentShares('),
  ';return{BCAT,CAT_PALETTE,paintColors,budgetPercentShares};',
].join('\n'))();

test('two reserved category colors extend the palette without recoloring the original categories or payments',()=>{
  const original=['#b45309','#ea580c','#4d7c0f','#059669','#0d9488','#0891b2','#0284c7','#6366f1','#c026d3','#db2777','#e11d48','#64748b','#8250f0'];
  assert.deepEqual(api.paintColors(api.BCAT.slice(0,13)),original);
  const expanded=api.paintColors(api.BCAT);
  assert.deepEqual(expanded.slice(0,13),original);
  assert.equal(new Set(expanded).size,api.BCAT.length);
  assert.deepEqual(expanded.slice(-2),['#477b65','#a94d6d']);
  const payments=['#f28b82','#a8d672','#5ba8ff','#8b9cf6','#f7a876','#f6d06f','#7fa8f2','#6ec6e8'].map(color=>({color}));
  assert.deepEqual(api.paintColors(payments),['#b45309','#4d7c0f','#0284c7','#6366f1','#ea580c','#059669','#0891b2','#64748b']);
  assert(api.BCAT.slice(-2).every(category=>category.limit===0));
});

test('largest-remainder percentages preserve the target and zero categories instead of rounding above it',()=>{
  assert.deepEqual(api.budgetPercentShares([{id:'a',weight:10},{id:'b',weight:10},{id:'c',weight:10},{id:'savings',weight:0},{id:'charity',weight:0}],8),{a:3,b:3,c:2,savings:0,charity:0});
  for(let target=0;target<=100;target++){
    const shares=api.budgetPercentShares([{id:'a',weight:9},{id:'b',weight:3},{id:'c',weight:7},{id:'zero',weight:0}],target);
    assert.equal(Object.values(shares).reduce((sum,value)=>sum+value,0),target);
    assert.equal(shares.zero,0);
    assert(Object.values(shares).every(value=>Number.isInteger(value)&&value>=0));
  }
});

test('legacy distribution keeps locked and edited shares while redistributing the remaining percentage exactly',()=>{
  const start=source.indexOf('var rebal=function(prev,skip,target)');
  const body=source.slice(start,source.indexOf(';var lockedPct=',start));
  assert(start>=0&&body.length>0);
  const cats=['locked','edit','a','b','c','savings','charity'].map(id=>({id}));
  const rebal=new Function('pCats','lockedCats','budgetPercentShares',body+';return rebal;')(cats,{locked:true},api.budgetPercentShares);
  const result=rebal({locked:30,edit:50,a:10,b:10,c:10,savings:0,charity:0},'edit',20);
  assert.deepEqual(result,{locked:30,edit:50,a:7,b:7,c:6,savings:0,charity:0});
  assert.equal(Object.values(result).reduce((sum,value)=>sum+value,0),100);
});
