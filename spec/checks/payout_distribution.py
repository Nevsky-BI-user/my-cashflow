"""Розподіл виплати: паритет із ядром, адаптивність і діалог без записів."""
from helpers import ROOT, check, freeze, settle, num
from checks.v157 import _nav

DAY = '2026-10-15'
OUT = ROOT / 'spec' / '.out'


def trigger(page):
    return page.locator('.pd-trigger:visible')


def open_card(page):
    trigger(page).click()
    d = page.locator('.pd-dialog[open]')
    d.wait_for(state='visible')
    return d


def verify_amounts(page):
    # Expected values come from raw projection fields/events, never from the adapter.
    pr = page.evaluate('window.__financeProjection')
    q = next(q for q in pr['periods'] if q['start'] == pr['nextPlan']['start'] and q['basis'] != 'current')
    events = [e for e in pr['events'] if e['date'] == q['start']]
    income = sum(e['amountCents'] for e in events if e['kind'] == 'income')
    payout = sum(e['amountCents'] for e in events if e['kind'] == 'payout')
    free = q['availableCents'] - q['payoutPrepayCents'] - q['monoOffsetCents']
    expected = {'opening': q['openingCashCents'], 'payout': payout, 'income': income,
                'sources': q['openingCashCents'] + payout + income,
                'arrears': sum(e['amountCents'] for e in events if e['kind'] == 'arrears'),
                'carry': q['leftoverCents'], 'carry-repay': q['leftoverRepayCents'],
                'carry-prepay': q['leftoverPrepayCents'], 'carry-savings': q['leftoverSavingsCents'],
                'own': q['ownCents'], 'reserve': q['reserveCents'], 'repay': q['payoutRepayCents'],
                'prepay': q['payoutPrepayCents'], 'free': free, 'budget': q['targetCents'],
                'covered': min(q['targetCents'], free), 'gap': max(0, q['targetCents'] - free),
                'surplus': max(0, free - q['targetCents']), 'cash': q['cashOutCents'],
                'mono': q['toMonoCents'] - q['monoOffsetCents'], 'due-short': q['dueShortCents']}
    d = page.locator('.pd-dialog[open]')
    for key, cents in expected.items():
        cell = d.locator(f'[data-row="{key}"] .pd-money')
        check(int(cell.get_attribute('data-cents')) == cents, f'{key}: wrong raw cents')
        check(abs(num(cell.inner_text()) * 100 - cents) < .01, f'{key}: displayed money loses cents')
    check(expected['sources'] == expected['arrears'] + expected['carry'] + expected['own'], 'source conservation')
    check(expected['own'] == expected['reserve'] + expected['repay'] + expected['prepay'] + free, 'pool conservation')
    check(free == expected['cash'] + expected['mono'], 'placement counted twice')
    check(trigger(page).get_attribute('data-date') == q['start'] and q['start'] > DAY, 'not strictly future payout')
    return expected


