// Текст Telegram із тієї самої проєкції, що й застосунок. Без API та надсилання повідомлень.
import type { financeProjection } from './budget.ts';
import { cellFormat, esc, hrn, preTable, uah } from './bot-table.ts';
type FinanceMessage = ReturnType<typeof financeProjection>;
export const money = (cents: number) => new Intl.NumberFormat('uk-UA', {maximumFractionDigits: 2}).format(cents / 100) + ' ₴';
export const day = (value: string) => value.slice(8, 10) + '.' + value.slice(5, 7);
// v186 (власник: «доступно до 06.11 1398 або 99,9 грн на день... нісенітниця»): власні кошти мінус обовʼязкові не ліміт витрат,
// бо щоденні витрати йдуть з кредитки; рядок лише попереджає про нестачу, сума без знака. Інакше null.
export const untilPayoutLine = (u: {end: string; cents: number; dailyCents: number; days: number}) => u.cents < 0
  ? `Не вистачає до ${day(u.end)}: ${money(-u.cents)}` : null;
// Залишок бюджету: від'ємний показується як «перевитрата» з додатною сумою
export const leftOrOver = (cents: number, left = 'лишилось') => cents < 0 ? `перевитрата ${money(-cents)}` : `${left} ${money(cents)}`;
// v186: єдине число «на день» у боті: залишок бюджету періоду на дні до кінця періоду (як плитка застосунку і звіт «Бюджет»)
export type BudgetLeft = {end: string; leftCents: number; dailyCents: number; leftDays: number; monthlyBudgetEstimated?: boolean};
// v234 (власник 17.11.2026: «якщо це прогнозована перевитрата, то так і пиши»): відʼємний залишок рахується з фактичних витрат
// (бюджет періоду мінус витрачено; з місячним планом ще й перебір місяця з попереднього періоду). Прогнозне в ньому лише план,
// оцінений за останнім місячним (monthlyBudget.estimated); тоді підпис «Прогноз перевитрати»
export const overLabel = (m: BudgetLeft) => (m.monthlyBudgetEstimated ? 'Прогноз перевитрати до ' : 'Перевитрата до ') + day(m.end);
export const dailyPart = (m: BudgetLeft) => m.leftCents > 0 && m.leftDays > 0 && m.dailyCents > 0 ? ` · ${money(m.dailyCents)}/день (${m.leftDays} дн.)` : '';
export const budgetLeftLine = (m: BudgetLeft) => `Бюджет до ${day(m.end)}: ${leftOrOver(m.leftCents)}` + dailyPart(m);
export const previousDay = (value: string) => new Date(Date.parse(value + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
const plural = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'операція' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'операції' : 'операцій';

// Власні й кредитні в гривнях так, як їх показують клітинки таблиць: сума округлених рядків рахунків
// Без переліку рахунків (знімок лише з підсумками): підсумки знімка, округлені так само
export function shownOwnDebt(snapshot: {accounts?: any[]; unassignedAdjustmentCents?: number; positiveOwnCents?: number; creditDebtCents?: number}): {ownCents: number; debtCents: number} {
  const accounts = snapshot.accounts || [];
  if (!accounts.length) return {ownCents: hrn(snapshot.positiveOwnCents || 0), debtCents: hrn(snapshot.creditDebtCents || 0)};
  return {
    ownCents: Math.max(0, accounts.reduce((n, a) => n + hrn(Math.max(0, a.balanceCents || 0)), 0) + hrn(snapshot.unassignedAdjustmentCents || 0)),
    debtCents: accounts.reduce((n, a) => n + hrn(a.debtCents || 0), 0),
  };
}

const KIND: Record<string, string> = {debit: 'дебетова', credit: 'кредитна', cash: 'готівка'};

// Рядки розділу «Картки» числами (гривні, округлені як клітинки таблиці): власні, борг, доступний кредит.
// «Разом» рахується з цих рядків, тож сходиться на калькуляторі. Спільне для таблиці бота і функції family-status.
// Доступно лише в рахунку з кредитним лімітом, інакше null; «Без рахунку» (ручні операції без рахунку після
// мітки ручних залишків) окремим рядком, null, коли округлено до нуля
export type AccountRow = {id: string | number; name: string; owner: string | null; kind: string | null; bank: string | null;
  ownCents: number; debtCents: number; availableCents: number | null; balanceUpdatedAt: string | null; mono: boolean; notes: string[]};
export type AccountRows = {rows: AccountRow[]; unassignedCents: number | null; totals: {ownCents: number; debtCents: number; availableCents: number | null}};
export function accountRows(p: FinanceMessage): AccountRows {
  const rows: AccountRow[] = [];
  let ownT = 0, debtT = 0, freeT = 0, hasFree = false;
  for (const a of p.snapshot.accounts || []) {
    const bal = hrn(a.balanceCents || 0), debt = hrn(a.debtCents || 0);
    const limit = Number(a.credit_limit) > 0 ? hrn(Math.max(0, Math.round(Number(a.credit_limit) * 100) - (a.debtCents || 0))) : null;
    ownT += bal; debtT += debt;
    if (limit != null) { freeT += limit; hasFree = true; }
    const extra: string[] = [];
    if (a.debtCents > 0) {
      const repay = p.events.find(e => e.kind === 'repay' && e.cashDeltaCents < 0 && String(e.id).startsWith(`repay:${a.id}:`));
      if (repay) extra.push(`план погашення ${day(repay.date)}`);
    }
    const ms = p.minSpend.find(m => String(m.accountId) === String(a.id));
    if (ms) extra.push(ms.left > 0 ? `мін. витрати ${money(ms.spent * 100)} з ${money(ms.min * 100)}` : 'мін. витрати виконано');
    rows.push({id: a.id, name: String(a.name), owner: a.owner ? String(a.owner) : null, kind: a.kind ?? null, bank: a.bank ?? null,
      ownCents: bal, debtCents: debt, availableCents: limit, balanceUpdatedAt: a.balance_updated_at ?? null, mono: !!a.mono_account_id, notes: extra});
  }
  // Операції без рахунку після ручних залишків входять у власні кошти: окремим рядком, щоб «Разом» сходився з Балансом
  const adj = hrn(p.snapshot.unassignedAdjustmentCents || 0);
  if (adj) ownT += adj;
  return {rows, unassignedCents: adj ? adj : null, totals: {ownCents: ownT, debtCents: debtT, availableCents: hasFree ? freeT : null}};
}

export type Installment = {name: string; n: number; amountCents: number; lastDate?: string};

// Розділи статусу бота окремими рядками (v215, власник: «Баланс» лише основне, решта окремими кнопками):
// top: таблиця бюджет періоду, залишок бюджету на день, нестача до виплати, власні, кредитні, баланс;
// cards, installments, due: таблиці <pre> (HTML) карток з рядком «Разом», розстрочок, найближчих платежів; unassigned: попередження.
// Порожній розділ дає порожній масив.
// totals: ті самі числа для короткої голосової відповіді (voice-say.ts), рахуються тут один раз разом із текстом
export type FinanceTotals = {balanceCents: number; cardDebtCents: number; installmentsCents: number; next: {date: string; name: string; cents: number} | null};
export type FinanceSections = {top: string[]; cards: string[]; installments: string[]; due: string[]; unassigned: string[]; totals: FinanceTotals};
export function financeSections(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = [], budget: BudgetLeft | null = null): FinanceSections {
  const accounts = p.snapshot.accounts || [];
  const instCents = installments.reduce((sum, i) => sum + i.n * i.amountCents, 0);
  const own = p.snapshot.positiveOwnCents;
  const cardDebt = accounts.reduce((sum, a) => sum + (a.debtCents || 0), 0);
  const balanceCents = own - cardDebt;
  // v233 (власник 17.11.2026: «оформи все у вигляді таблиці»): кожен розділ таблицею <pre>, одиниця один раз у підписі.
  // Гривні без копійок; Баланс і «Разом» рахуються з показаних клітинок, щоб сходились на калькуляторі.
  // Назву розділу показує кнопка, тож над таблицею підпису немає; ₴ стоїть у шапці.
  const top: string[] = [];
  const kv: string[][] = [];
  const plan = p.nextPlan;
  // Порядок: бюджет на початок періоду, залишок бюджету на день, нестача до виплати, власні, кредитні, баланс
  // v234 (власник: «навіщо рядок з одним значенням грн», «чому На день з відступом», «немає сітки»): без шапки з ₴,
  // одиниця одним рядком над таблицею; «На день» без відступу; бот шле таблицю картинкою з сіткою (rich-send.ts)
  if (plan) kv.push([`Бюджет ${day(plan.start)}-${day(plan.end)}`, uah(plan.spendableTargetCents ?? plan.targetCents)], ['На день', uah(plan.averageDailyCents)]);
  else top.push('Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
  // v186: залишок бюджету поточного періоду на день; власні мінус обовʼязкові до виплати лише як попередження про нестачу
  if (budget) {
    kv.push(budget.leftCents < 0 ? [overLabel(budget), uah(-budget.leftCents)] : [`Лишилось до ${day(budget.end)}`, uah(budget.leftCents)]);
    if (dailyPart(budget)) kv.push([`На день, ${budget.leftDays} дн.`, uah(budget.dailyCents)]);
  }
  const u = p.untilPayout;
  if (u && u.days > 0 && u.cents < 0) kv.push([`Не вистачає до ${day(u.end)}`, uah(-u.cents)]);
  // Власні й кредитні тими самими показаними клітинками, що «Разом» у розділі «Картки»: число одне на обох екранах
  const {ownCents: ownShown, debtCents: debtShown} = shownOwnDebt(p.snapshot);
  kv.push(['Власні', uah(ownShown)], ['Кредитні', uah(debtShown)], ['Баланс', uah(ownShown - debtShown)]);
  top.push('Суми в ₴', preTable(null, kv, 24));
  const cards: string[] = [];
  if (accounts.length) {
    // Картинка: окремі колонки Хто (поле owner, порожнє лишається порожнім) і Тип (kind); текст лишається вузьким
    const ar = accountRows(p), rows: string[][] = [], img: string[][] = [], notes: string[] = [];
    for (const a of ar.rows) {
      rows.push([a.name, uah(a.ownCents), a.debtCents ? uah(a.debtCents) : '', a.availableCents != null ? uah(a.availableCents) : '']);
      img.push([a.name, a.owner || '', KIND[String(a.kind)] || '', uah(a.ownCents), a.debtCents ? uah(a.debtCents) : '', a.availableCents != null ? uah(a.availableCents) : '']);
      if (a.notes.length) notes.push(`${esc(a.name)}: ${a.notes.join(' · ')}`);
    }
    if (ar.unassignedCents != null) { rows.push(['Без рахунку', uah(ar.unassignedCents), '', '']); img.push(['Без рахунку', '', '', uah(ar.unassignedCents), '', '']); }
    const t = ar.totals;
    rows.push(['Разом', uah(t.ownCents), uah(t.debtCents), t.availableCents != null ? uah(t.availableCents) : '']);
    img.push(['Разом', '', '', uah(t.ownCents), uah(t.debtCents), t.availableCents != null ? uah(t.availableCents) : '']);
    cards.push('Суми в ₴', preTable(['Рахунок', 'Власні', 'Борг', 'Доступно'], rows, 12, {
      head: ['Рахунок', 'Хто', 'Тип', 'Власні', 'Борг', 'Доступно'], rows: img,
      kinds: img.map((r) => r[0] === 'Разом' ? 'total' : 'row'), aligns: ['l', 'l', 'l', 'r', 'r', 'r'],
    }), ...notes);
  }
  const inst: string[] = [];
  if (installments.length) {
    // Залишок розстрочки: кількість × платіж = сума, місяць останнього платежу; точність колонки одна на всю колонку
    const f = cellFormat(installments.map(i => i.amountCents));
    const rows = installments.map(i => [i.name, String(i.n), f(i.amountCents), f(i.n * i.amountCents), i.lastDate ? i.lastDate.slice(5, 7) + '.' + i.lastDate.slice(2, 4) : '']);
    rows.push(['Разом', '', f(installments.reduce((n, i) => n + i.amountCents, 0)), f(instCents), '']);
    inst.push('Суми в ₴', preTable(['Розстрочка', 'К-ть', 'Платіж', 'Сума', 'До'], rows, 10));
  }
  const events = p.events.filter(e => ['mandatory', 'fee'].includes(e.kind)).slice(0, 3);
  const due: string[] = [];
  if (events.length) {
    const f = cellFormat(events.map(e => -e.cashDeltaCents));
    const rows = events.map(e => [`${day(e.date)} ${e.name}${e.certainty === 'conditional' ? ' (умовно)' : ''}`, f(-e.cashDeltaCents)]);
    if (events.length > 1) rows.push(['Разом', f(events.reduce((n, e) => n - e.cashDeltaCents, 0))]);
    due.push('Суми в ₴', preTable(['Найближчі платежі', 'Сума'], rows, 24));
  }
  const lost = unassigned.count > 0 ? [`⚠️ Без рахунку: ${unassigned.count} ${plural(unassigned.count)} на ${money(unassigned.amountCents)}. Виберіть рахунок під повідомленнями або в застосунку.`] : [];
  const next = events[0] ? {date: events[0].date, name: events[0].name, cents: -events[0].cashDeltaCents} : null;
  return {top, cards, installments: inst, due, unassigned: lost, totals: {balanceCents, cardDebtCents: cardDebt, installmentsCents: instCents, next}};
}

// Повний статус одним текстом (як до v215): розділи через порожній рядок. Бот шле розділи окремо, функція лишається для звірки.
export function formatFinanceMessage(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = [], budget: BudgetLeft | null = null): string {
  const s = financeSections(p, unassigned, installments, budget);
  const lines = [...s.top];
  for (const part of [s.cards, s.installments, s.due, s.unassigned]) if (part.length) lines.push('', ...part);
  return lines.join('\n');
}
