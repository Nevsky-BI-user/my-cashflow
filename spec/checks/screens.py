# Пʼять екранів на ПК (1280) і телефоні (375): рендер, заголовок, без горизонтального скролу
from helpers import TABS, check, go_tab
from checks.visual_layout import overview_bounds

NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
# Desktop: only the long Operations table may scroll inside a card.
INNER_SCROLL = r"""[...document.querySelectorAll('.content *')].filter(e=>{const o=getComputedStyle(e).overflowY;return e.offsetParent&&(o==='auto'||o==='scroll')&&e.scrollHeight>e.clientHeight+2&&!e.matches('.flow-table')}).map(e=>e.tagName+'.'+(e.className||'').toString().slice(0,30))"""


def desktop(page):
    header = page.locator('.shell > .header')
    check(header.count() == 1, 'немає шапки застосунку .shell > .header')
    check(header.evaluate("e=>getComputedStyle(e).display") == 'none', 'шапка на ПК не схована')
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
        if tid == 'overview':
            overview_bounds(page, 'Екрани/Огляд')
        if tid == 'flow':
            check(page.locator('.flow-table').evaluate("e=>{e.scrollTop=e.scrollHeight;const r=e.lastElementChild.getBoundingClientRect(),b=e.getBoundingClientRect();return r.bottom<=b.bottom+2}"), 'Остання операція недосяжна')
        if tid == 'credits':
            check(page.locator('.calendar-only .ck-cal').count() == 1, 'Платежі: календар відсутній')
            check(page.locator('.ck-side,.ck-day,.cal-tbl').count() == 0, 'Платежі: бічна таблиця подій залишилась')
            check(page.locator('.calendar-only .ck-cal').evaluate('e=>{const r=e.getBoundingClientRect();return r.bottom<=innerHeight+1&&r.width>=innerWidth-270}'), 'Платежі: календар не вміщується на сторінці')



def mobile(page):
    # v149: шоста вкладка «Налаштування» (сторінка, перевірка в v149.py)
    check(page.locator('.tab-bar .tab-btn').count() == 6, 'на телефоні не 6 нижніх вкладок')
    check(page.locator('.tab-bar .tab-btn').nth(5).inner_text().strip() == 'Налаштування', 'шоста вкладка не «Налаштування»')
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
