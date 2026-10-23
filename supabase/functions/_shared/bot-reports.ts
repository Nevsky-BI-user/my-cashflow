import { ownCashSeries } from './own-history.ts';
// Звіти Telegram-бота з тієї самої проєкції, що й застосунок: Графік, Бюджет, Тиждень, Місяць, ранковий підсумок,
// нагадування про платежі на завтра і запис «Оплачено». Чисті функції без I/O: їх перевіряють node-тести.
import { financeProjection, lastPayout, payoutBudget, repayDate, type SalaryCfg } from './budget.ts';
import { budgetLeftLine, dailyPart, day, leftOrOver, money, untilPayoutLine } from './finance-message.ts';

type P = Record<string, any>;
export type Tx = {
  id?: number | string; account_id?: number | string | null; category_id?: number | string | null; fixed_id?: number | string | null; payment_due_date?: string | null; transfer_id?: string | null;
  credit_id?: number | string | null; type: string; amount?: number | string; date?: string | null; created_at?: string; source?: string | null;
  description?: string | null;
};

const DAY = 86400000;
export const plusDays = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * DAY).toISOString().slice(0, 10);
const lastDayOf = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate(); // m: 1..12
// Зсув на n календарних місяців з обрізанням дня до кінця місяця (31.10 мінус місяць = 30.09)
export function addMonths(d: string, n: number): string {
  const k = Number(d.slice(0, 4)) * 12 + Number(d.slice(5, 7)) - 1 + n, y = Math.floor(k / 12), m = k % 12 + 1;
  return `${y}-${String(m).padStart(2, '0')}-${String(Math.min(Number(d.slice(8, 10)), lastDayOf(y, m))).padStart(2, '0')}`;
}
// Понеділок тижня дати (тиждень пн-нд)
export const monday = (d: string) => plusDays(d, -((new Date(d + 'T00:00:00Z').getUTCDay() + 6) % 7));
const cents = (v: unknown) => Math.round((Number(v) || 0) * 100);
const txDate = (t: Tx) => String(t.date || t.created_at || '').slice(0, 10);
const uniq = (txs: Tx[]) => {
  const seen = new Set<string>();
  return (txs || []).filter((t) => {
    if (t.id == null) return true;
    const k = String(t.id);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
};
const pct = (part: number, whole: number) => whole > 0 ? Math.round(part * 100 / whole) : 0;
const MONTHS = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень'];
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
// «2 рази», «5 разів», «21 раз»
const times = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'раз' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'рази' : 'разів';

// Київський час: дата і година (0-23) для моменту now. Літній і зимовий час рахує Intl
export function kyivNow(now: Date): { date: string; hour: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)!.value;
  return { date: `${get('year')}-${get('month')}-${get('day')}`, hour: Number(get('hour')) % 24 };
}
export const isKyivHour = (now: Date, hour: number) => kyivNow(now).hour === hour;

// ---------- Баланс у часі (як графік «Гроші в часі» застосунку) ----------
// v153 доповнення 6 (власник: «і в боті графік має бути БАЛАНС»): лінія знову = баланс, як у v148-v149, і може бути нижче нуля.
// Баланс = власні мінус борг кредиток. Сьогодні: positiveOwnCents мінус creditDebtCents (плитка «Баланс»). Минуле: від сьогодні назад мінус
// підписані операції всіх рахунків (витрата з кредитки зменшує баланс, погашення як пара операцій його не змінює), як balancePast застосунку.
// Майбутнє: netCents рушія (власні мінус борг мінус нестача) на кінець дня плюс зсув positiveOwnCents мінус cashCents, як підказка «Баланс» застосунку.
export type Point = { date: string; cents: number };
export type BalanceSeries = {
  from: string; to: string; today: Point; past: Point[]; future: Point[]; min: Point; max: Point;
  payouts: (Point & { kind: string })[]; afterPayout: Point | null;
};

// Копія pastOwnSeries з index.html: значення на кінець кожного дня [fromIso; toIso], якір anchorCents на toIso
export function pastSeries(txs: Tx[], ids: string[], anchorCents: number, fromIso: string, toIso: string): Point[] {
  const own = new Set(ids.map(String));
  const byDay: Record<string, number> = {};
  for (const t of txs || []) {
    const d = String(t.date || '').slice(0, 10);
    if (d.length < 10 || d <= fromIso || d > toIso) continue;
    if (!own.has(t.account_id == null ? '' : String(t.account_id))) continue;
    byDay[d] = (byDay[d] || 0) + (t.type === 'income' ? 1 : -1) * cents(t.amount);
  }
  const out: Point[] = [];
  let v = anchorCents;
  for (let d = toIso, g = 0; d >= fromIso && g < 20000; d = plusDays(d, -1), g++) {
    out.push({ date: d, cents: v });
    v -= byDay[d] || 0;
  }
  return out.reverse();
}

// histAll застосунку: операції без рахунку лише ручні й створені після найранішої мітки балансу ручного рахунку;
// ownIds = власні (не кредитні) рахунки і '' (готівка без рахунку), allIds = усі активні рахунки і ''
export function histOf(txs: Tx[], accounts: P[]): { hist: Tx[]; ownIds: string[]; allIds: string[] } {
  const active = (accounts || []).filter((a) => a.active !== false);
  const stamps = active.filter((a) => !a.mono_account_id).map((a) => Date.parse(a.balance_updated_at || '')).filter(Number.isFinite);
  const stamp = stamps.length ? Math.min(...stamps) : null;
  const hist = uniq(txs).filter((t) => t.account_id != null || (stamp != null && t.source !== 'mono' && Date.parse(t.created_at || '') > stamp));
  return {
    hist,
    ownIds: active.filter((a) => a.kind !== 'credit').map((a) => String(a.id)).concat(['']),
    allIds: active.map((a) => String(a.id)).concat(['']),
  };
}

export function balanceSeries(pr: P, txs: Tx[], accounts: P[], today: string, opts: { firstOwnDate?: string | null; salary?: SalaryCfg | null } = {}): BalanceSeries {
  const s = pr.snapshot;
  const nowCents = s.positiveOwnCents - s.creditDebtCents, shift = s.positiveOwnCents - s.cashCents;
  const { hist, ownIds, allIds } = histOf(txs, accounts);
  let first: string | null = opts.firstOwnDate || null;
  for (const t of hist) {
    const d = String(t.date || '').slice(0, 10);
    if (d.length === 10 && d <= today && ownIds.includes(t.account_id == null ? '' : String(t.account_id)) && (!first || d < first)) first = d;
  }
  const lo = addMonths(today, -1), to = addMonths(today, 1);
  const from = !first ? today : lo > first ? lo : first;
  const past = pastSeries(hist, allIds, nowCents, from, today);
  const future = (pr.days || []).filter((d: P) => d.date > today && d.date <= to)
    .map((d: P) => ({ date: d.date, cents: d.netCents + shift }));
  const todayPt = { date: today, cents: nowCents };
  // Мінімум за весь видимий відрізок (минуле і прогноз), як «мін.» на графіку застосунку; за рівності перша дата
  let min: Point = past[0] || todayPt;
  let max = min;
  for (const p of [...past, ...future]) { if (p.cents < min.cents) min = p; if (p.cents > max.cents) max = p; }
  const at = (date: string) => past.find((p: Point) => p.date === date) || future.find((p: Point) => p.date === date) || null;
  const payouts: (Point & { kind: string })[] = [];
  // минулі виплати за конфігурацією зарплати (той самий зсув вихідних), майбутні з подій рушія
  if (opts.salary) {
    let d = today;
    for (let i = 0; i < 6; i++) {
      const p = lastPayout(opts.salary, d);
      if (!p || p.date < from) break;
      const pt = at(p.date);
      if (pt && p.date <= today && !payouts.some((x) => x.date === p.date)) payouts.push({ ...pt, kind: p.kind });
      d = plusDays(p.date, -1);
    }
  }
  for (const e of pr.events || []) {
    if (e.kind !== 'payout' || e.date <= today || e.date > to || payouts.some((x) => x.date === e.date)) continue;
    const pt = at(e.date);
    if (pt) payouts.push({ ...pt, kind: /аванс/i.test(e.name) ? 'advance' : 'salary' });
  }
  payouts.sort((a, b) => a.date < b.date ? -1 : 1);
  const next = pr.untilPayout?.end || null;
  const nd = next ? (pr.days || []).find((d: P) => d.date === next) : null;
  const afterPayout = nd ? { date: next, cents: nd.netCents + shift } : null;
  return { from, to, today: todayPt, past, future, min, max, payouts, afterPayout };
}

export function chartCaption(s: BalanceSeries): string {
  const parts = [`Баланс сьогодні ${money(s.today.cents)}`, `мінімум ${money(s.min.cents)} ${day(s.min.date)}`];
  if (s.afterPayout) parts.push(`після виплати ${day(s.afterPayout.date)}: ${money(s.afterPayout.cents)}`);
  return parts.join(' · ');
}

// ---------- Бюджет періоду (як плитка «Бюджет періоду» застосунку) ----------
// v151: копія periodBudgetStart і perDayOf з index.html (паритет перевіряє spec/bot-reports.test.cjs): бюджет на старт періоду тим самим
// розподілом виплати, що в рушії (payoutBudget): власні на виплату (власні напередодні + надходження дня старту), резерв дебетових
// обовʼязкових, обовʼязкових з кредитки (v153) і комісій періоду, у день погашення належне = борг напередодні мінус кредитні витрати місяця до старту;
// бюджет min(20 000, A), якщо A > 15 000, інакше 15 000. Доступно = бюджет мінус витрачено, на день = доступно / днів до кінця періоду.
const isoDiff = (a: string, b: string) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / DAY);
export function perDayOf(availCents: number, todayIso: string, startIso: string, endIso: string): number {
  const from = startIso > todayIso ? startIso : todayIso, days = isoDiff(from, endIso);
  return days > 0 ? Math.max(0, Math.round(availCents / days)) : 0;
}
export type PeriodBudget = {
  start: string; end: string; own: number; income: number; ownAt: number; reserve: number; debt: number; due: number; repayDay: boolean;
  repay: number; dueShort: number; manual: number | null; A: number; budget: number; days: number; daily: number; spent: number; avail: number;
};
export function periodBudgetStart(pr: P, fi: P, txs: Tx[], allIds: string[], ownIds: string[], today: string): PeriodBudget | null {
  const cp = pr && pr.currentPeriod;
  if (!cp || !cp.start || !cp.end || cp.start > today) return null;
  const s = cp.start, e = cp.end, prev = plusDays(s, -1);
  const sn = pr.snapshot;
  const all = pastSeries(txs, allIds, sn.positiveOwnCents - sn.creditDebtCents, prev, today)[0];
  const own = ownCashSeries(fi.accounts || [], txs, sn.accounts || [], sn.positiveOwnCents, prev, today)[0].cents, debt = own - all.cents;
  const ow = new Set(ownIds.map(String)), al = new Set(allIds.map(String));
  const key = (t: Tx) => t.account_id == null ? '' : String(t.account_id);
  const inc = (txs || []).reduce((n, t) => String(t.date || '').slice(0, 10) === s && t.transfer_id == null && t.type === 'income' && ow.has(key(t)) ? n + cents(t.amount) : n, 0);
  const at = financeProjection({ ...fi, transactions: (fi.transactions || []).filter((t: Tx) => String(t.date || '').slice(0, 10) < s) } as any, { asof: prev, through: e }) as P;
  // v154: резерв = лише білі (credit_ok=false) обовʼязкові й комісії, як резерв виплати в рушії; обовʼязкові з кредитки не резервуються; без платежів із картки за сценарієм
  const reserved = (x: P) => x.kind === 'fee' || (x.kind === 'mandatory' && x.creditEligible !== true && x.funding !== 'credit');
  const ownAt = own + inc;
  const reserve = Math.min(Math.max(0, ownAt), (at.events || []).filter((x: P) => x.date >= s && x.date < e && reserved(x)).reduce((n: number, x: P) => n + x.amountCents, 0));
  const m0 = s.slice(0, 7) + '-01', pm = addMonths(m0, -1).slice(0, 7), repayDay = repayDate(pm, '') === s;
  const crNew = (txs || []).reduce((n, t) => {
    const d = String(t.date || '').slice(0, 10), k = key(t);
    if (d < m0 || d >= s || ow.has(k) || !al.has(k)) return n;
    const v = cents(t.amount);
    return t.type === 'expense' ? n + v : t.type === 'income' ? n - v : n;
  }, 0);
  const dbt = Math.max(0, debt), due = repayDay ? Math.max(0, Math.min(dbt, dbt - crNew)) : 0;
  // v153: ручний бюджет періоду з налаштувань виплат (salary_config.budget_manual, гривні; null: авто), той самий, що бере рушій
  const monthly=cp.monthlyBudget;
  const bm = monthly?.covered?monthly.rawTargetCents/100:fi && fi.salary ? fi.salary.budget_manual : null;
  const manual = bm != null && bm !== '' && isFinite(Number(bm)) && Number(bm) >= 0 ? Math.round(Number(bm) * 100) : null;
  // v152: кожна виплата гасить борг максимум (як рушій), належне лише в день погашення; v153: погашення лише після резерву й бюджету
  const plan = payoutBudget(ownAt, reserve, dbt, due, true, manual), budget = plan.targetCents;
  const days = cp.periodDays || Math.max(1, isoDiff(s, e)), spent = cp.actualVariableCents || 0, avail = monthly?.covered ? cp.remainingTargetCents : budget - spent;
  return { start: s, end: e, own, income: inc, ownAt, reserve, debt: dbt, due, repayDay, repay: plan.repayCents, dueShort: plan.dueShortCents, manual, A: plan.availableCents, budget, days,
    daily: perDayOf(avail, today, s, e), spent, avail };
}

