from helpers import check, freeze, go_tab, dialog, finance_state, touch_drag, num
from checks.live_refresh import MOCK, updated


def transfer(page):
    freeze(page,'2026-10-21',[("mono_account_id:'demo-mono',",'')])
    before=finance_state(page)['result']
    go_tab(page,2)
    page.get_by_role('button',name='Переказ',exact=True).click()
    d=dialog(page,'Переказ між рахунками')
    d.get_by_label('З рахунку',exact=True).select_option('l1')
    d.get_by_label('На рахунок',exact=True).select_option('l3')
    d.get_by_label('Сума переказу',exact=True).fill('250')
    d.get_by_role('button',name='Записати переказ',exact=True).click()
    page.wait_for_function("__financeInput.transactions.filter(t=>t.transfer_id).length===2")
    after=finance_state(page)['result']
    check(after['snapshot']['positiveOwnCents']==before['snapshot']['positiveOwnCents'],'переказ змінив загальні власні кошти')
    check(after['currentPeriod']['actualVariableCents']==before['currentPeriod']['actualVariableCents'],'переказ потрапив у витрати')
    legs=page.locator('[data-tx-id]');check(legs.filter(has_text='Переказ на monobank').count()==1,'немає списання з контрагентом')
    check(legs.filter(has_text='Переказ з Ощадбанк').count()==1,'немає зарахування з контрагентом')
    legs.filter(has_text='Переказ на monobank').click()
    check(dialog(page,'Переказ').count()==1,'не відкрилася спільна операція')
    check(dialog(page,'Переказ').locator('select,input').count()==0,'пару дозволено незалежно редагувати')


def row_ids(d): return d.locator('.account-order-row').evaluate_all('(rows)=>rows.map(x=>x.dataset.accountId)')
def open_order(page):
    page.get_by_role('button',name='Порядок карток',exact=True).click()
    # нативний <dialog>: роль неявна, тому шукаємо за роллю, а не за атрибутом [role=dialog]
    return page.get_by_role('dialog',name='Порядок карток',exact=True)


def ordering(page):
    freeze(page,'2026-10-21')
    d=open_order(page);original=row_ids(d)
    source=d.locator('.account-order-handle').first.bounding_box();target=d.locator('.account-order-row').nth(2).bounding_box()
    x=source['x']+source['width']/2;y=source['y']+source['height']/2;end=target['y']+target['height']/2
    if page.viewport_size['width']<1024: touch_drag(page,x,y,x,end,after=100)
    else:
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x,end,steps=15);page.mouse.up()
    wanted=[original[1],original[2],original[0]]
    check(row_ids(d)==wanted,'перетягування не змінило порядок')
    check(page.locator('.account-history-sheet').count()==0,'перетягування відкрило рахунок')
    d.get_by_role('button',name='Зберегти порядок',exact=True).click()
    page.wait_for_function("!document.querySelector('.account-order-dialog')")
    page.reload();page.wait_for_selector('.side' if page.viewport_size['width']>=1024 else '.tab-bar')
    check(page.evaluate('__financeInput.accounts.map(a=>String(a.id))')==wanted,'порядок не пережив reload')
    d=open_order(page)
    d.get_by_role('button',name='Підняти Ощадбанк',exact=True).focus();page.keyboard.press('Enter')
    check(row_ids(d)==[original[1],original[0],original[2]],'клавіатура не підняла картку')
    d.get_by_role('button',name='Скасувати',exact=True).click()
    check(page.evaluate('__financeInput.accounts.map(a=>String(a.id))')==wanted,'Скасувати змінило порядок')
    go_tab(page,2);page.get_by_role('button',name='Переказ',exact=True).click()
    options=dialog(page,'Переказ між рахунками').get_by_label('З рахунку',exact=True).locator('option').evaluate_all('(rows)=>rows.map(x=>x.value).filter(Boolean)')
    check(options==wanted,'селектор не застосував порядок карток')


