"""Нульові нові категорії доступні для місячного розподілу без руху фактичних коштів."""
from helpers import check, go_tab, expand_groups
from checks import monthly_budget
from checks.live_refresh import updated


EXTRA = """m.data.categories.push(
 {id:18,name:'Заощадження',icon:'🐷',color:'#0d9488',budget_limit:0,limit_abs:null,is_income:false,group_id:10,sort_order:18},
 {id:20,name:'Благодійність',icon:'❤️',color:'#db2777',budget_limit:0,limit_abs:null,is_income:false,group_id:9,sort_order:20}
);m.data.category_groups.push({id:9,name:'Подарунки',sort_order:9},{id:10,name:'Інше',sort_order:10});"""


def allocation(page):
    original = monthly_budget.MOCK
    monthly_budget.MOCK = original.replace('window.supabase={createClient:()=>sb};', EXTRA + 'window.supabase={createClient:()=>sb};')
    try:
        monthly_budget.mount(page)
    finally:
        monthly_budget.MOCK = original

    defaults = page.evaluate("""()=>{const names=['Заощадження','Благодійність'],demo=demoSeed();return{
      fallback:BCAT.filter(c=>names.includes(c.name)),demo:demo.categories.filter(c=>names.includes(c.name)),
      generated:demo.transactions.filter(t=>t.category_id===18||t.category_id===19).length,
      planned:demo.monthly_budgets.some(m=>(m.allocations['18']||0)!==0||(m.allocations['19']||0)!==0)
    }}""")
    check(len(defaults['fallback']) == 2 and all(c['limit'] == 0 for c in defaults['fallback']), 'fallback categories missing or alter initial budget')
    check({c['id']: c['groupId'] for c in defaults['fallback']} == {'savings': 10, 'charity': 9}, 'new categories are not in the existing groups')
    check(len(defaults['demo']) == 2 and all(c['budget_limit'] == 0 and not c['is_income'] for c in defaults['demo']), 'demo categories missing or seeded as income')
    check(defaults['generated'] == 0 and not defaults['planned'], 'new categories generated demo expenses or an initial allocation')
    facts = page.evaluate('JSON.stringify({tx:__liveMock.data.transactions,goals:__liveMock.data.goals,savings:__liveMock.data.savings_log})')
    go_tab(page, 1)
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    sheet = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    field = lambda name: sheet.get_by_role('textbox', name=name + ', ₴', exact=True)
    savings = lambda: int(sheet.locator('[data-auto-savings] output').get_attribute('data-cents'))
    check(field('Заощадження').count() == 0 and field('Благодійність').input_value() == '0', 'savings must be automatic and charity editable')
    check(savings() == 75000 and sheet.locator('.monthly-free').get_attribute('data-free-cents') == '0', 'salary1000 minus mandatory250 must become one savings goal750')
    field('Продукти').fill('400')
    field('Благодійність').fill('25.25')
    check(savings() == 32475 and sheet.locator('.monthly-free').get_attribute('data-free-cents') == '0', '100000-25000-40000-2525 must become savings32475')
    monthly_budget.save(page, sheet)
    saved = page.evaluate('__liveMock.data.monthly_budgets[0]')
    check(saved['allocations']['1'] == 40000 and saved['allocations']['18'] == 32475 and saved['allocations']['20'] == 2525, 'saved allocation amounts changed')
    check(sum(saved['allocations'].values()) == 75000, 'allocation lost cents from the net monthly envelope')
    check(saved['total_cents'] == 100000 and sum(i['amount_cents'] for i in saved['mandatory_items']) == 25000, 'allocation changed salary or mandatory envelope')
    check(page.evaluate('JSON.stringify({tx:__liveMock.data.transactions,goals:__liveMock.data.goals,savings:__liveMock.data.savings_log})') == facts, 'allocation created actual expenses or goal/savings movements')
    check(page.evaluate("__liveMock.writes.every(w=>w.table==='monthly_budgets')"), 'allocation wrote outside monthly budgets')

    page.reload()
    page.wait_for_selector('.side' if page.viewport_size['width'] >= 1024 else '.tab-bar', timeout=20000)
    updated(page)
    go_tab(page, 1)
    expand_groups(page)
    check(page.locator('.bud-cat[data-cat="18"]').count() == 1 and page.locator('.bud-cat[data-cat="20"]').count() == 1, 'saved categories absent from budget page')
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    sheet = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    check(field('Заощадження').count() == 0 and savings() == 32475 and field('Благодійність').input_value() == '25.25', 'automatic savings and charity did not survive reload')
    check(sheet.locator('.monthly-free').get_attribute('data-free-cents') == '0', 'reload changed the monthly balance')
    field('Благодійність').fill('0')
    monthly_budget.save(page, sheet)
    saved = page.evaluate('__liveMock.data.monthly_budgets[0]')
    check(saved['allocations']['1'] == 40000 and saved['allocations']['18'] == 35000 and saved['allocations']['20'] == 0, 'reset charity must release2525 into the same savings goal')
    check(page.evaluate('JSON.stringify({tx:__liveMock.data.transactions,goals:__liveMock.data.goals,savings:__liveMock.data.savings_log})') == facts, 'reset generated actual financial movements')


CHECKS = [
    ('Savings and charity: zero allocation, save, reload and no money movement desktop', 'desktop', allocation),
    ('Savings and charity: zero allocation, save, reload and no money movement mobile', 'mobile', allocation),
]
