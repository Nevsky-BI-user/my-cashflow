// Бюджет періоду і «вільно до виплати» за правилом власника (DESIGN.md, 08.10.2026).
// Перенесено з scripts/budget_pool.py і scripts/salary_check.py; те саме рахує застосунок (periodBudget).
// Чисті функції без залежностей: модуль запускається і в Edge Function, і в Node для звірки з Python.
// Дати: рядки YYYY-MM-DD, обчислення в UTC, щоб часовий пояс не зсував день.

export type Account = {
  id?: number; name?: string; kind?: string; balance: number | string; debt: number | string; active?: boolean;
  mono_account_id?: string | null; balance_updated_at?: string | null; debt_month?: string | null;
};
// Операція з привʼязкою до рахунку (для похідного балансу ручних рахунків)
// source: 'mono' | 'telegram' | 'manual' (потрібен лише для unassignedAdj: операції Monobank без рахунку не рахуємо)
export type AccTx = { account_id: number | null; type: string; amount: number | string; created_at: string; source?: string | null };
export type Fixed = { name: string; amount: number | string; day_of_month: number; type: string; active?: boolean; credit_ok?: boolean | null };
export type Credit = {
  name: string; monthly_amount: number | string; payment_day: number;
  start_year: number; start_month: number; total_payments: number; credit_ok?: boolean | null; source?: string | null;
};
export type SalaryCfg = { rate: number | string; split_day: number; advance_day: number; salary_day: number; savings_pct?: number | null };
export type Snapshot = { accounts: Account[]; fixed: Fixed[]; credits: Credit[]; salary: SalaryCfg; savings_pct?: number | null };

export type Payout = { date: string; kind: 'advance' | 'salary'; amount: number };
export type Obligation = { date: string; name: string; amount: number; credit_ok: boolean };

const DAY = 86_400_000;
const mk = (y: number, m: number, d: number) => new Date(Date.UTC(y, m - 1, d)); // m: 1..12
const iso = (d: Date) => d.toISOString().slice(0, 10);
const parse = (s: string) => new Date(s + 'T00:00:00Z');
export const addDays = (s: string, n: number) => iso(new Date(parse(s).getTime() + n * DAY));
export const diffDays = (a: string, b: string) => Math.round((parse(b).getTime() - parse(a).getTime()) / DAY);
const lastDay = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();
const round2 = (x: number) => Math.round(x * 100) / 100;
const num = (x: unknown) => Number(x) || 0;

