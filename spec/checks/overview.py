# Мобільний Огляд за DESIGN.md «Огляд, телефон» (третя редакція): порядок блоків, рахунки чипами, герой «Вільно до виплати» проти еталона
# «Вільно» = змінний бюджет періоду (scripts/budget_pool.py на демо-знімку) мінус витрати періоду від виплати до сьогодні.
from datetime import date

from helpers import check, current_ref, demo_snapshot, freeze, num, open_payout, shot

TODAY = '2026-10-08'
# o-ms-list: поріг мінімальних витрат рахунку (п. 11), у демо в Ощаду він є
ORDER = ['o-hero', 'o-accs', 'o-bal', 'o-ms-list', 'o-next', 'o-budget', 'o-recent', 'o-weeks', 'o-strip', 'o-ccy']


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
    # герой: еталон freeNow = max(0, min(varPool - витрати періоду, cashNow)); витрати рахує Python і кладе в знімок
    t = date.fromisoformat(TODAY)
    start, _ = open_payout(t)
    snap = demo_snapshot(page)
    snap['spent'] = _spent(page, start, t)
    ref = current_ref(snap, TODAY, TODAY)
    free = round(ref['freeNow'])
    hero = num(page.inner_text('.o-free-v'))
    print(f'      Огляд {TODAY}: чипів рахунків {shown}; budget_pool.py: varPool {ref["varPool"]:.2f}, витрати {ref["spent"]:.0f}, '
          f'whiteDue {ref["whiteDue"]:.2f}, cashNow {ref["cashNow"]:.2f}, freeNow {ref["freeNow"]:.2f}; у героя {hero}')
    check(abs(hero - free) <= 1, f'герой {hero}, а еталон freeNow = {free}')
    sub = page.inner_text('.o-chip')
    check(sub.startswith('на день ') and (' до авансу ' in sub or ' до зарплати ' in sub) and sub.endswith('дн.'), f'підрядок героя: {sub!r}')
    check(page.locator('.o-hero .fx-line, .o-hero [data-k=cash]').count() >= 1, 'під героєм немає рядка-пояснення')
    fs = page.evaluate("getComputedStyle(document.querySelector('.o-free-v')).fontSize")
    check(fs == '36px', f'кегль героя {fs}')
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


CHECKS = [
    ('Огляд телефона: порядок, гаманець, «Вільно до виплати»', 'mobile', mobile_today),
    ('Огляд телефона: перехід з останніх операцій у Потік', 'mobile', recent_to_flow),
]
