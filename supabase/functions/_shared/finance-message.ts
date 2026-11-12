// Текст Telegram із тієї самої проєкції, що й застосунок. Без API та надсилання повідомлень.
import type { financeProjection } from './budget.ts';
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
export type BudgetLeft = {end: string; leftCents: number; dailyCents: number; leftDays: number};
export const dailyPart = (m: BudgetLeft) => m.leftCents > 0 && m.leftDays > 0 && m.dailyCents > 0 ? ` · ${money(m.dailyCents)}/день (${m.leftDays} дн.)` : '';
export const budgetLeftLine = (m: BudgetLeft) => `Бюджет до ${day(m.end)}: ${leftOrOver(m.leftCents)}` + dailyPart(m);
export const previousDay = (value: string) => new Date(Date.parse(value + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
const plural = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'операція' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'операції' : 'операцій';

export type Installment = {name: string; n: number; amountCents: number; lastDate?: string};

// Розділи статусу бота окремими рядками (v215, власник: «Баланс» лише основне, решта окремими кнопками):
// top: бюджет на початок періоду, залишок бюджету на день, нестача до виплати, власні, баланс;
// cards, installments, due: картки, розстрочки, найближчі платежі з заголовком; unassigned: попередження про операції без рахунку.
// Порожній розділ дає порожній масив.
export type FinanceSections = {top: string[]; cards: string[]; installments: string[]; due: string[]; unassigned: string[]};
export function financeSections(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = [], budget: BudgetLeft | null = null): FinanceSections {
  const accounts = p.snapshot.accounts || [];
  const instCents = installments.reduce((sum, i) => sum + i.n * i.amountCents, 0);
  const own = p.snapshot.positiveOwnCents;
  const cardDebt = accounts.reduce((sum, a) => sum + (a.debtCents || 0), 0);
  const top: string[] = [];
  const plan = p.nextPlan;
  // Порядок: бюджет на початок періоду, залишок бюджету на день, нестача до виплати, власні, баланс (власні мінус борг карток)
  if (plan) top.push(`Бюджет на початок періоду: ${money(plan.spendableTargetCents ?? plan.targetCents)} · ${money(plan.averageDailyCents)}/день (${day(plan.start)}-${day(plan.end)})`);
  else top.push('Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
  // v186: залишок бюджету поточного періоду на день; власні мінус обовʼязкові до виплати лише як попередження про нестачу
  if (budget) top.push(budgetLeftLine(budget));
  const u = p.untilPayout, short = u && u.days > 0 ? untilPayoutLine(u) : null;
  if (short) top.push(short);
  top.push(`Власні кошти: ${money(own)}`, `Баланс: ${money(own - cardDebt)}`);
  const cards: string[] = [];
  if (accounts.length) {
    cards.push('Картки:');
    for (const a of accounts) {
      const parts = [`${a.name}: ${money(a.balanceCents || 0)}`];
      if (a.debtCents > 0) {
        const repay = p.events.find(e => e.kind === 'repay' && e.cashDeltaCents < 0 && String(e.id).startsWith(`repay:${a.id}:`));
        parts.push(`борг ${money(a.debtCents)}` + (repay ? ` · план погашення ${day(repay.date)}` : ''));
      }
      if (Number(a.credit_limit) > 0) parts.push(`доступно ${money(Math.max(0, Math.round(Number(a.credit_limit) * 100) - (a.debtCents || 0)))}`);
      const ms = p.minSpend.find(m => String(m.accountId) === String(a.id));
      if (ms) parts.push(ms.left > 0 ? `мін. витрати ${money(ms.spent * 100)} з ${money(ms.min * 100)}` : 'мін. витрати виконано');
      cards.push(parts.join(' · '));
    }
  }
  const inst: string[] = [];
  if (installments.length) {
    inst.push(`Розстрочки: ${money(instCents)}`);
    // Залишок розстрочки: кількість × платіж = сума, дата останнього платежу
    for (const i of installments) inst.push(`${i.name}: ${i.n} × ${money(i.amountCents)} = ${money(i.n * i.amountCents)}` + (i.lastDate ? ` · до ${day(i.lastDate)}.${i.lastDate.slice(0, 4)}` : ''));
  }
  const events = p.events.filter(e => ['mandatory', 'fee'].includes(e.kind)).slice(0, 3);
  const due = events.length ? ['Найближчі платежі:', ...events.map(e => `${day(e.date)} · ${e.name}: ${money(-e.cashDeltaCents)}${e.certainty === 'conditional' ? ' (умовно)' : ''}`)] : [];
  const lost = unassigned.count > 0 ? [`⚠️ Без рахунку: ${unassigned.count} ${plural(unassigned.count)} на ${money(unassigned.amountCents)}. Виберіть рахунок під повідомленнями або в застосунку.`] : [];
  return {top, cards, installments: inst, due, unassigned: lost};
}

// Повний статус одним текстом (як до v215): розділи через порожній рядок. Бот шле розділи окремо, функція лишається для звірки.
export function formatFinanceMessage(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = [], budget: BudgetLeft | null = null): string {
  const s = financeSections(p, unassigned, installments, budget);
  const lines = [...s.top];
  for (const part of [s.cards, s.installments, s.due, s.unassigned]) if (part.length) lines.push('', ...part);
  return lines.join('\n');
}
