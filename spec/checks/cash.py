# v139 (DESIGN.md п. 12, каса по датах), v145: Огляд з плиткою «Баланс» (власні мінус борг карток), Потік «сума, каса після» з сірим прогнозом,
# картка кредитного рахунку (мінус борг, доступно, закрити до DD.MM за правилом repayDate), режим «Календарний місяць» з памʼяттю в localStorage,
# жодного «до 25.MM» в інтерфейсі. Числа звіряються з еталоном scripts/budget_pool.py (допуск 1 ₴).
import re
from datetime import date, timedelta

from helpers import check, finance_ref, freeze, go_tab, num, open_payout, pool_ref, shot

DAY = '2026-10-08'
MON = {'СІЧНЯ': 1, 'ЛЮТОГО': 2, 'БЕРЕЗНЯ': 3, 'КВІТНЯ': 4, 'ТРАВНЯ': 5, 'ЧЕРВНЯ': 6, 'ЛИПНЯ': 7, 'СЕРПНЯ': 8, 'ВЕРЕСНЯ': 9,
       'ЖОВТНЯ': 10, 'ЛИСТОПАДА': 11, 'ГРУДНЯ': 12}


def _ref(page):
    r = finance_ref(page)
    n = r['nextPlan']; c = r['currentPeriod']; snap = r['snapshot']
    before = [d for d in r['days'] if d['date'] < n['start']][-1]
    return dict(r, startCash=snap['cashCents']/100, cashBeforePayout=before['closingCashCents']/100,
                ownDebit=snap['positiveOwnCents']/100, unassigned=snap['unassignedAdjustmentCents']/100,
                debt=snap['creditDebtCents']/100, varPoolCur=c['targetCents']/100, varPoolNext=n['targetCents']/100)


def money(text):
    """'−54 940,43 ₴' -> -54940.43 (останнє число в тексті, кома як десятковий роздільник)."""
    m = re.findall(r'[−-]?\d[\d \u00a0]*(?:,\d+)?', text)
    check(m, f'немає числа в {text!r}')
    t = m[-1].replace('\u00a0', '').replace(' ', '').replace(',', '.')
    return -float(t[1:]) if t[0] in '−-' else float(t)


def _bal_at(ref, iso):
    """v149: баланс на кінець дня iso за еталоном (власні мінус борг): netCents дня плюс зсув positiveOwn − cash; до першого дня: баланс сьогодні."""
    rows = [d for d in ref['days'] if d['date'] <= iso]
    sh = ref['snapshot']['positiveOwnCents'] - ref['snapshot']['cashCents']
    return (rows[-1]['netCents'] + sh)/100 if rows else (ref['snapshot']['positiveOwnCents'] - ref['snapshot']['creditDebtCents'])/100


def _kpi_balance(page, ref):
    """v145: плитка «Баланс» = власні мінус борг кредитних карток (як у боті), рядки «Власні» і «Мінусові», червона при мінусі."""
    t = page.locator('.kpi-balance')
    check(t.count() == 1, 'немає плитки «Баланс»')
    val = num(t.locator('.dv-kpi-v').inner_text())
    want = ref['ownDebit'] - ref['debt']
    own = num(t.locator('[data-r=own] .kpi-rv').inner_text())
    minus = num(t.locator('[data-r=minus] .kpi-rv').inner_text())
    print(f'      Баланс {val} = власні {own} - борг {abs(minus)}; еталон {want:.2f}')
    check(abs(val - want) <= 1, f'Баланс {val}, еталон власні {ref["ownDebit"]:.2f} - борг {ref["debt"]:.2f} = {want:.2f}')
    check(abs(own - ref['ownDebit']) <= 1 and abs(abs(minus) - ref['debt']) <= 1, f'рядки плитки: власні {own}, мінусові {minus}')
    red = t.locator('.dv-kpi-v').evaluate("e=>e.style.color")
    check((want < 0) == ('red' in red), f'колір Балансу {red!r} при {want:.2f}')


def overview(page):
    """Огляд 1920x1080 (v145): чотири плитки KPI, «Баланс» = власні мінус борг карток за еталоном; сторінка не довша за екран"""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 0)
    tiles = page.evaluate("[...document.querySelectorAll('.dv-kpis .kpi-t')].map(e=>e.dataset.k)")
    check(tiles == ['funds', 'budget', 'balance'], f'головні плитки KPI: {tiles}')
    installments = page.locator('.ov-grid > .kpi-t.kpi-inst')
    check(installments.count() == 1 and installments.is_visible(), 'окрема картка розстрочок відсутня або прихована')
    _kpi_balance(page, ref)
    check(page.locator('.dv-bal,.o-bal').count() == 0, 'лишився прибраний блок «Баланс»')
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 1080, f'Огляд на 1920x1080 довший за екран: {sh}')
    page.mouse.move(2, 2)
    shot(page, 'v139-ov-1920.jpg', full=False)


