# Правило бюджету періоду: periodBudget з index.html проти еталону scripts/budget_pool.py на знімку spec/fixtures
import json
import subprocess
import sys

from datetime import date

from helpers import ROOT, SHOTS, SPEC, check, current_ref, demo_snapshot, freeze, go_tab, num, open_payout, shot

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
    for today, debt, now in CASES:
        snap = json.loads(json.dumps(base))
        if debt is not None:
            snap['accounts'][1]['debt'] = debt
        ref = reference(snap, today, now)
        # план п. 12: виплата − чисті відтоки каси періоду (погашення кредитки 24-го M+1) − накопичення
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
    # знімок застосунку (рахунки, операції з мітками, витрати періоду): еталон дає і плановий varPool, і обмежений varPoolCur
    ref = current_ref(page.evaluate('window.__cashSnap()'), today, today)
    start, end = date.fromisoformat(ref['payout']['date']), date.fromisoformat(ref['end'])
    cats = page.evaluate("BCAT.map(c=>({id:c.id,name:c.name,limit:c.limit}))")
    total = sum(c['limit'] for c in cats)
    txs = page.evaluate("([y,m])=>txDemo(y,m)", [start.year, start.month - 1])
    spend, ops = {}, {}
    for x in txs:
        d = date.fromisoformat(x['date'])
        # застосунок бере операції періоду з місяця, у якому період почався (periodTl)
        if x['type'] != 'expense' or not x['category_id'] or not (start <= d < end):
            continue
        spend[x['category_id']] = spend.get(x['category_id'], 0) + x['amount']
        ops[x['category_id']] = ops.get(x['category_id'], 0) + 1
    days = (end - start).days
    frac = 0 if t < start else min(days, (t - start).days + 1) / days
    # категорії ділять обмежений готівкою бюджет поточного періоду (DESIGN.md п. 5)
    pool = ref['varPoolCur']
    hot = set()
    for c in cats:
        plan = pool * c['limit'] / total
        f = spend.get(c['id'], 0)
        if f > 0 and (plan <= 0 or f / plan > frac + 0.1):
            hot.add(c['name'])
    names = {c['id']: c['name'] for c in cats}
    return ref, start, end, {names[k]: v for k, v in spend.items()}, {names[k]: v for k, v in ops.items()}, hot


def kpi(page, cls):
    return page.locator(f'.{cls} .bud-kpi-v').inner_text()