def responsive(page):
    mobile = page.viewport_size['width'] < 1024
    freeze(page, DAY)
    sizes = [(320, 812), (390, 844)] if mobile else [(1280, 800), (1280, 860), (1440, 900)]
    for width, height in sizes:
        page.set_viewport_size(dict(width=width, height=height))
        page.wait_for_timeout(600)
        settle(page)
        geo = page.evaluate("""()=>{const visible=e=>e.getClientRects().length;const head=[...document.querySelectorAll('.fc-head')].find(visible);const main=document.querySelector('.dv-main'),bud=document.querySelector('.dv-bud'),plot=document.querySelector('.dv-fc svg');return{wide:document.documentElement.scrollWidth,head:head.getBoundingClientRect().height,headWide:head.scrollWidth-head.clientWidth,main:main?{client:main.clientHeight,scroll:main.scrollHeight,bottom:main.getBoundingClientRect().bottom}:null,budget:bud?bud.getBoundingClientRect().bottom:null,plot:plot?plot.getBoundingClientRect().height:null,money:[...document.querySelectorAll('.dv-kpi-v,.kpi-rv')].filter(e=>visible(e)&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)}}""")
        check(geo['wide'] <= width and geo['headWide'] <= 1 and not geo['money'], f'{width}: overview clipped {geo}')
        check(geo['head'] <= (60 if mobile else 31), f'{width}: payout action made forecast header taller {geo}')
        if not mobile:
            check(geo['main']['scroll'] <= geo['main']['client'] + 2 and geo['budget'] <= min(height, geo['main']['bottom'] + 1), f'{width}: core card below viewport {geo}')
            check(geo['plot'] >= (179.5 if height < 840 else 239.5), f'{width}: plot below approved minimum {geo}')
        page.screenshot(path=str(OUT / f'payout-distribution-{width}x{height}-overview.png'), full_page=True)
        d = open_card(page)
        verify_amounts(page)
        bad = d.evaluate("""d=>{const r=d.getBoundingClientRect();return{wide:d.scrollWidth-d.clientWidth,left:r.left,right:r.right,bottom:r.bottom,top:r.top,money:[...d.querySelectorAll('.pd-money')].filter(e=>{if(!e.getClientRects().length)return false;const b=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return e.scrollWidth>e.clientWidth+1||b.left<p.left-1||b.right>p.right+1||b.right>r.right-1}).map(e=>e.textContent)}}""")
        check(bad['wide'] <= 1 and bad['left'] >= 0 and bad['right'] <= width and bad['top'] >= 0 and bad['bottom'] <= height + 1 and not bad['money'], f'{width}: dialog money clipped {bad}')
        page.screenshot(path=str(OUT / f'payout-distribution-{width}x{height}-dialog.png'))
        d.locator('.pd-close').click()
        print(f'      payout {width}x{height}: header {geo["head"]}, plot {geo["plot"]}; full money visible')


def keyboard_motion(page):
    freeze(page, DAY)
    writes = []
    page.on('request', lambda q: writes.append(q.url) if q.method not in ('GET', 'HEAD', 'OPTIONS') else None)
    before = page.evaluate('JSON.stringify(window.__financeInput)')
    button = trigger(page)
    check(button.get_attribute('aria-haspopup') == 'dialog' and '₴' in button.get_attribute('aria-label'), 'missing accessible payout amount/dialog hint')
    check('Прогноз' in button.inner_text(), 'forecast label is only available to screen readers')
    button.focus()
    page.keyboard.press('Enter')
    d = page.locator('.pd-dialog[open]')
    check(d.locator('.pd-close').evaluate('e=>e===document.activeElement'), 'dialog initial focus')
    verify_amounts(page)
    for _ in range(4):
        page.keyboard.press('Tab')
        check(d.evaluate('e=>e.contains(document.activeElement)'), 'native modal focus escaped')
    for _ in range(4):
        page.keyboard.press('Shift+Tab')
        check(d.evaluate('e=>e.contains(document.activeElement)'), 'reverse modal focus escaped')
    page.keyboard.press('Escape')
    check(page.locator('.pd-dialog[open]').count() == 0, 'Escape did not close')
    check(button.evaluate('e=>e===document.activeElement'), 'focus not returned')
    check(button.locator('.pd-coin').evaluate("e=>getComputedStyle(e).animationDuration") == '0.48s', 'decorative animation duration')
    page.emulate_media(reduced_motion='reduce')
    check(button.locator('.pd-coin').evaluate("e=>getComputedStyle(e).animationName") == 'none', 'reduced motion still animated')
    open_card(page)
    check(page.locator('.pd-dialog [data-counting]').count() == 0, 'financial numbers animate')
    verify_amounts(page)
    page.keyboard.press('Escape')
    check(page.evaluate('JSON.stringify(window.__financeInput)') == before and not writes, 'read-only dialog changed data or sent write')


