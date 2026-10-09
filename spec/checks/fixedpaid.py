# DESIGN.md п. 13 (власник 09.10.2026): постійний платіж закриває витрата з fixed_id у місяці платежу, змінна сума з «≈ середня».
# Демо: Садочок (f2) 3 500 ₴ 10-го, у фікстурі змінний; сьогодні 08.10, оплата 3 400 ₴ раніше дати платежу.
import json
import os
import subprocess
import sys
from datetime import date, timedelta

from helpers import ROOT, SPEC, check, dialog, freeze, go_tab, open_payout, pool_ref, shot

DAY = '2026-10-08'
PATCH = [("{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false}",
          "{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false,variable:true}")]
PAID = 3400
# поля freeToPayout (TS) і budget_pool.py (Python), що мусять збігтися
KEYS = [('ownDebit', 'ownDebit'), ('unassigned', 'unassigned'), ('whiteSum', 'whiteDue'), ('cashNow', 'cashNow'), ('planCur', 'planCur'),
        ('varPoolCur', 'varPoolCur'), ('spent', 'spent'), ('freeNow', 'freeNow'), ('perDay', 'perDay'), ('shortage', 'shortage'),
        ('planNext', 'planNext'), ('whiteNext', 'whiteNext'), ('cardRepayNext', 'cardRepayNext'), ('cashAtPayout', 'cashAtPayout'),
        ('varPoolNext', 'varPoolNext'), ('minCash', 'minCash'), ('cashBeforeSalary', 'cashBeforeSalary')]
# кнопка «Оплачено» у рядку, де є назва платежу (найближчий предок з однією такою кнопкою)
PICK = """(name)=>{for(const b of document.querySelectorAll('.pay-done')){let e=b;while(e&&e.querySelectorAll('.pay-done').length<=1){if(e.textContent.includes(name)){b.setAttribute('data-pick','1');return true}e=e.parentElement}}return false}"""


def _btn(page, name='Садочок'):
    page.evaluate("()=>document.querySelectorAll('[data-pick]').forEach(e=>e.removeAttribute('data-pick'))")
    check(page.evaluate(PICK, name), f'немає «Оплачено» у рядку «{name}»')
    return page.locator('[data-pick="1"]')


CORE = "()=>{const c=window.__cashCore;return{cashBeforePayout:c.cashBeforePayout,freeNow:c.freeNow,whiteDue:c.whiteDue,tl:c.timeline.events.map(e=>[pbIso(e.date),e.name||'',Math.round(e.amount*100)/100])}}"


def _ts(snap):
    tmp = SPEC / '.out' / 'fixedpaid_snapshot.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    out = subprocess.run(['node', str(SPEC / 'ts_budget.mts'), str(tmp), DAY], capture_output=True, text=True, encoding='utf-8',
                         env={**os.environ, 'NODE_NO_WARNINGS': '1'}, cwd=str(ROOT))
    check(out.returncode == 0, f'node ts_budget.mts: {out.stderr[-400:]}')
    return json.loads([x for x in out.stdout.splitlines() if x.startswith('JSON ')][-1][5:])


def _py(snap):
    d, _ = open_payout(date.fromisoformat(DAY))
    return pool_ref(snap, str(d - timedelta(days=1)), DAY)


