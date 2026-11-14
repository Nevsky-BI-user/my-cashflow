// Мовлення відповіді бота: суми, дати, відсотки, дні й кількості словами (_shared/uk-speech.ts)
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/uk-speech.ts')).href);

test('числа словами: рід, тисячі, мільйони, нуль, мінус',async()=>{
 const {numberWords:n}=await mod();
 assert.equal(n(0),'нуль');
 assert.equal(n(1),'один'); assert.equal(n(1,'f'),'одна'); assert.equal(n(2,'f'),'дві'); assert.equal(n(2,'n'),'два');
 assert.equal(n(11),'одинадцять'); assert.equal(n(19),'девʼятнадцять'); assert.equal(n(40),'сорок'); assert.equal(n(90),'девʼяносто');
 assert.equal(n(1000),'тисяча'); assert.equal(n(1001),'тисяча один'); assert.equal(n(2000),'дві тисячі'); assert.equal(n(5000),'пʼять тисяч');
 assert.equal(n(21000),'двадцять одна тисяча'); assert.equal(n(12345),'дванадцять тисяч триста сорок пʼять');
 assert.equal(n(111000),'сто одинадцять тисяч'); assert.equal(n(1000000),'мільйон'); assert.equal(n(2500000),'два мільйони пʼятсот тисяч');
 assert.equal(n(-300),'мінус триста');
});

test('гривні й копійки: узгодження, копійки лише ненульові',async()=>{
 const {moneyWords:m}=await mod();
 assert.equal(m(100),'одна гривня');
 assert.equal(m(200),'дві гривні');
 assert.equal(m(500),'пʼять гривень');
 assert.equal(m(1100),'одинадцять гривень');
 assert.equal(m(2100),'двадцять одна гривня');
 assert.equal(m(230000),'дві тисячі триста гривень');
 assert.equal(m(1234567),'дванадцять тисяч триста сорок пʼять гривень шістдесят сім копійок');
 assert.equal(m(150),'одна гривня пʼятдесят копійок');
 assert.equal(m(1),'одна копійка');
 assert.equal(m(0),'нуль гривень');
 assert.equal(m(-1000000),'мінус десять тисяч гривень');
});

test('сума з тексту: пробіли Intl, один знак після коми = десятки копійок',async()=>{
 const {parseMoneyCents:p}=await mod();
 assert.equal(p('12 345,67'),1234567);
 assert.equal(p('1 470,5'),147050);
 assert.equal(p('-3 000'),-300000);
 assert.equal(p('abc'),null);
});

test('дати: родовий відмінок, діапазон одного місяця',async()=>{
 const {toSpeech:t,dateWords:d}=await mod();
 assert.equal(d(1,1),'першого січня'); assert.equal(d(25,11),'двадцять пʼятого листопада'); assert.equal(d(30,4),'тридцятого квітня');
 assert.equal(d(31,12),'тридцять першого грудня'); assert.equal(d(20,10),'двадцятого жовтня'); assert.equal(d(32,1),null);
 assert.equal(t('Борг до 25.11'),'Борг до двадцять пʼятого листопада');
 assert.equal(t('06.11-20.11'),'з шостого до двадцятого листопада');
 assert.equal(t('28.10-05.11'),'з двадцять восьмого жовтня до пʼятого листопада');
 assert.equal(t('до 05.03.2027'),'до пʼятого березня');
});

test('рядки бота: суми, «/день», «дн.», відсотки, «×» і «=»',async()=>{
 const {toSpeech:t}=await mod();
 const N=' ';
 assert.equal(t(`Бюджет до 20.11: лишилось 5${N}000 ₴ · 384,62 ₴/день (13 дн.)`),
  'Бюджет до двадцятого листопада: лишилось пʼять тисяч гривень, триста вісімдесят чотири гривні шістдесят дві копійки на день, тринадцять днів.');
 assert.equal(t(`Власні кошти: 3${N}760,65 ₴`),'Власні кошти: три тисячі сімсот шістдесят гривень шістдесят пʼять копійок');
 assert.equal(t('Баланс: -6 239,35 ₴'),'Баланс: мінус шість тисяч двісті тридцять девʼять гривень тридцять пʼять копійок');
 assert.equal(t('Зросли на 15%'),'Зросли на пʼятнадцять відсотків');
 assert.equal(t('+12,5%'),'плюс дванадцять кома пʼять відсотка');
 assert.equal(t(`Айфон: 3 × 1${N}000 ₴ = 3${N}000 ₴`),'Айфон: три платежі, кожен тисяча гривень, разом три тисячі гривень');
 assert.equal(t('34 операції'),'тридцять чотири операції');
 assert.equal(t('1 операція, 2 операції, 21 день'),'одна операція, дві операції, двадцять один день');
 assert.equal(t('500 грн'),'пʼятсот гривень');
});

test('символи й розмітка не потрапляють у мову',async()=>{
 const {toSpeech:t}=await mod();
 assert.equal(t('💰 <b>Баланс</b>: 100 ₴\n⚠️ Без рахунку'),'Баланс: одна гривня. Без рахунку'.replace('одна гривня','сто гривень'));
 assert.doesNotMatch(t('Картки:\nОщад: 3 237 ₴ · борг 10 000 ₴'),/[0-9₴·]/);
});
