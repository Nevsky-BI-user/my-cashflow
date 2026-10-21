# Правило бюджету періоду: periodBudget з index.html проти еталону scripts/budget_pool.py на знімку spec/fixtures
import json
import subprocess
import sys

from datetime import date

from helpers import ROOT, SHOTS, SPEC, check, finance_ref, current_ref, demo_snapshot, expand_groups, freeze, go_tab, num, open_payout, shot

FIX = SPEC / 'fixtures' / 'snapshot.json'
# (дата сьогодні, зміна боргу кредитки або None): звичайний день, день самої виплати, дефіцит, бюджет у мінусі
# третій елемент: «зараз» для вікна білих платежів whiteDue (None: увесь період)
CASES = [('2026-10-08', None, None), ('2026-10-21', None, None), ('2026-11-05', None, None), ('2026-10-08', 40000, None),
         ('2026-10-08', 100000, None), ('2026-10-08', None, '2026-10-26'), ('2026-10-20', None, '2026-10-08')]
# whiteDue і cashNow з п. 12 рахує каса по датах (cashCore), їх звіряє spec/checks/money.py
NUMS = ['oblSum', 'own', 'debt', 'deficit', 'pool0', 'savings', 'varPool', 'oblWhite']


def reference(snap, today, now=None):
    tmp = SPEC / '.out' / 'budget_snapshot.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    out = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), str(tmp), today] + ([now] if now else []),
                         capture_output=True, text=True, encoding='utf-8', check=True, env={'PYTHONUTF8': '1', **__import__('os').environ}).stdout
    line = [x for x in out.splitlines() if x.startswith('JSON ')]
    check(line, f'еталон не надрукував JSON для {today}')
    return json.loads(line[-1][5:])


def math(page):
    base = json.loads(FIX.read_text(encoding='utf-8'))
    check(page.evaluate("typeof window.periodBudget==='function'"), 'window.periodBudget не функція')
    # Історичний CLI не має подій поточного демо-прогнозу застосунку.
    page.evaluate('setRepayEvents([],[])')
    for today, debt, now in CASES:
        snap = json.loads(json.dumps(base))
        if debt is not None:
            snap['accounts'][1]['debt'] = debt
        ref = reference(snap, today, now)
        # план п. 12: виплата − чисті відтоки каси періоду (погашення кредитки з виплати 21-го M+1) − накопичення
        js = page.evaluate("""([t,s,n])=>periodBudget(t,s.salary,s.accounts,s.fixed,s.credits,s.salary.savings_pct,n||undefined)""", [today, snap, now])
        tag = f'{today}' + (f', борг {debt}' if debt is not None else '') + (f', зараз {now}' if now else '')
        check(js['payout']['date'] == ref['payout']['date'] and js['payout']['kind'] == ref['payout']['kind'],
              f'{tag}: виплата JS {js["payout"]}, еталон {ref["payout"]}')
        check(abs(js['payout']['amount'] - ref['payout']['amount']) <= 0.01, f'{tag}: сума виплати JS {js["payout"]["amount"]}, еталон {ref["payout"]["amount"]}')
        check(js['end'] == ref['end'], f'{tag}: кінець періоду JS {js["end"]}, еталон {ref["end"]}')
        jo = [(o['date'], o['name'], round(o['amount'], 2), o['creditOk']) for o in js['obligations']]
        ro = [(o['date'], o['name'], round(o['amount'], 2), o['creditOk']) for o in ref['obligations']]
        check(jo == ro, f'{tag}: обовʼязкові JS {jo}, еталон {ro}')
        for k in NUMS:
            check(abs(js[k] - ref[k]) <= 0.01, f'{tag}: {k} JS {js[k]}, еталон {ref[k]}')


