# Меню налаштувань: ПК (розділи праворуч) і телефон (список, другий рівень)
from helpers import check, dialog

SECTIONS = ['Зарплата', 'Розподіл бюджету', 'Накопичення', 'Платежі', 'Рахунки', 'Категорії', 'Тема', 'Інтеграції', 'Підказки']
PANEL_TITLE = r"""()=>{const dl=document.querySelector('[role=dialog][aria-label="Налаштування"]');const pn=dl.children[1];
return {title:pn.children[0].innerText.split('\n')[0].trim(),active:((dl.querySelector('nav [aria-current=page]')||{}).innerText||'').trim()}}"""


def desktop(page):
    page.keyboard.press('s')
    page.wait_for_timeout(400)
    d = dialog(page, 'Налаштування')
    check(d.count() == 1, 'меню не відкрилось')
    for sec in SECTIONS:
        d.locator('nav button', has_text=sec).first.click()
        page.wait_for_timeout(300)
        r = page.evaluate(PANEL_TITLE)
        check(r['title'] == sec, f'розділ «{sec}»: праворуч заголовок «{r["title"]}»')
        check(sec in r['active'], f'розділ «{sec}»: активний пункт «{r["active"]}»')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив меню')


def mobile(page):
    page.click('.hdr-gear')
    page.wait_for_timeout(400)
    d = dialog(page, 'Налаштування')
    check(d.count() == 1, 'шестерня не відкрила меню')
    # ручку шита (.sheet-grip) не рахуємо: це не рядок меню
    rows = page.evaluate("[...document.querySelector('[role=dialog][aria-label=\"Налаштування\"]').children].filter(e=>!e.classList.contains('sheet-grip')).length") - 1
    check(rows == 9, f'у списку {rows} рядків, а не 9')
    txt = d.inner_text()
    # «Підказки» на телефоні: кнопка туру і версія замість заголовка рядка
    miss = [s for s in SECTIONS[:-1] if s not in txt]
    check(not miss, f'у списку немає: {miss}')
    check('Версія cashflow-v' in txt, 'у списку немає рядка підказок із версією')
    # Накопичення: окремий екран поверх меню
    d.locator('button', has_text='Накопичення').first.click()
    page.wait_for_timeout(400)
    sv = dialog(page, 'Накопичення')
    check(sv.count() == 1, '«Накопичення» не відкрило екран')
    sv.locator('[aria-label="Закрити"]').first.click()
    page.wait_for_timeout(300)
    check(sv.count() == 0, 'екран «Накопичення» не закрився')
    # Інтеграції: другий рівень і повернення
    d.locator('button', has_text='Інтеграції').first.click()
    page.wait_for_timeout(300)
    first = d.inner_text().split('\n')
    check(any('Назад' in x for x in first[:2]) and 'Інтеграції' in d.inner_text(), f'«Інтеграції» не відкрили другий рівень: {first[:3]}')
    d.locator('button', has_text='Назад').click()
    page.wait_for_timeout(300)
    check(d.inner_text().split('\n')[0].strip() == 'Налаштування', '«← Назад» не повернув до списку')


CHECKS = [
    ('Меню: кожен розділ праворуч', 'desktop', desktop),
    ('Меню: список, Накопичення, Інтеграції', 'mobile', mobile),
]
