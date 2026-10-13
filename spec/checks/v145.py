# v145 (рішення власника 12.10.2026): чотири плитки KPI з поясненнями, кільце категорій бюджету, список «Платежі до зарплати DD.MM»
# на телефоні, щоденні витрати в Потоці одним рядком на період. Числа звіряються з єдиною проєкцією (finance_ref).
import re

from helpers import check, finance_ref, freeze, go_tab, num, settle, shot

DAY = '2026-10-08'
KEYS = ['funds', 'budget', 'balance', 'inst']
INST = re.compile(r'^.+ · [\d\s  ]+(,\d+)? ₴ × \d+ · до \d\d\.\d\d\.\d{4}( → \d\d\.\d\d\.\d{4})?$')  # v153 доповнення 5: прогнозна дата закриття (компактно «до ДД.ММ.РРРР → ДД.ММ.РРРР», рішення координатора) після дострокового погашення
TIP = re.compile(r'^.+: факт [\d\s  ]+ з плану [\d\s  ]+ ₴(, понад план)?$')
NO_OVERLAP = """sel=>{const b=[...document.querySelectorAll(sel)].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect());const bad=[];
for(let i=0;i<b.length;i++)for(let j=i+1;j<b.length;j++){const p=b[i],q=b[j];if(p.right>q.left+0.5&&q.right>p.left+0.5&&p.bottom>q.top+0.5&&q.bottom>p.top+0.5)bad.push([i,j])}return bad}"""


def _norm(t):
    return t.replace(' ', ' ').replace(' ', ' ').strip()


def _tiles(page, scope):
    return page.evaluate(f"[...document.querySelectorAll('{scope} .kpi-t')].map(e=>e.dataset.k)")


def kpi_values(page, scope):
    """Плитки: «Доступні кошти» = готівка + карти + кредитні (вільний ліміт), «Баланс» = власні мінус борг, розстрочки форматом
    «Назва · X ₴ × n · до DD.MM.YYYY»; значення з проєкції."""
    r = finance_ref(page)
    snap = r['snapshot']
    check(_tiles(page, scope) == KEYS, f'плитки KPI {_tiles(page, scope)}, а не {KEYS}')
    f = page.locator(f'{scope} .kpi-funds')
    rows = {k: num(f.locator(f'[data-r={k}] .kpi-rv').inner_text()) for k in ('cash', 'cards', 'credit')}
    total = num(f.locator('.dv-kpi-v').inner_text())
    accs = [a for a in snap['accounts'] if a.get('active') is not False]
    credit = sum(max(0, round(float(a.get('credit_limit') or 0) * 100) - (a.get('debtCents') or 0))
                 for a in accs if a.get('kind') == 'credit' and float(a.get('credit_limit') or 0) > 0) / 100
    own = snap['positiveOwnCents'] / 100
    print(f'      Доступні {total} = готівка {rows["cash"]} + карти {rows["cards"]} + кредитні {rows["credit"]}; еталон власні {own:.2f} + ліміт {credit:.2f}')
    check(abs(rows['cash'] + rows['cards'] - own) <= 1, f'готівка + карти {rows["cash"] + rows["cards"]}, а власні {own:.2f}')
    check(abs(rows['credit'] - credit) <= 1, f'кредитні {rows["credit"]}, еталон {credit:.2f}')
    check(abs(total - (rows['cash'] + rows['cards'] + rows['credit'])) <= 1, f'«Доступні кошти» {total} не сума рядків {rows}')
    b = page.locator(f'{scope} .kpi-balance')
    bal = num(b.locator('.dv-kpi-v').inner_text())
    want = (snap['positiveOwnCents'] - snap['creditDebtCents']) / 100
    check(abs(bal - want) <= 1, f'«Баланс» {bal}, еталон власні мінус борг {want:.2f}')
    inst = [_norm(t) for t in page.locator(f'{scope} .kpi-inst [data-r=inst], {scope} .kpi-inst[data-r=inst]').all_inner_texts()]
    print(f'      розстрочки: {inst}')
    for t in inst:
        check(INST.match(t.replace('\n', ' ')), f'рядок розстрочки не за форматом «Назва · X ₴ × n · до DD.MM.YYYY»: {t!r}')


