# Змінний бюджет наступного періоду за правилом власника (08.10.2026):
#   бюджет = наступна виплата - обовʼязкові платежі до наступної виплати - поточний мінус
#   (мінус = борги мінус власні кошти, якщо більше нуля); результат <= 0 означає нуль і перенесення дефіциту.
# Вхід: JSON {accounts, fixed, credits, salary} (знімок БД). Запуск:
#   PYTHONUTF8=1 python scripts/budget_pool.py <snapshot.json> [YYYY-MM-DD сьогодні]
import calendar, json, sys
from datetime import date, timedelta

snap = json.load(open(sys.argv[1], encoding='utf-8-sig'))
today = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
cfg = snap['salary']
RATE, SPLIT = float(cfg['rate']), int(cfg['split_day'])
ADV, SAL = int(cfg['advance_day']), int(cfg['salary_day'])


def wd(y, m, d1, d2):
    return sum(1 for d in range(d1, d2 + 1) if date(y, m, d).weekday() < 5)


def adj(y, m, d):
    w = date(y, m, d).weekday()
    return date(y, m, d - 1 if w == 5 else d + 1 if w == 6 else d)


def payouts(y, m):
    """Виплати в місяці (y, m): (дата, назва, сума)."""
    last = calendar.monthrange(y, m)[1]
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    plast = calendar.monthrange(py, pm)[1]
    return [
        (adj(y, m, ADV), 'аванс', round(RATE / wd(y, m, 1, last) * wd(y, m, 1, SPLIT), 2)),
        (adj(y, m, SAL), 'зарплата', round(RATE / wd(py, pm, 1, plast) * wd(py, pm, SPLIT + 1, plast), 2)),
    ]


# усі виплати на 3 місяці вперед, відсортовані
pays = []
for i in range(3):
    y, m = divmod(today.year * 12 + today.month - 1 + i, 12)
    pays += payouts(y, m + 1)
pays.sort()
future = [p for p in pays if p[0] > today]
p_next, p_after = future[0], future[1]
period = (p_next[0], p_after[0])  # [дата виплати; наступна виплата)

# поточний мінус
own = sum(float(a['balance']) for a in snap['accounts'] or [])
debt = sum(float(a['debt']) for a in snap['accounts'] or [])
net = own - debt
deficit = max(0.0, -net)


def in_period(day):
    """Дата платежу з днем місяця day у межах періоду [start, end)."""
    start, end = period
    for y, m in [(start.year, start.month), (end.year, end.month)]:
        d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if start <= d < end:
            return d
    return None


obl = []
for f in snap['fixed'] or []:
    d = in_period(int(f['day_of_month']))
    if d:
        amt = float(f['amount'])
        obl.append((d, f['name'], amt if f['type'] != 'income' else -amt))
for c in snap['credits'] or []:
    d = in_period(int(c['payment_day']))
    if d:
        first = c['start_year'] * 12 + c['start_month']
        cur = d.year * 12 + (d.month - 1)
        if first <= cur <= first + int(c['total_payments']) - 1:
            obl.append((d, c['name'] + ' (розстрочка)', float(c['monthly_amount'])))
obl.sort()

obl_sum = sum(a for _, _, a in obl)
pool = p_next[2] - obl_sum - deficit

print(f"сьогодні {today}; власні кошти {own:.2f}, борги {debt:.2f}, нетто {net:.2f}, мінус до перекриття {deficit:.2f}")
print(f"наступна виплата: {p_next[1]} {p_next[0]} = {p_next[2]:.2f}; період до {p_after[0]} ({p_after[1]})")
for d, n, a in obl:
    print(f"  {d}  {n:<32} {a:>10.2f}")
print(f"обовʼязкові за період: {obl_sum:.2f}")
print(f"змінний бюджет періоду: {max(0.0, pool):.2f}" + (f"  (дефіцит {-pool:.2f} переноситься далі)" if pool < 0 else ""))

# накопичення лише з додатного залишку: savings = pool0 * savings_pct / 100, змінні = pool0 - savings
pct = float(snap.get('savings_pct', cfg.get('savings_pct', 0)) or 0)
savings = round(max(0.0, pool) * pct / 100, 2)
var_pool = max(0.0, pool - savings)
print(f"накопичення {pct:g}%: {savings:.2f}; змінні після накопичень: {var_pool:.2f}")
# машинний рядок для spec/checks/budget.py
print('JSON ' + json.dumps({
    'payout': {'date': str(p_next[0]), 'kind': 'advance' if p_next[1] == 'аванс' else 'salary', 'amount': p_next[2]},
    'end': str(p_after[0]), 'obligations': [{'date': str(d), 'name': n, 'amount': a} for d, n, a in obl],
    'oblSum': obl_sum, 'own': own, 'debt': debt, 'deficit': deficit, 'pool0': pool,
    'savings': savings, 'varPool': var_pool}, ensure_ascii=False))
