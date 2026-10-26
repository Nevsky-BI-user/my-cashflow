"""Збережений план вибраного періоду та залишок відображаються без змішування сум."""
import json
from helpers import check, freeze, go_tab, settle, shot, num

CATS = [dict(id='purpose_card',name='Погашення кредиток',icon='💳',budget_role='debt_card',limit=0,color='#bc8451'),
        dict(id='purpose_inst',name='Дострокове погашення розстрочок',icon='📦',budget_role='debt_installment',limit=0,color='#8b79b5')]
ROWS = {month:dict(month_start=month,total_cents=2400000,allocations=dict(food=1500000,purpose_card=400000,purpose_inst=200000,savings=100000),mandatory_items=[])
        for month in ('2026-09-01','2026-10-01','2026-11-01','2026-12-01')}
PATCH = [('const BCAT=[','const BCAT=['+','.join(json.dumps(c,ensure_ascii=False) for c in CATS)+','),
         ('const[monthlyRows,setMonthlyRows]=useState({})','const[monthlyRows,setMonthlyRows]=useState('+json.dumps(ROWS)+')')]


def verify(page, desktop):
    host=page.locator('.dv-bud' if desktop else '.o-budget')
    section=host.locator('[data-budget-allocation="available"]')
    check(section.count()==1,'план вибраного періоду не показано')
    expected=page.evaluate("""()=>{const b=__budgetView,p=monthlyPeriodBudget(__financeInput.monthly_budgets,b.start,b.end,{categories:__financeInput.categories});
      const amount=id=>(p.categories.find(c=>c.id===id)||{}).totalCents||0;
      return{total:p.targetCents,parts:{daily:amount('food'),card:amount('purpose_card'),installment:amount('purpose_inst'),savings:amount('savings'),unallocated:p.unallocatedCents},range:pbDm(pbDate(b.start))+'–'+pbDm(pbAdd(pbDate(b.end),-1))};}""")
    check(int(section.get_attribute('data-total-cents'))==expected['total'],'знаменник не є планом вибраного періоду')
    check(expected['range'] in section.get_attribute('aria-label'),'графік стосується іншого періоду')
    for key,value in expected['parts'].items():
        item=section.locator('[data-allocation="'+key+'"]')
        check(item.count()==1 and int(item.get_attribute('data-cents'))==value,f'неправильний склад {key}')
        check(round(num(item.locator('b').inner_text())*100)==value,f'неповна сума {key}')
    check(sum(expected['parts'].values())==expected['total'],'суми не зберігають копійки')
    avail=page.locator('.kpi-budget [data-r="avail"] .kpi-rv')
    if avail.count():
        check(abs(num(section.locator('.purpose-heading b').inner_text())-abs(num(avail.first.inner_text())))<0.01,'залишок графіка не збігається з головним KPI')
    bounds=section.evaluate("""e=>{const r=e.getBoundingClientRect(),host=e.closest('.surface,.o-budget').getBoundingClientRect();return{bottom:r.bottom,hostBottom:host.bottom,bad:[...e.querySelectorAll('*')].filter(x=>{const q=x.getBoundingClientRect();return x.scrollWidth>x.clientWidth+1||q.left<r.left-1||q.right>r.right+1||q.top<r.top-1||q.bottom>r.bottom+1}).map(x=>x.className)}}""")
    check(not bounds['bad'] and bounds['bottom']<=bounds['hostBottom']+1,f'графік або суми обрізано {bounds}')
    if desktop:
        check(page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth'),'Огляд із планом прокручується')
        check(host.evaluate('e=>e.scrollHeight<=e.clientHeight+1'),'категорії з планом не вміщаються')


def desktop(page):
    for theme in ('light','dark'):
        freeze(page,'2026-10-26',PATCH)
        go_tab(page,0)
        page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
        for width,height in ((1280,720),(1440,900),(1920,1080),(2048,1220)):
            page.set_viewport_size(dict(width=width,height=height));page.wait_for_timeout(300);settle(page)
            verify(page,True)
            if width in (1440,2048):shot(page,f'budget-purpose-{theme}-{width}.jpg',full=False)
        for direction in ('Наступний період','Попередній період','Попередній період'):
            page.get_by_role('button',name=direction,exact=True).first.click();settle(page);verify(page,True)


def mobile(page):
    freeze(page,'2026-10-26',PATCH);go_tab(page,0)
    for theme in ('light','dark'):
        page.evaluate('t=>document.documentElement.dataset.theme=t',theme)
        for width in (320,375,390,430):
            page.set_viewport_size(dict(width=width,height=844));settle(page);verify(page,False)


CHECKS=[('budget purpose: exact selected plan and fit','desktop',desktop),('budget purpose: mobile allocation without overlap','mobile',mobile)]


def dense(page):
    from checks.no_scroll_layout import PATCHES
    from checks.visual_layout import overview_bounds
    page.set_viewport_size(dict(width=1280,height=720))
    freeze(page,'2026-10-26',PATCHES+PATCH)
    go_tab(page,0);settle(page)
    verify(page,True)
    overview_bounds(page,'17 категорій і збережений розподіл')
    shot(page,'budget-purpose-dense-1280.jpg',full=False)


CHECKS.append(('budget purpose: saved plan with populated categories','desktop',dense))
