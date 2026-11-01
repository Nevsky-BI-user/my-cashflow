"""Належний борг скорочує денний бюджет однаково в картці та графіку."""
import json
from helpers import check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_money


def due_today(page):
    day = '2026-10-10'
    page.emulate_media(reduced_motion='reduce')
    setup = {'accounts': [{'id': 1, 'name': 'Synthetic cash', 'kind': 'debit', 'bank': 'cash', 'balance': 10000, 'debt': 0, 'active': True},
                          {'id': 2, 'name': 'Synthetic credit', 'kind': 'credit', 'balance': 0, 'debt': 5000, 'debt_month': '2026-08-01', 'credit_limit': 10000, 'mono_account_id': 'synthetic', 'active': True}],
             'categories': [{'id': 'food', 'name': 'Продукти', 'icon': '🛒', 'color': '#7066e0', 'budget_limit': 100, 'group_id': 1}],
             'category_groups': [{'id': 1, 'name': 'Побут', 'sort_order': 0}],
             'salary_config': [{'id': 1, 'rate': 0, 'advance_day': 21, 'salary_day': 6, 'split_day': 15, 'advance_amount': 50000, 'salary_amount': 50000}],
             'monthly_budgets': [{'month_start': '2026-10-01', 'total_cents': 3100000, 'allocations': {'food': 3100000}}],
             'transactions': [], 'fixed_payments': [], 'credits': [], 'goals': []}
    assignments = ''.join('m.data.' + key + '=' + json.dumps(value, ensure_ascii=False) + ';' for key, value in setup.items())
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};'))
    freeze(page, day, patch=[('if(!sb){window.__financeProjection=', '{window.__financeProjection=')])
    go_tab(page, 0)
    page.wait_for_function('()=>window.__financeProjection&&__financeProjection.currentPeriod.spendableRemainingCents===500000')
    updated(page)
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', 500000 / 11)
    result = page.evaluate('''()=>{const p=__financeProjection,c=p.currentPeriod;return {
        daily:c.dailyCents,rows:c.futureSchedule.map(r=>r.spendCents),today:p.events.filter(e=>e.kind==='variable'&&e.date==='2026-10-10').length,
        paid:p.events.filter(e=>e.kind==='repay'&&e.date==='2026-10-10').reduce((s,e)=>s+e.amountCents,0)}}''')
    check(result['paid'] == 500000, 'Належний борг не погашено перед витратами')
    check(sum(result['rows']) == 500000 and all(abs(n-result['daily']) < 1 for n in result['rows']), 'Денний графік не збігається з KPI')
    check(result['today'] == 0, 'З’явилася вигадана сьогоднішня витрата')
    shot(page, 'due-priority-' + str(page.viewport_size['width']) + '.jpg', full=False)


CHECKS = [('Належний борг і однаковий денний ліміт', 'desktop', due_today),
          ('Належний борг і денний ліміт на телефоні', 'mobile', due_today)]
