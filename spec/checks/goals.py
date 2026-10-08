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
    for t in ('Фактичні накопичення', 'Що як', 'Історія накопичень'):
        check(t.lower() in side.lower(), f'у правій колонці немає «{t}»')
    check('Налаштувати накопичення'.lower() not in side.lower(), 'велика кнопка «Налаштувати накопичення» лишилась у правій колонці')
    check(page.locator('.goals-side .gh-ccy, .goals-side button', has_text='USD').count() == 0, 'великий перемикач валюти лишився у правій колонці')
    check('Горизонт подій'.lower() in page.locator('.goals-main').inner_text().lower(), 'горизонт не під картою')
    # шапка: сегмент ₴/$, ⚙ і «+ Ціль» ліворуч від головної кнопки; пунктирної плитки на дошці немає
    head = page.locator('.dtitle')
    check(head.locator('.gh-ccy button').all_inner_texts() == ['₴', '$'], 'у шапці немає сегмента ₴ / $')
    check(head.locator('.goals-cfg[aria-label]').count() == 1 and head.locator('.goals-cfg').inner_text().strip() == '⚙', 'у шапці немає кнопки ⚙')
    check(head.locator('.goals-add', has_text='+ Ціль').count() == 1, 'у шапці немає «+ Ціль»')
    check(page.locator('.gtile-add').count() == 0, 'пунктирна плитка «+ Ціль» лишилась на дошці')
    hb = [head.locator(sel).bounding_box() for sel in ('.gh-ccy', '.goals-cfg', '.goals-add', '.dact')]
    check(all(hb) and hb[0]['x'] < hb[1]['x'] < hb[2]['x'] < hb[3]['x'], 'порядок у шапці не ₴/$, ⚙, «+ Ціль», «+ Поповнення»')
    check(hb[0]['height'] <= 28.5 and hb[1]['height'] <= 28.5, f'сегмент або ⚙ вищі за 28px: {hb[0]["height"]}, {hb[1]["height"]}')
    # «Фактичні накопичення» вище за «Що як», «Що як» вище за історію
    tops = page.evaluate("['.goals-log','.goals-wi'].map(s=>document.querySelector(s).offsetTop)")
    check(tops[0] < tops[1], f'«Фактичні накопичення» не вище за «Що як»: {tops}')
    # сегмент валюти міняє суму «Зібрано» на $
    head.locator('.gh-ccy button', has_text='$').click()
    page.wait_for_timeout(250)
    check('$' in page.locator('.goals-acc').inner_text() and '$' in page.locator('.goals-log-tot').inner_text(), 'перемикач $ не змінив валюту сум')
    head.locator('.gh-ccy button', has_text='₴').click()
    page.wait_for_timeout(250)
    check('₴' in page.locator('.goals-acc').inner_text(), 'перемикач ₴ не повернув гривні')
    base = etas_ref(page, mt)
    rows = page.evaluate("[...document.querySelectorAll('.goals-wi-row')].map(e=>+e.dataset.eta)")
    check(rows == base, f'«Що як» без дельти {rows}, еталон {base}')
    near = page.locator('.goals-near').inner_text()
    mi = 6  # жовтень 2026: місяць плану 6 (квітень 2026 = 0)
    check(f'через {base[0] - mi} міс' in near, f'«Найближча»: «{near}», очікували через {base[0] - mi} міс')
    shot(page, 'goals-full-1280.jpg')
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
    # ⚙ у шапці відкриває налаштування накопичень
    page.locator('.dtitle .goals-cfg').click()
    page.wait_for_timeout(300)
    check(page.get_by_text('% накопичень з доходу').count() >= 1, '⚙ не відкрила налаштування накопичень')


SAV = ','.join("{id:'s%d',date:'2026-10-0%d',amount:%d,currency:'UAH',description:'Запис %d'}" % (i, i + 1, 1000 * (i + 1), i) for i in range(7))


def savings_log(page):
    """ПК: фактичні накопичення компактно (фікстура: 7 записів): видно 5, «Усі 7» розгортає, сума «Всього», «+» відкриває поповнення."""
    freeze(page, DAY, patch=[('const[savingsLog,setSavingsLog]=useState([]);', 'const[savingsLog,setSavingsLog]=useState([' + SAV + ']);')])
    go_tab(page, 4)
    log = page.locator('.goals-log')
    check(log.locator('.goals-log-row').count() == 5, f'у списку {log.locator(".goals-log-row").count()} записів, а не 5 останніх')
    tot = num(log.locator('.goals-log-tot').inner_text())
    want = sum(1000 * (i + 1) for i in range(7))
    check(tot == want, f'«Всього» {tot}, а сума записів {want}')
    fs = page.evaluate("getComputedStyle(document.querySelector('.goals-log-a')).fontSize")
    check(fs == '15px', f'сума запису {fs}, а не 15px')
    check(log.locator('.goals-log-empty').count() == 0, 'порожній стан при наявних записах')
    log.locator('button', has_text='Усі 7').click()
    page.wait_for_timeout(250)
    check(log.locator('.goals-log-row').count() == 7, '«Усі» не розгорнуло список')
    page.mouse.move(2, 2)
    shot(page, 'goals-log-1280.jpg', full=False)
    log.locator('.goals-log-add').click()
    page.wait_for_timeout(300)
    check(page.locator('[role=dialog]').count() >= 1, '«+» у «Фактичних накопиченнях» не відкрив вікно поповнення')


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
    ('ПК-Цілі: KPI, шапка ₴/$ ⚙ «+ Ціль», порядок колонки, «Що як», налаштування', 'desktop', desktop),
    ('ПК-Цілі: фактичні накопичення компактно, «Усі», «+»', 'desktop', savings_log),
    ('Цілі на телефоні: накопичення на місяць за правилом', 'mobile', mobile),
]
