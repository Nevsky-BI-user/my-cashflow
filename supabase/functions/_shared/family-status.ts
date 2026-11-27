// Стан сімейних фінансів для локального клієнта власника (userbot telegram-twin на ПК): лише читання.
// Числа не рахуються тут удруге: дані статусу ті самі, що в боті (_shared/bot-status.ts, як freeBlock для «Баланс» і «Картки»),
// рядки карток з accountRows, «Власні/Кредитні» з shownOwnDebt, залишок бюджету з budgetModel.
// Гривні округлені як клітинки таблиць бота; підсумки рахуються з показаних рядків, тож сходяться на калькуляторі.
// Захист: підпис HMAC секретом TWIN_SECRET з міткою часу (та сама перевірка, що для мовного сервісу, _shared/voice-auth.ts).
// Клієнт Supabase, годинник і завантаження передаються ззовні: модуль перевіряють node-тести без мережі.
import { voiceVerify } from './voice-auth.ts';
import { statusData, type StatusData } from './bot-status.ts';
import { accountRows, dailyPart, shownOwnDebt } from './finance-message.ts';
import { hrn } from './bot-table.ts';
import { kyivNow } from './bot-reports.ts';

// Що підписує клієнт: "<ts>\n" + цей рядок (тіла в GET немає, тож підпис покриває метод і шлях)
export const TWIN_SIGNED = 'GET /family-status';

// Гривні з копійок, округлені до гривні так само, як клітинка таблиці бота
const uahNum = (cents: number) => hrn(cents) / 100;

export type FamilyStatus = {
  today: string;
  generated_at: string;
  units: 'UAH';
  accounts: {name: string; bank: string | null; kind: string | null; owner: string | null; own: number; debt: number; available: number | null;
    source: 'mono' | 'manual'; balance_updated_at: string | null}[];
  unassigned_own: number | null;
  accounts_total: {own: number; debt: number; available: number | null};
  own_total: number;
  credit_debt_total: number;
  balance: number;
  next_payday: string | null;
  free_until_payday: number | null;
  payments_until_payday: {date: string; name: string; amount: number; conditional: boolean}[];
  payments_until_payday_total: number;
  budget: {start: string; end: string; left: number; daily: number | null; left_days: number; estimated: boolean} | null;
  freshness: {latest_transaction_at: string | null};
};

// Відповідь з даних статусу. Поля перелічені явно: жодних id, токенів, операцій чи інших полів рахунку
export function familyStatusModel(s: StatusData, today: string, latestTxAt: string | null, generatedAt: string): FamilyStatus {
  const p = s.projection, ar = accountRows(p), shown = shownOwnDebt(p.snapshot);
  const accounts = ar.rows.map((a) => ({
    name: a.name, bank: a.bank, kind: a.kind, owner: a.owner,
    own: a.ownCents / 100, debt: a.debtCents / 100, available: a.availableCents == null ? null : a.availableCents / 100,
    source: (a.mono ? 'mono' : 'manual') as 'mono' | 'manual', balance_updated_at: a.balanceUpdatedAt,
  }));
  const t = ar.totals;
  // Обовʼязкові платежі від сьогодні до дня перед виплатою: той самий набір, з якого рушій рахує «вільні до виплати»
  // (untilPayout = власні мінус ці платежі); сума платежу amountCents, як у розрахунку рушія
  const u = p.untilPayout;
  const payments = u ? p.events.filter((e: any) => (e.kind === 'mandatory' || e.kind === 'fee') && e.date >= today && e.date < u.end)
    .map((e: any) => ({date: String(e.date), name: String(e.name), amount: uahNum(e.amountCents), conditional: e.certainty === 'conditional'})) : [];
  const b = s.budget;
  return {
    today,
    generated_at: generatedAt,
    units: 'UAH',
    accounts,
    unassigned_own: ar.unassignedCents == null ? null : ar.unassignedCents / 100,
    accounts_total: {own: t.ownCents / 100, debt: t.debtCents / 100, available: t.availableCents == null ? null : t.availableCents / 100},
    own_total: shown.ownCents / 100,
    credit_debt_total: shown.debtCents / 100,
    balance: (shown.ownCents - shown.debtCents) / 100,
    next_payday: u ? u.end : null,
    free_until_payday: u ? uahNum(u.cents) : null,
    payments_until_payday: payments,
    payments_until_payday_total: Math.round(payments.reduce((n, x) => n + x.amount * 100, 0)) / 100,
    budget: b ? {start: b.start, end: b.end, left: uahNum(b.leftCents), daily: dailyPart(b) ? uahNum(b.dailyCents) : null, left_days: b.leftDays,
      estimated: !!b.monthlyBudgetEstimated} : null,
    freshness: {latest_transaction_at: latestTxAt},
  };
}

// Остання операція загалом: лише мітка часу запису, без суми й опису
export async function latestTransactionAt(sb: any): Promise<string | null> {
  const r = await sb.from('transactions').select('created_at').order('created_at', {ascending: false}).limit(1);
  if (r.error) throw new Error('latest transaction lookup failed');
  return r.data?.[0]?.created_at ?? null;
}

export type FamilyStatusDeps = {sb: any; secret: string; now?: () => Date; load?: typeof statusData};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'},
});

// Обробник функції family-status: спершу метод і підпис, потім читання бази
export async function handleFamilyStatus(req: Request, deps: FamilyStatusDeps): Promise<Response> {
  if (req.method !== 'GET') return json({error: 'method not allowed'}, 405);
  if (!await voiceVerify(deps.secret, req.headers.get('X-Twin-Ts'), req.headers.get('X-Twin-Sig'), TWIN_SIGNED)) return json({error: 'unauthorized'}, 401);
  const now = (deps.now || (() => new Date()))();
  const today = kyivNow(now).date;
  try {
    const [s, latest] = await Promise.all([(deps.load || statusData)(deps.sb, today), latestTransactionAt(deps.sb)]);
    return json(familyStatusModel(s, today, latest, now.toISOString()));
  } catch (e) {
    console.error('family-status failed', (e as Error)?.message);
    return json({error: 'internal'}, 500);
  }
}
