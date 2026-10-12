// Текст Telegram із тієї самої проєкції, що й застосунок. Без API та надсилання повідомлень.
import type { financeProjection } from './budget.ts';
type FinanceMessage = ReturnType<typeof financeProjection>;
const money = (cents: number) => new Intl.NumberFormat('uk-UA', {maximumFractionDigits: 2}).format(cents / 100) + ' ₴';
const day = (value: string) => value.slice(8, 10) + '.' + value.slice(5, 7);
const previousDay = (value: string) => new Date(Date.parse(value + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
const plural = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'операція' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'операції' : 'операцій';

export type Installment = {name: string; n: number; amountCents: number};

// Короткий статус для бота: бюджет на початок періоду, доступно до виплати, власні, баланс, кожна картка окремим рядком, розстрочки, найближчі платежі.
// today: розстрочки з датою до сьогодні включно сплачені за планом.
export function formatFinanceMessage(p: FinanceMessage, unassigned: {count: number; amountCents: number} = {count: 0, amountCents: 0},
  installments: Installment[] = [], today = ''): string {
  const accounts = p.snapshot.accounts || [];
  const instCents = installments.reduce((sum, i) => sum + i.n * i.amountCents, 0);
  const own = p.snapshot.positiveOwnCents;
  const cardDebt = accounts.reduce((sum, a) => sum + (a.debtCents || 0), 0);
  const paidByPlan = (e: {id: string; date: string}) => String(e.id).startsWith('installment:') && e.date <= today;
  const lines: string[] = [];
  const plan = p.nextPlan;
  // Порядок: бюджет на початок періоду, доступно до виплати, власні, баланс (власні мінус борг карток)
  if (plan) lines.push(`Бюджет на початок періоду: ${money(plan.targetCents)} · ${money(plan.averageDailyCents)}/день (${day(plan.start)}-${day(previousDay(plan.end))})`);
  else lines.push('Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.');
  // Доступно до виплати: власні мінус обовʼязкові платежі до дня виплати; борг кредиток гаситься з виплати
  if (plan && today && today < plan.start) {
    const dueCents = p.events.filter(e => ['mandatory', 'fee'].includes(e.kind) && e.date >= today && e.date < plan.start && !paidByPlan(e))
      .reduce((sum, e) => sum - e.cashDeltaCents, 0);
    const days = Math.round((Date.parse(plan.start) - Date.parse(today)) / 86400000);
    const avail = own - dueCents;
    lines.push(`Доступно до ${day(previousDay(plan.start))}: ${money(avail)}` + (avail > 0 ? ` · ${money(Math.floor(avail / days))}/день (${days} дн.)` : ''));
  }
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
    for (const i of installments) lines.push(`${i.name}: ${i.n} × ${money(i.amountCents)}`);
  }
  const due = p.events.filter(e => ['mandatory', 'fee'].includes(e.kind) && !paidByPlan(e)).slice(0, 3);
  if (due.length) lines.push('', 'Найближчі платежі:', ...due.map(e => `${day(e.date)} · ${e.name}: ${money(-e.cashDeltaCents)}${e.certainty === 'conditional' ? ' (умовно)' : ''}`));
  if (unassigned.count > 0) lines.push('', `⚠️ Без рахунку: ${unassigned.count} ${plural(unassigned.count)} на ${money(unassigned.amountCents)}. Виберіть рахунок під повідомленнями або в застосунку.`);
  return lines.join('\n');
}
