// Коротка голосова відповідь бота. Власник 14.11.2026: «вона утричі довша ніж потрібно. людина питає про баланс.
// значить потрібна одна цифра без копійок, можна навіть до сотні округлити. але не треба читати текст повідомлення
// який і так є в повідомленні». Текст під голосовим лишається повним і точним; голосом одна фраза з одним числом
// з тієї самої моделі, що й текст. Чисті функції, без мережі.
import { moneyWords, toSpeech } from './uk-speech.ts';
import { periodLabel, type SpendModel } from './spending.ts';
import { day, type FinanceTotals } from './finance-message.ts';
import type { BudgetModel } from './bot-reports.ts';

export type SaySection = 'balance' | 'cards' | 'installments' | 'payments';

// Сума для мови: до тисячі цілі гривні, від тисячі до сотень; половина вгору за модулем, знак зберігається
export function spokenCents(cents: number): number {
  const v = Number(cents) || 0, abs = Math.abs(v);
  // Одне округлення від копійок: 12 249,99 дає 12 200, а не 12 250 і потім 12 300
  const r = abs < 100000 ? Math.round(abs / 100) : Math.round(abs / 10000) * 100;
  return v < 0 && r ? -r * 100 : r * 100;
}
export const sayMoney = (cents: number) => moneyWords(spokenCents(cents));

export function sayBalance(t: FinanceTotals, section: SaySection): string {
  if (section === 'cards') return t.cardDebtCents > 0 ? `Борг на картках ${sayMoney(t.cardDebtCents)}.` : 'Боргу на картках немає.';
  if (section === 'installments') return t.installmentsCents > 0 ? `Розстрочки ${sayMoney(t.installmentsCents)}.` : 'Розстрочок немає.';
  if (section === 'payments') {
    const n = t.next;
    return n ? `${toSpeech(`Найближчий платіж ${day(n.date)} · ${n.name}`)}: ${sayMoney(n.cents)}.` : 'Найближчих обовʼязкових платежів немає.';
  }
  return `Баланс ${sayMoney(t.balanceCents)}.`;
}

export function saySpending(m: SpendModel, today: string): string {
  const period = periodLabel(m.from, m.to, today), own = m.category || m.search;
  if (!m.count) {
    if (own) return `${toSpeech(`${own} ${period}`)}: ${m.type === 'income' ? 'доходів' : 'витрат'} немає.`;
    return `${toSpeech(`${m.type === 'income' ? 'Доходів' : 'Витрат'} ${period}`)} немає.`;
  }
  return `${toSpeech(`${own || (m.type === 'income' ? 'Доходи' : 'Витрати')} ${period}`)}: ${sayMoney(m.totalCents)}.`;
}

const normName = (s: unknown) => String(s ?? '').normalize('NFKC').toLocaleLowerCase('uk-UA').trim();
export function sayBudget(m: BudgetModel | null, category: string | null): string {
  if (!m) return 'Бюджет недоступний.';
  if (!category) return m.leftCents < 0 ? `Перевитрата бюджету ${sayMoney(-m.leftCents)}.` : `У бюджеті лишилось ${sayMoney(m.leftCents)}.`;
  const row = m.rows.find((r) => normName(r.name) === normName(category));
  if (!row) return `${toSpeech(category)}: ні плану, ні витрат немає.`;
  const name = toSpeech(row.name);
  if (row.noPlan || row.plan <= 0) return `${name}: витрачено ${sayMoney(row.fact)}.`;
  const left = row.plan - row.fact;
  return left < 0 ? `${name}: перевитрата ${sayMoney(-left)}.` : `${name}: лишилось ${sayMoney(left)}.`;
}
