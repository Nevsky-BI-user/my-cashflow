"""Календар на всю сторінку: типи подій, повні суми й деталі за запитом."""
from helpers import check, freeze, go_tab, settle, dialog, shot, finance_ref, open_calendar_day


GEOMETRY = r"""()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom,w:r.width,h:r.height,clientH:e.clientHeight,scrollH:e.scrollHeight}};
 const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 return {width:innerWidth,height:innerHeight,docH:document.documentElement.scrollHeight,docW:document.documentElement.scrollWidth,
 calendar:rect(document.querySelector('.calendar-only .ck-cal')),cells:[...document.querySelectorAll('.calendar-only .cal-cell')].map(rect),
 amounts:[...document.querySelectorAll('.calendar-only .cal-amt')].filter(visible).map(e=>({text:e.textContent,...rect(e),cellRight:e.closest('.cal-cell').getBoundingClientRect().right,client:e.clientWidth,scroll:e.scrollWidth})),
 scroll:[...document.querySelectorAll('.calendar-only *')].filter(e=>visible(e)&&/auto|scroll/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+2).map(e=>e.className)};
}"""


def desktop(page):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        for day, cells in (('2026-10-26', 31), ('2026-08-21', 31)):
            freeze(page, day)
            go_tab(page, 3)
            for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
                page.set_viewport_size(dict(width=width, height=height))
                page.wait_for_timeout(500)
                settle(page)
                tag = f'{theme}/{day}/{width}x{height}'
                check(page.locator('.calendar-only .ck-kpis>.surface').count() == 3, f'{tag}: верхні підсумки зникли')
                check(page.locator('.calendar-only .ck-side,.calendar-only .ck-day,.calendar-only .cal-tbl,.calendar-only .cm-details,.calendar-only .cm-month').count() == 0, f'{tag}: список подій усе ще на сторінці')
                check(page.locator('.calendar-only .cal-cell').count() == cells, f'{tag}: пропали дні місяця')
                check(page.locator('.cal-legend[aria-label="Типи подій"] [role=listitem]').count() == 0, f'{tag}: легенда неповна')
                icons = page.locator('.cal-cell .cal-event-icon')
                check(icons.count() > 0 and all(icons.nth(i).get_attribute('aria-label') for i in range(icons.count())), f'{tag}: значки без змісту')
                g = page.evaluate(GEOMETRY)
                check(g['docW'] <= width and g['docH'] <= height + 1, f'{tag}: прокрутка сторінки {g}')
                check(not g['scroll'], f'{tag}: внутрішня прокрутка {g["scroll"]}')
                check(all(c['bottom'] <= height + 1 and c['scrollH'] <= c['clientH'] + 2 for c in g['cells']), f'{tag}: вміст клітинок обрізано {g}')
                check(all(a['scroll'] <= a['client'] + 1 and a['right'] <= a['cellRight'] + 1 for a in g['amounts']), f'{tag}: суми обрізано {g["amounts"]}')
                check(g['calendar']['w'] >= width - 270, f'{tag}: календар не використовує ширину')
                if width == 1280:
                    shot(page, f'calendar-only-{theme}-{day}.jpg', full=False)


def interaction(page):
    freeze(page, '2026-10-08')
    go_tab(page, 3)
    cell = page.locator('.calendar-only .cal-cell[data-date="2026-10-10"]')
    cell.focus()
    page.keyboard.press('Enter')
    details = page.locator('dialog.cal-day-dialog[open]')
    details.wait_for()
    check('Садочок' in details.inner_text() and '3' in details.inner_text(), 'повна назва та сума події не доступні')
    pay = details.locator('.pay-done', has_text='')
    check(pay.count() >= 1, 'з календаря немає доступу до внесення оплати')
    page.keyboard.press('Escape')
    check(not details.count() and cell.evaluate('e=>e===document.activeElement'), 'Escape не повертає фокус на день')
    cell.click()
    page.locator('dialog.cal-day-dialog[open] .pay-done').first.click()
    check(page.locator('dialog.cal-day-dialog[open]').count() == 0, 'деталі блокують форму оплати')
    operation = dialog(page, 'Нова операція')
    operation.wait_for()
    page.wait_for_timeout(500)
    check(operation.evaluate('e=>e.contains(document.activeElement)'), 'фокус після оплати повернувся за межі форми операції')
    check(operation.locator('select[aria-label="Постійний платіж"]').input_value() == 'f2', 'оплата втратила привʼязку до Садочка')
    page.keyboard.press('Escape')
    page.locator('.cal-cell[data-date="2026-10-11"]').click()
    installment = page.locator('dialog.cal-day-dialog[open] .cal-day-row', has_text='Ланцюжок')
    check(installment.get_attribute('data-event-kind') == 'installment', 'розстрочка має неправильний значок')
    check(installment.locator('.pay-done').count() == 1, 'розстрочку неможливо оплатити з календаря')
    installment.locator('.pay-done').click()
    operation = dialog(page, 'Нова операція')
    operation.wait_for()
    page.wait_for_timeout(500)
    check(operation.evaluate('e=>e.contains(document.activeElement)'), 'фокус після розстрочки повернувся за межі форми операції')
    check(operation.locator('select[aria-label="Розстрочка"]').input_value() != '', 'оплата втратила привʼязку до розстрочки')
    check('Ланцюжок' in operation.locator('input[type=text]').first.input_value(), 'форма розстрочки втратила опис')
    page.keyboard.press('Escape')
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    check('Листопад' in page.locator('.ck-month').inner_text(), 'навігація календаря не працює')
    early = next(e for e in finance_ref(page)['events'] if e['kind'] == 'prepay')
    details = open_calendar_day(page, early['date'])
    prepay = details.locator('.cal-day-row', has_text=early['name'])
    check(prepay.count() == 1 and prepay.get_attribute('data-event-kind') == 'installment', 'дострокове погашення не позначене як розстрочка')
    check('📦' in prepay.locator('.cal-event-icon').inner_text(), 'дострокове погашення має неправильний значок')


def mobile(page):
    freeze(page, '2026-10-08')
    go_tab(page, 3)
    check(page.locator('.calendar-only .ck-side,.calendar-only .cm-details,.calendar-only .cm-month').count() == 0, 'на телефоні залишився список подій')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'горизонтальна прокрутка телефону')
    cell = page.locator('.cal-cell[data-date="2026-10-10"]')
    cell.scroll_into_view_if_needed()
    cell.click()
    details = page.locator('dialog.cal-day-dialog[open]')
    details.wait_for()
    check('Садочок' in details.inner_text(), 'на телефоні не видно деталей події')
    check(details.locator('.cal-day-amount').first.evaluate('e=>e.scrollWidth<=e.clientWidth+1'), 'сума в деталях обрізана')
    page.keyboard.press('Escape')


CHECKS = [
    ('Calendar only: full viewport and semantic event icons', 'desktop', desktop),
    ('Calendar only: keyboard details and payment action', 'desktop', interaction),
    ('Calendar only: mobile event details without report list', 'mobile', mobile),
]