def desktop(page):
    freeze(page, DAY, PATCH)
    ref, start, end, spend, ops, hot = expected(page, DAY)
    check(start <= date.fromisoformat(DAY) < end, f'еталон: період {start}..{end} не містить {DAY}')
    go_tab(page, 1)
    check(page.locator('.p-budget.desk').count() == 1, 'на ПК немає .p-budget.desk')
    check(page.locator('.bud-kpis .bud-kpi').count() == 4, 'KPI-рядок не з 4 карток')
    lbl = page.locator('.side-pname').inner_text()
    check(lbl.startswith(str(start.day)), f'період у бічній панелі «{lbl}», очікували від {start}')
    v = num(kpi(page, 'bud-pool'))
    check(abs(v - ref['varPoolCur']) <= 1, f'«Бюджет періоду» {v}, еталон budget_pool.py varPoolCur {ref["varPoolCur"]:.2f}')
    if ref['varPoolCur'] < ref['planCur'] - 0.5:
        check('обмежено готівкою' in page.inner_text('.bud-pool .bud-cap'), 'немає підпису «обмежено готівкою»')
        check(abs(num(page.inner_text('.bud-pool .bud-plan')) - ref['planCur']) <= 1, 'плановий бюджет у підписі не той')
    sv = num(kpi(page, 'bud-sav'))
    check(sv == round(ref['savings']), f'«Накопичення періоду» {sv}, еталон {ref["savings"]:.2f}')
    total = sum(spend.values())
    got = num(kpi(page, 'bud-spent'))
    check(got == round(total), f'«Витрачено» {got}, сума демо-операцій періоду {total}')
    left = (end - date.fromisoformat(DAY)).days
    pd = num(kpi(page, 'bud-day'))
    want = ref['perDay']
    check(abs(pd - want) <= 1, f'«На день лишилось» {pd}, еталон perDay {want:.2f}')
    print(f'      ПК-Бюджет {DAY}: бюджет {v}, витрачено {got}, на день {pd}, накопичення {sv}; '
          f'еталон varPool {ref["varPool"]:.2f}, varPoolCur {ref["varPoolCur"]:.2f}, savings {ref["savings"]:.2f}, витрати {total}, «горить» {sorted(hot)}')
    rows = page.evaluate("""[...document.querySelectorAll('.bud-cat')].map(e=>({n:e.querySelector('.bud-name').textContent,
f:e.querySelector('.bud-nums b').textContent,hot:e.classList.contains('hot'),idle:e.classList.contains('idle')}))""")
    check(len(rows) == page.evaluate('BCAT.length'), f'{len(rows)} категорій замість усіх')
    for r in rows:
        f = num(r['f'])
        check(f == round(spend.get(r['n'], 0)), f'{r["n"]}: факт {f}, сума операцій періоду {spend.get(r["n"], 0)}')
        check(r['idle'] == (f == 0), f'{r["n"]}: сірий стан не збігається з витратами')
    got_hot = {r['n'] for r in rows if r['hot']}
    check(hot and got_hot == hot, f'«горить» {got_hot}, очікували {hot}')
    check(page.locator('.bud-cat.hot .bud-hot').count() == len(hot), 'немає бейджа «горить»')
    check(page.locator('.bud-pace path.bud-fact').count() == 1 and page.locator('.bud-pace .bud-plan').count() == 1,
          'графік темпу без ліній')
    check(page.locator('.bud-top .bud-row').count() >= 1, 'топ-5 місць порожній')
    shot(page, 'budget-1280.jpg')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    shot(page, 'budget-1920.jpg')
    # клік по категорії, що горить: операції за період і «У Потік»
    # (знімок на весь екран міняє розмір вікна і скидає стан компонентів, тому вікно спершу високе, знімок без full_page)
    name = sorted(hot)[0]
    for w, hh, f in ((1920, 1300, 'budget-cat-1920.jpg'), (1280, 1400, 'budget-cat-1280.jpg')):
        page.set_viewport_size({'width': w, 'height': hh})
        page.wait_for_timeout(300)
        if page.locator('.bud-ops').count() == 0:
            page.locator('.bud-cat', has_text=name).click()
            page.wait_for_timeout(300)
        n = page.locator('.bud-ops .bud-op').count()
        check(n == min(20, ops.get(name, 0)), f'{name}: {n} операцій у картці, очікували {ops.get(name, 0)}')
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f), quality=80, type='jpeg')
    page.locator('.bud-to-flow').click()
    page.wait_for_timeout(400)
    check(page.locator('.p-flow.desk').count() == 1, '«У Потік» не перемкнув вкладку')
    on = page.locator('.flow-cats .flow-chip.on').all_inner_texts()
    check(len(on) == 1 and name in on[0], f'фільтр категорій у Потоці {on}, очікували {name}')
    check('Період' in page.locator('.flow-scope button.on').inner_text(), 'обсяг вибірки не «Період»')
    fr = page.locator('.flow-row.tx').count()
    check(fr == ops.get(name, 0), f'у Потоці {fr} операцій, очікували {ops.get(name, 0)}')


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
    """Період, що ще не почався: «Витрачено» 0, «період почнеться», лише лінія плану."""
    freeze(page, DAY)
    go_tab(page, 1)
    page.locator('.side-arr').nth(1).click()
    page.wait_for_timeout(300)
    check(page.locator('.side-pname').inner_text().startswith('21'), 'стрілка не перейшла на період авансу 21.10')
    check(num(kpi(page, 'bud-spent')) == 0, '«Витрачено» не 0 для майбутнього періоду')
    check('період почнеться 21.10' in page.locator('.bud-spent').inner_text(), 'немає «період почнеться 21.10»')
    check('почнеться через 13 дн.' in page.locator('.bud-day').inner_text(), 'немає «почнеться через 13 дн.»')
    check(page.locator('.bud-pace path.bud-fact').count() == 0, 'у майбутньому періоді є лінія факту')
    check(page.locator('.bud-cat.hot').count() == 0, 'у майбутньому періоді щось «горить»')


def mobile(page):
    """Телефон: розмітка та сама, витрати з періоду (не з усього місяця)."""
    freeze(page, DAY, PATCH)
    ref, start, end, spend, ops, hot = expected(page, DAY)
    go_tab(page, 1)
    check(page.locator('.p-budget.desk').count() == 0, 'на телефоні ПК-розмітка')
    total = round(sum(spend.values()))
    month_total = round(sum(x['amount'] for x in page.evaluate("([y,m])=>txDemo(y,m)", [start.year, start.month - 1])
                            if x['type'] == 'expense' and x['category_id']))
    check(total != month_total, 'фікстура не розрізняє період і місяць')
    head = page.locator('.p-budget > div').first.inner_text()
    check(num(head.split('/')[0].splitlines()[-1]) == total, f'на телефоні «{head}», очікували витрати періоду {total} (місяць {month_total})')
    shot(page, 'budget-375.jpg')


CHECKS = [
    ('Бюджет періоду як в еталоні (7 випадків)', 'desktop', math),
    ('ПК-Бюджет: KPI, категорії, «горить», операції, У Потік', 'desktop', desktop),
    ('Період за замовчуванням містить сьогодні', 'desktop', default_period),
    ('ПК-Бюджет: період, що ще не почався', 'desktop', future_period),
    ('Бюджет на телефоні: витрати періоду', 'mobile', mobile),
]
