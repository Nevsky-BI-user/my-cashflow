"""Synthetic mobile wallet: actual motion, safe gestures and width-aware cents."""
from helpers import check, freeze, shot, touch_drag


def _deck(page, width):
    page.set_viewport_size({'width': width, 'height': 844})
    page.wait_for_timeout(150)
    deck = page.locator('.o-card-stack')
    deck.scroll_into_view_if_needed()
    return deck


def _current(page, index):
    check(page.locator('.o-stack-item').nth(index).get_attribute('aria-hidden') == 'false', 'Wrong active stack item')
    state = page.locator('.o-stack-item').evaluate_all("es=>es.map(e=>({inert:e.inert,hidden:e.getAttribute('aria-hidden')}))")
    check(all(x['inert'] == (i != index) for i, x in enumerate(state)), f'Inactive cards remain interactive: {state}')


def _step(page, key):
    # Стрілок під колодою немає: крок клавішею з поточної картки.
    page.locator('.o-stack-item[aria-hidden=false] button').first.focus()
    page.keyboard.press(key)


def gestures(page):
    freeze(page, '2026-10-13')
    for width in (320, 390, 430):
        deck = _deck(page, width)
        card = deck.locator('.o-bank-card').first
        card.focus()
        page.keyboard.press('Home')
        page.wait_for_timeout(500)
        first, second = deck.locator('.o-stack-item').nth(0).bounding_box(), deck.locator('.o-stack-item').nth(1).bounding_box()
        check(first['x'] < second['x'] < first['x'] + first['width'] and second['y'] > first['y'], f'{width}: cards do not overlap in depth')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{width}: horizontal document overflow')
        # Задні картки не обрізані, до наступного блоку не менше 16px.
        gap = page.evaluate("(()=>{const s=document.querySelector('.o-account-section'),n=s.nextElementSibling,d=document.querySelector('.o-card-stack').getBoundingClientRect();const b=Math.max(...[...document.querySelectorAll('.o-stack-item')].map(e=>e.getBoundingClientRect().bottom));return {clip:b-d.bottom,gap:n.getBoundingClientRect().top-b}})()")
        check(gap['clip'] <= 0 and gap['gap'] >= 16, f'{width}: картки злиплися з блоком нижче {gap}')
        check(page.get_by_role('button', name='Наступна картка').count() == 0 and page.get_by_role('button', name='Попередня картка').count() == 0, f'{width}: стрілки під колодою')
        start = deck.locator('.o-stack-item').first.evaluate('e=>getComputedStyle(e).transform')
        _step(page, 'ArrowRight')
        page.wait_for_timeout(90)
        mid = deck.locator('.o-stack-item').first.evaluate('e=>getComputedStyle(e).transform')
        if width == 390:
            shot(page, 'mobile-stack-390-mid.jpg', full=False)
        page.wait_for_timeout(500)
        end = deck.locator('.o-stack-item').first.evaluate('e=>getComputedStyle(e).transform')
        check(start != mid and mid != end, f'{width}: no measured intermediate animation frame')
        _current(page, 1)
        # Зліва лишається видима смужка попередньої картки, без накладання на поточну.
        box, prev, cur = deck.bounding_box(), deck.locator('.o-stack-item').nth(0).bounding_box(), deck.locator('.o-stack-item').nth(1).bounding_box()
        strip = prev['x'] + prev['width'] - box['x']
        check(14 <= strip <= 20 and prev['x'] + prev['width'] <= cur['x'], f'{width}: previous card strip {strip:.1f}px')
        check(deck.locator('.o-stack-item').nth(0).evaluate('e=>getComputedStyle(e).opacity') == '1', f'{width}: previous card hidden')
        _step(page, 'ArrowLeft')
        page.wait_for_timeout(500)
        _current(page, 0)
        r = card.bounding_box(); x, y = r['x'] + r['width']*.75, r['y']+r['height']*.5
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x-130, y, steps=10); page.mouse.up()
        page.wait_for_timeout(500)
        _current(page, 1)
        check(page.locator('.account-history-sheet').count() == 0, 'Swipe opened account history')
        # Вертикальний жест не перемикає рахунок, а pointercancel повертає колоду.
        active = deck.locator('.o-bank-card[aria-current=true]')
        active.dispatch_event('pointerdown', {'pointerId': 91, 'isPrimary': True, 'button': 0, 'clientX': 140, 'clientY': 300})
        active.dispatch_event('pointermove', {'pointerId': 91, 'isPrimary': True, 'clientX': 142, 'clientY': 370})
        active.dispatch_event('pointercancel', {'pointerId': 91, 'isPrimary': True})
        _current(page, 1)
        check(deck.evaluate("e=>getComputedStyle(e).touchAction") == 'pan-y', 'Deck blocks vertical page scrolling')
        check(deck.evaluate('e=>e.scrollLeft') == 0, 'Focus or swipe scrolled stack horizontally')
        active.focus(); page.keyboard.press('End'); page.wait_for_timeout(500)
        _current(page, 3)
        check(page.get_by_role('button', name='Додати рахунок', exact=True).evaluate('e=>e===document.activeElement'), 'End did not focus add tile')
        page.keyboard.press('Home'); page.wait_for_timeout(500); _current(page, 0)
        shot(page, f'mobile-stack-{width}.jpg', full=False)
    page.emulate_media(reduced_motion='reduce')
    card.focus(); page.keyboard.press('ArrowRight'); page.wait_for_timeout(40); _current(page, 1)
    duration = deck.locator('.o-stack-item').first.evaluate('e=>getComputedStyle(e).transitionDuration')
    check(duration in ('0s', '1e-05s'), 'Reduced motion still animates cards')
    page.keyboard.press('ArrowLeft'); page.wait_for_timeout(40); _current(page, 0)


