"""Фактичні заощадження виключаються з доступних коштів на ПК й телефоні."""
from helpers import check, freeze, num, settle, shot


def wait_total(page, expected):
    page.wait_for_function("""expected=>{
      const el=document.querySelector('.kpi-funds .dv-kpi-v');
      return el && Number(el.innerText.replace(/[^0-9,−-]/g,'').replace('−','-').replace(',','.'))===expected;
    }""", arg=expected)


def savings(page):
    page.emulate_media(reduced_motion='reduce')
    freeze(page, '2026-10-25', patch=[
        ('const[savingsLog,setSavingsLog]=useState([]);',
         'const[savingsLog,setSavingsLog]=useState([]);window.testSetSavings=setSavingsLog;'),
    ])
    if page.viewport_size['width'] >= 1024:
        page.set_viewport_size({'width': 1280, 'height': 720})
        settle(page)
    baseline = page.evaluate('kpiFunds(window.__financeProjection)')
    balance = num(page.locator('.kpi-balance .dv-kpi-v').inner_text())
    projection = page.evaluate('JSON.stringify(window.__financeProjection)')
    for amount in (300, 900000):
        page.evaluate('(amount)=>testSetSavings([{id:1,date:"2026-10-24",amount,currency:"UAH"},{id:2,date:"2026-12-01",amount:900000,currency:"UAH"}])', amount)
        expected = min(baseline['own'], amount * 100)
        wait_total(page, (baseline['total'] - expected) / 100)
        settle(page)
        check(num(page.locator('.kpi-funds .dv-kpi-v').inner_text()) == (baseline['total'] - expected) / 100, 'заощадження включені в доступні або зменшили кредитний ліміт')
        check(num(page.locator('.kpi-funds [data-r=savings] .kpi-rv').inner_text()) == -expected / 100, 'видиме віднімання не відповідає виключеній сумі')
        for key in ('cash', 'cards', 'credit'):
            check(num(page.locator(f'.kpi-funds [data-r={key}] .kpi-rv').inner_text()) == baseline[key] / 100, f'{key}: змінено вихідний залишок')
        check(num(page.locator('.kpi-balance .dv-kpi-v').inner_text()) == balance, 'заощадження зменшили майно двічі')
        check(page.evaluate('JSON.stringify(window.__financeProjection)') == projection, 'заощадження змінили прогноз або баланси рахунків')
        if amount == 300:
            shot(page, 'available-savings-desktop.jpg' if page.viewport_size['width'] >= 1024 else 'available-savings-mobile.jpg', full=True)
            if page.viewport_size['width'] >= 1024:
                geometry = page.evaluate("""()=>({height:document.documentElement.scrollHeight,
                  bottom:Math.max(...[...document.querySelectorAll('.p-overview.desk .surface')]
                    .filter(e=>e.getClientRects().length).map(e=>e.getBoundingClientRect().bottom))})""")
                check(geometry['height'] <= 721 and geometry['bottom'] <= 721,
                      f'1280x720: savings deduction makes Overview overflow: {geometry}')
        page.locator('.kpi-funds .kpi-i').click()
        tip = page.locator('.kpi-tip[data-k=funds]')
        tip.wait_for(state='visible')
        check('Заощадження:' in tip.inner_text() and 'Кредитний ліміт не зменшується.' in tip.inner_text(), 'немає пояснення виключення заощаджень')
        page.keyboard.press('Escape')
    # Вилучення внеску повертає доступну суму, але не змінює залишки рахунків.
    page.evaluate('testSetSavings([])')
    page.locator('.kpi-funds [data-r=savings]').wait_for(state='detached')
    wait_total(page, baseline['total'] / 100)
    settle(page)
    check(num(page.locator('.kpi-funds .dv-kpi-v').inner_text()) == baseline['total'] / 100, 'видалення внеску не повернуло доступні кошти')
    check(page.locator('.kpi-funds [data-r=savings]').count() == 0, 'нульовий рядок заощаджень займає місце')
    # Історичний Огляд виключає лише внесок, що існував на кінець вибраного періоду.
    page.evaluate('testSetSavings([{id:1,date:"2026-10-01",amount:300,currency:"UAH"},{id:2,date:"2026-10-24",amount:900000,currency:"UAH"}])')
    page.get_by_role('button', name='Попередній період', exact=True).click()
    page.wait_for_function("""()=>{
      const e=document.querySelector('.kpi-funds [data-r=savings] .kpi-rv');
      return e && Number(e.innerText.replace(/[^0-9,−-]/g,'').replace('−','-').replace(',','.'))===-300;
    }""")
    settle(page)
    check(num(page.locator('.kpi-funds [data-r=savings] .kpi-rv').inner_text()) == -300, 'минулий період віднімає пізніший внесок')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'віднімання розширило сторінку')


CHECKS = [
    ('Available funds exclude saved money and preserve balances/credit/history on desktop', 'desktop', savings),
    ('Available funds exclude saved money and preserve balances/credit/history on mobile', 'mobile', savings),
]
