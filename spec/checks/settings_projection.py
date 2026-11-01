"""Налаштування оновлюють усі сторінки без перезавантаження та змін розподілу."""
import json
from helpers import check, freeze, go_tab
from checks.live_refresh import MOCK, updated

ROWS=[{'month_start':'2026-10-01','total_cents':11000000,'income_basis_cents':11000000,'mandatory_items':[],'allocations':{'food':2000000}}, {'month_start':'2026-11-01','total_cents':11000000,'income_basis_cents':11000000,'mandatory_items':[],'allocations':{'food':2000000}}]


def settings(page):
    script=MOCK.replace('window.supabase={createClient:()=>sb};', 'm.data.monthly_budgets='+json.dumps(ROWS)+';window.supabase={createClient:()=>sb};')
    page.add_init_script(script)
    freeze(page,'2026-11-01',[("if(!sb){window.__financeProjection=", "{window.__financeProjection="), ("if(!sb)window.__calendarBudget=", "window.__calendarBudget=")])
    updated(page)
    initial=page.evaluate('JSON.stringify(__liveMock.data.monthly_budgets)')
    history=page.evaluate('JSON.stringify(__financeInput.monthly_budgets.find(r=>r.month_start==="2026-10-01"))')
    page.evaluate('__liveMock.data.salary_config[0].advance_amount=70000;__liveMock.event("salary_config")')
    page.wait_for_function('__financeInput.monthly_budgets.find(r=>r.month_start==="2026-11-01").total_cents===13000000')
    def all_pages(gross,mandatory):
        for tab in range(5):
            go_tab(page,tab)
            check('Сталася помилка' not in page.locator('body').inner_text(), 'render error on tab '+str(tab))
            row=page.evaluate('__financeInput.monthly_budgets.find(r=>r.month_start==="2026-11-01")')
            check(row['total_cents']==gross and sum(x['amount_cents'] for x in row['mandatory_items'])==mandatory,'different settings model on tab '+str(tab))
            if tab==1:
                check(int(page.locator('[data-budget-part=income]').get_attribute('data-cents'))==gross,'rendered salary not refreshed')
                check(int(page.locator('[data-budget-part=mandatory]').get_attribute('data-cents'))==mandatory,'rendered obligations not refreshed')
    all_pages(13000000,0)
    page.evaluate('__liveMock.data.fixed_payments=[{id:90,name:"Synthetic payment",type:"expense",amount:1000,day_of_month:25,active:true}];__liveMock.event("fixed_payments")')
    page.wait_for_function('__financeInput.monthly_budgets.find(r=>r.month_start==="2026-11-01").mandatory_items.some(x=>x.key.startsWith("fixed:90:"))')
    all_pages(13000000,100000)
    page.evaluate('__liveMock.data.credits=[{id:91,name:"Synthetic installment",monthly_amount:2000,payment_day:20,start_year:2026,start_month:10,total_payments:3,active:true}];__liveMock.event("credits")')
    page.wait_for_function('__financeInput.monthly_budgets.find(r=>r.month_start==="2026-11-01").mandatory_items.some(x=>x.key.startsWith("installment:91:"))')
    all_pages(13000000,300000)
    check(page.evaluate('JSON.stringify(__liveMock.data.monthly_budgets)')==initial,'settings refresh wrote or changed user allocations')
    page.evaluate('__liveMock.data.monthly_budgets[1].allocations.food=3000000;__liveMock.event("monthly_budgets")')
    page.wait_for_function('__financeInput.monthly_budgets.find(r=>r.month_start==="2026-11-01").allocations.food===3000000')
    all_pages(13000000,300000)
    check(page.evaluate('JSON.stringify(__financeInput.monthly_budgets.find(r=>r.month_start==="2026-10-01"))')==history,'historical plan rewritten')
    check(page.evaluate('__liveMock.writes.length')==0,'read-only refresh writes settings/plans')


CHECKS=[('settings recompute all rendered pages desktop','desktop',settings),('settings recompute all rendered pages mobile','mobile',settings)]
