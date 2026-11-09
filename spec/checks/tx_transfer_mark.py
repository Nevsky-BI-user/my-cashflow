from helpers import check, freeze, go_tab, finance_state, shot

# Дохід, записаний як подарунок, позначається переказом з іншого власного рахунку
FIX = "{id:'gift-fixture',date:'2026-10-07',created_at:'2026-10-07T13:00:00Z',amount:18000,type:'income',source:'telegram',account_id:'l2',category_id:null,description:'MOBILE BANKING, OSCHADBANK',categories:{name:'Подарунок'}}"


def mark(page):
    freeze(page, '2026-10-08', [("function txDemo(y,m){", "function txDemo(y,m){if(y===2026&&m===9)return [" + FIX + "];")])
    before = finance_state(page)
    snap0 = before['result']['snapshot']
    facts0 = page.evaluate("budgetRangeFacts(__financeInput.transactions,BCAT,'2026-10-01','2026-11-01','2026-10-08')")
    go_tab(page, 2)
    page.locator('[data-tx-id="gift-fixture"]').first.click()
    btn = page.get_by_role('button', name='Це переказ з мого рахунку')
    check(btn.count() == 1, 'немає кнопки «Це переказ» у вікні доходу')
    btn.click()
    grp = page.get_by_role('group', name='З якого рахунку прийшли гроші')
    check(grp.count() == 1, 'немає вибору рахунку-джерела')
    names = grp.locator('button').all_inner_texts()
    check('ПриватБанк кредитна' not in names and 'Ощадбанк' in names, f'у виборі той самий рахунок або бракує Ощаду: {names}')
    save = page.get_by_role('button', name='Зберегти як переказ')
    check(save.is_disabled(), 'збереження доступне без вибраного рахунку')
    grp.get_by_role('button', name='Ощадбанк', exact=True).click()
    box = page.locator('.tx-transfer-box').bounding_box()
    check(box['x'] >= 0 and box['x'] + box['width'] <= page.viewport_size['width'], 'блок переказу виходить за екран')
    shot(page, 'tx-transfer-mark-' + str(page.viewport_size['width']), full=False)
    save.click()
    page.wait_for_timeout(400)
    state = finance_state(page)
    legs = [t for t in state['data']['transactions'] if t.get('transfer_id')]
    check(len(legs) == 2 and legs[0]['transfer_id'] == legs[1]['transfer_id'], f'переказ не записано парою: {legs}')
    out = next((t for t in legs if t['type'] == 'expense'), None)
    check(out is not None and str(out['account_id']) == 'l1' and float(out['amount']) == 18000, f'немає списання з Ощаду: {legs}')
    check(sum(float(t['amount']) * (1 if t['type'] == 'income' else -1) for t in legs) == 0, 'пара незбалансована')
    snap1 = state['result']['snapshot']
    check(snap1['creditDebtCents'] == snap0['creditDebtCents'], 'борг кредитки змінився')
    check(snap1['cashCents'] == snap0['cashCents'] - 1800000, f"власні кошти мали зменшитись на 18 000: {snap0['cashCents']} -> {snap1['cashCents']}")
    facts1 = page.evaluate("budgetRangeFacts(__financeInput.transactions,BCAT,'2026-10-01','2026-11-01','2026-10-08')")
    check(facts1.get('expense') == facts0.get('expense'), 'переказ потрапив у витрати бюджету')
    page.locator('[data-tx-id="gift-fixture"]').first.click()
    check(page.get_by_role('button', name='Це переказ з мого рахунку').count() == 0, 'переказ знову пропонує позначитись переказом')


CHECKS = [('mark income as transfer desktop', 'desktop', mark), ('mark income as transfer mobile', 'mobile', mark)]
