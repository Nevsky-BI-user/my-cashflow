// Активна модель застосунку й Telegram: financeProjection (docs/redesign/projection-contract.md, 10.10.2026).
// Старі periodBudget/freeToPayout та nextPeriodPlan залишено для сумісності й історичних перевірок.
// Перенесено з scripts/budget_pool.py і scripts/salary_check.py; те саме рахує застосунок (periodBudget).
// Чисті функції без залежностей: модуль запускається і в Edge Function, і в Node для звірки з Python.
// Дати: рядки YYYY-MM-DD, обчислення в UTC, щоб часовий пояс не зсував день.

export type Account = {
  credit_limit?: number | string | null;
  id?: number | string; name?: string; kind?: string; balance: number | string; debt: number | string; active?: boolean;
  mono_account_id?: string | null; balance_updated_at?: string | null; debt_month?: string | null;
  min_spend?: number | string | null; min_spend_fee?: number | string | null;
  debt_months?: [string, number][]; // кошики боргу за місяцем (п. 12), ставить deriveAccounts
};
// Операція з привʼязкою до рахунку (для похідного балансу ручних рахунків)
// source: 'mono' | 'telegram' | 'manual' (потрібен лише для unassignedAdj: операції Monobank без рахунку не рахуємо)
// date: дата операції (YYYY-MM-DD), потрібна для порогу мінімальних витрат (без неї перші 10 знаків created_at)
// fixed_id: операція оплачує постійний платіж (п. 13), див. fixedPaid; credit_id: оплата розстрочки свого місяця
export type AccTx = {
  id?: string | number; category_id?: string | number | null;
  account_id: number | string | null; type: string; amount: number | string; created_at: string; source?: string | null; date?: string | null;
  fixed_id?: number | string | null; credit_id?: number | string | null;
};
// Поріг мінімальних витрат рахунку за календарний місяць (DESIGN.md, п. 11)
export type MinSpendRow = { accountId: number; month: string; spent: number; min: number; fee: number; left: number; metOn?: string };
// variable: сума змінна, amount = середня оцінка (п. 13; на розрахунок не впливає)
// period: 'month' (день day_of_month) або 'week' (ISO-день weekday 1=пн..7=нд; без коректного weekday подій немає); bank: лише підпис
export type Fixed = {
  id?: number | string; name: string; amount: number | string; day_of_month: number; type: string; active?: boolean;
  credit_ok?: boolean | null; variable?: boolean | null;
  period?: string | null; weekday?: number | string | null; bank?: string | null;
};
export type Credit = {
  id?: number | string; name: string; monthly_amount: number | string; payment_day: number;
  start_year: number; start_month: number; total_payments: number; credit_ok?: boolean | null; source?: string | null;
};
export type SalaryCfg = { rate?: number | string | null; advance_amount?: number | string | null; salary_amount?: number | string | null; split_day: number; advance_day: number; salary_day: number; savings_pct?: number | null };
// paid: ключі `${fixed_id}|YYYY-MM` і `${fixed_id}|W<понеділок YYYY-MM-DD>` оплачених постійних платежів (п. 13), будує fixedPaid з операцій
export type Snapshot = { accounts: Account[]; fixed: Fixed[]; credits: Credit[]; salary: SalaryCfg; savings_pct?: number | null; paid?: string[] };

export type Payout = { date: string; kind: 'advance' | 'salary'; amount: number };
export type Obligation = { date: string; name: string; amount: number; credit_ok: boolean };

const DAY = 86_400_000;
const mk = (y: number, m: number, d: number) => new Date(Date.UTC(y, m - 1, d)); // m: 1..12
const iso = (d: Date) => d.toISOString().slice(0, 10);
const parse = (s: string) => new Date(s + 'T00:00:00Z');
export const addDays = (s: string, n: number) => iso(new Date(parse(s).getTime() + n * DAY));
export const diffDays = (a: string, b: string) => Math.round((parse(b).getTime() - parse(a).getTime()) / DAY);
const lastDay = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();
// ISO-день тижня дати YYYY-MM-DD: 1=пн..7=нд
const isoWeekday = (s: string) => (parse(s).getUTCDay() + 6) % 7 + 1;
const round2 = (x: number) => Math.round(x * 100) / 100;
const num = (x: unknown) => Number(x) || 0;

// Похідний баланс ручних рахунків (DESIGN.md, «Наскрізне»): для рахунку без mono_account_id
// додаємо операції з його account_id, створені строго після balance_updated_at.
// debit/cash: balance − витрати + доходи; credit: спершу витрачаються власні кошти,
// а надходження спершу погашають борг. Невикористаний дохід збільшує власний залишок.
// Рахунки Monobank не коригуємо: баланс з API уже містить усі операції. Без мітки часу теж не коригуємо.
// Витрата: усе, що не 'income' (як у freeBlock). Повертає копії, вхідні обʼєкти не змінює.
export function deriveAccounts(accounts: Account[], txs: AccTx[]): Account[] {
  return (accounts || []).map((a) => {
    const out = { ...a };
    if (a.mono_account_id || a.id == null || !a.balance_updated_at) return out;
    const since = Date.parse(a.balance_updated_at);
    if (isNaN(since)) return out;
    let exp = 0, inc = 0;
    // кошики боргу за місяцем (п. 12): збережений борг у debt_month (без нього місяць мітки), витрати за датою операції
    const bk: Record<string, number> = { [String(a.debt_month || '').slice(0, 7) || String(a.balance_updated_at).slice(0, 7)]: num(a.debt) };
    for (const t of txs || []) {
      if (t.account_id == null || String(t.account_id) !== String(a.id) || !(Date.parse(t.created_at) > since)) continue;
      if (t.type === 'income') inc += num(t.amount);
      else {
        exp += num(t.amount);
        const m = String(t.date || t.created_at).slice(0, 7);
        bk[m] = (bk[m] || 0) + num(t.amount);
      }
    }
    if (a.kind === 'credit') {
      out.debt = round2(Math.max(0, num(a.debt) + exp - inc));
      let left = inc; // доходи (погашення) гасять найстаріші кошики
      const months: [string, number][] = [];
      for (const m of Object.keys(bk).sort()) {
        const v = bk[m] - Math.min(left, bk[m]);
        left -= bk[m] - v;
        if (round2(v) > 0) months.push([m, round2(v)]);
      }
      out.debt_months = months;
    } else out.balance = round2(num(a.balance) - exp + inc);
    return out;
  });
}

