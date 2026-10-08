# Змінний бюджет наступного періоду за правилом власника (08.10.2026):
#   бюджет = наступна виплата - обовʼязкові платежі до наступної виплати - поточний мінус
#   (мінус = борги мінус власні кошти, якщо більше нуля); результат <= 0 означає нуль і перенесення дефіциту.
# Правило «білої» картки (08.10.2026): білі обовʼязкові (credit_ok = false) йдуть лише з власних коштів
#   не кредитних рахунків; cashNow = ці кошти - білі з датою в [зараз; кінець періоду);
#   freeNow = max(0, min(varPool - spent, cashNow)). credit_ok за замовчуванням: fixed false,
#   credits true, якщо source містить 'privat'.
# Вхід: JSON {accounts, fixed, credits, salary, spent?, account_tx?} (знімок БД; spent: витрати періоду, за замовчуванням 0;
#   accounts[].min_spend, min_spend_fee: правило мінімальних витрат за місяць, п. 11).
# Похідний баланс ручних рахунків (як deriveAccounts у _shared/budget.ts): якщо є account_tx
#   (список {account_id, type, amount, created_at, date?}), рахунки без mono_account_id з id і balance_updated_at
#   отримують операції, створені строго після balance_updated_at: debit/cash balance - витрати + доходи,
#   credit debt + витрати - доходи (не менше 0). Без account_tx знімок рахується як раніше.
# Запуск: PYTHONUTF8=1 python scripts/budget_pool.py <snapshot.json> [YYYY-MM-DD сьогодні] [YYYY-MM-DD зараз]
#   «сьогодні» визначає період (виплата строго після нього), «зараз» початок вікна whiteDue (без нього весь період).
#   Застосунок і бот викликають з «сьогодні» = (остання виплата - 1 день), «зараз» = справжня дата: тоді поточний
#   період = [остання виплата; наступна), а «наступний» = [наступна; після неї).
#
# Правило власника (DESIGN.md, 08.10.2026, третя редакція, п. 1-10), поля останнього рядка 'JSON {...}':
#   own          Σ ефективних balance усіх активних рахунків знімка (як було, використовує deficit; кредитні дають 0)
#   ownDebit     Σ ефективних balance дебетових і готівкових рахунків (п. 2), без поправки unassigned
#   debt         Σ ефективних боргів активних рахунків (п. 2)
#   deficit      max(0, debt - own); pool0 бюджет без накопичень; savings накопичення;
#                varPool плановий бюджет періоду (= planCur, лишено для сумісності)
#   whiteDue     «білі» (без credit_ok, витрати) в [max(зараз; початок); кінець поточного періоду) (п. 3) плюс
#                погашення кредитки 25-го з цього вікна (п. 10), бо воно платиться з дебетових коштів;
#                борг уже погашено (debt_eff = 0): нічого не додається
#   cardRepayNow частина whiteDue, що є погашенням кредитки (0, якщо 25-те поза вікном [зараз; d1))
#   unassigned   знакова поправка п. 9: Σ(доходи - витрати) операцій account_tx без account_id (не source=mono),
#                створених строго після мінімального balance_updated_at ручних рахунків; 0, якщо account_tx немає
#   cashNow      ownDebit + unassigned - whiteDue (п. 4)
#   planCur      плановий бюджет поточного періоду (= varPool)
#   varPoolCur   обмежений бюджет (п. 5) = min(planCur, max(0, cashNow) + spent)
#   spent        витрати поточного періоду зі знімка
#   freeNow      «Вільно до виплати» (п. 6) = max(0, min(varPoolCur - spent, cashNow))
#   perDay       freeNow / днів від «зараз» до наступної виплати (п. 7), 0 якщо днів немає
#   shortage     -cashNow, якщо cashNow < 0, інакше 0 («Бракує N на білі платежі»)
#   nextPayout   {date, kind, amount} виплати, що завершує поточний період (d1)
#   planNext     плановий бюджет наступного періоду [d1; d2) за правилами періоду
#   whiteNext    «білі» обовʼязкові в [d1; d2)
#   cardRepayNext погашення кредитки 25-го в [d1; d2) (п. 10): debt_eff кредитних рахунків із debt_month раніше за
#                місяць події (лише для найближчої події від «зараз») + кредитні обовʼязкові (credit_ok, витрати)
#                з датою в попередньому місяці, що ще не настала; 0, якщо події у вікні немає
#   cashAtPayout залишок на d1 = max(0, cashNow - (varPoolCur - spent)) (п. 8)
#   varPoolNext  max(0, min(planNext, cashAtPayout + виплата d1 - whiteNext - cardRepayNext)) (п. 8)
#   minSpend     правило мінімальних витрат (п. 11): для активних рахунків з min_spend > 0 список
#                {accountId, month, spent, min, fee, left, metOn?}; spent = Σ витрат (type = 'expense') account_tx
#                з цим account_id і датою (поле date, без нього перші 10 знаків created_at) у місяці «зараз»;
#                left = max(0, min - spent); metOn: дата операції, на якій накопичена сума (порядок date, created_at,
#                amount) досягла min. Якщо left > 0, 1-го числа наступного місяця списується fee: подія «біла»,
#                входить у whiteDue (feeNow), якщо 1-ше в [зараз; d1), і у whiteNext (feeNext), якщо в [d1; d2)
#   Старі поля payout, end, obligations, oblSum, oblWhite, pool0, savings, ... лишаються без змін.
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

