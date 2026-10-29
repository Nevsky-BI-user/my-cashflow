const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync(path.join(__dirname,'../supabase/functions/telegram-webhook/index.ts'),'utf8');
const body=stripTypeScriptTypes(source.slice(source.indexOf('const tgSourceId ='),source.indexOf('type Pending =')));
const api=new Function('todayKyiv',body+';return {normalizeReceipt,receiptBatch,receiptAccount};')(()=> '2026-10-29');
const system=new Function(source.slice(source.indexOf('const RECEIPT_SYSTEM ='),source.indexOf('const SUPABASE_URL ='))+';return RECEIPT_SYSTEM;')();
const operation=(amount,extra={})=>({amount,type:'expense',currency:'UAH',description:'Тестовий платіж',date_text:'29 жовтня',...extra});
const batch=(extra={})=>({kind:'transactions',complete:true,readable:'good',transactions:[operation(111),operation(112)],...extra});

test('OCR distinguishes card-carousel picker from an applied all-accounts history filter',()=>{
  assert.match(system,/Карусель карток:[\s\S]*активну велику картку[\s\S]*account_scope:"selected"/);
  assert.match(system,/кнопка «Усі»[\s\S]*сама по собі НЕ означає account_scope:"all"/);
  assert.match(system,/явно спільна історія різних рахунків[\s\S]*фільтр «Всі рахунки» означає all/);
});

test('selected carousel card owns every history row even if counterparties show another bank',()=>{
  const response=batch({account_scope:'selected',selected_card_last4:'0246',selected_bank:'privat',
    transactions:[operation(111,{bank:'mono',card_last4:'1357'}),operation(112)]});
  const rows=api.receiptBatch(api.normalizeReceipt(response,'2026-10-29'));
  const accounts=[{id:1,bank:'privat',card_last4:'0246',active:true},{id:2,bank:'mono',card_last4:'1357',active:true}];
  assert.equal(rows.length,2);
  assert.deepEqual(rows.map(row=>api.receiptAccount(row.hint,accounts)?.id),[1,1]);
});

test('combined history never spreads one card header to rows without source evidence',()=>{
  const response=batch({account_scope:'all',bank:'privat',card_last4:'0246',
    transactions:[operation(111,{bank:'mono',card_last4:'1357'}),operation(112)]});
  const rows=api.receiptBatch(api.normalizeReceipt(response,'2026-10-29'));
  assert.equal(rows[0].hint.card_last4,'1357');
  assert.equal(rows[1].hint.card_last4,null);
  assert.equal(rows[1].hint.bank,null);
});