// v153: копія planSplit з index.html (паритет перевіряє spec/bot-reports.test.cjs): ділить суму в копійках між витратними категоріями,
// спершу абсолютні ліміти (limit_abs) за sort_order, решту за вагами budget_limit найбільшими остачами; без ваг решта в «Не розподілено».
export type PlanRow = { id: string; name: string; weight: number; limitAbsCents?: number; totalCents: number };
export function planSplit(total: number, cats: P[]): PlanRow[] {
  const cmp = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;
  const ct = (v: unknown) => Math.round((Number(v == null ? 0 : v) || 0) * 100);
  type Row = { id: string; name: string; weight: number; limitAbsCents?: number; wc: number };
  const ex = (cats || []).filter((c) => c.active !== false && c.type === 'expense');
  let rows: Row[] = ex.map((c): Row => c.limit_abs != null
    ? { id: String(c.id), name: c.name || '', weight: 0, limitAbsCents: Math.max(0, ct(c.limit_abs)), wc: 0 }
    : { id: String(c.id), name: c.name || '', weight: Math.max(0, ct(c.budget_limit != null ? c.budget_limit : c.limit)) / 100, wc: Math.max(0, ct(c.budget_limit != null ? c.budget_limit : c.limit)) })
    .sort((a, b) => cmp(a.id, b.id));
  const ord = ex.filter((c) => c.limit_abs != null).map((c) => ({ id: String(c.id), o: c.sort_order == null ? null : Number(c.sort_order) }))
    .sort((a, b) => a.o === b.o ? cmp(a.id, b.id) : a.o == null ? 1 : b.o == null ? -1 : a.o - b.o).map((o) => rows.findIndex((r) => r.id === o.id));
  const un: Row = { id: 'unallocated', name: 'Не розподілено', weight: 1, wc: 100 };
  if (!ord.length && !rows.some((r) => r.wc > 0)) rows = [un];
  const alloc = (t: number, ws: number[]): number[] => {
    if (!t) return ws.map(() => 0);
    const den = ws.reduce((s, v) => s + BigInt(v), BigInt(0));
    const rs = ws.map((w, i) => ({ i, v: Number(BigInt(t) * BigInt(w) / den), r: BigInt(t) * BigInt(w) % den }));
    const left = t - rs.reduce((s, r) => s + r.v, 0);
    rs.sort((a, b) => a.r === b.r ? a.i - b.i : a.r > b.r ? -1 : 1);
    for (let i = 0; i < left; i++) rs[i].v++;
    rs.sort((a, b) => a.i - b.i);
    return rs.map((r) => r.v);
  };
  let totals: number[];
  if (!ord.length) totals = alloc(total, rows.map((r) => r.wc));
  else {
    totals = rows.map(() => 0);
    let left = total;
    ord.forEach((i) => { const n = Math.min(rows[i].limitAbsCents as number, left); totals[i] = n; left -= n; });
    const ws = rows.map((r) => r.limitAbsCents != null ? 0 : r.wc);
    if (ws.some((w) => w > 0)) alloc(left, ws).forEach((n, i) => { totals[i] += n; });
    else if (left > 0) { rows = rows.concat([un]); totals = totals.concat([left]); }
  }
  return rows.map((r, i) => { const o: PlanRow = { id: r.id, name: r.name, weight: r.weight, totalCents: 0 }; if (r.limitAbsCents != null) o.limitAbsCents = r.limitAbsCents; o.totalCents = totals[i]; return o; });
}

