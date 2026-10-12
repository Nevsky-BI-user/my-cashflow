// Синтетична фікстура для тестів звітів бота (spec/bot-reports.test.cjs): прод-подібна структура, вигадані дані.
// Детермінована (власний генератор випадкових чисел), сьогодні 2026-10-12.
function botFixture(){
let seed=7;const rnd=()=>{seed=(seed*16807)%2147483647;return (seed-1)/2147483646;};
const stamp='2026-10-12T07:00:00Z';
const accounts=[
 {id:1,name:'Ощадбанк',bank:'oschad',kind:'debit',balance:2519,debt:0,active:true,balance_updated_at:stamp,mono_account_id:null},
 {id:2,name:'monobank',bank:'mono',kind:'debit',balance:1800,debt:0,active:true,balance_updated_at:stamp,mono_account_id:'m2'},
 {id:3,name:'Monobank',bank:'mono',kind:'credit',balance:0,debt:29070.45,credit_limit:50000,debt_month:'2026-10-01',active:true,balance_updated_at:stamp,mono_account_id:'m1'},
 {id:4,name:'ПриватБанк',bank:'privat',kind:'credit',balance:0,debt:9256.55,credit_limit:30000,debt_month:'2026-09-01',active:true,balance_updated_at:stamp,mono_account_id:null},
 {id:5,name:'Готівка',bank:'cash',kind:'cash',balance:1000,debt:0,active:true,balance_updated_at:stamp,mono_account_id:null}];
const salary={rate:130900,advance_day:21,salary_day:6,split_day:15,advance_amount:0,salary_amount:0,savings_pct:0};
const fixed=[
 {id:11,name:'Інтернет',amount:300,day_of_month:13,type:'expense',active:true,bank:'privat',period:'month'},
 {id:12,name:'Комуналка',amount:2500,day_of_month:20,type:'expense',active:true,bank:'oschad',period:'month',credit_ok:true},
 {id:13,name:'Прибирання',amount:500,day_of_month:1,type:'expense',active:true,bank:'cash',period:'week',weekday:1},
 {id:14,name:'Спортзал',amount:900,day_of_month:25,type:'expense',active:true,bank:'mono',period:'month'}];
const credits=[
 {id:21,name:'Ecoflow',monthly_amount:2083,payment_day:12,start_year:2026,start_month:8,total_payments:10,source:'mono'},
 {id:22,name:'Телефон',monthly_amount:1500,payment_day:13,start_year:2026,start_month:5,total_payments:12,source:'privat'}];
const cats=[['Продукти',40,'#a8d672'],['Кафе',15,'#f6a54c'],['Транспорт',10,'#6fb7ff'],['Здоровʼя',10,'#ff8fa3'],['Дім',10,'#6fd3b0'],
 ['Розваги',10,'#c4a1ff'],['Постійні платежі',0,null],['Розстрочки',0,null],['Інше',5,'#b8c1cc']].map(([name,w,color],i)=>({id:i+1,name,budget_limit:w,color,is_income:false,sort_order:i}));
cats.push({id:20,name:'Зарплата',budget_limit:0,is_income:true,color:null,sort_order:20});
const places={1:['Сільпо','АТБ','Novus','Фора'],2:['Aroma Kava','Пузата хата','McDonaldʼs'],3:['Uklon','Bolt','WOG'],4:['Аптека АНЦ','Аптека Доброго дня'],5:['Епіцентр','JYSK'],6:['Планета Кіно','Steam']};
const tx=[];let id=1;
const add=(account_id,type,amount,date,description,category_id,extra={})=>tx.push({id:id++,account_id,type,amount:Math.round(amount*100)/100,date,created_at:date+'T10:00:00Z',source:account_id===2||account_id===3?'mono':'manual',description,category_id,...extra});
const iso=t=>new Date(t).toISOString().slice(0,10);
for(let t=Date.parse('2026-09-01T00:00:00Z');t<=Date.parse('2026-10-12T00:00:00Z');t+=86400000){
 const d=iso(t);const n=1+Math.floor(rnd()*3);
 for(let k=0;k<n;k++){const r=rnd();const cat=r<0.45?1:r<0.62?2:r<0.75?3:r<0.83?4:r<0.92?5:6;const list=places[cat];
  const amt=cat===1?150+rnd()*900:cat===5?300+rnd()*2500:80+rnd()*600;
  const acc=[1,3,4,5,2][Math.floor(rnd()*5)];add(acc,'expense',amt,d,list[Math.floor(rnd()*list.length)],cat);}
}
add(1,'income',65450,'2026-09-07','Зарплата',20);add(1,'income',61200,'2026-09-21','Аванс',20);add(1,'income',69700,'2026-10-06','Зарплата',20);
add(4,'expense',300,'2026-09-14','Інтернет',7,{fixed_id:11});add(1,'expense',2500,'2026-09-21','Комуналка',7,{fixed_id:12});
add(3,'expense',2083,'2026-09-12','Ecoflow',8,{credit_id:21});add(4,'expense',1500,'2026-09-13','Телефон',8,{credit_id:22});
add(5,'expense',500,'2026-10-06','Прибирання',7,{fixed_id:13});add(3,'expense',2083,'2026-10-12','Ecoflow',8,{credit_id:21});
// погашення Привату з Ощаду: пара операцій
add(1,'expense',3000,'2026-10-08','Погашення Приват',null);add(4,'income',3000,'2026-10-08','Погашення',null);
add(null,'expense',420,'2026-10-12','Кава без рахунку',2);tx[tx.length-1].source='telegram';tx[tx.length-1].created_at='2026-10-12T08:00:00Z';
return {today:'2026-10-12',accounts,salary,fixed,credits,categories:cats.map(c=>({...c,type:c.is_income?'income':'expense'})),transactions:tx};
}
module.exports={botFixture};
