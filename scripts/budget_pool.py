# Еталон грошової логіки (DESIGN.md, «Гроші по рахунках», третя редакція, п. 1-12; власник 08.10.2026).
# Правило каси (п. 12, варіант А): відсотків не платимо, усе, що лягло на кредитку за місяць M, гаситься власними
#   грошима 24-го числа M+1 (вихідні не зсуваються). Каса по датах: старт = ownDebit + unassigned «зараз», далі події до
#   горизонту, баланс після кожної. Бюджет періоду не більший за найнижчу касу від його початку до горизонту мінус
#   бюджети попередніх періодів (жадібно від поточного).
# Вхід: JSON {accounts, fixed, credits, salary, spent?, account_tx?} (знімок БД; spent: витрати періоду, за замовчуванням 0;
#   accounts[].min_spend, min_spend_fee: правило мінімальних витрат за місяць, п. 11).
# Похідний баланс ручних рахунків (як deriveAccounts у _shared/budget.ts): якщо є account_tx
#   (список {account_id, type, amount, created_at, date?}), рахунки без mono_account_id з id і balance_updated_at
#   отримують операції, створені строго після balance_updated_at: debit/cash balance - витрати + доходи,
#   credit debt + витрати - доходи (не менше 0) і кошики debt_months [[YYYY-MM, сума]]: збережений борг у місяці
#   debt_month (без нього місяць мітки), витрати за місяцем дати операції, доходи гасять найстаріші кошики.
# Запуск: PYTHONUTF8=1 python scripts/budget_pool.py <snapshot.json> [YYYY-MM-DD сьогодні] [YYYY-MM-DD зараз]
#   «сьогодні» визначає період (виплата строго після нього), «зараз» початок каси по датах (без нього початок періоду).
#   Застосунок і бот викликають з «сьогодні» = (остання виплата - 1 день), «зараз» = справжня дата: тоді поточний
#   період = [остання виплата d0; наступна d1), «наступний» = [d1; d2).
#
# Події каси (cash_events, п. 12), сортування (дата, виплата, дохід, біла, комісія, погашення, назва):
#   payout   виплати з датою строго після «зараз» (виплата сьогодні вже в балансі), плюс
#   income   постійні доходи в дату, плюс
#   white    обовʼязкові без credit_ok (витрати) у дату, з датою >= «зараз», мінус
#   repay    погашення кредитки 24-го M+1: кошики боргу кредитних рахунків за місяцем M (прострочене 24-те: «зараз»)
#            плюс обовʼязкові з credit_ok з датою >= «зараз» у місяці M (раніші вже в боргу рахунку), мінус
#   fee      комісія за недосягнутий поріг мінімальних витрат (п. 11) 1-го числа наступного місяця, мінус
# Горизонт: max(3-тя виплата після «зараз», найпізніше погашення в межах 60 днів), включно.
#
# Поля останнього рядка 'JSON {...}':
#   own, debt    Σ ефективних balance / debt активних рахунків; deficit max(0, debt - own) (довідково)
#   ownDebit     Σ ефективних balance дебетових і готівкових рахунків (п. 2), без поправки unassigned
#   unassigned   знакова поправка п. 9: Σ(доходи - витрати) операцій account_tx без account_id (не source=mono),
#                створених строго після мінімального balance_updated_at ручних рахунків; 0, якщо account_tx немає
#   startCash    ownDebit + unassigned; timeline [{date, amount, name, kind, balance}] події каси до horizon
#   pool0        виплата d0 - чисті відтоки каси в [d0; d1); savings накопичення; varPool = planCur = pool0 - savings
#   whiteDue     чисті відтоки каси в [зараз; d1) = startCash - cashBeforePayout
#   cardRepayNow погашення кредитки в [зараз; d1); feeNow комісія в [зараз; d1)
#   cashNow      = cashBeforePayout: каса напередодні d1; daysToPayout днів від «зараз» до d1
#   cashBeforeSalary, daysToSalary, salaryDate: те саме до найближчої виплати «зарплата»
#   minCash, minCashDate найнижча каса від «зараз» до горизонту (старт теж точка) і дата події
#   freeNow      max(0, min(planCur - spent, minCash)); varPoolCur = spent + freeNow; shortage = max(0, -minCash)
#   perDay       freeNow / daysToPayout (0, якщо днів немає)
#   planNext     виплата d1 - чисті відтоки [d1; d2) - накопичення; whiteNext білі [d1; d2) + feeNext;
#                cardRepayNext погашення в [d1; d2)
#   varPoolNext  max(0, min(planNext, найнижча каса від d1 - freeNow)); cashAtPayout max(0, cashNow - freeNow)
#   periods      [{start, end, payout, plan, budget}] від поточного до горизонту, бюджети жадібно
#   minSpend     правило мінімальних витрат (п. 11): для активних рахунків з min_spend > 0 список
#                {accountId, month, spent, min, fee, left, metOn?}; spent = Σ витрат (type = 'expense') account_tx
#                з цим account_id і датою (поле date, без нього перші 10 знаків created_at) у місяці «зараз»
#   Старі поля payout, end, obligations, oblSum, oblWhite лишаються.
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
        # кошики боргу за місяцем (п. 12): збережений борг у debt_month (без нього місяць мітки), витрати за датою операції
        bk = {str(a.get('debt_month') or '')[:7] or str(a['balance_updated_at'])[:7]: float(a.get('debt') or 0)}
        for t in txs or []:
            if t.get('account_id') is None or str(t['account_id']) != str(a['id']):
                continue
            if not parse_ts(t['created_at']) > since:
                continue
            if t.get('type') == 'income':
                inc += float(t['amount'])
            else:
                exp += float(t['amount'])
                m = str(t.get('date') or t['created_at'])[:7]
                bk[m] = bk.get(m, 0.0) + float(t['amount'])
        if a.get('kind') == 'credit':
            a2['debt'] = round(max(0.0, float(a['debt']) + exp - inc), 2)
            left = inc  # доходи (погашення) гасять найстаріші кошики
            out_b = []
            for m in sorted(bk):
                v = bk[m] - min(left, bk[m])
                left -= bk[m] - v
                if round(v, 2) > 0:
                    out_b.append([m, round(v, 2)])
            a2['debt_months'] = out_b
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

