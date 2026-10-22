from helpers import check, freeze, dialog
from checks.live_refresh import MOCK, updated


def salary_account(page):
    mock=MOCK.replace("window.supabase={createClient:()=>sb};", "m.data.categories=[{id:1,name:'Зарплата',type:'income',is_income:true},{id:2,name:'Премія',type:'income',is_income:true}];m.data.transactions=[{id:71,account_id:1,type:'income',amount:500,date:'2026-10-15',created_at:'2026-10-15T10:00:00Z',source:'telegram',description:'Підтверджена зарплата тест',category_id:1,salary:[{transaction_id:71}],categories:{name:'Зарплата'}}];window.supabase={createClient:()=>sb};")
    page.add_init_script(mock)
    freeze(page,'2026-10-15')
    updated(page)
    if page.viewport_size['width']>=1024: page.get_by_role('button',name='Рахунок Synthetic cash',exact=True).click()
    else:
        card=page.locator('.o-bank-card',has_text='Synthetic cash');card.focus();card.click()
    page.locator('.account-history-row',has_text='Підтверджена зарплата тест').click()
    d=dialog(page,'Операція')
    buttons=d.locator('.drw-acc .acc-seg button')
    check(buttons.count()>0 and all(buttons.nth(i).is_disabled() for i in range(buttons.count())),'рахунок підтвердженої зарплати можна змінити')
    check('Рахунок підтвердженої зарплати змінити не можна' not in d.inner_text(),'v183: лишилось речення-пояснення обмеження')
    cat=d.locator('select').first
    check(cat.is_enabled(),'категорію заблоковано разом із рахунком')
    cat.select_option('2')
    d.get_by_role('button',name='Зберегти',exact=True).click()
    page.wait_for_function("__liveMock.data.transactions[0].category_id===2")
    check(page.evaluate("__liveMock.data.transactions[0].account_id") == 1,'рахунок змінився під час збереження категорії')
    check(page.evaluate("__liveMock.writes.filter(x=>x.table==='transactions').every(x=>!x.ops.some(o=>o[0]==='update'&&'account_id' in o[1]))"),'надіслано зміну рахунку')

CHECKS=[('salary account locked category editable desktop','desktop',salary_account),('salary account locked category editable mobile','mobile',salary_account)]