// Бюджет = periodBudgetStart (як плитка застосунку), витрачено = actualVariableCents, на день = perDayOf.
// Категорії: факт змінних витрат з початку періоду (без fixed_id і credit_id), план = planSplit від того самого бюджету (v153, як застосунок):
// сума планів = бюджету періоду.
export type BudgetRow = { id: string; name: string; color?: string | null; fact: number; plan: number; over: boolean; near: boolean; noPlan?: boolean };
export type BudgetModel = {
  start: string; end: string; poolCents: number; spentCents: number; leftCents: number; dailyCents: number; leftDays: number;
  rows: BudgetRow[]; topOver: BudgetRow[];
};

export function budgetModel(pr: P, txs: Tx[], cats: P[], today: string, fi: P, accounts: P[]): BudgetModel | null {
  const cp = pr.currentPeriod, q = (pr.periods || []).find((p: P) => p.basis === 'current');
  if (!cp || !q) return null;
  const h = histOf(txs, accounts), pb = periodBudgetStart(pr, fi, h.hist, h.allIds, h.ownIds, today);
  if (!pb) return null;
  const exp = (cats || []).filter((c) => !c.is_income && c.type !== 'income');
  const fact: Record<string, number> = {};
  let none = 0;
  for (const t of uniq(txs)) {
    const d = txDate(t);
    if (t.type !== 'expense' || t.transfer_id != null || t.fixed_id != null || t.credit_id != null || d < cp.start || d > today) continue;
    const c = t.category_id != null ? exp.find((x) => String(x.id) === String(t.category_id)) : null;
    if (c) fact[String(c.id)] = (fact[String(c.id)] || 0) + cents(t.amount);
    else none += cents(t.amount);
  }
  const plan: Record<string, P> = {};
  const monthly=cp.monthlyBudget;
  const planned=monthly?.covered?[...monthly.rawCategories.map((c:any)=>({...c,name:cats.find(x=>String(x.id)===c.id)?.name||'Категорія '+c.id})),{id:'unallocated',name:'Не розподілено',totalCents:monthly.rawUnallocatedCents}]:planSplit(pb.budget,cats);
  for (const c of planned) plan[String(c.id)] = c;
  const rows: BudgetRow[] = [];
  const add = (id: string, name: string, color: string | null, f: number, p: number, noPlan = false) => {
    if (f <= 0 && p <= 0) return;
    const over = !noPlan && f > p, near = !noPlan && !over && p > 0 && f * 10 >= p * 9;
    rows.push({ id, name, color, fact: f, plan: p, over, near, ...(noPlan ? { noPlan } : {}) });
  };
  for (const c of exp) add(String(c.id), String(c.name || ''), c.color || null, fact[String(c.id)] || 0, plan[String(c.id)]?.totalCents || 0);
  for(const id of Object.keys(plan))if(id!=='unallocated'&&!exp.some(c=>String(c.id)===id))add(id,plan[id].name||'Категорія '+id,null,fact[id]||0,plan[id].totalCents||0);
  if (plan.unallocated) add('unallocated', plan.unallocated.name || 'Не розподілено', null, 0, plan.unallocated.totalCents || 0);
  if (none > 0) add('__none', 'Без категорії', null, none, 0, true);
  rows.sort((a, b) => b.fact - a.fact || b.plan - a.plan || (a.id < b.id ? -1 : 1));
  const topOver = rows.filter((r) => r.over).sort((a, b) => (b.fact - b.plan) - (a.fact - a.plan)).slice(0, 3);
  return {
    start: cp.start, end: cp.end, poolCents: pb.budget, spentCents: pb.spent,
    leftCents: pb.avail, dailyCents: pb.daily, leftDays: Math.max(0, isoDiff(cp.start > today ? cp.start : today, cp.end)), rows, topOver,
  };
}

