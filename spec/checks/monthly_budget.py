"""Календарний план: збереження, історія, категорії, навігація та помилки."""
from helpers import check, freeze, go_tab, expand_groups, num, shot
from checks.live_refresh import MOCK, updated


def seed_demo(page, day, patch=None):
    """Явний збережений план фікстури; жодного автоімпорту плану виплат."""
    start=day[:7]+'-01'
    row="{month_start:'"+start+"',total_cents:3000000,allocations:Object.fromEntries(BCAT.map(c=>[c.id,100000]))}"
    freeze(page,day,list(patch or [])+[("const[monthlyRows,setMonthlyRows]=useState({})","const[monthlyRows,setMonthlyRows]=useState({'"+start+"':"+row+"})")])


def mount(page, day='2026-10-03'):
    mock = MOCK.replace("for(const method of ['insert','update','delete'])", "for(const method of ['insert','update','delete','upsert'])")
    mock = mock.replace("id:'food'", "id:1").replace("category_id:'food'", "category_id:1")
    mock = mock.replace("const apply=()=>{const update=", """const apply=()=>{if(m.failWrite)return{error:{message:'Synthetic save offline'}};const up=q.ops.find(x=>x[0]==='upsert');if(up){const rows=m.data[table]||(m.data[table]=[]),i=rows.findIndex(r=>r.month_start===up[1].month_start);if(i<0)rows.push(clone(up[1]));else rows[i]=clone(up[1]);localStorage.setItem('__monthly_mock_db',JSON.stringify(rows));return{data:[clone(up[1])],error:null}}const update=""")
    mock = mock.replace("window.supabase={createClient:()=>sb};", """m.data.monthly_budgets=JSON.parse(localStorage.getItem('__monthly_mock_db')||'[]');m.data.transactions[0].date='2026-10-02';m.data.transactions[0].amount=321.25;m.data.transactions.push({...m.data.transactions[0],id:2,date:'2026-09-25',amount:44,description:'September only'});window.supabase={createClient:()=>sb};""")
    page.add_init_script(mock)
    freeze(page, day)
    updated(page)
    return page.locator('.side-pname' if page.viewport_size['width'] >= 1024 else '.pp-t').inner_text()


def edit(page, total='1000', food='400'):
    page.locator('.bud-alloc').get_by_role('button', name='Розподіл бюджету').click()
    sheet=page.get_by_role('dialog', name='Розподіл бюджету місяця')
    sheet.locator('#monthly-total').fill(total)
    sheet.get_by_role('textbox', name='Продукти, ₴', exact=True).fill(food)
    return sheet


def save(page, sheet):
    sheet.get_by_role('button', name='Зберегти місячний бюджет').click()
    page.wait_for_function("!document.querySelector('.monthly-editor')")
    updated(page)


def contract(page):
    overview=mount(page)
    go_tab(page,1)
    check(page.locator('.p-budget').get_attribute('data-month')=='2026-10-01','1–5th must start current calendar month')
    check(page.locator('.bud-pool .bud-kpi-v').inner_text()=='Не задано','missing plan mistaken for zero')
    check(num(page.locator('.bud-spent .bud-kpi-v').inner_text())==321.25,'monthly fact excludes previous payout month')
    save(page,edit(page))
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==1000,'manual monthly total')
    check(num(page.locator('.bud-day .bud-kpi-v').inner_text())==600,'unallocated sum')
    check(num(page.locator('.bud-avail .bud-kpi-v').inner_text())==678.75,'remaining sum')
    expand_groups(page)
    row=page.locator('.bud-cat[data-cat="1"]')
    check('78,75' in row.inner_text(),'category remaining incorrect')
    row.click()
    check(page.locator('.cat-op').count()==1,'drawer leaked previous month')
    check(page.locator('.cat-lim-seg').count()==0,'monthly category exposed period percentage')
    page.locator('#cat-lim-v').fill('500.25')
    page.locator('.cat-lim-save').click()
    page.wait_for_function("__liveMock.data.monthly_budgets[0].allocations['1']===50025")
    page.locator('.cat-to-flow').click()
    check('Initial mock row' in page.locator('.p-flow').inner_text() and 'September only' not in page.locator('.p-flow').inner_text(),'drilldown month boundary')
    arrow='.dper' if page.viewport_size['width']>=1024 else '.per-pill'
    page.locator(arrow).get_by_role('button',name='Попередній період',exact=True).click()
    page.wait_for_function("document.querySelector('.p-flow').textContent.includes('September only')")
    go_tab(page,1)
    page.wait_for_function("document.querySelector('.bud-spent .bud-kpi-v')&&document.querySelector('.bud-spent .bud-kpi-v').textContent.includes('321')")
    check(num(page.locator('.bud-spent .bud-kpi-v').inner_text())==321.25,'return from other Flow month did not reload Budget')
    expand_groups(page)
    page.locator('.bud-cat[data-cat="1"]').click()
    page.locator('.cat-to-flow').click()
    if page.viewport_size['width']>=1024:
        page.locator('.flow-scope').get_by_role('button',name='Період',exact=True).click()
        check('Період' in page.locator('.flow-scope button.on').inner_text(),'Flow period scope stuck after monthly drilldown')
    else:
        page.locator('.pp-mid').click()
        page.get_by_role('button',name='Між виплатами',exact=True).click()
        page.get_by_role('dialog',name='Період',exact=True).get_by_role('button',name='×',exact=True).click()
    check('September only' in page.locator('.p-flow').inner_text() and 'Initial mock row' in page.locator('.p-flow').inner_text(),'Flow period label does not match crossmonth operation boundaries')
    go_tab(page,0)
    check(page.locator('.side-pname' if page.viewport_size['width']>=1024 else '.pp-t').inner_text()==overview,'Budget changed Overview period')
    go_tab(page,1)
    arrow='.dper' if page.viewport_size['width']>=1024 else '.per-pill'
    page.locator(arrow).get_by_role('button',name='Наступний період',exact=True).click()
    page.wait_for_function("document.querySelector('.p-budget').dataset.month==='2026-11-01'")
    updated(page)
    check(page.locator('.bud-pool .bud-kpi-v').inner_text()=='Не задано','next month inherited saved plan')
    save(page,edit(page,'2000','800'))
    page.locator(arrow).get_by_role('button',name='Попередній період',exact=True).click()
    updated(page)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==1000,'another month overwrote original plan')
    page.evaluate("__liveMock.data.categories[0].budget_limit=999;__liveMock.event('categories')")
    updated(page)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==1000,'forecast weights affected month')
    line=page.locator('.bud-plan')
    check(line.get_attribute('y1')==line.get_attribute('y2'),'monthly limit is not horizontal')
    check(page.evaluate("__liveMock.writes.every(x=>x.table==='monthly_budgets')"),'monthly editor wrote forecast settings')
    shot(page,'monthly-budget-'+str(page.viewport_size['width'])+'.jpg')
    sheet=edit(page)
    shot(page,'monthly-editor-'+str(page.viewport_size['width'])+'.jpg')
    sheet.get_by_role('button',name='Закрити',exact=True).click()
    page.reload()
    page.wait_for_selector('.side' if page.viewport_size['width']>=1024 else '.tab-bar')
    updated(page)
    go_tab(page,1)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==1000,'saved month lost after app reload')
    expand_groups(page)
    page.locator('.bud-cat[data-cat="1"]').click()
    check(page.locator('#cat-lim-v').input_value()=='500.25','saved category allocation lost after app reload')
    check(page.evaluate('__liveMock.writes.length')==0,'app reload wrote defaults over saved month')


