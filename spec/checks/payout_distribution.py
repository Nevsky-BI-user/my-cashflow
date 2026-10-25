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
    savings = q['savingsCents'] - q['leftoverSavingsCents']
    funded_reserve = min(q['reserveCents'], q['ownCents'])
    free = q['availableCents'] - q['payoutPrepayCents'] - q['monoOffsetCents'] - savings
    expected = {'opening': q['openingCashCents'], 'payout': payout, 'income': income,
                'sources': q['openingCashCents'] + payout + income,
                'arrears': sum(e['amountCents'] for e in events if e['kind'] == 'arrears'),
                'carry': q['leftoverCents'], 'carry-repay': q['leftoverRepayCents'],
                'carry-prepay': q['leftoverPrepayCents'], 'carry-savings': q['leftoverSavingsCents'],
                'own': q['ownCents'], 'reserve': funded_reserve, 'repay': q['payoutRepayCents'],
                'prepay': q['payoutPrepayCents'], 'savings': savings, 'free': free, 'budget': q['targetCents'],
                'covered': min(q['targetCents'], free), 'gap': max(0, q['targetCents'] - free),
                'surplus': max(0, free - q['targetCents']), 'cash': q['cashOutCents'],
                'mono': q['toMonoCents'] - q['monoOffsetCents'], 'due-short': q['dueShortCents']}
    d = page.locator('.pd-dialog[open]')
    for key, cents in expected.items():
        cell = d.locator(f'[data-row="{key}"] .pd-money')
        if key.startswith('carry') and q['leftoverCents'] == 0:
            check(cell.count() == 0 and cents == 0, 'zero legacy carry still presented as a separate distribution')
            continue
        check(int(cell.get_attribute('data-cents')) == cents, f'{key}: wrong raw cents')
        check(abs(num(cell.inner_text()) * 100 - cents) < .01, f'{key}: displayed money loses cents')
    check(expected['sources'] == expected['arrears'] + expected['carry'] + expected['own'], 'source conservation')
    check(expected['own'] == expected['reserve'] + expected['repay'] + expected['prepay'] + savings + free, 'pool conservation')
    check(d.locator('[data-row=savings]').count() == 1, 'savings not shown as one final amount')
    gap = max(q['reserveCents'], q['mandatoryCents']) - funded_reserve
    gap_cell = d.locator('[data-row=reserve-gap] .pd-money')
    check((int(gap_cell.get_attribute('data-cents')) if gap_cell.count() else 0) == gap, 'mandatory shortfall hidden or counted as funded reserve')
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
        geo = page.evaluate("""()=>{const visible=e=>e.getClientRects().length;const head=[...document.querySelectorAll('.fc-head')].find(visible);const main=document.querySelector('.dv-cols'),bud=document.querySelector('.dv-bud'),plot=document.querySelector('.dv-fc svg');return{wide:document.documentElement.scrollWidth,head:head.getBoundingClientRect().height,headWide:head.scrollWidth-head.clientWidth,main:main?{client:main.clientHeight,scroll:main.scrollHeight,bottom:main.getBoundingClientRect().bottom}:null,budget:bud?bud.getBoundingClientRect().bottom:null,plot:plot?plot.getBoundingClientRect().height:null,money:[...document.querySelectorAll('.dv-kpi-v,.kpi-rv')].filter(e=>visible(e)&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)}}""")
        check(geo['wide'] <= width and geo['headWide'] <= 1 and not geo['money'], f'{width}: overview clipped {geo}')
        check(geo['head'] <= (60 if mobile else 31), f'{width}: payout action made forecast header taller {geo}')
        if not mobile:
            check(geo['main']['scroll'] <= geo['main']['client'] + 2 and geo['budget'] <= min(height, geo['main']['bottom'] + 1), f'{width}: core card below viewport {geo}')
            check(geo['plot'] >= (159.5 if height < 900 else 179.5 if height < 1000 else 259.5), f'{width}: plot below approved minimum {geo}')
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
    check('Історичний період' not in d.inner_text() and d.locator('.pd-foot').count() == 0, 'v183: лишилась примітка-пояснення pd-foot')
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
    check('н/д' in d.inner_text() and 'Горизонт не покриває' not in d.inner_text(), 'partial horizon not marked н/д')
    check(d.locator('[data-row=credit],[data-row=short],[data-row=mandatory]').count() == 0, 'partial totals presented as zero/complete')


