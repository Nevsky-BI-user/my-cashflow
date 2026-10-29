import { monthlyPeriodBudget } from './monthly-budget.ts';
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
  fixed_id?: number | string | null; credit_id?: number | string | null; payment_due_date?: string | null; transfer_id?: string | null;
};
// Поріг мінімальних витрат рахунку за календарний місяць (DESIGN.md, п. 11)
export type MinSpendRow = { accountId: number; month: string; spent: number; min: number; fee: number; left: number; metOn?: string };
// variable: сума змінна, amount = середня оцінка (п. 13; на розрахунок не впливає)
// period: 'month' (день day_of_month) або 'week' (ISO-день weekday 1=пн..7=нд; без коректного weekday подій немає); bank: лише підпис
// type: 'payment' (витрата) або 'income' (постійний дохід поза зарплатою й авансом); end_date: остання дата події включно, null безстроково (міграція 29)
export type Fixed = {
  id?: number | string; name: string; amount: number | string; day_of_month: number; type: string; active?: boolean;
  credit_ok?: boolean | null; variable?: boolean | null;
  month_of_year?: number | string | null; period?: string | null; weekday?: number | string | null; bank?: string | null; end_date?: string | null;
};
// Подія постійного платежу з датою d (YYYY-MM-DD) після його end_date не генерується; end_date включно
const fixedEnded = (f: Fixed, d: string): boolean => !!f.end_date && d > String(f.end_date).slice(0, 10);
export type Credit = {
  id?: number | string; name: string; monthly_amount: number | string; payment_day: number;
  start_year: number; start_month: number; total_payments: number; credit_ok?: boolean | null; source?: string | null;
};
export type SalaryCfg = { rate?: number | string | null; rate_schedule?: {effective_from: string; rate: number}[] | null; advance_amount?: number | string | null; salary_amount?: number | string | null; split_day: number; advance_day: number; salary_day: number; savings_pct?: number | null; budget_manual?: number | string | null };
// paid: ключі `${fixed_id}|YYYY-MM` і `${fixed_id}|W<понеділок YYYY-MM-DD>` оплачених постійних платежів (п. 13), будує fixedPaid з операцій
export type Snapshot = { accounts: Account[]; fixed: Fixed[]; credits: Credit[]; salary: SalaryCfg; savings_pct?: number | null; paid?: string[]; paid_credit?: string[] };

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
 return (accounts||[]).map(a=>{
  const out={...a};if(a.mono_account_id||a.id==null||!a.balance_updated_at)return out;
  const since=Date.parse(a.balance_updated_at);if(!Number.isFinite(since))return out;
  let balance=num(a.balance),debt=Math.max(0,num(a.debt));
  const bk:Record<string,number>={[String(a.debt_month||a.balance_updated_at).slice(0,7)]:debt};
  const rows=(txs||[]).filter(t=>t.account_id!=null&&String(t.account_id)===String(a.id)&&Date.parse(t.created_at)>since).slice().sort((x,y)=>Date.parse(x.created_at)-Date.parse(y.created_at)||String(x.id||'').localeCompare(String(y.id||'')));
  for(const t of rows){const amount=num(t.amount);
   if(a.kind!=='credit'){balance+=t.type==='income'?amount:-amount;continue;}
   if(t.type==='income'){let left=amount;for(const m of Object.keys(bk).sort()){const used=Math.min(left,bk[m]);bk[m]-=used;debt-=used;left-=used;}balance+=left;}
   else{const own=Math.min(Math.max(0,balance),amount),borrowed=amount-own;balance-=own;debt+=borrowed;const m=String(t.date||t.created_at).slice(0,7);bk[m]=(bk[m]||0)+borrowed;}
  }
  out.balance=round2(balance);
  if(a.kind==='credit'){out.debt=round2(debt);out.debt_months=Object.keys(bk).sort().filter(m=>round2(bk[m])>0).map(m=>[m,round2(bk[m])]);}
  return out;
 });
}

// Єдине правило погашення кредитки (v147, рішення власника 12.10.2026): борг місяця M гаситься з виплати 21-го числа в M+1.
// Самодостатня (лише Date.UTC), бо вбудовується в index.html разом із financeProjection; ним користуються рушій, каса, бот і чипи.
export function repayDate(month: string, now: string): string {
  // субота й неділя зсуваються, як сама виплата (21.11.2026 субота: 20.11); минула дата гаситься «зараз»; now '' дає дату без зсуву на «зараз»
  const d=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5,7)),21)),w=d.getUTCDay();
  d.setUTCDate(21+(w===6?-1:w===0?1:0));
  const s=d.toISOString().slice(0,10);
  return now&&s<now?now:s;
}

