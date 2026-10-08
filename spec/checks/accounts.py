# Рахунки: банківські картки на ПК-Огляді (1280, 1920), форма рахунку, зарплатний рахунок лише один; ряд карток на телефоні
from helpers import check, dialog, shot

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
KPI_H = "[...document.querySelectorAll('.dv-kpis .dv-kpi')].map(e=>Math.round(e.getBoundingClientRect().height))"
# текстові вузли ПК-Огляду поза банківськими картками, дрібніші за 13px
SMALL = """[...document.querySelectorAll('.p-overview.desk *')].filter(e=>!e.closest('.bcard')&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))
.map(e=>[e.textContent.trim().slice(0,20),parseFloat(getComputedStyle(e).fontSize)]).filter(x=>x[1]<13)"""


def num(t):
    return t.replace(' ', ' ').replace(' ', ' ').strip()


def desktop(page):
    cards = page.locator('.dv-cards .bcard')
    check(cards.count() == 3, f'на ПК {cards.count()} карток замість 3')
    check(page.locator('.dv-cards .bcard-add').count() == 1, 'немає плитки «+ Рахунок»')
    w = cards.first.bounding_box()
    check(abs(w['width'] - 280) < 1 and abs(w['width'] / w['height'] - 1.586) < 0.02, f'картка {w["width"]:.0f}x{w["height"]:.0f}, а не 280 і 1.586:1')
    hs = page.evaluate(KPI_H)
    check(len(hs) == 3 and max(hs) - min(hs) <= 1, f'KPI не однакової висоти: {hs}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    page.mouse.move(2, 2)
    shot(page, 'ov-1280.jpg')
    # баланс Ощадбанку: повзунок 7300 і «Зберегти»
    cards.first.click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    check(d.count() == 1, 'клік по картці не відкрив форму рахунку')
    rng = d.locator('input.nf-range').first
    rng.evaluate(SETR, 7300)
    page.wait_for_timeout(150)
    shot(page, 'acc-edit-1280.jpg')
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(300)
    check(d.count() == 0, 'форма не закрилась після «Зберегти»')
    s = num(cards.first.locator('.bcard-sum').inner_text())
    check(s == '7 300 ₴', f'після збереження на картці «{s}», а не «7 300 ₴»')
    # зарплатний рахунок лише один: увімкнути на monobank
    cards.nth(2).click()
    page.wait_for_timeout(300)
    d.locator('[role=switch]').click()
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(300)
    gold = [cards.nth(i).inner_text().count('зарплата сюди') for i in range(3)]
    check(gold == [0, 0, 1], f'позначка «зарплата сюди» по картках: {gold}, очікували лише на третій')
    # Esc закриває форму
    cards.first.click()
    page.wait_for_timeout(300)
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив форму рахунку')


def wide(page):
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(400)
    cw = page.evaluate("document.querySelector('.content').getBoundingClientRect().width")
    check(cw <= 1400.5, f'ширина контенту {cw:.0f}px більша за 1400')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    fs = page.evaluate("getComputedStyle(document.querySelector('.content')).fontSize")
    check(fs == '15px', f'базовий шрифт .content {fs}, а не 15px')
    small = page.evaluate(SMALL)
    check(not small, f'на ПК-Огляді є текст дрібніший за 13px: {small[:5]}')
    page.mouse.move(2, 2)
    shot(page, 'ov-1920.jpg')


def mobile(page):
    row = page.locator('.o-cards')
    check(row.count() == 1, 'на телефоні немає ряду карток')
    check(row.locator('.bcard').count() == 3, 'у ряду не 3 картки')
    st = row.evaluate("e=>({sw:e.scrollWidth,cw:e.clientWidth,ox:getComputedStyle(e).overflowX,snap:getComputedStyle(e).scrollSnapType})")
    check(st['ox'] == 'auto' and st['sw'] > st['cw'], f'ряд карток не прокручується горизонтально: {st}')
    check('x' in st['snap'], f'немає scroll-snap: {st["snap"]}')
    row.evaluate('e=>e.scrollLeft=e.scrollWidth')
    page.wait_for_timeout(200)
    check(row.evaluate('e=>e.scrollLeft') > 0, 'ряд карток не прокрутився')
    row.evaluate('e=>e.scrollLeft=0')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол сторінки на 375')
    free = page.locator('.o-free').inner_text().lower()  # підпис героя у верхньому регістрі (text-transform)
    check('вільно до виплати' in free, f'герой «Вільно до виплати» не знайдено: {free!r}')
    shot(page, 'ov-375.jpg')


CHECKS = [
    ('Картки на ПК, форма, баланс, зарплатний один', 'desktop', desktop),
    ('ПК 1920: ширина 1400, шрифт 15, без дрібного', 'desktop', wide),
    ('Ряд карток на телефоні прокручується', 'mobile', mobile),
]