export function formatBudget(m: BudgetModel | null): string {
  if (!m) return 'Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.';
  const lines = [`📊 Бюджет періоду ${day(m.start)}-${day(m.end)}`,
    `Бюджет: ${money(m.poolCents)} · витрачено ${money(m.spentCents)} (${pct(m.spentCents, m.poolCents)}%) · ${leftOrOver(m.leftCents)}`];
  if (m.leftDays > 0 && m.leftCents >= 0) lines.push(`До ${day(m.end)}: ${money(m.dailyCents)}/день (${m.leftDays} дн.)`);
  return lines.join('\n');
}

// ---------- Тиждень: події 7 днів з рушія ----------
export type WeekModel = {
  from: string; to: string; events: { date: string; name: string; kind: string; cents: number; conditional: boolean }[];
  variableCents: number; endBalanceCents: number | null; endCashCents: number | null; gap: { date: string; cents: number } | null;
  days?: { date: string; spendCents: number; balanceCents: number }[];
};
const KINDS = ['payout', 'income', 'mandatory', 'fee', 'repay'];
// v151: підпис погашення як у застосунку (repayKind/repayLabel в index.html): «Погашення Приват · обовʼязкове» (дата = обовʼязкова дата
// кошика), «· додатково» (раніше), «· прострочене» (пізніше); банк рахунку зі знімка рушія за accountId
const BANK_SHORT: Record<string, string> = { oschad: 'Ощад', privat: 'Приват', mono: 'Mono', cash: 'Готівка' };
export function repayKind(e: P): string {
  const p = e.plannedRepaymentDate || e.date;
  return e.date < p ? 'додатково' : e.date > p ? 'прострочене' : 'обовʼязкове';
}
export function repayLabel(pr: P, e: P): string {
  const a = (pr?.snapshot?.accounts || []).find((x: P) => String(x.id) === String(e.accountId));
  return `Погашення ${a ? (BANK_SHORT[a.bank] || a.name || 'Рахунок') : (e.name || 'кредитки')} · ${repayKind(e)}`;
}

