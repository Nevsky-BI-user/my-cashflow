const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const keyboard=import(pathToFileURL(path.join(root,'supabase/functions/_shared/bot-kb.ts')).href);
const labels={
 balance:'💰 Баланс',chart:'📈 Графік',budget:'📊 Бюджет',week:'📅 Тиждень',month:'🔍 Місяць',
 income:'➕ Дохід',expense:'➖ Витрата',last:'📋 Останні',help:'❓ Допомога',app:'📱 Застосунок',
 menu:'⬅️ Головне меню',text:'✍️ Текстом',image:'📷 Зображенням',cancel:'✖ Скасувати',yes:'✅ Так, додати',
};
const rows=(keys)=>keys.map(row=>row.map(key=>({text:labels[key]})));

test('спільний контракт зберігає точні назви всіх 15 кнопок',async()=>{
 const {KB_BTN}=await keyboard;
 assert.deepEqual(KB_BTN,labels);
 assert.equal(new Set(Object.values(KB_BTN)).size,15);
});

test('головне меню відкриває всі дії та не пропонує підтвердження без операції',async()=>{
 const {MAIN_KB}=await keyboard;
 assert.deepEqual(MAIN_KB,{
  keyboard:rows([['income','expense'],['balance','chart'],['budget','week'],['month','last'],['help','app'],['menu','cancel']]),
  resize_keyboard:true,is_persistent:true,
 });
 const buttons=MAIN_KB.keyboard.flat().map(button=>button.text);
 assert.equal(new Set(buttons).size,12);
 for(const key of ['income','expense','balance','chart','budget','week','month','last','help','app','menu','cancel'])assert.ok(buttons.includes(labels[key]),key);
 assert.ok(!buttons.includes(labels.yes));
});

test('клавіатури введення пропонують текст, зображення та вихід із кроку',async()=>{
 const {ENTRY_KB,ENTRY_INPUT_KB}=await keyboard;
 assert.deepEqual(ENTRY_KB,{keyboard:rows([['text','image'],['menu','cancel']]),resize_keyboard:true,is_persistent:true});
 assert.deepEqual(ENTRY_INPUT_KB,{keyboard:rows([['menu','cancel']]),resize_keyboard:true,is_persistent:true});
});

test('каталог містить усі 15 команд з допустимими назвами й українськими описами',async()=>{
 const {BOT_COMMANDS}=await keyboard;
 const commands=['menu','income','expense','balance','chart','budget','week','month','last','app','help','cancel','yes','no','start'];
 assert.deepEqual(BOT_COMMANDS.map(item=>item.command),commands);
 assert.equal(new Set(BOT_COMMANDS.map(item=>item.command)).size,15);
 for(const {command,description} of BOT_COMMANDS){
  assert.match(command,/^[a-z0-9_]{1,32}$/);
  assert.ok(description.length>=1&&description.length<=256,command);
  assert.match(description,/[А-ЯІЇЄҐа-яіїєґ]/u);
  assert.ok(!description.includes('\n'),command);
 }
 const descriptions=Object.fromEntries(BOT_COMMANDS.map(item=>[item.command,item.description]));
 assert.match(descriptions.balance,/Поточний баланс/);
 assert.match(descriptions.chart,/прогноз/);
 assert.match(descriptions.budget,/періоду/);
 assert.match(descriptions.week,/тижня/);
 assert.match(descriptions.month,/Порівняння витрат/);
});

test('telegram-setup реєструє спільний каталог без локального дубліката',()=>{
 const source=fs.readFileSync(path.join(root,'supabase/functions/telegram-setup/index.ts'),'utf8');
 assert.match(source,/import\s*\{\s*BOT_COMMANDS\s*\}\s*from\s*'\.\.\/_shared\/bot-kb\.ts'/);
 assert.match(source,/call\('setMyCommands',\s*\{\s*commands:\s*BOT_COMMANDS\s*,?\s*\}\)/);
 assert.equal((source.match(/commands\s*:/g)||[]).length,1);
});

test('нагадування зберігають кнопку оплати й посилання на застосунок',async()=>{
 const {APP_URL,paidKb}=await keyboard;
 assert.equal(APP_URL,'https://nevsky-bi-user.github.io/my-cashflow/');
 assert.deepEqual(paidKb('paid:fixed:123'),{inline_keyboard:[[{text:'✅ Оплачено',callback_data:'paid:fixed:123'}]]});
 assert.deepEqual(paidKb(null),{inline_keyboard:[[{text:'📱 Відкрити застосунок',url:APP_URL}]]});
});
