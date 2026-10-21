from helpers import check, dialog, freeze, go_tab, finance_state


def annual_form(page):
    freeze(page, '2026-10-08')
    go_tab(page, 3)
    if page.viewport_size['width'] >= 1024:
        page.click('.dact')
    else:
        page.evaluate("()=>{const b=[...document.querySelectorAll('button')].filter(x=>getComputedStyle(x).position==='fixed'&&!x.closest('.tab-bar'));b[b.length-1].click()}")
    d=dialog(page,'Платежі')
    if d.locator('[aria-label="Тип платежів"]').count():
        d.locator('[aria-label="Тип платежів"] button',has_text='Постійні').click()
    d.locator('button',has_text='Claude').first.click()
    d.locator('[aria-label="Періодичність"] button',has_text='Щороку').click()
    d.locator('[aria-label="Місяць платежу"]').select_option('11')
    d.get_by_role('button',name='Зберегти',exact=True).click()
    page.wait_for_timeout(350)
    state=finance_state(page)
    fixed=next(x for x in state['data']['fixed'] if x['name']=='Claude')
    check(fixed['period']=='year' and fixed['month_of_year']==11,'щорічний розклад не збережено')
    events=[e for e in state['result']['events'] if e['occurrenceId'].startswith('fixed:f3:')]
    check(events and all(e['date'][5:7]=='11' for e in events),'щорічний платіж зʼявився поза листопадом')


def early_payment(page):
    freeze(page,'2026-12-08')
    go_tab(page,2)
    check(page.evaluate("""()=>{for(const b of document.querySelectorAll('.pay-done')){let e=b;while(e&&e.querySelectorAll('.pay-done').length<=1){if(e.textContent.includes('Садочок')){b.click();return true}e=e.parentElement}}return false}"""),'немає кнопки оплати')
    d=dialog(page,'Нова операція')
    check(d.locator('[aria-label="Дата фактичної оплати"]').input_value()=='2026-12-08','фактична дата не сьогодні')
    d.locator('[aria-label="Планова дата платежу"]').fill('2027-01-10')
    d.locator('.acc-seg button[data-acc="l1"]').click()
    d.locator('.tx-save').click()
    page.wait_for_timeout(650)
    state=finance_state(page)
    tx=next(t for t in state['data']['transactions'] if t.get('fixed_id')=='f2')
    check(tx['date']=='2026-12-08' and tx['payment_due_date']=='2027-01-10','дата факту або планова дата втрачена')
    ids=[e['occurrenceId'] for e in state['result']['events']]
    check('fixed:f2:2026-12' in ids,'грудень помилково закрито оплатою січня')
    check('fixed:f2:2027-01' not in ids,'січень не закрито достроковою оплатою')
    go_tab(page,3)
    if page.viewport_size['width'] < 1024:
        page.locator('.cal-cell[data-date="2026-12-08"]').click()
        check(page.locator('.cm-details .fx-paid').count()>0,'early payment missing from actual calendar day')
    else:
        check(any('\u0441\u043f\u043b\u0430\u0447\u0435\u043d\u043e' in t for t in page.locator('.cal-ev',has_text='\u0421\u0430\u0434\u043e\u0447\u043e\u043a').all_inner_texts()),'early payment missing from actual calendar month')

CHECKS=[('annual create/edit desktop','desktop',annual_form),('annual create/edit mobile','mobile',annual_form),('early Dec to Jan desktop','desktop',early_payment),('early Dec to Jan mobile','mobile',early_payment)]

def correct_existing(page):
    freeze(page,'2026-10-08')
    go_tab(page,2)
    rows=page.locator('.flow-row[data-tx-id], [data-tx-id]')
    check(rows.count()>0,'немає звичайної операції')
    chosen=page.evaluate("""()=>{const t=window.__financeInput.transactions.find(t=>t.type==='expense'&&!t.fixed_id&&!t.credit_id&&t.date>='2026-10-01'&&t.date<='2026-10-08');return t&&{id:t.id,date:t.date}}""")
    check(chosen is not None,'немає фікстури витрати')
    page.locator('[data-tx-id="'+str(chosen['id'])+'"]').first.click()
    page.locator('select[aria-label="Постійний платіж"]').select_option('f3')
    page.wait_for_timeout(350)
    page.locator('[aria-label="Планова дата платежу"]').fill('2026-11-12')
    page.wait_for_timeout(350)
    tx=next(t for t in finance_state(page)['data']['transactions'] if str(t['id'])==str(chosen['id']))
    check(tx.get('fixed_id')=='f3' and tx.get('payment_due_date')=='2026-11-12','привʼязка наявної витрати не збереглася')
    check(tx['date']==chosen['date'],'перепривʼязка змінила фактичну дату')

CHECKS += [('correct existing Claude expense desktop','desktop',correct_existing),('correct existing Claude expense mobile','mobile',correct_existing)]

def invalid_occurrence(page):
    freeze(page,'2026-10-08')
    go_tab(page,2)
    page.evaluate("""()=>{for(const b of document.querySelectorAll('.pay-done')){let e=b;while(e&&e.querySelectorAll('.pay-done').length<=1){if(e.textContent.includes('Садочок')){b.click();return}e=e.parentElement}}}""")
    d=dialog(page,'Нова операція')
    d.locator('[aria-label="Планова дата платежу"]').fill('')
    # Clearing a date preserves the last valid selection; arbitrary browser input never writes an invalid date.
    d.locator('[aria-label="Планова дата платежу"]').fill('2026-11-30')
    check(d.locator('[aria-label="Планова дата платежу"]').input_value()=='2026-11-10','планова дата не нормалізована до дня розкладу')

CHECKS += [('occurrence date follows schedule','desktop',invalid_occurrence)]
