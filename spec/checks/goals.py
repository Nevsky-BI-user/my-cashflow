# ПК-Цілі: KPI, «Що як», історія накопичень; накопичення на місяць за правилом бюджету періоду на обох платформах
import math
from datetime import date

from helpers import check, current_ref, demo_snapshot, freeze, go_tab, num, pool_ref, shot

DAY = '2026-10-08'


def monthly_ref(page, today):
    """Накопичення на місяць: savings поточного періоду плюс savings наступного (еталон scripts/budget_pool.py)."""
    snap = demo_snapshot(page)
    cur, nxt = current_ref(snap, today), pool_ref(snap, today)
    check(nxt['payout']['date'] == cur['end'], f'наступний період {nxt["payout"]["date"]} не йде за поточним {cur["end"]}')
    return round(cur['savings'] + nxt['savings']), cur, nxt


def etas_ref(page, mt):
    """goalEtaMonths тим самим правилом: кумулятивні цілі мінус стартові накопичення, поділені на mt, угору."""
    init, goals = page.evaluate("[INIT_SAVINGS,GOALS.map(g=>g.target)]")
    out, cum = [], 0
    for t in goals:
        cum += t
        out.append(max(0, math.ceil((cum - init) / mt)) if mt > 0 else None)
    return out


def desktop(page):
    freeze(page, DAY)
    mt, cur, nxt = monthly_ref(page, DAY)
    go_tab(page, 4)
    check(page.locator('.p-goals.desk').count() == 1, 'на ПК немає .p-goals.desk')
    check(page.locator('.goals-kpis .goals-kpi').count() == 3, 'KPI-рядок не з 3 карток')
    got = num(page.locator('.goals-sav .goals-kpi-v').inner_text())
    check(got == mt, f'«Відкладаємо» {got}, еталон {cur["savings"]:.2f} + {nxt["savings"]:.2f} = {mt}')
    print(f'      Цілі {DAY}: «Відкладаємо» {got} ₴/міс; еталон savings {cur["payout"]["date"]} {cur["savings"]:.2f} + '
          f'{nxt["payout"]["date"]} {nxt["savings"]:.2f} = {mt}')
    side = page.locator('.goals-side').inner_text()
    for t in ('Що як', 'Історія накопичень', 'Налаштувати накопичення'):
        check(t.lower() in side.lower(), f'у правій колонці немає «{t}»')
    check('Горизонт подій'.lower() in page.locator('.goals-main').inner_text().lower(), 'горизонт не під картою')
    base = etas_ref(page, mt)
    rows = page.evaluate("[...document.querySelectorAll('.goals-wi-row')].map(e=>+e.dataset.eta)")
    check(rows == base, f'«Що як» без дельти {rows}, еталон {base}')
    near = page.locator('.goals-near').inner_text()
    mi = 6  # жовтень 2026: місяць плану 6 (квітень 2026 = 0)
    check(f'через {base[0] - mi} міс' in near, f'«Найближча»: «{near}», очікували через {base[0] - mi} міс')
    shot(page, 'goals-1280.jpg')
    # повзунок «Що як»: +5 000 ₴ на місяць зсуває строки раніше
    inp = page.locator("input[aria-label='Відкладати більше на місяць']").first
    inp.fill('5000')
    inp.press('Enter')
    page.wait_for_timeout(300)
    more = etas_ref(page, mt + 5000)
    rows2 = page.evaluate("[...document.querySelectorAll('.goals-wi-row')].map(e=>+e.dataset.eta)")
    check(rows2 == more, f'«Що як» +5000: {rows2}, еталон {more}')
    check(all(b <= a for a, b in zip(base, rows2)) and any(b < a for a, b in zip(base, rows2)), 'строки не зсунулись раніше')
    check(page.locator('.goals-wi-row.early .goals-wi-d').count() >= 1, 'немає зеленого «на N міс раніше»')
    shot(page, 'goals-whatif-1280.jpg')
    # налаштування накопичень відкриваються
    page.locator('.goals-cfg').click()
    page.wait_for_timeout(300)
    check(page.get_by_text('% накопичень з доходу').count() >= 1, '«Налаштувати накопичення» не відкрило блок')


def mobile(page):
    """Телефон: розмітка без змін, сума на місяць за правилом (не з повного доходу)."""
    freeze(page, DAY)
    mt, cur, nxt = monthly_ref(page, DAY)
    go_tab(page, 4)
    check(page.locator('.p-goals.desk').count() == 0, 'на телефоні ПК-розмітка')
    txt = page.locator('.p-goals').inner_text()
    line = [x for x in txt.splitlines() if '/міс' in x]
    check(line and num(line[0]) == mt, f'на телефоні «{line}», очікували {mt} ₴/міс')
    shot(page, 'goals-375.jpg')


CHECKS = [
    ('ПК-Цілі: KPI, «Що як», історія, налаштування', 'desktop', desktop),
    ('Цілі на телефоні: накопичення на місяць за правилом', 'mobile', mobile),
]
