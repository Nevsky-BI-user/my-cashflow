# DESIGN.md п. 13 (власник 09.10.2026): постійний платіж закриває витрата з fixed_id у місяці платежу, змінна сума з «≈ середня».
# Демо: Садочок (f2) 3 500 ₴ 10-го, у фікстурі змінний; сьогодні 08.10, оплата 3 400 ₴ раніше дати платежу.
from helpers import check, finance_ref, finance_state, dialog, freeze, go_tab, shot, open_calendar_day, num

DAY = '2026-10-08'
PATCH = [("{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false}",
          "{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false,variable:true}")]
PAID = 3400
# кнопка «Оплачено» у рядку, де є назва платежу (найближчий предок з однією такою кнопкою)
PICK = """(name)=>{for(const b of document.querySelectorAll('.pay-done')){let e=b;while(e&&e.querySelectorAll('.pay-done').length<=1){if(e.textContent.includes(name)){b.setAttribute('data-pick','1');return true}e=e.parentElement}}return false}"""


def _btn(page, name='Садочок'):
    page.evaluate("()=>document.querySelectorAll('[data-pick]').forEach(e=>e.removeAttribute('data-pick'))")
    check(page.evaluate(PICK, name), f'немає «Оплачено» у рядку «{name}»')
    return page.locator('[data-pick="1"]')


def _pay(page, shot_form=None):
    """«Оплачено» на плановій події Садочка в Потоці ПК: форма заповнена, сума 3 400, рахунок Ощадбанк, зберегти."""
    go_tab(page, 2)
    _btn(page).click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, '«Оплачено» не відкрило форму операції')
    amt = dlg.locator('input[placeholder="Сума"]').input_value()
    desc = dlg.locator('input[type=text]').first.input_value()
    sel = dlg.locator('select[aria-label="Постійний платіж"]').input_value()
    print(f'      форма: сума {amt!r}, опис {desc!r}, постійний платіж {sel!r}')
    check(float(amt) == 3500 and desc == 'Садочок' and sel == 'f2', f'форма не заповнена: {amt!r} {desc!r} {sel!r}')
    check(dlg.locator('input[aria-label="Дата фактичної оплати"]').input_value() == DAY, 'дата форми не сьогодні')
    dlg.locator('input[placeholder="Сума"]').fill(str(PAID))
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    page.wait_for_timeout(150)
    if shot_form:
        shot(page, shot_form, full=False)
    dlg.locator('.tx-save').click()
    page.wait_for_timeout(600)
    check(dialog(page, 'Нова операція').count() == 0, 'форма не закрилась після збереження')


