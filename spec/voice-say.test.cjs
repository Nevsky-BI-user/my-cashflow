// Коротка голосова відповідь (_shared/voice-say.ts): одна фраза з одним числом, без копійок, від тисячі до сотень.
// Власник 14.11.2026: «людина питає про баланс. значить потрібна одна цифра без копійок, можна навіть до сотні округлити».
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const mod=()=>import(pathToFileURL(path.resolve(__dirname,'../supabase/functions/_shared/voice-say.ts')).href);
const TODAY='2026-11-14';
const totals=(o={})=>({balanceCents:4234567,cardDebtCents:0,installmentsCents:0,next:null,...o});

test('округлення для мови: до тисячі цілі гривні, від тисячі до сотень, знак зберігається',async()=>{
 const {spokenCents:r}=await mod();
 const cases=[[0,0],[49,0],[50,100],[8590,8600],[99949,99900],[99950,100000],[123456,120000],[125000,130000],[1234567,1230000],[1225000,1230000],
  [1224999,1220000],[-4235000,-4240000],[-8590,-8600],[-49,0]];
 for(const [c,want] of cases)assert.equal(r(c),want,String(c));
});

test('баланс: одна фраза з одним числом, без копійок і без решти розділу',async()=>{
 const {sayBalance}=await mod();
 assert.equal(sayBalance(totals(),'balance'),'Баланс сорок дві тисячі триста гривень.');
 assert.equal(sayBalance(totals({balanceCents:-720000}),'balance'),'Баланс мінус сім тисяч двісті гривень.');
 assert.equal(sayBalance(totals({cardDebtCents:1000049}),'cards'),'Борг на картках десять тисяч гривень.');
 assert.equal(sayBalance(totals(),'cards'),'Боргу на картках немає.');
 assert.equal(sayBalance(totals({installmentsCents:928600}),'installments'),'За розстрочками лишилось сплатити девʼять тисяч триста гривень.');
 assert.equal(sayBalance(totals({next:{date:'2026-11-20',name:'Садочок',cents:964000}}),'payments'),'Найближчий платіж двадцятого листопада, Садочок: девʼять тисяч шістсот гривень.');
 assert.equal(sayBalance(totals(),'payments'),'Найближчих обовʼязкових платежів немає.');
 for(const s of ['balance','cards','installments','payments'])assert.ok(!/\d|копій/.test(sayBalance(totals({cardDebtCents:5,next:{date:'2026-11-20',name:'Інтернет',cents:35050}}),s)),s);
});

test('витрати: предмет, період і одна сума; без кількості операцій і переліку категорій',async()=>{
 const {saySpending}=await mod();
 const m=(o)=>({type:'expense',from:'2026-10-01',to:'2026-10-31',totalCents:819950,count:25,byCategory:[{name:'Кафе',cents:1,count:1}],category:null,search:null,...o});
 assert.equal(saySpending(m({category:'Продукти'}),TODAY),'Продукти за жовтень: вісім тисяч двісті гривень.');
 assert.equal(saySpending(m(),TODAY),'Витрати за жовтень: вісім тисяч двісті гривень.');
 assert.equal(saySpending(m({search:'атб',totalCents:45050}),TODAY),'атб за жовтень: чотириста пʼятдесят одна гривня.');
 assert.equal(saySpending(m({from:'2026-11-01',to:'2026-11-14',type:'income',totalCents:6545900}),TODAY),'Доходи з першого до чотирнадцятого листопада: шістдесят пʼять тисяч пʼятсот гривень.');
 assert.equal(saySpending(m({count:0,totalCents:0}),TODAY),'Витрат за жовтень немає.');
 assert.equal(saySpending(m({count:0,totalCents:0,category:'Кафе'}),TODAY),'Кафе за жовтень: витрат немає.');
});

test('бюджет: залишок або перевитрата одним числом, категорія за назвою з моделі',async()=>{
 const {sayBudget}=await mod();
 const b={start:'2026-11-06',end:'2026-11-20',poolCents:3000000,spentCents:1860000,leftCents:1140000,dailyCents:190000,leftDays:6,topOver:[],
  rows:[{id:'1',name:'Продукти',fact:820000,plan:900000,over:false,near:true},{id:'2',name:'Кафе',fact:310000,plan:200000,over:true,near:false},{id:'3',name:'Подарунки',fact:150000,plan:0,over:false,near:false,noPlan:true}]};
 assert.equal(sayBudget(b,null),'У бюджеті лишилось одинадцять тисяч чотириста гривень.');
 assert.equal(sayBudget({...b,leftCents:-250000},null),'Перевитрата бюджету дві тисячі пʼятсот гривень.');
 assert.equal(sayBudget(b,'продукти'),'Продукти: лишилось вісімсот гривень.');
 assert.equal(sayBudget(b,'Кафе'),'Кафе: перевитрата тисяча сто гривень.');
 assert.equal(sayBudget(b,'Подарунки'),'Подарунки: витрачено тисяча пʼятсот гривень.');
 assert.equal(sayBudget(b,'Авто'),'Авто: ні плану, ні витрат немає.');
 assert.equal(sayBudget({...b,rows:[...b.rows,{id:'4',name:'Здоровʼя',fact:50000,plan:100000}]},"здоров'я"),'Здоровʼя: лишилось пʼятсот гривень.','апостроф будь-якого виду');
 assert.equal(sayBudget(null,null),'Бюджет недоступний.');
});