def unavailable(page):
    freeze(page, DAY, [('const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:financeThrough});', "const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:'2026-10-20'});")])
    check(trigger(page).get_attribute('data-state') == 'unavailable', 'outside-horizon allocation fabricated')
    d = open_card(page)
    check(d.locator('[role=status]').inner_text().strip() == 'н/д', 'unavailable payout not marked н/д')
    check(d.locator('.pd-money').count() == 0, 'unavailable allocation shown as financial zero')


def compact_tabs(page):
    # Перевіряємо CSS-пікселі після масштабування, обидві теми та вузькі екрани.
    freeze(page, DAY)
    for theme in ('dark', 'light'):
        page.evaluate("t=>document.documentElement.dataset.theme=t", theme)
        for width, height in ((1060, 640), (1280, 720), (1440, 900), (320, 812), (390, 844)):
            page.set_viewport_size(dict(width=width, height=height))
            d = open_card(page)
            verify_amounts(page)
            panel = d.get_by_role('tabpanel')
            geo = d.evaluate("""d=>{const p=d.querySelector('.pd-panel:not([hidden])'),r=d.getBoundingClientRect();return{height:d.clientHeight,scroll:d.scrollHeight,left:r.left,right:r.right,top:r.top,bottom:r.bottom,body:p.clientHeight,bodyScroll:p.scrollHeight,close:d.querySelector('.pd-close').getBoundingClientRect().width}}""")
            check(geo['scroll'] <= geo['height'] + 1 and geo['close'] >= 44, f'{theme}/{width}: dialog scroll or close target {geo}')
            check(geo['left'] >= 7 and geo['top'] >= 7 and geo['right'] <= width - 7 and geo['bottom'] <= height - 7, f'{theme}/{width}: dialog touches viewport {geo}')
            if width >= 960:
                check(geo['bodyScroll'] <= geo['body'] + 1, f'{theme}/{width}: summary needs vertical scrolling {geo}')
            else:
                check(panel.locator('.pd-group-pool').evaluate("e=>e.getBoundingClientRect().top") < panel.locator('.pd-group-budget').evaluate("e=>e.getBoundingClientRect().top") < panel.locator('.pd-group-sources').evaluate("e=>e.getBoundingClientRect().top"), 'mobile summary order')
                panel.evaluate('e=>e.scrollTop=e.scrollHeight')
                last = panel.locator('[data-row=mono]')
                check(last.evaluate("e=>{const r=e.getBoundingClientRect(),p=e.closest('.pd-panel').getBoundingClientRect();return r.bottom<=p.bottom&&r.top>=p.top}"), 'mobile final placement inaccessible')
            tabs = d.get_by_role('tab')
            check(tabs.count() == 3 and tabs.nth(0).get_attribute('aria-selected') == 'true', 'reopen did not reset summary')
            for i in range(3):
                target = tabs.nth(i).get_attribute('aria-controls')
                check(d.locator('#' + target).get_attribute('aria-labelledby') == tabs.nth(i).get_attribute('id'), 'tab/panel linkage')
            tabs.nth(0).focus()
            for key, expected in [('ArrowRight', 1), ('End', 2), ('ArrowRight', 0), ('ArrowLeft', 2), ('Home', 0)]:
                page.keyboard.press(key)
                check(tabs.nth(expected).get_attribute('aria-selected') == 'true' and tabs.nth(expected).evaluate('e=>e===document.activeElement'), f'{key}: tab selection/focus')
            page.screenshot(path=str(OUT / f'payout-compact-{theme}-{width}x{height}.png'))
            tabs.nth(2).click()
            page.keyboard.press('Escape')
            check(trigger(page).evaluate('e=>e===document.activeElement'), 'tabbed dialog did not restore trigger focus')


    # Дефіцит: реальні сирі дані рушія, а не підміна фінансових результатів.
    from checks.finance import FIXTURE, fixture
    import copy
    page.set_viewport_size(dict(width=1060, height=640))
    for extra_arrears in (False, True):
        data = copy.deepcopy(FIXTURE)
        data['monthly_budgets'] = []
        data['accounts'][0]['balance'] = 0
        data['salary']['advance_amount'] = 1000
        if extra_arrears:
            data['fixed'].append(dict(id=3, name='Попередня нестача', type='expense', amount=200000, day_of_month=11))
        fixture(page, data)
        d = open_card(page)
        verify_amounts(page)
        for key in ('reserve-gap', 'arrears-left'):
            check(int(d.locator(f'[data-row={key}] .pd-money').get_attribute('data-cents')) > 0, 'deficit fixture lacks ' + key)
        panel = d.get_by_role('tabpanel')
        check(panel.evaluate('p=>p.scrollHeight<=p.clientHeight+1'), 'deficit summary needs desktop scrolling')
        check(panel.locator('.pd-money').evaluate_all("els=>els.every(e=>{const r=e.getBoundingClientRect(),p=e.closest('.pd-panel').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom})"), 'deficit money clipped')
        page.screenshot(path=str(OUT / f'payout-deficit-{extra_arrears}.png'))
        d.locator('.pd-close').click()
        page.unroute(page.url)
    # Сумісність рендерера зі старим адаптерним carry: явно задані 4 рядки,
    # без зміни чи тверджень про поточні формули рушія.
    freeze(page, DAY, [("const v=p.view,dlg=React.useRef(null)", "const v=p.view&&p.view.status==='available'?Object.assign({},p.view,{carry:{total:1234567,repay:1000000,prepay:200000,savings:34567}}):p.view,dlg=React.useRef(null)")])
    d = open_card(page)
    for key, cents in {'carry': 1234567, 'carry-repay': 1000000, 'carry-prepay': 200000, 'carry-savings': 34567}.items():
        cell = d.locator(f'[data-row={key}] .pd-money')
        check(int(cell.get_attribute('data-cents')) == cents and abs(num(cell.inner_text()) * 100 - cents) < .01, 'carry renderer lost value ' + key)
    panel = d.get_by_role('tabpanel')
    check(panel.evaluate('p=>p.scrollHeight<=p.clientHeight+1'), 'carry summary needs desktop scrolling')
    check(panel.locator('.pd-money').evaluate_all("els=>els.every(e=>{const r=e.getBoundingClientRect(),p=e.closest('.pd-panel').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom})"), 'carry money clipped')
    page.screenshot(path=str(OUT / 'payout-legacy-carry-1060x640.png'))
    d.locator('.pd-close').click()


