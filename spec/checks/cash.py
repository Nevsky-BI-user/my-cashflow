# v139 (DESIGN.md п. 12, каса по датах): Огляд з блоком «Баланс» і KPI «Залишок до виплати», Потік «сума, баланс після» з сірим прогнозом,
# картка кредитного рахунку (мінус борг, доступно, закрити до 24.MM), режим «Календарний місяць» з памʼяттю в localStorage,
# жодного «до 25.MM» в інтерфейсі. Числа звіряються з еталоном scripts/budget_pool.py (допуск 1 ₴).
import re
from datetime import date, timedelta

from helpers import check, freeze, go_tab, num, open_payout, pool_ref, shot

DAY = '2026-10-08'
MON = {'СІЧНЯ': 1, 'ЛЮТОГО': 2, 'БЕРЕЗНЯ': 3, 'КВІТНЯ': 4, 'ТРАВНЯ': 5, 'ЧЕРВНЯ': 6, 'ЛИПНЯ': 7, 'СЕРПНЯ': 8, 'ВЕРЕСНЯ': 9,
       'ЖОВТНЯ': 10, 'ЛИСТОПАДА': 11, 'ГРУДНЯ': 12}


def _ref(page):
    snap = page.evaluate('window.__cashSnap()')
    d, _ = open_payout(date.fromisoformat(DAY))
    return pool_ref(snap, str(d - timedelta(days=1)), DAY)


def money(text):
    """'−54 940,43 ₴' -> -54940.43 (останнє число в тексті, кома як десятковий роздільник)."""
    m = re.findall(r'[−-]?\d[\d \u00a0]*(?:,\d+)?', text)
    check(m, f'немає числа в {text!r}')
    t = m[-1].replace('\u00a0', '').replace(' ', '').replace(',', '.')
    return -float(t[1:]) if t[0] in '−-' else float(t)


def _bal_at(ref, iso):
    """Каса на кінець дня iso за еталоном: баланс останньої події не пізніше дати, інакше стартова каса."""
    b = ref['startCash']
    for e in ref['timeline']:
        if e['date'] <= iso:
            b = e['balance']
    return b