// Канонічна проєкція: вхід у гривнях, вихід у копійках; без I/O та мутації входу.
// Функція самодостатня, щоб автономний фронтенд міг вбудувати той самий алгоритм.
export function financeProjection(data: NextPeriodInput, options: {asof: string; through: string; scenario?: {selections: {occurrenceId: string; accountId: string | number; amountCents: number}[]} | null}) {
  const {asof, through} = options;
  const cmp = (a: any, b: any) => a < b ? -1 : a > b ? 1 : 0;
  const day = (s: string) => new Date(s + 'T00:00:00Z');
  const iso = (d: Date) => d.toISOString().slice(0,10);
  const date = (y: number,m: number,d: number) => iso(new Date(Date.UTC(y,m-1,d)));
  const plus = (s: string,n: number) => iso(new Date(day(s).getTime()+n*86400000));
  const distance = (a: string,b: string) => Math.round((day(b).getTime()-day(a).getTime())/86400000);
  for (const s of [asof,through]) if (!/^\d{4}-\d{2}-\d{2}$/.test(s) || !Number.isFinite(day(s).getTime()) || iso(day(s))!==s) throw new RangeError('Invalid date');
  if (through<asof || distance(asof,through)>3660) throw new RangeError('Invalid horizon');
  const safe = (v: number) => {if (!Number.isSafeInteger(v)) throw new RangeError('Unsafe cents');return v;};
  const cents = (v: unknown) => {
    const n=Number(v??0); if(!Number.isFinite(n)) throw new RangeError('Invalid money');
    const [coefficient, exponent='0']=String(n).toLowerCase().split('e');
    const neg=coefficient.startsWith('-'),[whole,fraction='']=coefficient.replace('-','').split('.');
    let digits=BigInt(whole+fraction);const shift=2+Number(exponent)-fraction.length;
    if(shift>=0)digits*=10n**BigInt(shift);else{const divisor=10n**BigInt(-shift);digits=(digits+divisor/2n)/divisor;}
    return safe(Number(neg?-digits:digits));
  };
  const sum = (values: number[]) => safe(values.reduce((s,v)=>s+v,0));
  const txDate = (t: AccTx) => String(t.date||t.created_at||'').slice(0,10);
  const seen=new Set();
  const txs=(data.transactions??data.account_tx??[]).filter(t=>{if(txDate(t)>asof)return false;if(t.id==null)return true;const id=String(t.id);if(seen.has(id))return false;seen.add(id);return true;}).slice().sort((a,b)=>(Date.parse(a.created_at)-Date.parse(b.created_at))||cmp(String(a.id??''),String(b.id??'')));
  const accounts: Record<string,any>[]=(data.accounts||[]).filter(a=>a.active!==false).map((original,index)=>{
    const a={...original,id:original.id??('unidentified:'+index)};
    let balance=cents(a.balance),debt=Math.max(0,cents(a.debt));
    const month=String(a.debt_month||a.balance_updated_at||asof).slice(0,7);
    const buckets: Record<string,number>={};
    for(const [m,v] of a.debt_months||[[month,debt/100]])buckets[m]=(buckets[m]||0)+Math.max(0,cents(v));
    // Залишок боргу завжди узгоджений зі знімком; неповні кошики доповнюємо.
    let excess=sum(Object.values(buckets))-debt;
    if(excess<0)buckets[month]=(buckets[month]||0)-excess;
    if(excess>0)for(const m of Object.keys(buckets).sort().reverse()){const n=Math.min(excess,buckets[m]);buckets[m]-=n;excess-=n;}
    if(!a.mono_account_id&&a.id!=null&&Number.isFinite(Date.parse(a.balance_updated_at||''))){
      for(const t of txs){if(String(t.account_id)!==String(a.id)||!(Date.parse(t.created_at)>Date.parse(a.balance_updated_at!)))continue;const amount=Math.max(0,cents(t.amount));
        if(a.kind!=='credit'){balance=safe(balance+(t.type==='income'?amount:-amount));continue;}
        if(t.type==='income'){let left=amount;for(const m of Object.keys(buckets).sort()){const n=Math.min(left,buckets[m]);buckets[m]-=n;left-=n;debt-=n;}balance=safe(balance+left);}
        else{const own=Math.min(Math.max(0,balance),amount);balance-=own;const borrowed=amount-own;const m=txDate(t).slice(0,7);buckets[m]=(buckets[m]||0)+borrowed;debt=safe(debt+borrowed);}
      }
    }
    return {...a,balance:balance/100,debt:debt/100,balanceCents:balance,debtCents:debt,debt_months:Object.keys(buckets).sort().filter(m=>buckets[m]>0).map(m=>[m,buckets[m]/100])};
  });
  const stamps=accounts.filter(a=>!a.mono_account_id).map(a=>Date.parse(a.balance_updated_at||'')).filter(Number.isFinite);
  const adjustment=stamps.length?sum(txs.filter(t=>t.account_id==null&&t.source!=='mono'&&Date.parse(t.created_at)>Math.min(...stamps)).map(t=>(t.type==='income'?1:-1)*cents(t.amount))):0;
  const positiveOwnCents=Math.max(0,sum([...accounts.map(a=>Math.max(0,a.balanceCents)),adjustment]));
  const cashCents=sum([...accounts.map(a=>a.balanceCents),adjustment]);
  // Борг усіх карток, і кредитних, і дебетових з боргом (як Mono з лімітом); кожен кошик має одну подію погашення.
  const creditDebtCents=sum(accounts.map(a=>a.debtCents));
  const snapshot={positiveOwnCents,cashCents,unassignedAdjustmentCents:adjustment,creditDebtCents,accounts,warnings:[]};
  const cfg: Record<string,any>|null|undefined=data.salary;
  const valid=cfg&&[cfg.advance_day,cfg.salary_day,cfg.split_day].every(v=>Number.isInteger(Number(v))&&Number(v)>=1&&Number(v)<=31);
  const monthIndex=(s: string)=>Number(s.slice(0,4))*12+Number(s.slice(5,7))-1;
  const ym=(k: number)=>[Math.floor(k/12),k%12+1];
  const last=(y: number,m: number)=>new Date(Date.UTC(y,m,0)).getUTCDate();
  const weekdays=(y: number,m: number,lo: number,hi: number)=>{let n=0;for(let d=lo;d<=hi;d++){const w=day(date(y,m,d)).getUTCDay();if(w!==0&&w!==6)n++;}return n;};
  const payoutList: Record<string,any>[]=[];
  if(valid)for(let k=monthIndex(asof)-2;k<=monthIndex(through)+3;k++){
    const [y,m]=ym(k),[py,pm]=ym(k-1);
    for(const kind of ['advance','salary']){let d=date(y,m,Number(cfg[kind+'_day']));const w=day(d).getUTCDay();d=plus(d,w===6?-1:w===0?1:0);const [sy,sm]=kind==='advance'?[y,m]:[py,pm];const rate=Number(cfg.rate)||0;
      const amountCents=rate>0?cents(rate/weekdays(sy,sm,1,last(sy,sm))*weekdays(sy,sm,kind==='advance'?1:Number(cfg.split_day)+1,kind==='advance'?Number(cfg.split_day):last(sy,sm))):cents(cfg[kind+'_amount']);
      if(amountCents>0)payoutList.push({date:d,kind,amount:amountCents/100,amountCents});
    }
  }
  payoutList.sort((a,b)=>cmp(a.date,b.date)||cmp(a.kind,b.kind));
  // Виплати одного дня належать одному періоду та надходять разом.
  const payoutDates=[...new Set(payoutList.map(p=>p.date))].sort();
  const nextDate=payoutDates.find(d=>d>asof)||'',followingDate=payoutDates.find(d=>nextDate&&d>nextDate)||'';
  const hasPlan=Boolean(nextDate&&followingDate);
  const payoutAt=(d: string)=>{const list=payoutList.filter(p=>p.date===d);const amountCents=sum(list.map(p=>p.amountCents));return {...list[0],amount:amountCents/100,amountCents};};
  const endGeneration=payoutDates.find(d=>d>through&&d>=followingDate)||plus(through,1);
  const events: Record<string,any>[]=[];
  const make=(id: string,d: string,name: string,kind: string,amount: number,extra: Record<string,any>={})=>({id,occurrenceId:id,date:d,name,kind,cashDeltaCents:kind==='income'||kind==='payout'?amount:-amount,debtDeltaCents:0,funding:'cash',certainty:'planned',amountCents:amount,...extra});
  for(const p of payoutList)if(p.date>asof&&p.date<=endGeneration)events.push(make('payout:'+p.kind+':'+p.date,p.date,p.kind==='advance'?'Аванс':'Зарплата','payout',p.amountCents));
  // ISO-день тижня 1=пн..7=нд і понеділок тижня дати.
  const isoDay=(s: string)=>(day(s).getUTCDay()+6)%7+1;
  const monday=(s: string)=>plus(s,1-isoDay(s));
  const weekly=(f: Fixed)=>f.period==='week';
  // Витрата з fixed_id закриває місяць своєї дати і тиждень пн-нд; витрата з credit_id: розстрочку свого місяця.
  const paid=new Set(txs.filter(t=>t.type==='expense'&&t.fixed_id!=null).flatMap(t=>{const d=txDate(t);return [String(t.fixed_id)+'|'+d.slice(0,7),...(/^\d{4}-\d{2}-\d{2}$/.test(d)?[String(t.fixed_id)+'|W'+monday(d)]:[])];}));
  const paidCredit=new Set(txs.filter(t=>t.type==='expense'&&t.credit_id!=null).map(t=>String(t.credit_id)+'|'+txDate(t).slice(0,7)));
  for(let k=monthIndex(asof);k<=monthIndex(endGeneration);k++){
    const [y,m]=ym(k),month=date(y,m,1).slice(0,7);
    (data.fixed||[]).forEach((f,i)=>{const d=date(y,m,Math.min(Number(f.day_of_month),last(y,m)));if(weekly(f)||f.active===false||d<asof||d>endGeneration||(f.id!=null&&paid.has(String(f.id)+'|'+month)))return;events.push(make('fixed:'+String(f.id??i)+':'+month,d,f.name,f.type==='income'?'income':'mandatory',Math.max(0,cents(f.amount)),{creditEligible:f.type!=='income'&&f.credit_ok===true}));});
    // Розстрочка з датою <= asof сплачена за планом; витрата з credit_id закриває платіж свого місяця.
    (data.credits||[]).forEach((c,i)=>{const d=date(y,m,Math.min(Number(c.payment_day),last(y,m))),first=Number(c.start_year)*12+Number(c.start_month);if(d<=asof||d>endGeneration||k<first||k>=first+Number(c.total_payments)||(c.id!=null&&paidCredit.has(String(c.id)+'|'+month)))return;events.push(make('installment:'+String((c as any).id??i)+':'+month,d,c.name+' (розстрочка)','mandatory',Math.max(0,cents(c.monthly_amount)),{creditEligible:c.credit_ok===true}));});
  }
  // Щотижневі постійні: подія на кожну дату з ISO-днем weekday, id з датою події; оплачений тиждень подій не дає.
  (data.fixed||[]).forEach((f,i)=>{const w=Number(f.weekday);if(!weekly(f)||f.active===false||!Number.isInteger(w)||w<1||w>7)return;
    for(let d=plus(asof,(w-isoDay(asof)+7)%7);d<=endGeneration;d=plus(d,7)){if(f.id!=null&&paid.has(String(f.id)+'|W'+monday(d)))continue;events.push(make('fixed:'+String(f.id??i)+':'+d,d,f.name,f.type==='income'?'income':'mandatory',Math.max(0,cents(f.amount)),{creditEligible:f.type!=='income'&&f.credit_ok===true}));}
  });
  const dueFor=(m: string)=>{const [y,n]=ym(monthIndex(m+'-01')+1);return date(y,n,24);};
  for(const a of accounts)for(const [month,amount] of a.debt_months){const due=dueFor(month),planned=due<asof?asof:nextDate&&nextDate<due?nextDate:due;events.push(make('repay:'+String(a.id)+':'+month,planned,a.name||'Погашення кредитки','repay',cents(amount),{accountId:a.id,debtDeltaCents:-cents(amount),contractualDueDate:due,plannedRepaymentDate:planned}));}
  const minSpend: Record<string,any>[]=[];
  for(const a of accounts){if(a.id==null||cents(a.min_spend)<=0)continue;let spent=0,metOn;
    for(const t of txs.filter(t=>String(t.account_id)===String(a.id)&&t.type==='expense'&&txDate(t).slice(0,7)===asof.slice(0,7)).sort((a,b)=>cmp(txDate(a),txDate(b))||cmp(String(a.created_at),String(b.created_at))||cents(a.amount)-cents(b.amount))){spent+=cents(t.amount);if(metOn==null&&spent>=cents(a.min_spend))metOn=txDate(t);}
    minSpend.push({accountId:a.id,month:asof.slice(0,7),spent:spent/100,min:cents(a.min_spend)/100,fee:cents(a.min_spend_fee)/100,left:Math.max(0,cents(a.min_spend)-spent)/100,...(metOn?{metOn}:{})});
  }
  const order: Record<string,number>={payout:0,income:1,repay:2,mandatory:3,fee:4,variable:5};
  const compareEvents=(a: Record<string,any>,b: Record<string,any>)=>cmp(a.date,b.date)||order[a.kind]-order[b.kind]||cmp(a.id,b.id);
  const scenario: {selectedCents:number;newDebtCents:number;cashPlanCents:number;gapCents:number;repayments:Record<string,any>[];errors:string[]}|null=options.scenario?{selectedCents:0,newDebtCents:0,cashPlanCents:0,gapCents:0,repayments:[],errors:[]}:null;
  // Перевірка ліміту на дату вибраної події враховує попередні погашення та позики.
  if(scenario){
    const selections=options.scenario!.selections||[];
    const used=new Set();
    for(const selection of selections.slice().sort((a,b)=>compareEvents(events.find(e=>e.occurrenceId===a.occurrenceId)||{date:'9999',kind:'mandatory',id:a.occurrenceId},events.find(e=>e.occurrenceId===b.occurrenceId)||{date:'9999',kind:'mandatory',id:b.occurrenceId}))){
      const e=events.find(e=>e.occurrenceId===selection.occurrenceId&&e.kind==='mandatory'),a=accounts.find(a=>String(a.id)===String(selection.accountId)),n=selection.amountCents;
      let error='';
      if(!e||e.creditEligible!==true)error='Платіж не дозволений для кредитного сценарію.';
      else if(used.has(e.id)||!Number.isSafeInteger(n)||n<=0||n>e.amountCents)error='Некоректна сума або повторний вибір платежу.';
      else if(!a||a.kind!=='credit'||a.credit_limit==null)error='Для кредитного рахунку потрібен відомий ліміт.';
      else{const debtAt=a.debtCents+sum(events.filter(v=>String(v.accountId)===String(a.id)&&compareEvents(v,e)<0).map(v=>v.debtDeltaCents));if(n>cents(a.credit_limit)-debtAt)error='На дату платежу бракує кредитного ліміту.';}
      if(error||!e||!a){scenario.errors.push(error);continue;}
      used.add(e.id);scenario.selectedCents+=n;scenario.newDebtCents+=n;
      e.cashDeltaCents+=n;
      if(n===e.amountCents){e.funding='credit';e.accountId=a.id;e.debtDeltaCents=n;}
      else{e.amountCents-=n;events.push({...e,id:e.id+':credit',amountCents:n,cashDeltaCents:0,debtDeltaCents:n,funding:'credit',accountId:a.id});}
      const due=dueFor(e.date.slice(0,7));const repayment=make('scenario-repay:'+e.occurrenceId+':'+String(a.id),due,'Погашення сценарного боргу','repay',n,{accountId:a.id,debtDeltaCents:-n,contractualDueDate:due,plannedRepaymentDate:due});
      scenario.repayments.push(repayment);events.push(repayment);
    }
  }
  // Поточний місяць підтверджують факти; майбутній: лише явно задане фінансування.
  for(let k=monthIndex(asof);k<=monthIndex(endGeneration);k++){
    const [y,m]=ym(k),month=date(y,m,1).slice(0,7),[ny,nm]=ym(k+1),d=date(ny,nm,1);if(d>endGeneration)continue;
    for(const a of accounts){if(a.id==null||cents(a.min_spend)<=0||cents(a.min_spend_fee)<=0)continue;
      const actual=sum(txs.filter(t=>String(t.account_id)===String(a.id)&&t.type==='expense'&&txDate(t).slice(0,7)===month).map(t=>cents(t.amount)));
      const assigned=month===asof.slice(0,7)?0:sum(events.filter(e=>e.kind==='mandatory'&&String(e.accountId)===String(a.id)&&e.date.slice(0,7)===month).map(e=>e.amountCents));
      if(actual+assigned<cents(a.min_spend))events.push(make('fee:'+a.id+':'+month,d,'Комісія: '+(a.name||a.id),'fee',cents(a.min_spend_fee),{accountId:a.id,certainty:'conditional'}));
    }
  }
  // Категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit.
  const expenseCats=(data.categories||[]).filter(c=>c.active!==false&&c.type==='expense');
  const categories: {id:string;name:string;weight:number;limitAbsCents?:number}[]=expenseCats.map(c=>c.limit_abs!=null?{id:String(c.id),name:c.name||'',weight:0,limitAbsCents:Math.max(0,cents(c.limit_abs))}:{id:String(c.id),name:c.name||'',weight:Math.max(0,cents(c.budget_limit??c.limit))/100}).sort((a,b)=>cmp(a.id,b.id));
  if(new Set(categories.map(c=>c.id)).size!==categories.length)throw new RangeError('Duplicate category id');
  // Черга сум у гривнях: sort_order (null в кінці), при рівності id.
  const absOrder=expenseCats.filter(c=>c.limit_abs!=null).map(c=>({id:String(c.id),order:c.sort_order==null?null:Number(c.sort_order)})).sort((a,b)=>a.order===b.order?cmp(a.id,b.id):a.order==null?1:b.order==null?-1:a.order-b.order).map(o=>categories.findIndex(c=>c.id===o.id));
  if(!absOrder.length&&!categories.some(c=>c.weight>0))categories.splice(0,categories.length,{id:'unallocated',name:'Не розподілено',weight:1});
  const allocate=(total: number,weights: number[])=>{if(!total)return weights.map(()=>0);const den=weights.reduce((s,v)=>s+BigInt(v),0n);const rows=weights.map((w,i)=>({i,value:Number(BigInt(total)*BigInt(w)/den),rest:BigInt(total)*BigInt(w)%den}));let left=total-sum(rows.map(r=>r.value));rows.sort((a,b)=>a.rest===b.rest?a.i-b.i:a.rest>b.rest?-1:1);for(let i=0;i<left;i++)rows[i].value++;rows.sort((a,b)=>a.i-b.i);return rows.map(r=>r.value);};
  // Суми в гривнях по черзі min(ліміт, що лишилось), залишок за вагами; ваг немає: «Не розподілено». caps: ліміти поточного періоду.
  const split=(total: number,caps?: number[])=>{if(!absOrder.length)return {rows:categories,totals:allocate(total,categories.map(c=>cents(c.weight)))};
    const totals=categories.map(()=>0),weights=categories.map(c=>c.limitAbsCents!=null?0:cents(c.weight));let left=total;
    for(const i of absOrder){const n=Math.min(caps?caps[i]:categories[i].limitAbsCents??0,left);totals[i]=n;left-=n;}
    if(weights.some(w=>w>0)){allocate(left,weights).forEach((n,i)=>totals[i]+=n);return {rows:categories,totals};}
    return left>0?{rows:[...categories,{id:'unallocated',name:'Не розподілено',weight:1}],totals:[...totals,left]}:{rows:categories,totals};
  };
  const distribution=(target: number,start: string,end: string,available: number,caps?: number[])=>{const count=distance(start,end),{rows,totals}=split(count>0?target:0,caps),remaining=totals.slice(),schedule=[];let balance=available;
    for(let i=0;i<count;i++){const spendCents=Math.floor(target/count)+(i<target%count?1:0),amounts=i===count-1?remaining.slice():allocate(spendCents,remaining);amounts.forEach((n,j)=>remaining[j]-=n);balance=safe(balance-spendCents);schedule.push({date:plus(start,i),spendCents,remainingCents:balance,byCategory:rows.map((c,j)=>({id:c.id,name:c.name,amountCents:amounts[j]}))});}
    return {categories:rows.map((c,i)=>({...c,totalCents:totals[i]})),schedule};
  };
  const between=(start: string,end: string)=>events.filter(e=>e.date>=start&&e.date<end&&e.kind!=='variable');
  const mandatory=(start: string,end: string)=>sum(between(start,end).filter(e=>e.kind==='mandatory'||e.kind==='fee').map(e=>e.amountCents));
  // До наступної виплати: власні кошти мінус обовʼязкові й комісії [asof; виплата); борг карток гаситься з виплати.
  const untilPayout=nextDate?(()=>{const days=distance(asof,nextDate),value=safe(positiveOwnCents-mandatory(asof,nextDate));return {end:nextDate,days,cents:value,dailyCents:value>0&&days>0?Math.floor(value/days):0};})():null;
  let nextPlan: Record<string,any>|null=null,currentPeriod: Record<string,any>|null=null;
  const periods: Record<string,any>[]=[];
  if(hasPlan){const next=payoutAt(nextDate),after=payoutAt(followingDate),mandatoryCents=mandatory(nextDate,followingDate),baseAvailableCents=safe(positiveOwnCents+next.amountCents-mandatoryCents-creditDebtCents),targetCents=Math.max(1500000,baseAvailableCents);
    nextPlan={start:nextDate,end:followingDate,days:distance(nextDate,followingDate),nextPayout:next,followingPayout:after,positiveOwnCents,debtCents:creditDebtCents,mandatoryCents,otherIncomeCents:sum(between(nextDate,followingDate).filter(e=>e.kind==='income').map(e=>e.amountCents)),eligibleMandatoryCents:sum(between(nextDate,followingDate).filter(e=>e.kind==='mandatory'&&e.creditEligible).map(e=>e.amountCents)),baseAvailableCents,targetCents,gapCents:Math.max(0,targetCents-baseAvailableCents),averageDailyCents:targetCents/distance(nextDate,followingDate),...distribution(targetCents,nextDate,followingDate,baseAvailableCents)};
    // Поточний період: каса мінус обовʼязкові до виплати; борг карток резервується один раз у nextPlan.
    // Темп щоденних витрат від завтра до дня перед виплатою: більше з 15 000 ₴ на весь період [start; виплата) і untilPayout на дні, що лишились.
    // Сума в гривнях на прогноз від завтра: ліміт мінус факт змінних витрат категорії з початку періоду, не нижче 0.
    const start=payoutDates.filter(d=>d<=asof).pop()||asof,actualVariableCents=sum(txs.filter(t=>t.type==='expense'&&t.fixed_id==null&&t.credit_id==null&&txDate(t)>=start).map(t=>cents(t.amount))),mandatoryCentsNow=mandatory(asof,nextDate),available=safe(cashCents-mandatoryCentsNow),periodDays=distance(start,nextDate),leftDays=Math.max(0,distance(plus(asof,1),nextDate)),floorLeft=periodDays>0?Math.floor(1500000*leftDays/periodDays):0,freeLeft=Math.max(0,untilPayout?untilPayout.cents:0),remaining=leftDays>0?Math.max(floorLeft,freeLeft):0,target=actualVariableCents+remaining,caps=categories.map(c=>c.limitAbsCents==null?0:Math.max(0,c.limitAbsCents-sum(txs.filter(t=>t.type==='expense'&&t.fixed_id==null&&t.credit_id==null&&txDate(t)>=start&&t.category_id!=null&&String(t.category_id)===c.id).map(t=>cents(t.amount))))),dist=distribution(remaining,plus(asof,1),nextDate,available,caps);
    currentPeriod={start,end:nextDate,actualVariableCents,targetCents:target,remainingTargetCents:remaining,periodDays,leftDays,dailyCents:leftDays>0?remaining/leftDays:0,futureSchedule:dist.schedule};
    periods.push({start,end:nextDate,basis:'current',openingCashCents:cashCents,payoutCents:0,mandatoryCents:mandatoryCentsNow,debtReserveCents:0,availableCents:available,targetCents:target,gapCents:Math.max(0,remaining-available),...dist});
    // Обчислення періодів послідовне: знак залишку зберігається.
    const futureDates=payoutDates.filter(d=>d>asof);
    for(let i=0;i<futureDates.length-1&&futureDates[i]<=through;i++){
      const start=futureDates[i],end=futureDates[i+1],opening=safe(cashCents+sum(events.filter(e=>e.date>=asof&&e.date<start).map(e=>e.cashDeltaCents))-sum(periods.flatMap(p=>p.schedule).filter(d=>d.date<start).map(d=>d.spendCents))),entries=between(start,end),payoutCents=sum(entries.filter(e=>e.kind==='payout').map(e=>e.amountCents)),mandatoryCents=mandatory(start,end),scheduledRepay=sum(entries.filter(e=>e.kind==='repay').map(e=>e.amountCents)),outstandingDebt=safe(creditDebtCents+sum(events.filter(e=>e.date<start).map(e=>e.debtDeltaCents))),newRepay=sum(entries.filter(e=>e.kind==='repay'&&e.id.startsWith('scenario-repay:')&&events.some(v=>v.funding==='credit'&&v.date>=start&&v.date<end&&e.id==='scenario-repay:'+v.occurrenceId+':'+String(v.accountId))).map(e=>e.amountCents)),debtReserveCents=outstandingDebt+newRepay,availableCents=safe(opening+sum(entries.map(e=>e.cashDeltaCents))+scheduledRepay-debtReserveCents),targetCents=i===0?nextPlan.targetCents:Math.max(1500000,availableCents);
      periods.push({start,end,basis:i===0?'headline':'projected',openingCashCents:opening,payoutCents,mandatoryCents,debtReserveCents,availableCents,targetCents,gapCents:Math.max(0,targetCents-availableCents),...distribution(targetCents,start,end,availableCents)});
    }
  }
  if(scenario){const base=nextPlan?.baseAvailableCents??0;const gain=nextPlan?sum(events.filter(e=>e.funding==='credit'&&e.date>=nextPlan.start&&e.date<nextPlan.end).map(e=>e.amountCents))-sum(scenario.repayments.filter(e=>e.date>=nextPlan.start&&e.date<nextPlan.end).map(e=>e.amountCents)):0;scenario.cashPlanCents=safe(base+gain);scenario.gapCents=Math.max(0,(nextPlan?.targetCents??1500000)-scenario.cashPlanCents);}
  for(const p of periods)for(const d of p.schedule)for(const c of d.byCategory)if(c.amountCents>0)events.push(make('variable:'+d.date+':'+c.id,d.date,c.name,'variable',c.amountCents,{categoryId:c.id}));
  const visible=events.filter(e=>e.date>=asof&&e.date<=through).sort(compareEvents);
  let cash=cashCents,debt=creditDebtCents;const days=[];
  for(let d=asof;d<=through;d=plus(d,1)){const opening=cash,today=visible.filter(e=>e.date===d),byCategory=[];let minimum=cash,variable=0;
    for(const e of today){cash=safe(cash+e.cashDeltaCents);debt=safe(debt+e.debtDeltaCents);e.cashAfterCents=cash;e.debtAfterCents=debt;minimum=Math.min(minimum,cash);if(e.kind==='variable'){variable+=e.amountCents;byCategory.push({id:e.categoryId,name:e.name,amountCents:e.amountCents});}}
    days.push({date:d,openingCashCents:opening,closingCashCents:cash,debtCents:debt,netCents:cash-debt,variableCents:variable,byCategory,minCashCents:minimum,shortfallCents:Math.max(0,-minimum),eventIds:today.map(e=>e.id)});
  }
  return {snapshot,nextPlan,reason:nextPlan?null:'no_next_payout',currentPeriod,untilPayout,periods,events:visible,days,scenario,minSpend};
}

