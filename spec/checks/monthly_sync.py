import json
from helpers import check, freeze, finance_state, go_tab
from checks.live_refresh import MOCK, updated

ROWS=[{'month_start':'2026-10-01','total_cents':310001,'allocations':{'food':200001},'mandatory_items':[]},{'month_start':'2026-11-01','total_cents':300003,'allocations':{'food':100001},'mandatory_items':[]}]

def demo(page):
    rows={r['month_start']:r for r in ROWS}
    freeze(page,'2026-10-21',[("const[monthlyRows,setMonthlyRows]=useState({})","const[monthlyRows,setMonthlyRows]=useState("+json.dumps(rows)+")")])
    state=finance_state(page)
    check(len(state['data']['monthly_budgets'])==2,'не всі місячні плани передані рушію')
    actual=page.evaluate("(()=>{const p=__financeProjection.currentPeriod,m=monthlyPeriodBudget(__financeInput.monthly_budgets,p.start,p.end);return [p.targetCents,m.targetCents,__budgetView.plan]})()")
    check(actual[0]==actual[1] and actual[2]==actual[1],f'різний план рушія/огляду {actual}')
    for tab in [1,2,3,0]:
        go_tab(page,tab)
        check('Сталася помилка' not in page.locator('body').inner_text(),'сторінка впала з місячним планом')
    check(page.evaluate('__budgetView.plan')==actual[1],'навігація змінила план')


def realtime(page):
    mock=MOCK.replace('window.supabase={createClient:()=>sb};','m.data.monthly_budgets='+json.dumps(ROWS)+';window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page,'2026-10-21',[("if(!sb){window.__financeProjection=","{window.__financeProjection="),("if(!sb)window.__budgetView=","window.__budgetView=")])
    updated(page)
    check(page.evaluate('__financeInput.monthly_budgets.length')==2,'завантажено лише поточний місяць')
    check(page.evaluate("__liveMock.reads.filter(x=>x.table==='monthly_budgets').every(x=>!x.ops.some(o=>o[0]==='eq'&&o[1]==='month_start'))"),'запит фільтрує поточний місяць')
    page.evaluate("__liveMock.data.monthly_budgets=__liveMock.data.monthly_budgets.map(r=>({...r,total_cents:0,allocations:{}}));__liveMock.event('monthly_budgets')")
    page.wait_for_function('__budgetView.plan===0',timeout=15000)
    check(page.evaluate('__financeProjection.currentPeriod.targetCents')==0,'рушій зберіг мінімум 15000 після оновлення')
    for tab in [1,2,3,0]: go_tab(page,tab)
    check(page.evaluate('__budgetView.plan')==0,'сторінки використовують старий бюджет')

CHECKS=[('monthly cross-month plan desktop','desktop',demo),('monthly cross-month plan mobile','mobile',demo),('monthly all-row realtime zero budget','desktop',realtime)]

def overspend(page):
    rows=[{'month_start':'2026-10-01','total_cents':310000,'allocations':{'food':310000},'mandatory_items':[]}]
    mock=MOCK.replace('window.supabase={createClient:()=>sb};',"m.data.monthly_budgets="+json.dumps(rows)+";m.data.transactions[0].date='2026-10-10';m.data.transactions[0].created_at='2026-10-10T10:00:00Z';m.data.transactions[0].amount=3000;window.supabase={createClient:()=>sb};")
    page.add_init_script(mock)
    freeze(page,'2026-10-21',[("if(!sb){window.__financeProjection=","{window.__financeProjection="),("if(!sb)window.__periodBudget=","window.__periodBudget=")])
    updated(page)
    values=page.evaluate('({ui:__periodBudget,cp:__financeProjection.currentPeriod})')
    check(values['ui']['avail']==61666 and values['ui']['avail']==values['cp']['remainingTargetCents'],'залишок ранньої частини місяця не враховано')
    # Спільний залишок: 100 ₴ жовтня плюс точна частка плану за 1–5 листопада.
    signed=310000-300000+310000*5//30
    check(values['ui']['rawRemaining']==signed==values['cp']['signedSpendableRemainingCents'],'Огляд не використовує спільний залишок з урахуванням ранніх перевитрат')
    check('616,66' in page.locator('.kpi-budget [data-r="avail"]').inner_text(),'плитка не показує обмежений залишок')
    check('38,54' in page.locator('.kpi-budget [data-r="daily"]').inner_text(),'плитка дня використовує старий залишок')

CHECKS += [('monthly overspend cap desktop','desktop',overspend),('monthly overspend cap mobile','mobile',overspend)]
