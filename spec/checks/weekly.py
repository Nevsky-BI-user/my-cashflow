# v143 (власник 12.10.2026): щотижневий постійний платіж, банк у формах платежів, «Внести оплату» розстрочки, рахунок банку «Готівка».
# Сьогодні понеділок 12.10.2026: тиждень оплати 12.10-18.10.
import calendar

from helpers import check, dialog, finance_ref, finance_state, freeze, go_tab, shot

DAY = '2026-10-12'
NAME = 'Прибирання'
# понеділків у жовтні 2026: рахує скрипт, а не рукою
MONDAYS = sum(1 for d in range(1, calendar.monthrange(2026, 10)[1] + 1) if calendar.weekday(2026, 10, d) == 0)


def _payments(page):
    go_tab(page, 3)
    page.click('.dact')
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'вікно платежів не відкрилось')
    return d


def _amount(d, label, value):
    inp = d.locator(f'input[aria-label="{label}"]').first
    check(inp.count() == 1, f'немає поля «{label}»')
    inp.fill(str(value))
    inp.press('Tab')  # NumField приймає значення на blur; Enter у формі рахунку зберігає всю форму


def weekly_form(page):
    """ПК 1920: «Щомісяця / Щотижня», день тижня Пн-Нд замість дня місяця, банк «Готівка»; рядок «щопонеділка», сума за місяць; рушій дає подію щопонеділка."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    d = _payments(page)
    d.locator('button', has_text='+ Постійний').first.click()
    page.wait_for_timeout(300)
    per = d.locator('[role=group][aria-label="Періодичність"]')
    check(per.count() == 1, 'у формі немає перемикача «Періодичність»')
    check(per.locator('button[aria-pressed=true]').inner_text() == 'Щомісяця', 'новий платіж не щомісячний за замовчуванням')
    check(d.locator('input[aria-label="День місяця"]').count() == 1, 'у щомісячного немає «День місяця»')
    per.locator('button', has_text='Щотижня').click()
    page.wait_for_timeout(200)
    wd = d.locator('[role=group][aria-label="День тижня"]')
    check(wd.count() == 1 and wd.locator('button').count() == 7, 'у щотижневого немає 7 днів Пн-Нд')
    check(d.locator('input[aria-label="День місяця"]').count() == 0, 'у щотижневого лишилось поле «День місяця»')
    d.locator('input[placeholder="Напр. Інтернет"]').fill(NAME)
    _amount(d, 'Сума', 500)
    wd.locator('button', has_text='Пн').click()
    bank = d.locator('[role=group][aria-label="Банк"]')
    check(bank.count() == 1 and bank.locator('button', has_text='Готівка').count() == 1, 'у формі постійного платежу немає банку «Готівка»')
    bank.locator('button', has_text='Готівка').click()
    page.mouse.move(2, 2)
    shot(page, 'v143-weekly-form-1920.jpg', full=False)
    d.locator('button', has_text='Зберегти').first.click()
    page.wait_for_timeout(500)
    row = d.locator('button', has_text=NAME).first
    t = row.inner_text()
    print(f'      рядок: {t!r}; понеділків у жовтні {MONDAYS}')
    month_sum = f'{500 * MONDAYS:,}'.replace(',', ' ')
    check('щопонеділка' in t and 'готівка' in t, f'у рядку немає «щопонеділка» і банку: {t!r}')
    check('за місяць' in t and month_sum in t.replace(' ', ' '), f'у рядку немає суми за місяць {month_sum}: {t!r}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    fx = [f for f in finance_state(page)['data']['fixed'] if f['name'] == NAME]
    check(len(fx) == 1 and fx[0].get('period') == 'week' and fx[0].get('weekday') == 1 and fx[0].get('bank') == 'cash', f'збережено не так: {fx}')
    ref = finance_ref(page, verify_ts=True)
    ids = [e['occurrenceId'] for e in ref['events'] if e['occurrenceId'].startswith('fixed:' + str(fx[0]['id']) + ':')]
    print(f'      події: {ids[:5]}')
    check(ids[:3] == [f'fixed:{fx[0]["id"]}:2026-10-{d}' for d in ('12', '19', '26')], f'щотижневі події не щопонеділка: {ids[:4]}')


def weekly_pay(page):
    """ПК 1920: «Внести оплату» лише для поточного тижня; оплата закриває тиждень 12.10-18.10, наступний понеділок лишається, змінні витрати не ростуть."""
    weekly_form(page)
    fid = [f for f in finance_state(page)['data']['fixed'] if f['name'] == NAME][0]['id']
    before = finance_ref(page)
    go_tab(page, 3)
    ev = page.locator('.cal-ev', has_text=NAME)
    texts = ev.all_inner_texts()
    btns = [ev.nth(i).locator('.pay-done').count() for i in range(ev.count())]
    print(f'      Календар: {len(texts)} рядків, кнопки {btns}')
    # 05.10 (минулий тиждень, як минулий місячний: план без оплати) і 12.10 (поточний) мають кнопку, 19.10 і 26.10 ні
    check(btns == [1, 1, 0, 0], f'«Внести оплату» не лише в поточному і минулому тижні: {btns}')
    ev.nth(0).locator('.pay-done').click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.locator('input[type=date]').input_value() == '2026-10-05', 'оплата минулого тижня не датована його днем')
    check('05.10-11.10' in dlg.locator('.fx-week').inner_text(), 'у формі минулого тижня немає 05.10-11.10')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    ev.nth(1).locator('.pay-done').click()
    page.wait_for_timeout(400)
    check(dlg.locator('input[type=date]').input_value() == DAY, 'оплата поточного тижня не сьогоднішня')
    check(dlg.count() == 1, '«Внести оплату» не відкрило форму операції')
    check(dlg.locator('select[aria-label="Постійний платіж"]').input_value() == str(fid), 'у формі не вибрано щотижневий платіж')
    hint = dlg.locator('.fx-week').inner_text()
    check('12.10-18.10' in hint, f'у формі немає тижня 12.10-18.10: {hint!r}')
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    dlg.locator('.tx-save').click()
    page.wait_for_timeout(600)
    after = finance_ref(page, verify_ts=True)
    ids = [e['occurrenceId'] for e in after['events'] if e['occurrenceId'].startswith(f'fixed:{fid}:')]
    check(f'fixed:{fid}:2026-10-12' not in ids and f'fixed:{fid}:2026-10-19' in ids, f'оплата закрила не той тиждень: {ids[:3]}')
    check(after['currentPeriod']['actualVariableCents'] == before['currentPeriod']['actualVariableCents'], 'оплата щотижневого потрапила у змінні витрати')
    check(after['snapshot']['cashCents'] == before['snapshot']['cashCents'] - 50000, 'оплата не зменшила касу на 500')


def credit_cash(page):
    """ПК 1920: розстрочка з банком «Готівка» зберігається; «Внести оплату» розстрочки створює витрату з credit_id, платіж місяця закритий, змінні не ростуть."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    d = _payments(page)
    d.locator('button', has_text='+ Розстрочка').first.click()
    page.wait_for_timeout(300)
    bank = d.locator('[role=group][aria-label="Банк"]')
    names = bank.locator('button').all_inner_texts()
    print(f'      банки розстрочки: {names}')
    check(names == ['Ощад', 'Приват', 'mono', 'Готівка', 'Інший'], f'у формі розстрочки не спільний список банків: {names}')
    d.locator('input[placeholder="Напр. Ноутбук"]').fill('Пральна машина')
    _amount(d, 'Сума на місяць', 1000)
    _amount(d, 'День платежу', 25)
    bank.locator('button', has_text='Готівка').click()
    shot(page, 'v143-credit-cash-1920.jpg', full=False)
    d.locator('button', has_text='Зберегти').first.click()
    page.wait_for_timeout(500)
    t = d.locator('button', has_text='Пральна машина').first.inner_text()
    check('готівка' in t, f'у рядку розстрочки немає банку «готівка»: {t!r}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    cr = [c for c in finance_state(page)['data']['credits'] if c['name'] == 'Пральна машина']
    check(len(cr) == 1 and cr[0].get('source') == 'cash', f'розстрочка збережена не з банком cash: {cr}')
    # «Внести оплату» на розстрочці Навушники (21-го, ще не настала)
    before = finance_ref(page)
    head = [e for e in before['events'] if e['occurrenceId'].startswith('installment:') and 'Навушники' in e['name']]
    check(head and head[0]['date'] == '2026-10-21', f'немає планової розстрочки Навушники 21.10: {head[:1]}')
    cid = head[0]['occurrenceId'].split(':')[1]
    go_tab(page, 3)
    ev = page.locator('.cal-ev', has_text='Навушники').first
    check(ev.locator('.pay-done').count() == 1, 'у розстрочки немає «Внести оплату»')
    ev.locator('.pay-done').click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.locator('select[aria-label="Розстрочка"]').input_value() == cid, 'у формі не вибрано розстрочку')
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    dlg.locator('.tx-save').click()
    page.wait_for_timeout(600)
    after = finance_ref(page, verify_ts=True)
    ids = [e['occurrenceId'] for e in after['events'] if e['occurrenceId'].startswith(f'installment:{cid}:')]
    check(f'installment:{cid}:2026-10' not in ids and f'installment:{cid}:2026-11' in ids, f'оплата не закрила розстрочку жовтня: {ids[:2]}')
    check(after['currentPeriod']['actualVariableCents'] == before['currentPeriod']['actualVariableCents'], 'оплата розстрочки потрапила у змінні витрати')


