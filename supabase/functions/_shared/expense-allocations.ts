// Частини використовуються лише для категорій; каса завжди читає оригінальну операцію.
export function expenseCategoryParts(tx: any, categories?: any[]): any[] {
  const total = Math.round(Number(tx.amount) * 100);
  const fallback = () => [{ ...tx, amount_cents: total, originalTransactionId: tx.id }];
  const ordinary = (c: any) => c && c.type !== 'income' && !c.is_income && !c.isIncome && !c.budget_role && String(c.id) !== 'savings' && String(c.name || '').normalize('NFKC').trim().toLocaleLowerCase('uk-UA') !== 'заощадження';
  const rows = tx.expense_allocations;
  if (tx.type !== 'expense' || tx.transfer_id != null || tx.fixed_id != null || tx.credit_id != null || !Number.isSafeInteger(total) || total <= 0 || !Array.isArray(rows) || rows.length < 2 || rows.length > 100) return fallback();
  if (categories && tx.category_id != null && !ordinary(categories.find(c => String(c.id) === String(tx.category_id)))) return fallback();
  let sum = 0;
  for (const r of rows) {
    if (!r || typeof r !== 'object' || Array.isArray(r) || !((Number.isSafeInteger(r.category_id) && r.category_id > 0) || (typeof r.category_id === 'string' && r.category_id.trim().length > 0)) || !Number.isSafeInteger(r.amount_cents) || r.amount_cents <= 0 || (r.label !== undefined && (typeof r.label !== 'string' || [...r.label].length > 160)) || (categories && !ordinary(categories.find(c => String(c.id) === String(r.category_id))))) return fallback();
    sum += r.amount_cents;
    if (!Number.isSafeInteger(sum)) return fallback();
  }
  if (sum !== total) return fallback();
  return rows.map((r, i) => ({ ...tx, category_id: r.category_id, amount: r.amount_cents / 100, amount_cents: r.amount_cents, allocationLabel: r.label || '', allocationIndex: i, originalTransactionId: tx.id }));
}