// Бюджет розпочатого періоду, обмежений готівкою (DESIGN.md, п. 5):
// min(плановий, max(0, cashNow) + витрачено). Змінює сторінку «Бюджет», а не «Вільно до виплати».
export const capBudget = (plan: number, cashNow: number, spent: number): number =>
  Math.min(plan, Math.max(0, cashNow) + spent);

// Операції без рахунку (DESIGN.md, п. 9): дохід плюс, витрата мінус; повертає знакову поправку до власних.
// Операції Monobank не рахуємо (баланс з API уже їх містить). since (мс): лише створені строго після цієї мітки
// (мінімальний balance_updated_at ручних рахунків), щоб не віднімати старі.
export function unassignedAdj(txs: AccTx[], since?: number): number {
  let s = 0;
  for (const t of txs || []) {
    if (t.account_id != null || t.source === 'mono') continue;
    if (since != null && !(Date.parse(t.created_at) > since)) continue;
    s += t.type === 'income' ? num(t.amount) : -num(t.amount);
  }
  return round2(s);
}

// Дата операції: поле date, без нього перші 10 знаків created_at (як tx_day у budget_pool.py)
const txDay = (t: AccTx) => String(t.date || t.created_at || '').slice(0, 10);

// Мінімальні витрати за місяць (DESIGN.md, п. 11): для активних рахунків з min_spend > 0 сума витрат
// (type = 'expense' строго) з цим account_id і датою в календарному місяці today. left = max(0, min − spent);
// metOn: дата операції, на якій накопичена сума (порядок date, created_at, amount) досягла порогу.
export function minSpendStatus(accounts: Account[], txs: AccTx[], today: string): MinSpendRow[] {
  const month = today.slice(0, 7);
  const out: MinSpendRow[] = [];
  for (const a of accounts || []) {
    const mn = num(a.min_spend);
    if (a.active === false || mn <= 0 || a.id == null) continue;
    const list = (txs || []).filter((t) => t.account_id != null && Number(t.account_id) === Number(a.id) &&
      t.type === 'expense' && txDay(t).slice(0, 7) === month);
    const cmp = (u: string, v: string) => (u < v ? -1 : u > v ? 1 : 0); // порівняння за кодами, як у Python
    list.sort((x, y) => cmp(txDay(x), txDay(y)) || cmp(String(x.created_at || ''), String(y.created_at || '')) ||
      num(x.amount) - num(y.amount));
    let cum = 0; let met: string | undefined;
    for (const t of list) {
      cum += num(t.amount);
      if (met == null && cum >= mn - 1e-9) met = txDay(t);
    }
    const row: MinSpendRow = { accountId: Number(a.id), month, spent: round2(cum), min: mn, fee: num(a.min_spend_fee), left: round2(Math.max(0, mn - cum)) };
    if (met) row.metOn = met;
    out.push(row);
  }
  return out;
}

