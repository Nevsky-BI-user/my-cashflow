// Голосовий запис операції (_shared/voice-entry.ts): сума й опис з тексту розпізнавача, питання не стає записом
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/voice-entry.ts')).href);

test('записи: сума першою чи останньою, гривні, копійки, тисячі, плюс і дохід',async()=>{
 const {parseVoiceEntry:p}=await mod();
 assert.deepEqual(p('500 гривень продукти.'),{type:'expense',amount:'500',description:'продукти'});
 assert.deepEqual(p('Плюс 65 459 гривень зарплата.'),{type:'income',amount:'65459',description:'зарплата'});
 assert.deepEqual(p('+51000 зарплата'),{type:'income',amount:'51000',description:'зарплата'});
 assert.deepEqual(p('Витратила 250 на каву'),{type:'expense',amount:'250',description:'каву'});
 assert.deepEqual(p('кава 85 гривень'),{type:'expense',amount:'85',description:'кава'});
 assert.deepEqual(p('1.250 грн АТБ приват'),{type:'expense',amount:'1250',description:'АТБ приват'});
 assert.deepEqual(p('120,50 таксі'),{type:'expense',amount:'120.50',description:'таксі'});
 assert.deepEqual(p('99 гривень 90 копійок молоко'),{type:'expense',amount:'99.90',description:'молоко'});
 assert.deepEqual(p('Запиши витрату 300 гривень, аптека'),{type:'expense',amount:'300',description:'аптека'});
 assert.deepEqual(p('Запиши 300 гривень, аптека'),{type:'expense',amount:'300',description:'аптека'});
 assert.deepEqual(p('Дохід 2000 подарунок'),{type:'income',amount:'2000',description:'подарунок'});
});

test('не записи: питання, без суми, без опису, нуль',async()=>{
 const {parseVoiceEntry:p}=await mod();
 for(const t of['Скільки ми витратили на продукти?','скільки за 2 тижні на кафе','Який баланс','Покажи витрати за 3 дні',
  'продукти','500','500 гривень','0 гривень кава','Привіт','чи вистачить 5000 до зарплати'])
  assert.equal(p(t),null,t);
});

test('сума: групи тисяч лише по три цифри, дробова частина до двох цифр',async()=>{
 const {voiceAmount:a}=await mod();
 assert.equal(a('65 459'),'65459'); assert.equal(a('1,250'),'1250'); assert.equal(a('12,5'),'12.5');
 assert.equal(a('1 250,75'),'1250.75'); assert.equal(a('12 34'),null); assert.equal(a('0'),null);
});
