# ПК-Цілі: KPI, «Що як», історія накопичень; накопичення на місяць за правилом бюджету періоду на обох платформах
from helpers import check, freeze, go_tab, num, shot

DAY = '2026-10-08'


def desktop(page):
    freeze(page, DAY)
    go_tab(page, 4)
    check(page.locator('.p-goals.desk').count() == 1, 'на ПК немає .p-goals.desk')
    check('збережено' in page.inner_text('.goals-kpis').lower(), 'немає фактичних заощаджень')
    check(num(page.locator('.goals-kpis strong').first.inner_text())==0, 'без внесків збережений баланс не нуль')
    check('Автоматичних накопичень' not in page.inner_text('.goals-kpis'), 'v183: лишилось речення-пояснення внесків')
    check(page.locator('.goals-wi-row').count()==0, 'старі ETA показуються без плану внесків')
    # шапка: сегмент ₴/$, «Налаштувати» (v149 замість шестерні) і «+ Ціль» ліворуч від головної кнопки; пунктирної плитки на дошці немає
    head = page.locator('.dtitle')
    check(head.locator('.gh-ccy button').all_inner_texts() == ['₴', '$'], 'у шапці немає сегмента ₴ / $')
    check(head.locator('.goals-cfg').count() == 1 and head.locator('.goals-cfg').inner_text().strip() == 'Налаштувати', 'у шапці немає кнопки «Налаштувати»')
    check(head.locator('.goals-add', has_text='+ Ціль').count() == 1, 'у шапці немає «+ Ціль»')
    check(page.locator('.gtile-add').count() == 0, 'пунктирна плитка «+ Ціль» лишилась на дошці')
    hb = [head.locator(sel).bounding_box() for sel in ('.gh-ccy', '.goals-cfg', '.goals-add', '.dact')]
    check(all(hb) and hb[0]['x'] < hb[1]['x'] < hb[2]['x'] < hb[3]['x'], 'порядок у шапці не ₴/$, «Налаштувати», «+ Ціль», «+ Поповнення»')
    check(hb[0]['height'] <= 28.5 and hb[1]['height'] <= 28.5, f'сегмент або «Налаштувати» вищі за 28px: {hb[0]["height"]}, {hb[1]["height"]}')
    # сегмент валюти міняє суму «Зібрано» на $
    head.locator('.gh-ccy button', has_text='$').click()
    page.wait_for_timeout(250)
    check('$' in page.locator('.goals-kpis strong').first.inner_text() and '$' in page.locator('.goals-log-tot').inner_text(), 'перемикач $ не змінив валюту сум')
    head.locator('.gh-ccy button', has_text='₴').click()
    page.wait_for_timeout(250)
    check('₴' in page.locator('.goals-kpis strong').first.inner_text(), 'перемикач ₴ не повернув гривні')
    shot(page, 'goals-full-1280.jpg')
    page.locator('.dtitle .goals-cfg').click()
    page.wait_for_timeout(300)
    act = page.locator('.set-page nav [aria-current=page]')
    check(act.count() == 1 and 'Накопичення' in act.inner_text(), '«Налаштувати» не відкрило розділ «Накопичення» сторінки налаштувань')


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
    check(log.locator('.goals-log-empty').count() == 0, 'порожній стан при наявних записах')
    log.locator('button', has_text='Усі внески').click()
    page.wait_for_timeout(250)
    check(log.locator('.goals-log-row').count() == 7, '«Усі» не розгорнуло список')
    check(log.evaluate('e=>e.scrollHeight<=e.clientHeight+1&&e.scrollWidth<=e.clientWidth+1'), 'розгорнуті внески мають внутрішню прокрутку')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'розгорнуті внески розширюють сторінку')
    page.mouse.move(2, 2)
    shot(page, 'goals-log-1280.jpg', full=False)
    log.get_by_role('button',name='+ Внесок',exact=True).click()
    page.wait_for_timeout(300)
    check(page.locator('[role=dialog]').count() >= 1, '«+» у «Фактичних накопиченнях» не відкрив вікно поповнення')


def mobile(page):
    """Телефон: розмітка без змін, сума на місяць за правилом (не з повного доходу)."""
    freeze(page, DAY)
    go_tab(page, 4)
    check(page.locator('.p-goals.desk').count() == 0, 'на телефоні ПК-розмітка')
    txt=page.locator('.p-goals').inner_text()
    # пояснення v142: лише явні внески за пріоритетом цілей, без автоматичних накопичень і строків (projection-contract.md)
    check('Внески розподіляються' not in txt and 'Автоматичних накопичень' not in txt, 'v183: лишилось речення-пояснення заощаджень')
    check('Горизонт подій' not in txt and 'Історія накопичень' not in txt, 'мобільний екран показує прогноз строків')
    check(page.locator('.goals-wi-row').count()==0, 'мобільний екран обіцяє ETA')
    shot(page, 'goals-375.jpg')


CHECKS = [
    ('ПК-Цілі: фактичний баланс, валюта, шапка і налаштування', 'desktop', desktop),
    ('ПК-Цілі: фактичні накопичення компактно, «Усі», «+»', 'desktop', savings_log),
    ('Цілі на телефоні: явні внески без автоматичного ETA', 'mobile', mobile),
]
