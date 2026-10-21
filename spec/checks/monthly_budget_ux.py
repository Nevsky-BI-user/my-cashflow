"""Розподіл у гривнях і відсотках, видимий залишок та доступний графік."""
from helpers import check, go_tab, expand_groups, num
from checks.monthly_budget import mount
from checks.live_refresh import updated


def allocation(page):
    mount(page)
    # Довгий список перевіряє видимість підсумку біля останнього поля.
    page.evaluate("for(let i=2;i<=15;i++)__liveMock.data.categories.push({...__liveMock.data.categories[0],id:i,name:'Категорія '+i});__liveMock.event('categories')")
    updated(page)
    go_tab(page, 1)
    check(page.locator('.bud-day,.bud-alloc').count()==0,'page repeats allocation editor summary')
    action=page.get_by_role('button',name='Розподіл бюджету',exact=True)
    check(action.count()==1,'Budget must expose one allocation action')
    action.click()
    sheet=page.get_by_role('dialog',name='Розподіл бюджету місяця')
    free=sheet.locator('.monthly-free')
    value=lambda: int(free.get_attribute('data-free-cents'))
    field=sheet.get_by_role('textbox',name='Продукти, ₴',exact=True)
    field.fill('400')
    check(value()==35000,'available allocation did not update while typing hryvnias')
    mode=sheet.get_by_role('group',name='Одиниця для Продукти',exact=True)
    mode.get_by_role('button',name='%',exact=True).click()
    field=sheet.get_by_role('textbox',name='Продукти, %',exact=True)
    field.fill('25')
    check(value()==56250,'25 percent must apply to net salary after mandatory payments')
    check('187' in sheet.locator('.monthly-category[data-cat="1"] .monthly-equivalent').inner_text(),'percent row lacks hryvnia equivalent')
    for _ in range(3):
        mode.get_by_role('button',name='₴',exact=True).click()
        check(sheet.get_by_role('textbox',name='Продукти, ₴',exact=True).input_value()=='187.5','mode switch changed allocation cents')
        mode.get_by_role('button',name='%',exact=True).click()
        check(value()==56250,'repeated mode switch changed free cents')
    sheet.get_by_role('textbox',name='Продукти, %',exact=True).fill('100.01')
    check(sheet.get_by_role('button',name='Зберегти місячний бюджет').is_disabled(),'invalid percent can save stale valid allocation')
    check(page.evaluate('__liveMock.writes.length')==0,'invalid percentage was written')
    mode.get_by_role('button',name='₴',exact=True).click()
    sheet.get_by_role('textbox',name='Продукти, ₴',exact=True).fill('187.51')
    mode.get_by_role('button',name='%',exact=True).click()
    check(value()==56249,'rounded percentage mode changed original allocation cents')
    mode.get_by_role('button',name='₴',exact=True).click()
    check(sheet.get_by_role('textbox',name='Продукти, ₴',exact=True).input_value()=='187.51','rounded percentage roundtrip lost a cent')
    sheet.get_by_role('textbox',name='Продукти, ₴',exact=True).fill('750.01')
    check(value()==-1,'over-allocation must retain negative live balance')
    check(sheet.get_by_role('button',name='Зберегти місячний бюджет').is_disabled(),'over-allocation can be saved')
    check(page.evaluate('__liveMock.writes.length')==0,'invalid allocation was written')
    sheet.get_by_role('textbox',name='Продукти, ₴',exact=True).fill('187.50')
    last=sheet.locator('.monthly-category input').last
    last.scroll_into_view_if_needed()
    last.fill('10.01')
    check(value()==55249,'last category did not update live balance')
    geometry=sheet.locator('.monthly-editor-footer').evaluate('(e)=>{const r=e.getBoundingClientRect();return{top:r.top,bottom:r.bottom,height:r.height,viewport:innerHeight}}')
    check(geometry['top']>=0 and geometry['bottom']<=geometry['viewport']+1 and geometry['height']>0,'allocation footer is outside viewport at last category')
    if page.viewport_size['width']<1024:
        old=page.viewport_size
        page.set_viewport_size(dict(width=old['width'],height=592))
        last.scroll_into_view_if_needed()
        box=sheet.locator('.monthly-editor-footer').bounding_box()
        field_box=last.bounding_box()
        check(box['y']>=0 and box['y']+box['height']<=592+1,'keyboard resize obscures live allocation footer')
        check(field_box['y']>=0 and field_box['y']+field_box['height']<=box['y']+1,'keyboard resize obscures edited input')
        page.set_viewport_size(old)
    sheet.get_by_role('button',name='Зберегти місячний бюджет').click()
    page.wait_for_function('!document.querySelector(".monthly-editor")')
    saved=page.evaluate('__liveMock.data.monthly_budgets[0]')
    check(saved['allocations']['1']==18750 and saved['allocations']['15']==1001,'percent or final amount saved with wrong cents')