# поточний мінус (лише активні рахунки, як у застосунку)
ACCS = [a for a in snap['accounts'] or [] if a.get('active') is not False]
own = sum(float(a['balance']) for a in ACCS)
debt = sum(float(a['debt']) for a in ACCS)
net = own - debt
deficit = max(0.0, -net)


def in_window(day, start, end):
    """Дата платежу з днем місяця day у вікні [start, end)."""
    for y, m in [(start.year, start.month), (end.year, end.month)]:
        d = date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if start <= d < end:
            return d
    return None


def period_obl(start, end):
    """Обовʼязкові у вікні [start, end): постійні (дохід зі знаком мінус) і активні розстрочки."""
    res = []
    for f in snap['fixed'] or []:
        if f.get('active') is False:
            continue
        d = in_window(int(f['day_of_month']), start, end)
        if d:
            amt = float(f['amount'])
            res.append((d, f['name'], amt if f['type'] != 'income' else -amt, f.get('credit_ok') is True))
    for c in snap['credits'] or []:
        d = in_window(int(c['payment_day']), start, end)
        if d:
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
def card_repay(start, end):
    """Погашення кредитки 25-го числа в [start, end) (п. 10), див. шапку."""
    def ev(y, m):
        return date(y, m, min(25, calendar.monthrange(y, m)[1]))
    y, m = t_now.year, t_now.month
    first = ev(y, m)
    if first < t_now:
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
        first = ev(y, m)
    total = 0.0
    ey, em = start.year, start.month
    for _ in range(3):
        e = ev(ey, em)
        if start <= e < end:
            if e == first:
                for a in ACCS:
                    if a.get('kind') == 'credit' and a.get('debt_month') and str(a['debt_month'])[:7] < e.isoformat()[:7]:
                        total += float(a['debt'])
            m_start = date(ey, em, 1)
            p_start = date(ey - 1, 12, 1) if em == 1 else date(ey, em - 1, 1)
            for o in period_obl(max(p_start, t_now), m_start):
                if o[3] and o[2] > 0:
                    total += o[2]
        em += 1
        if em > 12:
            em, ey = 1, ey + 1
    return round(total, 2)


card_repay_now = card_repay(max(t_now, period[0]), d1)
white_due += card_repay_now


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


def min_spend_fee(start, end):
    """Сума комісій за недосягнутий поріг, якщо 1-ше наступного місяця в [start; end)."""
    if not (start <= fee_date < end):
        return 0.0
    return round(sum(r['fee'] for r in min_spend if r['left'] > 0 and r['fee'] > 0), 2)


fee_now = min_spend_fee(max(t_now, period[0]), d1)
white_due += fee_now
cash_now = cash_own + unassigned - white_due
plan_cur = var_pool
var_pool_cur = min(plan_cur, max(0.0, cash_now) + spent)  # п. 5
free_now = max(0.0, min(var_pool_cur - spent, cash_now))  # п. 6
shortage = -cash_now if cash_now < 0 else 0.0
days_left = max(0, (d1 - t_now).days)
per_day = free_now / days_left if days_left > 0 else 0.0  # п. 7
print(f"білі за період: {obl_white:.2f}; білі з {w_from} до {period[1]}: {white_due:.2f}; "
      f"власні не кредитних {cash_own:.2f}; без рахунку {unassigned:.2f}; cashNow {cash_now:.2f}; витрати {spent:.2f}; "
      f"бюджет обмежений {var_pool_cur:.2f}; freeNow {free_now:.2f}; на день {per_day:.2f}")

# п. 8, 10: наступний період [d1; d2)
d2 = future[2][0]
next_payout = p_after
obl_n = period_obl(d1, d2)
n_oblsum = sum(o[2] for o in obl_n)
n_pool0 = next_payout[2] - n_oblsum - deficit
n_savings = round(max(0.0, n_pool0) * pct / 100, 2)
plan_next = max(0.0, n_pool0 - n_savings)
white_next = sum(o[2] for o in obl_n if not o[3] and o[2] > 0)
fee_next = min_spend_fee(d1, d2)
white_next += fee_next


card_repay_next = card_repay(d1, d2)
cash_at_payout = max(0.0, cash_now - (var_pool_cur - spent))
var_pool_next = max(0.0, min(plan_next, cash_at_payout + next_payout[2] - white_next - card_repay_next))
for r in min_spend:
    print(f"мін. витрати рахунку {r['accountId']} за {r['month']}: {r['spent']:.2f} з {r['min']:.2f}, лишилось {r['left']:.2f}"
          + (f", досягнуто {r['metOn']}" if r.get('metOn') else f", інакше комісія {r['fee']:.2f} {fee_date}"))
print(f"наступний період {d1}..{d2}: плановий {plan_next:.2f}; білі {white_next:.2f}; погашення кредитки {card_repay_next:.2f}; "
      f"залишок на {d1} {cash_at_payout:.2f}; бюджет {var_pool_next:.2f}")
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
    'minSpend': min_spend, 'feeNow': fee_now, 'feeNext': fee_next}, ensure_ascii=False))
