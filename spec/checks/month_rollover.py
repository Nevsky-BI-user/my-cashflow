"""Перевитрата лишається в поточному зарплатному періоді на межі місяців."""
import json
from helpers import ROOT, check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_transactions, wait_money


def verify_day(page, day, days):
    page.emulate_media(reduced_motion='reduce')
    data = json.loads((ROOT / 'spec/fixtures/daily-forecast.json').read_text(encoding='utf-8'))
    setup = {'accounts': data['accounts'], 'categories': data['categories'],
             'category_groups': [{'id': 1, 'name': 'Побут', 'sort_order': 0}],
             'salary_config': [{'id': 1, **data['salary']}], 'monthly_budgets': data['monthly_budgets'],
             'transactions': data['transactions'], 'fixed_payments': [], 'credits': [], 'goals': []}
    assignments = ''.join('m.data.' + key + '=' + json.dumps(value, ensure_ascii=False) + ';' for key, value in setup.items())
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};'))
    freeze(page, day, patch=[('if(!sb){window.__financeProjection=', '{window.__financeProjection=')])
    wait_transactions(page, data['transactions'])
    go_tab(page, 0)
    page.wait_for_function('()=>window.__financeProjection&&__financeProjection.currentPeriod.spendableRemainingCents===205542')
    updated(page)
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', 205542 / days)
    result = page.evaluate('''()=>{const p=__financeProjection.currentPeriod;return {start:p.start,end:p.end,sum:p.futureSchedule.reduce((s,d)=>s+d.spendCents,0)}}''')
    check(result == {'start': '2026-10-21', 'end': '2026-11-06', 'sum': 205542}, 'Межа місяця змінила залишок періоду')
    shot(page, 'month-rollover-' + day + '-' + str(page.viewport_size['width']) + '.jpg', full=False)


def october(page):
    verify_day(page, '2026-10-31', 6)


def november(page):
    verify_day(page, '2026-11-01', 5)


CHECKS = [('Залишок періоду 31 жовтня', 'desktop', october),
          ('Той самий залишок 1 листопада', 'desktop', november),
          ('Залишок періоду 31 жовтня на телефоні', 'mobile', october),
          ('Той самий залишок 1 листопада на телефоні', 'mobile', november)]
