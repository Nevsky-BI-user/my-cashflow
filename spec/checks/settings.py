# Меню налаштувань: ПК (розділи праворуч) і телефон (v149: шоста вкладка «Налаштування», сторінка зі списком, другий рівень)
from helpers import check, dialog, go_tab

SECTIONS = ['Зарплата', 'Розподіл бюджету', 'Накопичення', 'Платежі', 'Рахунки', 'Категорії', 'Тема', 'Інтеграції', 'Підказки']
PANEL_TITLE = r"""()=>{const dl=document.querySelector('.set-page[aria-label="Налаштування"]');const pn=dl.children[1];
return {title:pn.children[0].innerText.split('\n')[0].trim(),active:((dl.querySelector('nav [aria-current=page]')||{}).innerText||'').trim()}}"""


def desktop(page):
    page.keyboard.press('s')
    page.wait_for_timeout(400)
    d = page.locator('.set-page')
    check(d.count() == 1, 'сторінка налаштувань не відкрилась')
    for sec in SECTIONS:
        d.locator('nav button', has_text=sec).first.click()
        page.wait_for_timeout(300)
        r = page.evaluate(PANEL_TITLE)
        check(r['title'] == sec, f'розділ «{sec}»: праворуч заголовок «{r["title"]}»')
        check(sec in r['active'], f'розділ «{sec}»: активний пункт «{r["active"]}»')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив сторінку налаштувань')


def mobile(page):
    go_tab(page, 5)
    page.wait_for_timeout(200)
    d = page.locator('.set-mpage[aria-label="Налаштування"]')
    check(d.count() == 1 and dialog(page, 'Налаштування').count() == 0, 'шоста вкладка не відкрила сторінку налаштувань (або відкрила діалог)')
    check(page.locator('.tab-bar .tab-btn[aria-current=page]').inner_text().strip() == 'Налаштування', 'вкладка «Налаштування» не активна')
    rows = page.evaluate("[...document.querySelector('.set-mpage').children].length") - 1
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