def overview(page):
    """Огляд 1920x1080: KPI «Залишок до виплати» = каса напередодні виплати, блок «Баланс» (власні, борг до 24.MM, доступно, розстрочки, нетто);
    сторінка не довша за екран"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 0)
    k = page.locator('.dv-kpi.dv-cash')
    check(k.count() == 1, 'на Огляді немає KPI «Залишок до виплати»')
    kt = k.inner_text()
    print(f'      KPI: {kt!r}; еталон cashBeforePayout {ref["cashBeforePayout"]:.2f} ({ref["daysToPayout"]} дн.), до зарплати {ref["cashBeforeSalary"]}')
    check('залишок до виплати' in kt.lower(), f'підпис KPI: {kt!r}')
    v = num(page.inner_text('.dv-kpi.dv-cash .dv-kpi-v'))
    check(abs(v - ref['cashBeforePayout']) <= 1, f'KPI {v}, еталон {ref["cashBeforePayout"]:.2f}')
    check(f'{ref["daysToPayout"]} дн.' in kt and 'до зарплати' in kt, f'KPI без днів або рядка «до зарплати»: {kt!r}')
    check(page.locator('.dv-kpi').count() == 4, f'KPI {page.locator(".dv-kpi").count()}, а не 4')
    bal = page.evaluate("Object.fromEntries([...document.querySelectorAll('.dv-bal [data-b]')].map(e=>[e.dataset.b,e.innerText]))")
    print(f'      Баланс: {bal}')
    for key in ('own', 'debt', 'avail', 'rem', 'net'):
        check(key in bal, f'у блоці «Баланс» немає {key}')
    own, debt = num(bal['own']), num(bal['debt'].split('\n')[-1])
    check(abs(own - (ref['ownDebit'] + ref['unassigned'])) <= 1, f'власні {own}, еталон {ref["ownDebit"] + ref["unassigned"]:.2f}')
    check(abs(abs(debt) - ref['debt']) <= 1, f'борг {debt}, еталон {ref["debt"]:.2f}')
    check(ref['debt'] <= 0 or 'до 24.' in bal['debt'], f'борг без «до 24.MM»: {bal["debt"]!r}')
    rem = money(bal['rem'])
    net = money(bal['net'])
    print(f'      нетто {net} = власні {own} - борг {abs(debt)} - розстрочки {abs(rem)} -> {own - abs(debt) - abs(rem)}')
    check(abs(net - (own - abs(debt) - abs(rem))) <= 2, f'нетто {net} != власні {own} - борг {abs(debt)} - розстрочки {abs(rem)}')
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 1080, f'Огляд на 1920x1080 довший за екран: {sh}')
    page.mouse.move(2, 2)
    shot(page, 'v139-ov-1920.jpg', full=False)


def overview_mobile(page):
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 0)
    b = page.locator('.p-overview .o-bal')
    check(b.count() == 1, 'на телефоні немає блоку «Баланс»')
    order = page.evaluate("[...document.querySelector('.p-overview').children].map(e=>String(e.className))")
    ia = next((i for i, c in enumerate(order) if 'o-accs' in c), -1)
    ib = next((i for i, c in enumerate(order) if 'o-bal' in c), -1)
    check(ia >= 0 and ib == ia + 1, f'«Баланс» не одразу після рахунків: {order}')
    cash = page.inner_text('.o-bal [data-b="cash"]')
    print(f'      телефон: {cash!r}')
    check('Залишок до виплати' in cash, f'рядок каси: {cash!r}')
    v = num(page.inner_text('.o-bal [data-b="cash"] .bal-v'))
    check(abs(v - ref['cashBeforePayout']) <= 1, f'каса до виплати {cash!r}, еталон {ref["cashBeforePayout"]:.2f}')
    page.mouse.move(2, 2)
    shot(page, 'v139-ov-375.jpg')


FLOW_ROWS = """[...document.querySelectorAll('.p-flow.desk .flow-row.row-plan.future')].map(r=>{let p=r.previousElementSibling;
while(p&&!p.classList.contains('flow-day'))p=p.previousElementSibling;const b=r.querySelector('.flow-bal');
return {day:p?p.innerText.split(String.fromCharCode(10))[0]:'',bal:b.innerText,cls:b.className,clr:getComputedStyle(b).color}})"""


def flow(page):
    """Потік 1920: колонка «Сума», потім «Баланс після»; майбутні планові рядки: сірий «прогноз X» = каса на кінець дня за еталоном"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 2)
    hd = [x.strip().upper() for x in page.inner_text('.p-flow.desk .flow-head').split('\n') if x.strip()]
    check('СУМА' in hd and 'БАЛАНС ПІСЛЯ' in hd and hd.index('СУМА') + 1 == hd.index('БАЛАНС ПІСЛЯ'), f'порядок колонок: {hd}')
    rows = page.evaluate(FLOW_ROWS)
    check(rows, 'у Потоці немає майбутніх планових рядків')
    tx = page.evaluate("(()=>{const b=document.querySelector('.p-flow.desk .flow-row.tx .flow-bal');return b?getComputedStyle(b).color:null})()")
    n = 0
    for r in rows:
        check('fc' in r['cls'], f'плановий рядок без класу прогнозу: {r}')
        check(tx is None or r['clr'] != tx, f'прогноз не сірий: {r["clr"]} як у факту')
        if r['bal'].startswith('прогноз'):
            m = re.match(r'(\d+) ([^\s,]+)', r['day'].upper())
            check(m and m.group(2) in MON, f'не розібрано дату дня: {r["day"]!r}')
            iso = f'{date.fromisoformat(DAY).year}-{MON[m.group(2)]:02d}-{int(m.group(1)):02d}'
            want = _bal_at(ref, iso)
            check(abs(num(r['bal']) - want) <= 1, f'{iso}: {r["bal"]!r}, еталон каси на кінець дня {want:.2f}')
            n += 1
        else:
            check(r['bal'] == 'план', f'плановий рядок: {r["bal"]!r}')
    print(f'      прогнозів у Потоці звірено з еталоном: {n} з {len(rows)}')
    check(n >= 3, f'звірено лише {n} прогнозів')
    page.mouse.move(2, 2)
    shot(page, 'v139-flow-1920.jpg', full=False)