def kpi_desktop(page):
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    go_tab(page, 0)
    kpi_values(page, '.dv-kpis')
    # наведення показує пояснення, відведення ховає; «i» закріплює, Escape закриває
    # v154 (власник): пояснення відкривається лише наведенням на «i», не на число плитки
    page.locator('.kpi-funds .kpi-i').hover()
    page.wait_for_selector('.kpi-tip[data-k=funds]')
    check('Готівка і плюсові баланси' in page.inner_text('.kpi-tip[data-k=funds]'), 'пояснення «Доступні кошти» без тексту')
    page.mouse.move(2, 2)
    page.wait_for_timeout(400)
    check(page.locator('.kpi-tip').count() == 0, 'пояснення не сховалось після відведення миші')
    i = page.locator('.kpi-budget .kpi-i')
    i.click()
    page.wait_for_selector('.kpi-tip[data-k=budget]')
    check(i.get_attribute('aria-expanded') == 'true', 'кнопка «i» без aria-expanded=true')
    page.mouse.move(2, 2)
    page.wait_for_timeout(400)
    check(page.locator('.kpi-tip[data-k=budget]').count() == 1, 'закріплене пояснення зникло після відведення миші')
    tip = page.locator('.kpi-tip[data-k=budget]')
    check(tip.get_by_role('button', name='Сценарій кредитки', exact=True).count() == 1, 'у поясненні бюджету немає «Сценарій кредитки»')
    check(tip.get_by_role('button', name='Як пораховано', exact=True).count() == 1, 'у поясненні бюджету немає «Як пораховано»')
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)
    check(page.locator('.kpi-tip').count() == 0 and i.get_attribute('aria-expanded') == 'false', 'Escape не закрив пояснення')
    shot(page, 'v145-kpi-1920.jpg', full=False)


def kpi_mobile(page):
    freeze(page, DAY)
    go_tab(page, 0)
    kpi_values(page, '.projection-summary')
    for k in KEYS:
        i = page.locator(f'.kpi-{k} .kpi-i')
        i.click()
        page.wait_for_selector(f'.kpi-tip[data-k={k}]')
        box = page.locator(f'.kpi-tip[data-k={k}]').bounding_box()
        vw = page.evaluate('document.documentElement.clientWidth')
        check(i.get_attribute('aria-expanded') == 'true', f'{k}: «i» без aria-expanded=true')
        check(box['x'] >= 0 and box['x'] + box['width'] <= vw + 0.5, f'{k}: пояснення виходить за екран {box}')
        i.click()
        page.wait_for_timeout(200)
        check(page.locator('.kpi-tip').count() == 0 and i.get_attribute('aria-expanded') == 'false', f'{k}: повторний дотик не закрив пояснення')
    sw = page.evaluate('[document.scrollingElement.scrollWidth,innerWidth]')
    check(sw[0] <= sw[1], f'горизонтальна прокрутка {sw}')
    shot(page, 'v145-kpi-375.jpg', full=False)


def _donut(page, scope, header=None):
    segs = page.evaluate(f"[...document.querySelectorAll('{scope} .bd-seg')].map(e=>({{id:e.dataset.id,pct:+e.dataset.pct}}))")
    rows = page.evaluate(f"[...document.querySelectorAll('{scope} .bd-row')].map(e=>e.dataset.id)")
    check(segs, f'{scope}: кільце без сегментів')
    check([s['id'] for s in segs] == rows, f'{scope}: сегменти {[s["id"] for s in segs]} не відповідають легенді {rows}')
    check(sum(s['pct'] for s in segs) == 100, f'{scope}: частки разом {sum(s["pct"] for s in segs)}, а не 100')
    check(len([s for s in segs if s['id'] == '__other']) <= 1, f'{scope}: «Інші» двічі')
    check(not page.evaluate(NO_OVERLAP, f'{scope} .bd-row'), f'{scope}: рядки легенди накладаються')
    ctr = num(page.inner_text(f'{scope} .bd-c b'))
    if header:
        spent = num(page.inner_text(header).split('/')[0])
        print(f'      центр кільця {ctr}, витрачено в шапці {spent}, сегментів {len(segs)}')
        check(abs(ctr - spent) <= 1, f'{scope}: центр кільця {ctr} не дорівнює витраченому {spent}')
    return segs


def _hover_seg(page, scope, segs, k):
    """Мишу на середину дуги сегмента k (кути з часток, від 12 години за годинниковою)."""
    b = page.locator(f'{scope} .bd-ring svg').bounding_box()
    import math
    before = sum(s['pct'] for s in segs[:k])
    a = -math.pi / 2 + 2 * math.pi * (before + segs[k]['pct'] / 2) / 100
    r = b['width'] / 2 * 0.8
    page.mouse.move(b['x'] + b['width'] / 2 + r * math.cos(a), b['y'] + b['height'] / 2 + r * math.sin(a))
    page.wait_for_timeout(150)