export function weekModel(pr: P, today: string): WeekModel {
  const to = plusDays(today, 6), s = pr.snapshot, shift = s.positiveOwnCents - s.cashCents;
  const events = (pr.events || []).filter((e: P) => e.date >= today && e.date <= to && KINDS.includes(e.kind))
    .map((e: P) => ({
      date: e.date, kind: e.kind, conditional: e.certainty === 'conditional', cents: e.cashDeltaCents,
      name: e.kind === 'repay' ? repayLabel(pr, e) : e.name,
    }));
  const days = (pr.days || []).filter((d: P) => d.date >= today && d.date <= to);
  const last = days[days.length - 1];
  // v150: власні не мінус; попередження про нестачу (платіж без права на кредит, який не покрито)
  const neg = days.find((d: P) => (d.arrearsCents || 0) > 0);
  return {
    from: today, to, events, variableCents: days.reduce((n: number, d: P) => n + (d.variableCents || 0), 0),
    endBalanceCents: last ? last.netCents + shift : null, endCashCents: last ? last.closingCashCents : null,
    gap: neg ? { date: neg.date, cents: neg.arrearsCents } : null,
    // Кожен день: усі витрати дня (щоденні за бюджетом + обовʼязкові платежі й комісії; погашення кредитки це переказ, не витрата)
    // і баланс на кінець дня (сьогодні поточний, далі прогноз) за формулою застосунку
    days: days.map((d: P) => ({
      date: d.date, balanceCents: d.netCents + shift,
      spendCents: (d.variableCents || 0) + events.filter((e: { date: string; kind: string; cents: number }) => e.date === d.date && (e.kind === 'mandatory' || e.kind === 'fee') && e.cents < 0)
        .reduce((n: number, e: { cents: number }) => n - e.cents, 0),
    })),
  };
}

const signed = (c: number) => (c > 0 ? '+' : c < 0 ? '-' : '') + money(Math.abs(c));