def cash_account(page):
    """ПК 1920: «+» на Огляді створює рахунок банку «Готівка»: картка в ряду, вибір рахунку у формі операції, власні кошти ростуть на баланс."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    before = finance_state(page)['result']['snapshot']['cashCents']
    page.locator('.dv-acc-add').click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    d.locator('[role=group][aria-label="Банк"] button', has_text='Готівка').click()
    d.locator('input[type=text]').first.fill('Гаманець')
    _amount(d, 'Баланс (власні кошти)', 700)
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(500)
    check(page.locator('.dv-cards .bcard', has_text='Гаманець').count() == 1, 'картки «Гаманець» немає в ряду')
    acc = [a for a in finance_state(page)['data']['accounts'] if a['name'] == 'Гаманець']
    check(len(acc) == 1 and acc[0].get('bank') == 'cash', f'рахунок не з банком cash: {acc}')
    after = finance_ref(page)['snapshot']['cashCents']
    print(f'      власні кошти: {before} -> {after}')
    check(after - before == 70000, f'власні кошти змінились на {after - before}, а не на 70 000 коп.')
    page.keyboard.press('KeyN')
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, 'клавіша N не відкрила форму операції')
    check(dlg.locator(f'.acc-seg button[data-acc="{acc[0]["id"]}"]').count() == 1, 'у формі операції немає рахунку «Гаманець»')


def cash_account_mobile(page):
    """Телефон 390: «+» у ряду рахунків Огляду створює рахунок банку «Готівка»: чип у ряду, рахунок у формі операції, власні кошти ростуть на баланс."""
    page.set_viewport_size({'width': 390, 'height': 844})
    freeze(page, DAY)
    before = finance_state(page)['result']['snapshot']['cashCents']
    row = page.locator('.p-overview .o-accs')
    chips = row.locator('.o-acc-chip:not(.o-unas):not(.o-acc-add)')
    n0 = chips.count()
    add = row.locator('.o-acc-add')
    check(add.count() == 1, '390: у ряду рахунків немає «+»')
    add.scroll_into_view_if_needed()
    add.click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    d.locator('[role=group][aria-label="Банк"] button', has_text='Готівка').click()
    d.locator('input[type=text]').first.fill('Гаманець')
    _amount(d, 'Баланс (власні кошти)', 700)
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(500)
    check(chips.count() == n0 + 1, f'390: чипів рахунків {chips.count()}, очікували {n0 + 1}')
    acc = [a for a in finance_state(page)['data']['accounts'] if a['name'] == 'Гаманець']
    check(len(acc) == 1 and acc[0].get('bank') == 'cash', f'390: рахунок не з банком cash: {acc}')
    after = finance_ref(page)['snapshot']['cashCents']
    check(after - before == 70000, f'390: власні кошти змінились на {after - before}, а не на 70 000 коп.')
    go_tab(page, 2)
    page.locator('button.fab[aria-label="Додати операцію"]').click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, '390: кнопка «Додати операцію» не відкрила форму')
    check(dlg.locator(f'.acc-seg button[data-acc="{acc[0]["id"]}"]').count() == 1, '390: у формі операції немає рахунку «Гаманець»')


SETR = "(e,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(e,String(v));e.dispatchEvent(new Event('input',{bubbles:true}))}"


def debt_minus(page):
    """Погашення кредитки з мінусом скрізь: «Найближче», день прогнозу, таблиця «Події і баланс», розклад дня."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY)
    go_tab(page, 0)
    near = page.evaluate("[...document.querySelectorAll('.dv-near .dv-ev')].filter(e=>e.textContent.includes('Погашення')).map(e=>e.lastElementChild.textContent)")
    rng = page.locator('.dv-fc input.fc-range')
    fc = []
    for i in range(60):
        rng.evaluate(SETR, i)
        if page.locator('.fc-day .fc-debt').count():
            fc = page.evaluate("[...document.querySelectorAll('.fc-day .fc-debt')].map(e=>e.lastElementChild.textContent)")
            break
    go_tab(page, 3)
    repay = [e for e in finance_ref(page)['events'] if e['kind'] == 'repay' and e['date'][:7] == DAY[:7]]
    check(repay, 'немає погашення в поточному місяці')
    iso = repay[0]['date']
    tbl = page.evaluate(f"[...document.querySelectorAll('.cal-tbl .cal-ev.cal-ev-debt[data-date=\"{iso}\"] .ce-a')].map(e=>e.textContent)")
    page.click(f'.ck-cal .cal-cell[data-date="{iso}"]')
    page.wait_for_timeout(250)
    day = page.evaluate("[...document.querySelectorAll('.ck-day-events .ck-bd-row')].filter(e=>e.textContent.includes('Погашення')).map(e=>e.querySelector('.ce-a').textContent)")
    print(f'      Найближче {near}, прогноз {fc}, таблиця {tbl}, розклад {day}')
    for where, vals in (('Найближче', near), ('день прогнозу', fc), ('Події і баланс', tbl), ('розклад дня', day)):
        check(vals and all(v.strip().startswith('−') for v in vals), f'{where}: погашення без мінуса {vals}')


