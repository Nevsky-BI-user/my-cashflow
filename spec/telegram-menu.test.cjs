const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const keyboard=import(pathToFileURL(path.join(root,'supabase/functions/_shared/bot-kb.ts')).href);
const labels={
 balance:'💰 Баланс',chart:'📈 Графік',budget:'📊 Бюджет',week:'📅 Тиждень',month:'🔍 Місяць',today:'🧾 Витрати за сьогодні',
 income:'➕ Дохід',expense:'➖ Витрата',last:'📋 Останні',help:'❓ Допомога',app:'📱 Застосунок',
 menu:'⬅️ Головне меню',text:'✍️ Текстом',image:'📷 Зображенням',cancel:'✖ Скасувати',yes:'✅ Так, додати',
};
const rows=(keys)=>keys.map(row=>row.map(key=>({text:labels[key]})));

test('спільний контракт зберігає точні назви 16 поточних і сумісних кнопок',async()=>{
 const {KB_BTN}=await keyboard;
 assert.deepEqual(KB_BTN,labels);
 assert.equal(new Set(Object.values(KB_BTN)).size,16);
});

test('головне меню містить шість кнопок у трьох рядках і не згортається',async()=>{
 const {MAIN_KB}=await keyboard;
 assert.deepEqual(MAIN_KB,{
  keyboard:rows([['balance','chart'],['budget','week'],['today','last']]),
  resize_keyboard:true,is_persistent:true,one_time_keyboard:false,input_field_placeholder:'Сума й опис або фото операції',
 });
 const buttons=MAIN_KB.keyboard.flat().map(button=>button.text);
 assert.equal(new Set(buttons).size,6);
 for(const key of ['balance','chart','budget','week','today','last'])assert.ok(buttons.includes(labels[key]),key);
 for(const key of ['month','income','expense','menu','cancel','yes','help','app'])assert.ok(!buttons.includes(labels[key]),key);
 assert.equal(MAIN_KB.is_persistent,true);
});

test('вибір способу введення згортається, головне меню постійне, прибраних кнопок немає',async()=>{
 const {MAIN_KB,ENTRY_KB,ENTRY_INPUT_KB}=await keyboard;
 assert.deepEqual(ENTRY_KB,{
  keyboard:rows([['text','image']]),resize_keyboard:true,is_persistent:false,one_time_keyboard:true,
  input_field_placeholder:'Сума й опис або фото операції',
 });
 assert.equal(ENTRY_INPUT_KB,MAIN_KB);
 for(const kb of [MAIN_KB,ENTRY_KB,ENTRY_INPUT_KB]){
  assert.equal(kb.resize_keyboard,true);
  assert.equal(kb.is_persistent,kb!==ENTRY_KB);
  assert.equal(kb.one_time_keyboard,kb===ENTRY_KB);
  assert.ok(kb.input_field_placeholder.length>=1&&kb.input_field_placeholder.length<=64);
  const buttons=kb.keyboard.flat().map(button=>button.text);
  for(const key of ['income','expense','menu','cancel','yes'])assert.ok(!buttons.includes(labels[key]),key);
 }
});

test('меню команд не реєструється: telegram-setup видаляє каталог',async()=>{
 const kb=await keyboard;
 assert.equal(kb.BOT_COMMANDS,undefined);
 const source=fs.readFileSync(path.join(root,'supabase/functions/telegram-setup/index.ts'),'utf8');
 assert.match(source,/call\('deleteMyCommands'/);
 assert.ok(!/setMyCommands/.test(source));
});

test('нагадування зберігають кнопку оплати, без посилання на застосунок',async()=>{
 const {APP_URL,paidKb}=await keyboard;
 assert.equal(APP_URL,'https://nevsky-bi-user.github.io/my-cashflow/');
 assert.deepEqual(paidKb('paid:fixed:123'),{inline_keyboard:[[{text:'✅ Оплачено',callback_data:'paid:fixed:123'}]]});
 assert.equal(paidKb(null),undefined);
});
