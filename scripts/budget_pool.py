# Активний еталон: finance_projection / --finance, контракт docs/redesign/projection-contract.md (10.10.2026).
# Нижче також збережено історичний CLI та його опис для сумісності з попередніми перевірками.
# Правило каси (п. 12, варіант А): відсотків не платимо, усе, що лягло на кредитку за місяць M, гаситься власними
#   грошима з виплати 21-го числа M+1 (v147: одне правило repay_plan, як repayDate у budget.ts; субота й неділя
#   зсуваються, як сама виплата). Каса по датах: старт = ownDebit + unassigned «зараз», далі події до
#   горизонту, баланс після кожної. Бюджет періоду не більший за найнижчу касу від його початку до горизонту мінус
#   бюджети попередніх періодів (жадібно від поточного).
# Вхід: JSON {accounts, fixed, credits, salary, spent?, account_tx?} (знімок БД; spent: витрати періоду, за замовчуванням 0;
#   accounts[].min_spend, min_spend_fee: правило мінімальних витрат за місяць, п. 11).
# Похідний баланс ручних рахунків (як deriveAccounts у _shared/budget.ts): якщо є account_tx
#   (список {account_id, type, amount, created_at, date?}), рахунки без mono_account_id з id і balance_updated_at
#   отримують операції, створені строго після balance_updated_at: debit/cash balance - витрати + доходи,
#   credit спершу витрачає власний залишок, дохід спершу гасить борг; кошики debt_months [[YYYY-MM, сума]]: борг у місяці
#   debt_month (без нього місяць мітки), витрати за місяцем дати операції, доходи гасять найстаріші кошики.
# Оплата постійного платежу (п. 13): fixed[] містить id і variable (сума змінна, amount = середня; на розрахунок не
#   впливає), account_tx[] містить fixed_id. Операція type = 'expense' з fixed_id = f.id і датою (поле date, без нього
#   перші 10 знаків created_at) у місяці M закриває платіж f місяця M: його немає в обовʼязкових, білих, погашеннях і касі
#   по датах (факт уже зменшив баланс рахунку). Оплата раніше дати платежу теж закриває місяць. Майбутні місяці: amount.
#   Знімок мусить містити привʼязані операції всіх місяців вікна (від місяця «сьогодні»).
# Запуск: PYTHONUTF8=1 python scripts/budget_pool.py <snapshot.json> [YYYY-MM-DD сьогодні] [YYYY-MM-DD зараз]
#   «сьогодні» визначає період (виплата строго після нього), «зараз» початок каси по датах (без нього початок періоду).
#   Застосунок і бот викликають з «сьогодні» = (остання виплата - 1 день), «зараз» = справжня дата: тоді поточний
#   період = [остання виплата d0; наступна d1), «наступний» = [d1; d2).
#
# Події каси (cash_events, п. 12), сортування (дата, виплата, дохід, біла, комісія, погашення, назва):
#   payout   виплати з датою строго після «зараз» (виплата сьогодні вже в балансі), плюс
#   income   постійні доходи в дату, плюс
#   white    обовʼязкові без credit_ok (витрати) у дату, з датою >= «зараз», мінус
#   repay    погашення кредитки з виплати 21-го M+1: кошики боргу кредитних рахунків за місяцем M (минуле: «зараз»)
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
#   paidFixed    п. 13: [[id, YYYY-MM]] оплачених постійних платежів (відсортовано)
#   Старі поля payout, end, obligations, oblSum, oblWhite лишаються.
import calendar, json, math, re, sys
from datetime import date, datetime, timedelta


def salary_period_amount(cfg, y, m, lo, hi, fixed):
    """Ставка за робочими днями; до першої зміни діє базова ставка або фіксована сума."""
    base = float(cfg.get('rate') or 0)
    work = [date(y, m, d) for d in range(lo, hi + 1) if date(y, m, d).weekday() < 5]
    total = sum(date(y, m, d).weekday() < 5 for d in range(1, calendar.monthrange(y, m)[1] + 1))
    end = date(y, m, hi).isoformat()
    schedule = sorted([x for x in (cfg.get('rate_schedule') or []) if x.get('effective_from', '') <= end and float(x.get('rate') or 0) > 0], key=lambda x: x['effective_from'])
    if not schedule:
        return math.floor(base / total * len(work) * 100 + 0.5) / 100 if base > 0 else float(fixed or 0)
    weighted, fixed_days = 0, 0
    for day in work:
        active = [x for x in schedule if x['effective_from'] <= day.isoformat()]
        rate = float(active[-1]['rate']) if active else base
        if rate > 0:
            weighted += rate
        else:
            fixed_days += 1
    return math.floor((weighted / total + (fixed_days / len(work) * float(fixed or 0) if work else 0)) * 100 + 0.5) / 100


