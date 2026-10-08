# Змінний бюджет наступного періоду за правилом власника (08.10.2026):
#   бюджет = наступна виплата - обовʼязкові платежі до наступної виплати - поточний мінус
#   (мінус = борги мінус власні кошти, якщо більше нуля); результат <= 0 означає нуль і перенесення дефіциту.
# Правило «білої» картки (08.10.2026): білі обовʼязкові (credit_ok = false) йдуть лише з власних коштів
#   не кредитних рахунків; cashNow = ці кошти - білі з датою в [зараз; кінець періоду);
#   freeNow = max(0, min(varPool - spent, cashNow)). credit_ok за замовчуванням: fixed false,
#   credits true, якщо source містить 'privat'.
# Вхід: JSON {accounts, fixed, credits, salary, spent?, account_tx?} (знімок БД; spent: витрати періоду, за замовчуванням 0).
# Похідний баланс ручних рахунків (як deriveAccounts у _shared/budget.ts): якщо є account_tx
#   (список {account_id, type, amount, created_at}), рахунки без mono_account_id з id і balance_updated_at
#   отримують операції, створені строго після balance_updated_at: debit/cash balance - витрати + доходи,
#   credit debt + витрати - доходи (не менше 0). Без account_tx знімок рахується як раніше.
# Запуск: PYTHONUTF8=1 python scripts/budget_pool.py <snapshot.json> [YYYY-MM-DD сьогодні] [YYYY-MM-DD зараз]
#   «сьогодні» визначає період (виплата строго після нього), «зараз» початок вікна whiteDue (без нього весь період).
import calendar, json, sys
from datetime import date, datetime, timedelta


def parse_ts(s):
    """Мітка часу Postgres/ISO (+00:00, +00, Z) з точністю до мілісекунд, як Date.parse у TS."""
    s = str(s).strip().replace(' ', 'T', 1)
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    t = datetime.fromisoformat(s)
    return t.replace(microsecond=t.microsecond // 1000 * 1000)


def derive_accounts(accounts, txs):
    """Копії рахунків з ефективними balance/debt (правило похідного балансу, див. шапку)."""
    out = []
    for a in accounts or []:
        a2 = dict(a)
        out.append(a2)
        if a.get('mono_account_id') or a.get('id') is None or not a.get('balance_updated_at'):
            continue
        since = parse_ts(a['balance_updated_at'])
        exp = inc = 0.0
        for t in txs or []:
            if t.get('account_id') is None or int(t['account_id']) != int(a['id']):
                continue
            if not parse_ts(t['created_at']) > since:
                continue
            if t.get('type') == 'income':
                inc += float(t['amount'])
            else:
                exp += float(t['amount'])
        if a.get('kind') == 'credit':
            a2['debt'] = round(max(0.0, float(a['debt']) + exp - inc), 2)
        else:
            a2['balance'] = round(float(a['balance']) - exp + inc, 2)
    return out


snap = json.load(open(sys.argv[1], encoding='utf-8-sig'))
if snap.get('account_tx') is not None:
    snap['accounts'] = derive_accounts(snap['accounts'], snap['account_tx'])
today = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
now = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else None
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
        obl.append((d, f['name'], amt if f['type'] != 'income' else -amt, f.get('credit_ok') is True))
for c in snap['credits'] or []:
    d = in_period(int(c['payment_day']))
    if d:
        first = c['start_year'] * 12 + c['start_month']
        cur = d.year * 12 + (d.month - 1)
        if first <= cur <= first + int(c['total_payments']) - 1:
            ok = c.get('credit_ok')
            ok = bool(ok) if ok is not None else 'privat' in str(c.get('source') or '').lower()
            obl.append((d, c['name'] + ' (розстрочка)', float(c['monthly_amount']), ok))
obl.sort(key=lambda o: (o[0], o[1]))

obl_sum = sum(o[2] for o in obl)
pool = p_next[2] - obl_sum - deficit

print(f"сьогодні {today}; власні кошти {own:.2f}, борги {debt:.2f}, нетто {net:.2f}, мінус до перекриття {deficit:.2f}")
print(f"наступна виплата: {p_next[1]} {p_next[0]} = {p_next[2]:.2f}; період до {p_after[0]} ({p_after[1]})")
for d, n, a, ok in obl:
    print(f"  {d}  {n:<32} {a:>10.2f}  {'кредитна' if ok else 'біла'}")
print(f"обовʼязкові за період: {obl_sum:.2f}")
print(f"змінний бюджет періоду: {max(0.0, pool):.2f}" + (f"  (дефіцит {-pool:.2f} переноситься далі)" if pool < 0 else ""))

# накопичення лише з додатного залишку: savings = pool0 * savings_pct / 100, змінні = pool0 - savings
pct = float(snap.get('savings_pct', cfg.get('savings_pct', 0)) or 0)
savings = round(max(0.0, pool) * pct / 100, 2)
var_pool = max(0.0, pool - savings)
print(f"накопичення {pct:g}%: {savings:.2f}; змінні після накопичень: {var_pool:.2f}")
# біла картка: обовʼязкові без credit_ok (лише витрати), вікно whiteDue [max(now, start); end)
white = [o for o in obl if not o[3] and o[2] > 0]
obl_white = sum(o[2] for o in white)
w_from = max(now, period[0]) if now else period[0]
white_due = sum(o[2] for o in white if w_from <= o[0] < period[1])
cash_own = sum(float(a['balance']) for a in snap['accounts'] or [] if a.get('kind') != 'credit')
cash_now = cash_own - white_due
spent = float(snap.get('spent') or 0)
free_now = max(0.0, min(var_pool - spent, cash_now))
print(f"білі за період: {obl_white:.2f}; білі з {w_from} до {period[1]}: {white_due:.2f}; "
      f"власні не кредитних {cash_own:.2f}; cashNow {cash_now:.2f}; витрати {spent:.2f}; freeNow {free_now:.2f}")
# машинний рядок для spec/checks/budget.py
print('JSON ' + json.dumps({
    'payout': {'date': str(p_next[0]), 'kind': 'advance' if p_next[1] == 'аванс' else 'salary', 'amount': p_next[2]},
    'end': str(p_after[0]), 'obligations': [{'date': str(d), 'name': n, 'amount': a, 'creditOk': ok} for d, n, a, ok in obl],
    'oblSum': obl_sum, 'own': own, 'debt': debt, 'deficit': deficit, 'pool0': pool,
    'savings': savings, 'varPool': var_pool, 'oblWhite': obl_white, 'whiteDue': white_due, 'cashNow': cash_now,
    'spent': spent, 'freeNow': free_now}, ensure_ascii=False))