// v151: розподіл виплати за правилом власника; одна функція для рушія, плитки «Бюджет періоду», старту періоду і «За планом»
// (вбудовується в index.html разом із financeProjection). A = власні − резерв − погашення; бюджет min(20 000, A), якщо A > 15 000, інакше 15 000.
// v153 (власник: «як ти гасиш кредитку, якщо на це немає білих грошей?»): з виплати спершу резерв (обовʼязкові до наступної виплати) і бюджет
// періоду, погашення лише з того, що лишилось: min(борг, max(0, власні − резерв − бюджет)); належне має пріоритет усередині цієї суми
// (порядок кошиків у рушії), непокрите належне = dueShortCents (нестача, а не погашення з повітря).
// v153 (власник: «має бути можливість встановлювати суму, яка розподіляється»): manualCents (salary_config.budget_manual) замість авто:
// бюджет = рівно ця сума, погашення = min(борг, max(0, власні − резерв − ця сума)). null: авто (15 000 / до 20 000).
export function payoutBudget(ownCents: number, reserveCents: number, debtCents: number, dueCents: number, repayDay: boolean, manualCents?: number | null): {repayCents: number; dueShortCents: number; availableCents: number; targetCents: number} {
  const man=manualCents!=null&&manualCents>=0,base=man?manualCents as number:1500000,debt=Math.max(0,debtCents),free=ownCents-reserveCents,repayCents=repayDay?Math.min(debt,Math.max(0,free-base)):0,availableCents=free-repayCents;
  return {repayCents,dueShortCents:repayDay?Math.max(0,Math.min(Math.max(0,dueCents),debt)-repayCents):0,availableCents,targetCents:man?base:availableCents>1500000?Math.min(2000000,availableCents):1500000};
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
    // v145: кошики за FIFO. Погашення гасять найстаріші кошики, тож залишок боргу складають найновіші витрати рахунку:
    // борг, не більший за витрати поточного місяця, увесь у поточному місяці; частина понад відомі витрати лишається
    // в найстаршому збереженому кошику (debt_month), якщо він старший за найранішу витрату.
    if(a.kind==='credit'&&debt>0){const spent: Record<string,number>={};for(const t of txs)if(String(t.account_id)===String(a.id)&&t.type!=='income'){const m=txDate(t).slice(0,7);spent[m]=(spent[m]||0)+Math.max(0,cents(t.amount));}
      // v146: збережений debt_month задає найстарший місяць боргу: витрати раніших місяців уже погашені, борг на них не відкочується.
      const old=Object.keys(buckets).filter(m=>buckets[m]>0).sort()[0]||month,floor=a.debt_month?old:'';
      const ms=Object.keys(spent).filter(m=>spent[m]>0&&m>=floor).sort().reverse();
      if(ms.length){for(const m of Object.keys(buckets))delete buckets[m];let left=debt;
        for(const m of ms){if(left<=0)break;const n=Math.min(left,spent[m]);buckets[m]=n;left-=n;}
        if(left>0){const first=ms[ms.length-1],m=old<first?old:first;buckets[m]=(buckets[m]||0)+left;}}}
    return {...a,balance:balance/100,debt:debt/100,balanceCents:balance,debtCents:debt,debt_months:Object.keys(buckets).sort().filter(m=>buckets[m]>0).map(m=>[m,buckets[m]/100])};
  });
  const stamps=accounts.filter(a=>!a.mono_account_id).map(a=>Date.parse(a.balance_updated_at||'')).filter(Number.isFinite);
  const adjustment=stamps.length?sum(txs.filter(t=>t.account_id==null&&t.source!=='mono'&&Date.parse(t.created_at)>Math.min(...stamps)).map(t=>(t.type==='income'?1:-1)*cents(t.amount))):0;
  const positiveOwnCents=Math.max(0,sum([...accounts.map(a=>Math.max(0,a.balanceCents)),adjustment]));
  const cashCents=sum([...accounts.map(a=>a.balanceCents),adjustment]);
  // Борг усіх карток, і кредитних, і дебетових з боргом (як Mono з лімітом); кожен кошик має одну подію погашення.
  const creditDebtCents=sum(accounts.map(a=>a.debtCents));
  const snapshot={positiveOwnCents,cashCents,unassignedAdjustmentCents:adjustment,creditDebtCents,accounts,warnings:[] as Record<string,any>[]};
  const cfg: Record<string,any>|null|undefined=data.salary;
  // v153: ручний бюджет періоду (salary_config.budget_manual, гривні); null або порожньо: авто
  const bm=cfg?cfg.budget_manual:null,manual: number|null=bm!=null&&bm!==''&&Number.isFinite(Number(bm))&&Number(bm)>=0?Math.round(Number(bm)*100):null;
  const valid=cfg&&[cfg.advance_day,cfg.salary_day,cfg.split_day].every(v=>Number.isInteger(Number(v))&&Number(v)>=1&&Number(v)<=31);
  const monthIndex=(s: string)=>Number(s.slice(0,4))*12+Number(s.slice(5,7))-1;
  const ym=(k: number)=>[Math.floor(k/12),k%12+1];
  const last=(y: number,m: number)=>new Date(Date.UTC(y,m,0)).getUTCDate();
  const weekdays=(y: number,m: number,lo: number,hi: number)=>{let n=0;for(let d=lo;d<=hi;d++){const w=day(date(y,m,d)).getUTCDay();if(w!==0&&w!==6)n++;}return n;};
  // Ставка діє за відпрацьовані дні; дата виплати не змінює ставку попереднього місяця.
  const earnedAmount=(y: number,m: number,lo: number,hi: number,fixed: unknown)=>{
    const total=weekdays(y,m,1,last(y,m)),worked=weekdays(y,m,lo,hi),base=Number(cfg!.rate)||0;
    const schedule=(Array.isArray(cfg!.rate_schedule)?cfg!.rate_schedule:[]).filter((x: any)=>x&&/^\d{4}-\d{2}-\d{2}$/.test(x.effective_from)&&Number.isFinite(Number(x.rate))&&Number(x.rate)>0&&x.effective_from<=date(y,m,hi)).slice().sort((a: any,b: any)=>a.effective_from.localeCompare(b.effective_from));
    if(!schedule.length)return base>0?base/total*worked:Number(fixed)||0;
    let weighted=0,fixedDays=0;
    for(let d=lo;d<=hi;d++){const iso=date(y,m,d),w=day(iso).getUTCDay();if(w===0||w===6)continue;let rate=base;for(const x of schedule){if(x.effective_from>iso)break;rate=Number(x.rate);}if(rate>0)weighted+=rate;else fixedDays++;}
    return weighted/total+(worked?fixedDays/worked*(Number(fixed)||0):0);
  };
  const payoutList: Record<string,any>[]=[];
  if(valid)for(let k=monthIndex(asof)-2;k<=monthIndex(through)+3;k++){
    const [y,m]=ym(k),[py,pm]=ym(k-1);
    for(const kind of ['advance','salary']){let d=date(y,m,Number(cfg[kind+'_day']));const w=day(d).getUTCDay();d=plus(d,w===6?-1:w===0?1:0);const [sy,sm]=kind==='advance'?[y,m]:[py,pm];const rate=Number(cfg.rate)||0;
      const amountCents=cents(earnedAmount(sy,sm,kind==='advance'?1:Number(cfg.split_day)+1,kind==='advance'?Number(cfg.split_day):last(sy,sm),cfg[kind+'_amount']));
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
  // Після end_date (включно) постійний платіж чи дохід подій не дає.
  const ended=(f: Fixed,d: string)=>!!f.end_date&&d>String(f.end_date).slice(0,10);
  // Витрата з fixed_id закриває місяць своєї дати і тиждень пн-нд; витрата з credit_id: розстрочку свого місяця.
  const paid=new Set(txs.filter(t=>t.type==='expense'&&t.fixed_id!=null).flatMap(t=>{const d=String(t.payment_due_date??txDate(t)).slice(0,10);return [String(t.fixed_id)+'|'+d.slice(0,7),...(/^\d{4}-\d{2}-\d{2}$/.test(d)?[String(t.fixed_id)+'|W'+monday(d)]:[])];}));
  const paidCredit=new Set(txs.filter(t=>t.type==='expense'&&t.credit_id!=null).map(t=>String(t.credit_id)+'|'+String(t.payment_due_date??txDate(t)).slice(0,7)));
  for(let k=monthIndex(asof);k<=monthIndex(endGeneration);k++){
    const [y,m]=ym(k),month=date(y,m,1).slice(0,7);
    (data.fixed||[]).forEach((f,i)=>{const d=date(y,m,Math.min(Number(f.day_of_month),last(y,m)));if((f.period==='year'&&Number(f.month_of_year)!==m)||weekly(f)||f.active===false||d<asof||d>endGeneration||ended(f,d)||(f.id!=null&&paid.has(String(f.id)+'|'+month)))return;events.push(make('fixed:'+String(f.id??i)+':'+month,d,f.name,f.type==='income'?'income':'mandatory',Math.max(0,cents(f.amount)),{creditEligible:f.type!=='income'&&f.credit_ok===true}));});
    // Розстрочка з датою <= asof сплачена за планом; витрата з credit_id закриває платіж свого місяця.
    (data.credits||[]).forEach((c,i)=>{const d=date(y,m,Math.min(Number(c.payment_day),last(y,m))),first=Number(c.start_year)*12+Number(c.start_month);if(d<=asof||d>endGeneration||k<first||k>=first+Number(c.total_payments)||(c.id!=null&&paidCredit.has(String(c.id)+'|'+month)))return;events.push(make('installment:'+String((c as any).id??i)+':'+month,d,c.name+' (розстрочка)','mandatory',Math.max(0,cents(c.monthly_amount)),{creditEligible:c.credit_ok===true}));});
  }
  // Щотижневі постійні: подія на кожну дату з ISO-днем weekday, id з датою події; оплачений тиждень подій не дає.
  (data.fixed||[]).forEach((f,i)=>{const w=Number(f.weekday);if(!weekly(f)||f.active===false||!Number.isInteger(w)||w<1||w>7)return;
    for(let d=plus(asof,(w-isoDay(asof)+7)%7);d<=endGeneration;d=plus(d,7)){if(ended(f,d))break;if(f.id!=null&&paid.has(String(f.id)+'|W'+monday(d)))continue;events.push(make('fixed:'+String(f.id??i)+':'+d,d,f.name,f.type==='income'?'income':'mandatory',Math.max(0,cents(f.amount)),{creditEligible:f.type!=='income'&&f.credit_ok===true}));}
  });
  // договірний строк 24-го M+1: лише інформаційне поле contractualDueDate, у розрахунках не бере участі
  const dueFor=(m: string)=>{const [y,n]=ym(monthIndex(m+'-01')+1);return date(y,n,24);};
  // v147: дата погашення лише за спільним правилом repayDate (виплата 21-го в M+1), однакова для рушія, каси, бота й чипів
  for(const a of accounts)for(const [month,amount] of a.debt_months){const due=dueFor(month),planned=repayDate(month,asof);events.push(make('repay:'+String(a.id)+':'+month,planned,a.name||'Погашення кредитки','repay',cents(amount),{accountId:a.id,debtDeltaCents:-cents(amount),contractualDueDate:due,plannedRepaymentDate:planned}));}
  const minSpend: Record<string,any>[]=[];
  for(const a of accounts){if(a.id==null||cents(a.min_spend)<=0)continue;let spent=0,metOn;
    for(const t of txs.filter(t=>String(t.account_id)===String(a.id)&&t.type==='expense'&&t.transfer_id==null&&txDate(t).slice(0,7)===asof.slice(0,7)).sort((a,b)=>cmp(txDate(a),txDate(b))||cmp(String(a.created_at),String(b.created_at))||cents(a.amount)-cents(b.amount))){spent+=cents(t.amount);if(metOn==null&&spent>=cents(a.min_spend))metOn=txDate(t);}
    minSpend.push({accountId:a.id,month:asof.slice(0,7),spent:spent/100,min:cents(a.min_spend)/100,fee:cents(a.min_spend_fee)/100,left:Math.max(0,cents(a.min_spend)-spent)/100,...(metOn?{metOn}:{})});
  }
  const order: Record<string,number>={payout:0,income:1,arrears:2,repay:3,prepay:4,savings:5,mandatory:6,fee:7,variable:8};
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
      const due=dueFor(e.date.slice(0,7)),planned=repayDate(e.date.slice(0,7),asof);const repayment=make('scenario-repay:'+e.occurrenceId+':'+String(a.id),planned,'Погашення сценарного боргу','repay',n,{accountId:a.id,debtDeltaCents:-n,contractualDueDate:due,plannedRepaymentDate:planned});
      scenario.repayments.push(repayment);events.push(repayment);
    }
  }
  // Поточний місяць підтверджують факти; майбутній: лише явно задане фінансування.
  for(let k=monthIndex(asof);k<=monthIndex(endGeneration);k++){
    const [y,m]=ym(k),month=date(y,m,1).slice(0,7),[ny,nm]=ym(k+1),d=date(ny,nm,1);if(d>endGeneration)continue;
    for(const a of accounts){if(a.id==null||cents(a.min_spend)<=0||cents(a.min_spend_fee)<=0)continue;
      const actual=sum(txs.filter(t=>String(t.account_id)===String(a.id)&&t.type==='expense'&&t.transfer_id==null&&txDate(t).slice(0,7)===month).map(t=>cents(t.amount)));
      const assigned=month===asof.slice(0,7)?0:sum(events.filter(e=>e.kind==='mandatory'&&String(e.accountId)===String(a.id)&&e.date.slice(0,7)===month).map(e=>e.amountCents));
      if(actual+assigned<cents(a.min_spend))events.push(make('fee:'+a.id+':'+month,d,'Комісія: '+(a.name||a.id),'fee',cents(a.min_spend_fee),{accountId:a.id,certainty:'conditional'}));
    }
  }
  // Категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit.
  const expenseCats=(data.categories||[]).filter(c=>c.active!==false&&c.type==='expense'&&!c.budget_role&&!(String(c.id)==='savings'||String(c.name||'').normalize('NFKC').trim().toLocaleLowerCase('uk-UA')==='заощадження'));
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
  const monthlyRows=data.monthly_budgets||[],monthlyOptions={categories:data.categories||[]};
  const rolePlan=monthlyPeriodBudget([],asof,asof,monthlyOptions),savingsIds=new Set(rolePlan.savingsCategoryIds),debtIds=new Set(rolePlan.debtCategoryIds);
  const actualCardRepayment=(target:any,rows:any[],original:any[],effective:any[])=>{
 const raw=original.find(a=>String(a.id)===String(target.account_id)),current=effective.find(a=>String(a.id)===String(target.account_id));if(!raw||!current)return 0;
 const time=(t:any)=>Date.parse(t.created_at||String(t.date)+'T00:00:00Z'),ordered=rows.filter(t=>String(t.account_id)===String(target.account_id)).slice().sort((a,b)=>time(a)-time(b)||String(a.id??'').localeCompare(String(b.id??''))),at=ordered.indexOf(target),stamp=Date.parse(raw.balance_updated_at||'');
 let debt=Math.max(0,Math.round((Number(raw.debt)||0)*100)),own=Math.max(0,Math.round((Number(raw.balance)||0)*100));
 if(!raw.mono_account_id&&Number.isFinite(stamp)&&time(target)>stamp){for(const t of ordered.slice(0,at)){if(Number.isFinite(stamp)&&time(t)<=stamp)continue;const n=Math.max(0,Math.round((Number(t.amount)||0)*100));if(t.type==='income'){const cut=Math.min(debt,n);debt-=cut;own+=n-cut;}else{const used=Math.min(own,n);own-=used;debt+=n-used;}}}
 else{let net=Math.round(((Number(current.balance)||0)-(Number(current.debt)||0))*100);for(const t of ordered.slice(at)){const n=Math.max(0,Math.round((Number(t.amount)||0)*100));net+=t.type==='income'?-n:n;}debt=Math.max(0,-net);}
 return Math.min(Math.max(0,Math.round((Number(target.amount)||0)*100)),debt);
};
  const debtProgress=(month:string)=>{
    const monthTx=txs.filter(t=>txDate(t).slice(0,7)===month.slice(0,7)),seenTransfers=new Set<string>();let cardPaymentsCents=0;
    for(const t of monthTx){if(t.type!=='income'||t.transfer_id==null)continue;const key=String(t.transfer_id),dest=accounts.find(a=>String(a.id)===String(t.account_id));
      if(seenTransfers.has(key)||dest?.kind!=='credit'||!txs.some(s=>s.transfer_id===t.transfer_id&&s.type==='expense'&&String(s.account_id)!==String(t.account_id)&&accounts.some(a=>String(a.id)===String(s.account_id)&&a.kind!=='credit')))continue;
      seenTransfers.add(key);cardPaymentsCents+=actualCardRepayment(t,txs,data.accounts||[],accounts);}
    const row=monthlyRows.filter(r=>String(r.month_start)<=month).sort((a,b)=>String(a.month_start).localeCompare(String(b.month_start))).pop(),reserved:Record<string,number>={},paid:Record<string,number>={};
    for(const x of row?.mandatory_items||[])if(x.kind==='installment'){const key=String(x.key).split(':')[1]+'|'+month.slice(0,7);reserved[key]=(reserved[key]||0)+Number(x.amount_cents||0);}
    for(const t of monthTx)if(t.type==='expense'&&t.credit_id!=null&&t.transfer_id==null){const key=String(t.credit_id)+'|'+String(t.payment_due_date??txDate(t)).slice(0,7);paid[key]=(paid[key]||0)+Math.max(0,cents(t.amount));}
    const installmentAdditionalPaymentsCents=sum(Object.entries(paid).map(([key,n])=>Math.max(0,n-(reserved[key]||0))));return{cardPaymentsCents,installmentAdditionalPaymentsCents,debtPaymentsCents:cardPaymentsCents+installmentAdditionalPaymentsCents};
  };
  const monthlyPlan=(start:string,end:string,legacyTarget:number,subtractActual=false)=>{
    if(!monthlyRows.length)return null;
    const legacy=split(legacyTarget),m=monthlyPeriodBudget(monthlyRows,start,end,{...monthlyOptions,legacyTargetCents:legacyTarget,legacyAllocations:Object.fromEntries(legacy.rows.map((c,i)=>[c.id,legacy.totals[i]]))});
    if(!m.covered)return null;
    const by:Record<string,number>={},remainingSegments:any[]=[],monthSignedSpendableCaps:Record<string,number>={},monthDebtProgress:Record<string,any>={};
    for(const seg of m.segments){
      const md=day(seg.month),monthEnd=date(md.getUTCFullYear(),md.getUTCMonth()+2,1),full=monthlyPeriodBudget(monthlyRows,seg.month,monthEnd,monthlyOptions),budgetRows=[...seg.categories,{id:'unallocated',totalCents:seg.unallocatedCents}],fullRows=[...full.categories,{id:'unallocated',totalCents:full.unallocatedCents}];
      const fact=txs.filter(t=>t.type==='expense'&&t.fixed_id==null&&t.credit_id==null&&t.transfer_id==null&&txDate(t)>=seg.month&&txDate(t)<monthEnd),known=new Set((seg.legacy?seg.categories:full.categories).map((c:any)=>c.id));
      const cat=(t:AccTx)=>t.category_id!=null&&!debtIds.has(String(t.category_id))&&known.has(String(t.category_id))?String(t.category_id):'unallocated';
      const projected=events.filter(e=>(e.kind==='variable'||e.budgetSavings)&&e.date>=seg.month&&e.date<seg.start);
      let values=budgetRows.map(c=>{if(debtIds.has(c.id))return 0;const spent=sum(fact.filter(t=>cat(t)===c.id).map(t=>cents(t.amount))),part=subtractActual?sum(fact.filter(t=>cat(t)===c.id&&txDate(t)>=seg.start&&txDate(t)<seg.end).map(t=>cents(t.amount))):0;
        const used=sum(projected.filter(e=>String(e.categoryId)===c.id).map(e=>e.amountCents)),cap=seg.legacy?Infinity:Math.max(0,(fullRows.find(x=>x.id===c.id)?.totalCents||0)-spent-used);
        return Math.min(Math.max(0,c.totalCents-part),cap);});
      const actualPart=subtractActual?sum(fact.filter(t=>txDate(t)>=seg.start&&txDate(t)<seg.end).map(t=>cents(t.amount))):0;
      // Перевитрата звичайної категорії зменшує спільний залишок, а не резерв заощаджень.
      const savingsIndexes=budgetRows.map((c,i)=>!seg.legacy&&savingsIds.has(c.id)?i:-1).filter(i=>i>=0),ordinaryIndexes=budgetRows.map((_,i)=>i).filter(i=>!savingsIndexes.includes(i));
      const savingsRemaining=sum(savingsIndexes.map(i=>values[i])),ordinaryCandidates=ordinaryIndexes.map(i=>values[i]);
      const fullSavingsRemaining=seg.legacy?0:Math.max(0,full.savingsTargetCents-sum(fact.filter(t=>savingsIds.has(cat(t))).map(t=>cents(t.amount)))-sum(projected.filter(e=>e.budgetSavings).map(e=>e.amountCents)));
      const debtPaid=debtProgress(seg.month),debtExtraOverrunCents=Math.max(0,debtPaid.debtPaymentsCents-full.debtBudgetTargetCents);monthDebtProgress[seg.month]={...debtPaid,debtBudgetTargetCents:full.debtBudgetTargetCents,debtExtraOverrunCents};
      const monthSigned=full.targetCents-full.debtBudgetTargetCents-debtExtraOverrunCents-sum(fact.map(t=>cents(t.amount)))-sum(projected.map(e=>e.amountCents))-fullSavingsRemaining,segmentSigned=seg.targetCents-seg.debtBudgetTargetCents-actualPart-savingsRemaining;
      const signedSpendableRemainingCents=Math.min(sum(ordinaryCandidates),segmentSigned,seg.legacy?Infinity:monthSigned);
      const ordinary=allocate(Math.max(0,signedSpendableRemainingCents),ordinaryCandidates);ordinaryIndexes.forEach((j,i)=>values[j]=ordinary[i]);
      if(!seg.legacy)monthSignedSpendableCaps[seg.month]=monthSigned;
      if(!subtractActual||seg.end>asof){budgetRows.forEach((c,i)=>by[c.id]=(by[c.id]||0)+values[i]);remainingSegments.push({...seg,categories:budgetRows.map((c,i)=>({id:c.id,totalCents:values[i]})),targetCents:sum(values),savingsTargetCents:savingsRemaining,spendableTargetCents:sum(ordinary),signedSpendableRemainingCents});}
    }
    return {...m,remainingSegments,monthSignedSpendableCaps,monthDebtProgress,debtExtraOverrunCents:sum(Object.values(monthDebtProgress).map(p=>p.debtExtraOverrunCents)),signedSpendableRemainingCents:sum(remainingSegments.map(s=>s.signedSpendableRemainingCents)),rawCategories:m.categories,rawUnallocatedCents:m.unallocatedCents,rawTargetCents:m.targetCents,rawSavingsTargetCents:m.savingsTargetCents,debtBudgetTargetCents:m.debtBudgetTargetCents,rawSpendableTargetCents:m.spendableTargetCents,savingsTargetCents:sum(Object.entries(by).filter(([id])=>savingsIds.has(id)).map(([,n])=>n)),spendableTargetCents:sum(Object.entries(by).filter(([id])=>!savingsIds.has(id)).map(([,n])=>n)),targetCents:sum(Object.values(by)),categories:Object.entries(by).filter(([id])=>id!=='unallocated').map(([id,totalCents])=>({id,totalCents})),unallocatedCents:by.unallocated||0};
  };
  const distribution=(target: number,start: string,end: string,available: number,caps?: number[],monthly?: any,uniform=false)=>{const count=distance(start,end),exact=monthly||monthlyPlan(start,end,target),chosen=exact?[...exact.categories.filter((c:any)=>!debtIds.has(c.id)&&!savingsIds.has(c.id)),{id:'unallocated',totalCents:exact.unallocatedCents}]:null,{rows,totals}=chosen?{rows:chosen.map((c:any)=>({id:c.id,name:(data.categories||[]).find(x=>String(x.id)===c.id)?.name||(c.id==='unallocated'?'Не розподілено':'Категорія '+c.id),weight:0})),totals:uniform?allocate(target,chosen.map((c:any)=>c.totalCents)):chosen.map((c:any)=>c.totalCents)}:split(count>0?target:0,caps),remaining=totals.slice(),schedule=[];let balance=available;
    const natural=chosen&&!uniform?monthlyPeriodBudget(monthlyRows,start,end,monthlyOptions):null,direct=natural?.covered&&natural.targetCents===sum(totals)&&rows.every((r,i)=>(r.id==='unallocated'?natural.unallocatedCents:natural.categories.find(c=>c.id===r.id)?.totalCents||0)===totals[i]);
    for(let i=0;i<count;i++){const effective=sum(totals),daily=direct?monthlyPeriodBudget(monthlyRows,plus(start,i),plus(start,i+1),monthlyOptions):null;let spendCents=Math.floor(effective/count)+(i<effective%count?1:0),amounts=chosen&&!uniform?totals.map((n,j)=>{if(daily)return rows[j].id==='unallocated'?daily.unallocatedCents:daily.categories.find(c=>c.id===rows[j].id)?.totalCents||0;const dt=plus(start,i),seg=exact.remainingSegments?.find((x:any)=>x.start<=dt&&x.end>dt);if(seg){const lo=seg.start>start?seg.start:start,hi=seg.end<end?seg.end:end,D=distance(lo,hi),k=distance(lo,dt),v=seg.categories.find((c:any)=>c.id===rows[j].id)?.totalCents||0;return Number(BigInt(v)*BigInt(k+1)/BigInt(D)-BigInt(v)*BigInt(k)/BigInt(D));}return Number(BigInt(n)*BigInt(i+1)/BigInt(count)-BigInt(n)*BigInt(i)/BigInt(count));}):i===count-1?remaining.slice():allocate(spendCents,remaining);if(chosen)spendCents=sum(amounts);amounts.forEach((n,j)=>remaining[j]-=n);balance=safe(balance-spendCents);schedule.push({date:plus(start,i),spendCents,remainingCents:balance,byCategory:rows.map((c,j)=>({id:c.id,name:c.name,amountCents:amounts[j],...(exact?.covered&&savingsIds.has(c.id)?{budgetSavings:true}:{})}))});}
    const savingsTargetCents=exact?.covered?exact.savingsTargetCents:0;
    return {categories:rows.map((c,i)=>({...c,totalCents:totals[i]})),schedule,savingsTargetCents,spendableTargetCents:sum(totals)};
  };
  const between=(start: string,end: string)=>events.filter(e=>e.date>=start&&e.date<end&&e.kind!=='variable');
  const mandatory=(start: string,end: string)=>sum(between(start,end).filter(e=>e.kind==='mandatory'||e.kind==='fee').map(e=>e.amountCents));
  // До наступної виплати: власні кошти мінус обовʼязкові й комісії [asof; виплата); борг карток гаситься з виплати.
  const untilPayout=nextDate?(()=>{const days=distance(asof,nextDate),value=safe(positiveOwnCents-mandatory(asof,nextDate));return {end:nextDate,days,cents:value,dailyCents:value>0&&days>0?Math.floor(value/days):0};})():null;
  let nextPlan: Record<string,any>|null=null,currentPeriod: Record<string,any>|null=null;
  const periods: Record<string,any>[]=[];
  if(hasPlan){const next=payoutAt(nextDate),after=payoutAt(followingDate),mandatoryCents=mandatory(nextDate,followingDate),baseAvailableCents=safe(positiveOwnCents+next.amountCents-mandatoryCents-creditDebtCents),legacyTarget=Math.max(1500000,baseAvailableCents),mp=monthlyPlan(nextDate,followingDate,legacyTarget),targetCents=mp?mp.targetCents:legacyTarget;
    nextPlan={start:nextDate,end:followingDate,days:distance(nextDate,followingDate),nextPayout:next,followingPayout:after,positiveOwnCents,debtCents:creditDebtCents,mandatoryCents,otherIncomeCents:sum(between(nextDate,followingDate).filter(e=>e.kind==='income').map(e=>e.amountCents)),eligibleMandatoryCents:sum(between(nextDate,followingDate).filter(e=>e.kind==='mandatory'&&e.creditEligible).map(e=>e.amountCents)),baseAvailableCents,targetCents,gapCents:Math.max(0,targetCents-baseAvailableCents),averageDailyCents:(mp?mp.spendableTargetCents:targetCents)/distance(nextDate,followingDate),...distribution(targetCents,nextDate,followingDate,baseAvailableCents,undefined,mp),...(mp?{debtBudgetTargetCents:mp.debtBudgetTargetCents,grossBudgetTargetCents:mp.rawTargetCents}:{}),...(mp?{monthlyBudget:mp}:{})};
    // Поточний період: каса мінус обовʼязкові до виплати; борг карток резервується один раз у nextPlan.
    // Темп щоденних витрат від завтра до дня перед виплатою: більше з 15 000 ₴ на весь період [start; виплата) і untilPayout на дні, що лишились.
    // Сума в гривнях на прогноз від завтра: ліміт мінус факт змінних витрат категорії з початку періоду, не нижче 0.
    let start=payoutDates.filter(d=>d<=asof).pop()||asof,actualVariableCents=sum(txs.filter(t=>t.type==='expense'&&t.transfer_id==null&&t.fixed_id==null&&t.credit_id==null&&txDate(t)>=start).map(t=>cents(t.amount))),mandatoryCentsNow=mandatory(asof,nextDate),available=safe(cashCents-mandatoryCentsNow),periodDays=distance(start,nextDate),leftDays=Math.max(0,distance(plus(asof,1),nextDate)),floorLeft=periodDays>0?Math.floor((manual!=null?manual:1500000)*leftDays/periodDays):0,freeLeft=Math.max(0,untilPayout?untilPayout.cents:0),remaining=leftDays>0?Math.max(floorLeft,manual!=null?manual-actualVariableCents:freeLeft):0,target=actualVariableCents+remaining,caps=categories.map(c=>c.limitAbsCents==null?0:Math.max(0,c.limitAbsCents-sum(txs.filter(t=>t.type==='expense'&&t.transfer_id==null&&t.fixed_id==null&&t.credit_id==null&&txDate(t)>=start&&t.category_id!=null&&String(t.category_id)===c.id).map(t=>cents(t.amount))))),dist=distribution(remaining,plus(asof,1),nextDate,available,caps);
    const currentMonthly=monthlyPlan(start,nextDate,target),remainingMonthly=currentMonthly?monthlyPlan(start,nextDate,target,true):null;
    if(currentMonthly&&remainingMonthly){target=currentMonthly.rawTargetCents;remaining=remainingMonthly.targetCents;
      // Єдиний денний план: перевитрата попередньої частини періоду зменшує спільний залишок.
      // Сьогодні має свою частку плану, але її не додаємо до фактичного балансу як вигадану витрату.
      dist=distribution(Math.max(0,remainingMonthly.signedSpendableRemainingCents),asof,nextDate,available,undefined,remainingMonthly,true);
    }
    const actualSavingsCents=currentMonthly?sum(txs.filter(t=>t.type==='expense'&&t.transfer_id==null&&t.fixed_id==null&&t.credit_id==null&&txDate(t)>=start&&savingsIds.has(String(t.category_id))).map(t=>cents(t.amount))):0,savingsTargetCents=currentMonthly?currentMonthly.rawSavingsTargetCents:0,savingsRemainingCents=remainingMonthly?remainingMonthly.savingsTargetCents:0;
    const signedSpendableRemainingCents=remainingMonthly?remainingMonthly.signedSpendableRemainingCents:remaining-savingsRemainingCents,spendableRemainingCents=Math.max(0,signedSpendableRemainingCents);
    currentPeriod={start,end:nextDate,actualVariableCents,actualSpendableCents:actualVariableCents-actualSavingsCents,actualSavingsCents,targetCents:target,remainingTargetCents:remaining,savingsTargetCents,debtBudgetTargetCents:currentMonthly?.debtBudgetTargetCents||0,debtExtraOverrunCents:remainingMonthly?.debtExtraOverrunCents||0,spendableTargetCents:target-savingsTargetCents-(currentMonthly?.debtBudgetTargetCents||0),savingsRemainingCents,signedSpendableRemainingCents,spendableRemainingCents,periodDays,leftDays,dailyCents:currentMonthly?spendableRemainingCents/Math.max(1,distance(asof,nextDate)):leftDays>0?(remaining-savingsRemainingCents)/leftDays:0,futureSchedule:dist.schedule,...(currentMonthly?{monthlyBudget:currentMonthly,overrunCents:Math.max(0,-signedSpendableRemainingCents)}:{})};
    periods.push({start,end:nextDate,basis:'current',openingCashCents:cashCents,payoutCents:0,mandatoryCents:mandatoryCentsNow,debtReserveCents:0,availableCents:available,targetCents:target,gapCents:Math.max(0,remaining-available),...dist,...(currentMonthly?{monthlyBudget:currentMonthly}:{})});
  }
  // v151 (власник: «власні кошти не можуть бути мінусові»): послідовна симуляція від asof. Власні (дебетові й готівка) не нижче 0.
  // Витрата понад вільні власні йде в борг: спершу Mono (рахунок з mono_account_id), далі інші картки з кредитним лімітом, кожна до свого ліміту.
  // Обовʼязковий платіж лише з дебетової (credit_ok=false) і комісія кредиту не беруть: непокрите стає нестачею (попередження), яку гасить наступне надходження.
  // v152 (власник: «одразу має закритись кредитки з власних коштів»): КОЖНА виплата (зарплата чи аванс, не лише 21-го) проходить той самий розподіл.
  // Розподіл виплати: резерв дебетових обовʼязкових до наступної виплати, погашення
  // min(борг, max(0, власні − резерв − 15 000)), але не менше належного на цю дату (спершу належне, далі інші картки, далі Mono);
  // A = власні − резерв − погашення; бюджет min(20 000, A), якщо A > 15 000, інакше 15 000; надлишок A − бюджет понад 10 000 ішов у накопичення (до v153 доповнення 7: тепер накопичення лише із залишку періоду, поріг не діє);
  // готівка 3 000, решта на Mono і спершу гасить борг Mono. До v152 так розподілялась лише виплата в день погашення (repayDate попереднього місяця), аванс ішов без погашення.
  // Погашення кошика на кожній виплаті має власну подію: перше repay:<рахунок>:<місяць>, наступні того ж кошика repay:<рахунок>:<місяць>:<дата>.
  // v153 (власник обрав А+Б): А. резерв виплати = дебетові обовʼязкові й комісії (reserved) плюс обовʼязкові з кредитки credit_ok (reservedOk) до наступної
  // виплати: вони платяться з власних, кредитка під них не наростає. Власні мають три шари: reserved, reservedOk, вільні. Дебетовий платіж бере
  // reserved, вільні, reservedOk; credit_ok бере reservedOk, вільні, потім кредитку, останнім reserved; змінні й інші: вільні, кредитка, reservedOk, reserved.
  // v154 (власник: «приват тут буде погашено повністю, а монобанк частково, але точно кредитні одразу мають зменшуватися»): доповнення А v153 скасовано.
  // Резерв виплати = лише білі (credit_ok=false) обовʼязкові, чергові білі платежі розстрочок і комісії до наступної виплати; разом із бюджетом
  // періоду це все, що тримається з виплати. Обовʼязкові з credit_ok не резервуються: як до v153, беруть вільні власні, далі кредитку.
  // Решта понад резерв і бюджет одразу в день виплати гасить кредитки (належне, далі не-Mono, далі Mono), окрема подія на кожен рахунок.
  // Шар reservedOk лишається в спільному списанні, але завжди 0.
  // Б. накопичення = max(0, надлишок − нестача), нестача = найглибший мінус власних після розподілу за подіями періоду (обовʼязкові, комісії,
  // змінні за новим планом на день, інші надходження) до наступної виплати. Порядок: резерв, погашення максимум, бюджет, накопичення, готівка, решта.
  // v153 (власник: «як ти гасиш кредитку, якщо на це немає білих грошей?»): порядок резерв, бюджет (авто або ручна сума), погашення з решти
  // (належне першим), накопичення, готівка, решта на Mono. Непокрите належне лишається на кредитці (dueShortCents, попередження due_short).
  // Решта на Mono гасить борг Mono лише надлишком понад бюджет; день без виплати гасить належне лише з вільних понад резерв і змінні до виплати.
  for(let i=events.length-1;i>=0;i--)if(events[i].kind==='repay')events.splice(i,1);
  const limitOf=(a: Record<string,any>)=>a.credit_limit==null?0:Math.max(0,cents(a.credit_limit));
  const lenders=[...accounts.filter(a=>a.mono_account_id&&limitOf(a)>0),...accounts.filter(a=>!a.mono_account_id&&limitOf(a)>0)];
  const book: Record<string,Record<string,number>>={};
  for(const a of accounts){book[String(a.id)]={};for(const [m,v] of a.debt_months)book[String(a.id)][m]=(book[String(a.id)][m]||0)+cents(v);}
  const debtOf=(a: Record<string,any>)=>sum(Object.values(book[String(a.id)]));
  const debtAll=()=>sum(accounts.map(debtOf));
  const debitOnly=(e: Record<string,any>)=>e.kind==='fee'||(e.kind==='mandatory'&&e.creditEligible!==true&&e.funding!=='credit');
  const okFunded=(e: Record<string,any>)=>e.kind==='mandatory'&&!debitOnly(e)&&e.funding!=='credit';
  const simEnd=hasPlan&&nextDate>through?nextDate:through;
  const byDate: Record<string,Record<string,any>[]>={};
  const put=(e: Record<string,any>)=>{(byDate[e.date]=byDate[e.date]||[]).push(e);};
  const categoryEvent=(d:string,c:any)=>make((c.budgetSavings?'budget-savings:':'variable:')+d+':'+c.id,d,c.budgetSavings?'У заощадження: '+c.name:c.name,c.budgetSavings?'savings':'variable',c.amountCents,{categoryId:c.id,...(c.budgetSavings?{budgetSavings:true,plannedCents:c.amountCents}:{})});
  for(const p of periods)for(const d of p.schedule)for(const c of d.byCategory)if(c.amountCents>0&&!(p.basis==='current'&&d.date===asof))events.push(categoryEvent(d.date,c));
  for(const e of events)if(e.date>=asof&&e.date<=simEnd)put(e);
  const debitBetween=(start: string,end: string)=>sum(events.filter(e=>e.date>=start&&e.date<end&&debitOnly(e)).map(e=>e.amountCents));
  // Старт: власні як у плитці (positiveOwnCents); мінусові залишки рахунків і мінусова поправка стають нестачею, яку гасить перше надходження
  let own=positiveOwnCents,arrears=positiveOwnCents-cashCents;
  let reserved=Math.min(own,nextDate?debitBetween(asof,nextDate):0),reservedOk=0;
  const days=[];let head: Record<string,any>|null=null,debtRun=creditDebtCents;
  // Погашення кошиків рахунку: належні (дата погашення не пізніше d) або всі за FIFO; повертає суми за місяцями
  const repayFrom=(a: Record<string,any>,limit: number,d: string,onlyDue: boolean,out: Record<string,number>)=>{let left=limit;const b=book[String(a.id)];
    for(const m of Object.keys(b).sort()){if(left<=0)break;if(b[m]<=0||(onlyDue&&repayDate(m,asof)>d))continue;const n=Math.min(left,b[m]);b[m]-=n;if(!b[m])delete b[m];left-=n;const k=String(a.id)+'|'+m;out[k]=(out[k]||0)+n;}
    return limit-left;};
  const dueOn=(d: string)=>sum(accounts.flatMap(a=>Object.entries(book[String(a.id)]).filter(([m])=>repayDate(m,asof)<=d).map(([,v])=>v)));
  // v153: належне, що лишилось непогашеним на дату, за рахунками
  const dueLeft=(d: string)=>accounts.map(a=>({accountId:a.id,name:a.name||'Кредитка',cents:sum(Object.entries(book[String(a.id)]).filter(([m])=>repayDate(m,asof)<=d).map(([,v])=>v))})).filter(x=>x.cents>0);
  // Перше погашення кошика має id repay:<рахунок>:<місяць> (за ним шукає бот), наступні часткові: з датою в кінці
  const usedRepay=new Set<string>();
  // v153 (власник: «ми не можемо заощаджувати поки не закриємо борги за кредиткою та за розстрочками»): залишок розстрочки = платіж × неоплачені
  // платежі графіка після asof (той самий графік, що й події installment:). Дострокове погашення (prepaid) зрізає графік з кінця: платіж дати p
  // = clamp(платіж + хвіст після p − prepaid, 0, платіж), тож останній може бути частковим, а далі платежі зникають. Лише прогноз, БД не змінюється.
  const inst=(data.credits||[]).map((c,i)=>{const m=Math.max(0,cents(c.monthly_amount)),first=Number(c.start_year)*12+Number(c.start_month),dates: string[]=[];
    for(let k=first;k<first+Number(c.total_payments);k++){const [y,n]=ym(k),d=date(y,n,Math.min(Number(c.payment_day),last(y,n)));if(d<=asof||(c.id!=null&&paidCredit.has(String(c.id)+'|'+d.slice(0,7))))continue;dates.push(d);}
    return {id:String((c as any).id??i),name:String(c.name||'Розстрочка'),m,dates,prepaid:0};}).filter(x=>x.m>0&&x.dates.length>0);
  const instFrom=(x: {m:number;dates:string[];prepaid:number},from: string)=>Math.max(0,x.m*x.dates.filter(v=>v>=from).length-x.prepaid);
  const instCut=(x: {id:string;m:number;dates:string[];prepaid:number},after: string)=>{for(const e of events.filter(e=>e.kind==='mandatory'&&e.date>after&&String(e.id).startsWith('installment:'+x.id+':'))){
    const eff=Math.max(0,Math.min(x.m,x.m+x.m*x.dates.filter(v=>v>e.date).length-x.prepaid));if(eff>0){e.amountCents=eff;e.cashDeltaCents=-eff;continue;}
    events.splice(events.indexOf(e),1);const b=byDate[e.date];if(b&&b.includes(e))b.splice(b.indexOf(e),1);}};
  const emitRepays=(d: string,out: Record<string,number>,list: Record<string,any>[])=>{for(const k of Object.keys(out).sort()){if(out[k]<=0)continue;const cut=k.lastIndexOf('|'),aid=k.slice(0,cut),m=k.slice(cut+1),a=accounts.find(v=>String(v.id)===aid)!,planned=repayDate(m,asof);
    const base='repay:'+aid+':'+m,id=usedRepay.has(base)?base+':'+d:base;usedRepay.add(base);
    const e=make(id,d,a.name||'Погашення кредитки','repay',out[k],{accountId:a.id,debtDeltaCents:-out[k],contractualDueDate:dueFor(m),plannedRepaymentDate:planned});events.push(e);list.push(e);}};
  // Списання з власних за шарами: D резерв дебетових, C резерв credit_ok, F вільні; повертає списане
  const spend=(x: number,tiers: string)=>{let left=x;for(const t of tiers){if(left<=0)break;const room=t==='D'?Math.min(own,reserved):t==='C'?Math.min(own,reservedOk):Math.max(0,own-reserved-reservedOk),n=Math.min(room,left);if(n<=0)continue;own-=n;left-=n;if(t==='D')reserved-=n;else if(t==='C')reservedOk-=n;}return x-left;};
  const borrow=(n: number,d: string)=>{let left=n;for(const a of lenders){if(left<=0)break;const k=Math.min(left,Math.max(0,limitOf(a)-debtOf(a)));if(k>0){const b=book[String(a.id)],m=d.slice(0,7);b[m]=(b[m]||0)+k;left-=k;}}return n-left;};
  for(let d=asof;d<=simEnd;d=plus(d,1)){
    const opening=own,openArrears=arrears,list: Record<string,any>[]=(byDate[d]||[]).slice().sort(compareEvents),gen: Record<string,any>[]=[];
    for(const e of list)if(e.kind==='payout'||e.kind==='income'){own=safe(own+e.amountCents);e.cashDeltaCents=e.amountCents;e.debtDeltaCents=0;}
    if(arrears>0&&own>0&&list.some(e=>e.kind==='payout'||e.kind==='income')){const n=Math.min(own,arrears);own-=n;arrears-=n;const e=make('arrears:'+d,d,'Сплата нестачі','arrears',n);events.push(e);gen.push(e);}
    const payout=list.filter(e=>e.kind==='payout'),end=payoutDates.find(v=>v>d)||'';
    if(payout.length&&end){
      const monthly=monthlyPlan(d,end,manual??1500000),periodManual=monthly?monthly.spendableTargetCents:manual;
      // v153 доповнення 7 (власник: «заощадження відкладаються в день заробітньої плати з того, що залишилося за поточний період, тобто в день отримання
      // заробітньої плати ми відкладаємо з авансу і навпаки»): до розподілу нової виплати залишок попереднього періоду (власні на початок дня виплати) гасить
      // борг кредиток (належне першим, далі решта, Mono останнім), потім дострокове розстрочок (найменший залишок після цього періоду першим); що лишилось,
      // коли боргів немає, іде в накопичення. З нової виплати накопичень немає: її надлишок понад резерв і бюджет лишається у власних до наступної виплати.
      const leftover=Math.max(0,Math.min(opening,own)),out: Record<string,number>={},pre: Record<string,number>={},leftoverPrepay: Record<string,any>[]=[];let leftoverSavings=0,leftoverPrepaid=0;
      const byLeft=(x: {id:string;m:number;dates:string[];prepaid:number})=>[instFrom(x,end),x.id] as [number,string];
      const prepayBy=(budget: number,list: Record<string,any>[])=>{let left=budget,n0=0;for(const x of inst.slice().sort((a,b)=>byLeft(a)[0]-byLeft(b)[0]||cmp(a.id,b.id))){if(left<=0)break;const n=Math.min(left,instFrom(x,end));if(n<=0)continue;
        x.prepaid+=n;left-=n;n0+=n;instCut(x,d);pre[x.id]=(pre[x.id]||0)+n;list.push({creditId:x.id,name:x.name,cents:n});}return n0;};
      // Увесь власний залишок спершу захищає обовʼязкові платежі та життя наступного періоду.
      const leftoverRepay=sum(Object.values(out));own-=leftoverRepay+leftoverPrepaid+leftoverSavings;
      const ownAt=own,rd=Math.min(own,debitBetween(d,end)),rc=Math.min(Math.max(0,own-rd),Math.max(0,mandatory(d,end)-debitBetween(d,end))),reserve=rd+rc;let repay=0,savings=0,cashOut=0,toMono=0,offset=0;
      {let left=payoutBudget(own,reserve,debtAll(),dueOn(d),true,periodManual).repayCents;
        for(const a of accounts){if(left<=0)break;left-=repayFrom(a,left,d,true,out);}
        for(const a of accounts.filter(a=>!a.mono_account_id)){if(left<=0)break;left-=repayFrom(a,left,d,false,out);}
        for(const a of accounts.filter(a=>a.mono_account_id)){if(left<=0)break;left-=repayFrom(a,left,d,false,out);}
        repay=sum(Object.values(out))-leftoverRepay;}
      const available=own-reserve-repay,target=payoutBudget(available,0,0,0,false,periodManual).targetCents,dist=distribution(target,d,end,available,undefined,monthly);
      // Власні після розподілу проти подій періоду (обовʼязкові, комісії, змінні за новим планом на день, інші надходження): найглибший мінус, якщо зняти ще x
      const ahead: Record<string,any>[]=events.filter(e=>e.date>=d&&e.date<end&&!(e.funding==='credit'&&e.accountId!=null)&&(e.kind==='income'?e.date>d:!['payout','repay','prepay','savings','arrears'].includes(e.kind)));
      for(const s of dist.schedule)for(const c of s.byCategory)if(c.amountCents>0)ahead.push({id:'variable:'+s.date+':'+c.id,date:s.date,kind:'variable',amountCents:c.amountCents});
      ahead.sort(compareEvents);const lowWith=(x: number)=>{let run=own-repay-x,low=0;for(const e of ahead){run+=e.kind==='income'?e.amountCents:-e.amountCents;low=Math.min(low,run);}return low;};
      // v153 доповнення 5: борг кредиток 0, тоді надлишок понад бюджет (мінус нестача до виплати) іде в дострокове погашення розстрочок, найменший залишок
      // після цього періоду першим (платежі до наступної виплати вже в резерві). Накопичення лише коли кредитки й усі розстрочки закриті.
      const payoutPrepay: Record<string,any>[]=[];let prepaid=0;
      const residual=Math.max(0,Math.min(available-target,available-target+lowWith(available-target)));
      if(debtAll()===0&&arrears===0&&residual>0)prepaid=prepayBy(residual,payoutPrepay);
      if(debtAll()===0&&arrears===0&&!inst.some(x=>instFrom(x,end)>0))savings=Math.max(0,residual-prepaid);
      const free=available-prepaid-savings;
      {cashOut=Math.min(300000,Math.max(0,free));toMono=Math.max(0,free-cashOut);
        const cap=Math.min(toMono,Math.max(0,free-target));let left=cap;for(const a of accounts.filter(a=>a.mono_account_id)){if(left<=0)break;left-=repayFrom(a,left,d,false,out);}offset=cap-left;}
      own-=repay+offset+prepaid+savings;
      emitRepays(d,out,gen);
      // одна подія дострокового погашення на розстрочку за день (із залишку періоду і з виплати разом)
      const prepay=inst.filter(x=>pre[x.id]>0).sort((a,b)=>cmp(a.id,b.id)).map(x=>({creditId:x.id,name:x.name,cents:pre[x.id]}));
      for(const x of prepay){const e=make('prepay:'+x.creditId+':'+d,d,'Дострокове погашення '+x.name,'prepay',x.cents,{creditId:x.creditId});events.push(e);gen.push(e);}
      // v153: належне, якого виплата не покрила після резерву й бюджету: лишається на кредитці, показується нестачею (не погашенням)
      const dueShort=dueLeft(d),dueShortCents=sum(dueShort.map(x=>x.cents));
      if(dueShortCents>0&&d<=through)snapshot.warnings.push({kind:'due_short',date:d,shortCents:dueShortCents,accounts:dueShort});
      if(savings>0){const ps=payoutDates.filter(v=>v<d).pop()||asof,dm=(v: string)=>v.slice(8,10)+'.'+v.slice(5,7);
        const e=make('savings:'+d,d,'У заощадження: вільний залишок після платежів і боргів','savings',savings);events.push(e);gen.push(e);}
      reserved=rd;reservedOk=rc;
      const rec: Record<string,any>={start:d,end,basis:head?'projected':'headline',openingCashCents:opening,payoutCents:sum(payout.map(e=>e.amountCents)),mandatoryCents:mandatory(d,end),debtReserveCents:leftoverRepay+repay+offset,availableCents:available,targetCents:target,gapCents:Math.max(0,target-available),ownCents:ownAt,reserveCents:reserve,repayCents:leftoverRepay+repay+offset,savingsCents:savings,cashOutCents:cashOut,toMonoCents:toMono,monoOffsetCents:offset,dueShortCents,dueShort,prepayCents:prepaid+leftoverPrepaid,prepay,leftoverCents:leftover,leftoverRepayCents:leftoverRepay,leftoverPrepayCents:leftoverPrepaid,leftoverPrepay,
        ...(monthly?{monthlyBudget:monthly,debtBudgetTargetCents:monthly.debtBudgetTargetCents,grossBudgetTargetCents:monthly.rawTargetCents}:{}),leftoverSavingsCents:leftoverSavings,payoutRepayCents:repay+offset,payoutPrepayCents:prepaid,payoutPrepay,installmentsLeft:inst.map(x=>({creditId:x.id,name:x.name,cents:instFrom(x,d)})).filter(x=>x.cents>0),...dist};
      if(!head)head=rec;
      if(d<=through)periods.push(rec);
      for(const s of rec.schedule)for(const c of s.byCategory)if(c.amountCents>0){const e=categoryEvent(s.date,c);events.push(e);if(s.date<=simEnd)put(e);}
    }else{const due=dueOn(d);if(due>0){const out: Record<string,number>={},nx=payoutDates.find(v=>v>d)||'9999-12-31';let left=Math.min(due,Math.max(0,own-reserved-reservedOk-sum(events.filter(e=>(e.kind==='variable'||e.budgetSavings)&&e.date>=d&&e.date<nx).map(e=>e.amountCents))));for(const a of accounts){if(left<=0)break;left-=repayFrom(a,left,d,true,out);}const n=sum(Object.values(out));own-=n;emitRepays(d,out,gen);
      // v153: непокрите належне: попередження в день, коли кошик став належним (не щодня)
      const dueShort=dueLeft(d);if(dueShort.length&&d<=through&&accounts.some(a=>Object.keys(book[String(a.id)]).some(m=>repayDate(m,asof)===d)))snapshot.warnings.push({kind:'due_short',date:d,shortCents:sum(dueShort.map(x=>x.cents)),accounts:dueShort});}}
    for(const e of (byDate[d]||[]).filter(e=>e.date===d&&!list.includes(e)))list.push(e);
    list.sort(compareEvents);
    for(const e of list){if(e.kind==='payout'||e.kind==='income')continue;const x=e.amountCents;
      if(e.funding==='credit'&&e.accountId!=null){const b=book[String(e.accountId)];b[d.slice(0,7)]=(b[d.slice(0,7)]||0)+x;e.cashDeltaCents=0;e.debtDeltaCents=x;continue;}
      if(e.budgetSavings){const funded=spend(x,'F');e.fundedCents=funded;e.unfundedCents=x-funded;e.amountCents=funded;e.cashDeltaCents=0-funded;e.debtDeltaCents=0;continue;}
      let fromOwn=0,borrowed=0;
      if(debitOnly(e))fromOwn=spend(x,'DFC');
      else if(okFunded(e)){fromOwn=spend(x,'CF');borrowed=borrow(x-fromOwn,d);fromOwn+=spend(x-fromOwn-borrowed,'D');}
      else{fromOwn=spend(x,'F');borrowed=borrow(x-fromOwn,d);fromOwn+=spend(x-fromOwn-borrowed,'CD');}
      const short=x-fromOwn-borrowed;arrears+=short;e.cashDeltaCents=fromOwn?-fromOwn:0;e.debtDeltaCents=borrowed;
      if(short>0){e.shortCents=short;if(d<=through&&e.kind!=='variable')snapshot.warnings.push({kind:'shortage',date:d,eventId:e.id,name:e.name,amountCents:x,shortCents:short});}
    }
    const all=[...list,...gen].sort(compareEvents);let cash=opening,debt=debtRun,owed=openArrears,minimum=opening,variable=0;const byCategory=[];
    // arrearsAfterCents: нестача після події (росте на непокриту частину, гаситься подією arrears), щоб баланс після події = власні − борг − нестача
    for(const e of all){cash=safe(cash+e.cashDeltaCents);debt=safe(debt+e.debtDeltaCents);owed=safe(owed+(e.kind==='arrears'?-e.amountCents:(e.shortCents||0)));e.cashAfterCents=cash;e.debtAfterCents=debt;e.arrearsAfterCents=owed;minimum=Math.min(minimum,cash);if(e.kind==='variable'){variable+=e.amountCents;byCategory.push({id:e.categoryId,name:e.name,amountCents:e.amountCents});}}
    if(cash!==own||debt!==debtAll()||owed!==arrears)throw new RangeError('Projection state mismatch');debtRun=debt;
    if(d<=through)days.push({date:d,openingCashCents:opening,closingCashCents:own,debtCents:debt,arrearsCents:arrears,netCents:own-debt-arrears,variableCents:variable,byCategory,minCashCents:minimum,shortfallCents:arrears,eventIds:all.map(e=>e.id)});
  }
  if(nextPlan&&head)Object.assign(nextPlan,{baseAvailableCents:head.availableCents,targetCents:head.targetCents,gapCents:head.gapCents,averageDailyCents:head.spendableTargetCents/nextPlan.days,savingsTargetCents:head.savingsTargetCents,spendableTargetCents:head.spendableTargetCents,reserveCents:head.reserveCents,repayCents:head.repayCents,savingsCents:head.savingsCents,cashOutCents:head.cashOutCents,toMonoCents:head.toMonoCents,monoOffsetCents:head.monoOffsetCents,categories:head.categories,schedule:head.schedule});
  if(scenario){const base=nextPlan?.baseAvailableCents??0;const gain=nextPlan?sum(events.filter(e=>e.funding==='credit'&&e.date>=nextPlan.start&&e.date<nextPlan.end).map(e=>e.amountCents))-sum(scenario.repayments.filter(e=>e.date>=nextPlan.start&&e.date<nextPlan.end).map(e=>e.amountCents)):0;scenario.cashPlanCents=safe(base+gain);scenario.gapCents=Math.max(0,(nextPlan?.targetCents??1500000)-scenario.cashPlanCents);}
  const visible=events.filter(e=>e.date>=asof&&e.date<=through).sort(compareEvents);
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
      t.type === 'expense' && t.transfer_id == null && txDay(t).slice(0, 7) === month);
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
export function salaryPeriodAmount(cfg: SalaryCfg, y: number, m: number, lo: number, hi: number, fixed: unknown): number {
  const total=wd(y,m,1,lastDay(y,m)),worked=wd(y,m,lo,hi),base=num(cfg.rate);
  const schedule=(Array.isArray(cfg.rate_schedule)?cfg.rate_schedule:[]).filter(x=>x&&/^\d{4}-\d{2}-\d{2}$/.test(x.effective_from)&&Number.isFinite(Number(x.rate))&&Number(x.rate)>0&&x.effective_from<=iso(mk(y,m,hi))).slice().sort((a,b)=>a.effective_from.localeCompare(b.effective_from));
  if(!schedule.length)return base>0?round2(base/total*worked):num(fixed);
  let weighted=0,fixedDays=0;
  for(let d=lo;d<=hi;d++){const when=mk(y,m,d),date=iso(when),w=when.getUTCDay();if(w===0||w===6)continue;let rate=base;for(const x of schedule){if(x.effective_from>date)break;rate=Number(x.rate);}if(rate>0)weighted+=rate;else fixedDays++;}
  return round2(weighted/total+(worked?fixedDays/worked*num(fixed):0));
}
export function monthPayouts(cfg: SalaryCfg, y: number, m: number): Payout[] {
  const rate = num(cfg.rate), split = Number(cfg.split_day);
  const [py, pm] = m > 1 ? [y, m - 1] : [y - 1, 12];
  const last = lastDay(y, m), plast = lastDay(py, pm);
  return [
    { date: iso(adj(y, m, Number(cfg.advance_day))), kind: 'advance', amount: salaryPeriodAmount(cfg,y,m,1,split,cfg.advance_amount) },
    { date: iso(adj(y, m, Number(cfg.salary_day))), kind: 'salary', amount: salaryPeriodAmount(cfg,py,pm,split+1,plast,cfg.salary_amount) },
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
    const d = String(t.payment_due_date ?? t.date ?? t.created_at ?? '').slice(0, 10);
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
      if (f.active === false || f.period === 'week' || (f.period === 'year' && Number(f.month_of_year) !== m)) continue;
      if (f.id != null && paid.has(String(f.id) + '|' + ym)) continue; // п. 13: оплачено в цьому місяці
      const d = iso(mk(y, m, Math.min(Number(f.day_of_month), ld)));
      if (!(start <= d && d < end) || fixedEnded(f, d)) continue;
      const a = num(f.amount);
      out.push({ date: d, name: f.name, amount: f.type !== 'income' ? a : -a, credit_ok: f.credit_ok === true });
    }
    for (const c of snap.credits || []) {
      if ((snap.paid_credit || []).includes(String(c.id) + '|' + ym)) continue;
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
      if (fixedEnded(f, d)) break;
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

// Погашення боргу за місяць M: спільне правило repayDate (над financeProjection)

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
  monthly_budgets?: any[];
  accounts: Account[]; fixed: Fixed[]; credits: Credit[]; salary?: SalaryCfg | null;
  transactions?: AccTx[]; account_tx?: AccTx[]; profiles?: unknown[];
  categories: { id: string | number; name?: string; type?: string; budget_role?: string | null; active?: boolean; budget_limit?: number | string | null; limit?: number | string | null; limit_abs?: number | string | null; sort_order?: number | null }[];
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
  if(data.monthly_budgets?.length&&monthlyPeriodBudget(data.monthly_budgets,next.date,after.date).covered){const projection=financeProjection(data,{asof,through:after.date});return projection.nextPlan;}
  const transactions = data.transactions ?? data.account_tx ?? [];
  const accounts = deriveAccounts(data.accounts, transactions).filter(a => a.active !== false);
  const stamps = accounts.filter(a => !a.mono_account_id && a.balance_updated_at).map(a => Date.parse(a.balance_updated_at!)).filter(Number.isFinite);
  const adjustment = stamps.length ? cents(unassignedAdj(transactions, Math.min(...stamps))) : 0;
  const positiveOwnCents = Math.max(0, sum([...accounts.map(a => Math.max(0, cents(a.balance))), adjustment]));
  const debtCents = sum(accounts.filter(a => a.kind === 'credit').map(a => Math.max(0, cents(a.debt))));
  const entries = obligations({ accounts, fixed: data.fixed, credits: (data.credits || []).map(c => ({ ...c, credit_ok: c.credit_ok === true })), salary: cfg, paid: fixedPaid(transactions), paid_credit: transactions.filter(t=>t.type==='expense'&&t.credit_id!=null).map(t=>String(t.credit_id)+'|'+String(t.payment_due_date??t.date??t.created_at??'').slice(0,7)) }, next.date, after.date);
  const mandatoryCents = sum(entries.filter(e => e.amount > 0).map(e => cents(e.amount)));
  const otherIncomeCents = sum(entries.filter(e => e.amount < 0).map(e => cents(-e.amount)));
  const eligibleMandatoryCents = sum(entries.filter(e => e.amount > 0 && e.credit_ok).map(e => cents(e.amount)));
  const incoming = sum([positiveOwnCents, cents(next.amount)]), reserved = sum([mandatoryCents, debtCents]);
  const baseAvailableCents = sum([incoming, -reserved]);
  const targetCents = Math.max(1500000, baseAvailableCents), gapCents = sum([targetCents, -baseAvailableCents]);
  // Категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit.
  const expenseCats = (data.categories || []).filter(c => c.active !== false && c.type === 'expense' && !c.budget_role && !(String(c.id)==='savings'||String(c.name||'').normalize('NFKC').trim().toLocaleLowerCase('uk-UA')==='заощадження'));
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
// Фактичний борг карток і майбутні неоплачені платежі розстрочок; без прогнозних погашень.
export function budgetDebtSummary(data:any,asof:string){
 const actualCardRepayment=(target:any,rows:any[],original:any[],effective:any[])=>{
 const raw=original.find(a=>String(a.id)===String(target.account_id)),current=effective.find(a=>String(a.id)===String(target.account_id));if(!raw||!current)return 0;
 const time=(t:any)=>Date.parse(t.created_at||String(t.date)+'T00:00:00Z'),ordered=rows.filter(t=>String(t.account_id)===String(target.account_id)).slice().sort((a,b)=>time(a)-time(b)||String(a.id??'').localeCompare(String(b.id??''))),at=ordered.indexOf(target),stamp=Date.parse(raw.balance_updated_at||'');
 let debt=Math.max(0,Math.round((Number(raw.debt)||0)*100)),own=Math.max(0,Math.round((Number(raw.balance)||0)*100));
 if(!raw.mono_account_id&&Number.isFinite(stamp)&&time(target)>stamp){for(const t of ordered.slice(0,at)){if(Number.isFinite(stamp)&&time(t)<=stamp)continue;const n=Math.max(0,Math.round((Number(t.amount)||0)*100));if(t.type==='income'){const cut=Math.min(debt,n);debt-=cut;own+=n-cut;}else{const used=Math.min(own,n);own-=used;debt+=n-used;}}}
 else{let net=Math.round(((Number(current.balance)||0)-(Number(current.debt)||0))*100);for(const t of ordered.slice(at)){const n=Math.max(0,Math.round((Number(t.amount)||0)*100));net+=t.type==='income'?-n:n;}debt=Math.max(0,-net);}
 return Math.min(Math.max(0,Math.round((Number(target.amount)||0)*100)),debt);
};
 const seen=new Set<string>(),transactions=(data.transactions||[]).filter((t:any)=>{const id=t.id==null?null:String(t.id);if(id!=null){if(seen.has(id))return false;seen.add(id);}return String(t.date||t.created_at||'').slice(0,10)<=asof;});
 const accounts=deriveAccounts(data.accounts||[],transactions).filter(a=>a.active!==false),cardDebtCents=accounts.filter(a=>a.kind==='credit').reduce((n,a)=>n+Math.max(0,Math.round((Number(a.debt)||0)*100)),0);
 const paid=new Set(transactions.filter((t:any)=>t.type==='expense'&&t.credit_id!=null).map((t:any)=>String(t.credit_id)+'|'+String(t.payment_due_date??t.date??t.created_at).slice(0,7))),installments:any[]=[];
 for(const [i,c]of (data.credits||[]).entries()){const first=Number(c.start_year)*12+Number(c.start_month),amountCents=Math.max(0,Math.round((Number(c.monthly_amount)||0)*100));for(let k=first;k<first+Number(c.total_payments);k++){const y=Math.floor(k/12),m=k%12,day=Math.min(Number(c.payment_day),new Date(Date.UTC(y,m+1,0)).getUTCDate()),date=new Date(Date.UTC(y,m,day)).toISOString().slice(0,10);if(date<=asof||paid.has(String(c.id)+'|'+date.slice(0,7)))continue;installments.push({creditId:String(c.id??i),name:String(c.name||'Розстрочка'),date,amountCents});}}
 const month=asof.slice(0,7),transferIds=new Set<string>();let cardPaymentsCents=0;
 for(const t of transactions){if(t.type!=='income'||t.transfer_id==null||String(t.date||t.created_at).slice(0,7)!==month)continue;const key=String(t.transfer_id),account=accounts.find(a=>String(a.id)===String(t.account_id));if(transferIds.has(key)||!account||account.kind!=='credit'||!transactions.some((s:any)=>s.transfer_id===t.transfer_id&&s.type==='expense'&&String(s.account_id)!==String(t.account_id)&&accounts.some(a=>String(a.id)===String(s.account_id)&&a.kind!=='credit')))continue;transferIds.add(key);cardPaymentsCents+=actualCardRepayment(t,transactions,data.accounts||[],accounts);}
 const installmentPaymentsCents=transactions.filter((t:any)=>t.type==='expense'&&t.credit_id!=null&&t.transfer_id==null&&String(t.date||t.created_at).slice(0,7)===month).reduce((n:number,t:any)=>n+Math.max(0,Math.round(Number(t.amount)*100)),0);
 const monthRow=(data.monthly_budgets||[]).filter((r:any)=>String(r.month_start)<=month+'-01').sort((a:any,b:any)=>String(a.month_start).localeCompare(String(b.month_start))).pop(),reserved:Record<string,number>={},paidAmounts:Record<string,number>={};
 for(const x of monthRow?.mandatory_items||[])if(x.kind==='installment'){const key=String(x.key).split(':')[1]+'|'+month;reserved[key]=(reserved[key]||0)+Number(x.amount_cents||0);}
 for(const t of transactions)if(t.type==='expense'&&t.credit_id!=null&&t.transfer_id==null&&String(t.date||t.created_at).slice(0,7)===month){const key=String(t.credit_id)+'|'+String(t.payment_due_date??t.date??t.created_at).slice(0,7);paidAmounts[key]=(paidAmounts[key]||0)+Math.max(0,Math.round(Number(t.amount)*100));}
 const installmentAdditionalPaymentsCents=Object.entries(paidAmounts).reduce((n,[key,amount])=>n+Math.max(0,amount-(reserved[key]||0)),0);
 const debtPaymentsCents=cardPaymentsCents+installmentAdditionalPaymentsCents,debtIds=new Set((data.categories||[]).filter((c:any)=>['debt_card','debt_installment'].includes(c.budget_role)).map((c:any)=>String(c.id))),debtBudgetTargetCents=Object.entries(monthRow?.allocations||{}).reduce((n,[id,v])=>n+(debtIds.has(id)?Number(v)||0:0),0),debtExtraOverrunCents=Math.max(0,debtPaymentsCents-debtBudgetTargetCents);
 return{cardDebtCents,debtBudgetTargetCents,debtPaymentsCents,debtExtraOverrunCents,installmentAdditionalPaymentsCents,installmentRemainingCents:installments.reduce((n,x)=>n+x.amountCents,0),cardPaymentsCents,installmentPaymentsCents,installments};
}
