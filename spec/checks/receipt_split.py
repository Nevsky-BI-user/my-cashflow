from helpers import check, freeze, go_tab, shot, expand_groups


def mount(page, amount=1000):
    freeze(page, '2026-10-08', [("function txDemo(y,m){", "function txDemo(y,m){if(y===2026&&m===9)return [{id:'split-fixture',date:'2026-10-07',amount:"+str(amount)+",type:'expense',source:'manual',account_id:'l1',category_id:'food',description:'Тестовий чек',categories:{name:'Продукти'}}];")])
    go_tab(page, 2)
    page.locator('[data-tx-id="split-fixture"]').first.click()
    page.get_by_role('button', name='Розподілити чек', exact=True).click()
    return page.get_by_role('dialog', name='Розподіл чека', exact=True)


def split_and_merge(page):
    d=mount(page)
    before=page.evaluate('__financeProjection.snapshot.cashCents')
    d.get_by_label('Сума позиції 1', exact=True).fill('600,00')
    d.get_by_label('Категорія позиції 2', exact=True).select_option('health')
    d.get_by_label('Сума позиції 2', exact=True).fill('401')
    check(d.get_by_role('button', name='Зберегти розподіл').is_disabled(), 'oversum allowed')
    check('Зайві 1' in d.inner_text(), 'missing overage')
    d.get_by_label('Сума позиції 2', exact=True).fill('400')
    d.get_by_label('Назва позиції 2', exact=True).fill('Ліки')
    check(d.locator('optgroup').count()>0,'category groups missing')
    d.get_by_label('Пошук категорії чи групи').fill('Здоров')
    check(d.get_by_label('Категорія позиції 2',exact=True).locator('option[value=health]').count()==1,'search lost selected category')
    d.get_by_label('Пошук категорії чи групи').fill('')
    box=d.bounding_box();footer=d.locator('footer').bounding_box()
    check(box['x']>=0 and box['x']+box['width']<=page.viewport_size['width'],'horizontal overflow')
    check(footer['height']<110,'oversized sticky footer')
    shot(page,'receipt-split-'+str(page.viewport_size['width']),full=False)
    d.get_by_role('button',name='Зберегти розподіл').click()
    d.wait_for(state='hidden')
    check(page.evaluate('__financeProjection.snapshot.cashCents')==before,'split changed bank cash')
    facts=page.evaluate("budgetRangeFacts(__financeInput.transactions,BCAT,'2026-10-01','2026-11-01','2026-10-08')")
    check(facts['byCategory']['food']==60000 and facts['byCategory']['health']==40000,'wrong category sums')
    check(facts['expense']==100000,'cash duplicated')
    check(page.locator('[data-tx-id="split-fixture"]').count()==1,'operation duplicated')
    if page.viewport_size['width']>=1024:
        page.keyboard.press('Escape')
        page.locator('.flow-cats').get_by_role('button',name='Здоров',exact=False).click()
        row=page.locator('[data-tx-id="split-fixture"]')
        check('400' in row.inner_text(),'selected category not limited to portion')
        row.click();check('1 000' in page.locator('.drw-amt').inner_text().replace('\u00a0',' '),'filtered row did not open parent amount')
        page.keyboard.press('Escape');page.locator('.flow-cats').get_by_role('button',name='Усі',exact=True).click()
        go_tab(page,0)
        check(page.locator('[data-tx-id="split-fixture"]').count()==1,'overview duplicated receipt')
        go_tab(page,1);expand_groups(page);page.locator('.bud-cat[data-cat=health]').click()
        check('400' in page.locator('.cat-op').inner_text(),'category drawer shows full parent instead of portion')
        page.locator('.cat-op').click();check('1 000' in page.locator('.drw-amt').inner_text().replace('\u00a0',' '),'category drawer did not open parent')
    page.get_by_role('button',name='Редагувати розподіл',exact=True).click()
    d=page.get_by_role('dialog',name='Розподіл чека',exact=True)
    check(d.get_by_label('Сума позиції 2',exact=True).input_value()=='400.00','edit lost saved split')
    d.get_by_role('button',name='Об’єднати в одну категорію').click()
    d.get_by_label('Єдина категорія',exact=True).select_option('health')
    d.get_by_role('button',name='Зберегти розподіл').click()
    d.wait_for(state='hidden')
    facts=page.evaluate("budgetRangeFacts(__financeInput.transactions,BCAT,'2026-10-01','2026-11-01','2026-10-08')")
    parent=page.get_by_role('dialog',name='Операція',exact=True)
    check((parent.get_by_label('Категорія',exact=True) if page.viewport_size['width']>=1024 else parent.locator('select').last).input_value()=='health','merge left old category input')
    check(parent.get_by_role('button',name='Зберегти',exact=True).is_disabled(),'merge left destructive save enabled')
    check(facts['byCategory']['health']==100000 and not facts['byCategory'].get('food'),'merge wrong')
    check(page.evaluate('__financeProjection.snapshot.cashCents')==before,'merge changed cash')


