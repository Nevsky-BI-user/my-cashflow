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
import calendar, json, re, sys
from datetime import date, datetime, timedelta


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


def week_key(day):
    """Ключ тижня оплати: 'W' + понеділок тижня дати YYYY-MM-DD; некоректна дата: None."""
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        return None
    d = date.fromisoformat(day)
    return 'W' + (d - timedelta(days=d.weekday())).isoformat()


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
            amount = cents(rate/weekdays(sy,sm,1,last)*weekdays(sy,sm,lo,hi))/100 if rate>0 else float(cfg.get(kind+'_amount') or 0)
            if d>current and amount>0:
                upcoming.append({'date':d.isoformat(),'kind':kind,'amount':amount,'amountCents':cents(amount)})
    upcoming.sort(key=lambda p:p['date'])
    if not upcoming:
        return missing
    nxt = upcoming[0]
    after = next((p for p in upcoming if p['date']>nxt['date']),None)
    if not after:
        return missing
    start,end = date.fromisoformat(nxt['date']),date.fromisoformat(after['date'])
    txs = data.get('transactions',data.get('account_tx',[]))
    accounts = [a for a in derive_accounts(data.get('accounts',[]),txs) if a.get('active') is not False]
    stamps = [parse_ts(a['balance_updated_at']) for a in accounts if not a.get('mono_account_id') and a.get('balance_updated_at')]
    adjustment = cents(sum(float(t['amount'])*(1 if t.get('type')=='income' else -1) for t in txs if t.get('account_id') is None and t.get('source')!='mono' and stamps and parse_ts(t['created_at'])>min(stamps)))
    own = max(0,total([max(0,cents(a.get('balance'))) for a in accounts]+[adjustment]))
    debt = total(max(0,cents(a.get('debt'))) for a in accounts if a.get('kind')=='credit')
    paid = {(str(t['fixed_id']),str(t.get('date') or t.get('created_at') or '')[:7]) for t in txs if t.get('fixed_id') is not None and t.get('type')=='expense'}
    paid |= {(str(t['fixed_id']),week_key(str(t.get('date') or t.get('created_at') or '')[:10])) for t in txs if t.get('fixed_id') is not None and t.get('type')=='expense'}
    entries = []
    for k in range(start.year*12+start.month-1,end.year*12+end.month):
        y,m0=divmod(k,12); m=m0+1; last=calendar.monthrange(y,m)[1]
        for f in data.get('fixed',[]):
            if f.get('active') is False or f.get('period')=='week' or (str(f.get('id')),f'{y:04d}-{m:02d}') in paid:
                continue
            d=date(y,m,min(int(f['day_of_month']),last))
            if start<=d<end:
                entries.append((cents(f['amount'])*(-1 if f['type']=='income' else 1),f.get('credit_ok') is True))
        for c in data.get('credits',[]):
            d=date(y,m,min(int(c['payment_day']),last)); first=int(c['start_year'])*12+int(c['start_month'])
            if start<=d<end and first<=k<first+int(c['total_payments']):
                entries.append((cents(c['monthly_amount']),c.get('credit_ok') is True))
    # щотижневі постійні: кожна дата з ISO-днем weekday у [start; end), оплачений тиждень пропускаємо
    for f in data.get('fixed',[]):
        w=week_day(f)
        if f.get('active') is False or f.get('period')!='week' or w is None:
            continue
        d=start+timedelta(days=(w-1-start.weekday())%7)
        while d<end:
            if (str(f.get('id')),week_key(d.isoformat())) not in paid:
                entries.append((cents(f['amount'])*(-1 if f['type']=='income' else 1),f.get('credit_ok') is True))
            d+=timedelta(days=7)
    mandatory=total(a for a,_ in entries if a>0)
    income=total(-a for a,_ in entries if a<0)
    eligible=total(a for a,ok in entries if a>0 and ok)
    base=total([total([own,nxt['amountCents']]),-total([mandatory,debt])])
    target=max(1500000,base); gap=total([target,-base]); days=(end-start).days
    # категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit
    expense_cats=[c for c in data.get('categories',[]) if c.get('active') is not False and c.get('type')=='expense']
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
                amount=cents(rate/weekdays(sy,sm,1,last)*weekdays(sy,sm,1 if kind=='advance' else int(cfg['split_day'])+1,int(cfg['split_day']) if kind=='advance' else last)) if rate>0 else cents(cfg.get(kind+'_amount'))
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
    # витрата з fixed_id закриває місяць своєї дати і тиждень пн-нд; витрата з credit_id: розстрочку свого місяця
    paid=set()
    for t in txs:
        if t.get('type')=='expense' and t.get('fixed_id') is not None:
            paid.add(sid(t['fixed_id'])+'|'+txdate(t)[:7])
            if week_key(txdate(t)): paid.add(sid(t['fixed_id'])+'|'+week_key(txdate(t)))
    paid_credit={sid(t['credit_id'])+'|'+txdate(t)[:7] for t in txs if t.get('type')=='expense' and t.get('credit_id') is not None}
    for k in range(mi(asof),mi(end_generation)+1):
        y,m=ym(k); month=dt(y,m,1)[:7]; last=calendar.monthrange(y,m)[1]
        for i,f in enumerate(data.get('fixed',[])):
            if weekly(f): continue
            d=dt(y,m,min(int(f['day_of_month']),last))
            if f.get('active') is False or d<asof or d>end_generation or (f.get('id') is not None and sid(f['id'])+'|'+month in paid): continue
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
        while d<=end_generation:
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
        rows=sorted([t for t in txs if sid(t.get('account_id'))==sid(a['id']) and t.get('type')=='expense' and txdate(t)[:7]==asof[:7]],key=lambda t:(txdate(t),str(t.get('created_at','')),cents(t.get('amount'))))
        for t in rows:
            spent+=cents(t.get('amount'))
            if met is None and spent>=cents(a.get('min_spend')): met=txdate(t)
        row={'accountId':a['id'],'month':asof[:7],'spent':spent/100,'min':cents(a.get('min_spend'))/100,'fee':cents(a.get('min_spend_fee'))/100,'left':max(0,cents(a.get('min_spend'))-spent)/100}
        if met: row['metOn']=met
        min_spend.append(row)
    order={'payout':0,'income':1,'repay':2,'mandatory':3,'fee':4,'variable':5}
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
            actual=total(cents(t.get('amount')) for t in txs if sid(t.get('account_id'))==sid(a['id']) and t.get('type')=='expense' and txdate(t)[:7]==month)
            assigned=0 if month==asof[:7] else total(e['amountCents'] for e in events if e['kind']=='mandatory' and sid(e.get('accountId'))==sid(a['id']) and e['date'][:7]==month)
            if actual+assigned<cents(a.get('min_spend')): events.append(make('fee:'+sid(a['id'])+':'+month,d,'Комісія: '+str(a.get('name') or a['id']),'fee',cents(a.get('min_spend_fee')),{'accountId':a['id'],'certainty':'conditional'}))
    # категорія з limit_abs: сума в гривнях (budget_limit ігнорується), інакше вага budget_limit
    expense_cats=[c for c in data.get('categories',[]) if c.get('active') is not False and c.get('type')=='expense']
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
    def distribution(target,start,end,available,caps=None):
        count=distance(start,end); rows,totals=split(target if count>0 else 0,caps); remaining=totals[:]; schedule=[]; balance=available
        for i in range(count):
            spend=target//count+int(i<target%count); amounts=remaining[:] if i==count-1 else allocate(spend,remaining); remaining=[v-a for v,a in zip(remaining,amounts)]; balance=safe(balance-spend)
            schedule.append({'date':plus(start,i),'spendCents':spend,'remainingCents':balance,'byCategory':[{'id':c['id'],'name':c['name'],'amountCents':a} for c,a in zip(rows,amounts)]})
        return {'categories':[{**c,'totalCents':a} for c,a in zip(rows,totals)],'schedule':schedule}
    def between(start,end): return [e for e in events if start<=e['date']<end and e['kind']!='variable']
    def mandatory(start,end): return total(e['amountCents'] for e in between(start,end) if e['kind'] in ('mandatory','fee'))
    # до наступної виплати: власні кошти мінус обовʼязкові й комісії [asof; виплата); борг карток гаситься з виплати
    until_payout=None
    if next_date:
        left_days=distance(asof,next_date); left=safe(own-mandatory(asof,next_date))
        until_payout={'end':next_date,'days':left_days,'cents':left,'dailyCents':left//left_days if left>0 and left_days>0 else 0}
    next_plan=current_period=None; periods=[]
    if has_plan:
        nxt=payout_at(next_date); after=payout_at(following); reserved=mandatory(next_date,following); base=safe(own+nxt['amountCents']-reserved-debt); target=max(1500000,base)
        next_plan={'start':next_date,'end':following,'days':distance(next_date,following),'nextPayout':nxt,'followingPayout':after,'positiveOwnCents':own,'debtCents':debt,'mandatoryCents':reserved,'otherIncomeCents':total(e['amountCents'] for e in between(next_date,following) if e['kind']=='income'),'eligibleMandatoryCents':total(e['amountCents'] for e in between(next_date,following) if e['kind']=='mandatory' and e.get('creditEligible')),'baseAvailableCents':base,'targetCents':target,'gapCents':max(0,target-base),'averageDailyCents':target/distance(next_date,following),**distribution(target,next_date,following,base)}
        # темп щоденних витрат від завтра до дня перед виплатою: більше з 15 000 ₴ на весь період [start; виплата) і untilPayout на дні, що лишились
        start=next((d for d in reversed(payout_dates) if d<=asof),asof); actual=total(cents(t.get('amount')) for t in txs if t.get('type')=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None and txdate(t)>=start); mandatory_now=mandatory(asof,next_date); available=safe(cash-mandatory_now)
        period_days=distance(start,next_date); left_days=max(0,distance(plus(asof,1),next_date)); floor_left=1500000*left_days//period_days if period_days>0 else 0; free_left=max(0,until_payout['cents'] if until_payout else 0); remaining=max(floor_left,free_left) if left_days>0 else 0; target=actual+remaining
        # сума в гривнях на прогноз від завтра: ліміт мінус факт змінних витрат категорії з початку періоду, не нижче 0
        caps=[max(0,c['limitAbsCents']-total(cents(t.get('amount')) for t in txs if t.get('type')=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None and txdate(t)>=start and t.get('category_id') is not None and sid(t['category_id'])==c['id'])) if 'limitAbsCents' in c else 0 for c in categories]
        dist=distribution(remaining,plus(asof,1),next_date,available,caps)
        current_period={'start':start,'end':next_date,'actualVariableCents':actual,'targetCents':target,'remainingTargetCents':remaining,'periodDays':period_days,'leftDays':left_days,'dailyCents':remaining/left_days if left_days>0 else 0,'futureSchedule':dist['schedule']}
        periods.append({'start':start,'end':next_date,'basis':'current','openingCashCents':cash,'payoutCents':0,'mandatoryCents':mandatory_now,'debtReserveCents':0,'availableCents':available,'targetCents':target,'gapCents':max(0,remaining-available),**dist})
        future=[d for d in payout_dates if d>asof]
        for i in range(len(future)-1):
            start,end=future[i:i+2]
            if start>through: break
            opening=safe(cash+total(e['cashDeltaCents'] for e in events if asof<=e['date']<start)-total(d['spendCents'] for p in periods for d in p['schedule'] if d['date']<start)); entries=between(start,end); payout=total(e['amountCents'] for e in entries if e['kind']=='payout'); reserved=mandatory(start,end); scheduled_repay=total(e['amountCents'] for e in entries if e['kind']=='repay'); outstanding_debt=safe(debt+total(e['debtDeltaCents'] for e in events if e['date']<start)); new_repay=total(e['amountCents'] for e in entries if e['kind']=='repay' and e['id'].startswith('scenario-repay:') and any(v['funding']=='credit' and start<=v['date']<end and e['id']=='scenario-repay:'+v['occurrenceId']+':'+sid(v.get('accountId')) for v in events)); debt_reserved=outstanding_debt+new_repay; available=safe(opening+total(e['cashDeltaCents'] for e in entries)+scheduled_repay-debt_reserved); target=next_plan['targetCents'] if i==0 else max(1500000,available)
            periods.append({'start':start,'end':end,'basis':'headline' if i==0 else 'projected','openingCashCents':opening,'payoutCents':payout,'mandatoryCents':reserved,'debtReserveCents':debt_reserved,'availableCents':available,'targetCents':target,'gapCents':max(0,target-available),**distribution(target,start,end,available)})
    if scenario is not None:
        base=next_plan['baseAvailableCents'] if next_plan else 0
        gain=total(e['amountCents'] for e in events if e['funding']=='credit' and next_plan['start']<=e['date']<next_plan['end'])-total(e['amountCents'] for e in scenario['repayments'] if next_plan['start']<=e['date']<next_plan['end']) if next_plan else 0
        scenario['cashPlanCents']=safe(base+gain); scenario['gapCents']=max(0,(next_plan['targetCents'] if next_plan else 1500000)-scenario['cashPlanCents'])
    for p in periods:
        for d in p['schedule']:
            for c in d['byCategory']:
                if c['amountCents']>0: events.append(make('variable:'+d['date']+':'+c['id'],d['date'],c['name'],'variable',c['amountCents'],{'categoryId':c['id']}))
    visible=sorted([e for e in events if asof<=e['date']<=through],key=event_key); days=[]; d=asof
    while d<=through:
        opening=cash; today=[e for e in visible if e['date']==d]; by_category=[]; minimum=cash; variable=0
        for e in today:
            cash=safe(cash+e['cashDeltaCents']); debt=safe(debt+e['debtDeltaCents']); e['cashAfterCents']=cash; e['debtAfterCents']=debt; minimum=min(minimum,cash)
            if e['kind']=='variable':
                variable+=e['amountCents']; by_category.append({'id':e['categoryId'],'name':e['name'],'amountCents':e['amountCents']})
        days.append({'date':d,'openingCashCents':opening,'closingCashCents':cash,'debtCents':debt,'netCents':cash-debt,'variableCents':variable,'byCategory':by_category,'minCashCents':minimum,'shortfallCents':max(0,-minimum),'eventIds':[e['id'] for e in today]}); d=plus(d,1)
    return {'snapshot':snapshot,'nextPlan':next_plan,'reason':None if next_plan else 'no_next_payout','currentPeriod':current_period,'untilPayout':until_payout,'periods':periods,'events':visible,'days':days,'scenario':scenario,'minSpend':min_spend}


# Окремий синтетичний/CLI API не запускає стару касову модель.
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
        (adj(y, m, ADV), 'аванс', round(RATE / wd(y, m, 1, last) * wd(y, m, 1, SPLIT), 2) if RATE > 0 else float(cfg.get('advance_amount') or 0)),
        (adj(y, m, SAL), 'зарплата', round(RATE / wd(py, pm, 1, plast) * wd(py, pm, SPLIT + 1, plast), 2) if RATE > 0 else float(cfg.get('salary_amount') or 0)),
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
        out.add((str(t['fixed_id']), str(t.get('date') or t.get('created_at') or '')[:7]))
        wk = week_key(str(t.get('date') or t.get('created_at') or '')[:10])
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
            if f.get('active') is False or f.get('period') == 'week':
                continue
            if f.get('id') is not None and (str(f['id']), f'{y:04d}-{m:02d}') in PAID:
                continue  # п. 13: оплачено в цьому місяці
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
    # щотижневі постійні: кожна дата з ISO-днем weekday у [start, end), оплачений тиждень пропускаємо
    for f in snap['fixed'] or []:
        w = week_day(f)
        if f.get('active') is False or f.get('period') != 'week' or w is None:
            continue
        d = start + timedelta(days=(w - 1 - start.weekday()) % 7)
        while d < end:
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
    print(f"  {d}  {n:<32} {a:>10.2f}  {'кредитна, гаситься з виплати 21-го наступного місяця' if ok else 'біла'}")
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