def historical(page):
    freeze(page, DAY)
    initial = trigger(page).get_attribute('data-date')
    _nav(page, -1)
    check(trigger(page).get_attribute('data-date') == initial, 'history incorrectly changes upcoming payout')
    d = open_card(page)
    expected = verify_amounts(page)
    check('Історичний період' in d.inner_text(), 'history/current date context missing')
    d.locator('.pd-close').click()
    _nav(page, 2)
    check(trigger(page).get_attribute('data-date') == initial, 'selected future range changed nearest payout')
    open_card(page)
    check(verify_amounts(page) == expected, 'selected period changes current payout projection')


def scenario(page):
    from checks.finance import fixture, _budget_tip
    fixture(page)
    before = page.evaluate('JSON.stringify(window.__financeInput)')
    writes = []
    page.on('request', lambda q: writes.append(q.url) if q.method not in ('GET', 'HEAD', 'OPTIONS') else None)
    _budget_tip(page)
    page.locator('.kpi-tip[data-k=budget]').get_by_role('button', name='Сценарій кредитки', exact=True).click()
    d = page.locator('dialog[open]')
    d.get_by_label('Дозволений платіж').select_option('fixed:1:2026-10')
    d.get_by_label('Кредитний рахунок').select_option('2')
    d.get_by_label('Сума перенесення', exact=True).fill('4000')
    d.get_by_role('button', name='Переглянути сценарій').click()
    d.get_by_role('button', name='Закрити', exact=True).click()
    check(trigger(page).get_attribute('data-scenario') == 'true' and 'Сценарій' in trigger(page).get_attribute('aria-label'), 'scenario trigger not labeled')
    check('Сценарій' in trigger(page).inner_text(), 'scenario is marked only by color/aria-label')
    d = open_card(page)
    check('кредитний сценарій' in d.locator('.pd-status').inner_text(), 'scenario dialog not labeled')
    verify_amounts(page)
    page.screenshot(path=str(OUT / 'payout-distribution-scenario.png'))
    d.locator('.pd-close').click()
    for width, height in ((1280, 800), (320, 812), (390, 844)):
        page.set_viewport_size(dict(width=width, height=height))
        page.wait_for_timeout(400)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{width}: scenario header creates horizontal overflow')
        check('Сценарій' in trigger(page).inner_text(), f'{width}: missing visible scenario label')
        open_card(page)
        verify_amounts(page)
        page.locator('.pd-close:visible').click()
    check(page.evaluate('JSON.stringify(window.__financeInput)') == before and not writes, 'scenario preview performed data write')


def partial(page):
    freeze(page, DAY, [('const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:financeThrough});', "const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:'2026-10-21'});")])
    check(trigger(page).get_attribute('data-state') == 'available', 'partial horizon lost known payout allocation')
    d = open_card(page)
    verify_amounts(page)
    check('Горизонт не покриває весь період' in d.inner_text(), 'partial horizon not disclosed')
    check(d.locator('[data-row=credit],[data-row=short],[data-row=mandatory]').count() == 0, 'partial totals presented as zero/complete')


def unavailable(page):
    freeze(page, DAY, [('const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:financeThrough});', "const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:'2026-10-20'});")])
    check(trigger(page).get_attribute('data-state') == 'unavailable', 'outside-horizon allocation fabricated')
    d = open_card(page)
    check('поза горизонтом' in d.locator('[role=status]').inner_text(), 'missing reason for unavailable payout')
    check(d.locator('.pd-money').count() == 0, 'unavailable allocation shown as financial zero')


CHECKS = [
    ('payout_distribution: desktop geometry and monetary parity', 'desktop', responsive),
    ('payout_distribution: mobile geometry and monetary parity', 'mobile', responsive),
    ('payout_distribution: keyboard reduced motion and no writes', 'desktop', keyboard_motion),
    ('payout_distribution: selected historical range desktop', 'desktop', historical),
    ('payout_distribution: selected historical range mobile', 'mobile', historical),
    ('payout_distribution: explicit actual credit scenario', 'desktop', scenario),
    ('payout_distribution: partial horizon honest period totals', 'desktop', partial),
    ('payout_distribution: outside horizon unavailable', 'desktop', unavailable),
]