def thirds_keyboard(page):
    d=mount(page,1000.01)
    d.get_by_role('button',name='+ Додати позицію').click()
    d.get_by_label('Категорія позиції 2',exact=True).select_option('food')
    d.get_by_label('Категорія позиції 3',exact=True).select_option('food')
    d.get_by_role('button',name='Розділити порівну').click()
    check([d.get_by_label('Сума позиції '+str(i),exact=True).input_value() for i in (1,2,3)]==['333.34','333.34','333.33'],'thirds not exact')
    save=d.get_by_role('button',name='Зберегти розподіл');save.focus();page.keyboard.press('Tab')
    check(d.evaluate('(el)=>el.contains(document.activeElement)'),'focus escaped')
    page.evaluate("()=>{window.__originalConfirm=window.confirm;window.__confirmCalls=[];window.confirm=message=>{window.__confirmCalls.push(message);return false}} ");page.keyboard.press('Escape')
    check(d.is_visible(),'dirty draft discarded')
    calls=page.evaluate('__confirmCalls')
    check(len(calls)==1 and 'без збереження' in calls[0],'dirty confirmation mismatch: '+str(calls))
    page.evaluate('()=>{window.confirm=window.__originalConfirm}')
    save.click();d.wait_for(state='hidden')
    check(page.evaluate("__financeInput.transactions.find(t=>t.id==='split-fixture').expense_allocations.length")==3,'repeated categories collapsed')


CHECKS=[('split and merge desktop','desktop',split_and_merge),('split and merge mobile','mobile',split_and_merge),('exact thirds keyboard dirty guard','desktop',thirds_keyboard)]


def mount_rpc(page):
    from checks.live_refresh import MOCK, updated
    mock=MOCK.replace("id:'food'","id:1").replace("category_id:'food'","category_id:1")
    mock=mock.replace('window.supabase={createClient:()=>sb};',r"""
    m.data.categories.push({id:2,name:'Здоров’я',group_id:1,budget_limit:1});m.data.transactions[0].amount=1000;m.data.transactions[0].allocation_revision=0;m.data.transactions[0].expense_allocations=[];
    m.rpcCalls=[];m.rpcFail=null;m.rpcHold=false;m.rpcPending=[];
    sb.rpc=async(name,args)=>{m.rpcCalls.push({name,args});const apply=()=>{if(m.rpcFail)return {error:{message:m.rpcFail,code:'40001'}};const row=m.data.transactions[0];if(row.allocation_revision!==args.p_expected_revision)return {error:{message:'revision conflict',code:'40001'}};Object.assign(row,{expense_allocations:clone(args.p_allocations),allocation_revision:row.allocation_revision+1,auto_categorized:false});if(args.p_category_id!=null)row.category_id=args.p_category_id;return {data:clone(row),error:null}};if(m.rpcHold)return new Promise(resolve=>m.rpcPending.push(()=>resolve(apply())));return apply()};
    window.supabase={createClient:()=>sb};""")
    page.add_init_script(mock);freeze(page,'2026-10-15');updated(page);go_tab(page,2)
    page.locator('[data-tx-id="1"]').first.click();page.get_by_role('button',name='Розподілити чек',exact=True).click()
    d=page.get_by_role('dialog',name='Розподіл чека',exact=True)
    d.get_by_label('Сума позиції 1',exact=True).fill('600');d.get_by_label('Сума позиції 2',exact=True).fill('400');d.get_by_label('Категорія позиції 2',exact=True).select_option('2')
    return d


