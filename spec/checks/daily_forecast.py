"""План на день та прогнозні щоденні витрати мають одну суму й живе оновлення."""
import copy
import json

from helpers import ROOT, check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_money, wait_transactions, replace_transactions

DAY = '2026-10-29'


def daily_forecast(page):
    page.emulate_media(reduced_motion='reduce')
    data = json.loads((ROOT / 'spec' / 'fixtures' / 'daily-forecast.json').read_text(encoding='utf-8'))
    setup = {'accounts': data['accounts'], 'categories': data['categories'],
             'category_groups': [{'id': 1, 'name': 'Побут', 'sort_order': 0}],
             'salary_config': [{'id': 1, **data['salary']}], 'monthly_budgets': data['monthly_budgets'],
             'transactions': data['transactions'], 'fixed_payments': [], 'credits': [], 'goals': []}
    assignments = ''.join('m.data.' + key + '=' + json.dumps(value, ensure_ascii=False) + ';' for key, value in setup.items())
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};'))
    freeze(page, DAY, patch=[('if(!sb){window.__financeProjection=', '{window.__financeProjection='),
                            ('if(!sb)window.__periodBudget=', 'window.__periodBudget=')])
    wait_transactions(page, data['transactions'])
    go_tab(page, 0)

    def verify(remaining, label):
        page.wait_for_function('value=>window.__financeProjection&&__financeProjection.currentPeriod.spendableRemainingCents===value', arg=remaining)
        updated(page)
        # Картка Огляду використовує ту саму поточну добу у знаменнику.
        wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', remaining / 8)
        result = page.evaluate("""()=>{const p=__financeProjection,c=p.currentPeriod;return {daily:c.dailyCents,
          plan:c.futureSchedule.map(d=>d.spendCents),sum:c.futureSchedule.reduce((s,d)=>s+d.spendCents,0),
          today:p.events.filter(e=>e.kind==='variable'&&e.date==='2026-10-29').length,
          closing:p.days[0].closingCashCents,snapshot:p.snapshot.positiveOwnCents,
          selected:p.events.filter(e=>e.kind==='variable'&&e.date==='2026-11-02').reduce((s,e)=>s+e.amountCents,0)}}""")
        check(result['sum'] == remaining and all(abs(n - result['daily']) < 1 for n in result['plan']), 'графік не збігається з денним планом')
        check(result['today'] == 0 and result['closing'] == result['snapshot'], 'план змінив фактичний баланс сьогодні')
        plot = page.locator('.dv-fc .fc-plot')
        plot.scroll_into_view_if_needed()
        plot.focus()
        page.keyboard.press('Escape')
        for _ in range(4):
            page.keyboard.press('ArrowRight')
        box = page.locator('.dv-fc .fc-box')
        check('02.11' in box.inner_text(), 'підказка не відкрила 2 листопада')
        row = box.locator('.fc-tip-r').filter(has_text='Щоденні витрати').first
        check(row.count() == 1, 'у підказці немає щоденних витрат')
        shown = page.evaluate("n=>new Intl.NumberFormat('uk-UA',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n/100)", result['selected'])
        check(shown in row.inner_text(), f'підказка округлила щоденний план: {row.inner_text()} замість {shown}')
        shot(page, 'daily-forecast-' + label + '-' + str(page.viewport_size['width']) + '.jpg', full=False)

    verify(205542, 'initial')
    rows = copy.deepcopy(data['transactions'])
    rows.append({**rows[0], 'id': 2, 'amount': 80, 'date': DAY, 'created_at': DAY + 'T10:00:00Z'})
    replace_transactions(page, rows)
    verify(197542, 'expense')
    budgets = copy.deepcopy(data['monthly_budgets'])
    budgets[1]['total_cents'] += 60000
    budgets[1]['allocations']['food'] += 60000
    page.evaluate("rows=>{__liveMock.data.monthly_budgets=rows;__liveMock.event('monthly_budgets')}", budgets)
    verify(207542, 'budget')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'графік розширив сторінку')


CHECKS = [('Прогноз щодня дорівнює плану та реагує на витрату й бюджет', 'desktop', daily_forecast),
          ('Прогноз телефон: точна сума в підказці та живе оновлення', 'mobile', daily_forecast)]
