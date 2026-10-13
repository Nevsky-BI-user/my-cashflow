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
    freeze(page, DAY, PATCH)
    ref, start, end, spend, ops, hot = expected(page, DAY)
    check(start <= date.fromisoformat(DAY) < end, f'еталон: період {start}..{end} не містить {DAY}')
    go_tab(page, 1)
    check(page.locator('.p-budget.desk').count() == 1, 'на ПК немає .p-budget.desk')
    check(page.locator('.bud-kpis .bud-kpi').count() == 4, 'KPI-рядок не з 4 карток')
    lbl = page.locator('.side-pname').inner_text()
    check(lbl.startswith(str(start.day)), f'період у бічній панелі «{lbl}», очікували від {start}')
    v = num(kpi(page, 'bud-pool'))
    # v150 (власник: «повний бюджет періоду»): плитка показує бюджет на весь період від виплати, а не ціль рушія від сьогодні;
    # (periodBudgetStart, window.__periodBudget); v151 (знахідка 2): той самий розподіл виплати, що в рушії: A = власні на виплату − резерв − погашення,
    # бюджет min(20 000, A), якщо A > 15 000, інакше 15 000
    pb = page.evaluate("window.__periodBudget")
    check(pb['A'] == pb['ownAt'] - pb['reserve'] - pb['repay'], f'A {pb["A"]} != власні {pb["ownAt"]} − резерв {pb["reserve"]} − погашення {pb["repay"]}')
    check(pb['budget'] == (min(2000000, pb['A']) if pb['A'] > 1500000 else 1500000), f'бюджет {pb["budget"]} не за правилом від A {pb["A"]}')
    check(pb is not None and pb['start'] == ref['payout']['date'], f'повний бюджет періоду не від виплати {ref["payout"]["date"]}: {pb and pb.get("start")}')
    check(abs(v - pb['budget'] / 100) <= 1, f'«Бюджет періоду» {v}, повний бюджет періоду {pb["budget"] / 100:.2f}')
    check('обмежено готівкою' not in page.inner_text('.bud-pool'), 'план досі стискається готівкою')
    total = sum(spend.values())
    got = num(kpi(page, 'bud-spent'))
    check(got == round(total), f'«Витрачено» {got}, сума демо-операцій періоду {total}')
    # v150: замість «Нестача» плитка «Доступно» = бюджет − витрачено
    sv = num(kpi(page, 'bud-sav'))
    check('доступно' in page.inner_text('.bud-sav').lower() and abs(sv - (v - got)) <= 1, f'«Доступно» {sv}, а бюджет {v} − витрачено {got}')
    left = (end - date.fromisoformat(DAY)).days
    pd = num(kpi(page, 'bud-day'))
    # v151 (знахідка 4): «План на день» = Доступно / днів до кінця періоду включно з сьогодні; те саме число, що «План на день» на Огляді
    want = (v - got) / left if left > 0 else 0
    check(abs(pd - want) <= 1, f'«План на день» {pd}, а доступно {v - got} / {left} дн. = {want:.2f}')
    check(abs(pd - pb['daily'] / 100) <= 1, f'«План на день» {pd} не дорівнює «План на день» Огляду {pb["daily"] / 100}')
    # v144: категорії в групах; закриті групи розгортаємо, щоб побачити всі
    check(page.locator('.bud-grp').count() >= 2, 'немає груп категорій')
    expand_groups(page)
    rows = page.evaluate("""[...document.querySelectorAll('.bud-cat')].map(e=>({n:e.querySelector('.bud-name').textContent,
f:e.querySelector('.bud-nums b').textContent,p:e.querySelector('.bud-nums').textContent.split('/')[1]||'',hot:e.classList.contains('hot'),idle:e.classList.contains('idle')}))""")
    check(len(rows) == page.evaluate('BCAT.length'), f'{len(rows)} категорій замість усіх')
    for r in rows:
        f = num(r['f'])
        check(f == round(spend.get(r['n'], 0)), f'{r["n"]}: факт {f}, сума операцій періоду {spend.get(r["n"], 0)}')
        check(r['idle'] == (f == 0), f'{r["n"]}: сірий стан не збігається з витратами')
    # v150: план категорій від повного бюджету періоду, тож факт порівнюється з ним: «горить», коли факт > плану × (частка періоду + 10 %)
    frac = min((end - start).days, (date.fromisoformat(DAY) - start).days + 1) / max(1, (end - start).days)
    for r in rows:
        f, pl = num(r['f']), num(r['p'])
        want = f > 0 and (pl <= 0 or f / pl > frac + 0.1)
        check(r['hot'] == want, f'{r["n"]}: «горить» {r["hot"]}, а факт {f} / план {pl} при {frac:.0%} періоду')
    check('факт / план на період' in page.inner_text('.bud-catcard'), 'не пояснено базу категорій (v150: план від повного бюджету періоду)')
    check(page.locator('.bud-top .bud-row').count() >= 1, 'топ-5 місць порожній')
    shot(page, 'budget-1280.jpg')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    shot(page, 'budget-1920.jpg')
    # v144: клік по категорії відкриває бічну панель: операції періоду, фокус у панелі, Esc закриває і повертає фокус
    name = sorted(spend)[0]
    for w, hh, f in ((1920, 1080, 'budget-cat-1920.jpg'), (1280, 800, 'budget-cat-1280.jpg')):
        page.set_viewport_size({'width': w, 'height': hh})
        page.wait_for_timeout(300)
        btn = page.locator('.bud-cat', has_text=name)
        btn.click()
        page.wait_for_timeout(350)
        drw = page.locator('.cat-drw[role=dialog]')
        check(drw.count() == 1 and name in drw.locator('.cat-drw-n').inner_text(), f'{name}: бічна панель не відкрилась')
        check(page.evaluate("document.activeElement&&!!document.activeElement.closest('.cat-drw')"), 'фокус не в бічній панелі')
        n = drw.locator('.cat-op').count()
        check(n == ops.get(name, 0), f'{name}: {n} операцій у панелі, очікували {ops.get(name, 0)}')
        check(page.locator('.bud-ops').count() == 0, 'старий блок операцій під правою колонкою лишився')
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f), quality=80, type='jpeg')
        page.keyboard.press('Escape')
        page.wait_for_timeout(250)
        check(page.locator('.cat-drw').count() == 0, 'Esc не закрив панель')
        check(page.evaluate("document.activeElement&&document.activeElement.classList.contains('bud-cat')"), 'фокус не повернувся на категорію')
    page.locator('.bud-cat', has_text=name).click()
    page.wait_for_timeout(300)
    page.locator('.cat-drw-bg').click(position={'x': 40, 'y': 400})
    page.wait_for_timeout(250)
    check(page.locator('.cat-drw').count() == 0, 'клік по тлу не закрив панель')
    page.locator('.bud-cat', has_text=name).click()
    page.wait_for_timeout(300)
    page.locator('.cat-drw .drw-x').click()
    page.wait_for_timeout(250)
    check(page.locator('.cat-drw').count() == 0, '× не закрив панель')
    page.locator('.bud-cat', has_text=name).click()
    page.wait_for_timeout(300)
    page.locator('.cat-drw .bud-to-flow').click()
    page.wait_for_timeout(400)
    check(page.locator('.cat-drw').count() == 0, 'панель лишилась після переходу в Потік')
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
    ('Legacy periodBudget: ізольована сумісність (7 випадків)', 'desktop', math),
    ('ПК-Бюджет: ціль, факт/майбутній план, операції та У Потік', 'desktop', desktop),
    ('Період за замовчуванням містить сьогодні', 'desktop', default_period),
    ('ПК-Бюджет: період, що ще не почався', 'desktop', future_period),
    ('Бюджет на телефоні: витрати періоду', 'mobile', mobile),
]
