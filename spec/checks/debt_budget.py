"""Синтетичний бюджет: борговий резерв, факт погашення та формула доступних коштів."""
import json

from helpers import check, freeze, go_tab, expand_groups, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_money


def debt_budget(page):
    page.emulate_media(reduced_motion='reduce')
    viewport = 'desktop' if page.viewport_size['width'] >= 1024 else 'mobile'
    setup = {
        'accounts': [
            {'id': 1, 'name': 'Synthetic cash', 'bank': 'cash', 'kind': 'cash', 'balance': 1000,
             'debt': 0, 'active': True, 'balance_updated_at': '2026-10-01T00:00:00Z'},
            {'id': 2, 'name': 'Synthetic card', 'bank': 'privat', 'kind': 'credit', 'balance': 0,
             'debt': 60, 'credit_limit': 100, 'active': True, 'balance_updated_at': '2026-10-01T00:00:00Z'}],
        'categories': [
            {'id': 'food', 'name': 'Продукти', 'icon': '🛒', 'budget_limit': 1, 'group_id': 1},
            {'id': 'savings', 'name': 'Заощадження', 'icon': '₴', 'budget_limit': 0, 'group_id': 1},
            {'id': 'dc', 'name': 'Погашення кредиток', 'icon': '💳', 'budget_role': 'debt_card', 'group_id': 2},
            {'id': 'di', 'name': 'Додаткове погашення розстрочок', 'icon': '▦', 'budget_role': 'debt_installment', 'group_id': 2}],
        'category_groups': [{'id': 1, 'name': 'Побут'}, {'id': 2, 'name': 'Погашення боргу'}],
        'credits': [{'id': 5, 'name': 'Synthetic installments', 'monthly_amount': 10, 'payment_day': 15,
                     'start_year': 2026, 'start_month': 9, 'total_payments': 5, 'active': True}],
        'salary_config': [{'id': 1, 'rate': 0, 'salary_day': 6, 'advance_day': 21, 'split_day': 15,
                           'salary_amount': 100, 'advance_amount': 100, 'savings_pct': 0}],
        'transactions': [], 'monthly_budgets': []}
    mock = MOCK.replace("['insert','update','delete']", "['insert','update','delete','upsert']")
    mock = mock.replace('const apply=()=>{const update=', "const apply=()=>{const up=q.ops.find(x=>x[0]==='upsert');if(up){m.data[table]=[clone(up[1])];return{data:[clone(up[1])],error:null}}const update=")
    assignments = ''.join('m.data.' + key + '=' + json.dumps(value, ensure_ascii=False) + ';' for key, value in setup.items())
    mock = mock.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, '2026-10-10', patch=[
        ('if(!sb){window.__financeProjection=', '{window.__financeProjection='),
        ('if(!sb)window.__calendarBudget=', 'window.__calendarBudget=')])
    updated(page)
    page.wait_for_function('window.__financeInput&&__financeInput.accounts.length===2')
    go_tab(page, 1)
    wait_money(page, '[data-debt-total=card]', 6000)
    wait_money(page, '[data-debt-total=installment]', 5000)
    wait_money(page, '[data-debt-total=total]', 11000)
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    sheet = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    sheet.get_by_role('textbox', name='Продукти, ₴', exact=True).fill('80')
    sheet.get_by_role('textbox', name='Заощадження, ₴', exact=True).fill('10')
    page.wait_for_function("document.querySelector('[data-debt-role=debt_card] output').dataset.cents==='6000'")
    check(sheet.locator('[data-debt-role=debt_installment] output').get_attribute('data-cents') == '4000', 'mandatory installment reserved twice')
    check(sheet.locator('[data-debt-role] input').count() == 0, 'automatic debt rows are editable')
    sheet.get_by_role('textbox', name='Продукти, ₴', exact=True).fill('130')
    page.wait_for_function("document.querySelector('[data-debt-role=debt_card] output').dataset.cents==='5000'")
    check(sheet.locator('[data-debt-role=debt_installment] output').get_attribute('data-cents') == '0', 'card-first allocation failed')
    sheet.get_by_role('textbox', name='Продукти, ₴', exact=True).fill('80')
    shot(page, 'debt-budget-editor-' + viewport + '.jpg')
    sheet.get_by_role('button', name='Зберегти місячний бюджет', exact=True).click()
    page.wait_for_function("!document.querySelector('.monthly-editor')&&__liveMock.data.monthly_budgets.length===1")
    saved = page.evaluate('__liveMock.data.monthly_budgets[0]')
    check(sum(saved['allocations'].values()) + sum(i['amount_cents'] for i in saved['mandatory_items']) == saved['total_cents'], 'envelope does not conserve salary')
    check(page.evaluate('__liveMock.data.accounts[1].debt') == 60, 'saving plan changed actual debt')
    wait_money(page, '[data-debt-total=card]', 6000)
    wait_money(page, '.bud-mandatory .bud-kpi-v', 1000)
    wait_money(page, '.bud-pool .bud-kpi-v', 20000)
    wait_money(page, '.bud-avail .bud-kpi-v', 8000)
    expand_groups(page)
    check(page.locator('.bud-cat[data-cat=dc]').get_attribute('aria-disabled') == 'true', 'system category opens ordinary editor')
    go_tab(page, 0)
    wait_money(page, '.kpi-funds .dv-kpi-v', 103000)
    page.locator('.kpi-funds .kpi-i').click()
    formula = page.locator('[data-funds-formula]')
    check(formula.is_visible(), 'available formula missing')
    text = formula.inner_text().replace('\u00a0', ' ')
    check('1 000' in text and '40' in text and '10' in text and '1 030' in text, 'cash + unused credit - savings formula differs')
    shot(page, 'debt-budget-funds-formula-' + viewport + '.jpg')
    page.keyboard.press('Escape')
    # One linked own-to-card transfer, with a duplicated delivery, counts once.
    page.evaluate("""()=>{const base={date:'2026-10-09',created_at:'2026-10-09T12:00:00Z',amount:20,transfer_id:'synthetic-transfer'};const out={...base,id:11,account_id:1,type:'expense'},inc={...base,id:12,account_id:2,type:'income'};__liveMock.data.transactions=[out,inc,inc];__liveMock.event('transactions')}""")
    page.wait_for_function('__financeInput.transactions.some(t=>t.id===12)')
    go_tab(page, 1)
    wait_money(page, '[data-debt-total=card]', 4000)
    expand_groups(page)
    wait_money(page, '.bud-cat[data-cat=dc] .bud-nums', 2000)
    wait_money(page, '.bud-avail .bud-kpi-v', 8000)
    check(page.evaluate('__liveMock.data.monthly_budgets[0].allocations.dc') == 6000, 'actual payment rewrote the saved plan')
    page.evaluate("()=>{__liveMock.data.transactions.push({id:13,type:'expense',account_id:1,category_id:'dc',amount:5,date:'2026-10-10',created_at:'2026-10-10T10:00:00Z',source:'manual'});__liveMock.event('transactions')}")
    page.wait_for_function('__financeInput.transactions.some(t=>t.id===13)')
    wait_money(page, '.bud-avail .bud-kpi-v', 7500)
    wait_money(page, '.bud-cat[data-cat=dc] .bud-nums', 2000)
    shot(page, 'debt-budget-progress-' + viewport + '.jpg')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'debt content overflows viewport')
    period = page.locator('.dper' if viewport == 'desktop' else '.per-pill')
    period.get_by_role('button', name='Наступний період', exact=True).click()
    page.wait_for_function("document.querySelector('.calendar-budget').dataset.month==='2026-11-01'")
    updated(page)
    wait_money(page, '[data-debt-total=card]', 4000)
    expand_groups(page)
    wait_money(page, '.bud-cat[data-cat=dc] .bud-nums', 0)
    period.get_by_role('button', name='Попередній період', exact=True).click()
    page.wait_for_function("document.querySelector('.calendar-budget').dataset.month==='2026-10-01'")
    updated(page)
    expand_groups(page)
    wait_money(page, '.bud-cat[data-cat=dc] .bud-nums', 2000)
    # No debt: the remaining envelope stays available, never becomes a fictitious repayment.
    page.evaluate("()=>{__liveMock.data.accounts[1].debt=0;__liveMock.data.transactions=[];__liveMock.data.credits=[];__liveMock.event('accounts');__liveMock.event('credits');__liveMock.event('transactions')}")
    page.wait_for_function('__financeInput.credits.length===0&&__financeInput.accounts[1].debt===0&&__financeInput.transactions.length===0')
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    page.wait_for_function("document.querySelector('[data-debt-role=debt_card] output').dataset.cents==='0'")
    check(sheet.locator('[data-debt-role=debt_installment] output').get_attribute('data-cents') == '0', 'zero debt allocated installments')
    check(sheet.locator('.monthly-free').get_attribute('data-free-cents') == '11000', 'debt-free residual lost')
    page.keyboard.press('Escape')
    go_tab(page, 2)
    page.get_by_role('button', name='+ Операція' if viewport == 'desktop' else 'Додати операцію', exact=True).first.click()
    overlay = page.locator('.overlay').last
    check('Продукти' in overlay.inner_text(), 'ordinary category picker missing')
    check('Погашення кредиток' not in overlay.inner_text() and 'Додаткове погашення розстрочок' not in overlay.inner_text(), 'budget-only debt categories leaked into expense picker')
    page.keyboard.press('Escape')


CHECKS = [
    ('Debt budget allocation, repayment progress and funds formula desktop', 'desktop', debt_budget),
    ('Debt budget allocation, repayment progress and funds formula mobile', 'mobile', debt_budget),
]