def _bot_money(cents):
    """Як money() у finance-message.ts: Intl uk-UA, до 2 знаків без хвостових нулів, групи нерозривним пробілом."""
    v = round(cents / 100, 2)
    whole, frac = f'{abs(v):.2f}'.split('.')
    frac = frac.rstrip('0')
    txt = f'{int(whole):,}'.replace(',', ' ') + (',' + frac if frac else '')
    return ('-' if v < 0 else '') + txt + ' ₴'


def _until_text(u):
    """Рядок бота «Доступно до dd.mm: X ₴ · Y ₴/день (N дн.)» з untilPayout; дата: день перед виплатою."""
    import datetime
    d = datetime.date.fromisoformat(u['end']) - datetime.timedelta(days=1)
    t = f"Доступно до {d.strftime('%d.%m')}: {_bot_money(u['cents'])}"
    return t + (f" · {_bot_money(u['dailyCents'])}/день ({u['days']} дн.)" if u['dailyCents'] > 0 else '')


def until_line(page):
    """Огляд: рядок «Доступно до» з untilPayout у блоці Баланс, текст як у боті."""
    desk = page.viewport_size['width'] >= 1024
    freeze(page, DAY)
    go_tab(page, 0)
    u = finance_ref(page)['untilPayout']
    check(u and u['days'] > 0, 'немає untilPayout у демо')
    want = _until_text(u)
    sel = '.dv-bal [data-b=until]' if desk else '.o-bal [data-b=until]'
    loc = page.locator(sel)
    check(loc.count() == 1, f'немає рядка «Доступно до» ({sel})')
    norm = lambda x: x.replace(' ', ' ').strip()
    got = loc.inner_text()
    print(f'      {got!r}')
    check(norm(got) == norm(want), f'текст не як у боті: {got!r} проти {want!r}')
    check(loc.is_visible(), 'рядок «Доступно до» не видно')


CHECKS = [
    ('Постійні щотижня: форма, «щопонеділка», подія щопонеділка', 'desktop', weekly_form),
    ('Постійні щотижня: оплата закриває тиждень', 'desktop', weekly_pay),
    ('Розстрочка: банк «Готівка», «Внести оплату» з credit_id', 'desktop', credit_cash),
    ('Рахунок банку «Готівка»: картка, форма операції, власні кошти', 'desktop', cash_account),
    ('Рахунок банку «Готівка» на телефоні: чип, форма операції, власні кошти', 'mobile', cash_account_mobile),
    ('Погашення кредитки з мінусом у всіх списках', 'desktop', debt_minus),
    ('Огляд ПК: «Доступно до» з untilPayout як у боті', 'desktop', until_line),
    ('Огляд телефона: «Доступно до» з untilPayout як у боті', 'mobile', until_line),
]