def _bal(r, d):
    return [e['balance'] for e in r['timeline'] if e['date'] <= d][-1]


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
    check(dlg.locator('input[type=date]').input_value() == DAY, 'дата форми не сьогодні')
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
    snapA = page.evaluate('window.__cashSnap()')
    coreA = page.evaluate(CORE)
    go_tab(page, 2)
    check(page.locator('.fx-var', has_text='≈ середня').count() >= 1, 'у Потоці немає «≈ середня» біля змінного платежу')
    check(any(n == 'Садочок' and d == '2026-10-10' for d, n, _ in coreA['tl']), 'до оплати Садочка 10.10 немає в касі по датах')
    page.mouse.move(2, 2)
    shot(page, 'v141-flow-1920.jpg', full=False)
    _pay(page, 'v141-tx-form-1920.jpg')
    snapB = page.evaluate('window.__cashSnap()')
    coreB = page.evaluate(CORE)
    linked = [t for t in snapB['account_tx'] if t.get('fixed_id') == 'f2']
    check(len(linked) == 1 and linked[0]['amount'] == PAID and linked[0]['type'] == 'expense', f'у знімку немає оплати з fixed_id: {linked}')
    check(not any(n == 'Садочок' and d.startswith('2026-10') for d, n, _ in coreB['tl']), f'після оплати Садочок лишився в касі жовтня: {coreB["tl"]}')
    check(any(n == 'Садочок' and d == '2026-11-10' for d, n, _ in coreB['tl']), 'у листопаді Садочка в касі немає (наступний місяць не оплачений)')
    go_tab(page, 2)
    check(not page.evaluate(PICK, 'Садочок'), 'після оплати у Потоці лишилась кнопка «Оплачено» Садочка')
    # еталон і TS: A без оплати, B з оплатою 3 400 08.10
    pa, pb = _py(snapA), _py(snapB)
    ta, tb = _ts(snapA), _ts(snapB)
    oa = sum(o['amount'] for o in pa['obligations'])
    ob = sum(o['amount'] for o in pb['obligations'])
    end = pa['end']
    print(f'      Python: обовʼязкові до {end}: A {oa:.2f}, B {ob:.2f}, різниця {ob - oa:+.2f}')
    print(f'      Python: Садочок в обовʼязкових A {[o["amount"] for o in pa["obligations"] if o["name"] == "Садочок"]}, '
          f'B {[o["amount"] for o in pb["obligations"] if o["name"] == "Садочок"]}; paidFixed B {pb["paidFixed"]}')
    dc = _bal(pb, end) - _bal(pa, end)
    print(f'      каса на кінець {end}: A {_bal(pa, end):.2f}, B {_bal(pb, end):.2f}, різниця {dc:+.2f}, очікувано {3500 - PAID:+.2f}')
    check(abs((ob - oa) + 3500) < 0.005, f'обовʼязкові мали зменшитись на 3 500: {ob - oa:+.2f}')
    check(abs(dc - (3500 - PAID)) < 0.005, f'каса на {end}: різниця {dc:+.2f}, очікувано {3500 - PAID:+.2f}')
    check(pb['paidFixed'] == [['f2', '2026-10']], f'paidFixed {pb["paidFixed"]}')
    check(tb['paid'] == ['f2|2026-10'], f'TS paid {tb["paid"]}')
    bad = []
    for k, t, p in (('A', ta, pa), ('B', tb, pb)):
        for tk, pk in KEYS:
            if abs(round(t[tk], 2) - round(p[pk], 2)) >= 0.005:
                bad.append((k, tk, t[tk], p[pk]))
        if [(e['date'], round(e['balance'], 2)) for e in t['timeline']] != [(e['date'], round(e['balance'], 2)) for e in p['timeline']]:
            bad.append((k, 'timeline'))
        print(f'      паритет TS/Python {k}: {len(KEYS)} полів, каса по датах {len(p["timeline"])} подій')
    check(not bad, f'TS і Python різні: {bad}')
    # застосунок проти еталона після оплати
    for k in ('cashBeforePayout', 'freeNow', 'whiteDue'):
        check(abs(coreB[k] - pb[k]) <= 1, f'застосунок {k} {coreB[k]}, еталон {pb[k]}')
    print(f'      застосунок B: cashBeforePayout {coreB["cashBeforePayout"]:.2f} (еталон {pb["cashBeforePayout"]:.2f})')


def calendar_paid(page):
    """ПК 1920: Календар до оплати з «≈ середня» і «Оплачено», після: рядок «сплачено» з фактичною сумою без балансу."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    go_tab(page, 3)
    ev = page.locator('.cal-ev', has_text='Садочок')
    check(ev.count() >= 1, 'у «Події і баланс» немає Садочка')
    check('≈ середня' in ev.first.inner_text(), f'немає «≈ середня»: {ev.first.inner_text()!r}')
    check(ev.first.locator('.pay-done').count() == 1, 'немає «Оплачено» в рядку Календаря')
    _pay(page)
    go_tab(page, 3)
    ev = page.locator('.cal-ev', has_text='Садочок')
    texts = ev.all_inner_texts()
    print(f'      Календар після оплати: {texts}')
    check(len(texts) == 1 and 'сплачено' in texts[0] and '3' in texts[0] and '400' in texts[0], f'немає «сплачено» з 3 400: {texts}')
    check(ev.first.get_attribute('data-bal') is None, 'сплачений рядок має баланс')
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
    paid = page.evaluate("()=>[...document.querySelectorAll('.fx-paid')].map(e=>e.parentElement.textContent)")
    print(f'      Календар телефону після оплати: {paid}')
    check(any('Садочок' in x and '3' in x and '400' in x for x in paid), f'немає «сплачено» Садочка 3 400: {paid}')
    check(not page.evaluate(PICK, 'Садочок'), 'після оплати лишилось «Оплачено» Садочка')


def drawer_link(page):
    """ПК: у дровері витрати вибір «Постійний платіж»: привʼязка Київстару до Інтернету прибирає план Інтернету жовтня, відвʼязка повертає."""
    page.set_viewport_size({'width': 1920, 'height': 1080})
    freeze(page, DAY, PATCH)
    go_tab(page, 2)
    check(page.evaluate(PICK, 'Інтернет'), 'до привʼязки немає плану Інтернету з «Оплачено»')
    page.locator('.flow-row.tx', has_text='Київстар').first.click()
    page.wait_for_timeout(400)
    sel = page.locator('select[aria-label="Постійний платіж"]')
    check(sel.count() == 1, 'у дровері немає вибору «Постійний платіж»')
    sel.select_option('f4')
    page.wait_for_timeout(400)
    check(not page.evaluate(PICK, 'Інтернет'), 'після привʼязки план Інтернету лишився')
    check(sel.input_value() == 'f4', 'вибір у дровері не тримає привʼязку')
    sel.select_option('')
    page.wait_for_timeout(400)
    check(page.evaluate(PICK, 'Інтернет'), 'після відвʼязки план Інтернету не повернувся')


CHECKS = [
    ('Постійні: привʼязка і відвʼязка в дровері операції', 'desktop', drawer_link),
    ('Постійні: «Оплачено» в Потоці, план зникає з каси, паритет TS/Python', 'desktop', flow_paid),
    ('Постійні: Календар «≈ середня», після оплати «сплачено»', 'desktop', calendar_paid),
    ('Постійні: перемикач «Сума змінна» і «≈» у списку', 'desktop', fixed_form),
    ('Постійні: «Оплачено» на телефоні', 'mobile', phone_paid),
]
