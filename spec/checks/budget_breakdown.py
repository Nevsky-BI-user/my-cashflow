"""Повний розрахунок бюджету та компактне редагування категорій."""
import json
from helpers import check,freeze,go_tab,num,shot,settle
from checks.live_refresh import MOCK,updated


def layout(page):
    cats=[{'id':'food','name':'Продукти','icon':'🛒','budget_limit':100,'group_id':1},
          {'id':'debt','name':'Погашення кредиток','budget_role':'debt_card','icon':'💳','group_id':1},
          {'id':'savings','name':'Заощадження','icon':'🐷','group_id':1}]
    cats += [{'id':'c'+str(i),'name':'Категорія '+str(i),'icon':'•','group_id':1} for i in range(12)]
    items=[{'key':'fixed:1:2026-11-15','date':'2026-11-15','name':'Обов’язкові','amount_cents':5071627,'kind':'fixed'}]
    row={'month_start':'2026-11-01','total_cents':13492619,'mandatory_items':items,'allocations':{'food':7186706,'debt':1234286,'savings':0}}
    setup={'accounts':[{'id':1,'name':'Готівка','kind':'debit','balance':100000,'active':True},{'id':2,'name':'Кредитка','kind':'credit','debt':25865.49,'balance':0,'credit_limit':50000,'debt_month':'2026-10-01','active':True}],
           'categories':cats,'category_groups':[{'id':1,'name':'Категорії'}],'salary_config':[{'id':1,'rate':0,'advance_day':21,'salary_day':6,'split_day':15,'advance_amount':69476.19,'salary_amount':65450}],
           'monthly_budgets':[row],'fixed_payments':[{'id':1,'name':'Обов’язкові','amount':50716.27,'day_of_month':15,'type':'payment','active':True}], 'credits':[],'transactions':[],'goals':[]}
    mock=MOCK.replace("for(const method of ['insert','update','delete'])","for(const method of ['insert','update','delete','upsert'])")
    mock=mock.replace('const apply=()=>{const update=',"const apply=()=>{const up=q.ops.find(x=>x[0]==='upsert');if(up){m.data[table]=[clone(up[1])];return{data:[clone(up[1])],error:null}}const update=")
    assignments=''.join('m.data.'+k+'='+json.dumps(v,ensure_ascii=False)+';' for k,v in setup.items())
    page.add_init_script(mock.replace('window.supabase={createClient:()=>sb};',assignments+'window.supabase={createClient:()=>sb};'))
    page.emulate_media(reduced_motion='reduce')
    freeze(page,'2026-11-01',patch=[('if(!sb){window.__financeProjection=','{window.__financeProjection=')])
    updated(page);go_tab(page,1)
    parts=page.locator('.budget-reconciliation')
    for key,value in [('income',13492619),('mandatory',5071627),('reserved',1234286),('spent',0),('remaining',7186706)]:
        cell=parts.locator('[data-budget-part='+key+']')
        check(int(cell.get_attribute('data-cents'))==value,'неправильна частина '+key)
        check(round(num(cell.locator('b').inner_text())*100)==value,'неповна сума '+key)
    shot(page,'budget-reconciliation-'+str(page.viewport_size['width'])+'.jpg',full=False)
    page.get_by_role('button',name='Розподіл бюджету',exact=True).click()
    dialog=page.locator('.monthly-editor')
    for width,height in ([(1280,800),(1920,1080)] if page.viewport_size['width']>=1024 else [(375,812),(390,844)]):
        page.set_viewport_size({'width':width,'height':height});settle(page)
        geometry=dialog.evaluate('''e=>{const d=e.getBoundingClientRect(),b=e.querySelector('.monthly-editor-body').getBoundingClientRect(),f=e.querySelector('.monthly-editor-footer').getBoundingClientRect();return{dialog:d.height,body:b.height,footer:f.height,overlap:b.bottom>f.top+1}}''')
        check(geometry['footer']<=110 and geometry['body']>=geometry['dialog']*.5 and not geometry['overlap'],str(geometry))
        check(dialog.locator('.monthly-editor-body .monthly-debt').count()==1,'борги поза прокручуваною частиною')
        last=dialog.locator('.monthly-category').last;last.scroll_into_view_if_needed()
        check(last.bounding_box()['y']+last.bounding_box()['height']<=dialog.locator('footer').bounding_box()['y']+1,'останню категорію перекрито')
        shot(page,'budget-breakdown-'+str(width)+'.jpg',full=False)
    dialog.locator('#monthly-cat-food').fill('71767.06')
    debt=dialog.locator('[data-debt-role=debt_card] output')
    check(int(debt.get_attribute('data-cents'))==1244286,'редагування не перерахувало резерв')
    dialog.locator('.monthly-debt summary').click()
    check(debt.is_visible(),'деталі боргу не відкриваються')
    dialog.get_by_role('button',name='Зберегти місячний бюджет').click()
    page.wait_for_function("!document.querySelector('.monthly-editor')");updated(page)
    check(int(page.locator('[data-budget-part=reserved]').get_attribute('data-cents'))==1244286,'сторінка не оновила резерв після збереження')
    go_tab(page,0)
    check(page.evaluate("__financeProjection.currentPeriod.monthlyBudget.rawCategories.some(c=>c.id==='food'&&c.totalCents>0)"),'Огляд не отримав план')


CHECKS=[('Розклад суми та компактний редактор ПК','desktop',layout),('Розклад суми та компактний редактор телефон','mobile',layout)]


def deficit(page):
    row={'month_start':'2026-11-01','total_cents':100000,'mandatory_items':[{'key':'fixed:1:2026-11-15','date':'2026-11-15','name':'Платіж','amount_cents':120000,'kind':'fixed'}],'allocations':{}}
    setup={'accounts':[{'id':1,'name':'Готівка','kind':'debit','balance':1000,'active':True}], 'categories':[{'id':'food','name':'Продукти','icon':'🛒','budget_limit':100}],
           'salary_config':[{'id':1,'rate':0,'advance_day':21,'salary_day':6,'split_day':15,'advance_amount':600,'salary_amount':400}], 'monthly_budgets':[row],
           'fixed_payments':[{'id':1,'name':'Платіж','amount':1200,'day_of_month':15,'type':'payment','active':True}],'credits':[],'transactions':[],'goals':[]}
    assignments=''.join('m.data.'+k+'='+json.dumps(v,ensure_ascii=False)+';' for k,v in setup.items())
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};',assignments+'window.supabase={createClient:()=>sb};'))
    page.emulate_media(reduced_motion='reduce');freeze(page,'2026-11-01');updated(page);go_tab(page,1)
    reserve=page.locator('[data-budget-part=reserved]');remaining=page.locator('[data-budget-part=remaining]')
    check(int(reserve.get_attribute('data-cents'))==0,'Нестача стала від’ємним резервом')
    check(int(remaining.get_attribute('data-cents'))==-20000 and 'Нестача' in remaining.inner_text(),'Нестачу не показано')
    check(num(remaining.locator('b').inner_text())==200,'Неправильна сума нестачі')
    check('200 ₴' in page.locator('.bud-debt [role=alert]').inner_text(),'Немає пояснення нестачі обов’язкових')
    check(page.locator('.bud-avail .bud-kpi-v').get_attribute('data-over')=='1','Нестача не позначена в головній картці')


CHECKS += [('Резерв без від’ємних сум при нестачі зарплати','desktop',deficit)]