// Найближче 1-ше число строго після today: дата списання комісії за недосягнутий поріг поточного місяця
export function minSpendFeeDate(today: string): string {
  const t = parse(today);
  return iso(mk(t.getUTCFullYear(), t.getUTCMonth() + 2, 1));
}

// Сума комісій у вікні [start; end): подія 1-го числа наступного місяця, лише поки поріг не досягнуто
export function minSpendFee(rows: MinSpendRow[], today: string, start: string, end: string): number {
  const d = minSpendFeeDate(today);
  if (!(start <= d && d < end)) return 0;
  return round2((rows || []).filter((r) => r.left > 0 && r.fee > 0).reduce((s, r) => s + r.fee, 0));
}

// Робочі дні Пн-Пт у місяці (y, m) з d1 по d2 включно
function wd(y: number, m: number, d1: number, d2: number): number {
  let n = 0;
  for (let d = d1; d <= d2; d++) {
    const w = mk(y, m, d).getUTCDay();
    if (w !== 0 && w !== 6) n++;
  }
  return n;
}

// День виплати: субота переноситься на пʼятницю, неділя на понеділок
function adj(y: number, m: number, d: number): Date {
  const w = mk(y, m, d).getUTCDay();
  return mk(y, m, w === 6 ? d - 1 : w === 0 ? d + 1 : d);
}