# поточний мінус (лише активні рахунки, як у застосунку)
ACCS = [a for a in snap['accounts'] or [] if a.get('active') is not False]
own = sum(float(a['balance']) for a in ACCS)
debt = sum(float(a['debt']) for a in ACCS)
net = own - debt
deficit = max(0.0, -net)


def months_span(start, end):
    """Місяці (y, m) від місяця start до місяця end включно."""
    k, last = start.year * 12 + start.month - 1, end.year * 12 + end.month - 1
    while k <= last:
        y, m = divmod(k, 12)
        yield y, m + 1
        k += 1


def period_obl(start, end):
    """Обовʼязкові у вікні [start, end): постійні (дохід зі знаком мінус) і активні розстрочки, помісячно (п. 12)."""
    res = []
    for y, m in months_span(start, end):
        last = calendar.monthrange(y, m)[1]
        for f in snap['fixed'] or []:
            if f.get('active') is False:
                continue
            d = date(y, m, min(int(f['day_of_month']), last))
            if start <= d < end:
                amt = float(f['amount'])
                res.append((d, f['name'], amt if f['type'] != 'income' else -amt, f.get('credit_ok') is True))
        for c in snap['credits'] or []:
            d = date(y, m, min(int(c['payment_day']), last))
            if not (start <= d < end):
                continue
            first = c['start_year'] * 12 + c['start_month']
            cur = d.year * 12 + (d.month - 1)
            if first <= cur <= first + int(c['total_payments']) - 1:
                ok = c.get('credit_ok')
                ok = bool(ok) if ok is not None else 'privat' in str(c.get('source') or '').lower()
                res.append((d, c['name'] + ' (розстрочка)', float(c['monthly_amount']), ok))
    res.sort(key=lambda o: (o[0], o[1]))
    return res


obl = period_obl(*period)
obl_sum = sum(o[2] for o in obl)
pct = float(snap.get('savings_pct', cfg.get('savings_pct', 0)) or 0)
cash_own = sum(float(a['balance']) for a in ACCS if a.get('kind') != 'credit')

# п. 9: операції без рахунку (лише після мінімального balance_updated_at ручних рахунків, не mono)
unassigned = 0.0
manual = [parse_ts(a['balance_updated_at']) for a in ACCS if not a.get('mono_account_id') and a.get('balance_updated_at')]
if snap.get('account_tx') is not None and manual:
    since = min(manual)
    for t in snap['account_tx']:
        if t.get('account_id') is not None or t.get('source') == 'mono' or not parse_ts(t['created_at']) > since:
            continue
        unassigned += float(t['amount']) if t.get('type') == 'income' else -float(t['amount'])
    unassigned = round(unassigned, 2)

spent = float(snap.get('spent') or 0)
d1 = period[1]
t_now = now or period[0]


