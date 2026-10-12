// Текст Telegram із тієї самої проєкції, що й застосунок. Без API та надсилання повідомлень.
import type { financeProjection } from './budget.ts';
type FinanceMessage = ReturnType<typeof financeProjection>;
export const money = (cents: number) => new Intl.NumberFormat('uk-UA', {maximumFractionDigits: 2}).format(cents / 100) + ' ₴';
export const day = (value: string) => value.slice(8, 10) + '.' + value.slice(5, 7);
export const previousDay = (value: string) => new Date(Date.parse(value + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
const plural = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'операція' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'операції' : 'операцій';

export type Installment = {name: string; n: number; amountCents: number; lastDate?: string};

// Короткий статус для бота: бюджет на початок періоду, доступно до виплати, власні, баланс, кожна картка окремим рядком, розстрочки, найближчі платежі.
export function formatFinanceMessage(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = []): string {
  const accounts = p.snapshot.accounts || [];
  const instCents = installments.reduce((sum, i) => sum + i.n * i.amountCents, 0);
  const own = p.snapshot.positiveOwnCents;
  const cardDebt = accounts.reduce((sum, a) => sum + (a.debtCents || 0), 0);
  const lines: string[] = [];
  const plan = p.nextPlan;
  // Порядок: бюджет на початок періоду, доступно до виплати, власні, баланс (власні мінус борг карток)
  if (plan) lines.push(`Бюджет на початок періоду: ${money(plan.targetCents)} · ${money(plan.averageDailyCents)}/день (${day(plan.start)}-${day(plan.end)})`);
  else lines.push('Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
  // Доступно до виплати: з рушія (власні мінус обовʼязкові до виплати; борг кредиток гаситься з виплати)
  const u = p.untilPayout;
  if (u && u.days > 0) lines.push(`Доступно до ${day(u.end)}: ${money(u.cents)}` + (u.dailyCents > 0 ? ` · ${money(u.dailyCents)}/день (${u.days} дн.)` : ''));
  lines.push(`Власні кошти: ${money(own)}`, `Баланс: ${money(own - cardDebt)}`);
  if (accounts.length) {
    lines.push('', 'Картки:');
    for (const a of accounts) {
      const parts = [`${a.name}: ${money(a.balanceCents || 0)}`];
      if (a.debtCents > 0) {
        const repay = p.events.find(e => e.kind === 'repay' && e.cashDeltaCents < 0 && String(e.id).startsWith(`repay:${a.id}:`));
        parts.push(`борг ${money(a.debtCents)}` + (repay ? ` до ${day(repay.date)}` : ''));
      }
      if (Number(a.credit_limit) > 0) parts.push(`доступно ${money(Math.max(0, Math.round(Number(a.credit_limit) * 100) - (a.debtCents || 0)))}`);
      const ms = p.minSpend.find(m => String(m.accountId) === String(a.id));
      if (ms) parts.push(ms.left > 0 ? `мін. витрати ${money(ms.spent * 100)} з ${money(ms.min * 100)}` : 'мін. витрати виконано');
      lines.push(parts.join(' · '));
    }
  }
  if (installments.length) {
    lines.push('', `Розстрочки: ${money(instCents)}`);
    // Залишок розстрочки: кількість × платіж = сума, дата останнього платежу
    for (const i of installments) lines.push(`${i.name}: ${i.n} × ${money(i.amountCents)} = ${money(i.n * i.amountCents)}` + (i.lastDate ? ` · до ${day(i.lastDate)}.${i.lastDate.slice(0, 4)}` : ''));
  }
  const due = p.events.filter(e => ['mandatory', 'fee'].includes(e.kind)).slice(0, 3);
  if (due.length) lines.push('', 'Найближчі платежі:', ...due.map(e => `${day(e.date)} · ${e.name}: ${money(-e.cashDeltaCents)}${e.certainty === 'conditional' ? ' (умовно)' : ''}`));
  if (unassigned.count > 0) lines.push('', `⚠️ Без рахунку: ${unassigned.count} ${plural(unassigned.count)} на ${money(unassigned.amountCents)}. Виберіть рахунок під повідомленнями або в застосунку.`);
  return lines.join('\n');
}
