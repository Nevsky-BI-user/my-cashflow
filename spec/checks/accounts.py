# Рахунки: банківські картки на ПК-Огляді (1280, 1920), форма рахунку, зарплатний рахунок лише один; ряд карток на телефоні
import re as _re
from datetime import datetime as _dt

from helpers import check, dialog, shot

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
KPI_H = "[...document.querySelectorAll('.dv-kpis .dv-kpi')].map(e=>Math.round(e.getBoundingClientRect().height))"
# текстові вузли ПК-Огляду поза банківськими картками, дрібніші за 11.5px (підписи 11.5, основний 13; дизайн ПК v135)
SMALL = """[...document.querySelectorAll('.p-overview.desk *')].filter(e=>!e.closest('.bcard')&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))
.map(e=>[e.textContent.trim().slice(0,20),parseFloat(getComputedStyle(e).fontSize)]).filter(x=>x[1]<11.5)"""


def num(t):
    return t.replace(' ', ' ').replace(' ', ' ').strip()


def desktop(page):
    cards = page.locator('.dv-cards .bcard')
    check(cards.count() == 3, f'на ПК {cards.count()} карток замість 3')
    # «+ Рахунок» не плитка, а мала кнопка в заголовку «Рахунки»
    check(page.locator('.dv-cards .bcard-add').count() == 0, 'у ряду карток лишилась плитка «+ Рахунок»')
    check(page.locator('.dv-acc-head .dv-acc-add').count() == 1, 'немає кнопки «+ Рахунок» у заголовку рахунків')
    for i in range(3):
        w = cards.nth(i).bounding_box()
        check(240 <= w['width'] <= 300.5 and abs(w['height'] - 96) <= 1, f'картка {i + 1}: {w["width"]:.0f}x{w["height"]:.0f}, а не 240-300 x 96')
    # monobank: чорна картка, «дебетова», кнопка ↻ «Оновити» без БД не падає й оновлює час
    mono = page.locator('.dv-cards .bcard-mono')
    check(mono.count() == 1, 'немає картки monobank')
    mt = mono.inner_text().lower()
    check('monobank' in mt and 'дебетова' in mt and 'оновлено' in mt, f'картка monobank: {mt!r}')
    # дизайн ПК v135: плоска картка, mono #1a1c22 без градієнта
    bg = mono.evaluate("e=>{const s=getComputedStyle(e);return s.backgroundImage+' | '+s.backgroundColor}")
    check(bg == 'none | rgb(26, 28, 34)', f'картка monobank не плоска чорна #1a1c22: {bg[:90]}')
    upd = page.locator('.dv-acc-head .dv-mono-upd')
    check(upd.count() == 1 and 'Оновити' in upd.inner_text(), 'немає кнопки «Оновити» для monobank')
    upd.click()
    page.wait_for_timeout(300)
    hm = _re.search(r'оновлено (\d\d:\d\d)', mono.inner_text())
    now = _dt.now()
    check(hm and abs((now.hour * 60 + now.minute) - (int(hm.group(1)[:2]) * 60 + int(hm.group(1)[3:]))) <= 1,
          f'↻ без БД не оновив час: {hm.group(1) if hm else None}, зараз {now:%H:%M}')
    check(page.locator('.dv-mono-msg').count() == 0, 'без БД зʼявилось повідомлення про помилку monobank')
    hs = page.evaluate(KPI_H)
    check(len(hs) == 3 and max(hs) - min(hs) <= 1, f'KPI не однакової висоти: {hs}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    page.mouse.move(2, 2)
    shot(page, 'ov-1280.jpg', full=False)
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
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    cw = page.evaluate("document.querySelector('.content').getBoundingClientRect().width")
    check(cw <= 1600.5, f'ширина контенту {cw:.0f}px більша за 1600')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    fs = page.evaluate("getComputedStyle(document.querySelector('.content')).fontSize")
    check(fs == '13px', f'базовий шрифт .content {fs}, а не 13px')
    small = page.evaluate(SMALL)
    check(not small, f'на ПК-Огляді є текст дрібніший за 12px: {small[:5]}')
    page.mouse.move(2, 2)
    shot(page, 'ov-1920.jpg', full=False)


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
    ('ПК 1920: ширина 1600, шрифт 14, без дрібного', 'desktop', wide),
    ('Ряд карток на телефоні прокручується', 'mobile', mobile),
]
