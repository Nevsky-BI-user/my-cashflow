// Бюджет періоду, каса по датах і «вільно до виплати» за правилом власника (DESIGN.md, п. 1-13, 08-09.10.2026).
// Перенесено з scripts/budget_pool.py і scripts/salary_check.py; те саме рахує застосунок (periodBudget).
// Чисті функції без залежностей: модуль запускається і в Edge Function, і в Node для звірки з Python.
// Дати: рядки YYYY-MM-DD, обчислення в UTC, щоб часовий пояс не зсував день.

export type Account = {
  id?: number; name?: string; kind?: string; balance: number | string; debt: number | string; active?: boolean;
  mono_account_id?: string | null; balance_updated_at?: string | null; debt_month?: string | null;
  min_spend?: number | string | null; min_spend_fee?: number | string | null;
  debt_months?: [string, number][]; // кошики боргу за місяцем (п. 12), ставить deriveAccounts
};
// Операція з привʼязкою до рахунку (для похідного балансу ручних рахунків)
// source: 'mono' | 'telegram' | 'manual' (потрібен лише для unassignedAdj: операції Monobank без рахунку не рахуємо)
// date: дата операції (YYYY-MM-DD), потрібна для порогу мінімальних витрат (без неї перші 10 знаків created_at)
// fixed_id: операція оплачує постійний платіж (п. 13), див. fixedPaid
export type AccTx = {
  account_id: number | null; type: string; amount: number | string; created_at: string; source?: string | null; date?: string | null;
  fixed_id?: number | string | null;
};
// Поріг мінімальних витрат рахунку за календарний місяць (DESIGN.md, п. 11)
export type MinSpendRow = { accountId: number; month: string; spent: number; min: number; fee: number; left: number; metOn?: string };
// variable: сума змінна, amount = середня оцінка (п. 13; на розрахунок не впливає)
export type Fixed = {
  id?: number | string; name: string; amount: number | string; day_of_month: number; type: string; active?: boolean;
  credit_ok?: boolean | null; variable?: boolean | null;
};
export type Credit = {
  name: string; monthly_amount: number | string; payment_day: number;
  start_year: number; start_month: number; total_payments: number; credit_ok?: boolean | null; source?: string | null;
};
export type SalaryCfg = { rate: number | string; split_day: number; advance_day: number; salary_day: number; savings_pct?: number | null };
// paid: ключі `${fixed_id}|YYYY-MM` оплачених постійних платежів (п. 13), будує fixedPaid з операцій
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

// п. 13: оплачені постійні платежі. Операція type = 'expense' з fixed_id і датою (без неї перші 10 знаків created_at)
// у місяці M закриває платіж місяця M (і раніше дати платежу). Ключі `${fixed_id}|YYYY-MM` для Snapshot.paid.
export function fixedPaid(txs: AccTx[]): string[] {
  const out = new Set<string>();
  for (const t of txs || []) {
    if (t.fixed_id == null || t.type !== 'expense') continue;
    out.add(String(t.fixed_id) + '|' + String(t.date || t.created_at || '').slice(0, 7));
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
      if (f.active === false) continue;
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