def flow_paid(page):
    """ПК 1920: «≈ середня» і «Оплачено» в Потоці, форма заповнена, після збереження план зникає з Потоку й каси; паритет TS/Python/застосунок."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    pa = finance_ref(page, verify_ts=True)
    coreA = {'tl':[(e['date'],e['name'],e.get('amountCents',0)/100) for e in pa['events']]}
    go_tab(page, 2)
    check(page.locator('.fx-var', has_text='≈ середня').count() >= 1, 'у Потоці немає «≈ середня» біля змінного платежу')
    check(any(n == 'Садочок' and d == '2026-10-10' for d, n, _ in coreA['tl']), 'до оплати Садочка 10.10 немає в касі по датах')
    page.mouse.move(2, 2)
    shot(page, 'v141-flow-1920.jpg', full=False)
    _pay(page, 'v141-tx-form-1920.jpg')
    pb = finance_ref(page, verify_ts=True)
    snapB = {'account_tx':finance_state(page)['data']['transactions']}
    coreB = {'tl':[(e['date'],e['name'],e.get('amountCents',0)/100) for e in pb['events']]}
    linked = [t for t in snapB['account_tx'] if t.get('fixed_id') == 'f2']
    check(len(linked) == 1 and linked[0]['amount'] == PAID and linked[0]['type'] == 'expense', f'у знімку немає оплати з fixed_id: {linked}')
    check(not any(n == 'Садочок' and d.startswith('2026-10') for d, n, _ in coreB['tl']), f'після оплати Садочок лишився в касі жовтня: {coreB["tl"]}')
    check(any(n == 'Садочок' and d == '2026-11-10' for d, n, _ in coreB['tl']), 'у листопаді Садочка в касі немає (наступний місяць не оплачений)')
    go_tab(page, 2)
    check(not page.evaluate(PICK, 'Садочок'), 'після оплати у Потоці лишилась кнопка «Оплачено» Садочка')
    check(pb['snapshot']['cashCents'] == pa['snapshot']['cashCents']-PAID*100, 'факт не зменшив касу рівно на сплачену суму')
    check(pb['currentPeriod']['actualVariableCents']==pa['currentPeriod']['actualVariableCents'], 'пов’язаний факт вдруге потрапив у змінні витрати')
    check(not any(e['occurrenceId']=='fixed:f2:2026-10' for e in pb['events']), 'план жовтня після часткової оплати лишився')
    nov=[e for e in pb['events'] if e['occurrenceId']=='fixed:f2:2026-11']
    check(len(nov)==1 and nov[0]['amountCents']==350000, 'наступний місяць має повний план 3500')


def calendar_paid(page):
    """ПК 1920: Календар до оплати з «≈ середня» і «Оплачено», після: рядок «сплачено» з фактичною сумою без балансу."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    go_tab(page, 3)
    details = open_calendar_day(page, '2026-10-10')
    ev = details.locator('.cal-day-events .cal-day-row', has_text='Садочок')
    check(ev.count() >= 1, 'у «Події і баланс» немає Садочка')
    check('≈ середня' in ev.first.inner_text(), f'немає «≈ середня»: {ev.first.inner_text()!r}')
    check(ev.first.locator('.pay-done').count() == 1, 'немає «Оплачено» в рядку Календаря')
    page.keyboard.press('Escape')
    _pay(page)
    go_tab(page, 3)
    details = open_calendar_day(page, DAY)
    ev = details.locator('.cal-day-events .cal-day-row', has_text='Садочок')
    texts = ev.all_inner_texts()
    print(f'      Календар після оплати: {texts}')
    check(len(texts) == 1 and 'сплачено' in texts[0].lower() and abs(num(ev.first.locator('.cal-day-amount').inner_text())) == PAID, f'немає «сплачено» з 3 400: {texts}')
    check(ev.first.get_attribute('data-paid') == 'true', 'сплачений рядок не позначено')
    check(ev.first.locator('.pay-done').count() == 0, 'у сплаченого лишилось «Оплачено»')
    page.mouse.move(2, 2)
    shot(page, 'v141-cal-1920.jpg', full=False)