// Похідний баланс ручних рахунків (DESIGN.md, «Наскрізне»): для рахунку без mono_account_id
// додаємо операції з його account_id, створені строго після balance_updated_at.
// debit/cash: balance − витрати + доходи; credit: debt + витрати − доходи (не менше 0), balance не чіпаємо.
// Рахунки Monobank не коригуємо: баланс з API уже містить усі операції. Без мітки часу теж не коригуємо.
// Витрата: усе, що не 'income' (як у freeBlock). Повертає копії, вхідні обʼєкти не змінює.
export function deriveAccounts(accounts: Account[], txs: AccTx[]): Account[] {
  return (accounts || []).map((a) => {
    const out = { ...a };
    if (a.mono_account_id || a.id == null || !a.balance_updated_at) return out;
    const since = Date.parse(a.balance_updated_at);
    if (isNaN(since)) return out;
    let exp = 0, inc = 0;
    for (const t of txs || []) {
      if (Number(t.account_id) !== Number(a.id) || !(Date.parse(t.created_at) > since)) continue;
      if (t.type === 'income') inc += num(t.amount); else exp += num(t.amount);
    }
    if (a.kind === 'credit') out.debt = round2(Math.max(0, num(a.debt) + exp - inc));
    else out.balance = round2(num(a.balance) - exp + inc);
    return out;
  });
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
    { date: iso(adj(y, m, Number(cfg.advance_day))), kind: 'advance', amount: round2(rate / wd(y, m, 1, last) * wd(y, m, 1, split)) },
    { date: iso(adj(y, m, Number(cfg.salary_day))), kind: 'salary', amount: round2(rate / wd(py, pm, 1, plast) * wd(py, pm, split + 1, plast)) },
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

// Дата платежу з днем місяця day у вікні [start; end) або null (як in_period у budget_pool.py)
function inWindow(day: number, start: string, end: string): string | null {
  const s = parse(start), e = parse(end);
  for (const [y, m] of [[s.getUTCFullYear(), s.getUTCMonth() + 1], [e.getUTCFullYear(), e.getUTCMonth() + 1]]) {
    const d = iso(mk(y, m, Math.min(day, lastDay(y, m))));
    if (start <= d && d < end) return d;
  }
  return null;
}

// Обовʼязкові у вікні [start; end): постійні (дохід зі знаком мінус) і активні розстрочки
function obligations(snap: Snapshot, start: string, end: string): Obligation[] {
  const out: Obligation[] = [];
  for (const f of snap.fixed || []) {
    if (f.active === false) continue;
    const d = inWindow(Number(f.day_of_month), start, end);
    if (!d) continue;
    const a = num(f.amount);
    out.push({ date: d, name: f.name, amount: f.type !== 'income' ? a : -a, credit_ok: f.credit_ok === true });
  }
  for (const c of snap.credits || []) {
    const d = inWindow(Number(c.payment_day), start, end);
    if (!d) continue;
    // Та сама арифметика місяців, що в budget_pool.py і застосунку
    const first = Number(c.start_year) * 12 + Number(c.start_month);
    const cur = Number(d.slice(0, 4)) * 12 + (Number(d.slice(5, 7)) - 1);
    if (first <= cur && cur <= first + Number(c.total_payments) - 1) {
      // credit_ok не заданий: кредитна, якщо розстрочка ПриватБанку (як у budget_pool.py)
      const ok = c.credit_ok ?? String(c.source || '').toLowerCase().includes('privat');
      out.push({ date: d, name: c.name + ' (розстрочка)', amount: num(c.monthly_amount), credit_ok: ok === true });
    }
  }
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

// Погашення кредитки у вікні [start; end) (DESIGN.md, п. 10): подія 25-го числа місяця E (у короткому місяці останній день)
// = борг, утворений до кінця місяця M = E-1: debt_eff кредитних рахунків із debt_month раніше за місяць E
// (лише для найближчої події від today, бо далі борг уже погашений) плюс кредитні обовʼязкові (credit_ok, витрати)
// з датою в місяці M, що ще не настала (date >= today).
export function cardRepay(snap: Snapshot, today: string, start: string, end: string): number {
  const ev = (y: number, m: number) => iso(mk(y, m, Math.min(25, lastDay(y, m))));
  const t = parse(today);
  let y = t.getUTCFullYear(), m = t.getUTCMonth() + 1;
  let first = ev(y, m);
  if (first < today) { m++; if (m > 12) { m = 1; y++; } first = ev(y, m); }
  let sum = 0;
  const s = parse(start);
  let ey = s.getUTCFullYear(), em = s.getUTCMonth() + 1;
  for (let i = 0; i < 3; i++) {
    const e = ev(ey, em);
    if (start <= e && e < end) {
      const eMonth = e.slice(0, 7);
      if (e === first) {
        for (const a of snap.accounts || []) {
          if (a.active === false || a.kind !== 'credit' || !a.debt_month) continue;
          if (String(a.debt_month).slice(0, 7) < eMonth) sum += num(a.debt);
        }
      }
      const mStart = eMonth + '-01';
      const [py, pm] = em > 1 ? [ey, em - 1] : [ey - 1, 12];
      const pStart = iso(mk(py, pm, 1));
      for (const o of obligations(snap, pStart > today ? pStart : today, mStart)) {
        if (o.credit_ok && o.amount > 0) sum += o.amount;
      }
    }
    em++; if (em > 12) { em = 1; ey++; }
  }
  return round2(sum);
}

// Бюджет періоду, що починається з першої виплати після today (точний аналог budget_pool.py)
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
  const pool0 = pn.amount - oblSum - deficit;
  const pct = num(snap.savings_pct ?? cfg.savings_pct ?? 0);
  const savings = round2(Math.max(0, pool0) * pct / 100);
  const varPool = Math.max(0, pool0 - savings);
  return { payout: pn, end: pa.date, obligations: obl, oblSum, own, debt, deficit, pool0, savings, varPool };
}

// «Вільно до виплати» на today: поточний період [остання виплата; наступна), spent: витрати з останньої виплати.
// unassigned: знакова поправка від unassignedAdj (операції без рахунку), додається до власних (п. 9).
// Рахунки в snap мають бути вже ефективні (deriveAccounts).
export function freeToPayout(snap: Snapshot, today: string, spent: number, unassigned = 0) {
  const last = lastPayout(snap.salary, today);
  const pb = periodBudget(snap, addDays(last.date, -1)); // як periodBudget(pbOpen − 1) у застосунку
  const fut = payouts(snap.salary, today, 0, 3).filter((p) => p.date > today);
  const next = fut[0], after = fut[1];
  // Власні кошти дебетових і готівкових рахунків (кредитна картка не дає плюсових грошей)
  const ownDebit = (snap.accounts || [])
    .filter((a) => a.active !== false && a.kind !== 'credit')
    .reduce((s, a) => s + num(a.balance), 0);
  // «Білі» платежі: не можна оплатити кредиткою; лише витрати, доходи cashNow не збільшують
  const white = obligations(snap, today, next.date).filter((o) => !o.credit_ok && o.amount > 0);
  // Погашення кредитки 25-го в [today; next) платиться з дебетових коштів, тож це теж «біле» (п. 10)
  const cardRepayNow = cardRepay(snap, today, today, next.date);
  const whiteSum = white.reduce((s, o) => s + o.amount, 0) + cardRepayNow;
  const cashNow = ownDebit + unassigned - whiteSum;
  const planCur = pb.varPool;
  const budgetCur = capBudget(planCur, cashNow, spent); // п. 5
  const freeRaw = Math.min(budgetCur - spent, cashNow);
  const freeNow = Math.max(0, freeRaw); // п. 6
  const shortage = cashNow < 0 ? -cashNow : 0;
  const daysLeft = Math.max(0, diffDays(today, next.date));
  const perDay = daysLeft > 0 ? freeNow / daysLeft : 0; // п. 7
  // Наступний період [next; after) (п. 8): залишок на виплату + виплата − білі − погашення кредитки, не більше планового
  const pbn = periodBudget(snap, addDays(next.date, -1));
  const whiteNext = obligations(snap, next.date, after.date).filter((o) => !o.credit_ok && o.amount > 0)
    .reduce((s, o) => s + o.amount, 0);
  const cardRepayNext = cardRepay(snap, today, next.date, after.date);
  const cashAtPayout = Math.max(0, cashNow - (budgetCur - spent));
  const varPoolNext = Math.max(0, Math.min(pbn.varPool, cashAtPayout + next.amount - whiteNext - cardRepayNext));
  return {
    lastPayout: last, nextPayout: next, periodStart: last.date, varPool: planCur, pool0: pb.pool0,
    spent, ownDebit, unassigned, white, whiteSum, cardRepayNow, cashNow, freeRaw, freeNow, daysLeft, perDay,
    planCur, varPoolCur: budgetCur, shortage,
    planNext: pbn.varPool, whiteNext, cardRepayNext, varPoolNext, cashAtPayout,
  };
}