def repay_plan(month, now=''):
    """v147: єдине правило погашення (дзеркало repayDate у budget.ts): борг місяця M гаситься з виплати 21-го в M+1,
    субота й неділя зсуваються, як сама виплата; минула дата гаситься «зараз» (з now '' дата без зсуву на «зараз»)."""
    y, m = int(month[:4]), int(month[5:7])
    d = date(y + m // 12, m % 12 + 1, 21)
    w = d.weekday()
    s = (d + timedelta(days=-1 if w == 5 else 1 if w == 6 else 0)).isoformat()
    return now if now and s < now else s


def parse_ts(s):
    """Мітка часу Postgres/ISO (+00:00, +00, Z) з точністю до мілісекунд, як Date.parse у TS."""
    s = str(s).strip().replace(' ', 'T', 1)
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    t = datetime.fromisoformat(s)
    return t.replace(microsecond=t.microsecond // 1000 * 1000)


def week_day(f):
    """ISO-день тижня щотижневого постійного платежу (1=пн..7=нд) або None: без коректного weekday подій немає."""
    try:
        w = float(f.get('weekday'))
    except (TypeError, ValueError):
        return None
    return int(w) if w.is_integer() and 1 <= w <= 7 else None


def fixed_ended(f, d):
    """Дата d (date або YYYY-MM-DD) після end_date постійного платежу: подія не генерується; end_date включно, порожня: безстроково (міграція 29)."""
    e = str(f.get('end_date') or '')[:10]
    return bool(e) and (d if isinstance(d, str) else d.isoformat()) > e


def payment_day(t):
    """Дата зобовʼязання; фактична дата операції для каси залишається незмінною."""
    return str(t.get('payment_due_date') or t.get('date') or t.get('created_at') or '')[:10]


def fixed_in_month(f, month):
    """Річний платіж виникає лише у вибраному місяці (1..12)."""
    return f.get('period') != 'year' or str(f.get('month_of_year')) == str(month)


def week_key(day):
    """Ключ тижня оплати: 'W' + понеділок тижня дати YYYY-MM-DD; некоректна дата: None."""
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        return None
    d = date.fromisoformat(day)
    return 'W' + (d - timedelta(days=d.weekday())).isoformat()


def derive_accounts(accounts, txs):
    """????? ???????: ?????? ?????, ???? ?? FIFO ? ?????????; Monobank ??? ??? ???? ? ???????."""
    out = []
    for a in accounts or []:
        row = dict(a); out.append(row)
        if a.get('mono_account_id') or a.get('id') is None or not a.get('balance_updated_at'): continue
        try: since = parse_ts(a['balance_updated_at'])
        except ValueError: continue
        balance, debt = float(a.get('balance') or 0), max(0, float(a.get('debt') or 0))
        buckets = {str(a.get('debt_month') or a['balance_updated_at'])[:7]: debt}
        rows = sorted([t for t in txs or [] if t.get('account_id') is not None and str(t['account_id']) == str(a['id']) and parse_ts(t['created_at']) > since], key=lambda t: (parse_ts(t['created_at']), str(t.get('id') or '')))
        for t in rows:
            amount = float(t.get('amount') or 0)
            if a.get('kind') != 'credit':
                balance += amount if t.get('type') == 'income' else -amount
            elif t.get('type') == 'income':
                left = amount
                for month in sorted(buckets):
                    used = min(left, buckets[month]); buckets[month] -= used; debt -= used; left -= used
                balance += left
            else:
                own = min(max(0, balance), amount); borrowed = amount-own; balance -= own; debt += borrowed
                month = str(t.get('date') or t['created_at'])[:7]; buckets[month] = buckets.get(month, 0)+borrowed
        row['balance'] = round(balance, 2)
        if a.get('kind') == 'credit':
            row['debt'] = round(debt, 2)
            row['debt_months'] = [[m, round(buckets[m], 2)] for m in sorted(buckets) if round(buckets[m], 2) > 0]
    return out


def next_period_plan(data, asof):
    """Новий план після резервування; *Cents: копійки, averageDailyCents: середнє.
    salary: salary_config; remainingCents не є банківською касою по датах.
    Немає відомої майбутньої виплати: {plan: None, reason: no_next_payout}.
    """
    from decimal import Decimal, ROUND_HALF_UP
    def safe(n):
        if abs(n) > 9007199254740991:
            raise ValueError('Unsafe cents')
        return n
    def cents(n):
        return safe(int((Decimal(str(n or 0)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    def total(values):
        return safe(sum(values))
    current = date.fromisoformat(asof)
    cfg = data.get('salary')
    missing = {'plan': None, 'reason': 'no_next_payout'}
    def valid_day(value):
        try:
            n = float(value)
            return n.is_integer() and 1 <= n <= 31
        except (ValueError, TypeError):
            return False
    if not cfg or any(not valid_day(cfg.get(k)) for k in ('advance_day', 'salary_day', 'split_day')):
        return missing
    upcoming = []
    rate = float(cfg.get('rate') or 0)
    def weekdays(y, m, lo, hi):
        return sum((date(y,m,1)+timedelta(days=d-1)).weekday() < 5 for d in range(lo,hi+1))
    for i in range(-1, 3):
        y, m0 = divmod(current.year*12+current.month-1+i,12)
        m = m0+1
        py, pm = (y,m-1) if m>1 else (y-1,12)
        for kind in ('advance','salary'):
            d = date(y,m,1)+timedelta(days=int(cfg[kind+'_day'])-1)
            d += timedelta(days=-1 if d.weekday()==5 else 1 if d.weekday()==6 else 0)
            sy,sm = (y,m) if kind=='advance' else (py,pm)
            last = calendar.monthrange(sy,sm)[1]
            lo,hi = (1,int(cfg['split_day'])) if kind=='advance' else (int(cfg['split_day'])+1,last)
            amount = salary_period_amount(cfg,sy,sm,lo,hi,cfg.get(kind+'_amount'))
            if d>current and amount>0:
                upcoming.append({'date':d.isoformat(),'kind':kind,'amount':amount,'amountCents':cents(amount)})
    upcoming.sort(key=lambda p:p['date'])
    if not upcoming:
        return missing
    nxt = upcoming[0]
    after = next((p for p in upcoming if p['date']>nxt['date']),None)
    if not after:
        return missing
    if data.get('monthly_budgets') and monthly_period_budget(data['monthly_budgets'],nxt['date'],after['date'])['covered']:
        return finance_projection(data,{'asof':asof,'through':after['date']})['nextPlan']
    start,end = date.fromisoformat(nxt['date']),date.fromisoformat(after['date'])
    txs = data.get('transactions',data.get('account_tx',[]))
    accounts = [a for a in derive_accounts(data.get('accounts',[]),txs) if a.get('active') is not False]
    stamps = [parse_ts(a['balance_updated_at']) for a in accounts if not a.get('mono_account_id') and a.get('balance_updated_at')]
    adjustment = cents(sum(float(t['amount'])*(1 if t.get('type')=='income' else -1) for t in txs if t.get('account_id') is None and t.get('source')!='mono' and stamps and parse_ts(t['created_at'])>min(stamps)))
    own = max(0,total([max(0,cents(a.get('balance'))) for a in accounts]+[adjustment]))
    debt = total(max(0,cents(a.get('debt'))) for a in accounts if a.get('kind')=='credit')
    paid = {(str(t['fixed_id']),payment_day(t)[:7]) for t in txs if t.get('fixed_id') is not None and t.get('type')=='expense'}
    paid |= {(str(t['fixed_id']),week_key(payment_day(t))) for t in txs if t.get('fixed_id') is not None and t.get('type')=='expense'}
    paid_credit = {(str(t['credit_id']),payment_day(t)[:7]) for t in txs if t.get('credit_id') is not None and t.get('type')=='expense'}
    entries = []
    for k in range(start.year*12+start.month-1,end.year*12+end.month):
        y,m0=divmod(k,12); m=m0+1; last=calendar.monthrange(y,m)[1]
        for f in data.get('fixed',[]):
            if f.get('active') is False or f.get('period')=='week' or not fixed_in_month(f,m) or (str(f.get('id')),f'{y:04d}-{m:02d}') in paid:
                continue
            d=date(y,m,min(int(f['day_of_month']),last))
            if start<=d<end and not fixed_ended(f,d):
                entries.append((cents(f['amount'])*(-1 if f['type']=='income' else 1),f.get('credit_ok') is True))
        for c in data.get('credits',[]):
            d=date(y,m,min(int(c['payment_day']),last)); first=int(c['start_year'])*12+int(c['start_month'])
            if start<=d<end and first<=k<first+int(c['total_payments']) and (str(c.get('id')),f'{y:04d}-{m:02d}') not in paid_credit:
                entries.append((cents(c['monthly_amount']),c.get('credit_ok') is True))
    # щотижневі постійні: кожна дата з ISO-днем weekday у [start; end), оплачений тиждень пропускаємо
    for f in data.get('fixed',[]):
        w=week_day(f)
        if f.get('active') is False or f.get('period')!='week' or w is None:
            continue
        d=start+timedelta(days=(w-1-start.weekday())%7)
        while d<end and not fixed_ended(f,d):
            if (str(f.get('id')),week_key(d.isoformat())) not in paid:
                entries.append((cents(f['amount'])*(-1 if f['type']=='income' else 1),f.get('credit_ok') is True))
            d+=timedelta(days=7)
    mandatory=total(a for a,_ in entries if a>0)
    income=total(-a for a,_ in entries if a<0)
    eligible=total(a for a,ok in entries if a>0 and ok)
    base=total([total([own,nxt['amountCents']]),-total([mandatory,debt])])
    target=max(1500000,base); gap=total([target,-base]); days=(end-start).days
    # категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit
    expense_cats=[c for c in data.get('categories',[]) if c.get('active') is not False and c.get('type')=='expense' and not c.get('budget_role') and not (str(c.get('id'))=='savings' or __import__('unicodedata').normalize('NFKC',str(c.get('name') or '')).strip().lower()=='заощадження')]
    categories=sorted([{'id':str(c['id']),'name':c.get('name') or '','weight':0,'limitAbsCents':max(0,cents(c['limit_abs']))} if c.get('limit_abs') is not None else {'id':str(c['id']),'name':c.get('name') or '', 'weight':max(0,cents(c.get('budget_limit') if c.get('budget_limit') is not None else c.get('limit')))/100} for c in expense_cats],key=lambda c:c['id'])
    if len({c['id'] for c in categories})!=len(categories): raise ValueError('Duplicate category id')
    # черга сум у гривнях: sort_order (None в кінці), при рівності id
    abs_order=[next(i for i,x in enumerate(categories) if x['id']==str(c['id'])) for c in sorted([c for c in expense_cats if c.get('limit_abs') is not None],key=lambda c:(c.get('sort_order') is None,float(c['sort_order']) if c.get('sort_order') is not None else 0,str(c['id'])))]
    if not abs_order and not any(c['weight']>0 for c in categories): categories = [{'id':'unallocated','name':'Не розподілено','weight':1}]
    def allocate(amount,weights):
        if amount==0: return [0]*len(weights)
        denominator=sum(weights)
        values=[amount*w//denominator for w in weights]
        order=sorted(range(len(weights)),key=lambda i:(-(amount*weights[i]%denominator),i))
        for i in order[:amount-sum(values)]: values[i]+=1
        return values
    # суми в гривнях по черзі min(ліміт, що лишилось), залишок за вагами; ваг немає: «Не розподілено»
    if not abs_order: totals=allocate(target,[cents(c['weight']) for c in categories])
    else:
        totals=[0]*len(categories); weights=[0 if 'limitAbsCents' in c else cents(c['weight']) for c in categories]; left=target
        for i in abs_order:
            n=min(categories[i]['limitAbsCents'],left); totals[i]=n; left-=n
        if any(w>0 for w in weights): totals=[t+a for t,a in zip(totals,allocate(left,weights))]
        elif left>0: categories=categories+[{'id':'unallocated','name':'Не розподілено','weight':1}]; totals.append(left)
    remaining=totals[:]; balance=base; schedule=[]
    for day in range(days):
        spend=target//days+int(day<target%days)
        amounts=remaining[:] if day==days-1 else allocate(spend,remaining)
        remaining=[v-a for v,a in zip(remaining,amounts)]; balance=total([balance,-spend])
        schedule.append({'date':(start+timedelta(days=day)).isoformat(),'spendCents':spend,'remainingCents':balance,'byCategory':[{'id':c['id'],'name':c['name'],'amountCents':a} for c,a in zip(categories,amounts)]})
    return {'start':start.isoformat(),'end':end.isoformat(),'days':days,'nextPayout':nxt,'followingPayout':after,'positiveOwnCents':own,'debtCents':debt,'mandatoryCents':mandatory,'otherIncomeCents':income,'eligibleMandatoryCents':eligible,'baseAvailableCents':base,'targetCents':target,'gapCents':gap,'averageDailyCents':target/days,'categories':[{**c,'totalCents':a} for c,a in zip(categories,totals)],'schedule':schedule}


def payout_budget(own, reserve, debt, due, repay_day, manual=None):
    """v151: розподіл виплати за правилом власника (дзеркало payoutBudget у budget.ts): погашення, A і бюджет min(20 000, A), якщо A > 15 000, інакше 15 000.
    v153: спершу резерв і бюджет (авто 15 000 або ручна сума manual), погашення min(борг, max(0, власні − резерв − бюджет)), непокрите належне dueShortCents"""
    man = manual is not None and manual >= 0
    base = manual if man else 1500000
    debt = max(0, debt)
    free = own - reserve
    repay = min(debt, max(0, free - base)) if repay_day else 0
    available = free - repay
    return {'repayCents': repay, 'dueShortCents': max(0, min(max(0, due), debt) - repay) if repay_day else 0, 'availableCents': available,
            'targetCents': base if man else (min(2000000, available) if available > 1500000 else 1500000)}


def monthly_period_budget(rows, start, end, options=None):
    """Точні копійки місячного плану на піввідкритий період; майбутнє успадковує останній план."""
    options = options or {}
    days = lambda a, b: (date.fromisoformat(b)-date.fromisoformat(a)).days
    def valid(n):
        v = float(n)
        if not v.is_integer() or v < 0 or v > 9007199254740991: raise ValueError('Invalid monthly budget cents')
        return int(v)
    prefix = lambda n, a, b, d: n*b//d-n*a//d
    savings_ids=[str(c.get('id')) for c in options.get('categories',[]) if not c.get('is_income') and not c.get('isIncome') and c.get('type')!='income' and (str(c.get('id'))=='savings' or __import__('unicodedata').normalize('NFKC',str(c.get('name') or '')).strip().lower()=='заощадження')]
    debt_ids=[str(c.get('id')) for c in options.get('categories',[]) if c.get('budget_role') in ('debt_card','debt_installment')]
    saved = sorted(rows or [], key=lambda r: str(r['month_start']))
    span = days(start,end)
    if span < 0: raise ValueError('Invalid budget period')
    cursor, unallocated, covered, totals, segments = start, 0, False, {}, []
    while cursor < end:
        dt = date.fromisoformat(cursor); month = cursor[:7]+'-01'
        following = date(dt.year+(dt.month==12),dt.month%12+1,1).isoformat(); stop = min(following,end)
        D,a,b = days(month,following),days(month,cursor),days(month,stop)
        row = next((r for r in reversed(saved) if str(r['month_start'])<=month),None)
        source, estimated = None,False
        if row is not None:
            covered=True; source=str(row['month_start']); estimated=source!=month
            pool=max(0,valid(row['total_cents'])-sum(valid(x['amount_cents']) for x in row.get('mandatory_items') or []))
            allocation={str(k):valid(v) for k,v in (row.get('allocations') or {}).items()}; used=sum(allocation.values())
            if used>pool: raise ValueError('Monthly allocation exceeds variable pool')
            rest=prefix(pool-used,a,b,D); allocation={k:prefix(v,a,b,D) for k,v in allocation.items()}
        else:
            total=valid(options.get('legacyTargetCents') or 0); raw=options.get('legacyAllocations') or {}; used=sum(valid(v) for v in raw.values())
            if used>total: raise ValueError('Legacy allocation exceeds target')
            allocation={str(k):prefix(valid(v),days(start,cursor),days(start,stop),span) for k,v in raw.items()}
            rest=prefix(total-used,days(start,cursor),days(start,stop),span)
        categories=[{'id':k,'totalCents':v} for k,v in sorted(allocation.items())]
        for c in categories: totals[c['id']]=totals.get(c['id'],0)+c['totalCents']
        unallocated+=rest
        savings_target=sum(c['totalCents'] for c in categories if c['id'] in savings_ids) if row is not None else 0
        debt_target=sum(c['totalCents'] for c in categories if c['id'] in debt_ids) if row is not None else 0
        segments.append({'start':cursor,'end':stop,'month':month,'sourceMonth':source,'estimated':estimated,'legacy':row is None,'targetCents':sum(allocation.values())+rest,'savingsTargetCents':savings_target,'debtBudgetTargetCents':debt_target,'spendableTargetCents':sum(allocation.values())+rest-savings_target-debt_target,'categories':categories,'unallocatedCents':rest});cursor=stop
    categories=[{'id':k,'totalCents':v} for k,v in sorted(totals.items())]
    return {'targetCents':sum(totals.values())+unallocated,'savingsTargetCents':sum(x['savingsTargetCents'] for x in segments),'debtBudgetTargetCents':sum(x['debtBudgetTargetCents'] for x in segments),'spendableTargetCents':sum(totals.values())+unallocated-sum(x['savingsTargetCents']+x['debtBudgetTargetCents'] for x in segments),'savingsCategoryIds':savings_ids,'debtCategoryIds':debt_ids,'categories':categories,'unallocatedCents':unallocated,'segments':segments,'sourceMonths':list(dict.fromkeys(s['sourceMonth'] for s in segments if s['sourceMonth'])),'estimated':any(s['estimated'] for s in segments),'legacy':any(s['legacy'] for s in segments),'covered':covered}


def finance_projection(data, options):
    """Чиста канонічна проєкція. Вхід: гривні; грошовий вихід: копійки."""
    from decimal import Decimal, ROUND_HALF_UP
    from copy import deepcopy
    asof, through = options['asof'], options['through']
    def safe(n):
        if abs(n)>9007199254740991: raise ValueError('Unsafe cents')
        return n
    def cents(n): return safe(int((Decimal(str(n or 0))*100).quantize(Decimal(1),rounding=ROUND_HALF_UP)))
    def total(values): return safe(sum(values))
    def plus(s,n): return (date.fromisoformat(s)+timedelta(days=n)).isoformat()
    def distance(a,b): return (date.fromisoformat(b)-date.fromisoformat(a)).days
    def dt(y,m,d): return (date(y,m,1)+timedelta(days=d-1)).isoformat()
    def mi(s): return int(s[:4])*12+int(s[5:7])-1
    def ym(k):
        y,m=divmod(k,12)
        return y,m+1
    def txdate(t): return str(t.get('date') or t.get('created_at') or '')[:10]
    def sid(v): return str(v) if v is not None else 'null'
    if through<asof or distance(asof,through)>3660: raise ValueError('Invalid horizon')
    for s in (asof,through):
        if date.fromisoformat(s).isoformat()!=s: raise ValueError('Invalid date')
    seen=set(); txs=[]
    for t in data.get('transactions',data.get('account_tx',[])):
        if txdate(t)>asof: continue
        if t.get('id') is not None:
            if sid(t['id']) in seen: continue
            seen.add(sid(t['id']))
        txs.append(deepcopy(t))
    txs.sort(key=lambda t:(parse_ts(t['created_at']).timestamp(),str(t.get('id',''))))
    accounts=[]
    for index,a in enumerate(a for a in data.get('accounts',[]) if a.get('active') is not False):
        a=deepcopy(a)
        if a.get('id') is None: a['id']='unidentified:'+str(index)
        balance=cents(a.get('balance')); debt=max(0,cents(a.get('debt')))
        month=str(a.get('debt_month') or a.get('balance_updated_at') or asof)[:7]; buckets={}
        for m,v in a.get('debt_months',[[month,debt/100]]): buckets[m]=buckets.get(m,0)+max(0,cents(v))
        excess=total(buckets.values())-debt
        if excess<0: buckets[month]=buckets.get(month,0)-excess
        if excess>0:
            for m in sorted(buckets,reverse=True):
                n=min(excess,buckets[m]); buckets[m]-=n; excess-=n
        if not a.get('mono_account_id') and a.get('id') is not None and a.get('balance_updated_at'):
            try: since=parse_ts(a['balance_updated_at'])
            except ValueError: since=None
            if since is not None:
                for t in txs:
                    if sid(t.get('account_id'))!=sid(a['id']) or parse_ts(t['created_at'])<=since: continue
                    amount=max(0,cents(t.get('amount')))
                    if a.get('kind')!='credit':
                        balance=safe(balance+(amount if t.get('type')=='income' else -amount)); continue
                    if t.get('type')=='income':
                        left=amount
                        for m in sorted(buckets):
                            n=min(left,buckets[m]); buckets[m]-=n; left-=n; debt-=n
                        balance=safe(balance+left)
                    else:
                        own=min(max(0,balance),amount); balance-=own; borrowed=amount-own; m=txdate(t)[:7]
                        buckets[m]=buckets.get(m,0)+borrowed; debt=safe(debt+borrowed)
        # v145: кошики за FIFO, як у budget.ts: залишок боргу складають найновіші витрати рахунку, частина понад відомі
        # витрати лишається в найстаршому збереженому кошику, якщо він старший за найранішу витрату
        if a.get('kind')=='credit' and debt>0:
            spent={}
            for t in txs:
                if sid(t.get('account_id'))==sid(a['id']) and t.get('type')!='income':
                    m=txdate(t)[:7]; spent[m]=spent.get(m,0)+max(0,cents(t.get('amount')))
            # v146: збережений debt_month задає найстарший місяць боргу, раніші витрати вже погашені
            old=(sorted(m for m in buckets if buckets[m]>0) or [month])[0]; floor=old if a.get('debt_month') else ''
            ms=sorted((m for m in spent if spent[m]>0 and m>=floor),reverse=True)
            if ms:
                buckets={}; left=debt
                for m in ms:
                    if left<=0: break
                    n=min(left,spent[m]); buckets[m]=n; left-=n
                if left>0:
                    m=old if old<ms[-1] else ms[-1]; buckets[m]=buckets.get(m,0)+left
        a.update(balance=balance/100,debt=debt/100,balanceCents=balance,debtCents=debt,debt_months=[[m,buckets[m]/100] for m in sorted(buckets) if buckets[m]>0]); accounts.append(a)
    stamps=[]
    for a in accounts:
        if not a.get('mono_account_id') and a.get('balance_updated_at'):
            try: stamps.append(parse_ts(a['balance_updated_at']))
            except ValueError: pass
    adjustment=total((1 if t.get('type')=='income' else -1)*cents(t.get('amount')) for t in txs if stamps and t.get('account_id') is None and t.get('source')!='mono' and parse_ts(t['created_at'])>min(stamps))
    own=max(0,total([max(0,a['balanceCents']) for a in accounts]+[adjustment])); cash=total([a['balanceCents'] for a in accounts]+[adjustment])
    # борг усіх карток, і кредитних, і дебетових з боргом (як Mono з лімітом); кожен кошик має одну подію погашення
    debt=total(a['debtCents'] for a in accounts)
    snapshot={'positiveOwnCents':own,'cashCents':cash,'unassignedAdjustmentCents':adjustment,'creditDebtCents':debt,'accounts':accounts,'warnings':[]}
    cfg=data.get('salary'); payout_list=[]
    # v153: ручний бюджет періоду (salary_config.budget_manual, гривні); None або порожньо: авто
    bm=(cfg or {}).get('budget_manual')
    try: manual=cents(bm) if bm is not None and bm!='' and float(bm)>=0 else None
    except (ValueError,TypeError): manual=None
    def valid_day(v):
        try: return float(v).is_integer() and 1<=float(v)<=31
        except (ValueError,TypeError): return False
    valid=cfg and all(valid_day(cfg.get(k)) for k in ('advance_day','salary_day','split_day'))
    def weekdays(y,m,lo,hi): return sum(date.fromisoformat(dt(y,m,d)).weekday()<5 for d in range(lo,hi+1))
    if valid:
        for k in range(mi(asof)-2,mi(through)+4):
            y,m=ym(k); py,pm=ym(k-1)
            for kind in ('advance','salary'):
                d=dt(y,m,int(cfg[kind+'_day'])); w=date.fromisoformat(d).weekday(); d=plus(d,-1 if w==5 else 1 if w==6 else 0)
                sy,sm=(y,m) if kind=='advance' else (py,pm); rate=float(cfg.get('rate') or 0); last=calendar.monthrange(sy,sm)[1]
                amount=cents(salary_period_amount(cfg,sy,sm,1 if kind=='advance' else int(cfg['split_day'])+1,int(cfg['split_day']) if kind=='advance' else last,cfg.get(kind+'_amount')))
                if amount>0: payout_list.append({'date':d,'kind':kind,'amount':amount/100,'amountCents':amount})
    payout_list.sort(key=lambda p:(p['date'],p['kind'])); payout_dates=sorted({p['date'] for p in payout_list})
    next_date=next((d for d in payout_dates if d>asof),''); following=next((d for d in payout_dates if next_date and d>next_date),''); has_plan=bool(next_date and following)
    def payout_at(d):
        rows=[p for p in payout_list if p['date']==d]; amount=total(p['amountCents'] for p in rows)
        return {**rows[0],'amount':amount/100,'amountCents':amount}
    end_generation=next((d for d in payout_dates if d>through and d>=following),plus(through,1)); events=[]
    def make(i,d,name,kind,amount,extra=None):
        return {'id':i,'occurrenceId':i,'date':d,'name':name,'kind':kind,'cashDeltaCents':amount if kind in ('income','payout') else -amount,'debtDeltaCents':0,'funding':'cash','certainty':'planned','amountCents':amount,**(extra or {})}
    for p in payout_list:
        if asof<p['date']<=end_generation: events.append(make('payout:'+p['kind']+':'+p['date'],p['date'],'Аванс' if p['kind']=='advance' else 'Зарплата','payout',p['amountCents']))
    def iso_day(s): return date.fromisoformat(s).weekday()+1
    def weekly(f): return f.get('period')=='week'
    # Привʼязана витрата закриває період зобовʼязання; без нього — період фактичної дати.
    paid=set()
    for t in txs:
        if t.get('type')=='expense' and t.get('fixed_id') is not None:
            paid.add(sid(t['fixed_id'])+'|'+payment_day(t)[:7])
            if week_key(payment_day(t)): paid.add(sid(t['fixed_id'])+'|'+week_key(payment_day(t)))
    paid_credit={sid(t['credit_id'])+'|'+payment_day(t)[:7] for t in txs if t.get('type')=='expense' and t.get('credit_id') is not None}
    for k in range(mi(asof),mi(end_generation)+1):
        y,m=ym(k); month=dt(y,m,1)[:7]; last=calendar.monthrange(y,m)[1]
        for i,f in enumerate(data.get('fixed',[])):
            if weekly(f) or not fixed_in_month(f,m): continue
            d=dt(y,m,min(int(f['day_of_month']),last))
            if f.get('active') is False or d<asof or d>end_generation or fixed_ended(f,d) or (f.get('id') is not None and sid(f['id'])+'|'+month in paid): continue
            events.append(make('fixed:'+sid(f.get('id',i))+':'+month,d,f['name'],'income' if f.get('type')=='income' else 'mandatory',max(0,cents(f.get('amount'))),{'creditEligible':f.get('type')!='income' and f.get('credit_ok') is True}))
        for i,c in enumerate(data.get('credits',[])):
            d=dt(y,m,min(int(c['payment_day']),last)); first=int(c['start_year'])*12+int(c['start_month'])
            # розстрочка з датою <= asof сплачена за планом; витрата з credit_id закриває платіж свого місяця
            if d<=asof or d>end_generation or k<first or k>=first+int(c['total_payments']) or (c.get('id') is not None and sid(c['id'])+'|'+month in paid_credit): continue
            events.append(make('installment:'+sid(c.get('id',i))+':'+month,d,c['name']+' (розстрочка)','mandatory',max(0,cents(c.get('monthly_amount'))),{'creditEligible':c.get('credit_ok') is True}))
    # щотижневі постійні: подія на кожну дату з ISO-днем weekday, id з датою події; оплачений тиждень подій не дає
    for i,f in enumerate(data.get('fixed',[])):
        w=week_day(f)
        if not weekly(f) or f.get('active') is False or w is None: continue
        d=plus(asof,(w-iso_day(asof)+7)%7)
        while d<=end_generation and not fixed_ended(f,d):
            if not (f.get('id') is not None and sid(f['id'])+'|'+week_key(d) in paid):
                events.append(make('fixed:'+sid(f.get('id',i))+':'+d,d,f['name'],'income' if f.get('type')=='income' else 'mandatory',max(0,cents(f.get('amount'))),{'creditEligible':f.get('type')!='income' and f.get('credit_ok') is True}))
            d=plus(d,7)
    def due_for(m):  # договірний строк 24-го M+1: лише інформаційне поле contractualDueDate
        y,n=ym(mi(m+'-01')+1)
        return dt(y,n,24)
    # v147: дата погашення лише за спільним правилом repay_plan (виплата 21-го в M+1)
    for a in accounts:
        for month,amount in a['debt_months']:
            due=due_for(month); planned=repay_plan(month,asof)
            extra={'debtDeltaCents':-cents(amount),'contractualDueDate':due,'plannedRepaymentDate':planned}
            if 'id' in a: extra['accountId']=a['id']
            events.append(make('repay:'+('undefined' if a.get('id') is None else sid(a['id']))+':'+month,planned,a.get('name') or 'Погашення кредитки','repay',cents(amount),extra))
    min_spend=[]
    for a in accounts:
        if a.get('id') is None or cents(a.get('min_spend'))<=0: continue
        spent=0; met=None
        rows=sorted([t for t in txs if sid(t.get('account_id'))==sid(a['id']) and t.get('type')=='expense' and t.get('transfer_id') is None and txdate(t)[:7]==asof[:7]],key=lambda t:(txdate(t),str(t.get('created_at','')),cents(t.get('amount'))))
        for t in rows:
            spent+=cents(t.get('amount'))
            if met is None and spent>=cents(a.get('min_spend')): met=txdate(t)
        row={'accountId':a['id'],'month':asof[:7],'spent':spent/100,'min':cents(a.get('min_spend'))/100,'fee':cents(a.get('min_spend_fee'))/100,'left':max(0,cents(a.get('min_spend'))-spent)/100}
        if met: row['metOn']=met
        min_spend.append(row)
    order={'payout':0,'income':1,'arrears':2,'repay':3,'prepay':4,'savings':5,'mandatory':6,'fee':7,'variable':8}
    def event_key(e): return e['date'],order[e['kind']],e['id']
    scenario={'selectedCents':0,'newDebtCents':0,'cashPlanCents':0,'gapCents':0,'repayments':[],'errors':[]} if options.get('scenario') is not None else None
    if scenario is not None:
        used=set()
        def selection_key(s): return event_key(next((e for e in events if e['occurrenceId']==s['occurrenceId']),{'date':'9999','kind':'mandatory','id':s['occurrenceId']}))
        for selection in sorted(options['scenario'].get('selections',[]),key=selection_key):
            e=next((e for e in events if e['occurrenceId']==selection['occurrenceId'] and e['kind']=='mandatory'),None); a=next((a for a in accounts if sid(a.get('id'))==sid(selection['accountId'])),None); n=selection['amountCents']; error=''
            if e is None or not e.get('creditEligible'): error='Платіж не дозволений для кредитного сценарію.'
            elif e['id'] in used or not isinstance(n,(int,float)) or int(n)!=n or abs(n)>9007199254740991 or n<=0 or n>e['amountCents']: error='Некоректна сума або повторний вибір платежу.'
            elif a is None or a.get('kind')!='credit' or a.get('credit_limit') is None: error='Для кредитного рахунку потрібен відомий ліміт.'
            else:
                debt_at=a['debtCents']+total(v['debtDeltaCents'] for v in events if sid(v.get('accountId'))==sid(a['id']) and event_key(v)<event_key(e))
                if n>cents(a['credit_limit'])-debt_at: error='На дату платежу бракує кредитного ліміту.'
            if error: scenario['errors'].append(error); continue
            used.add(e['id']); scenario['selectedCents']+=n; scenario['newDebtCents']+=n; e['cashDeltaCents']+=n
            if n==e['amountCents']: e.update(funding='credit',accountId=a['id'],debtDeltaCents=n)
            else:
                e['amountCents']-=n; events.append({**e,'id':e['id']+':credit','amountCents':n,'cashDeltaCents':0,'debtDeltaCents':n,'funding':'credit','accountId':a['id']})
            due=due_for(e['date'][:7]); planned=repay_plan(e['date'][:7],asof); repayment=make('scenario-repay:'+e['occurrenceId']+':'+sid(a['id']),planned,'Погашення сценарного боргу','repay',n,{'accountId':a['id'],'debtDeltaCents':-n,'contractualDueDate':due,'plannedRepaymentDate':planned}); scenario['repayments'].append(repayment); events.append(repayment)
    for k in range(mi(asof),mi(end_generation)+1):
        y,m=ym(k); month=dt(y,m,1)[:7]; ny,nm=ym(k+1); d=dt(ny,nm,1)
        if d>end_generation: continue
        for a in accounts:
            if a.get('id') is None or cents(a.get('min_spend'))<=0 or cents(a.get('min_spend_fee'))<=0: continue
            actual=total(cents(t.get('amount')) for t in txs if sid(t.get('account_id'))==sid(a['id']) and t.get('type')=='expense' and t.get('transfer_id') is None and txdate(t)[:7]==month)
            assigned=0 if month==asof[:7] else total(e['amountCents'] for e in events if e['kind']=='mandatory' and sid(e.get('accountId'))==sid(a['id']) and e['date'][:7]==month)
            if actual+assigned<cents(a.get('min_spend')): events.append(make('fee:'+sid(a['id'])+':'+month,d,'Комісія: '+str(a.get('name') or a['id']),'fee',cents(a.get('min_spend_fee')),{'accountId':a['id'],'certainty':'conditional'}))
    # категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit
    expense_cats=[c for c in data.get('categories',[]) if c.get('active') is not False and c.get('type')=='expense' and not c.get('budget_role') and not (str(c.get('id'))=='savings' or __import__('unicodedata').normalize('NFKC',str(c.get('name') or '')).strip().lower()=='заощадження')]
    categories=sorted([{'id':sid(c['id']),'name':c.get('name') or '','weight':0,'limitAbsCents':max(0,cents(c['limit_abs']))} if c.get('limit_abs') is not None else {'id':sid(c['id']),'name':c.get('name') or '', 'weight':max(0,cents(c.get('budget_limit') if c.get('budget_limit') is not None else c.get('limit')))/100} for c in expense_cats],key=lambda c:c['id'])
    if len({c['id'] for c in categories})!=len(categories): raise ValueError('Duplicate category id')
    # черга сум у гривнях: sort_order (None в кінці), при рівності id
    abs_order=[next(i for i,x in enumerate(categories) if x['id']==sid(c['id'])) for c in sorted([c for c in expense_cats if c.get('limit_abs') is not None],key=lambda c:(c.get('sort_order') is None,float(c['sort_order']) if c.get('sort_order') is not None else 0,sid(c['id'])))]
    if not abs_order and not any(c['weight']>0 for c in categories): categories=[{'id':'unallocated','name':'Не розподілено','weight':1}]
    def allocate(amount,weights):
        if not amount: return [0]*len(weights)
        denominator=sum(weights); values=[amount*w//denominator for w in weights]; indices=sorted(range(len(weights)),key=lambda i:(-(amount*weights[i]%denominator),i))
        for i in indices[:amount-sum(values)]: values[i]+=1
        return values
    # суми в гривнях по черзі min(ліміт, що лишилось), залишок за вагами; ваг немає: «Не розподілено»; caps: ліміти поточного періоду
    def split(amount,caps=None):
        if not abs_order: return categories,allocate(amount,[cents(c['weight']) for c in categories])
        totals=[0]*len(categories); weights=[0 if 'limitAbsCents' in c else cents(c['weight']) for c in categories]; left=amount
        for i in abs_order:
            n=min(caps[i] if caps is not None else categories[i]['limitAbsCents'],left); totals[i]=n; left-=n
        if any(w>0 for w in weights): return categories,[t+a for t,a in zip(totals,allocate(left,weights))]
        return (categories+[{'id':'unallocated','name':'Не розподілено','weight':1}],totals+[left]) if left>0 else (categories,totals)
    monthly_rows=data.get('monthly_budgets') or []; monthly_options={'categories':data.get('categories') or []}
    role_plan=monthly_period_budget([],asof,asof,monthly_options); savings_ids=set(role_plan['savingsCategoryIds']); debt_ids=set(role_plan['debtCategoryIds'])
    def actual_card_repayment(target):
        raw=next((a for a in data.get('accounts',[]) if str(a.get('id'))==str(target.get('account_id'))),None)
        current=next((a for a in accounts if str(a.get('id'))==str(target.get('account_id'))),None)
        if not raw or not current: return 0
        def time(t): return parse_ts(t.get('created_at') or str(t.get('date'))+'T00:00:00Z').timestamp()
        ordered=sorted([t for t in txs if str(t.get('account_id'))==str(target.get('account_id'))],key=lambda t:(time(t),str(t.get('id','')))); at=next(i for i,t in enumerate(ordered) if t is target)
        try: stamp=parse_ts(raw['balance_updated_at']).timestamp() if raw.get('balance_updated_at') else None
        except (ValueError, TypeError): stamp=None
        debt=max(0,cents(raw.get('debt'))); balance=max(0,cents(raw.get('balance')))
        if not raw.get('mono_account_id') and stamp is not None and time(target)>stamp:
            for t in ordered[:at]:
                if stamp is not None and time(t)<=stamp: continue
                n=max(0,cents(t.get('amount')))
                if t.get('type')=='income':
                    cut=min(debt,n); debt-=cut; balance+=n-cut
                else:
                    used=min(balance,n); balance-=used; debt+=n-used
        else:
            net=cents(current.get('balance'))-cents(current.get('debt'))
            for t in ordered[at:]:
                n=max(0,cents(t.get('amount'))); net+=-n if t.get('type')=='income' else n
            debt=max(0,-net)
        return min(max(0,cents(target.get('amount'))),debt)
    def debt_progress(month):
        month_tx=[t for t in txs if txdate(t)[:7]==month[:7]]; seen_transfers=set(); card_paid=0
        for t in month_tx:
            if t.get('type')!='income' or t.get('transfer_id') is None: continue
            key=str(t['transfer_id']); dest=next((a for a in accounts if str(a.get('id'))==str(t.get('account_id'))),None)
            if key in seen_transfers or not dest or dest.get('kind')!='credit': continue
            if not any(x.get('transfer_id')==t['transfer_id'] and x.get('type')=='expense' and str(x.get('account_id'))!=str(t.get('account_id')) and any(str(a.get('id'))==str(x.get('account_id')) and a.get('kind')!='credit' for a in accounts) for x in txs): continue
            seen_transfers.add(key); card_paid+=actual_card_repayment(t)
        row=next((r for r in sorted(monthly_rows,key=lambda r:str(r['month_start']),reverse=True) if str(r['month_start'])<=month),None); reserved={}; paid={}
        for x in (row or {}).get('mandatory_items') or []:
            if x.get('kind')=='installment':
                key=str(x['key']).split(':')[1]+'|'+month[:7]; reserved[key]=reserved.get(key,0)+int(x.get('amount_cents') or 0)
        for t in month_tx:
            if t.get('type')=='expense' and t.get('credit_id') is not None and t.get('transfer_id') is None:
                key=str(t['credit_id'])+'|'+str(t.get('payment_due_date') or txdate(t))[:7]; paid[key]=paid.get(key,0)+max(0,cents(t.get('amount')))
        extra=sum(max(0,n-reserved.get(key,0)) for key,n in paid.items())
        return {'cardPaymentsCents':card_paid,'installmentAdditionalPaymentsCents':extra,'debtPaymentsCents':card_paid+extra}
    def monthly_plan(start,end,legacy_target,subtract_actual=False):
        if not monthly_rows: return None
        lr,lt=split(legacy_target)
        m=monthly_period_budget(monthly_rows,start,end,{**monthly_options,'legacyTargetCents':legacy_target,'legacyAllocations':{c['id']:n for c,n in zip(lr,lt)}})
        if not m['covered']: return None
        by={}; remaining_segments=[]; month_signed_caps={}; month_debt_progress={}
        for seg in m['segments']:
            year,month=map(int,seg['month'][:7].split('-')); year,month=ym(year*12+month); month_end=dt(year,month,1)
            full=monthly_period_budget(monthly_rows,seg['month'],month_end,monthly_options)
            budget_rows=seg['categories']+[{'id':'unallocated','totalCents':seg['unallocatedCents']}]
            full_rows=full['categories']+[{'id':'unallocated','totalCents':full['unallocatedCents']}]
            fact=[t for t in txs if t.get('type')=='expense' and all(t.get(k) is None for k in ('fixed_id','credit_id','transfer_id')) and seg['month']<=txdate(t)<month_end]
            known={c['id'] for c in (seg['categories'] if seg['legacy'] else full['categories'])}
            def cat(t): return str(t['category_id']) if t.get('category_id') is not None and str(t['category_id']) not in debt_ids and str(t['category_id']) in known else 'unallocated'
            projected=[e for e in events if (e['kind']=='variable' or e.get('budgetSavings')) and seg['month']<=e['date']<seg['start']]
            values=[]
            for c in budget_rows:
                if c['id'] in debt_ids:
                    values.append(0); continue
                spent=total(cents(t.get('amount')) for t in fact if cat(t)==c['id'])
                part=total(cents(t.get('amount')) for t in fact if cat(t)==c['id'] and seg['start']<=txdate(t)<seg['end']) if subtract_actual else 0
                used=total(e['amountCents'] for e in projected if str(e.get('categoryId'))==c['id'])
                cap=float('inf') if seg['legacy'] else max(0,next((r['totalCents'] for r in full_rows if r['id']==c['id']),0)-spent-used)
                values.append(min(max(0,c['totalCents']-part),cap))
            actual_part=total(cents(t.get('amount')) for t in fact if seg['start']<=txdate(t)<seg['end']) if subtract_actual else 0
            savings_indexes=[i for i,c in enumerate(budget_rows) if not seg['legacy'] and c['id'] in savings_ids]
            ordinary_indexes=[i for i in range(len(budget_rows)) if i not in savings_indexes]
            savings_remaining=sum(values[i] for i in savings_indexes); candidates=[values[i] for i in ordinary_indexes]
            full_savings_remaining=0 if seg['legacy'] else max(0,full['savingsTargetCents']-total(cents(t.get('amount')) for t in fact if cat(t) in savings_ids)-total(e['amountCents'] for e in projected if e.get('budgetSavings')))
            debt_paid=debt_progress(seg['month']); debt_extra=max(0,debt_paid['debtPaymentsCents']-full['debtBudgetTargetCents']); month_debt_progress[seg['month']]={**debt_paid,'debtBudgetTargetCents':full['debtBudgetTargetCents'],'debtExtraOverrunCents':debt_extra}
            month_signed=full['targetCents']-full['debtBudgetTargetCents']-debt_extra-total(cents(t.get('amount')) for t in fact)-total(e['amountCents'] for e in projected)-full_savings_remaining
            segment_signed=seg['targetCents']-seg['debtBudgetTargetCents']-actual_part-savings_remaining
            signed_remaining=min(sum(candidates),segment_signed,float('inf') if seg['legacy'] else month_signed)
            ordinary=allocate(max(0,signed_remaining),candidates)
            for i,n in zip(ordinary_indexes,ordinary): values[i]=n
            if not seg['legacy']: month_signed_caps[seg['month']]=month_signed
            if not subtract_actual or seg['end']>asof:
                for c,n in zip(budget_rows,values): by[c['id']]=by.get(c['id'],0)+n
                remaining_segments.append({**seg,'categories':[{'id':c['id'],'totalCents':n} for c,n in zip(budget_rows,values)],'targetCents':sum(values),'savingsTargetCents':savings_remaining,'spendableTargetCents':sum(ordinary),'signedSpendableRemainingCents':signed_remaining})
        return {**m,'remainingSegments':remaining_segments,'monthSignedSpendableCaps':month_signed_caps,'monthDebtProgress':month_debt_progress,'debtExtraOverrunCents':sum(p['debtExtraOverrunCents'] for p in month_debt_progress.values()),'signedSpendableRemainingCents':sum(s['signedSpendableRemainingCents'] for s in remaining_segments),'rawCategories':m['categories'],'rawUnallocatedCents':m['unallocatedCents'],'rawTargetCents':m['targetCents'],'rawSavingsTargetCents':m['savingsTargetCents'],'debtBudgetTargetCents':m['debtBudgetTargetCents'],'rawSpendableTargetCents':m['spendableTargetCents'],'savingsTargetCents':sum(v for k,v in by.items() if k in savings_ids),'spendableTargetCents':sum(v for k,v in by.items() if k not in savings_ids),'targetCents':sum(by.values()),'categories':[{'id':k,'totalCents':by[k]} for k in sorted(by, key=lambda k: (0,int(k)) if k.isascii() and k.isdigit() and str(int(k))==k and int(k)<4294967295 else (1,list(by).index(k))) if k!='unallocated'],'unallocatedCents':by.get('unallocated',0)}
    def distribution(target,start,end,available,caps=None,monthly=None,uniform=False):
        count=distance(start,end); exact=monthly or monthly_plan(start,end,target)
        chosen=[c for c in exact['categories'] if c['id'] not in debt_ids and c['id'] not in savings_ids]+[{'id':'unallocated','totalCents':exact['unallocatedCents']}] if exact else None
        if chosen is not None:
            rows=[{'id':c['id'],'name':next((x['name'] for x in data.get('categories',[]) if str(x['id'])==c['id']),('Не розподілено' if c['id']=='unallocated' else 'Категорія '+c['id'])),'weight':0} for c in chosen]; totals=allocate(target,[c['totalCents'] for c in chosen]) if uniform else [c['totalCents'] for c in chosen]
        else: rows,totals=split(target if count>0 else 0,caps)
        remaining=totals[:]; schedule=[]; balance=available
        natural=monthly_period_budget(monthly_rows,start,end,monthly_options) if chosen is not None and not uniform else None
        def amount_of(m,k): return m['unallocatedCents'] if k=='unallocated' else next((c['totalCents'] for c in m['categories'] if c['id']==k),0)
        direct=natural and natural['covered'] and natural['targetCents']==sum(totals) and all(amount_of(natural,r['id'])==n for r,n in zip(rows,totals))
        for i in range(count):
            effective=sum(totals); daily=monthly_period_budget(monthly_rows,plus(start,i),plus(start,i+1),monthly_options) if direct else None
            spend=effective//count+int(i<effective%count)
            def daily_amount(r,n):
                if daily: return amount_of(daily,r['id'])
                d=plus(start,i); seg=next((x for x in exact.get('remainingSegments',[]) if x['start']<=d<x['end']),None)
                if seg:
                    lo=max(seg['start'],start); hi=min(seg['end'],end); D=distance(lo,hi); k=distance(lo,d); v=next((c['totalCents'] for c in seg['categories'] if c['id']==r['id']),0)
                    return v*(k+1)//D-v*k//D
                return n*(i+1)//count-n*i//count
            amounts=[daily_amount(r,n) for r,n in zip(rows,totals)] if chosen is not None and not uniform else remaining[:] if i==count-1 else allocate(spend,remaining)
            if chosen is not None: spend=sum(amounts)
            remaining=[v-a for v,a in zip(remaining,amounts)]; balance=safe(balance-spend)
            schedule.append({'date':plus(start,i),'spendCents':spend,'remainingCents':balance,'byCategory':[{'id':c['id'],'name':c['name'],'amountCents':a,**({'budgetSavings':True} if exact and exact.get('covered') and c['id'] in savings_ids else {})} for c,a in zip(rows,amounts)]})
        savings_target=exact['savingsTargetCents'] if exact and exact.get('covered') else 0
        return {'categories':[{**c,'totalCents':a} for c,a in zip(rows,totals)],'schedule':schedule,'savingsTargetCents':savings_target,'spendableTargetCents':sum(totals)}
    def between(start,end): return [e for e in events if start<=e['date']<end and e['kind']!='variable']
    def mandatory(start,end): return total(e['amountCents'] for e in between(start,end) if e['kind'] in ('mandatory','fee'))
    # до наступної виплати: власні кошти мінус обовʼязкові й комісії [asof; виплата); борг карток гаситься з виплати
    until_payout=None
    if next_date:
        left_days=distance(asof,next_date); left=safe(own-mandatory(asof,next_date))
        until_payout={'end':next_date,'days':left_days,'cents':left,'dailyCents':left//left_days if left>0 and left_days>0 else 0}
    next_plan=current_period=None; periods=[]
    if has_plan:
        nxt=payout_at(next_date); after=payout_at(following); reserved=mandatory(next_date,following); base=safe(own+nxt['amountCents']-reserved-debt); target=max(1500000,base); mp=monthly_plan(next_date,following,target); target=mp['targetCents'] if mp else target
        next_plan={'start':next_date,'end':following,'days':distance(next_date,following),'nextPayout':nxt,'followingPayout':after,'positiveOwnCents':own,'debtCents':debt,'mandatoryCents':reserved,'otherIncomeCents':total(e['amountCents'] for e in between(next_date,following) if e['kind']=='income'),'eligibleMandatoryCents':total(e['amountCents'] for e in between(next_date,following) if e['kind']=='mandatory' and e.get('creditEligible')),'baseAvailableCents':base,'targetCents':target,'gapCents':max(0,target-base),'averageDailyCents':(mp['spendableTargetCents'] if mp else target)/distance(next_date,following),**distribution(target,next_date,following,base,monthly=mp),**({'debtBudgetTargetCents':mp['debtBudgetTargetCents'],'grossBudgetTargetCents':mp['rawTargetCents']} if mp else {}),**({'monthlyBudget':mp} if mp else {})}
        # темп щоденних витрат від завтра до дня перед виплатою: більше з 15 000 ₴ на весь період [start; виплата) і untilPayout на дні, що лишились
        start=next((d for d in reversed(payout_dates) if d<=asof),asof); actual=total(cents(t.get('amount')) for t in txs if t.get('type')=='expense' and t.get('transfer_id') is None and t.get('fixed_id') is None and t.get('credit_id') is None and txdate(t)>=start); mandatory_now=mandatory(asof,next_date); available=safe(cash-mandatory_now)
        period_days=distance(start,next_date); left_days=max(0,distance(plus(asof,1),next_date)); floor_left=(manual if manual is not None else 1500000)*left_days//period_days if period_days>0 else 0; free_left=max(0,until_payout['cents'] if until_payout else 0); remaining=max(floor_left,manual-actual if manual is not None else free_left) if left_days>0 else 0; target=actual+remaining
        # сума в гривнях на прогноз від завтра: ліміт мінус факт змінних витрат категорії з початку періоду, не нижче 0
        caps=[max(0,c['limitAbsCents']-total(cents(t.get('amount')) for t in txs if t.get('type')=='expense' and t.get('transfer_id') is None and t.get('fixed_id') is None and t.get('credit_id') is None and txdate(t)>=start and t.get('category_id') is not None and sid(t['category_id'])==c['id'])) if 'limitAbsCents' in c else 0 for c in categories]
        dist=distribution(remaining,plus(asof,1),next_date,available,caps)
        current_monthly=monthly_plan(start,next_date,target); remaining_monthly=monthly_plan(start,next_date,target,True) if current_monthly else None
        if current_monthly and remaining_monthly:
            target=current_monthly['rawTargetCents']; remaining=remaining_monthly['targetCents']
            dist=distribution(max(0,remaining_monthly['signedSpendableRemainingCents']),asof,next_date,available,None,remaining_monthly,True)
        actual_savings=total(cents(t.get('amount')) for t in txs if t.get('type')=='expense' and all(t.get(k) is None for k in ('transfer_id','fixed_id','credit_id')) and txdate(t)>=start and str(t.get('category_id')) in savings_ids) if current_monthly else 0
        savings_target=current_monthly['rawSavingsTargetCents'] if current_monthly else 0; savings_remaining=remaining_monthly['savingsTargetCents'] if remaining_monthly else 0
        signed_remaining=remaining_monthly['signedSpendableRemainingCents'] if remaining_monthly else remaining-savings_remaining; spendable_remaining=max(0,signed_remaining)
        current_period={'start':start,'end':next_date,'actualVariableCents':actual,'actualSpendableCents':actual-actual_savings,'actualSavingsCents':actual_savings,'targetCents':target,'remainingTargetCents':remaining,'savingsTargetCents':savings_target,'debtBudgetTargetCents':current_monthly['debtBudgetTargetCents'] if current_monthly else 0,'debtExtraOverrunCents':remaining_monthly['debtExtraOverrunCents'] if remaining_monthly else 0,'spendableTargetCents':target-savings_target-(current_monthly['debtBudgetTargetCents'] if current_monthly else 0),'savingsRemainingCents':savings_remaining,'signedSpendableRemainingCents':signed_remaining,'spendableRemainingCents':spendable_remaining,'periodDays':period_days,'leftDays':left_days,'dailyCents':spendable_remaining/max(1,distance(asof,next_date)) if current_monthly else (remaining-savings_remaining)/left_days if left_days>0 else 0,'futureSchedule':dist['schedule'],**({'monthlyBudget':current_monthly,'overrunCents':max(0,-signed_remaining)} if current_monthly else {})}
        periods.append({'start':start,'end':next_date,'basis':'current','openingCashCents':cash,'payoutCents':0,'mandatoryCents':mandatory_now,'debtReserveCents':0,'availableCents':available,'targetCents':target,'gapCents':max(0,remaining-available),**dist,**({'monthlyBudget':current_monthly} if current_monthly else {})})
    # v151 (власник: «власні кошти не можуть бути мінусові»): послідовна симуляція, дзеркало budget.ts
    events[:]=[e for e in events if e['kind']!='repay']
    def limit_of(a): return 0 if a.get('credit_limit') is None else max(0,cents(a.get('credit_limit')))
    lenders=[a for a in accounts if a.get('mono_account_id') and limit_of(a)>0]+[a for a in accounts if not a.get('mono_account_id') and limit_of(a)>0]
    book={}
    for a in accounts:
        b=book.setdefault(sid(a['id']),{})
        for m,v in a['debt_months']: b[m]=b.get(m,0)+cents(v)
    def debt_of(a): return total(book[sid(a['id'])].values())
    def debt_all(): return total(debt_of(a) for a in accounts)
    def debit_only(e): return e['kind']=='fee' or (e['kind']=='mandatory' and e.get('creditEligible') is not True and e.get('funding')!='credit')
    # v153 А: обовʼязкові з кредитки (credit_ok) теж резервуються з виплати і платяться з власних (див. budget.ts)
    def ok_funded(e): return e['kind']=='mandatory' and not debit_only(e) and e.get('funding')!='credit'
    sim_end=next_date if has_plan and next_date>through else through
    by_date={}
    def put(e): by_date.setdefault(e['date'],[]).append(e)
    def category_event(d,c):
        saving=c.get('budgetSavings',False)
        return make(('budget-savings:' if saving else 'variable:')+d+':'+c['id'],d,'У заощадження: '+c['name'] if saving else c['name'],'savings' if saving else 'variable',c['amountCents'],{'categoryId':c['id'],**({'budgetSavings':True,'plannedCents':c['amountCents']} if saving else {})})
    for p in periods:
        for d in p['schedule']:
            for c in d['byCategory']:
                if c['amountCents']>0 and not (p['basis']=='current' and d['date']==asof): events.append(category_event(d['date'],c))
    for e in events:
        if asof<=e['date']<=sim_end: put(e)
    def debit_between(start,end): return total(e['amountCents'] for e in events if start<=e['date']<end and debit_only(e))
    # v154: доповнення А v153 скасовано: резерв виплати = лише білі (credit_ok=false) обовʼязкові, білі платежі розстрочок і комісії до наступної
    # виплати; обовʼязкові з credit_ok не резервуються (вільні власні, далі кредитка). Шар reserved_ok лишається, але завжди 0. Як у budget.ts.
    bal=own; arrears=own-cash
    reserved=min(bal,debit_between(asof,next_date) if next_date else 0); reserved_ok=0
    days=[]; head=None; debt_run=debt
    def repay_from(a,limit,d,only_due,out):
        left=limit; b=book[sid(a['id'])]
        for m in sorted(b):
            if left<=0: break
            if b[m]<=0 or (only_due and repay_plan(m,asof)>d): continue
            n=min(left,b[m]); b[m]-=n
            if not b[m]: del b[m]
            left-=n; k=sid(a['id'])+'|'+m; out[k]=out.get(k,0)+n
        return limit-left
    def due_on(d): return total(v for a in accounts for m,v in book[sid(a['id'])].items() if repay_plan(m,asof)<=d)
    def due_left(d):
        # v153: належне, що лишилось непогашеним на дату, за рахунками
        out=[{'accountId':a['id'],'name':a.get('name') or 'Кредитка','cents':total(v for m,v in book[sid(a['id'])].items() if repay_plan(m,asof)<=d)} for a in accounts]
        return [x for x in out if x['cents']>0]
    # перше погашення кошика має id repay:<рахунок>:<місяць> (за ним шукає бот), наступні часткові: з датою в кінці
    used_repay=set()
    # v153 доповнення 5: залишок розстрочки = платіж × неоплачені платежі графіка після asof; дострокове погашення зрізає графік з кінця
    inst=[]
    for i,c in enumerate(data.get('credits',[])):
        m_=max(0,cents(c.get('monthly_amount'))); first=int(c['start_year'])*12+int(c['start_month']); dates=[]
        for k in range(first,first+int(c['total_payments'])):
            y,n=ym(k); d=dt(y,n,min(int(c['payment_day']),calendar.monthrange(y,n)[1]))
            if d<=asof or (c.get('id') is not None and sid(c['id'])+'|'+d[:7] in paid_credit): continue
            dates.append(d)
        if m_>0 and dates: inst.append({'id':sid(c.get('id',i)),'name':str(c.get('name') or 'Розстрочка'),'m':m_,'dates':dates,'prepaid':0})
    def inst_from(x,frm): return max(0,x['m']*len([v for v in x['dates'] if v>=frm])-x['prepaid'])
    def inst_cut(x,after):
        for e in [e for e in events if e['kind']=='mandatory' and e['date']>after and str(e['id']).startswith('installment:'+x['id']+':')]:
            eff=max(0,min(x['m'],x['m']+x['m']*len([v for v in x['dates'] if v>e['date']])-x['prepaid']))
            if eff>0:
                e['amountCents']=eff; e['cashDeltaCents']=-eff; continue
            events[:]=[v for v in events if v is not e]
            b=by_date.get(e['date'])
            if b and any(v is e for v in b): b[:]=[v for v in b if v is not e]
    def emit_repays(d,out,lst):
        for k in sorted(out):
            if out[k]<=0: continue
            cut=k.rindex('|'); aid=k[:cut]; m=k[cut+1:]; a=next(v for v in accounts if sid(v['id'])==aid); planned=repay_plan(m,asof)
            base='repay:'+aid+':'+m; rid=base+':'+d if base in used_repay else base; used_repay.add(base)
            e=make(rid,d,a.get('name') or 'Погашення кредитки','repay',out[k],{'accountId':a['id'],'debtDeltaCents':-out[k],'contractualDueDate':due_for(m),'plannedRepaymentDate':planned}); events.append(e); lst.append(e)
    # списання з власних за шарами: D резерв дебетових, C резерв credit_ok, F вільні; повертає списане
    def spend(x,tiers):
        nonlocal bal,reserved,reserved_ok
        left=x
        for t in tiers:
            if left<=0: break
            room=min(bal,reserved) if t=='D' else min(bal,reserved_ok) if t=='C' else max(0,bal-reserved-reserved_ok)
            n=min(room,left)
            if n<=0: continue
            bal-=n; left-=n
            if t=='D': reserved-=n
            elif t=='C': reserved_ok-=n
        return x-left
    def borrow(n,d):
        left=n
        for a in lenders:
            if left<=0: break
            k=min(left,max(0,limit_of(a)-debt_of(a)))
            if k>0:
                b=book[sid(a['id'])]; m=d[:7]; b[m]=b.get(m,0)+k; left-=k
        return n-left
    d=asof
    while d<=sim_end:
        opening=bal; open_arrears=arrears; lst=sorted(by_date.get(d,[]),key=event_key); gen=[]
        for e in lst:
            if e['kind'] in ('payout','income'): bal=safe(bal+e['amountCents']); e['cashDeltaCents']=e['amountCents']; e['debtDeltaCents']=0
        if arrears>0 and bal>0 and any(e['kind'] in ('payout','income') for e in lst):
            n=min(bal,arrears); bal-=n; arrears-=n; e=make('arrears:'+d,d,'Сплата нестачі','arrears',n); events.append(e); gen.append(e)
        payout=[e for e in lst if e['kind']=='payout']; end=next((v for v in payout_dates if v>d),'')
        if payout and end:
            monthly=monthly_plan(d,end,manual if manual is not None else 1500000); period_manual=monthly['spendableTargetCents'] if monthly else manual
            # v152: кожна виплата (зарплата чи аванс) проходить той самий розподіл: погашення, накопичення, готівка, переказ на Mono
            # v153 доповнення 7: залишок попереднього періоду (власні на початок дня виплати) до розподілу нової виплати гасить борг кредиток, потім
            # дострокове розстрочок (найменший залишок першим); без боргів решта йде в накопичення. З нової виплати накопичень немає.
            leftover=max(0,min(opening,bal)); out={}; pre={}; leftover_prepay=[]; leftover_savings=0; leftover_prepaid=0
            def prepay_by(budget,lst):
                left=budget; n0=0
                for x in sorted(inst,key=lambda x:(inst_from(x,end),x['id'])):
                    if left<=0: break
                    n=min(left,inst_from(x,end))
                    if n<=0: continue
                    x['prepaid']+=n; left-=n; n0+=n; inst_cut(x,d); pre[x['id']]=pre.get(x['id'],0)+n
                    lst.append({'creditId':x['id'],'name':x['name'],'cents':n})
                return n0
            leftover_repay=total(out.values()); bal-=leftover_repay+leftover_prepaid+leftover_savings
            own_at=bal; rd=min(bal,debit_between(d,end)); rc=min(max(0,bal-rd),max(0,mandatory(d,end)-debit_between(d,end))); reserve=rd+rc; repay=cash_out=to_mono=offset=0; savings=0
            left=payout_budget(bal,reserve,debt_all(),due_on(d),True,period_manual)['repayCents']
            for a in accounts:
                if left<=0: break
                left-=repay_from(a,left,d,True,out)
            for a in [a for a in accounts if not a.get('mono_account_id')]:
                if left<=0: break
                left-=repay_from(a,left,d,False,out)
            for a in [a for a in accounts if a.get('mono_account_id')]:
                if left<=0: break
                left-=repay_from(a,left,d,False,out)
            repay=total(out.values())-leftover_repay
            available=bal-reserve-repay; target=payout_budget(available,0,0,0,False,period_manual)['targetCents']; dist=distribution(target,d,end,available,monthly=monthly)
            # власні після розподілу проти подій періоду: найглибший мінус, якщо зняти ще x
            ahead=[e for e in events if d<=e['date']<end and not (e.get('funding')=='credit' and e.get('accountId') is not None) and (e['date']>d if e['kind']=='income' else e['kind'] not in ('payout','repay','prepay','savings','arrears'))]
            for s in dist['schedule']:
                for c in s['byCategory']:
                    if c['amountCents']>0: ahead.append({'id':'variable:'+s['date']+':'+c['id'],'date':s['date'],'kind':'variable','amountCents':c['amountCents']})
            ahead.sort(key=event_key)
            def low_with(x):
                run=bal-repay-x; low=0
                for e in ahead:
                    run+=e['amountCents'] if e['kind']=='income' else -e['amountCents']; low=min(low,run)
                return low
            # v153 доповнення 5: без боргу кредиток надлишок понад бюджет іде в дострокове погашення розстрочок, найменший залишок першим
            payout_prepay=[]; prepaid=0
            residual=max(0,min(available-target,available-target+low_with(available-target)))
            if debt_all()==0 and arrears==0 and residual>0: prepaid=prepay_by(residual,payout_prepay)
            if debt_all()==0 and arrears==0 and not any(inst_from(x,end)>0 for x in inst): savings=max(0,residual-prepaid)
            free=available-prepaid-savings
            cash_out=min(300000,max(0,free)); to_mono=max(0,free-cash_out)
            # toMono гасить борг Mono лише надлишком понад бюджет
            cap=min(to_mono,max(0,free-target)); left=cap
            for a in [a for a in accounts if a.get('mono_account_id')]:
                if left<=0: break
                left-=repay_from(a,left,d,False,out)
            offset=cap-left
            bal-=repay+offset+prepaid+savings
            emit_repays(d,out,gen)
            # одна подія дострокового погашення на розстрочку за день (із залишку періоду і з виплати разом)
            prepay=[{'creditId':x['id'],'name':x['name'],'cents':pre[x['id']]} for x in sorted(inst,key=lambda x:x['id']) if pre.get(x['id'],0)>0]
            for x in prepay:
                e=make('prepay:'+x['creditId']+':'+d,d,'Дострокове погашення '+x['name'],'prepay',x['cents'],{'creditId':x['creditId']}); events.append(e); gen.append(e)
            due_short=due_left(d); due_short_cents=total(x['cents'] for x in due_short)
            if due_short_cents>0 and d<=through: snapshot['warnings'].append({'kind':'due_short','date':d,'shortCents':due_short_cents,'accounts':due_short})
            if savings>0:
                ps=([v for v in payout_dates if v<d] or [asof])[-1]; dm=lambda v: v[8:10]+'.'+v[5:7]
                e=make('savings:'+d,d,'У заощадження: вільний залишок після платежів і боргів','savings',savings); events.append(e); gen.append(e)
            reserved=rd; reserved_ok=rc
            rec={'start':d,'end':end,'basis':'projected' if head else 'headline','openingCashCents':opening,'payoutCents':total(e['amountCents'] for e in payout),'mandatoryCents':mandatory(d,end),'debtReserveCents':leftover_repay+repay+offset,'availableCents':available,'targetCents':target,'gapCents':max(0,target-available),'ownCents':own_at,'reserveCents':reserve,'repayCents':leftover_repay+repay+offset,'savingsCents':savings,'cashOutCents':cash_out,'toMonoCents':to_mono,'monoOffsetCents':offset,'dueShortCents':due_short_cents,'dueShort':due_short,'prepayCents':prepaid+leftover_prepaid,'prepay':prepay,'leftoverCents':leftover,'leftoverRepayCents':leftover_repay,'leftoverPrepayCents':leftover_prepaid,'leftoverPrepay':leftover_prepay,**({'monthlyBudget':monthly,'debtBudgetTargetCents':monthly['debtBudgetTargetCents'],'grossBudgetTargetCents':monthly['rawTargetCents']} if monthly else {}),'leftoverSavingsCents':leftover_savings,'payoutRepayCents':repay+offset,'payoutPrepayCents':prepaid,'payoutPrepay':payout_prepay,'installmentsLeft':[{'creditId':x['id'],'name':x['name'],'cents':inst_from(x,d)} for x in inst if inst_from(x,d)>0],**dist}
            if head is None: head=rec
            if d<=through: periods.append(rec)
            for s in rec['schedule']:
                for c in s['byCategory']:
                    if c['amountCents']>0:
                        e=category_event(s['date'],c); events.append(e)
                        if s['date']<=sim_end: put(e)
        else:
            due=due_on(d)
            if due>0:
                nx=next((v for v in payout_dates if v>d),'9999-12-31')
                out={}; left=min(due,max(0,bal-reserved-reserved_ok-total(e['amountCents'] for e in events if (e['kind']=='variable' or e.get('budgetSavings')) and d<=e['date']<nx)))
                for a in accounts:
                    if left<=0: break
                    left-=repay_from(a,left,d,True,out)
                bal-=total(out.values()); emit_repays(d,out,gen)
                due_short=due_left(d)
                if due_short and d<=through and any(repay_plan(m,asof)==d for a in accounts for m in book[sid(a['id'])]):
                    snapshot['warnings'].append({'kind':'due_short','date':d,'shortCents':total(x['cents'] for x in due_short),'accounts':due_short})
        ids={id(e) for e in lst}
        lst+=[e for e in by_date.get(d,[]) if e['date']==d and id(e) not in ids]
        lst.sort(key=event_key)
        for e in lst:
            if e['kind'] in ('payout','income'): continue
            x=e['amountCents']
            if e.get('funding')=='credit' and e.get('accountId') is not None:
                b=book[sid(e['accountId'])]; b[d[:7]]=b.get(d[:7],0)+x; e['cashDeltaCents']=0; e['debtDeltaCents']=x; continue
            if e.get('budgetSavings'):
                funded=spend(x,'F');e['fundedCents']=funded;e['unfundedCents']=x-funded;e['amountCents']=funded;e['cashDeltaCents']=-funded;e['debtDeltaCents']=0;continue
            from_own=borrowed=0
            if debit_only(e): from_own=spend(x,'DFC')
            elif ok_funded(e):
                from_own=spend(x,'CF'); borrowed=borrow(x-from_own,d); from_own+=spend(x-from_own-borrowed,'D')
            else:
                from_own=spend(x,'F'); borrowed=borrow(x-from_own,d); from_own+=spend(x-from_own-borrowed,'CD')
            short=x-from_own-borrowed; arrears+=short; e['cashDeltaCents']=-from_own; e['debtDeltaCents']=borrowed
            if short>0:
                e['shortCents']=short
                if d<=through and e['kind']!='variable': snapshot['warnings'].append({'kind':'shortage','date':d,'eventId':e['id'],'name':e['name'],'amountCents':x,'shortCents':short})
        allv=sorted(lst+gen,key=event_key); run=opening; drun=debt_run; owed=open_arrears; minimum=opening; variable=0; by_category=[]
        for e in allv:
            run=safe(run+e['cashDeltaCents']); drun=safe(drun+e['debtDeltaCents']); owed=safe(owed+(-e['amountCents'] if e['kind']=='arrears' else e.get('shortCents',0))); e['cashAfterCents']=run; e['debtAfterCents']=drun; e['arrearsAfterCents']=owed; minimum=min(minimum,run)
            if e['kind']=='variable':
                variable+=e['amountCents']; by_category.append({'id':e['categoryId'],'name':e['name'],'amountCents':e['amountCents']})
        if run!=bal or drun!=debt_all() or owed!=arrears: raise ValueError('Projection state mismatch')
        debt_run=drun
        if d<=through: days.append({'date':d,'openingCashCents':opening,'closingCashCents':bal,'debtCents':drun,'arrearsCents':arrears,'netCents':bal-drun-arrears,'variableCents':variable,'byCategory':by_category,'minCashCents':minimum,'shortfallCents':arrears,'eventIds':[e['id'] for e in allv]})
        d=plus(d,1)
    if next_plan and head:
        next_plan.update(baseAvailableCents=head['availableCents'],targetCents=head['targetCents'],gapCents=head['gapCents'],averageDailyCents=head['spendableTargetCents']/next_plan['days'],savingsTargetCents=head['savingsTargetCents'],spendableTargetCents=head['spendableTargetCents'],reserveCents=head['reserveCents'],repayCents=head['repayCents'],savingsCents=head['savingsCents'],cashOutCents=head['cashOutCents'],toMonoCents=head['toMonoCents'],monoOffsetCents=head['monoOffsetCents'],categories=head['categories'],schedule=head['schedule'])
    if scenario is not None:
        base=next_plan['baseAvailableCents'] if next_plan else 0
        gain=total(e['amountCents'] for e in events if e['funding']=='credit' and next_plan['start']<=e['date']<next_plan['end'])-total(e['amountCents'] for e in scenario['repayments'] if next_plan['start']<=e['date']<next_plan['end']) if next_plan else 0
        scenario['cashPlanCents']=safe(base+gain); scenario['gapCents']=max(0,(next_plan['targetCents'] if next_plan else 1500000)-scenario['cashPlanCents'])
    visible=sorted([e for e in events if asof<=e['date']<=through],key=event_key)
    return {'snapshot':snapshot,'nextPlan':next_plan,'reason':None if next_plan else 'no_next_payout','currentPeriod':current_period,'untilPayout':until_payout,'periods':periods,'events':visible,'days':days,'scenario':scenario,'minSpend':min_spend}


# Окремий синтетичний/CLI API не запускає стару касову модель.
if len(sys.argv) > 1 and sys.argv[1] == '--monthly-period':
    print(json.dumps([monthly_period_budget(c['rows'], c['start'], c['end'], c.get('options')) for c in json.load(sys.stdin)], ensure_ascii=True))
    sys.exit(0)

if len(sys.argv) > 1 and sys.argv[1] == '--finance':
    print(json.dumps([finance_projection(c['data'], c.get('options', c)) for c in json.load(sys.stdin)], ensure_ascii=True))
    sys.exit(0)

if len(sys.argv) > 1 and sys.argv[1] == '--next-period':
    print(json.dumps([next_period_plan(c['data'], c['asof']) for c in json.load(sys.stdin)], ensure_ascii=True))
    sys.exit(0)


snap = json.load(open(sys.argv[1], encoding='utf-8-sig'))
if snap.get('account_tx') is not None:
    snap['accounts'] = derive_accounts(snap['accounts'], snap['account_tx'])
today = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
now = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else None
cfg = snap['salary']
RATE, SPLIT = float(cfg.get('rate') or 0), int(cfg['split_day'])
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
        (adj(y, m, ADV), 'аванс', salary_period_amount(cfg,y,m,1,SPLIT,cfg.get('advance_amount'))),
        (adj(y, m, SAL), 'зарплата', salary_period_amount(cfg,py,pm,SPLIT+1,plast,cfg.get('salary_amount'))),
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


def fixed_paid(txs):
    """п. 13: множина (id постійного платежу, YYYY-MM або W<понеділок>), оплачених операціями-витратами з fixed_id."""
    out = set()
    for t in txs or []:
        if t.get('fixed_id') is None or t.get('type') != 'expense':
            continue
        out.add((str(t['fixed_id']), payment_day(t)[:7]))
        wk = week_key(payment_day(t))
        if wk:
            out.add((str(t['fixed_id']), wk))  # тиждень пн-нд для щотижневих
    return out


PAID = fixed_paid(snap.get('account_tx'))


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
            if f.get('active') is False or f.get('period') == 'week' or not fixed_in_month(f,m):
                continue
            if f.get('id') is not None and (str(f['id']), f'{y:04d}-{m:02d}') in PAID:
                continue  # п. 13: оплачено в цьому місяці
            d = date(y, m, min(int(f['day_of_month']), last))
            if start <= d < end and not fixed_ended(f, d):
                amt = float(f['amount'])
                res.append((d, f['name'], amt if f['type'] != 'income' else -amt, f.get('credit_ok') is True))
        for c in snap['credits'] or []:
            d = date(y, m, min(int(c['payment_day']), last))
            if not (start <= d < end):
                continue
            if any(t.get('type') == 'expense' and str(t.get('credit_id')) == str(c.get('id')) and payment_day(t)[:7] == f'{y:04d}-{m:02d}' for t in snap.get('account_tx') or []):
                continue
            first = c['start_year'] * 12 + c['start_month']
            cur = d.year * 12 + (d.month - 1)
            if first <= cur <= first + int(c['total_payments']) - 1:
                ok = c.get('credit_ok')
                ok = bool(ok) if ok is not None else 'privat' in str(c.get('source') or '').lower()
                res.append((d, c['name'] + ' (розстрочка)', float(c['monthly_amount']), ok))
    # щотижневі постійні: кожна дата з ISO-днем weekday у [start, end), оплачений тиждень пропускаємо
    for f in snap['fixed'] or []:
        w = week_day(f)
        if f.get('active') is False or f.get('period') != 'week' or w is None:
            continue
        d = start + timedelta(days=(w - 1 - start.weekday()) % 7)
        while d < end and not fixed_ended(f, d):
            if not (f.get('id') is not None and (str(f['id']), week_key(d.isoformat())) in PAID):
                amt = float(f['amount'])
                res.append((d, f['name'], amt if f['type'] != 'income' else -amt, f.get('credit_ok') is True))
            d += timedelta(days=7)
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
               and t.get('type') == 'expense' and t.get('transfer_id') is None and tx_day(t)[:7] == month]
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


# п. 12: каса по датах. Борг кредитного рахунку за місяць M гаситься за спільним правилом repay_plan (минуле: «зараз»)
def repay_date(month):
    return date.fromisoformat(repay_plan(month, t_now.isoformat()))


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
    кредитні обовʼязкові з датою >= «зараз» і борг кредитних рахунків мінус з виплати 21-го M+1, комісія п. 11 мінус 1-го."""
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
    print(f"  {d}  {n:<32} {a:>10.2f}  {'кредитна, гаситься з найближчої виплати' if ok else 'біла'}")
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
    'horizon': str(horizon), 'startCash': start_cash, 'timeline': timeline, 'periods': periods,
    'paidFixed': [list(x) for x in sorted(PAID)]}, ensure_ascii=False))