def rpc_failure_reload(page):
    from checks.live_refresh import updated
    d=mount_rpc(page);page.evaluate("__liveMock.data.transactions[0].expense_allocations=[{category_id:1,amount_cents:50000},{category_id:2,amount_cents:50000}];__liveMock.data.transactions[0].allocation_revision=1")
    d.get_by_role('button',name='Зберегти розподіл').click()
    d.get_by_role('alert').wait_for()
    check('Операцію вже змінено' in d.inner_text(),'conflict message missing')
    check(d.get_by_label('Сума позиції 1',exact=True).input_value()=='600','error erased draft')
    d.get_by_role('button',name='Завантажити актуальний розподіл').click()
    page.wait_for_function("document.querySelector('[aria-label=\"Сума позиції 1\"]').value==='500.00'")
    d.get_by_label('Сума позиції 1',exact=True).fill('600');d.get_by_label('Сума позиції 2',exact=True).fill('400')
    page.evaluate('__liveMock.rpcHold=true');d.get_by_role('button',name='Зберегти розподіл').click()
    page.wait_for_function('__liveMock.rpcPending.length===1')
    page.evaluate("__liveMock.event('transactions')");page.wait_for_timeout(800);updated(page)
    page.evaluate('__liveMock.rpcHold=false;__liveMock.rpcPending.splice(0).forEach(fn=>fn())');d.wait_for(state='hidden');updated(page)
    check(page.evaluate('__liveMock.rpcCalls[0].args.p_expected_revision')==0,'CAS missing')
    check(page.evaluate('__liveMock.rpcCalls[0].args.p_allocations[0].category_id')==1,'RPC id not numeric')
    check(page.evaluate('__liveMock.rpcCalls[1].args.p_expected_revision')==1,'refresh did not update CAS')
    page.get_by_role('button',name='Редагувати розподіл',exact=True).click()
    check(d.get_by_label('Сума позиції 1',exact=True).input_value()=='600.00','successful save left stale open drawer')
    page.keyboard.press('Escape')
    check(page.evaluate("__liveMock.writes.filter(w=>w.table==='categorization_cache').length")==0,'split trained categorization cache')
    page.keyboard.press('Escape');page.locator('[data-tx-id="1"]').first.click()
    check('Здоров’я' in page.locator('.receipt-split-summary').inner_text(),'reload lost split')
    page.evaluate("__liveMock.data.transactions[0].expense_allocations=[{category_id:1,amount_cents:20000},{category_id:2,amount_cents:80000}];__liveMock.data.transactions[0].allocation_revision++;__liveMock.event('transactions')")
    page.wait_for_timeout(900);updated(page);page.keyboard.press('Escape');page.locator('[data-tx-id="1"]').first.click()
    check('800' in page.locator('.receipt-split-summary').inner_text(),'realtime lost external split')


def rpc_auth_pending(page):
    d=mount_rpc(page);page.evaluate('__liveMock.rpcHold=true');d.get_by_role('button',name='Зберегти розподіл').click()
    page.wait_for_function('__liveMock.rpcPending.length===1')
    page.evaluate("__liveMock.auth('SIGNED_OUT',null);__liveMock.rpcPending.splice(0).forEach(fn=>fn())")
    d.wait_for(state='hidden');page.wait_for_timeout(400)
    check(page.get_by_role('dialog',name='Операція',exact=True).count()==0,'stale save restored operation after logout')


CHECKS += [('RPC conflict reload realtime','desktop',rpc_failure_reload),('RPC pending auth switch','desktop',rpc_auth_pending)]
