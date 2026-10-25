"""Орієнтовні заощадження обмежують бюджет витрат, а рахунки змінює лише факт."""
from helpers import check, freeze, go_tab, num, shot

DAY = '2026-10-25'
ZERO_PLAN = {'2026-10-01': {'month_start': '2026-10-01', 'total_cents': 3100000,
                           'allocations': {'food': 2790000, 'savings': 0}, 'mandatory_items': []}}
SAVINGS_PLAN = {'2026-10-01': {**ZERO_PLAN['2026-10-01'],
                              'allocations': {'food': 2790000, 'savings': 310000}}}
EMPTY_EDITS = {'add': [], 'del': {}, 'acc': {}, 'fx': {}, 'cr': {}, 'due': {}, 'transfers': {}}


def wait_money(page, selector, cents):
    page.wait_for_function("""({selector,cents})=>{
      const el=document.querySelector(selector);
      return el && Math.round(Number(el.innerText.replace(/[^0-9,−-]/g,'').replace('−','-').replace(',','.'))*100)===cents;
    }""", arg={'selector': selector, 'cents': round(cents)})


def wait_plan(page, savings):
    page.wait_for_function("""savings=>__financeInput.monthly_budgets.length===1 &&
      __financeInput.monthly_budgets[0].allocations.savings===savings""", arg=savings)