def tx_day(t):
    """Дата операції: поле date, без нього перші 10 знаків created_at."""
    return str(t.get('date') or t.get('created_at') or '')[:10]


def min_spend_rows():
    """п. 11: поріг мінімальних витрат за календарний місяць t_now для рахунків з min_spend > 0."""
    month = t_now.isoformat()[:7]
    rows = []
    for a in ACCS:
        mn = float(a.get('min_spend') or 0)
        if mn <= 0 or a.get('id') is None:
            continue
        # id порівнюється рядком: у демо-знімку id рахунків текстові (l1), у БД числові
        txs = [t for t in snap.get('account_tx') or [] if t.get('account_id') is not None and str(t['account_id']) == str(a['id'])
               and t.get('type') == 'expense' and tx_day(t)[:7] == month]
        txs.sort(key=lambda t: (tx_day(t), str(t.get('created_at') or ''), float(t['amount'])))
        cum, met = 0.0, None
        for t in txs:
            cum += float(t['amount'])
            if met is None and cum >= mn - 1e-9:
                met = tx_day(t)
        aid = int(a['id']) if str(a['id']).isdigit() else a['id']
        row = {'accountId': aid, 'month': month, 'spent': round(cum, 2), 'min': mn,
               'fee': float(a.get('min_spend_fee') or 0), 'left': round(max(0.0, mn - cum), 2)}
        if met:
            row['metOn'] = met
        rows.append(row)
    return rows


min_spend = min_spend_rows()
fee_date = date(t_now.year + (t_now.month == 12), t_now.month % 12 + 1, 1)  # найближче 1-ше строго після t_now
fee_total = round(sum(r['fee'] for r in min_spend if r['left'] > 0 and r['fee'] > 0), 2)


def min_spend_fee(start, end):
    """Сума комісій за недосягнутий поріг, якщо 1-ше наступного місяця в [start; end)."""
    return fee_total if start <= fee_date < end else 0.0


# п. 12: каса по датах. Борг кредитного рахунку за місяць M гаситься 24-го M+1 (прострочене: «зараз»)
def repay_date(month):
    y, m = int(month[:4]), int(month[5:7])
    y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    d = date(y, m, 24)
    return d if d >= t_now else t_now


def debt_buckets(a):
    """Кошики боргу [(YYYY-MM, сума)]: з derive_accounts (debt_months) або весь борг у місяці debt_month
    (без нього місяць мітки balance_updated_at, без неї місяць «зараз»)."""
    b = a.get('debt_months')
    if b is None:
        m = str(a.get('debt_month') or '')[:7] or str(a.get('balance_updated_at') or '')[:7] or t_now.isoformat()[:7]
        b = [[m, float(a.get('debt') or 0)]]
    return [(m, float(v)) for m, v in b if float(v) > 0]


def all_payouts(lo, hi):
    """Виплати з датою в [lo; hi] і строго після t_now: (дата, назва, сума)."""
    out = []
    for y, m in months_span(date(lo.year, lo.month, 1) - timedelta(days=1), hi + timedelta(days=31)):
        out += [p for p in payouts(y, m) if lo <= p[0] <= hi and p[0] > t_now]
    return sorted(out)


KIND_ORDER = {'payout': 0, 'income': 1, 'white': 2, 'fee': 3, 'repay': 4}


def cash_events(lo, hi):
    """Події каси з датою в [lo; hi] (п. 12): виплати (після «зараз») плюс, постійні доходи плюс, білі мінус у дату,
    кредитні обовʼязкові з датою >= «зараз» і борг кредитних рахунків мінус 24-го M+1, комісія п. 11 мінус 1-го."""
    ev = []
    for d, n, a in all_payouts(lo, hi):
        ev.append({'date': d, 'amount': a, 'name': n, 'kind': 'payout', 'payout': 'advance' if n == 'аванс' else 'salary'})
    for d, n, a, ok in period_obl(lo, hi + timedelta(days=1)):
        if a < 0:
            ev.append({'date': d, 'amount': -a, 'name': n, 'kind': 'income'})
        elif not ok:
            ev.append({'date': d, 'amount': -a, 'name': n, 'kind': 'white'})
    rep = {}
    if hi >= t_now:
        for d, n, a, ok in period_obl(t_now, hi + timedelta(days=1)):
            if ok and a > 0:
                r = repay_date(d.isoformat()[:7])
                if lo <= r <= hi:
                    rep[r] = rep.get(r, 0.0) + a
        for a in ACCS:
            if a.get('kind') != 'credit':
                continue
            for m, v in debt_buckets(a):
                r = repay_date(m)
                if lo <= r <= hi:
                    rep[r] = rep.get(r, 0.0) + v
    for r, v in rep.items():
        if round(v, 2) > 0:
            ev.append({'date': r, 'amount': -round(v, 2), 'name': 'Погашення кредитки', 'kind': 'repay'})
    if fee_total > 0 and lo <= fee_date <= hi:
        ev.append({'date': fee_date, 'amount': -fee_total, 'name': 'Комісія за мінімальні витрати', 'kind': 'fee'})
    ev.sort(key=lambda e: (e['date'], KIND_ORDER[e['kind']], e['name']))
    return ev


