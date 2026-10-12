# Мобільний Огляд за DESIGN.md «Огляд, телефон» (третя редакція): порядок блоків, рахунки чипами, герой «Вільно до виплати» проти еталона
# «Вільно» = змінний бюджет періоду (scripts/budget_pool.py на демо-знімку) мінус витрати періоду від виплати до сьогодні.
import re
from datetime import date

from helpers import check, dialog, finance_ref, current_ref, demo_snapshot, freeze, num, open_payout, shot

TODAY = '2026-10-08'
# o-ms-list: поріг мінімальних витрат рахунку (п. 11), у демо в Ощаду він є
# v145: блок «Баланс» (o-bal) прибрано, баланс у плитці KPI
ORDER = ['projection-summary', 'o-accs', 'o-next', 'dv-fc', 'o-ms-list', 'o-budget', 'o-recent', 'o-weeks', 'o-strip', 'o-ccy']


def _spent(page, start, today):
    """Витрати демо-операцій (txDemo) з дати виплати start до today включно, рахує Python."""
    months = sorted({(start.year, start.month - 1), (today.year, today.month - 1)})
    rows = []
    for y, m in months:
        rows += page.evaluate(f'txDemo({y},{m})')
    s0, s1 = start.isoformat(), today.isoformat()
    return sum(float(t['amount']) for t in rows if t['type'] == 'expense' and s0 <= t['date'] <= s1)


def mobile_today(page):
    freeze(page, TODAY)
    blocks = page.evaluate("[...document.querySelector('.panel.p-overview').children].map(e=>e.className)")
    got = [next((c for c in ORDER if c in b.split()), b) for b in blocks]
    check(got == ORDER, f'порядок блоків Огляду: {got}')
    # рахунки чипами: на кожен активний рахунок чип із залишком (кредитка: «борг» і сума боргу), «+» додає рахунок
    accs = page.evaluate("window.__cashCore.accounts.filter(a=>a.active!==false).map(a=>({k:a.kind,b:Number(a.balance)||0,d:Number(a.debt)||0}))")
    chips = page.evaluate("[...document.querySelectorAll('.o-accs .o-acc-chip:not(.o-unas):not(.o-acc-add)')].map(e=>e.innerText)")
    check(len(chips) == len(accs), f'чипів рахунків {len(chips)}, а рахунків {len(accs)}')
    for a, c in zip(accs, chips):
        v = a['d'] if a['k'] == 'credit' else a['b']
        b = c.split('\n')
        got = [x for x in c.replace('\n', ' ').split(' ') if x]
        check(('борг' in c) == (a['k'] == 'credit'), f'чип {c!r}: позначка боргу не відповідає рахунку')
        check(f'{round(v):,}'.replace(',', ' ') in c.replace('\u00a0', ' ').replace('\u202f', ' '), f'чип {c!r} без суми {v}')
    check(page.locator('.o-accs .o-acc-add').count() == 1, 'у ряді рахунків немає «+»')
    shown = len(chips)
    ref = finance_ref(page)
    n = ref['nextPlan']
    # v148: плитка «Бюджет періоду» = бюджет на старт періоду після виплати (не нижче 15 000), рядки «Доступно» = бюджет мінус змінні витрати і «Щоденні витрати» = бюджет / днів
    pb = page.evaluate("window.__periodBudget")
    hero = num(page.inner_text('.kpi-budget .dv-kpi-v'))
    check(pb and abs(hero - pb['budget'] / 100) <= 1 and pb['budget'] >= 1500000, f'«Бюджет періоду» {hero}, а бюджет на старт {pb}')
    check(abs(num(page.inner_text('.kpi-budget [data-r=avail] .kpi-rv')) - pb['avail'] / 100) <= 1, '«Доступно» не бюджет мінус змінні витрати')
    check(abs(num(page.inner_text('.kpi-budget [data-r=daily] .kpi-rv')) - pb['daily'] / 100) <= 1, '«Щоденні витрати» не бюджет / днів')
    txt = page.inner_text('.kpi-budget')
    check(not re.search(r'\d\d\.\d\d-\d\d\.\d\d', txt) and 'Доступно до' not in txt and 'Готівка' not in txt, f'у плитці лишились дати, «Доступно до» чи покриття: {txt!r}')
    check('бюджет періоду' in page.inner_text('.projection-summary').lower(), 'немає назви «Бюджет періоду»')
    fs = page.evaluate("getComputedStyle(document.querySelector('.kpi-budget .dv-kpi-v')).fontSize")
    check(float(fs.removesuffix('px')) >= 18, f'кегль суми плитки {fs}')
    lbl = page.evaluate("[...document.querySelectorAll('.o-strip div')].filter(e=>/^(Дохід|Витрати|Залишок)$/i.test(e.innerText.trim())).map(e=>getComputedStyle(e).fontSize)")
    check(len(lbl) == 3 and all(x == '11px' for x in lbl), f'підписи стрічки періоду: {lbl}')
    nxt = page.locator('.o-next .o-next-row')
    check(nxt.count() == 3, f'у «Найближче» {nxt.count()} подій, а не 3')
    # v148 (власник: «прибери це»): рядка «Щоденні витрати, прогноз» у «Найближче» немає, у Потоці й календарі він лишається
    check('Щоденні витрати' not in page.inner_text('.o-next'), 'у «Найближче» лишився рядок «Щоденні витрати, прогноз»')
    check(page.locator('.o-recent .o-to-flow').count() == 1, 'немає переходу «Усі операції в Потоці»')
    shot(page, 'ov-375-final.jpg')
    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(150)
    shot(page, 'ov-375-dark.jpg')


def recent_to_flow(page):
    rows = page.locator('.o-recent').locator('button.o-to-flow')
    rows.click()
    page.wait_for_timeout(350)
    check(page.locator('.panel.p-flow').count() == 1, '«Усі операції в Потоці» не відкрили Потік')


def pay_period(page):
    # v148: дат періоду в плитці «Бюджет періоду» немає; «Налаштувати зарплату» у підказці «i» плитки, працює з клавіатури
    check(page.locator('.p-overview .kpi-budget .ps-period').count() == 0, 'у плитці лишились дати періоду')
    page.locator('.p-overview .kpi-budget .kpi-i').click()
    page.wait_for_selector('.kpi-tip[data-k=budget]')
    b = page.locator('.kpi-tip[data-k=budget] .kpi-pay')
    check(b.count() == 1 and b.inner_text() == 'Налаштувати зарплату', 'у підказці бюджету немає «Налаштувати зарплату»')
    b.focus()
    page.keyboard.press('Enter')
    page.wait_for_timeout(400)
    d = dialog(page, 'Зарплата')
    check(d.count() == 1 and 'Ставка на місяць' in d.inner_text(), 'Enter на періоді не відкрив налаштування зарплати')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив налаштування зарплати')


CHECKS = [
    ('Огляд телефона: порядок, гаманець, план після виплати', 'mobile', mobile_today),
    ('Огляд телефона: перехід з останніх операцій у Потік', 'mobile', recent_to_flow),
    ('Огляд ПК: період виплати відкриває зарплату', 'desktop', pay_period),
    ('Огляд телефона: період виплати відкриває зарплату', 'mobile', pay_period),
]
