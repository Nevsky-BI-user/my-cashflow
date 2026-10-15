# Пʼять екранів на ПК (1280) і телефоні (375): рендер, заголовок, без горизонтального скролу
from helpers import TABS, check, go_tab

NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
# елементи всередині .content з власним вертикальним скролом; погоджені лише довгі списки:
# таблиця операцій і розклад подій Платежів (.ck-day, .ck-side), як у calendar.py і density.py
INNER_SCROLL = r"""[...document.querySelectorAll('.content *')].filter(e=>{const o=getComputedStyle(e).overflowY;return e.offsetParent&&(o==='auto'||o==='scroll')&&e.scrollHeight>e.clientHeight+2&&!e.matches('.flow-table,.ck-day,.ck-side')}).map(e=>e.tagName+'.'+(e.className||'').toString().slice(0,30))"""
# остання подія розкладу Платежів досяжна прокруткою всередині списку і видна на екрані
LAST_EVENT = r"""()=>{const box=document.querySelector('.p-credits .ck-day');const last=box&&[...box.querySelectorAll('.cal-ev')].pop();if(!last)return false;
const sc=[box,...box.querySelectorAll('*')].filter(x=>['auto','scroll'].includes(getComputedStyle(x).overflowY)&&x.scrollHeight>x.clientHeight+2);sc.forEach(x=>x.scrollTop=x.scrollHeight);
const r=last.getBoundingClientRect(),b=box.getBoundingClientRect();const ok=r.bottom<=Math.min(b.bottom,innerHeight)+2&&r.top>=b.top-2;sc.forEach(x=>x.scrollTop=0);return ok}"""


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
        if tid == 'flow':
            check(page.locator('.flow-table').evaluate("e=>{e.scrollTop=e.scrollHeight;const r=e.lastElementChild.getBoundingClientRect(),b=e.getBoundingClientRect();return r.bottom<=b.bottom+2}"), 'Остання операція недосяжна')
        if tid == 'credits':
            check(page.evaluate(LAST_EVENT), 'Платежі: остання подія розкладу недосяжна')



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
