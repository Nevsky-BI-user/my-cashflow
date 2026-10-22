from helpers import check, freeze, dialog, finance_state


def open_transfer(page):
    if page.viewport_size['width']>=1024:
        page.get_by_role('button',name='Рахунок ПриватБанк кредитна',exact=True).click()
    else:
        card=page.locator('.o-bank-card',has_text='ПриватБанк кредитна')
        while card.get_attribute('aria-current')!='true':
            page.locator('.o-stack-item[aria-hidden=false] button').first.focus();page.keyboard.press('ArrowRight');page.wait_for_timeout(500)
        card.click()
    page.get_by_role('button',name='Погасити з картки',exact=True).click()
    d=dialog(page,'Погашення з картки')
    check(d.count()==1,'форма не відкрилась')
    return d


def repayment(page):
    freeze(page,'2026-10-08')
    before=finance_state(page)['result']['snapshot']
    d=open_transfer(page)
    d.locator('[aria-label="Сума переказу"]').fill('1000')
    d.locator('.transfer-save').click()
    page.wait_for_timeout(400)
    state=finance_state(page);after=state['result']['snapshot'];legs=[t for t in state['data']['transactions'] if t.get('transfer_id')]
    check(len(legs)==2 and legs[0]['transfer_id']==legs[1]['transfer_id'],'переказ не записаний парою')
    check(after['cashCents']==before['cashCents']-100000,'власні кошти не зменшилися рівно на 1000')
    check(after['creditDebtCents']==before['creditDebtCents']-100000,'борг не зменшився рівно на 1000')
    check(sum(t['amount']*(1 if t['type']=='income' else -1) for t in legs)==0,'пара незбалансована')
    # History is account-scoped and transfer opens a read-only record.
    if page.viewport_size['width']>=1024: page.get_by_role('button',name='Рахунок ПриватБанк кредитна',exact=True).click()
    else:
        card=page.locator('.o-bank-card',has_text='ПриватБанк кредитна')
        while card.get_attribute('aria-current')!='true':
            page.locator('.o-stack-item[aria-hidden=false] button').first.focus();page.keyboard.press('ArrowRight');page.wait_for_timeout(500)
        card.click()
    row=page.locator('.account-history-row',has_text='Переказ з Ощадбанк')
    check(row.count()==1,'немає контрагента у історії')
    row.click()
    check(dialog(page,'Переказ').count()==1,'переказ не відкрився')
    check(dialog(page,'Переказ').locator('select,input').count()==0,'переказ дозволяє редагувати одну сторону')


def invalid_and_surplus(page):
    freeze(page,'2026-10-08',[("kind:'debit',balance:5000,debt:0","kind:'debit',balance:50000,debt:0")])
    history_js="balancePast(__financeProjection,__financeInput.transactions,__financeInput.accounts.map(a=>String(a.id)).concat(['']),__financeInput.accounts.filter(a=>a.kind!=='credit').map(a=>String(a.id)).concat(['']),'2026-10-07','2026-10-08',__financeInput.accounts)"
    history_before=page.evaluate(history_js)
    d=open_transfer(page)
    d.locator('[aria-label="Сума переказу"]').fill('999999')
    d.locator('.transfer-save').click()
    check('Недостатньо власних коштів' in d.inner_text(),'недостатні власні кошти не заблоковано')
    d.locator('[aria-label="Сума переказу"]').fill('11000')
    d.locator('.transfer-save').dblclick()
    page.wait_for_timeout(400)
    state=finance_state(page)
    target=next(a for a in state['result']['snapshot']['accounts'] if a['id']=='l2')
    check(target['debtCents']==0 and target['balanceCents']==100000,'переплата не стала власними коштами')
    check(len([t for t in state['data']['transactions'] if t.get('transfer_id')])==2,'подвійне натискання створило другий переказ')
    history_after=page.evaluate(history_js)
    check(history_after[0]['own']==history_before[0]['own'],'переплата змінила власні кошти до переказу')
    check(history_after[0]['cents']==history_before[0]['cents'],'переказ змінив історичний чистий баланс')

CHECKS=[('repayment account history desktop','desktop',repayment),('repayment account history mobile','mobile',repayment),('insufficient own and surplus','desktop',invalid_and_surplus)]

def imported_mono(page):
    seed="add:[{id:'mono-transfer-test',account_id:'l3',source:'mono',type:'expense',amount:1000,date:'2026-10-08',created_at:'2026-10-08T10:00:00Z',description:'Банківський переказ'}],del:{}"
    freeze(page,'2026-10-08',[("add:[],del:{}",seed)])
    d=open_transfer(page)
    d.locator('[aria-label="З рахунку"]').select_option('l3')
    d.locator('[aria-label="Сума переказу"]').fill('1000')
    d.locator('.transfer-save').click()
    check('оберіть відповідну імпортовану операцію' in d.inner_text(),'Monobank допускає повторний ручний запис')
    d.locator('[aria-label="Списання Monobank"]').select_option('mono-transfer-test')
    d.locator('.transfer-save').click()
    page.wait_for_timeout(400)
    txs=finance_state(page)['data']['transactions']
    linked=[t for t in txs if t.get('transfer_id')]
    check(len(linked)==2,'імпорт не привʼязаний до другої сторони')
    check(len([t for t in linked if t['account_id']=='l3'])==1,'створено дубль імпортованого списання')
    check(next(t for t in linked if t['account_id']=='l3')['id']=='mono-transfer-test','імпорт замінений новим записом')


def salary_tips(page):
    freeze(page,'2026-10-21',[("kind:'debit',balance:5000,debt:0","kind:'debit',balance:50000,debt:0")])
    tips=page.locator('.repayment-tips')
    check(tips.count()==1,'немає підказки погашення у день виплати')
    check('Ощадбанк → ПриватБанк кредитна' in tips.inner_text(),'немає конкретного джерела та отримувача')
    tips.get_by_role('button',name='Записати погашення').first.click()
    d=dialog(page,'Погашення з картки')
    check(d.locator('[aria-label="З рахунку"]').input_value()=='l1','підказка не підставила джерело')
    check(d.locator('[aria-label="На кредитну картку"]').input_value()=='l2','підказка не підставила кредитку')
    check(float(d.locator('[aria-label="Сума переказу"]').input_value())>0,'підказка не підставила суму')

CHECKS += [('link imported Mono without duplicate','desktop',imported_mono),('salary day actionable tip desktop','desktop',salary_tips),('salary day actionable tip mobile','mobile',salary_tips)]