# --- ПК-Бюджет на демо-даних із замороженою датою ---
DAY = '2026-10-08'
# фікстура «горить»: демо-витрата на транспорт 900 ₴ (txDemo стискає дні до сьогодні: 28 -> 7 жовтня, у періоді)
HOT_ROW = "[28,'Uklon',900,'out','mono',4121,'transport'],"
PATCH = [('TX_DEMO_ROWS=[', 'TX_DEMO_ROWS=[' + HOT_ROW)]


def expected(page, today):
    """Очікуване з демо-операцій і еталона budget_pool.py: період, бюджет, витрати за категоріями, «горить»."""
    t = date.fromisoformat(today)
    # Повна проєкція Python перевіряє браузер; тут читаємо поточну ціль.
    projection = finance_ref(page)
    cur = next(p for p in projection['periods'] if p['basis']=='current')
    ref = dict(payout={'date':cur['start']}, end=cur['end'], varPoolCur=cur['targetCents']/100, gap=max(0,cur['targetCents']-cur['availableCents'])/100, perDay=(projection['currentPeriod']['remainingTargetCents']/100/max(1,len(projection['currentPeriod']['futureSchedule']))))
    start, end = date.fromisoformat(ref['payout']['date']), date.fromisoformat(ref['end'])
    cats = page.evaluate("BCAT.map(c=>({id:c.id,name:c.name,limit:c.limit}))")
    txs = page.evaluate("([y,m])=>txDemo(y,m)", [start.year, start.month - 1])
    spend, ops = {}, {}
    for x in txs:
        d = date.fromisoformat(x['date'])
        # застосунок бере операції періоду з місяця, у якому період почався (periodTl)
        if x['type'] != 'expense' or not x['category_id'] or not (start <= d < end):
            continue
        spend[x['category_id']] = spend.get(x['category_id'], 0) + x['amount']
        ops[x['category_id']] = ops.get(x['category_id'], 0) + 1
    hot = set()  # Поточний факт не порівнюємо з залишковим планом від завтра.
    names = {c['id']: c['name'] for c in cats}
    return ref, start, end, {names[k]: v for k, v in spend.items()}, {names[k]: v for k, v in ops.items()}, hot


def kpi(page, cls):
    return page.locator(f'.{cls} .bud-kpi-v').inner_text()


def desktop(page):
    """Стабільний місячний план; суми перевіряються незалежно від адаптера."""
    from checks.monthly_budget import seed_demo
    seed_demo(page, DAY, PATCH)
    ref, start, end, spend, ops, hot = expected(page, DAY)
    pb=page.evaluate("window.__periodBudget")
    check(pb['A']==pb['ownAt']-pb['reserve']-pb['repay'],'payout allocation formula changed')
    # Фікстура має збережений жовтень: план періоду — точні частки категорій
    # і нерозподіленого залишку, а не старий мінімум 15 000 ₴.
    saved=page.evaluate("window.__financeInput.monthly_budgets[0]")
    check(pb['start'][:7]=='2026-10' and pb['end'][:7]=='2026-10','fixture period moved outside October')
    first=date.fromisoformat(pb['start']).day-1
    stop=date.fromisoformat(pb['end']).day-1
    pool=max(0,saved['total_cents']-sum(x['amount_cents'] for x in saved.get('mandatory_items',[])))
    parts=list(saved['allocations'].values())
    parts.append(pool-sum(parts))
    planned=sum(amount*stop//31-amount*first//31 for amount in parts)
    check(pb['budget']==planned,'period target differs from saved monthly category slices')
    check(pb['avail']==page.evaluate('window.__financeProjection.currentPeriod.remainingTargetCents'),'spendable ignores remaining monthly caps')
    go_tab(page,1)
    check(page.locator('.bud-kpis .bud-kpi').count()==4,'four monthly KPIs')
    check(num(kpi(page,'bud-pool'))==30000,'saved monthly total')
    raw=page.evaluate("txDemo(2026,9)")
    valid=[t for t in raw if t['type']=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None and '2026-10-01'<=t['date'][:10]<=DAY]
    fact=sum(round(t['amount']*100) for t in valid)/100
    check(abs(num(kpi(page,'bud-spent'))-fact)<.01,'month fact from raw operations')
    check(abs(num(kpi(page,'bud-sav'))-(30000-fact))<.01,'month remaining')
    expand_groups(page)
    for c in page.evaluate('BCAT'):
        f=sum(round(t['amount']*100) for t in valid if str(t.get('category_id'))==str(c['id']))/100
        row=page.locator('.bud-cat[data-cat="'+str(c['id'])+'"]')
        check(abs(num(row.locator('.bud-value[data-label="Факт"]').inner_text())-f)<.01,'category fact')
        check(num(row.locator('.bud-remaining').inner_text())==1000-f,'category remaining')
    check(page.locator('.bud-cat.hot').count()==0,'linear daily expectation returned')
    check(all(label in page.locator('.bud-table-head').inner_text() for label in ('Факт','План','Залишок')),'monthly category columns lack explicit labels')
    for width,height in [(1280,800),(1910,917)]:
        page.set_viewport_size(dict(width=width,height=height))
        page.wait_for_timeout(300)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'horizontal overflow')
        shot(page,'monthly-budget-'+str(width)+'.jpg')
    page.locator('.bud-cat[data-cat=food]').click()
    check(page.locator('.cat-op').count()==sum(t.get('category_id')=='food' for t in valid),'drawer month operations')
    page.keyboard.press('Escape')
    check(page.locator('.cat-drw').count()==0,'drawer Escape')
    page.locator('.bud-cat[data-cat=food]').click()
    page.locator('.cat-to-flow').click()
    check('Місяць' in page.locator('.flow-scope button.on').inner_text(),'monthly Flow scope')
    check(page.locator('.flow-row.tx').count()==sum(t.get('category_id')=='food' for t in valid),'Flow month operations')