def rollback(page):
    mock=MOCK.replace("window.supabase={createClient:()=>sb};", """m.data.accounts.push({...m.data.accounts[0],id:2,name:'Second',sort_order:1},{...m.data.accounts[0],id:3,name:'Third',sort_order:2});m.data.accounts=JSON.parse(localStorage.getItem('__order_accounts')||'null')||m.data.accounts;m.orderFail=true;sb.rpc=async(name,args)=>{m.writes.push({rpc:name,args});if(m.orderFail)return{error:{message:'Synthetic order failure'}};m.data.accounts=args.p_account_ids.map((id,i)=>({...m.data.accounts.find(a=>a.id===id),sort_order:i}));localStorage.setItem('__order_accounts',JSON.stringify(m.data.accounts));return{data:null,error:null}};window.supabase={createClient:()=>sb};""")
    page.add_init_script(mock);freeze(page,'2026-10-21',[("if(!sb){window.__financeProjection=","{window.__financeProjection=")]);updated(page)
    d=open_order(page);d.get_by_role('button',name='Опустити Synthetic cash',exact=True).click();d.get_by_role('button',name='Зберегти порядок',exact=True).click()
    page.wait_for_selector('.account-order-dialog [role=alert]')
    check(page.evaluate('__financeInput.accounts.map(a=>a.id)')==[1,2,3],'помилка RPC не відкотила порядок')
    check('Попередній порядок відновлено' in d.inner_text(),'немає пояснення відкату')
    page.evaluate('__liveMock.orderFail=false')
    d.get_by_role('button',name='Зберегти порядок',exact=True).click();page.wait_for_function("!document.querySelector('.account-order-dialog')")
    page.wait_for_function('__financeInput.accounts[0].id===2')
    page.reload();updated(page)
    check(page.evaluate('__financeInput.accounts.map(a=>a.id)')==[2,1,3],'збережений серверний порядок втрачено')


def _sum_bar(page):
    import re
    t=page.locator('.flow-sum').inner_text()
    m=re.search(r'витрати\s+(.+?)\s*₴\s*·\s*доходи\s+(.+?)\s*₴\s*·\s*разом\s+(.+?)\s*₴',t)
    check(m,f'не розібрано підсумок {t!r}')
    return [num(x) for x in m.groups()]


def _shown(page):
    # підсумок рядків, які видно в таблиці (без плану)
    rows=page.locator('.flow-table [data-tx-id] .flow-amt').all_inner_texts()
    return [num(x) for x in rows]


def flow_totals(page):
    freeze(page,'2026-10-21',[("mono_account_id:'demo-mono',",'')])
    go_tab(page,2)
    page.get_by_role('button',name='Переказ',exact=True).click()
    d=dialog(page,'Переказ між рахунками')
    d.get_by_label('З рахунку',exact=True).select_option('l1')
    d.get_by_label('На рахунок',exact=True).select_option('l3')
    d.get_by_label('Сума переказу',exact=True).fill('250')
    d.get_by_role('button',name='Записати переказ',exact=True).click()
    page.wait_for_function("__financeInput.transactions.filter(t=>t.transfer_id).length===2")
    out,inc,net=_sum_bar(page)
    shown=_shown(page)
    plain=[v for v in shown]
    # без фільтра переказ не входить у підсумок: разом = доходи − витрати, а обидві ноги переказу виключені
    check(abs(net-(inc+out))<0.01 and abs(net-(inc-abs(out)))<0.01,f'разом не сходиться {out} {inc} {net}')
    legs=sum(num(x) for x in page.locator('.flow-table [data-tx-id]').filter(has_text='Переказ').locator('.flow-amt').all_inner_texts())
    check(abs(sum(plain)-legs-net)<0.01,f'без фільтра: разом {net} ≠ рядки {sum(plain)} без переказу {legs}')
    # фільтр по рахунку-джерелу: переказ рахується, підсумок = сума показаних рядків
    page.locator('.flow-srcs .flow-chip').filter(has_text='Ощад').first.click()
    page.wait_for_timeout(200)
    out,inc,net=_sum_bar(page)
    shown=_shown(page)
    check(abs(sum(shown)-net)<0.01,f'з фільтром: разом {net} ≠ сума рядків {sum(shown)}')
    check(any(abs(v+250)<0.01 for v in shown) and abs(out)>=250,f'з фільтром переказ не в витратах {shown} {out}')
    days=page.locator('.flow-table .flow-day').all_inner_texts()
    check(days,'немає підсумків днів')


CHECKS=[('Operations debit transfer desktop','desktop',transfer),('Operations debit transfer mobile','mobile',transfer),('card ordering mouse keyboard save reload','desktop',ordering),('card ordering touch keyboard save reload','mobile',ordering),('card ordering RPC rollback and reload','desktop',rollback),('Потік: переказ у підсумку лише з фільтром рахунку','desktop',flow_totals)]
