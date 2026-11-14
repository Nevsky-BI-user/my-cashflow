// v232: витрати за рік на Бюджеті (yearSpendModel). Власник 14.11.2026: «діаграму витрат за рік… щоб бачити, скільки витрачав
// кожного місяця», обрав «щоденні + обовʼязкові». daily = «Витрачено» моделі місяця, paid = витрати з fixed_id чи credit_id.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const splitHelpers=html.split(/\r?\n/).filter(l=>/^function (splitOrdinaryCategory|splitEligible|txCategoryParts|isSavingsCategory|isDebtCategory)\(/.test(l)).join('\n');
const model=html.split('/* MONTHLY BUDGET MODEL */')[1].split('/* END MONTHLY BUDGET MODEL */')[0];
const monthly=html.split('/* CANONICAL MONTHLY PERIOD BUDGET */')[1].split('/* END CANONICAL MONTHLY PERIOD BUDGET */')[0];
const savings=html.slice(html.indexOf('function monthlySavingsReserve('),html.indexOf('function monthlyPlanCategories('));
const facts=html.slice(html.indexOf('function budgetRangeFacts('),html.indexOf('/* MONTHLY BUDGET MODEL */'));
const dependencies=html.split(/\r?\n/).filter(l=>/^const (getDow|wdRange|pbIso)=|^function pbPayouts\(|^function pbObl\(|^function fpMonth\(|^function fpWd\(|function fpEnded\(|const crOk=/.test(l)).join('\n');
const {monthlyBudgetModel,yearSpendModel}=new Function('const fmtM=v=>String(v);\n'+dependencies+'\n'+monthly+savings+splitHelpers+facts+model+';return{monthlyBudgetModel,yearSpendModel}')();
const cats=[{id:1,name:'Продукти'},{id:'savings',name:'Заощадження'},{id:3,name:'Комуналка'}];
const rows=[
 {id:1,date:'2026-11-03',type:'expense',amount:100,category_id:1},
 {id:1,date:'2026-11-03',type:'expense',amount:100,category_id:1},            // той самий id двічі: один раз
 {id:2,date:'2026-11-05',type:'expense',amount:50,category_id:'savings'},     // заощадження: не витрати
 {id:3,date:'2026-11-06',type:'expense',amount:30.5,category_id:3,fixed_id:7},// постійний платіж: сплачені обовʼязкові
 {id:4,date:'2026-11-07',type:'expense',amount:20,credit_id:2},              // розстрочка: сплачені обовʼязкові
 {id:5,date:'2026-11-08',type:'expense',amount:999,transfer_id:9},           // переказ: не входить
 {id:6,date:'2026-11-09',type:'income',amount:1000},
 {id:7,date:'2026-11-20',type:'expense',amount:500,category_id:1},           // після сьогодні: ще не витрачено
 {id:8,date:'2026-10-02',type:'expense',amount:200.1,category_id:1},
 {id:9,date:'2026-10-15',type:'expense',amount:40,fixed_id:7},
 {id:10,date:'2026-09-01',type:'income',amount:300},                         // лише дохід: н/д
 {id:11,date:'2025-12-31',type:'expense',amount:10,category_id:1},
 {id:12,date:'2025-11-30',type:'expense',amount:999,category_id:1},          // за межею 12 місяців
];

test('12 місяців до сьогодні: щоденні без заощаджень і переказів, сплачені обовʼязкові окремо, порожній місяць н/д',()=>{
 const y=yearSpendModel(()=>rows,cats,'2026-11-14');
 assert.equal(y.length,12);
 assert.deepEqual(y.map(m=>m.start),['2025-12-01','2026-01-01','2026-02-01','2026-03-01','2026-04-01','2026-05-01','2026-06-01','2026-07-01','2026-08-01','2026-09-01','2026-10-01','2026-11-01']);
 const by=Object.fromEntries(y.map(m=>[m.start,m]));
 assert.deepEqual([by['2026-11-01'].daily,by['2026-11-01'].paid],[10000,5050]);
 assert.deepEqual([by['2026-10-01'].daily,by['2026-10-01'].paid],[20010,4000]);
 assert.deepEqual([by['2026-09-01'].daily,by['2026-09-01'].paid],[null,null]);
 assert.deepEqual([by['2025-12-01'].daily,by['2025-12-01'].paid],[1000,0]);
 assert.deepEqual([by['2026-03-01'].daily,by['2026-03-01'].paid],[null,null]);
 assert.deepEqual(y.map(m=>[m.year,m.month]).slice(0,2),[[2025,11],[2026,0]]);
});

test('стовпець місяця дорівнює «Витрачено» моделі із збереженим бюджетом (картка Бюджету)',()=>{
 const saved={month_start:'2026-11-01',total_cents:500000,mandatory_items:[],allocations:{1:100000,savings:50000,3:20000}};
 const card=monthlyBudgetModel(saved,rows,cats,2026,10,'2026-11-14',null);
 const bar=yearSpendModel(()=>rows,cats,'2026-11-14').find(m=>m.start==='2026-11-01');
 assert.equal(bar.daily,card.spendableFact);
 assert.equal(bar.paid,card.expense-card.fact);
 const oct={month_start:'2026-10-01',total_cents:400000,mandatory_items:[],allocations:{1:100000}};
 assert.equal(yearSpendModel(()=>rows,cats,'2026-11-14').find(m=>m.start==='2026-10-01').daily,monthlyBudgetModel(oct,rows,cats,2026,9,'2026-11-14',null).spendableFact);
});

test('межа року: на 31.01 вікно лютий-січень, місяці й роки підряд',()=>{
 const y=yearSpendModel(()=>[],cats,'2026-01-31');
 assert.deepEqual([y[0].start,y[11].start],['2025-02-01','2026-01-01']);
 assert.ok(y.every(m=>m.daily===null&&m.paid===null));
 for(let i=1;i<12;i++)assert.equal((y[i].year*12+y[i].month)-(y[i-1].year*12+y[i-1].month),1);
});