def donut_desktop(page):
    for w, hgt in ((1920, 1080), (1280, 800)):
        page.set_viewport_size({'width': w, 'height': hgt})
        freeze(page, DAY)
        go_tab(page, 0)
        segs = _donut(page, '.dv-main', '.dv-main .dv-bud-v')
        # v148: нижче 840px Огляд ПК прокручується сторінкою, тож кільце спершу в поле зору
        page.locator('.dv-main .bd-ring').scroll_into_view_if_needed()
        k = next(i for i, s in enumerate(segs) if not s['id'].startswith('__'))
        _hover_seg(page, '.dv-main', segs, k)
        tip = _norm(page.inner_text('.bd-tip .bd-tip-h')) if page.locator('.bd-tip').count() else ''
        check(TIP.match(tip), f'{w}: підказка сегмента не «Назва: факт X з плану Y ₴»: {tip!r}')
        dim = page.locator('.dv-main .bd-seg.dim').count()
        check(dim == len(segs) - 1, f'{w}: при наведенні приглушено {dim} з {len(segs) - 1} інших сегментів')
        shot(page, f'v145-donut-{w}.jpg', full=False)
        _hover_seg(page, '.dv-main', segs, k)
        page.mouse.down()
        page.mouse.up()
        page.wait_for_timeout(400)
        check(page.locator('.cat-drw').count() == 1, f'{w}: клік по сегменту не відкрив бічну панель категорії')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)


def donut_mobile(page):
    freeze(page, DAY)
    go_tab(page, 0)
    page.locator('.p-overview .bd').scroll_into_view_if_needed()
    segs = _donut(page, '.p-overview')
    row = page.locator('.p-overview .bd-row').nth(next(i for i, s in enumerate(segs) if not s['id'].startswith('__')))
    lbl = _norm(row.get_attribute('aria-label') or '')
    check(TIP.match(lbl.split(', ')[0] + (', понад план' if ', понад план' in lbl else '')) and '% факту' in lbl, f'aria-label рядка легенди: {lbl!r}')
    row.click()
    page.wait_for_timeout(400)
    check(page.locator('.cat-drw-m, .cat-drw').count() >= 1, 'дотик по рядку легенди не відкрив категорію')
    sw = page.evaluate('[document.scrollingElement.scrollWidth,innerWidth]')
    check(sw[0] <= sw[1], f'горизонтальна прокрутка {sw}')


def pay_list(page):
    """Телефон, Платежі: список під календарем «Платежі до зарплати DD.MM · N», де DD.MM: дата наступної зарплати (не авансу), N: рядків у списку."""
    freeze(page, DAY)
    go_tab(page, 3)
    s = page.locator('details.cm-month > summary')
    check(s.count() == 1, 'немає списку платежів місяця')
    t = _norm(s.inner_text())
    m = re.match(r'^Платежі до зарплати (\d\d)\.(\d\d) · (\d+)$', t)
    check(m, f'заголовок списку: {t!r}')
    n = finance_ref(page)['nextPlan']
    sal = next((x['date'] for x in (n.get('nextPayout'), n.get('followingPayout')) if x and x.get('kind') == 'salary'), None)
    print(f'      {t!r}, наступна зарплата {sal}')
    check(sal and (m.group(2), m.group(1)) == (sal[5:7], sal[8:10]), f'дата в заголовку {m.group(1)}.{m.group(2)}, а зарплата {sal}')
    s.click()
    page.wait_for_timeout(200)
    n = page.evaluate("document.querySelectorAll('details.cm-month > .cm-event').length")  # v149: без рядка-шапки «Подія / Сума · баланс після»
    check(n == int(m.group(3)), f'у заголовку {m.group(3)} платежів, а рядків {n}')


def flow_daily(page):
    """Потік: прогноз щоденних витрат одним рядком на період «Щоденні витрати, прогноз (DD.MM-DD.MM)», без рядка на кожен день."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    go_tab(page, 2)
    rows = [_norm(t) for t in page.locator('.p-flow.desk .flow-row').all_inner_texts()]
    daily = [t for t in rows if 'Щоденні витрати' in t]
    lbl = [re.search(r'Щоденні витрати, прогноз \((\d\d\.\d\d)-(\d\d\.\d\d)\)', t) for t in daily]
    print(f'      рядків щоденних витрат {len(daily)}: {[m.group(0) if m else None for m in lbl]}')
    check(daily, 'у Потоці немає прогнозу щоденних витрат')
    check(all(lbl), f'рядок щоденних витрат без періоду: {daily}')
    keys = [m.group(0) for m in lbl]
    check(len(keys) == len(set(keys)), f'період повторюється: {keys}')


CHECKS = [
    ('v145: плитки KPI на ПК, пояснення наведенням і «i»', 'desktop', kpi_desktop),
    ('v145: плитки KPI на телефоні, «i» відкриває і закриває', 'mobile', kpi_mobile),
    ('v145: кільце категорій на ПК: сегменти, частки, підказка, бічна панель', 'desktop', donut_desktop),
    ('v145: кільце категорій на телефоні', 'mobile', donut_mobile),
    ('v145: «Платежі до зарплати DD.MM · N» на телефоні', 'mobile', pay_list),
    ('v145: щоденні витрати в Потоці одним рядком на період', 'desktop', flow_daily),
]