def net_out(a, b):
    """Чисті відтоки каси (без виплат) у [a; b)."""
    return round(-sum(e['amount'] for e in cash_events(a, b - timedelta(days=1)) if e['kind'] != 'payout'), 2)


def plan_of(payout_amt, a, b):
    """План періоду [a; b): виплата - відтоки каси - накопичення (п. 12). Повертає (pool0, savings, план)."""
    p0 = round(payout_amt - net_out(a, b), 2)
    sv = round(max(0.0, p0) * pct / 100, 2)
    return p0, sv, max(0.0, p0 - sv)


# горизонт: не менше 3 виплат після «зараз» і до найпізнішого погашення в межах 60 днів, включно
fut_now = all_payouts(t_now, t_now + timedelta(days=120))
p3 = fut_now[2][0]
lim = t_now + timedelta(days=60)
ev_all = cash_events(t_now, max(p3, lim))
horizon = max([p3] + [e['date'] for e in ev_all if e['kind'] == 'repay' and e['date'] <= lim])
start_cash = round(cash_own + unassigned, 2)
timeline, bal = [], start_cash
for e in ev_all:
    if e['date'] > horizon:
        break
    bal = round(bal + e['amount'], 2)
    timeline.append({**e, 'date': str(e['date']), 'balance': bal})
min_cash, min_cash_date = start_cash, str(t_now)
for e in timeline:
    if e['balance'] < min_cash - 1e-9:
        min_cash, min_cash_date = e['balance'], e['date']


def cash_before(d):
    """Каса напередодні дати d: баланс після всіх подій з датою < d."""
    b = start_cash
    for e in timeline:
        if e['date'] < str(d):
            b = e['balance']
    return b


def min_from(d):
    """Найнижча каса від дати d (події з датою >= d) до горизонту; подій немає: каса напередодні d."""
    vals = [e['balance'] for e in timeline if e['date'] >= str(d)]
    return min(vals) if vals else cash_before(d)


pool, savings, var_pool = plan_of(p_next[2], period[0], d1)
print(f"сьогодні {today}; власні кошти {own:.2f}, борги {debt:.2f}, нетто {net:.2f}, мінус до перекриття {deficit:.2f}")
print(f"поточна виплата: {p_next[1]} {p_next[0]} = {p_next[2]:.2f}; період до {p_after[0]} ({p_after[1]})")
for d, n, a, ok in obl:
    print(f"  {d}  {n:<32} {a:>10.2f}  {'кредитна, гаситься 24-го наступного місяця' if ok else 'біла'}")
print(f"обовʼязкові за період: {obl_sum:.2f}; відтоки каси за період {net_out(period[0], d1):.2f}")
print(f"план періоду: {max(0.0, pool):.2f}; накопичення {pct:g}%: {savings:.2f}; змінні після накопичень: {var_pool:.2f}")
obl_white = sum(o[2] for o in obl if not o[3] and o[2] > 0)

cash_now = cash_before(d1)  # каса напередодні наступної виплати
white_due = round(start_cash - cash_now, 2)  # чисті відтоки каси в [зараз; d1)
card_repay_now = round(-sum(e['amount'] for e in timeline if e['kind'] == 'repay' and e['date'] < str(d1)), 2)
fee_now = min_spend_fee(t_now, d1)
plan_cur = var_pool
free_now = max(0.0, min(plan_cur - spent, min_cash))  # п. 12
var_pool_cur = spent + free_now
shortage = max(0.0, -min_cash)
days_left = max(0, (d1 - t_now).days)
per_day = free_now / days_left if days_left > 0 else 0.0
print(f"каса зараз (власні {cash_own:.2f} + без рахунку {unassigned:.2f}) {start_cash:.2f}; горизонт {horizon}")
for e in timeline:
    print(f"  {e['date']}  {e['amount']:>+12.2f}  {e['balance']:>12.2f}  {e['kind']:<6} {e['name']}")
