# v144: бічна панель категорії, групи Бюджету, ліміти в ₴ або %, список Календаря до дня перед зарплатою
from datetime import date, timedelta

from helpers import check, expand_groups, finance_ref, finance_state, freeze, go_tab, num, shot

DAY = '2026-10-12'


def _cur(page):
    """Поточний період проєкції браузера (той самий вхід, що бачить екран)."""
    r = finance_state(page)['result']
    return next(p for p in r['periods'] if p['basis'] == 'current')


def drawer_desktop(page):
    """ПК: панель праворуч, фокус у ній, Esc закриває і повертає фокус на категорію; нижнього блоку операцій немає."""
    from checks.monthly_budget import seed_demo
    seed_demo(page, DAY)
    go_tab(page, 1)
    check(page.locator('.bud-ops').count() == 0, 'лишився блок «операції за період» унизу правої колонки')
    expand_groups(page)  # v145: групи за замовчуванням згорнуті
    btn = page.locator('.bud-grp.open .bud-cat').first
    name = btn.locator('.bud-name').inner_text()
    btn.click()
    page.wait_for_timeout(350)
    d = page.locator('.cat-drw[role=dialog][aria-modal=true]')
    check(d.count() == 1, 'панель категорії не відкрилась')
    box = d.bounding_box()
    vw = page.viewport_size['width']
    check(abs(box['x'] + box['width'] - vw) <= 1 and box['y'] <= 1, f'панель не праворуч на всю висоту: {box}')
    check(name in d.locator('.cat-drw-n').inner_text(), 'у панелі не та категорія')
    check(page.evaluate("!!document.activeElement.closest('.cat-drw')"), 'фокус не в панелі')
    txt = d.inner_text()
    for s in ('Операції місяця', 'У Потік', 'План на місяць'):
        check(s in txt, f'у панелі немає «{s}»')
    ops = d.locator('.cat-op')
    if ops.count():
        r = ops.first.inner_text()
        check('.' in r and '₴' in r, f'рядок операції без дати або суми: {r!r}')
    # Tab з останнього елемента лишається в панелі (пастка фокуса модального діалогу)
    n = page.evaluate("[...document.querySelector('.cat-drw').querySelectorAll('button,input,[tabindex]:not([tabindex=\"-1\"])')].filter(e=>!e.disabled&&e.offsetParent).length")
    page.locator('.cat-drw .cat-to-flow').focus()
    for _ in range(3):
        page.keyboard.press('Tab')
        check(page.evaluate("!!document.activeElement.closest('.cat-drw')"), 'Tab вивів фокус з панелі')
    page.keyboard.press('Shift+Tab')
    check(page.evaluate("!!document.activeElement.closest('.cat-drw')"), 'Shift+Tab вивів фокус з панелі')
    print(f'      фокусованих у панелі: {n}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(250)
    check(page.locator('.cat-drw').count() == 0, 'Esc не закрив панель')
    check(page.evaluate("document.activeElement.classList.contains('bud-cat')"), 'фокус не повернувся на категорію')
    check(page.locator('.p-budget.desk').count() == 1, 'Esc перемкнув вкладку')


def drawer_mobile(page):
    """Телефон: рядок категорії відкриває панель знизу на всю ширину; × і Esc закривають."""
    from checks.monthly_budget import seed_demo
    seed_demo(page, DAY)
    go_tab(page, 1)
    expand_groups(page)  # v145: групи за замовчуванням згорнуті
    row = page.locator('.bud-cat').first
    check(row.count() == 1, 'на телефоні немає рядків категорій у групах')
    row.click()
    page.wait_for_timeout(350)
    d = page.locator('.cat-drw.cat-drw-m')
    check(d.count() == 1, 'панель знизу не відкрилась')
    box = d.bounding_box()
    vw, vh = page.viewport_size['width'], page.viewport_size['height']
    check(abs(box['width'] - vw) <= 1 and abs(box['y'] + box['height'] - vh) <= 1, f'панель не знизу на всю ширину: {box}')
    top = page.evaluate("(()=>{const d=document.querySelector('.cat-drw'),x=d.querySelector('.drw-x').getBoundingClientRect(),cs=getComputedStyle(d);const at=document.elementFromPoint(innerWidth/2,innerHeight-4);return {pos:cs.position,over:!!(at&&at.closest('.cat-drw')),xw:x.width,xh:x.height}})()")
    print(f'      аркуш: {top}')
    check(top['pos'] == 'fixed' and top['over'], f'аркуш не поверх вкладок і кнопки «+»: {top}')
    check(top['xw'] >= 44 and top['xh'] >= 44, f'кнопка × менша за 44px: {top}')
    check(page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'), 'горизонтальна прокрутка з панеллю')
    shot(page, 'v144-drawer-375.jpg', full=False)
    d.locator('.drw-x').click()
    page.wait_for_timeout(250)
    check(page.locator('.cat-drw').count() == 0, '× не закрив панель')
    row.click()
    page.wait_for_timeout(300)
    page.keyboard.press('Escape')
    page.wait_for_timeout(250)
    check(page.locator('.cat-drw').count() == 0, 'Esc не закрив панель на телефоні')


def groups(page):
    """Групи за sort_order; v145: усі згорнуті за замовчуванням, рядок групи розгортає (клік, Enter, Space), стан памʼятається;
    сума групи = сума її категорій; без group_id: «Інше»."""
    from checks.monthly_budget import seed_demo
    seed_demo(page, DAY)
    go_tab(page, 1)
    gs = page.evaluate("""[...document.querySelectorAll('.bud-grp')].map(g=>({id:g.dataset.g,open:g.querySelector('.bud-grp-h').getAttribute('aria-expanded')==='true',
n:g.querySelector('.bud-grp-n').firstChild.textContent}))""")
    order = page.evaluate("BGROUPS.slice().sort((a,b)=>a.sort_order-b.sort_order).map(g=>String(g.id))")
    ids = [g['id'] for g in gs]
    check(ids == [i for i in order if i in ids], f'порядок груп {ids}, очікували за sort_order {order}')
    check(gs and not any(g['open'] for g in gs), f'групи не згорнуті за замовчуванням: {[g["n"] for g in gs if g["open"]]}')
    check(page.locator('.bud-grp .bud-cat:visible').count() == 0, 'у згорнутих групах видно категорії')
    h0 = page.locator('.bud-grp-h').first
    rot = lambda: page.evaluate("getComputedStyle(document.querySelector('.bud-grp .bud-grp-chev')).transform")
    r0 = rot()
    h0.click()
    page.wait_for_timeout(300)
    check(h0.get_attribute('aria-expanded') == 'true' and page.locator('.bud-grp').first.locator('.bud-cat:visible').count() > 0, 'клік не розгорнув групу')
    check(rot() != r0, f'шеврон не обернувся: {r0} -> {rot()}')
    h0.focus()
    page.keyboard.press('Enter')
    page.wait_for_timeout(200)
    check(h0.get_attribute('aria-expanded') == 'false', 'Enter не згорнув групу')
    page.keyboard.press('Space')
    page.wait_for_timeout(200)
    check(h0.get_attribute('aria-expanded') == 'true', 'Space не розгорнув групу')
    page.reload()
    page.wait_for_selector('.side', timeout=20000)
    go_tab(page, 1)
    check(page.locator('.bud-grp-h').first.get_attribute('aria-expanded') == 'true', 'розгорнута група не запамʼяталась після перезавантаження')
    expand_groups(page)
    rows = page.evaluate("""[...document.querySelectorAll('.bud-grp')].map(g=>({n:g.querySelector('.bud-grp-n').firstChild.textContent,s:[...g.querySelectorAll('.bud-grp-h .bud-value')].map(e=>e.textContent),
c:[...g.querySelectorAll('.bud-cat')].map(c=>({n:c.querySelector('.bud-name').textContent,v:[...c.querySelectorAll('.bud-value')].map(e=>e.textContent)}))}))""")
    for g in rows:
        f = sum(num(c['v'][0]) for c in g['c'])
        pl = sum(num(c['v'][1]) for c in g['c'])
        check(abs(num(g['s'][0]) - f) <= len(g['c']), f'{g["n"]}: факт групи {g["s"]} проти суми категорій {f}')
        check(abs(num(g['s'][1]) - pl) <= len(g['c']), f'{g["n"]}: план групи {g["s"]} проти суми категорій {pl}')
    other = next((g for g in rows if g['n'] == 'Інше'), None)
    check(other and any(c['n'] == 'Інше' for c in other['c']), 'категорія без group_id не потрапила в групу «Інше»')
    # Усі змінні факти включно з некатегоризованими: одна вибірка [start,end), до asof.
    st = finance_state(page)
    fsum = sum(num(c['v'][0]) for g in rows for c in g['c'])
    cp = page.evaluate('window.__calendarBudget')
    av = cp['fact'] / 100
    unique = {str(x['id']): x for x in st['data']['transactions']}
    actual = [x for x in unique.values() if x.get('type') == 'expense'
              and x.get('fixed_id') is None and x.get('credit_id') is None
              and cp['start'] <= str(x.get('date'))[:10] < cp['end']
              and str(x.get('date'))[:10] <= st['options']['asof']]
    raw = sum(round(float(x['amount']) * 100) for x in actual) / 100
    print(f'      факт груп {fsum}, незалежний факт {raw}, actualVariable рушія {av}')
    check(abs(fsum - raw) <= 1 and abs(raw - av) <= .01,
          f'факт груп {fsum}, сирі змінні факти {raw}, рушій {av}')
    start = cp['start']
    food = lambda: num(page.locator('.bud-cat', has_text='Продукти').locator('.bud-value[data-label="Факт"]').inner_text())
    f0 = food()
    # фікстура: дві витрати на Продукти з fixed_id і credit_id не змінюють ні факт категорії, ні actualVariable
    seed_demo(page, DAY, [("TX_DEMO_ROWS=[", "TX_DEMO_ROWS=[[25,'FIXTEST',777,'out','mono',5411,'food'],[26,'CRTEST',555,'out','mono',5411,'food'],"),
                       ("description:r[1],amount:amt,", "description:r[1],fixed_id:r[1]==='FIXTEST'?'fx-test':null,credit_id:r[1]==='CRTEST'?'cr-test':null,amount:amt,")])
    go_tab(page, 1)
    expand_groups(page)
    st2 = finance_state(page)
    check(sum(1 for x in st2['data']['transactions'] if (x.get('fixed_id') == 'fx-test' or x.get('credit_id') == 'cr-test') and start <= x['date'][:10] <= DAY) == 2, 'фікстура fixed_id/credit_id не дійшла до входу поточного періоду')
    check(food() == f0, f'операції з fixed_id/credit_id потрапили у факт Продуктів: {f0} -> {food()}')
    check(page.evaluate('window.__calendarBudget.fact') / 100 == av, 'місячний бюджет зарахував fixed_id/credit_id')


def limit_abs(page):
    """Ліміт у ₴: зберігається (оптимістично), рушій дає категорії max(0, ліміт мінус факт), підсумок «розподілено X з T, вільно Y» сходиться."""
    freeze(page, DAY)
    before = _cur(page)
    t0 = sum(c['totalCents'] for c in before['categories'])
    page.locator('.bd-row', has_text='Продукти').click()
    page.wait_for_timeout(300)
    d = page.locator('.cat-drw')
    p0 = d.locator('#cat-lim-v').input_value()
    check(d.locator('.cat-lim-seg button[aria-pressed=true]').inner_text() == '%', 'вагова категорія відкрилась не в %')
    # частка в панелі = частка в аркуші «Розподіл» (там ціле)
    ws = sum(c['limit'] for c in page.evaluate("BCAT.filter(c=>!c.isIncome).map(c=>({limit:c.limit}))"))
    fl = page.evaluate("BCAT.find(c=>c.id==='food').limit")
    check(abs(float(p0) - fl / ws * 100) <= 0.05, f'частка Продуктів у панелі {p0}, очікували {fl / ws * 100:.2f}')
    d.locator('.cat-lim-seg button', has_text='₴').click()
    d.locator('#cat-lim-v').fill('5000')
    d.locator('.cat-lim-save').click()
    page.wait_for_timeout(400)
    check(d.locator('.cat-lim-err').count() == 0, 'помилка збереження ліміту')
    check(d.locator('.cat-lim-seg button[aria-pressed=true]').inner_text() == '₴', 'після збереження перемикач не на ₴')
    check(d.locator('#cat-lim-v').input_value() == '5000', 'поле не показує збережену суму')
    check(d.locator('.cat-lim-save').is_disabled(), 'кнопка збереження активна без змін')
    inp = finance_state(page)['data']['categories']
    food = next(c for c in inp if c['id'] == 'food')
    check(food['limit_abs'] == 5000, f'limit_abs у вході рушія {food.get("limit_abs")}')
    cur = _cur(page)
    fc = next(c for c in cur['categories'] if c['id'] == 'food')
    tl = finance_state(page)['data']['transactions']
    fact = sum(round(float(x['amount']) * 100) for x in tl if x.get('category_id') == 'food' and x.get('type') == 'expense' and not x.get('fixed_id') and not x.get('credit_id')
               and cur['start'] <= str(x.get('date', ''))[:10] <= DAY)
    want = max(0, 500000 - fact)
    print(f'      Продукти: ліміт 500000, факт {fact}, частка від завтра {fc["totalCents"]}, очікувано {want}')
    check(fc.get('limitAbsCents') == 500000 and fc['totalCents'] == min(want, t0), f'частка Продуктів {fc}, очікували {want}')
    tot = sum(c['totalCents'] for c in cur['categories'])
    free = sum(c['totalCents'] for c in cur['categories'] if c['id'] == 'unallocated')
    check(tot == t0, f'бюджет періоду змінився від ліміту: {t0} -> {tot}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(250)
    check(tot==t0 and free>=0,'forecast allocation conservation')
    # назад у %: limit_abs стає null
    page.locator('.bd-row', has_text='Продукти').click()
    page.wait_for_timeout(300)
    d.locator('.cat-lim-seg button', has_text='%').click()
    d.locator('#cat-lim-v').fill(p0)
    d.locator('.cat-lim-save').click()
    page.wait_for_timeout(400)
    food = next(c for c in finance_state(page)['data']['categories'] if c['id'] == 'food')
    check(food['limit_abs'] is None and abs(food['budget_limit'] - fl) / fl < 0.005, f'повернення до % не очистило limit_abs або вага далека від {fl}: {food}')
    a, b = [c['totalCents'] for c in _cur(page)['categories']], [c['totalCents'] for c in before['categories']]
    print(f'      після повернення до {p0}%: найбільше відхилення частки {max(abs(x - y) for x, y in zip(a, b))} коп. з {t0}')
    check(len(a) == len(b) and sum(a) == sum(b) and all(abs(x - y) <= t0 * 0.001 for x, y in zip(a, b)), 'повернення до тієї самої частки не відновило розподіл')


def cal_list(page):
    """Календар: список від початку поточного періоду до дня перед наступною зарплатою (06.11), щоденні витрати по обох періодах."""
    mob = page.viewport_size['width'] < 1024
    for day, lo, hi in ((DAY, '2026-10-06', '2026-11-05'), ('2026-11-03', '2026-10-21', '2026-11-05')):
        freeze(page, day)
        go_tab(page, 3)
        if mob:
            # телефон: список показується, коли не вибрано день (за замовчуванням вибрано сьогодні)
            if page.locator('.cal-tbl').count() == 0 and page.locator('.ck-day .ck-link').count():
                page.locator('.ck-day .ck-link').first.click()
                page.wait_for_timeout(200)
            if page.locator('.cal-tbl').count() == 0:
                # телефон: таблиці «Події і баланс» немає, є календар, «Події дня» і «Усі платежі місяця» (без балансу); п. 5 стосується таблиці ПК
                check(page.locator('details.cm-month').count() == 1, 'на телефоні немає «Усі платежі місяця»')
                print('      телефон: таблиці «Події і баланс» немає, є «Усі платежі місяця» (місяць, з кнопками оплати)')
                return
        rows = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev')].map(r=>({d:r.dataset.date,c:r.className,n:r.querySelector('.ce-n').textContent}))")
        ds = [r['d'] for r in rows]
        print(f'      {day}: рядків {len(rows)}, дати {ds[0]}..{ds[-1]}')
        check(ds[0] >= lo and ds[-1] == hi, f'{day}: список {ds[0]}..{ds[-1]}, очікували {lo}..{hi}')
        check(ds == sorted(ds), f'{day}: дати списку не за порядком')
        var = [r for r in rows if 'cal-ev-var' in r['c']]
        want = 2 if day == DAY else 1
        check(len(var) == want, f'{day}: рядків щоденних витрат {len(var)}, очікували {want}: {[r["n"] for r in var]}')
        check(var[-1]['n'].endswith('-05.11)'), f'{day}: останній рядок щоденних витрат не до 05.11: {var[-1]["n"]}')
        if day != DAY:
            check(any(r['d'] < '2026-11-01' and 'past' in r['c'] for r in rows), f'{day}: немає минулих днів періоду з жовтня')
            check(page.locator('.cal-tbl .pay-done').count() == page.locator('.cal-tbl .cal-ev[data-date^="2026-11"] .pay-done').count(), 'кнопка оплати на рядку іншого місяця')


CR = r"""(e)=>{const P=c=>c.match(/[\d.]+/g).map(Number);const L=c=>{const f=x=>{x/=255;return x<=0.04045?x/12.92:Math.pow((x+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
const bg=P(getComputedStyle(e).backgroundColor);const out=[];e.querySelectorAll('.bcard-sum,.bcard-bank,.bcard-badge,.bcard-avail,span').forEach(t=>{if(!t.childNodes.length||![...t.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))return;if(t.closest('.chip-due'))return;
let fg=P(getComputedStyle(t).color);const a=fg.length>3?fg[3]:1;let b=bg;const tb=P(getComputedStyle(t).backgroundColor);if(tb.length>3&&tb[3]>0)b=[0,1,2].map(i=>tb[i]*tb[3]+bg[i]*(1-tb[3]));fg=[0,1,2].map(i=>fg[i]*a+b[i]*(1-a));const x=L(fg),y=L(b);out.push(Math.round((Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)*100)/100)});return out}"""


def colors(page):
    """Градієнти карток за банком (обидві теми, контраст тексту від 4.5 на найсвітлішій зупинці), KPI на фоні картки (v155), градієнтні акцентна кнопка і активна вкладка."""
    freeze(page, DAY)
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>document.documentElement.setAttribute("data-theme",t)', theme)
        page.wait_for_timeout(200)
        cards = page.evaluate("""[...document.querySelectorAll('.dv-cards .bcard')].map(e=>{const s=getComputedStyle(e),probe=(p,v)=>{const d=document.createElement('div');d.style[p]=v;e.appendChild(d);const c=getComputedStyle(d)[p];d.remove();return c};return{c:[...e.classList].find(x=>x.startsWith('bk-')),bi:s.backgroundImage,sh:s.boxShadow,edge:s.borderTopColor,tokenOk:s.backgroundImage===probe('backgroundImage','var(--ov-bank-gradient)')&&s.backgroundColor===probe('backgroundColor','var(--ov-bank-base)')&&s.borderTopColor===probe('borderTopColor','var(--bank-edge)')}})""")
        check(len(cards) >= 3 and all(c['c'] and 'gradient' in c['bi'] and c['sh'] != 'none' for c in cards), f'{theme}: картки без градієнта за банком: {cards}')
        check(all(c['tokenOk'] for c in cards) and len({c['edge'] for c in cards}) == len({c['c'] for c in cards}), f'{theme}: bank surfaces or identity edges differ from desktop Overview roles: {cards}')
        ratios = [r for i in range(len(cards)) for r in page.locator('.dv-cards .bcard').nth(i).evaluate(CR)]
        print(f'      {theme}: контраст тексту карток мін. {min(ratios)}')
        check(min(ratios) >= 4.5, f'{theme}: контраст тексту на картці {min(ratios)} < 4.5')
        # v155, рішення власника «одна система» (v154) у палітрі Apple: KPI-плитки без кольорових підкладок, фон = токен картки (раніше тут вимагався градієнт)
        kpi = page.evaluate("(()=>{const d=document.createElement('div');d.style.background='var(--ov-raised)';return [...document.querySelectorAll('.p-overview.desk .dv-kpi')].filter(e=>e.offsetParent).map(e=>{e.closest('.p-overview').appendChild(d);const cc=getComputedStyle(d).backgroundColor;d.remove();const s=getComputedStyle(e);return {bi:s.backgroundImage,ok:s.backgroundColor===cc}})})()")
        check(kpi and all(k['bi'] == 'none' and k['ok'] for k in kpi), f'{theme}: KPI з кольоровою підкладкою або фоном не картки: {kpi}')
        action = page.evaluate("()=>{const e=document.querySelector('.overview-active .side-add'),s=getComputedStyle(e),d=document.createElement('div');d.style.background='var(--ov-accent)';e.appendChild(d);const expected=getComputedStyle(d).backgroundColor;d.remove();return {ok:s.backgroundColor===expected&&s.backgroundImage==='none',shadow:s.boxShadow}}")
        check(action['ok'] and action['shadow'] != 'none', f'{theme}: desktop primary action lost its accent surface role: {action}')
        active = page.evaluate("()=>{const e=document.querySelector('.overview-active .side-item[aria-current=page]'),s=getComputedStyle(e),d=document.createElement('div');d.style.background='var(--ov-accent)';e.appendChild(d);const expected=getComputedStyle(d).backgroundColor;d.remove();return {ok:s.boxShadow.includes(expected)&&s.boxShadow.includes('inset'),shadow:s.boxShadow}}")
        check(active['ok'] and active['shadow'] != 'none', f'{theme}: desktop active navigation lost its inset accent role: {active}')
        page.mouse.move(2, 2)
        shot(page, f'v144-overview-{theme}-1280.jpg', full=False)


def motion(page):
    """Поява блоків і докрут сум завершуються; при prefers-reduced-motion анімацій і докруту немає."""
    freeze(page, DAY)
    check(page.locator('[data-counting]').count() == 0, 'докрут сум не завершився')
    v1 = page.inner_text('.kpi-budget .dv-kpi-v')
    go_tab(page, 1)
    go_tab(page, 0)
    page.wait_for_timeout(50)
    check(page.locator('[data-counting]').count() == 0 and page.inner_text('.kpi-budget .dv-kpi-v') == v1, 'докрут повторився при поверненні на вкладку')
    page.emulate_media(reduced_motion='reduce')
    page.reload()
    page.wait_for_selector('.side', timeout=20000)
    page.wait_for_timeout(100)
    an = page.evaluate("[...document.querySelectorAll('.panel,.panel>*')].map(e=>getComputedStyle(e).animationName).filter(n=>n!=='none')")
    check(not an and page.locator('[data-counting]').count() == 0, f'reduced-motion: лишились анімації {an[:3]} або докрут')
    go_tab(page, 1)
    check(page.evaluate("[...document.querySelectorAll('.anim-rise')].every(e=>getComputedStyle(e).animationName==='none'&&getComputedStyle(e).opacity==='1')"), 'reduced-motion: групи Бюджету з анімацією')


CHECKS = [
    ('v144: панель категорії на ПК, Esc і фокус', 'desktop', drawer_desktop),
    ('v144: панель категорії знизу на телефоні', 'mobile', drawer_mobile),
    ('v144: групи Бюджету за макрокатегоріями', 'desktop', groups),
    ('v144: ліміт ₴ зберігається, підсумок з рушія', 'desktop', limit_abs),
    ('v144: Календар до дня перед зарплатою', 'desktop', cal_list),
    ('v144: Календар до дня перед зарплатою, телефон', 'mobile', cal_list),
    ('v144: кольори карток, KPI, акцентів у двох темах', 'desktop', colors),
    ('v144: плавність і reduced-motion', 'desktop', motion),
]
