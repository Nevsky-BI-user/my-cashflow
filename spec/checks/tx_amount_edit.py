"""v223: сума операції змінюється в деталях для всіх джерел, крім Monobank.
ПК: дровер Потоку; телефон: модалка операції. Перевірка: рядок у базі, сума в деталях і в списку = введеній;
операція Monobank і переказ без кнопки; кома й копійки; помилкове значення не пишеться."""
import json

from helpers import check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated

TODAY = '2026-10-20'
CAT = {'name': 'Продукти', 'icon': '🛒', 'color': '#7066e0'}
TXS = [
    {'id': 801, 'date': '2026-10-18', 'created_at': '2026-10-18T10:00:00Z', 'type': 'expense', 'amount': 120, 'account_id': 1,
     'category_id': 'food', 'description': 'Synthetic manual shop', 'source': 'manual', 'categories': CAT, 'expense_allocations': []},
    {'id': 802, 'date': '2026-10-18', 'created_at': '2026-10-18T11:00:00Z', 'type': 'expense', 'amount': 75, 'account_id': 1,
     'category_id': 'food', 'description': 'Synthetic bot cafe', 'source': 'telegram', 'categories': CAT, 'expense_allocations': []},
    {'id': 803, 'date': '2026-10-18', 'created_at': '2026-10-18T12:00:00Z', 'type': 'expense', 'amount': 50, 'account_id': 1,
     'category_id': 'food', 'description': 'Synthetic mono kiosk', 'source': 'mono', 'source_id': 'syn-m1', 'categories': CAT, 'expense_allocations': []},
]
# оновлення в підмінній базі повертає змінені рядки і враховує .neq, як PostgREST
APPLY_OLD = "const apply=()=>{const update=q.ops.find(x=>x[0]==='update'),eq=q.ops.find(x=>x[0]==='eq');if(update)(m.data[table]||[]).forEach(row=>{if(!eq||row[eq[1]]===eq[2])Object.assign(row,update[1])});return{data:[],error:null}};"
APPLY_NEW = "const apply=()=>{const update=q.ops.find(x=>x[0]==='update'),eq=q.ops.find(x=>x[0]==='eq'),ne=q.ops.find(x=>x[0]==='neq');const hit=[];if(update)(m.data[table]||[]).forEach(row=>{if((!eq||row[eq[1]]===eq[2])&&(!ne||row[ne[1]]!==ne[2])){Object.assign(row,update[1]);hit.push({id:row.id})}});return{data:hit,error:null}};"


def setup(page):
    page.emulate_media(reduced_motion='reduce')
    assert MOCK.count(APPLY_OLD) == 1
    mock = MOCK.replace(APPLY_OLD, APPLY_NEW).replace('window.supabase={createClient:()=>sb};',
        'm.data.transactions=m.data.transactions.concat(' + json.dumps(TXS, ensure_ascii=False) + ');window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, TODAY)
    updated(page)
    go_tab(page, 2)
    page.wait_for_timeout(500)


def row_amount(i):
    return "(__liveMock.data.transactions.find(t=>t.id===%d)||{}).amount" % i


def edit(page, scope, tag):
    btn = scope.locator('.tx-amt-btn')
    check(btn.count() == 1, f'{tag}: немає кнопки «Змінити суму»')
    btn.click()
    inp = scope.locator('.tx-amt-in')
    check(inp.input_value() == '120,00', f'{tag}: поле не заповнене поточною сумою {inp.input_value()}')
    inp.fill('0')
    scope.locator('.tx-amt-save').click()
    check(scope.locator('.tx-amt-err').count() == 1, f'{tag}: нуль не дав помилки')
    check(page.evaluate(row_amount(801)) == 120, f'{tag}: нуль записано')
    inp.fill('1 234,5')
    inp.press('Enter')
    page.wait_for_function('%s===1234.5' % row_amount(801))
    page.wait_for_timeout(400)
    check('1 234,50' in scope.inner_text().replace('\xa0', ' '), f'{tag}: у деталях не нова сума')
    check(scope.locator('.tx-amt-in').count() == 0, f'{tag}: поле не закрилось')


def desktop(page):
    page.set_viewport_size({'width': 1440, 'height': 900})
    setup(page)
    rows = page.locator('.p-flow.desk .flow-row.tx')
    rows.filter(has_text='Synthetic manual shop').first.click()
    drw = page.locator('.drawer[role=dialog]')
    drw.wait_for()
    edit(page, drw, 'ПК')
    shot(page, 'tx-amount-edit-1440.jpg', full=False)
    rt = rows.filter(has_text='Synthetic manual shop').first.inner_text().replace('\xa0', ' ')
    check('−1 235 ₴' in rt, f'ПК: у списку Потоку стара сума {rt!r}')
    page.keyboard.press('Escape')
    for d, has in (('Synthetic bot cafe', 1), ('Synthetic mono kiosk', 0)):
        rows.filter(has_text=d).first.click()
        drw.wait_for()
        page.wait_for_timeout(200)
        check(drw.locator('.tx-amt-btn').count() == has, f'ПК: {d}: кнопка {drw.locator(".tx-amt-btn").count()} замість {has}')
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
    check(page.evaluate(row_amount(803)) == 50, 'ПК: сума Monobank змінилась')


def mobile(page):
    setup(page)
    page.locator('.panel.p-flow div', has_text='Synthetic manual shop').last.click()
    sheet = page.locator('.overlay .sheet', has_text='Транзакція')
    sheet.wait_for()
    edit(page, sheet, 'телефон 375')
    g = page.evaluate("()=>{const r=document.querySelector('.overlay .sheet').getBoundingClientRect();return[...document.querySelectorAll('.tx-amt-edit *')].every(e=>{const b=e.getBoundingClientRect();return b.right<=r.right+0.5&&b.left>=r.left-0.5})}")
    check(g, 'телефон 375: правка суми виходить за картку')
    shot(page, 'tx-amount-edit-375.jpg', full=False)
    page.locator('.overlay .sheet button', has_text='×').first.click()
    page.wait_for_timeout(300)
    page.locator('.panel.p-flow div', has_text='Synthetic mono kiosk').last.click()
    sheet.wait_for()
    check(sheet.locator('.tx-amt-btn').count() == 0, 'телефон 375: у Monobank є кнопка')


CHECKS = [
    ('Операція: зміна суми в дровері, Monobank без правки (ПК 1440)', 'desktop', desktop),
    ('Операція: зміна суми в модалці (телефон 375)', 'mobile', mobile),
]
