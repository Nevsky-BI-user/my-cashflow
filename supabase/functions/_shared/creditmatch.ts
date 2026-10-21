// Зіставлення фактичної витрати з графіком розстрочки (власник 12.10.2026): списання, схоже на платіж розстрочки,
// отримує transactions.credit_id і закриває платіж місяця своєї дати фактом.
// Збіг: банк рахунку = credits.source або в описі є перше слово назви (від 4 літер); сума в межах max(1 ₴, 1 %)
// від monthly_amount; місяць дати в графіку; день у межах 5 днів від payment_day; цей місяць ще не оплачений.
// Кілька збігів: не привʼязуємо (неоднозначно).
export type CreditRow = {
  id: number | string; name: string; monthly_amount: number | string; payment_day: number | string;
  start_year: number | string; start_month: number | string; total_payments: number | string; source?: string | null;
};
export type CreditTx = { amount: number; date: string; bank?: string | null; description?: string | null };

export function matchCredit(credits: CreditRow[], tx: CreditTx, paid: Set<string> = new Set()): number | null {
  const [y, m, d] = tx.date.split('-').map(Number);
  const k = y * 12 + (m - 1);
  const desc = String(tx.description || '').toLowerCase();
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const hits = credits.filter((c) => {
    const first = Number(c.start_year) * 12 + Number(c.start_month); // start_month з 0
    if (k < first || k >= first + Number(c.total_payments)) return false;
    const due = Math.min(Number(c.payment_day), last);
    if (Math.abs(d - due) > 5) return false;
    const amt = Number(c.monthly_amount);
    if (!(amt > 0) || Math.abs(tx.amount - amt) > Math.max(1, amt * 0.01)) return false;
    if (paid.has(String(c.id) + '|' + tx.date.slice(0, 7))) return false;
    const word = String(c.name || '').toLowerCase().trim().split(/\s+/)[0] || '';
    const byBank = !!tx.bank && !!c.source && String(c.source) === String(tx.bank);
    return byBank || ([...word].length >= 4 && desc.includes(word));
  });
  return hits.length === 1 ? Number(hits[0].id) : null;
}

// Ключі `${credit_id}|YYYY-MM` уже оплачених фактом місяців
export function creditPaid(txs: { credit_id?: number | string | null; payment_due_date?: string | null; created_at?: string | null; date?: string | null; type?: string }[]): Set<string> {
  return new Set(txs.filter((t) => t.credit_id != null && t.type !== 'income').map((t) => String(t.credit_id) + '|' + String(t.payment_due_date ?? t.date ?? t.created_at ?? '').slice(0, 7)));
}