def amounts(page):
    page.set_viewport_size({'width': 320, 'height': 844})
    freeze(page, '2026-10-13', [('balance:5000,debt:0,debt_month:null,min_spend', 'balance:1234567.89,debt:98.76,debt_month:null,min_spend')])
    deck = _deck(page, 320)
    amount = deck.locator('.o-bank-card').first.locator('.account-amounts b')
    details = amount.first.evaluate('e=>({width:e.clientWidth,text:e.textContent,precision:e.dataset.amountPrecision,font:getComputedStyle(e).font})')
    check(amount.first.get_attribute('data-amount-precision') == 'integer', f'Narrow large balance did not drop cents: {details}')
    check(amount.nth(1).get_attribute('data-amount-precision') == 'full', 'Short amount unnecessarily lost cents')
    exact = amount.first.get_attribute('data-exact-amount')
    check('89' in (exact or ''), 'Exact cents absent from accessible amount')
    check('89' in amount.first.locator('xpath=..').inner_text(), 'Exact cents absent from screen reader text')
    for width in (390, 430):
        _deck(page, width)
        check(amount.first.get_attribute('data-amount-precision') == 'full', f'{width}: balance did not regain cents after resize')
        check('89' in amount.first.inner_text(), f'{width}: visible cents missing')
    _deck(page, 320)
    check(amount.first.get_attribute('data-amount-precision') == 'integer', 'Narrowing again did not remeasure amount')
    check(amount.first.get_attribute('data-exact-amount') == exact, 'Responsive presentation changed exact amount')


def interrupted_swipe(page):
    freeze(page, '2026-10-13')
    deck = _deck(page, 390)
    _step(page, 'ArrowRight')
    page.wait_for_timeout(80)
    item = deck.locator('.o-stack-item').nth(1)
    before = item.evaluate('e=>new DOMMatrixReadOnly(getComputedStyle(e).transform).m41')
    r = item.bounding_box()
    x, y = r['x'] + r['width']*.45, r['y'] + r['height']*.45
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x+16, y, steps=1)
    during = item.evaluate('e=>new DOMMatrixReadOnly(getComputedStyle(e).transform).m41')
    check(abs(during-before) < 35, f'Interrupted animation jumped: {before} -> {during}')
    page.mouse.move(x+135, y, steps=8); page.mouse.up()
    page.wait_for_timeout(500)
    _current(page, 0)
    check(page.locator('.account-history-sheet').count() == 0, 'Fast reversal opened history')
    r = deck.locator('.o-bank-card').first.bounding_box()
    x, y = r['x'] + r['width']*.5, r['y'] + r['height']*.65
    scroll = lambda: page.evaluate('scrollY+(document.querySelector(".content")?.scrollTop||0)')
    start = scroll()
    touch_drag(page, x, y, x+2, y-120, after=300)
    check(scroll() > start+30, 'Vertical touch on the card blocked page scrolling')
    _current(page, 0)
    check(page.locator('.account-history-sheet').count() == 0, 'Vertical scroll opened history')


CHECKS = [
    ('Mobile stack 320/390/430: overlap, motion, gestures, keyboard and reduced motion', 'mobile', gestures),
    ('Mobile stack: cents disappear only when needed and return on resize', 'mobile', amounts),
    ('Mobile stack: rapid swipe reversal and real vertical scrolling', 'mobile', interrupted_swipe),
]
