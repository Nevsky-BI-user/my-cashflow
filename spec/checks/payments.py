# Вікно платежів із Календаря: ПК (кнопка в шапці екрана) і телефон (FAB)
from helpers import check, dialog, go_tab

FAB = "()=>{const b=[...document.querySelectorAll('button')].filter(x=>getComputedStyle(x).position==='fixed'&&!x.closest('.tab-bar'));b[b.length-1].click()}"


def desktop(page):
    go_tab(page, 3)
    page.click('.dact')
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'кнопка Календаря не відкрила вікно платежів')
    t = d.text_content()
    for s in ('Розстрочки', 'Постійні'):
        check(s in t, f'у вікні платежів немає секції «{s}»')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив вікно платежів')


def mobile(page):
    go_tab(page, 3)
    page.evaluate(FAB)
    page.wait_for_timeout(500)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'FAB Календаря не відкрила вікно платежів')
    seg = d.locator('[aria-label="Тип платежів"]')
    check(seg.count() == 1, 'немає перемикача «Тип платежів»')
    for s in ('Розстрочки', 'Постійні'):
        check(seg.locator('button', has_text=s).count() == 1, f'немає секції «{s}»')
    seg.locator('button', has_text='Постійні').click()
    page.wait_for_timeout(200)
    # на телефоні Esc не обробляється (гарячі клавіші лише на ПК), закриває хрестик
    d.locator('[aria-label="Закрити"]').first.click()
    page.wait_for_timeout(300)
    check(d.count() == 0, 'хрестик не закрив вікно платежів')


CHECKS = [
    ('Платежі з Календаря, Esc', 'desktop', desktop),
    ('Платежі з Календаря, FAB', 'mobile', mobile),
]