// Виплати місяця: аванс за 1..split поточного, зарплата за split+1..кінець попереднього
function monthPayouts(cfg: SalaryCfg, y: number, m: number): Payout[] {
  const rate = num(cfg.rate), split = Number(cfg.split_day);
  const [py, pm] = m > 1 ? [y, m - 1] : [y - 1, 12];
  const last = lastDay(y, m), plast = lastDay(py, pm);
  return [
    { date: iso(adj(y, m, Number(cfg.advance_day))), kind: 'advance', amount: rate > 0 ? round2(rate / wd(y, m, 1, last) * wd(y, m, 1, split)) : num(cfg.advance_amount) },
    { date: iso(adj(y, m, Number(cfg.salary_day))), kind: 'salary', amount: rate > 0 ? round2(rate / wd(py, pm, 1, plast) * wd(py, pm, split + 1, plast)) : num(cfg.salary_amount) },
  ];
}

// Виплати за months місяців, починаючи з місяця дати from (зсув shift місяців)
function payouts(cfg: SalaryCfg, from: string, shift: number, months: number): Payout[] {
  const f = parse(from);
  const out: Payout[] = [];
  for (let i = 0; i < months; i++) {
    const k = f.getUTCFullYear() * 12 + f.getUTCMonth() + shift + i;
    out.push(...monthPayouts(cfg, Math.floor(k / 12), (k % 12) + 1));
  }
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

// Остання виплата не пізніше today (як pbOpen у застосунку)
export function lastPayout(cfg: SalaryCfg, today: string): Payout {
  const l = payouts(cfg, today, -2, 3).filter((p) => p.date <= today);
  return l[l.length - 1];
}

// п. 13: оплачені постійні платежі. Операція type = 'expense' з fixed_id і датою (без неї перші 10 знаків created_at)
// у місяці M закриває платіж місяця M (і раніше дати платежу). Ключі `${fixed_id}|YYYY-MM` для Snapshot.paid,
// для щотижневих ще `${fixed_id}|W<понеділок тижня операції>` (тиждень пн-нд).
export function fixedPaid(txs: AccTx[]): string[] {
  const out = new Set<string>();
  for (const t of txs || []) {
    if (t.fixed_id == null || t.type !== 'expense') continue;
    const d = String(t.date || t.created_at || '').slice(0, 10);
    out.add(String(t.fixed_id) + '|' + d.slice(0, 7));
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) out.add(String(t.fixed_id) + '|W' + addDays(d, 1 - isoWeekday(d)));
  }
  return [...out].sort();
}