def fixed_form(page):
    """ПК 1920: у вікні платежів змінна сума з «≈» і «середня», перемикач «Сума змінна» увімкнений і зберігається."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    go_tab(page, 3)
    page.click('.dact')
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'вікно платежів не відкрилось')
    seg = d.locator('[aria-label="Тип платежів"]')
    if seg.count():
        seg.locator('button', has_text='Постійні').click()
        page.wait_for_timeout(200)
    row = d.locator('button', has_text='Садочок').first
    t = row.inner_text()
    check('≈' in t and 'середня' in t, f'у списку немає «≈» і «середня»: {t!r}')
    row.click()
    page.wait_for_timeout(300)
    sw = d.locator('[role=switch][aria-label="Сума змінна (вказано середню)"]')
    check(sw.count() == 1 and sw.get_attribute('aria-checked') == 'true', 'перемикач «Сума змінна» не увімкнений')
    page.mouse.move(2, 2)
    shot(page, 'v141-fixed-form-1920.jpg', full=False)
    # інший платіж: перемикач вимкнений, вмикається кліком
    d.locator('button', has_text='Інтернет').first.click()
    page.wait_for_timeout(300)
    check(sw.get_attribute('aria-checked') == 'false', 'перемикач увімкнений для незмінного платежу')
    sw.click()
    check(sw.get_attribute('aria-checked') == 'true', 'перемикач не вмикається')


def phone_paid(page):
    """Телефон: у Потоці «≈ середня» і «Оплачено», форма заповнена."""
    freeze(page, DAY, PATCH)
    go_tab(page, 2)
    check(page.locator('.row-var').count() >= 1, 'на телефоні немає «≈ середня»')
    _btn(page).click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, '«Оплачено» на телефоні не відкрило форму')
    check(dlg.locator('select[aria-label="Постійний платіж"]').input_value() == 'f2', 'форма телефону без привʼязки')
    dlg.locator('button', has_text='×').first.click()
    page.wait_for_timeout(400)
    # Календар телефону: «≈» і «Оплачено» у списку місяця, після оплати «сплачено» з фактичною сумою
    go_tab(page, 3)
    open_calendar_day(page, '2026-10-10')
    page.wait_for_timeout(200)
    btn = _btn(page)
    row = page.evaluate("()=>{let e=document.querySelector('[data-pick]');for(let k=0;k<6&&e&&!e.textContent.includes('≈');k++)e=e.parentElement;return e?e.textContent:''}")
    check('≈' in row, f'у Календарі телефону немає «≈»: {row!r}')
    btn.click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.locator('select[aria-label="Постійний платіж"]').input_value() == 'f2', 'Календар телефону: форма без привʼязки')
    dlg.locator('input[placeholder="Сума"]').fill(str(PAID))
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    dlg.locator('.tx-save').click()
    page.wait_for_timeout(600)
    go_tab(page, 3)
    details = open_calendar_day(page, '2026-10-08')
    page.wait_for_timeout(200)
    paid_rows = details.locator('.cal-day-events .cal-day-row[data-paid="true"]', has_text='Садочок')
    paid = paid_rows.all_inner_texts()
    print(f'      Календар телефону після оплати: {paid}')
    check(paid_rows.count() == 1 and abs(num(paid_rows.locator('.cal-day-amount').inner_text())) == PAID, f'немає «сплачено» Садочка 3 400: {paid}')
    check(not page.evaluate(PICK, 'Садочок'), 'після оплати лишилось «Оплачено» Садочка')


def drawer_link(page):
    """ПК: у дровері витрати вибір «Постійний платіж»: привʼязка Київстару до Інтернету прибирає план Інтернету жовтня, відвʼязка повертає."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    go_tab(page, 2)
    check(page.evaluate(PICK, 'Садочок'), 'до привʼязки немає плану Інтернету з «Оплачено»')
    page.locator('.flow-row.tx', has_text='Київстар').first.click()
    page.wait_for_timeout(400)
    sel = page.locator('select[aria-label="Постійний платіж"]')
    check(sel.count() == 1, 'у дровері немає вибору «Постійний платіж»')
    sel.select_option('f2')
    page.wait_for_timeout(400)
    check(not page.evaluate(PICK, 'Садочок'), 'після привʼязки план Інтернету лишився')
    check(sel.input_value() == 'f2', 'вибір у дровері не тримає привʼязку')
    sel.select_option('')
    page.wait_for_timeout(400)
    check(page.evaluate(PICK, 'Садочок'), 'після відвʼязки план Інтернету не повернувся')


CHECKS = [
    ('Постійні: привʼязка і відвʼязка в дровері операції', 'desktop', drawer_link),
    ('Постійні: «Оплачено» в Потоці, план зникає з каси, паритет TS/Python', 'desktop', flow_paid),
    ('Постійні: Календар «≈ середня», після оплати «сплачено»', 'desktop', calendar_paid),
    ('Постійні: перемикач «Сума змінна» і «≈» у списку', 'desktop', fixed_form),
    ('Постійні: «Оплачено» на телефоні', 'mobile', phone_paid),
]
