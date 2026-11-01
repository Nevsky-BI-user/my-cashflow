import math
import unicodedata


def expense_category_parts(tx, categories=None):
    try:
        total = math.floor(float(tx.get('amount', 0)) * 100 + .5)
    except (ValueError, TypeError, OverflowError):
        total = 0
    fallback = [dict(tx, amount_cents=total, originalTransactionId=tx.get('id'))]
    rows = tx.get('expense_allocations')
    def ordinary(c):
        return c and c.get('type') != 'income' and not c.get('is_income') and not c.get('isIncome') and not c.get('budget_role') and str(c.get('id')) != 'savings' and unicodedata.normalize('NFKC', c.get('name') or '').strip().lower() != 'заощадження'
    def find(cid):
        return next((c for c in categories if str(c.get('id')) == str(cid)), None)
    def safe(n):
        return type(n) in (int, float) and math.isfinite(n) and n == int(n) and 0 < n <= 9007199254740991
    if tx.get('type') != 'expense' or any(tx.get(k) is not None for k in ('transfer_id', 'fixed_id', 'credit_id')) or not safe(total) or not isinstance(rows, list) or not 2 <= len(rows) <= 100:
        return fallback
    if categories is not None and tx.get('category_id') is not None and not ordinary(find(tx['category_id'])):
        return fallback
    total_parts = 0
    for row in rows:
        if not isinstance(row, dict): return fallback
        cid = row.get('category_id')
        if not (safe(cid) or isinstance(cid, str) and cid.strip()) or not safe(row.get('amount_cents')): return fallback
        if 'label' in row and (not isinstance(row['label'], str) or len(row['label']) > 160): return fallback
        if categories is not None and not ordinary(find(cid)): return fallback
        total_parts += row['amount_cents']
        if not safe(total_parts): return fallback
    if total_parts != total: return fallback
    return [dict(tx, category_id=r['category_id'], amount=r['amount_cents']/100, amount_cents=r['amount_cents'], allocationLabel=r.get('label', ''), allocationIndex=i, originalTransactionId=tx.get('id')) for i, r in enumerate(rows)]
