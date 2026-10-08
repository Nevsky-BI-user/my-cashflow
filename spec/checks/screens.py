# Пʼять екранів на ПК (1280) і телефоні (375): рендер, заголовок, без горизонтального скролу
from helpers import TABS, check, go_tab

NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
# елементи всередині .content з власним вертикальним скролом (права колонка Календаря прокручується свідомо)
INNER_SCROLL = r"""[...document.querySelectorAll('.content *')].filter(e=>{if(e.closest('.ck-side'))return false;const o=getComputedStyle(e).overflowY;return o==='auto'||o==='scroll'}).map(e=>e.tagName+'.'+(e.className||'').toString().slice(0,30))"""


def desktop(page):
    check(page.evaluate("getComputedStyle(document.querySelector('header')||document.createElement('header')).display") == 'none'
          or page.locator('header').count() == 0, 'шапка на ПК не схована')
    w = page.evaluate("document.querySelector('.side').getBoundingClientRect().width")
    check(abs(w - 220) < 1, f'бічна панель {w}px, а не 220')
    for i, (tid, title) in enumerate(TABS):
        go_tab(page, i)
        h1 = page.inner_text('.dtitle h1').strip()
        check(h1 == title, f'клавіша {i + 1}: заголовок «{h1}», очікували «{title}»')
        check(page.locator(f'.panel.p-{tid}').count() == 1, f'{title}: немає .p-{tid}')
        check(page.evaluate(NO_HSCROLL), f'{title}: горизонтальний скрол')
        inner = page.evaluate(INNER_SCROLL)
        check(not inner, f'{title}: внутрішній скрол у .content: {inner[:3]}')


def mobile(page):
    check(page.locator('.tab-bar .tab-btn').count() == 5, 'на телефоні не 5 нижніх вкладок')
    for i, (tid, title) in enumerate(TABS):
        go_tab(page, i)
        check(page.locator(f'.panel.p-{tid}').count() == 1, f'вкладка {title}: немає .p-{tid}')
        txt = page.locator('.tab-bar .tab-btn').nth(i).inner_text()
        check(title in txt, f'вкладка {i + 1}: підпис «{txt.strip()}»')
        check(page.evaluate(NO_HSCROLL), f'{title}: горизонтальний скрол')


CHECKS = [
    ('Пʼять екранів на ПК', 'desktop', desktop),
    ('Пʼять екранів на телефоні', 'mobile', mobile),
]