// Місяці [y, m] (m: 1..12) від місяця start до місяця end включно
function monthsSpan(start: string, end: string): [number, number][] {
  const s = parse(start), e = parse(end);
  const out: [number, number][] = [];
  for (let k = s.getUTCFullYear() * 12 + s.getUTCMonth(); k <= e.getUTCFullYear() * 12 + e.getUTCMonth(); k++) {
    out.push([Math.floor(k / 12), (k % 12) + 1]);
  }
  return out;
}

const byDate = (a: { date: string; name: string }, b: { date: string; name: string }) =>
  a.date < b.date ? -1 : a.date > b.date ? 1 : a.name < b.name ? -1 : a.name > b.name ? 1 : 0;

// Обовʼязкові у вікні [start; end): постійні (дохід зі знаком мінус) і активні розстрочки, помісячно (п. 12, як period_obl)
function obligations(snap: Snapshot, start: string, end: string): Obligation[] {
  const out: Obligation[] = [];
  const paid = new Set(snap.paid || []);
  for (const [y, m] of monthsSpan(start, end)) {
    const ld = lastDay(y, m);
    const ym = `${y}-${String(m).padStart(2, '0')}`;
    for (const f of snap.fixed || []) {
      if (f.active === false || f.period === 'week') continue;
      if (f.id != null && paid.has(String(f.id) + '|' + ym)) continue; // п. 13: оплачено в цьому місяці
      const d = iso(mk(y, m, Math.min(Number(f.day_of_month), ld)));
      if (!(start <= d && d < end)) continue;
      const a = num(f.amount);
      out.push({ date: d, name: f.name, amount: f.type !== 'income' ? a : -a, credit_ok: f.credit_ok === true });
    }
    for (const c of snap.credits || []) {
      const d = iso(mk(y, m, Math.min(Number(c.payment_day), ld)));
      if (!(start <= d && d < end)) continue;
      // Та сама арифметика місяців, що в budget_pool.py і застосунку
      const first = Number(c.start_year) * 12 + Number(c.start_month);
      const cur = y * 12 + (m - 1);
      if (first <= cur && cur <= first + Number(c.total_payments) - 1) {
        // credit_ok не заданий: кредитна, якщо розстрочка ПриватБанку (як у budget_pool.py)
        const ok = c.credit_ok ?? String(c.source || '').toLowerCase().includes('privat');
        out.push({ date: d, name: c.name + ' (розстрочка)', amount: num(c.monthly_amount), credit_ok: ok === true });
      }
    }
  }
  // Щотижневі постійні: кожна дата з ISO-днем weekday у [start; end); оплачений тиждень (ключ W<понеділок>) пропускаємо
  for (const f of snap.fixed || []) {
    const w = Number(f.weekday);
    if (f.active === false || f.period !== 'week' || !Number.isInteger(w) || w < 1 || w > 7) continue;
    for (let d = addDays(start, (w - isoWeekday(start) + 7) % 7); d < end; d = addDays(d, 7)) {
      if (f.id != null && paid.has(String(f.id) + '|W' + addDays(d, 1 - isoWeekday(d)))) continue;
      const a = num(f.amount);
      out.push({ date: d, name: f.name, amount: f.type !== 'income' ? a : -a, credit_ok: f.credit_ok === true });
    }
  }
  return out.sort(byDate);
}

// Каса по датах (DESIGN.md, п. 12). Подія: kind payout | income | white | fee | repay, amount зі знаком, balance після
export type CashEvent = { date: string; amount: number; name: string; kind: string; payout?: 'advance' | 'salary'; balance?: number };
const KIND_ORDER: Record<string, number> = { payout: 0, income: 1, white: 2, fee: 3, repay: 4 };

// Погашення боргу за місяць M (YYYY-MM): 24-те M+1, вихідні не зсуваються; прострочене гаситься «зараз»
export function repayDate(month: string, now: string): string {
  const y = Number(month.slice(0, 4)), m = Number(month.slice(5, 7));
  const d = iso(mk(m < 12 ? y : y + 1, m < 12 ? m + 1 : 1, 24));
  return d >= now ? d : now;
}

// Кошики боргу кредитного рахунку [[YYYY-MM, сума]]: з deriveAccounts або весь борг у місяці debt_month
// (без нього місяць мітки balance_updated_at, без неї місяць «зараз»)
export function debtBuckets(a: Account, now: string): [string, number][] {
  const b = a.debt_months ?? [[String(a.debt_month || '').slice(0, 7) || String(a.balance_updated_at || '').slice(0, 7) || now.slice(0, 7), num(a.debt)]];
  return b.filter((x) => num(x[1]) > 0).map((x) => [x[0], num(x[1])]);
}