def errors(page):
    mount(page)
    go_tab(page,1)
    sheet=edit(page,'100','101')
    sheet.get_by_role('button',name='Зберегти місячний бюджет').click()
    check('перевищують' in sheet.get_by_role('alert').inner_text(),'overallocate accepted')
    check(page.evaluate('__liveMock.writes.length')==0,'invalid plan written')
    sheet.locator('#monthly-total').fill('1000')
    page.evaluate('__liveMock.failWrite=true')
    sheet.get_by_role('button',name='Зберегти місячний бюджет').click()
    page.wait_for_function("document.querySelector('.monthly-editor [role=alert]').textContent.includes('offline')")
    check(sheet.locator('#monthly-total').input_value()=='1000','failed save lost draft')
    page.evaluate('__liveMock.failWrite=false')
    save(page,sheet)
    page.evaluate("__liveMock.data.monthly_budgets[0].total_cents=123400;__liveMock.event('monthly_budgets')")
    page.wait_for_function("document.querySelector('.bud-pool .bud-kpi-v').textContent.includes('1 234')||document.querySelector('.bud-pool .bud-kpi-v').textContent.replace(/\\s/g,'').includes('1234')")
    updated(page)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==1234,'realtime month plan not refreshed')
    sheet=edit(page,'0','0')
    save(page,sheet)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==0,'explicit zero treated as unset')


def pending(page):
    mount(page)
    go_tab(page,1)
    save(page,edit(page))
    page.evaluate("__liveMock.data.monthly_budgets.push({month_start:'2026-11-01',total_cents:200000,allocations:{'1':100000}});__liveMock.hold=true")
    page.locator('.dper').get_by_role('button',name='Наступний період',exact=True).click()
    page.wait_for_function('__liveMock.pending.length>0')
    check(page.locator('.p-budget[aria-busy=true]').count()==1,'unloaded month must show loading state')
    page.locator('.dacts .dact').click()
    check(page.locator('.monthly-editor').count()==0,'unloaded month can overwrite saved plan')
    page.evaluate('__liveMock.release()')
    page.wait_for_function("document.querySelector('.bud-pool .bud-kpi-v')&&document.querySelector('.bud-pool .bud-kpi-v').textContent.replace(/\\s/g,'').includes('2000')")
    sheet=edit(page,'2200','1100')
    page.evaluate('__liveMock.holdWrites=true')
    sheet.get_by_role('button',name='Зберегти місячний бюджет').click()
    page.wait_for_function('__liveMock.pendingWrites.length>0')
    page.keyboard.press('Escape')
    check(sheet.count()==1 and sheet.locator('#monthly-total').input_value()=='2200','Escape dismissed pending save')
    page.evaluate('__liveMock.releaseWrites()')
    page.wait_for_function("!document.querySelector('.monthly-editor')")
    updated(page)
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==2200,'pending save not published')


CHECKS=[('monthly_budget: independent calendar, category, save and history desktop','desktop',contract),
        ('monthly_budget: independent calendar, category, save and history mobile','mobile',contract),
        ('monthly_budget: validation, failed draft, realtime and zero','desktop',errors),
        ('monthly_budget: unknown month and pending save guards','desktop',pending)]
