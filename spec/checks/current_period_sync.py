"""Current period cap reconciles monthly slices without changing account facts."""
import json
from helpers import ROOT, check, freeze, go_tab, num, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_transactions, wait_money


def assert_cap(page):
    expected = page.evaluate('''()=>{const p=__financeProjection,c=p.currentPeriod,r=c.reconciliation,f=kpiFunds(p,0);return {r,capacity:f.total,available:Math.min(f.total,r.availableCents),daily:Math.round(c.dailyCents),schedule:c.futureSchedule.reduce((s,d)=>s+d.spendCents,0),next:p.nextPlan.spendableTargetCents}}''')
    r = expected['r']
    check(r['plannedCents'] - r['actualCents'] - r['adjustmentCents'] == r['signedRemainingCents'], 'canonical equation is not exact')
    wait_money(page, '.kpi-funds .dv-kpi-v', expected['available'])
    wait_money(page, '.kpi-funds [data-r=capacity] .kpi-rv', expected['capacity'])
    wait_money(page, '.kpi-funds [data-r=plan] .kpi-rv', r['availableCents'])
    wait_money(page, '.kpi-budget [data-r=avail] .kpi-rv', abs(r['signedRemainingCents']))
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', expected['daily'])
    parts = page.locator('[data-period-equation] [data-period-part]').evaluate_all("es=>Object.fromEntries(es.map(e=>[e.dataset.periodPart,Number(e.dataset.cents)]))")
    check(parts == dict(plan=r['plannedCents'], fact=r['actualCents'], adjustment=r['adjustmentCents'], remaining=r['signedRemainingCents']), 'visible equation differs from canonical values')
    check(page.locator('.period-reconciliation').is_visible(), 'reconciliation hidden')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'page overflows horizontally')
    return expected


def scenario(page, day):
    page.emulate_media(reduced_motion='reduce')
    data = json.loads((ROOT / 'spec/fixtures/daily-forecast.json').read_text(encoding='utf-8'))
    # Synthetic deficit across Oct 21-Nov 6; November retains positive budget.
    data['transactions'][0]['amount'] = 15000
    data['transactions'].append(dict(data['transactions'][0], id=2, amount=35000, date='2026-10-10', created_at='2026-10-10T12:00:00Z'))
    data['accounts'][0]['balance'] = 5000
    data['accounts'].append(dict(id=2, name='Synthetic credit', kind='credit', bank='other', balance=0, debt=1000, credit_limit=40000, active=True))
    setup = dict(accounts=data['accounts'], categories=data['categories'],
                 category_groups=[dict(id=1, name='Synthetic group', sort_order=0)],
                 salary_config=[dict(id=1, **data['salary'])], monthly_budgets=data['monthly_budgets'],
                 transactions=data['transactions'], fixed_payments=[], credits=[], goals=[])
    assignments = ''.join('m.data.' + k + '=' + json.dumps(v, ensure_ascii=False) + ';' for k, v in setup.items())
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};'))
    freeze(page, day, patch=[('if(!sb){window.__financeProjection=', '{window.__financeProjection=')])
    wait_transactions(page, data['transactions'])
    go_tab(page, 0)
    first = assert_cap(page)
    check(first['r'] == dict(plannedCents=2298000, actualCents=1500000, adjustmentCents=1500000, signedRemainingCents=-702000, availableCents=0, overrunCents=702000), 'independent month-slice equation: 11000+11980-15000-15000=-7020')
    check(first['available'] == first['daily'] == first['schedule'] == 0, 'deficit must give zero available/daily/forecast')
    check(first['r']['adjustmentCents'] > 0 and first['r']['actualCents'] < first['r']['plannedCents'], 'fixture must show below-plan facts with a monthly adjustment')
    check(first['capacity'] > 0 and first['next'] > 0, 'fixture must distinguish physical and future money')
    shot(page, 'current-period-sync-' + day + '-' + str(page.viewport_size['width']) + '.jpg', full=True)
    # Monthly settings and then a receipt arriving on the same document.
    page.evaluate("()=>{const b=__liveMock.data.monthly_budgets[1];b.total_cents=18000000;b.allocations.food=18000000;__liveMock.event('monthly_budgets')}")
    page.wait_for_function('__financeInput.monthly_budgets[1].total_cents===18000000')
    updated(page)
    changed = assert_cap(page)
    check(changed['r']['plannedCents'] != first['r']['plannedCents'], 'monthly settings did not update current period')
    rows = data['transactions'] + [dict(data['transactions'][0], id=99, amount=20, date=day, created_at=day+'T11:00:00Z')]
    page.evaluate("rows=>{__liveMock.data.transactions=rows;__liveMock.event('transactions')}", rows)
    wait_transactions(page, rows)
    receipt = assert_cap(page)
    check(receipt['r']['actualCents'] == changed['r']['actualCents'] + 2000, 'receipt failed to update actual period expense')
    check(receipt['capacity'] == changed['capacity'] - 2000, 'receipt altered raw account capacity incorrectly')


CHECKS = [('current_period_sync: '+day+' '+vp, vp, lambda page, day=day: scenario(page, day))
          for day in ['2026-10-31', '2026-11-01'] for vp in ['desktop', 'mobile']]