// Виплати з датою в [lo; hi] і строго після now
function payoutsIn(cfg: SalaryCfg, lo: string, hi: string, now: string): Payout[] {
  const l = parse(lo);
  const from = iso(mk(l.getUTCFullYear(), l.getUTCMonth(), 1)); // місяць перед lo
  const out: Payout[] = [];
  for (const [y, m] of monthsSpan(from, addDays(hi, 31))) out.push(...monthPayouts(cfg, y, m));
  return out.filter((p) => lo <= p.date && p.date <= hi && p.date > now)
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

// Події каси з датою в [lo; hi] (як cash_events у budget_pool.py). Рахунки в snap мають бути вже ефективні (deriveAccounts).
export function cashEvents(snap: Snapshot, now: string, lo: string, hi: string, minSpend: MinSpendRow[] = []): CashEvent[] {
  const ev: CashEvent[] = [];
  for (const p of payoutsIn(snap.salary, lo, hi, now)) {
    ev.push({ date: p.date, amount: p.amount, name: p.kind === 'advance' ? 'аванс' : 'зарплата', kind: 'payout', payout: p.kind });
  }
  const hiX = addDays(hi, 1);
  for (const o of obligations(snap, lo, hiX)) {
    if (o.amount < 0) ev.push({ date: o.date, amount: -o.amount, name: o.name, kind: 'income' });
    else if (!o.credit_ok) ev.push({ date: o.date, amount: -o.amount, name: o.name, kind: 'white' });
  }
  const rep: Record<string, number> = {};
  if (hi >= now) {
    for (const o of obligations(snap, now, hiX)) {
      if (!o.credit_ok || !(o.amount > 0)) continue;
      const r = repayDate(o.date.slice(0, 7), now);
      if (lo <= r && r <= hi) rep[r] = (rep[r] || 0) + o.amount;
    }
    for (const a of snap.accounts || []) {
      if (a.active === false || a.kind !== 'credit') continue;
      for (const [m, v] of debtBuckets(a, now)) {
        const r = repayDate(m, now);
        if (lo <= r && r <= hi) rep[r] = (rep[r] || 0) + v;
      }
    }
  }
  for (const r of Object.keys(rep)) {
    const v = round2(rep[r]);
    if (v > 0) ev.push({ date: r, amount: -v, name: 'Погашення кредитки', kind: 'repay' });
  }
  const fee = round2((minSpend || []).filter((r) => r.left > 0 && r.fee > 0).reduce((s, r) => s + r.fee, 0));
  const fd = minSpendFeeDate(now);
  if (fee > 0 && lo <= fd && fd <= hi) ev.push({ date: fd, amount: -fee, name: 'Комісія за мінімальні витрати', kind: 'fee' });
  return ev.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0) || KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
    (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
}

// Чисті відтоки каси (без виплат) у [a; b)
function netOut(snap: Snapshot, now: string, a: string, b: string, minSpend: MinSpendRow[]): number {
  return round2(-cashEvents(snap, now, a, addDays(b, -1), minSpend).filter((e) => e.kind !== 'payout').reduce((s, e) => s + e.amount, 0));
}

// План періоду [a; b): виплата − відтоки каси − накопичення (п. 12)
function planOf(snap: Snapshot, now: string, payout: number, a: string, b: string, minSpend: MinSpendRow[]) {
  const pool0 = round2(payout - netOut(snap, now, a, b, minSpend));
  const pct = num(snap.savings_pct ?? snap.salary.savings_pct ?? 0);
  const savings = round2(Math.max(0, pool0) * pct / 100);
  return { pool0, savings, plan: Math.max(0, pool0 - savings) };
}

// Погашення кредитки у вікні [start; end) за правилом п. 12 (сума подій repay)
export function cardRepay(snap: Snapshot, today: string, start: string, end: string, minSpend: MinSpendRow[] = []): number {
  return round2(-cashEvents(snap, today, start, addDays(end, -1), minSpend).filter((e) => e.kind === 'repay').reduce((s, e) => s + e.amount, 0));
}

// Каса по датах від today до горизонту: max(3-тя виплата, найпізніше погашення в межах 60 днів), включно
export function cashTimeline(snap: Snapshot, today: string, startCash: number, minSpend: MinSpendRow[] = []) {
  const fut = payoutsIn(snap.salary, today, addDays(today, 120), today);
  const p3 = fut[2].date, lim = addDays(today, 60);
  const all = cashEvents(snap, today, today, p3 > lim ? p3 : lim, minSpend);
  let horizon = p3;
  for (const e of all) if (e.kind === 'repay' && e.date <= lim && e.date > horizon) horizon = e.date;
  const events: CashEvent[] = [];
  let bal = round2(startCash);
  for (const e of all) {
    if (e.date > horizon) break;
    bal = round2(bal + e.amount);
    events.push({ ...e, balance: bal });
  }
  let minCash = round2(startCash), minCashDate = today;
  for (const e of events) if ((e.balance as number) < minCash - 1e-9) { minCash = e.balance as number; minCashDate = e.date; }
  const before = (d: string) => { let b = round2(startCash); for (const e of events) if (e.date < d) b = e.balance as number; return b; };
  const minFrom = (d: string) => { const v = events.filter((e) => e.date >= d).map((e) => e.balance as number); return v.length ? Math.min(...v) : before(d); };
  return { startCash: round2(startCash), horizon, events, minCash, minCashDate, before, minFrom, payouts: fut };
}

// Бюджет періоду, що починається з першої виплати після today: старі поля для сумісності (план за п. 12 рахує freeToPayout)
export function periodBudget(snap: Snapshot, today: string) {
  const cfg = snap.salary;
  const future = payouts(cfg, today, 0, 3).filter((p) => p.date > today);
  const pn = future[0], pa = future[1];
  const accs = (snap.accounts || []).filter((a) => a.active !== false);
  const own = accs.reduce((s, a) => s + num(a.balance), 0);
  const debt = accs.reduce((s, a) => s + num(a.debt), 0);
  const deficit = Math.max(0, debt - own);
  const obl = obligations(snap, pn.date, pa.date);
  const oblSum = obl.reduce((s, o) => s + o.amount, 0);
  return { payout: pn, end: pa.date, obligations: obl, oblSum, own, debt, deficit };
}

// «Вільно до виплати» на today (п. 12): поточний період [остання виплата d0; d1), spent: витрати з d0.
// unassigned: знакова поправка від unassignedAdj (операції без рахунку), додається до власних (п. 9).
// minSpend: рядки minSpendStatus (п. 11); комісія 1-го числа: подія каси.
// Рахунки в snap мають бути вже ефективні (deriveAccounts).
export function freeToPayout(snap: Snapshot, today: string, spent: number, unassigned = 0, minSpend: MinSpendRow[] = []) {
  const last = lastPayout(snap.salary, today);
  const fut = payouts(snap.salary, today, 0, 3).filter((p) => p.date > today);
  const next = fut[0], after = fut[1];
  // Власні кошти дебетових і готівкових рахунків (кредитна картка не дає плюсових грошей)
  const ownDebit = (snap.accounts || [])
    .filter((a) => a.active !== false && a.kind !== 'credit')
    .reduce((s, a) => s + num(a.balance), 0);
  const tl = cashTimeline(snap, today, ownDebit + unassigned, minSpend);
  const cur = planOf(snap, today, last.amount, last.date, next.date, minSpend);
  const planCur = cur.plan;
  const cashNow = tl.before(next.date); // каса напередодні d1
  const whiteSum = round2(tl.startCash - cashNow);
  const white = tl.events.filter((e) => e.date < next.date && e.kind === 'white').map((e) => ({ date: e.date, name: e.name, amount: -e.amount }));
  const cardRepayNow = round2(-tl.events.filter((e) => e.date < next.date && e.kind === 'repay').reduce((s, e) => s + e.amount, 0));
  const feeNow = minSpendFee(minSpend, today, today, next.date);
  const freeRaw = Math.min(planCur - spent, tl.minCash);
  const freeNow = Math.max(0, freeRaw);
  const varPoolCur = spent + freeNow;
  const shortage = Math.max(0, -tl.minCash);
  const daysLeft = Math.max(0, diffDays(today, next.date));
  const perDay = daysLeft > 0 ? freeNow / daysLeft : 0;
  // Наступний період [d1; d2)
  const nx = planOf(snap, today, next.amount, next.date, after.date, minSpend);
  const feeNext = minSpendFee(minSpend, today, next.date, after.date);
  const whiteNext = round2(obligations(snap, next.date, after.date).filter((o) => !o.credit_ok && o.amount > 0)
    .reduce((s, o) => s + o.amount, 0) + feeNext);
  const cardRepayNext = cardRepay(snap, today, next.date, after.date, minSpend);
  const cashAtPayout = Math.max(0, cashNow - freeNow);
  const varPoolNext = Math.max(0, Math.min(nx.plan, tl.minFrom(next.date) - freeNow));
  // Найближча зарплата: каса напередодні
  const sal = tl.payouts.find((p) => p.kind === 'salary');
  const cashBeforeSalary = sal ? tl.before(sal.date) : null;
  const daysToSalary = sal ? diffDays(today, sal.date) : null;
  return {
    lastPayout: last, nextPayout: next, periodStart: last.date, varPool: planCur, pool0: cur.pool0,
    spent, ownDebit, unassigned, white, whiteSum, cardRepayNow, cashNow, freeRaw, freeNow, daysLeft, perDay,
    planCur, varPoolCur, shortage,
    planNext: nx.plan, whiteNext, cardRepayNext, varPoolNext, cashAtPayout,
    minSpend, feeNow, feeNext,
    cashBeforePayout: cashNow, daysToPayout: daysLeft, cashBeforeSalary, daysToSalary, salaryDate: sal ? sal.date : null,
    minCash: tl.minCash, minCashDate: tl.minCashDate, horizon: tl.horizon, startCash: tl.startCash, timeline: tl.events,
  };
}


export type NextPeriodInput = {
  accounts: Account[]; fixed: Fixed[]; credits: Credit[]; salary?: SalaryCfg | null;
  transactions?: AccTx[]; account_tx?: AccTx[]; profiles?: unknown[];
  categories: { id: string | number; name?: string; type?: string; active?: boolean; budget_limit?: number | string | null; limit?: number | string | null; limit_abs?: number | string | null; sort_order?: number | null }[];
};

// Новий план [найближча виплата строго після asof; наступна виплата).
// Вхідні суми: гривні; вихідні *Cents: цілі безпечні копійки (averageDailyCents: середнє).
// salary: запис salary_config; profiles не визначає графік виплат. Невідомий графік: plan:null.
// remainingCents: залишок денного бюджету ПІСЛЯ резервування, не банківська каса по датах.
// credit_ok лише позначає придатність: усі зобовʼязання резервуються, автоматичного переносу немає.
export function nextPeriodPlan(data: NextPeriodInput, asof: string) {
  const safe = (v: bigint): number => {
    if (v > BigInt(Number.MAX_SAFE_INTEGER) || v < -BigInt(Number.MAX_SAFE_INTEGER)) throw new RangeError('Unsafe cents');
    return Number(v);
  };
  // Десяткове округлення половини від нуля; однаково для рядків БД і чисел.
  const cents = (value: unknown): number => {
    const n = Number(value ?? 0);
    if (!Number.isFinite(n)) throw new RangeError('Invalid money');
    const [coefficient, exponent = '0'] = String(n).toLowerCase().split('e');
    const negative = coefficient.startsWith('-');
    const [whole, fraction = ''] = coefficient.replace('-', '').split('.');
    let digits = BigInt(whole + fraction);
    const shift = 2 + Number(exponent) - fraction.length;
    if (shift >= 0) digits *= 10n ** BigInt(shift);
    else { const divisor = 10n ** BigInt(-shift); digits = (digits + divisor / 2n) / divisor; }
    return safe(negative ? -digits : digits);
  };
  const sum = (values: number[]) => safe(values.reduce((a, b) => a + BigInt(b), 0n));
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asof) || !Number.isFinite(parse(asof).getTime()) || iso(parse(asof)) !== asof) throw new RangeError('Invalid asof');
  const cfg = data.salary;
  if (!cfg || ![cfg.advance_day, cfg.salary_day, cfg.split_day].every(d => Number.isInteger(Number(d)) && Number(d) >= 1 && Number(d) <= 31)) return { plan: null, reason: 'no_next_payout' as const };
  const future = payouts(cfg, asof, -1, 4).filter(p => p.date > asof && p.amount > 0);
  const next = future[0], after = future.find(p => next && p.date > next.date);
  if (!next || !after) return { plan: null, reason: 'no_next_payout' as const };
  const transactions = data.transactions ?? data.account_tx ?? [];
  const accounts = deriveAccounts(data.accounts, transactions).filter(a => a.active !== false);
  const stamps = accounts.filter(a => !a.mono_account_id && a.balance_updated_at).map(a => Date.parse(a.balance_updated_at!)).filter(Number.isFinite);
  const adjustment = stamps.length ? cents(unassignedAdj(transactions, Math.min(...stamps))) : 0;
  const positiveOwnCents = Math.max(0, sum([...accounts.map(a => Math.max(0, cents(a.balance))), adjustment]));
  const debtCents = sum(accounts.filter(a => a.kind === 'credit').map(a => Math.max(0, cents(a.debt))));
  const entries = obligations({ accounts, fixed: data.fixed, credits: (data.credits || []).map(c => ({ ...c, credit_ok: c.credit_ok === true })), salary: cfg, paid: fixedPaid(transactions) }, next.date, after.date);
  const mandatoryCents = sum(entries.filter(e => e.amount > 0).map(e => cents(e.amount)));
  const otherIncomeCents = sum(entries.filter(e => e.amount < 0).map(e => cents(-e.amount)));
  const eligibleMandatoryCents = sum(entries.filter(e => e.amount > 0 && e.credit_ok).map(e => cents(e.amount)));
  const incoming = sum([positiveOwnCents, cents(next.amount)]), reserved = sum([mandatoryCents, debtCents]);
  const baseAvailableCents = sum([incoming, -reserved]);
  const targetCents = Math.max(1500000, baseAvailableCents), gapCents = sum([targetCents, -baseAvailableCents]);
  // Категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit.
  const expenseCats = (data.categories || []).filter(c => c.active !== false && c.type === 'expense');
  const byId = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
  const categories: { id: string; name: string; weight: number; limitAbsCents?: number }[] = expenseCats.map(c => c.limit_abs != null ? { id: String(c.id), name: c.name ?? '', weight: 0, limitAbsCents: Math.max(0, cents(c.limit_abs)) } : { id: String(c.id), name: c.name ?? '', weight: Math.max(0, cents(c.budget_limit ?? c.limit)) / 100 }).sort((a,b) => byId(a.id, b.id));
  if (new Set(categories.map(c => c.id)).size !== categories.length) throw new RangeError('Duplicate category id');
  // Черга сум у гривнях: sort_order (null в кінці), при рівності id.
  const absOrder = expenseCats.filter(c => c.limit_abs != null).map(c => ({ id: String(c.id), order: c.sort_order == null ? null : Number(c.sort_order) })).sort((a,b) => a.order === b.order ? byId(a.id, b.id) : a.order == null ? 1 : b.order == null ? -1 : a.order - b.order).map(o => categories.findIndex(c => c.id === o.id));
  if (!absOrder.length && !categories.some(c => c.weight > 0)) categories.splice(0, categories.length, { id: 'unallocated', name: 'Не розподілено', weight: 1 });
  const allocate = (total: number, units: bigint[]) => {
    const denominator = units.reduce((a,b) => a+b, 0n);
    if (!total) return units.map(() => 0);
    const rows = units.map((u,i) => ({ i, value: Number(BigInt(total)*u/denominator), remainder: BigInt(total)*u%denominator }));
    const left = total - rows.reduce((a,r) => a+r.value,0);
    rows.sort((a,b) => a.remainder === b.remainder ? a.i-b.i : a.remainder > b.remainder ? -1 : 1);
    for (let i=0;i<left;i++) rows[i].value++;
    const result = units.map(() => 0); rows.forEach(r => result[r.i]=r.value); return result;
  };
  // Суми в гривнях по черзі min(ліміт, що лишилось), залишок за вагами; ваг немає: «Не розподілено».
  let totals: number[];
  if (!absOrder.length) totals = allocate(targetCents, categories.map(c => BigInt(cents(c.weight))));
  else {
    totals = categories.map(() => 0);
    const weights = categories.map(c => c.limitAbsCents != null ? 0n : BigInt(cents(c.weight)));
    let left = targetCents;
    for (const i of absOrder) { const n = Math.min(categories[i].limitAbsCents ?? 0, left); totals[i] = n; left -= n; }
    if (weights.some(w => w > 0n)) allocate(left, weights).forEach((n,i) => totals[i] += n);
    else if (left > 0) { categories.push({ id: 'unallocated', name: 'Не розподілено', weight: 1 }); totals.push(left); }
  }
  const remaining = totals.slice(), days = diffDays(next.date, after.date);
  let balance = baseAvailableCents;
  const schedule = Array.from({ length: days }, (_,day) => {
    const spendCents = Math.floor(targetCents/days) + (day < targetCents%days ? 1 : 0);
    const amounts = day === days-1 ? remaining.slice() : allocate(spendCents, remaining.map(BigInt));
    amounts.forEach((a,i) => remaining[i]-=a);
    balance = sum([balance,-spendCents]);
    return { date: addDays(next.date,day), spendCents, remainingCents: balance, byCategory: categories.map((c,i) => ({id:c.id,name:c.name,amountCents:amounts[i]})) };
  });
  return { start: next.date, end: after.date, days, nextPayout: {...next,amountCents:cents(next.amount)}, followingPayout: {...after,amountCents:cents(after.amount)}, positiveOwnCents, debtCents, mandatoryCents, otherIncomeCents, eligibleMandatoryCents, baseAvailableCents, targetCents, gapCents, averageDailyCents: targetCents/days, categories: categories.map((c,i) => ({...c,totalCents:totals[i]})), schedule };
}