def default_period(page):
    """Період за замовчуванням відкрила остання виплата не пізніше сьогодні: реальна дата і три заморожені."""
    for day in (None, '2026-10-08', '2026-10-03', '2026-10-21'):
        if day:
            freeze(page, day)
        t = date.fromisoformat(day) if day else date.today()
        d, kind = open_payout(t)
        got = page.locator('.side-pname').inner_text()
        check(got.startswith(str(d.day)), f'{t}: період «{got}», очікували від {d} ({kind})')


def future_period(page):
    freeze(page,DAY)
    go_tab(page,1)
    page.locator('.side-arr').nth(1).click()
    check(page.locator('.p-budget').get_attribute('data-month')=='2026-11-01','next calendar month')
    check(num(kpi(page,'bud-spent'))==0,'future actual spend')
    from checks.budget_period_parity import assert_unsaved_salary
    assert_unsaved_salary(page,'2026-11-01')
    line=page.locator('.bud-plan')
    check(line.count()==1 and line.get_attribute('y1')==line.get_attribute('y2'),'future salary envelope must show a constant category limit')


def mobile(page):
    from checks.monthly_budget import seed_demo
    seed_demo(page,DAY,PATCH)
    go_tab(page,1)
    check(page.locator('.p-budget.desk').count()==0,'desktop composition on phone')
    check(num(kpi(page,'bud-pool'))==30000,'mobile monthly total')
    b=page.evaluate('window.__calendarBudget')
    check(num(kpi(page,'bud-spent'))==b['fact']/100,'mobile monthly facts')
    page.set_viewport_size(dict(width=390,height=844))
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'mobile horizontal overflow')
    shot(page,'monthly-budget-390.jpg')


CHECKS = [
    ('Legacy periodBudget: ізольована сумісність (7 випадків)', 'desktop', math),
    ('ПК-Бюджет: ціль, факт/майбутній план, операції та У Потік', 'desktop', desktop),
    ('Період за замовчуванням містить сьогодні', 'desktop', default_period),
    ('ПК-Бюджет: період, що ще не почався', 'desktop', future_period),
    ('Бюджет на телефоні: витрати періоду', 'mobile', mobile),
]
