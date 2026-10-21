"""Карткові реквізити: форма, метадані та різні картки одного банку."""
from helpers import check, dialog


def instrument(page):
    # Лише тестове сховище: перевіряємо реальний saveAccount і відновлення поля.
    def route_handler(route):
        response = route.fetch()
        source = response.text()
        source = source.replace("useState(()=>sb?[]:ACCOUNTS_DEMO)",
                                "useState(()=>JSON.parse(localStorage.getItem('test_cards')||'null')||ACCOUNTS_DEMO)")
        source = source.replace("const[accEdit,setAccEdit]=useState(null);",
                                "window.testAccounts=accounts;useEffect(()=>{localStorage.setItem('test_cards',JSON.stringify(accounts))},[accounts]);const[accEdit,setAccEdit]=useState(null);")
        route.fulfill(response=response, body=source)
    page.route('**/index.html', route_handler)
    page.reload()
    page.locator('.dv-cards .bcard').first.wait_for()


def edit(page, index=0):
    page.locator('.dv-cards .bcard').nth(index).click()
    return dialog(page, 'Рахунок')


def save(d):
    d.get_by_role('button', name='Зберегти', exact=True).click()


def identity(page):
    instrument(page)
    before = page.evaluate('window.testAccounts[0].balance_updated_at')
    d = edit(page)
    field = d.get_by_label('Останні 4 цифри картки', exact=True)
    check(field.get_attribute('inputmode') == 'numeric' and field.get_attribute('type') == 'text', 'Поле має зберігати початкові нулі')
    for bad in ['123', '12345', '12a4', '１２３４']:
        field.fill(bad)
        save(d)
        check(d.get_by_role('alert').count() == 1, 'Прийнято невалідні цифри: ' + bad)
    field.fill('0017')
    save(d)
    check(d.count() == 0, 'Форма не збереглася')
    check(page.evaluate('window.testAccounts[0].balance_updated_at') == before, 'Редагування цифр змінило мітку балансу')
    page.reload()
    d = edit(page)
    check(d.get_by_label('Останні 4 цифри картки').input_value() == '0017', 'Початкові нулі втрачено після перезавантаження')
    d.get_by_label('Останні 4 цифри картки').fill('')
    save(d)
    check(page.evaluate('window.testAccounts[0].card_last4') is None, 'Порожній реквізит не null')
    d = edit(page)
    d.get_by_label('Останні 4 цифри картки').fill('0099')
    d.locator('[role=group][aria-label="Тип"]').get_by_role('button', name='Готівка', exact=True).click()
    check(d.get_by_label('Останні 4 цифри картки').count() == 0, 'Готівка показує карткове поле')
    save(d)
    check(page.evaluate('window.testAccounts[0].card_last4') is None, 'Готівка зберегла номер картки')
    page.locator('.dv-acc-add').click()
    d = dialog(page, 'Рахунок')
    d.locator('input[type=text]').first.fill('Інша картка')
    d.get_by_label('Останні 4 цифри картки').fill('0023')
    save(d)
    page.reload()
    check(page.evaluate("window.testAccounts.find(a=>a.name==='Інша картка').card_last4") == '0023', 'Створення не зберегло реквізит')


def same_bank(page):
    instrument(page)
    for index, suffix in [(0, '0017'), (1, '9234')]:
        d = edit(page, index)
        d.locator('[role=group][aria-label="Банк"]').get_by_role('button', name='Приват', exact=True).click()
        d.get_by_label('Останні 4 цифри картки').fill(suffix)
        save(d)
    d = edit(page, 2)
    d.get_by_label('Останні 4 цифри картки').fill('')
    save(d)
    page.set_viewport_size({'width': 375, 'height': 812})
    page.locator('.o-account-deck').wait_for()
    values = page.locator('.bank-privat .o-bank-number').all_text_contents()
    check(values == ['**** **** **** 0017', '**** **** **** 9234'], 'Картки одного банку мають неправильні реквізити: ' + str(values))
    check(page.locator('.bank-mono .o-bank-number').count() == 0, 'Невідомі цифри підставлено за банком')


CHECKS = [
    ('Реквізити картки: створення, редагування, нулі, очищення, готівка, мітка', 'desktop', identity),
    ('Реквізити картки: різні номери одного банку на телефоні', 'desktop', same_bank),
]