def overview_mobile(page):
    """Телефон (v145): ті самі чотири плитки на початку Огляду, «Баланс» за еталоном, блоку «Баланс» немає"""
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 0)
    order = page.evaluate("[...document.querySelector('.p-overview').children].map(e=>String(e.className))")
    check(order and 'projection-summary' in order[0], f'плитки KPI не першим блоком: {order}')
    tiles = page.evaluate("[...document.querySelectorAll('.p-overview .projection-summary .kpi-t')].map(e=>e.dataset.k)")
    check(tiles == ['funds', 'budget', 'balance', 'inst'], f'плитки KPI на телефоні: {tiles}')
    _kpi_balance(page, ref)
    check(page.locator('.o-bal').count() == 0, 'на телефоні лишився прибраний блок «Баланс»')
    page.mouse.move(2, 2)
    shot(page, 'v139-ov-375.jpg')


FLOW_ROWS = """[...document.querySelectorAll('.p-flow.desk .flow-row.row-plan.future')].map(r=>{let p=r.previousElementSibling;
while(p&&!p.classList.contains('flow-day'))p=p.previousElementSibling;const b=r.querySelector('.flow-bal');
return {day:p?p.innerText.split(String.fromCharCode(10))[0]:'',bal:b.innerText,cls:b.className,clr:getComputedStyle(b).color}})"""


def flow(page):
    """Потік 1920: колонка «Сума», потім «Баланс після» (v149) (v145: «баланс» лише власні мінус борг); майбутні планові рядки: сірий «прогноз X» = каса на кінець дня за еталоном"""
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
            check(abs(num(r['bal']) - want) <= 1, f'{iso}: {r["bal"]!r}, еталон балансу на кінець дня {want:.2f}')
            n += 1
        else:
            check(r['bal'] == 'план', f'плановий рядок: {r["bal"]!r}')
    print(f'      прогнозів у Потоці звірено з еталоном: {n} з {len(rows)}')
    check(n >= 3, f'звірено лише {n} прогнозів')
    page.mouse.move(2, 2)
    shot(page, 'v139-flow-1920.jpg', full=False)


def credit_card(page):
    """Картка кредитного рахунку: мінус борг, «доступно X ₴» (ліміт мінус борг) або «ліміт не задано»,
    «закрити до DD.MM» з датою за спільним правилом repayDate (v147: виплата 21-го наступного місяця)"""
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
            want = page.evaluate("n=>{const a=ACCOUNTS_DEMO.find(x=>x.name===n);const q=debtDue(a,new Date());return q?pbDm(q.date):''}", a['name'])
            check(want and want[:2] in ('20', '21', '22') and ('план погашення ' + want) in t, f'картка без «план погашення {want}» (v149): {t!r}')
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
    Огляд агрегує факт і майбутні дні; окремий Бюджет має власний збережений план місяця."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    ref = _ref(page)
    go_tab(page, 0)
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
    go_tab(page, 0)
    check('Жовтень' in page.inner_text('.side-pname'), f'після перезавантаження не місяць: {page.inner_text(".side-pname")!r}')
    projection=finance_ref(page)
    inp=page.evaluate('window.__financeInput')
    planned=sum(d['variableCents'] for d in projection['days'] if d['date'].startswith('2026-10'))
    actual=sum(round(t['amount']*100) for t in inp['transactions'] if t['type']=='expense' and not t.get('fixed_id') and not t.get('credit_id') and '2026-10-01'<=t['date']<=DAY)
    pool=(planned+actual)/100
    from checks.v157 import _snap, _bud_card
    fact_ui,plan_ui=_bud_card(_snap(page),'desktop')
    check(plan_ui is not None and abs(plan_ui-pool)<=1 and abs(fact_ui-actual/100)<=1, 'місячна картка Огляду не дорівнює факту + майбутнім дням')
    go_tab(page,1)
    check(page.locator('.p-budget').get_attribute('data-month')=='2026-10-01','Бюджет не на календарному місяці')
    from checks.budget_period_parity import assert_unsaved_salary
    assert_unsaved_salary(page)
    check(abs(num(page.locator('.bud-spent .bud-kpi-v').inner_text())-actual/100)<.01,'Бюджет показує не місячний факт')
    page.click('.side-pname')
    check(page.locator('.per-mode').count()==0,'Бюджет дозволяє перейти на період виплат')
    page.keyboard.press('Escape')
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
    ('Огляд: плитки KPI, «Баланс» за еталоном, 1920x1080', 'desktop', overview),
    ('Огляд на телефоні: плитки KPI, «Баланс» за еталоном', 'mobile', overview_mobile),
    ('Потік: «Сума», потім «Баланс після», сірий прогноз за еталоном', 'desktop', flow),
    ('Картка кредитки: мінус борг, доступно, закрити до дати погашення', 'desktop', credit_card),
    ('Жодного «до 25.MM» на вкладках', 'desktop', no_25),
    ('Режим «Календарний місяць»: localStorage, факт + план днів місяця', 'desktop', month_mode),
]