def long_details(page):
    # Синтетичні довгі списки перевіряють лише межі UI; суми підсумку звіряємо з ядром.
    freeze(page, DAY, [
        ('v.categories.map(function(c)', "v.categories.concat(Array.from({length:70},function(_,i){return{id:'stress-'+i,name:'Додаткова категорія '+i,cents:101+i}})).map(function(c)"),
        ('v.schedule.map(function(d)', "v.schedule.concat(Array.from({length:70},function(_,i){return{date:fcIsoAdd('2027-01-01',i),cents:101+i}})).map(function(d)"),
    ])
    for width, height in ((1060, 640), (320, 812), (390, 844)):
        page.set_viewport_size(dict(width=width, height=height))
        d = open_card(page)
        verify_amounts(page)
        for label in ('Категорії', 'По днях'):
            d.get_by_role('tab', name=label, exact=True).click()
            panel = d.get_by_role('tabpanel')
            check(panel.evaluate('e=>e.scrollHeight>e.clientHeight'), f'{width}/{label}: missing local list scroll')
            panel.evaluate('e=>e.scrollTop=e.scrollHeight')
            last = panel.locator('.pd-row').last
            check(last.evaluate("e=>{const r=e.getBoundingClientRect(),p=e.closest('.pd-panel').getBoundingClientRect();return r.top>=p.top&&r.bottom<=p.bottom+1}"), f'{width}/{label}: last detail row unreachable')
            check(d.evaluate('d=>d.scrollHeight<=d.clientHeight+1') and d.locator('.pd-close').is_visible(), 'detail expanded whole modal')
            page.screenshot(path=str(OUT / f'payout-long-{width}-{label}.png'))
        d.locator('.pd-close').click()


CHECKS = [
    ('payout_distribution: compact summary tabs themes and keyboard', 'desktop', compact_tabs),
    ('payout_distribution: bounded long category and day lists', 'desktop', long_details),
    ('payout_distribution: desktop geometry and monetary parity', 'desktop', responsive),
    ('payout_distribution: mobile geometry and monetary parity', 'mobile', responsive),
    ('payout_distribution: keyboard reduced motion and no writes', 'desktop', keyboard_motion),
    ('payout_distribution: selected historical range desktop', 'desktop', historical),
    ('payout_distribution: selected historical range mobile', 'mobile', historical),
    ('payout_distribution: explicit actual credit scenario', 'desktop', scenario),
    ('payout_distribution: partial horizon honest period totals', 'desktop', partial),
    ('payout_distribution: outside horizon unavailable', 'desktop', unavailable),
]