def credit_card(page):
    """Картка кредитного рахунку: мінус борг, «доступно X ₴» (ліміт мінус борг) або «ліміт не задано», «закрити до 24.MM»"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    accs = page.evaluate("ACCOUNTS_DEMO.filter(a=>a.kind==='credit').map(a=>({name:a.name,debt:Number(a.debt)||0,lim:Number(a.credit_limit)||0}))")
    check(accs, 'у демо немає кредитного рахунку')
    go_tab(page, 0)
    for a in accs:
        card = page.locator('.dv-cards .bcard', has_text=a['name']).first
        t = card.inner_text()
        print(f'      {a}: {t!r}')
        if a['debt'] > 0:
            heads = [x for x in t.split('\n') if x.strip().startswith('−')]
            check(heads and abs(num(heads[0]) + a['debt']) <= 1, f'картка без мінус боргу: {t!r}')
            check('закрити до 24.' in t, f'картка без «закрити до 24.MM»: {t!r}')
        av = card.locator('.bcard-avail').inner_text()
        if a['lim'] > 0:
            check(abs(num(av) - (a['lim'] - a['debt'])) <= 1, f'доступно {av!r}, очікували {a["lim"] - a["debt"]}')
        else:
            check(av == 'ліміт не задано', f'без ліміту: {av!r}')
    check('до 25.' not in page.inner_text('.dv-cards'), 'на картках лишилось «до 25»')


def no_25(page):
    """Жодного «до 25.MM» на пʼяти вкладках ПК (п. 12: борг гаситься 24-го)"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    for i in range(5):
        go_tab(page, i)
        t = page.inner_text('.content')
        hit = re.findall(r'.{0,30}до 25\.\d\d.{0,10}', t)
        check(not hit, f'вкладка {i}: {hit}')


def month_mode(page):
    """Режим «Календарний місяць»: перемикач у шторці періоду, памʼять у localStorage після перезавантаження,
    Бюджет місяця = сума бюджетів періодів з виплатою в місяці (зарплата 06.10 = поточний, аванс 21.10 = наступний), Потік за місяць"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 1)
    page.click('.side-pname')
    page.wait_for_timeout(250)
    sw = page.locator('.per-mode button', has_text='Календарний місяць')
    check(sw.count() == 1, 'у шторці періоду немає перемикача «Календарний місяць»')
    sw.click()
    page.wait_for_timeout(200)
    check(page.evaluate("localStorage.getItem('per_mode')") == 'month', 'режим не збережено в localStorage')
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)
    page.reload()
    page.wait_for_selector('.side', timeout=20000)
    page.wait_for_timeout(400)
    go_tab(page, 1)
    check('Жовтень' in page.inner_text('.side-pname'), f'після перезавантаження не місяць: {page.inner_text(".side-pname")!r}')
    note = page.inner_text('.bud-month')
    parts = re.findall(r'(зарплата|аванс) (\d\d\.\d\d) ([\d  ]+) ₴', note)
    print(f'      {note!r}')
    check(len(parts) == 2, f'у примітці не два періоди: {parts}')
    got = {k: int(re.sub(r'\D', '', v)) for k, _, v in parts}
    want = {'зарплата': ref['varPoolCur'], 'аванс': ref['varPoolNext']}
    for k in want:
        check(abs(got[k] - want[k]) <= 1, f'{k}: {got[k]}, еталон {want[k]:.2f}')
    pool = round(ref['varPoolCur'] + ref['varPoolNext'], 2)
    bt = page.inner_text('.content')
    check('бюджет місяця' in bt.lower(), 'немає підпису «Бюджет місяця»')
    shown = [num(x) for x in re.findall(r'\d[\d  ]{2,} ₴', bt)]
    check(any(abs(x - pool) <= 1 for x in shown), f'на екрані немає суми бюджету місяця {pool:.2f}')
    print(f'      бюджет місяця {pool:.2f} = {ref["varPoolCur"]:.2f} + {ref["varPoolNext"]:.2f}')
    page.mouse.move(2, 2)
    shot(page, 'v139-budget-month-1920.jpg', full=False)
    go_tab(page, 2)
    on = page.evaluate("[...document.querySelectorAll('.flow-scope button')].filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.textContent)")
    check(on == ['Місяць'], f'Потік у режимі місяця: {on}')
    go_tab(page, 0)
    check('бюджет місяця' in page.inner_text('.content').lower(), 'на Огляді немає «Бюджет місяця»')
    page.click('.side-pname')
    page.wait_for_timeout(250)
    page.locator('.per-mode button', has_text='Між виплатами').click()
    page.wait_for_timeout(200)
    check(page.evaluate("localStorage.getItem('per_mode')") == 'period', 'повернення в режим періоду не збережено')


CHECKS = [
    ('Огляд: «Залишок до виплати» і блок «Баланс» за еталоном, 1920x1080 без прокрутки', 'desktop', overview),
    ('Огляд на телефоні: блок «Баланс» після рахунків', 'mobile', overview_mobile),
    ('Потік: «Сума», потім «Баланс після», сірий прогноз за еталоном', 'desktop', flow),
    ('Картка кредитки: мінус борг, доступно, закрити до 24-го', 'desktop', credit_card),
    ('Жодного «до 25.MM» на вкладках', 'desktop', no_25),
    ('Режим «Календарний місяць»: localStorage, бюджет місяця = сума періодів', 'desktop', month_mode),
]