print(f"найнижча каса {min_cash:.2f} ({min_cash_date}); каса до {d1} {cash_now:.2f}; витрати {spent:.2f}; "
      f"бюджет {var_pool_cur:.2f}; freeNow {free_now:.2f}; на день {per_day:.2f}")

# наступний період [d1; d2) і далі жадібно до горизонту
d2 = future[2][0]
next_payout = p_after
n_pool0, n_savings, plan_next = plan_of(next_payout[2], d1, d2)
fee_next = min_spend_fee(d1, d2)
white_next = round(sum(o[2] for o in period_obl(d1, d2) if not o[3] and o[2] > 0) + fee_next, 2)
card_repay_next = round(-sum(e['amount'] for e in cash_events(d1, d2 - timedelta(days=1)) if e['kind'] == 'repay'), 2)
cash_at_payout = max(0.0, cash_now - free_now)
var_pool_next = max(0.0, min(plan_next, min_from(d1) - free_now))
periods = [{'start': str(period[0]), 'end': str(d1), 'payout': p_next[2], 'plan': plan_cur, 'budget': var_pool_cur}]
used = free_now
bounds = [d1] + [p[0] for p in fut_now if p[0] > d1]
pmap = {p[0]: p for p in fut_now}
for i in range(len(bounds) - 1):
    s, e = bounds[i], bounds[i + 1]
    if s > horizon:
        break
    pl = plan_of(pmap[s][2], s, e)[2]
    b = var_pool_next if i == 0 else max(0.0, min(pl, min_from(s) - used))
    used += b
    periods.append({'start': str(s), 'end': str(e), 'payout': pmap[s][2], 'plan': pl, 'budget': b})
sal = next((p for p in fut_now if p[1] == 'зарплата'), None)
cash_before_salary = cash_before(sal[0]) if sal else None
days_to_salary = (sal[0] - t_now).days if sal else None
for r in min_spend:
    print(f"мін. витрати рахунку {r['accountId']} за {r['month']}: {r['spent']:.2f} з {r['min']:.2f}, лишилось {r['left']:.2f}"
          + (f", досягнуто {r['metOn']}" if r.get('metOn') else f", інакше комісія {r['fee']:.2f} {fee_date}"))
print(f"наступний період {d1}..{d2}: план {plan_next:.2f}; найнижча каса від {d1} {min_from(d1):.2f}; бюджет {var_pool_next:.2f}")
print(f"до виплати {d1} ({days_left} дн.): каса {cash_now:.2f}; до зарплати {sal[0] if sal else '-'} ({days_to_salary} дн.): каса {cash_before_salary}")
for p in periods:
    print(f"  період {p['start']}..{p['end']}: план {p['plan']:.2f}, бюджет {p['budget']:.2f}")
# машинний рядок для spec/checks/budget.py
print('JSON ' + json.dumps({
    'payout': {'date': str(p_next[0]), 'kind': 'advance' if p_next[1] == 'аванс' else 'salary', 'amount': p_next[2]},
    'end': str(p_after[0]), 'obligations': [{'date': str(d), 'name': n, 'amount': a, 'creditOk': ok} for d, n, a, ok in obl],
    'oblSum': obl_sum, 'own': own, 'debt': debt, 'deficit': deficit, 'pool0': pool,
    'savings': savings, 'varPool': var_pool, 'oblWhite': obl_white, 'whiteDue': white_due, 'cashNow': cash_now,
    'spent': spent, 'freeNow': free_now,
    'ownDebit': cash_own, 'unassigned': unassigned, 'planCur': plan_cur, 'varPoolCur': var_pool_cur,
    'perDay': per_day, 'shortage': shortage,
    'nextPayout': {'date': str(next_payout[0]), 'kind': 'advance' if next_payout[1] == 'аванс' else 'salary', 'amount': next_payout[2]},
    'planNext': plan_next, 'whiteNext': white_next, 'cardRepayNext': card_repay_next,
    'cardRepayNow': card_repay_now, 'cashAtPayout': cash_at_payout, 'varPoolNext': var_pool_next,
    'minSpend': min_spend, 'feeNow': fee_now, 'feeNext': fee_next,
    'cashBeforePayout': cash_now, 'daysToPayout': days_left, 'cashBeforeSalary': cash_before_salary,
    'daysToSalary': days_to_salary, 'salaryDate': str(sal[0]) if sal else None, 'minCash': min_cash, 'minCashDate': min_cash_date,
    'horizon': str(horizon), 'startCash': start_cash, 'timeline': timeline, 'periods': periods}, ensure_ascii=False))
