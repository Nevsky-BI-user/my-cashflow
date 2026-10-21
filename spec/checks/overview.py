# Мобільний Огляд за DESIGN.md «Огляд, телефон» (третя редакція): порядок блоків, рахунки чипами, герой «Вільно до виплати» проти еталона
# «Вільно» = змінний бюджет періоду (scripts/budget_pool.py на демо-знімку) мінус витрати періоду від виплати до сьогодні.
import re
from datetime import date

from helpers import check, dialog, finance_ref, current_ref, demo_snapshot, freeze, num, open_payout, shot

TODAY = '2026-10-08'
# Поріг мінімальних витрат рахунку показано всередині картки Ощаду.
# v145: блок «Баланс» (o-bal) прибрано, баланс у плитці KPI
ORDER = ['projection-summary', 'o-account-section', 'o-next', 'dv-fc', 'o-budget', 'o-recent', 'o-weeks']


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
    # Баланс і заборгованість видно для кожного активного рахунку.
    accs = page.evaluate("window.__cashCore.accounts.filter(a=>a.active!==false).map(a=>({b:Number(a.balance)||0,d:Number(a.debt)||0}))")
    cards = page.locator('.o-account-deck .o-bank-card')
    check(cards.count() == len(accs), f'карток {cards.count()}, а рахунків {len(accs)}')
    for i, a in enumerate(accs):
        card = cards.nth(i)
        labels = card.locator('.account-amounts small').all_text_contents()
        values = card.locator('.account-amounts b').all_text_contents()
        check(labels == ['Баланс', 'Заборгованість'], f'картка {i}: підписи {labels}')
        check(len(values) == 2 and abs(num(values[0]) - a['b']) <= 1 and abs(num(values[1]) - a['d']) <= 1,
              f'картка {i}: суми {values}, рахунок {a}')
    add = page.locator('.o-account-section').get_by_role('button', name='Додати рахунок', exact=True)
    check(add.count() == 1 and add.inner_text().strip() == '+', 'після колоди немає малого «+» додавання рахунку')
    check(page.locator('.o-ms-list').count() == 0 and page.locator('.o-bank-card.bank-oschad .ms-wrap').count() == 1, 'мінімальні витрати Ощаду мають бути в його картці')
    ref = finance_ref(page)
    n = ref['nextPlan']
    # v148: плитка «Бюджет періоду» = бюджет на старт періоду після виплати (не нижче 15 000), рядки «Доступно» = бюджет мінус змінні витрати і «Щоденні витрати» = бюджет / днів
    pb = page.evaluate("window.__periodBudget")
    hero = num(page.inner_text('.kpi-budget .dv-kpi-v'))
    check(pb and abs(hero - pb['budget'] / 100) <= 1 and pb['budget'] >= 1500000, f'«Бюджет періоду» {hero}, а бюджет на старт {pb}')
    check(abs(num(page.inner_text('.kpi-budget [data-r=avail] .kpi-rv')) - pb['avail'] / 100) <= 1, '«Доступно» не бюджет мінус змінні витрати')
    # v151: рядок «План на день», як на Бюджеті (раніше «Щоденні витрати»)
    check('план на день' in page.inner_text('.kpi-budget [data-r=daily]').lower(), 'рядок плитки не «План на день»')
    check(abs(num(page.inner_text('.kpi-budget [data-r=daily] .kpi-rv')) - pb['daily'] / 100) <= 1, '«План на день» не доступно / днів')
    txt = page.inner_text('.kpi-budget')
    check(not re.search(r'\d\d\.\d\d-\d\d\.\d\d', txt) and 'Доступно до' not in txt and 'Готівка' not in txt, f'у плитці лишились дати, «Доступно до» чи покриття: {txt!r}')
    check('бюджет періоду' in page.inner_text('.projection-summary').lower(), 'немає назви «Бюджет періоду»')
    fs = page.evaluate("getComputedStyle(document.querySelector('.kpi-budget .dv-kpi-v')).fontSize")
    check(float(fs.removesuffix('px')) >= 18, f'кегль суми плитки {fs}')
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
