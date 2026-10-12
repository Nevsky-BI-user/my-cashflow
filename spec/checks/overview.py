# Мобільний Огляд за DESIGN.md «Огляд, телефон» (третя редакція): порядок блоків, рахунки чипами, герой «Вільно до виплати» проти еталона
# «Вільно» = змінний бюджет періоду (scripts/budget_pool.py на демо-знімку) мінус витрати періоду від виплати до сьогодні.
from datetime import date

from helpers import check, dialog, finance_ref, current_ref, demo_snapshot, freeze, num, open_payout, shot

TODAY = '2026-10-08'
# o-ms-list: поріг мінімальних витрат рахунку (п. 11), у демо в Ощаду він є
ORDER = ['projection-summary', 'o-accs', 'o-next', 'dv-fc', 'o-bal', 'o-ms-list', 'o-budget', 'o-recent', 'o-weeks', 'o-strip', 'o-ccy']


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
    hero = num(page.inner_text('.dv-free .dv-kpi-v'))
    check(abs(hero-n['baseAvailableCents']/100)<=1, 'герой не дорівнює плану наступного періоду')
    check('доступно після виплати' in page.inner_text('.projection-summary').lower(), 'немає назви плану')
    fs = page.evaluate("getComputedStyle(document.querySelector('.dv-free .dv-kpi-v')).fontSize")
    check(float(fs.removesuffix('px')) >= 28, f'кегль героя {fs}')
    lbl = page.evaluate("[...document.querySelectorAll('.o-strip div')].filter(e=>/^(Дохід|Витрати|Залишок)$/i.test(e.innerText.trim())).map(e=>getComputedStyle(e).fontSize)")
    check(len(lbl) == 3 and all(x == '11px' for x in lbl), f'підписи стрічки періоду: {lbl}')
    nxt = page.locator('.o-next .o-next-row')
    check(nxt.count() == 3, f'у «Найближче» {nxt.count()} подій, а не 3')
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
    # період у «Доступно після виплати» є кнопкою «Налаштувати зарплату»: працює з клавіатури, відкриває форму зарплати
    b = page.locator('.p-overview .dv-free .ps-period')
    check(b.count() == 1, 'період «Доступно після виплати» не кнопка')
    check(b.get_attribute('title') == 'Налаштувати зарплату', f'підказка кнопки періоду: {b.get_attribute("title")!r}')
    lbl = b.get_attribute('aria-label') or ''
    check(b.inner_text() in lbl and 'налаштувати зарплату' in lbl.lower(), f'aria-label кнопки періоду: {lbl!r}')
    # виглядає як підпис періоду, а не як системна кнопка: блок під сумою, прозоре тло, ціль натиску на телефоні не менша за 24px
    st = b.evaluate("e=>{const c=getComputedStyle(e);return [c.display,c.backgroundColor,Math.round(e.getBoundingClientRect().height)]}")
    check(st[0] == 'block' and st[1] in ('rgba(0, 0, 0, 0)', 'transparent'), f'кнопка періоду зі стилем системної кнопки: {st}')
    check(page.viewport_size['width'] >= 1024 or st[2] >= 24, f'кнопка періоду на телефоні нижча за 24px: {st}')
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