const WD = ['Нд', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// Гривні без копійок для таблиці; пробіл тисяч звичайний, щоб моноширинні колонки рівнялись
const uah = (c: number) => (c < 0 ? '-' : '') + String(Math.round(Math.abs(c) / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

// Таблиця дня у <pre>: день тижня і дата, щоденні витрати, баланс на кінець дня; сьогодні позначене ▸
export function weekTable(m: WeekModel): string {
  const rows = (m.days || []).map((d) => {
    const wd = WD[new Date(d.date + 'T00:00:00Z').getUTCDay()];
    return `${d.date === m.from ? '▸' : ' '}${wd} ${day(d.date)} ${uah(d.spendCents).padStart(7)} ${uah(d.balanceCents).padStart(9)}`;
  });
  if (!rows.length) return '';
  // Пробіли в кінці шапки: кнопка копіювання Telegram лягає на них, а не на «Баланс»
  return '<pre>' + [' День     Витрати    Баланс    ', ...rows].join('\n') + '</pre>';
}

// HTML (parse_mode HTML): таблиця днів, далі події тижня
export function formatWeek(m: WeekModel): string {
  const lines = [`📅 Тиждень ${day(m.from)}-${day(m.to)}`];
  const table = weekTable(m);
  if (table) lines.push('', 'Баланс на кінець дня: сьогодні поточний, далі прогноз, ₴', table);
  // Під таблицею: разом витрати тижня з розписом (щоденні + кожен платіж), далі інші події (виплати, погашення, доходи)
  const isSpend = (e: { kind: string; cents: number }) => (e.kind === 'mandatory' || e.kind === 'fee') && e.cents < 0;
  if (m.days?.length) {
    const total = m.days.reduce((n, d) => n + d.spendCents, 0);
    const spends = m.events.filter(isSpend);
    lines.push('', `Разом витрати за тиждень: ${money(total)}`);
    lines.push(`· щоденні витрати: ${money(total + spends.reduce((n, e) => n + e.cents, 0))}`);
    for (const e of spends) lines.push(`· ${day(e.date)} ${esc(e.name)}: ${money(-e.cents)}${e.conditional ? ' (умовно)' : ''}`);
  }
  const other = m.events.filter((e) => !isSpend(e));
  if (other.length) {
    lines.push('');
    for (const e of other) lines.push(`${day(e.date)} · ${esc(e.name)}: ${signed(e.cents)}${e.conditional ? ' (умовно)' : ''}`);
  }
  return lines.join('\n');
}

// ---------- Місяць: поточний календарний місяць проти того самого відрізка минулого ----------
// Погашення кредитки (дохід на кредитний рахунок і парна витрата з власного рахунку тієї ж суми ±1 день) не рахуються
// ні витратою, ні доходом: це переказ між своїми рахунками.
export type MonthCat = { name: string; cur: number; prev: number };
export type MonthModel = {
  curFrom: string; curTo: string; prevFrom: string; prevTo: string; prevFullTo: string; days: number;
  curSpent: number; prevSpent: number; prevFullSpent: number; curIncome: number; prevIncome: number;
  cats: MonthCat[]; places: { name: string; cents: number; count: number }[];
};

export function monthModel(txs: Tx[], cats: P[], accounts: P[], today: string): MonthModel {
  const y = Number(today.slice(0, 4)), m = Number(today.slice(5, 7)), d = Number(today.slice(8, 10));
  const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
  const pl = lastDayOf(py, pm), pk = `${py}-${String(pm).padStart(2, '0')}`;
  const curFrom = today.slice(0, 7) + '-01', prevFrom = pk + '-01';
  const prevTo = `${pk}-${String(Math.min(d, pl)).padStart(2, '0')}`, prevFullTo = `${pk}-${String(pl).padStart(2, '0')}`;
  const list = uniq(txs).filter((t) => t.transfer_id == null && txDate(t) >= prevFrom && txDate(t) <= today);
  const creditIds = new Set((accounts || []).filter((a) => a.kind === 'credit').map((a) => String(a.id)));
  const skip = new Set<Tx>();
  for (const inc of list.filter((t) => t.type === 'income' && t.account_id != null && creditIds.has(String(t.account_id)))) {
    skip.add(inc);
    const pair = list.find((t) => !skip.has(t) && t.type === 'expense' && !(t.account_id != null && creditIds.has(String(t.account_id))) &&
      cents(t.amount) === cents(inc.amount) && Math.abs(Date.parse(txDate(t)) - Date.parse(txDate(inc))) <= DAY);
    if (pair) skip.add(pair);
  }
  const names = new Map((cats || []).map((c) => [String(c.id), String(c.name || '')]));
  const by: Record<string, MonthCat> = {};
  const places: Record<string, { name: string; cents: number; count: number }> = {};
  let curSpent = 0, prevSpent = 0, prevFullSpent = 0, curIncome = 0, prevIncome = 0;
  for (const t of list) {
    if (skip.has(t)) continue;
    const dt = txDate(t), c = cents(t.amount), cur = dt >= curFrom, prev = dt >= prevFrom && dt <= prevTo, prevFull = dt >= prevFrom && dt <= prevFullTo;
    if (t.type === 'income') {
      if (cur) curIncome += c;
      else if (prev) prevIncome += c;
      continue;
    }
    if (t.type !== 'expense') continue;
    if (prevFull && !cur) prevFullSpent += c;
    if (!cur && !prev) continue;
    const name = (t.category_id != null && names.get(String(t.category_id))) || 'Без категорії';
    const row = by[name] = by[name] || { name, cur: 0, prev: 0 };
    if (cur) {
      row.cur += c;
      curSpent += c;
      const desc = String(t.description || '').trim();
      if (desc) {
        const key = desc.toLowerCase();
        const p = places[key] = places[key] || { name: desc, cents: 0, count: 0 };
        p.cents += c;
        p.count++;
      }
    } else {
      row.prev += c;
      prevSpent += c;
    }
  }
  return {
    curFrom, curTo: today, prevFrom, prevTo, prevFullTo, days: d, curSpent, prevSpent, prevFullSpent, curIncome, prevIncome,
    cats: Object.values(by).sort((a, b) => b.cur - a.cur || b.prev - a.prev || (a.name < b.name ? -1 : 1)),
    places: Object.values(places).sort((a, b) => b.cents - a.cents || (a.name < b.name ? -1 : 1)).slice(0, 5),
  };
}

// Дельта: стрілка, сума і відсоток від минулого; без минулого: «нова»
export function delta(cur: number, prev: number): string {
  if (cur === prev) return '= 0 ₴';
  const arrow = cur > prev ? '↑' : '↓';
  if (prev <= 0) return `${arrow} ${money(Math.abs(cur - prev))} (нова)`;
  const p = Math.round((cur - prev) * 100 / prev);
  return `${arrow} ${money(Math.abs(cur - prev))} (${p > 0 ? '+' : ''}${p}%)`;
}

// Зміна у відсотках для таблиці: без минулого «нова», без зміни «0%»
export function pctChange(cur: number, prev: number): string {
  if (cur === prev) return '0%';
  if (prev <= 0) return 'нова';
  const p = Math.round((cur - prev) * 100 / prev);
  return `${p > 0 ? '+' : ''}${p}%`;
}

const MON_SHORT = ['січ.', 'лют.', 'бер.', 'квіт.', 'трав.', 'черв.', 'лип.', 'серп.', 'вер.', 'жовт.', 'лист.', 'груд.'];
const NAME_W = 16;

// Таблиця місяця (<pre>): підсумки, далі категорії; колонки: цей місяць, минулий за той самий відрізок, зміна.
// Назва довша за колонку не обрізається: стоїть окремим рядком, числа рядком нижче.
export function monthTable(m: MonthModel): string {
  const prevDays = Number(m.prevTo.slice(8, 10));
  type Row = [string, number, number] | null;
  const rows: Row[] = [
    ['Витрати', m.curSpent, m.prevSpent],
    ['На день', Math.round(m.curSpent / Math.max(1, m.days)), Math.round(m.prevSpent / Math.max(1, prevDays))],
    ['Доходи', m.curIncome, m.prevIncome],
  ];
  if (m.cats.length) rows.push(null, ...m.cats.map((c): Row => [c.name, c.cur, c.prev]));
  const cells = rows.map((r) => r && [r[0], uah(r[1]), uah(r[2]), pctChange(r[1], r[2])]);
  const head = ['', MON_SHORT[Number(m.curFrom.slice(5, 7)) - 1], MON_SHORT[Number(m.prevFrom.slice(5, 7)) - 1], 'зміна'];
  const all = [head, ...cells.filter((r): r is string[] => !!r)];
  const w0 = Math.min(NAME_W, Math.max(...all.map((r) => r[0].length)));
  const w = [1, 2, 3].map((i) => Math.max(...all.map((r) => r[i].length)));
  const line = (r: string[]) => r[0].padEnd(w0) + ' ' + r.slice(1).map((v, i) => v.padStart(w[i])).join('  ');
  // Пробіли в кінці шапки: кнопка копіювання Telegram лягає на них, а не на «зміна»
  const out = [line(head) + '    '];
  for (const r of cells) {
    if (!r) out.push('', 'За категоріями');
    else if (r[0].length > w0) out.push(r[0], line(['', ...r.slice(1)]));
    else out.push(line(r));
  }
  return '<pre>' + esc(out.join('\n')) + '</pre>';
}

// HTML (parse_mode HTML): таблиця місяця, далі минулий місяць повністю і топ-5 місць
export function formatMonth(m: MonthModel): string {
  const curName = cap(MONTHS[Number(m.curFrom.slice(5, 7)) - 1]), prevName = MONTHS[Number(m.prevFrom.slice(5, 7)) - 1];
  const lines = [`🔍 ${curName}: ${day(m.curFrom)}-${day(m.curTo)} проти ${day(m.prevFrom)}-${day(m.prevTo)}`, '',
    'Суми в ₴, зміна до того самого відрізка минулого місяця', monthTable(m), '',
    `${cap(prevName)} повністю: витрати ${money(m.prevFullSpent)}`];
  if (m.places.length) {
    lines.push('', 'Топ-5 місць:');
    m.places.forEach((p, i) => lines.push(`${i + 1}. ${esc(p.name)}: ${money(p.cents)}` + (p.count > 1 ? ` (${p.count} ${times(p.count)})` : '')));
  }
  return lines.join('\n');
}

// ---------- Ранковий підсумок ----------
// Сьогоднішні розстрочки рушій уже вважає сплаченими за планом (дата <= asof), тож для «що спишеться сьогодні»
// беремо їх із графіка розстрочок, якщо місяць ще не оплачено фактом.
export function installmentsOn(credits: P[], txs: Tx[], date: string): { name: string; cents: number }[] {
  const y = Number(date.slice(0, 4)), m = Number(date.slice(5, 7)), k = y * 12 + m - 1, last = lastDayOf(y, m);
  const paid = new Set(uniq(txs).filter((t) => t.type === 'expense' && t.credit_id != null).map((t) => String(t.credit_id) + '|' + String(t.payment_due_date ?? txDate(t)).slice(0, 7)));
  return (credits || []).filter((c) => {
    const first = Number(c.start_year) * 12 + Number(c.start_month);
    return k >= first && k < first + Number(c.total_payments) && Math.min(Number(c.payment_day), last) === Number(date.slice(8, 10)) &&
      !paid.has(String(c.id) + '|' + date.slice(0, 7));
  }).map((c) => ({ name: `${c.name} (розстрочка)`, cents: cents(c.monthly_amount) }));
}

// Нагадуємо повну суму зобовʼязання, а не лише частину, покриту власними коштами.
// Сценарій може розділити одну подію на власне й кредитне фінансування.
function paymentDues(pr: P, date: string): P[] {
  const grouped = new Map<string, P>();
  for (const [i, e] of (pr.events || []).entries()) {
    if (e.date !== date || !['mandatory', 'fee', 'repay'].includes(e.kind)) continue;
    const key = e.occurrenceId || e.id || `event:${i}`;
    const prev = grouped.get(key);
    if (prev) prev.amountCents += e.amountCents;
    else grouped.set(key, { ...e });
  }
  return [...grouped.values()];
}

const dueOn = (pr: P, date: string) => paymentDues(pr, date)
  .map((e: P) => ({ name: e.kind === 'repay' ? repayLabel(pr, e) : e.name + (e.certainty === 'conditional' ? ' (умовно)' : ''), cents: e.amountCents }));

// v186: budget = budgetModel (залишок бюджету періоду на день, як звіт «Бюджет»); власні мінус обовʼязкові лише як попередження про нестачу
export function formatDigest(pr: P, credits: P[], txs: Tx[], today: string, budget: BudgetModel | null = null): string {
  const s = pr.snapshot, u = pr.untilPayout, tomorrow = plusDays(today, 1);
  const lines = [`☀️ Доброго ранку! ${day(today)}`, `Баланс: ${money(s.positiveOwnCents - s.creditDebtCents)}`];
  if(pr.currentPeriod?.monthlyBudget?.covered)lines.push('Бюджет періоду: '+money(pr.currentPeriod.targetCents)+' · '+((pr.currentPeriod.overrunCents||0)>0?leftOrOver(-pr.currentPeriod.overrunCents):leftOrOver(pr.currentPeriod.remainingTargetCents,'залишок'))+(budget&&(pr.currentPeriod.overrunCents||0)<=0?dailyPart(budget):'')+(pr.currentPeriod.monthlyBudget.estimated?' (прогноз за останнім місячним планом)':''));
  else if (budget) lines.push(budgetLeftLine(budget));
  const short = u && u.days > 0 ? untilPayoutLine(u) : null;
  if (short) lines.push(short);
  const list = (title: string, empty: string, rows: { name: string; cents: number }[]) => rows.length
    ? [`${title}: ${money(rows.reduce((n, r) => n + r.cents, 0))}`, ...rows.map((r) => `· ${r.name}: ${money(r.cents)}`)]
    : [empty];
  lines.push('', ...list('Заплановано на сьогодні', 'На сьогодні запланованих списань немає.', [...installmentsOn(credits, txs, today), ...dueOn(pr, today)]));
  lines.push(...list(`Заплановано на завтра, ${day(tomorrow)}`, 'На завтра запланованих платежів немає.', dueOn(pr, tomorrow)));
  return lines.join('\n');
}

// ---------- Нагадування на завтра і «Оплачено» ----------
// kind: f постійний платіж, c розстрочка, r погашення кредитки. callback_data несе лише тип, id і дату події.
export type DueItem = { kind: 'f' | 'c' | 'r'; id: string; name: string; cents: number; date: string; bank: string | null; button: boolean; callback: string | null };

export function dueTomorrow(pr: P, fixed: P[], credits: P[], today: string): DueItem[] {
  const tomorrow = plusDays(today, 1), out: DueItem[] = [];
  for (const e of paymentDues(pr, tomorrow)) {
    let kind: DueItem['kind'] | null = null, id = '', bank: string | null = null, name = e.name;
    const fx = /^fixed:(.+?):\d{4}-\d{2}(?:-\d{2})?$/.exec(e.occurrenceId || ''), cr = /^installment:(.+):\d{4}-\d{2}$/.exec(e.occurrenceId || '');
    if (e.kind === 'mandatory' && fx) {
      const f = (fixed || []).find((x) => String(x.id) === fx[1]);
      kind = 'f';
      id = fx[1];
      bank = f?.bank ?? null;
    } else if (e.kind === 'mandatory' && cr) {
      const c = (credits || []).find((x) => String(x.id) === cr[1]);
      kind = 'c';
      id = cr[1];
      bank = c?.source ?? null;
    } else if (e.kind === 'repay') {
      kind = 'r';
      id = String(e.accountId);
      name = repayLabel(pr, e);
    }
    if (!kind) continue;
    // Кнопки немає для погашення (у застосунку воно вноситься зміною боргу рахунку) і для списань Monobank (операція прийде з банку)
    const button = kind !== 'r' && bank !== 'mono';
    out.push({ kind, id, name, cents: e.amountCents, date: e.date, bank, button, callback: button ? `pd:${kind}:${id}:${e.date}` : null });
  }
  return out;
}

export function formatReminder(it: DueItem): string {
  const head = `⏰ Завтра, ${day(it.date)}: ${it.name}, ${money(it.cents)}`;
  if (it.kind === 'r') return head + '\nПогашення вноситься в застосунку: «Погасити» на вкладці Кредити.';
  if (it.bank === 'mono') return head + '\nСпишеться з Monobank, операція прийде сама.';
  return head + '\nПісля оплати натисніть «✅ Оплачено».';
}

export const parsePaidCallback = (data: string) => {
  const m = /^pd:([fc]):(\d+):(\d{4}-\d{2}-\d{2})$/.exec(String(data || ''));
  return m ? { kind: m[1] as 'f' | 'c', id: m[2], date: m[3] } : null;
};

// Межі [від, до) періоду оплати: місяць дати або тиждень пн-нд (як paidRange у боті і paid у рушії)
export function payRange(weekly: boolean, date: string): [string, string] {
  if (weekly) {
    const mon = monday(date);
    return [mon, plusDays(mon, 7)];
  }
  const y = Number(date.slice(0, 4)), m = Number(date.slice(5, 7));
  return [date.slice(0, 7) + '-01', m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`];
}
// Ключ оплати для source_id: однаковий для обох членів сімʼї, тож унікальний індекс не дасть другого запису
export const paySourceId = (kind: 'f' | 'c', id: string, date: string, weekly: boolean) =>
  `tgpaid:${kind}:${id}:` + (weekly ? 'W' + monday(date) : date.slice(0, 7));
// Дата запису: сьогодні, якщо сьогодні той самий місяць (тиждень) події; інакше дата події, щоб закрити саме її період
export function payDate(today: string, eventDate: string, weekly: boolean): string {
  const [a, b] = payRange(weekly, eventDate);
  return today >= a && today < b ? today : eventDate;
}

// Категорія оплати як у застосунку (fixedCat / creditCat): як у попередній оплаті цього платежу, інакше за назвою, інакше «Інше»
export function payCategory(kind: 'f' | 'c', item: P, history: Tx[], cats: P[]): number | null {
  const act = (cats || []).filter((c) => !c.is_income && c.type !== 'income');
  const has = (id: unknown) => act.some((c) => String(c.id) === String(id));
  const prev = (history || []).filter((t) => String(kind === 'f' ? t.fixed_id : t.credit_id) === String(item.id) && t.category_id != null && has(t.category_id))
    .sort((a, b) => String(a.date) < String(b.date) ? 1 : -1)[0];
  if (prev) return Number(prev.category_id);
  const lc = (v: unknown) => String(v || '').toLowerCase();
  const by = (fn: (c: P) => boolean) => {
    const c = act.find(fn);
    return c ? Number(c.id) : null;
  };
  if (kind === 'c') return by((c) => /розстроч|кредит/.test(lc(c.name))) ?? by((c) => lc(c.name) === 'інше');
  return by((c) => /^постійн/.test(lc(c.name))) ??
    by((c) => {
      const cn = lc(c.name);
      return cn.length >= 5 && lc(item.name).split(/\s+/).some((w) => w.length >= 5 && w.slice(0, 5) === cn.slice(0, 5));
    }) ?? by((c) => lc(c.name) === 'інше');
}

// Рішення для кнопки «Оплачено»: період уже закритий будь-якою витратою з привʼязкою, або рядок для вставки
export type PayRow = {
  amount: number; type: 'expense'; description: string; source: 'telegram'; source_id: string; date: string;
  fixed_id: number | null; credit_id: number | null; payment_due_date: string; category_id: number | null;
};
export type PayPlan = { status: 'already'; date: string } | { status: 'insert'; row: PayRow };
export function payPlan(o: { kind: 'f' | 'c'; item: P; eventDate: string; today: string; history: Tx[]; cats: P[] }): PayPlan {
  const weekly = o.kind === 'f' && o.item.period === 'week';
  const [a, b] = payRange(weekly, o.eventDate);
  const done = (o.history || []).find((t) => t.type === 'expense' && String(o.kind === 'f' ? t.fixed_id : t.credit_id) === String(o.item.id) &&
    String(t.payment_due_date ?? txDate(t)) >= a && String(t.payment_due_date ?? txDate(t)) < b);
  if (done) return { status: 'already', date: txDate(done) };
  const amount = Number(o.kind === 'f' ? o.item.amount : o.item.monthly_amount) || 0;
  return {
    status: 'insert', row: {
      amount, type: 'expense', description: String(o.item.name || ''), source: 'telegram',
      source_id: paySourceId(o.kind, String(o.item.id), o.eventDate, weekly), date: o.today, payment_due_date: o.eventDate,
      fixed_id: o.kind === 'f' ? Number(o.item.id) : null, credit_id: o.kind === 'c' ? Number(o.item.id) : null,
      category_id: payCategory(o.kind, o.item, o.history, o.cats),
    },
  };
}
