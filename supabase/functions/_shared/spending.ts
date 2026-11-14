// Витрати й доходи за довільний період для питань до бота («скільки витратили на продукти в жовтні»).
// Правила ті самі, що у звіті «Місяць» (monthModel): перекази не рахуються, погашення кредитки (дохід на кредитний рахунок
// і парна витрата з власного тієї ж суми ±1 день) не витрата і не дохід, категорії з розподілом чека за частинами.
// Операція без категорії лишається «Без категорії»: пошук за описом не дописує їй категорію.
// Речення з числами складає код; модель лише обирає період, категорію чи слово пошуку.
import { expenseCategoryParts } from './expense-allocations.ts';
import { money, day } from './finance-message.ts';

type P = Record<string, any>;
export type SpendQuery = { type: 'expense' | 'income'; from: string; to: string; category?: string | null; search?: string | null };
export type SpendCat = { name: string; cents: number; count: number };
export type SpendModel = {
  type: 'expense' | 'income'; from: string; to: string; totalCents: number; count: number; byCategory: SpendCat[];
  category: string | null; search: string | null;
};

const DAY = 86400000;
const cents = (v: unknown) => Math.round((Number(v) || 0) * 100);
const txDate = (t: P) => String(t.date || t.created_at || '').slice(0, 10);
export const shiftDay = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * DAY).toISOString().slice(0, 10);
// Ключ для зіставлення назв: апостроф будь-якого виду однаковий («Здоров'я» = «Здоровʼя»), регістр і пробіли не важать
export const nameKey = (s: unknown) => String(s ?? '').normalize('NFKC').replace(/[ʼ’'`]/g, 'ʼ').toLocaleLowerCase('uk-UA').replace(/\s+/g, ' ').trim();
const norm = nameKey;
export const UNCATEGORIZED = 'Без категорії';

function uniq(txs: P[]): P[] {
  const seen = new Set<string>();
  return (txs || []).filter((t) => {
    if (t.id == null) return true;
    const k = String(t.id);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

// Пари погашення кредитки, як у monthModel: перебір у порядку списку, кожна витрата в парі лише раз
function repaymentSkips(list: P[], accounts: P[]): Set<P> {
  const creditIds = new Set((accounts || []).filter((a) => a.kind === 'credit').map((a) => String(a.id)));
  const skip = new Set<P>();
  for (const inc of list.filter((t) => t.type === 'income' && t.account_id != null && creditIds.has(String(t.account_id)))) {
    skip.add(inc);
    const pair = list.find((t) => !skip.has(t) && t.type === 'expense' && !(t.account_id != null && creditIds.has(String(t.account_id))) &&
      cents(t.amount) === cents(inc.amount) && Math.abs(Date.parse(txDate(t)) - Date.parse(txDate(inc))) <= DAY);
    if (pair) skip.add(pair);
  }
  return skip;
}

// Операції завантажуються на день ширше з обох боків: пара погашення може лежати по різні боки межі періоду
export function spendingModel(txs: P[], cats: P[], accounts: P[], q: SpendQuery): SpendModel {
  const list = uniq(txs).filter((t) => t.transfer_id == null && txDate(t) >= shiftDay(q.from, -1) && txDate(t) <= shiftDay(q.to, 1));
  const skip = repaymentSkips(list, accounts);
  const names = new Map((cats || []).map((c) => [String(c.id), String(c.name || '')]));
  const wantCat = q.category ? norm(q.category) : null, needle = q.search ? norm(q.search) : null;
  const by: Record<string, SpendCat> = {};
  let totalCents = 0, count = 0;
  for (const t of list) {
    if (skip.has(t) || t.type !== q.type) continue;
    const dt = txDate(t);
    if (dt < q.from || dt > q.to) continue;
    if (needle && !norm(t.description).includes(needle)) continue;
    let txCents = 0;
    for (const part of expenseCategoryParts(t, cats)) {
      const name = (part.category_id != null && names.get(String(part.category_id))) || UNCATEGORIZED;
      if (wantCat && norm(name) !== wantCat) continue;
      const row = by[name] = by[name] || { name, cents: 0, count: 0 };
      row.cents += part.amount_cents;
      row.count++;
      txCents += part.amount_cents;
    }
    if (wantCat && !txCents) continue;
    totalCents += wantCat ? txCents : cents(t.amount);
    count++;
  }
  if (!Number.isSafeInteger(totalCents)) throw new RangeError('spending total exceeds safe cents');
  return {
    type: q.type, from: q.from, to: q.to, totalCents, count,
    byCategory: Object.values(by).sort((a, b) => b.cents - a.cents || (a.name < b.name ? -1 : 1)),
    category: q.category || null, search: q.search || null,
  };
}

const MONTHS_ACC = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень'];
const lastDay = (y: number, m: number) => new Date(Date.UTC(y, m, 0)).getUTCDate();
const ops = (n: number) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? 'операція' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'операції' : 'операцій'}`;

// Підпис періоду: повний календарний місяць словом, інакше дати (неповний місяць видно з дат: «01.11-14.11»)
export function periodLabel(from: string, to: string, today: string): string {
  const y = Number(from.slice(0, 4)), m = Number(from.slice(5, 7));
  const year = y !== Number(today.slice(0, 4)) ? ` ${y}` : '';
  if (from.slice(0, 7) === to.slice(0, 7) && from.endsWith('-01') && Number(to.slice(8, 10)) === lastDay(y, m)) return `за ${MONTHS_ACC[m - 1]}${year}`;
  if (from === to) return day(from) + year;
  return `${day(from)}-${day(to)}${year}`;
}

// Відповідь текстом: одне-два речення, числа лише з моделі
export function formatSpending(m: SpendModel, today: string): string {
  const period = periodLabel(m.from, m.to, today);
  const what = m.type === 'income' ? 'Доходи' : 'Витрати';
  const subject = m.category ? `${m.category}` : m.search ? `«${m.search}»` : what;
  if (!m.count) {
    if (m.category || m.search) return `${subject} ${period}: ${m.type === 'income' ? 'доходів' : 'витрат'} немає.`;
    return `${m.type === 'income' ? 'Доходів' : 'Витрат'} ${period} немає.`;
  }
  const head = `${subject} ${period}: ${money(m.totalCents)}, ${ops(m.count)}.`;
  if (m.category || m.type === 'income') return head;
  const top = m.byCategory.slice(0, 3).map((c) => `${c.name} ${money(c.cents)}`);
  return top.length ? `${head} Найбільше: ${top.join(', ')}.` : head;
}

// Межі періоду від моделі: дати ISO, від ≤ до, не в майбутньому (обрізаються до сьогодні), не довше 400 днів
export function clampPeriod(from: unknown, to: unknown, today: string): { from: string; to: string } | null {
  // Дата має існувати: 30.02 не перетворюється тихо на 02.03
  const iso = (v: unknown) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !isNaN(Date.parse(v + 'T00:00:00Z')) &&
    new Date(v + 'T00:00:00Z').toISOString().slice(0, 10) === v ? v : null;
  const f = iso(from), t0 = iso(to);
  if (!f || !t0) return null;
  const t = t0 > today ? today : t0;
  if (f > t || f < '2020-01-01') return null;
  if ((Date.parse(t) - Date.parse(f)) / DAY > 400) return null;
  return { from: f, to: t };
}

// Відносний період рахує код, а не модель (сліпий замір 14.11.2026: «минулого тижня» модель дала як поточний тиждень).
// Тиждень з понеділка; «за тиждень» = останні 7 днів разом із сьогодні; поточні періоди до сьогодні.
export const NAMED_PERIODS = ['today', 'yesterday', 'this_week', 'last_week', 'last_7_days', 'this_month', 'last_month', 'this_year', 'last_year'] as const;
export type NamedPeriod = typeof NAMED_PERIODS[number];
export function namedPeriod(name: unknown, today: string): { from: string; to: string } | null {
  const y = Number(today.slice(0, 4)), m = Number(today.slice(5, 7));
  const ym = (yy: number, mm: number) => `${yy}-${String(mm).padStart(2, '0')}`;
  const monday = shiftDay(today, -((new Date(today + 'T00:00:00Z').getUTCDay() + 6) % 7));
  const py = m === 1 ? y - 1 : y, pm = m === 1 ? 12 : m - 1;
  switch (name) {
    case 'today': return { from: today, to: today };
    case 'yesterday': { const d = shiftDay(today, -1); return { from: d, to: d }; }
    case 'this_week': return { from: monday, to: today };
    case 'last_week': return { from: shiftDay(monday, -7), to: shiftDay(monday, -1) };
    case 'last_7_days': return { from: shiftDay(today, -6), to: today };
    case 'this_month': return { from: ym(y, m) + '-01', to: today };
    case 'last_month': return { from: ym(py, pm) + '-01', to: `${ym(py, pm)}-${String(lastDay(py, pm)).padStart(2, '0')}` };
    case 'this_year': return { from: `${y}-01-01`, to: today };
    case 'last_year': return { from: `${y - 1}-01-01`, to: `${y - 1}-12-31` };
    default: return null;
  }
}
// Названий місяць без року: останній такий місяць, що вже почався (у листопаді «грудень» це грудень минулого року).
// Поточний місяць до сьогодні, минулі повністю.
export function monthPeriod(month: unknown, year: unknown, today: string): { from: string; to: string } | null {
  const mm = Number(month), y0 = Number(today.slice(0, 4)), m0 = Number(today.slice(5, 7));
  if (!Number.isInteger(mm) || mm < 1 || mm > 12) return null;
  const yy = year == null || year === '' ? (mm <= m0 ? y0 : y0 - 1) : Number(year);
  if (!Number.isInteger(yy) || yy < 2020 || yy > y0 || (yy === y0 && mm > m0)) return null;
  const p = `${yy}-${String(mm).padStart(2, '0')}`;
  return { from: p + '-01', to: yy === y0 && mm === m0 ? today : `${p}-${String(lastDay(yy, mm)).padStart(2, '0')}` };
}

// Названий лише рік: увесь рік, поточний до сьогодні (замір 14.11.2026: «цього року» модель передала як year без періоду)
export function yearPeriod(year: unknown, today: string): { from: string; to: string } | null {
  const yy = Number(year), y0 = Number(today.slice(0, 4));
  if (!Number.isInteger(yy) || yy < 2020 || yy > y0) return null;
  return { from: `${yy}-01-01`, to: yy === y0 ? today : `${yy}-12-31` };
}

// Завантаження операцій періоду (на день ширше), сторінками по 1000 без тихого обрізання
export async function loadSpendingTxs(sb: any, from: string, to: string): Promise<P[]> {
  const rows: P[] = [];
  for (let page = 0; page < 100; page++) {
    const { data, error } = await sb.from('transactions')
      .select('id,account_id,category_id,expense_allocations,fixed_id,credit_id,transfer_id,type,amount,date,created_at,description')
      .gte('date', shiftDay(from, -1)).lte('date', shiftDay(to, 1)).order('id', { ascending: true }).range(page * 1000, page * 1000 + 999);
    if (error) throw new Error('spending transactions lookup failed');
    rows.push(...(data || []));
    if (!data || data.length < 1000) return rows;
  }
  throw new Error('spending transactions pagination limit');
}