def savings(page):
    page.emulate_media(reduced_motion='reduce')
    desktop = page.viewport_size['width'] >= 1024
    if desktop:
        page.set_viewport_size({'width': 1280, 'height': 720})
    freeze(page, DAY, patch=[
        ('const TX_DEMO_ROWS=[[', 'const TX_DEMO_ROWS=[];const SAVINGS_UNUSED_ROWS=[['),
        ('const[savingsLog,setSavingsLog]=useState([]);',
         'const[savingsLog,setSavingsLog]=useState([]);window.testSetMonthlyRows=setMonthlyRows;window.testSetSavings=setSavingsLog;window.testSavingsLog=savingsLog;'),
        ('const[demoEd,setDemoEd]=useState({add:[],del:{},acc:{},fx:{},cr:{},due:{},transfers:{}});',
         'const[demoEd,setDemoEd]=useState({add:[],del:{},acc:{},fx:{},cr:{},due:{},transfers:{}});window.testSetDemoEd=setDemoEd;'),
    ])
    check(page.evaluate('testSavingsLog.length===0 && __financeInput.transactions.length===0'), 'synthetic fixture is not empty')
    legacy = page.evaluate('({funds:kpiFunds(__financeProjection).total,daily:__periodBudget.daily})')
    page.evaluate('rows=>testSetMonthlyRows(rows)', ZERO_PLAN)
    wait_plan(page, 0)
    page.wait_for_function('__periodBudget.monthly===true')
    baseline = page.evaluate('({funds:kpiFunds(__financeProjection),period:__periodBudget})')
    wait_money(page, '.kpi-funds .dv-kpi-v', baseline['funds']['total'])
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'zero reserve occupies a row')

    # Орієнтовна ціль звужує бюджет витрат, але не списує фактичні кошти наперед.
    page.evaluate('rows=>testSetMonthlyRows(rows)', SAVINGS_PLAN)
    wait_plan(page, 310000)
    expected_funds = baseline['funds']['total']
    wait_money(page, '.kpi-funds .dv-kpi-v', expected_funds)
    check(page.evaluate('testSavingsLog.length') == 0, 'allocation generated a ledger contribution')
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'provisional goal deducted from actual funds')
    current = page.evaluate('__periodBudget')
    # 21.10–06.11: 11/31 жовтня + 5/30 листопада, точні prefix-копійки.
    reserve_slice = 310000 - 310000 * 20 // 31 + 310000 * 5 // 30
    expected_left = baseline['period']['avail'] - reserve_slice
    check(current['avail'] == expected_left, f'period still includes savings: {current["avail"]} vs {expected_left}')
    check(abs(current['daily'] - expected_left / 12) < 0.001, 'daily is not net remaining / days including today')
    check(current['daily'] < baseline['period']['daily'], 'allocation left daily unchanged')
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', current['daily'])
    wait_money(page, '.kpi-budget [data-r=avail] .kpi-rv', expected_left)
    for key in ('cash', 'cards', 'credit'):
        check(num(page.locator(f'.kpi-funds [data-r={key}] .kpi-rv').inner_text()) == baseline['funds'][key] / 100,
              f'{key}: allocation changed the original balance')
    check(page.evaluate('__financeInput.monthly_budgets[0].total_cents') == 3100000, 'gross envelope changed')
    page.locator('.kpi-funds .kpi-i').click()
    tip = page.locator('.kpi-tip[data-k=funds]')
    tip.wait_for(state='visible')
    check('План не віднімається від коштів на рахунках.' in tip.inner_text() and 'однією сумою' in tip.inner_text(), 'wrong provisional savings explanation')
    page.keyboard.press('Escape')
    tip.wait_for(state='hidden')
    near = page.locator('.dv-near' if desktop else '.o-next')
    check('Оренда' in near.inner_text(), 'daily savings displaced a real upcoming bill')
    check('У заощадження: Заощадження' not in near.inner_text(), 'internal savings schedule occupies the upcoming shortlist')
    check(page.evaluate("!__financeProjection.events.some(e=>e.id.startsWith('budget-savings:'))"), 'daily savings reserve remains in financial model')
    check(page.evaluate("(()=>{const es=__financeProjection.events,ss=es.filter(e=>e.id.startsWith('savings:'));return new Set(ss.map(e=>e.date)).size===ss.length&&ss.every(s=>es.some(e=>e.kind==='payout'&&e.date===s.date))})()"), 'forecast savings are not single payout lumps')
    shot(page, 'available-savings-desktop.jpg' if desktop else 'available-savings-mobile.jpg', full=True)
    if desktop:
        geometry = page.evaluate("""()=>({height:document.documentElement.scrollHeight,
          bottom:Math.max(...[...document.querySelectorAll('.p-overview.desk .surface')]
            .filter(e=>e.getClientRects().length).map(e=>e.getBoundingClientRect().bottom))})""")
        check(geometry['height'] <= 721 and geometry['bottom'] <= 721, f'1280x720: reserve causes overflow: {geometry}')

    # Зміна журналу не віднімає резерв повторно.
    projection = page.evaluate('JSON.stringify(__financeProjection)')
    page.evaluate('testSetSavings([{id:901,date:"2026-10-24",amount:250,currency:"UAH"}])')
    page.wait_for_function('testSavingsLog.length===1')
    check(page.evaluate('JSON.stringify(__financeProjection)') == projection, 'ledger changed projection')
    check(page.evaluate('__periodBudget.avail') == expected_left, 'ledger changed daily spending basis')
    wait_money(page, '.kpi-funds .dv-kpi-v', expected_funds)

    # Фактична витрата списує рахунок один раз; бюджетна ціль не списується вдруге.
    page.evaluate("""()=>testSetDemoEd({add:[{id:'fixture-saving',date:'2026-10-25',created_at:new Date().toISOString(),
      account_id:'l1',category_id:'savings',type:'expense',amount:1000,source:'manual',description:'Synthetic saving'}],
      del:{},acc:{},fx:{},cr:{},due:{},transfers:{}})""")
    page.wait_for_function('__financeProjection.snapshot.positiveOwnCents===1650000')
    reserve = page.evaluate("monthlySavingsReserve(__financeInput.monthly_budgets,__financeInput.categories,__financeInput.transactions,'2026-10-25')")
    check(reserve['reserveCents'] == 0 and reserve['plannedCents'] == 310000 and reserve['factCents'] == 100000, 'provisional goal, actual saving and cash reserve conflated')
    wait_money(page, '.kpi-funds .dv-kpi-v', expected_funds - 100000)
    check(page.evaluate('__periodBudget.avail') == expected_left, 'actual saving deducted twice from spending budget')
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', current['daily'])

    # Минула дата виключає пізніший факт; майбутня враховує вже профінансований прогноз.
    page.get_by_role('button', name='Попередній період', exact=True).click()
    page.locator('.ov-per').wait_for(state='visible')
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'past view deducts provisional goal')
    page.get_by_role('button', name='Наступний період', exact=True).click()
    page.locator('.ov-per').wait_for(state='detached')
    page.get_by_role('button', name='Наступний період', exact=True).click()
    page.locator('.ov-per').wait_for(state='visible')
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'future view deducts provisional goal again')
    check(page.evaluate('__budgetView.plan') == 1302000, 'future budget includes savings')
    check('У заощадження: Заощадження' not in near.inner_text(), 'future payment shortlist exposes the internal savings schedule')
    page.get_by_role('button', name='До поточного', exact=True).click()
    page.locator('.ov-per').wait_for(state='detached')

    go_tab(page, 1)
    check(page.evaluate('__calendarBudget.plan') == 3100000, 'calendar editor lost gross allocation')
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    editor = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    check(editor.get_by_role('textbox', name='Заощадження, ₴', exact=True).count() == 0, 'savings still manually distributed')
    check(page.evaluate('__financeProjection.snapshot.creditDebtCents') >= 310000, 'fixture no longer has debt exceeding its provisional surplus')
    check(editor.locator('[data-auto-savings] output').get_attribute('data-cents') == '0', 'editor allocates savings before covering card debt')
    check(editor.get_by_role('textbox', name='Продукти, ₴', exact=True).input_value() == '27900', 'ordinary allocation changed')
    page.keyboard.press('Escape')
    go_tab(page, 0)

    page.evaluate('edits=>testSetDemoEd(edits)', EMPTY_EDITS)
    page.evaluate('testSetSavings([]);testSetMonthlyRows({})')
    page.wait_for_function('__financeInput.monthly_budgets.length===0 && __financeInput.transactions.length===0 && testSavingsLog.length===0')
    wait_money(page, '.kpi-funds .dv-kpi-v', legacy['funds'])
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'absent plan left a reserve row')
    check(abs(page.evaluate('__periodBudget.daily') - legacy['daily']) < 0.001, 'absent plan changed legacy daily')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'reserve widened page')


CHECKS = [
    ('Provisional savings leave actual funds intact and protect daily budget on desktop', 'desktop', savings),
    ('Provisional savings leave actual funds intact and protect daily budget on mobile', 'mobile', savings),
]