def page_chart(page):
    mount(page)
    go_tab(page,1)
    expand_groups(page)
    check(page.locator('.bud-day,.bud-alloc').count()==0,'allocation summary visible on page')
    row=page.locator('.bud-cat[data-cat="1"]')
    check(row.locator('.bud-value').count()==3,'category must expose fact, plan and remaining columns')
    for label in ('Факт','План','Залишок'):
        check(row.locator('.bud-value[data-label="'+label+'"]').count()==1,'missing category value label '+label)
    if page.viewport_size['width']>=1024:
        geometry=row.evaluate('(e)=>{const n=e.querySelector(".bud-category-title").getBoundingClientRect(),v=e.querySelector(".bud-value").getBoundingClientRect();return{gap:v.left-n.right,width:n.width}}')
        check(geometry['gap']<=24 and geometry['width']<=190,'category column stretches excessively before amounts')
    name=row.get_attribute('aria-label') or row.inner_text()
    check(all(label in name for label in ('Факт','План','Залишок')),'category accessible name lacks amount meanings')
    chart=page.locator('.bud-chart')
    check(chart.get_attribute('role')=='slider' and chart.get_attribute('tabindex')=='0','chart is not keyboard accessible')
    check(chart.locator('text').count()>=4,'chart axes lack explicit date and money labels')
    readout=page.locator('.bud-chart-readout')
    chart.focus()
    chart.press('Home')
    first=readout.inner_text()
    check('01.10' in first,'chart Home does not select first day')
    chart.press('ArrowRight')
    second=readout.inner_text()
    check('02.10' in second and '321' in second,'chart keyboard readout lacks selected date and expense')
    chart.press('End')
    check(chart.get_attribute('aria-valuenow')=='3','chart End must stop at latest actual day')
    chart.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
    point=chart.evaluate('e=>{const p=e.querySelector(".bud-fact").points.getItem(2),m=e.getScreenCTM();return{x:p.x*m.a+m.e,y:p.y*m.d+m.f}}')
    check(page.evaluate("p=>!!document.elementFromPoint(p.x,p.y)?.closest('.bud-chart')",point),'chart point is covered by navigation')
    if page.viewport_size['width']<1024:
        page.touchscreen.tap(point['x'],point['y'])
    else:
        page.mouse.move(point['x'],point['y'])
    check('02.10' in readout.inner_text(),'chart pointer/touch does not update selected date')
    check('Бюджет' in readout.inner_text() and 'Залишок' in readout.inner_text(),'chart readout lacks explicit money series names')
    check(num(page.locator('.bud-mandatory .bud-kpi-v').inner_text())==250,'mandatory KPI lost reserve amount')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Budget page overflows horizontally')


CHECKS=[
    ('monthly_budget_ux: live amount percent and visible footer desktop','desktop',allocation),
    ('monthly_budget_ux: live amount percent and visible footer mobile','mobile',allocation),
    ('monthly_budget_ux: labeled compact categories and pointer keyboard chart desktop','desktop',page_chart),
    ('monthly_budget_ux: labeled compact categories and touch keyboard chart mobile','mobile',page_chart),
]
