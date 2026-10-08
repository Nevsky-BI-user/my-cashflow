# periodTl: період авансу бачить операції 1-5 числа наступного місяця, період зарплати не бачить нічого після 21-го.
# Еталон: Python-підрахунок операцій txDemo за тим самим правилом [виплата; наступна виплата) з вихідними (helpers._adj).
from datetime import date

from helpers import ADV_DAY, SAL_DAY, _adj, check, freeze, go_tab, shot

TODAY = '2026-10-08'
MON_GEN = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
# групи по днях у ПК-Потоці: підпис «1 жовтня, четвер» і кількість фактичних операцій
GROUPS = r"""[...document.querySelectorAll('.p-flow.desk .flow-group')].map(g=>({d:g.querySelector('.flow-day span').innerText,n:g.querySelectorAll('.flow-row.tx').length}))"""


def demo_rows(page):
    """txDemo вересня й жовтня 2026 зі сторінки (дата заморожена): [(date, type)]."""
    rows = page.evaluate("txDemo(2026,8).concat(txDemo(2026,9)).map(t=>[t.date,t.type])")
    return [(date.fromisoformat(d), t) for d, t in rows]


def ui_rows(page):
    out = []
    for g in page.evaluate(GROUPS):
        day, mon = g['d'].split(',')[0].split(' ')
        out += [(date(2026, MON_GEN.index(mon) + 1, int(day)), g['n'])]
    return out


def open_period(page, back):
    """ПК-Потік, обсяг «Період», back разів ← від поточного періоду."""
    go_tab(page, 2)
    page.locator('.flow-scope button', has_text='Період').click()
    page.wait_for_timeout(250)
    for _ in range(back):
        page.keyboard.press('ArrowLeft')
        page.wait_for_timeout(300)


def advance(page):
    freeze(page, TODAY)
    open_period(page, 1)
    check('аванс' in page.inner_text('.dtitle-sub'), 'один крок ← від 08.10 не період авансу')
    lo, hi = _adj(2026, 9, ADV_DAY), _adj(2026, 10, SAL_DAY)
    ref = [r for r in demo_rows(page) if lo <= r[0] < hi]
    nxt = [r for r in ref if r[0].month == 10 and r[0].day <= 5]
    check(nxt, 'у txDemo жовтня немає операцій 1-5 числа (еталон порожній)')
    ui = ui_rows(page)
    n_ui = sum(n for _, n in ui)
    print(f'      аванс {lo}..{hi}: еталон {len(ref)} операцій (з них 1-5 жовтня {len(nxt)}), у Потоці {n_ui}')
    check(n_ui == len(ref), f'у періоді авансу {n_ui} операцій, еталон {len(ref)}')
    check(any(d.month == 10 and d.day <= 5 and n for d, n in ui), 'період авансу не містить операцій 1-5 жовтня')
    check(all(lo <= d < hi for d, n in ui if n), f'у періоді авансу операції поза межами: {ui}')
    shot(page, 'periods-advance-1280.jpg')


def salary(page):
    freeze(page, TODAY)
    open_period(page, 2)
    check('зарплата' in page.inner_text('.dtitle-sub'), 'два кроки ← від 08.10 не період зарплати')
    lo, hi = _adj(2026, 9, SAL_DAY), _adj(2026, 9, ADV_DAY)
    rows = demo_rows(page)
    ref = [r for r in rows if lo <= r[0] < hi]
    late = [r for r in rows if r[0].month == 9 and r[0] >= hi]
    check(late, 'у txDemo вересня немає операцій після 21-го (перевірка була б порожньою)')
    ui = ui_rows(page)
    n_ui = sum(n for _, n in ui)
    print(f'      зарплата {lo}..{hi}: еталон {len(ref)} операцій, у Потоці {n_ui}; після 21-го в txDemo {len(late)}')
    check(n_ui == len(ref), f'у періоді зарплати {n_ui} операцій, еталон {len(ref)}')
    check(all(lo <= d < hi for d, n in ui if n), f'у періоді зарплати операції після 21-го або до 6-го: {ui}')


CHECKS = [
    ('Період авансу: операції 1-5 наступного місяця', 'desktop', advance),
    ('Період зарплати: нічого після 21-го', 'desktop', salary),
]
