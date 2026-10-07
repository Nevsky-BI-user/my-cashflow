# Прогноз балансу на ПК-Огляді, приглушене майбутнє, календар із виплатами й дедлайном боргу
from datetime import date

from helpers import check, go_tab, shot

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""


def chart(page):
    rng = page.locator('.dv-fc input.fc-range')
    check(rng.count() == 1, 'немає повзунка дат прогнозу')
    check(rng.get_attribute('max') == '59', f'повзунок до {rng.get_attribute("max")}, а не 59')
    r0 = page.inner_text('.fc-readout')
    check('баланс' in r0, f'readout без балансу: {r0!r}')
    rng.evaluate(SETR, 10)
    page.wait_for_timeout(150)
    r1 = page.inner_text('.fc-readout')
    check(r1 != r0, 'повзунок не змінив readout')
    check(page.locator('.dv-fc [data-ev=debt]').count() >= 1, 'на графіку немає маркера дедлайну боргу')
    # день дедлайну: подія «Погасити борг» у списку дня
    found = False
    for i in range(60):
        rng.evaluate(SETR, i)
        if page.locator('.fc-day .fc-debt').count():
            found = 'Погасити борг' in page.inner_text('.fc-day')
            break
    check(found, 'жоден день прогнозу не показав подію «Погасити борг»')
    # «Найближче»: майбутні приглушені, сьогодні ні
    rows = page.evaluate("[...document.querySelectorAll('.dv-near .dv-ev')].map(e=>({t:e.innerText,f:e.classList.contains('future'),o:getComputedStyle(e).opacity}))")
    check(len(rows) == 8, f'у «Найближче» {len(rows)} подій, а не 8')
    for r in rows:
        fut = 'через' in r['t']
        check(fut == r['f'], f'клас .future не відповідає даті: {r}')
        if fut:
            check(abs(float(r['o']) - 0.55) < 0.01, f'майбутнє не приглушене: opacity {r["o"]}')


def calendar(page):
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits')
    check(cal.locator('.cal-badge', has_text='А').count() == 1 and cal.locator('.cal-badge', has_text='З').count() == 1,
          'у сітці місяця немає бейджів виплат А і З')
    t = date.today()
    if t.day <= 25:
        check(cal.locator('.cal-debt').count() == 1, 'у сітці немає бейджа «борг» на 25-те')
        check(cal.locator('.cal-ev-debt').count() == 1, 'у списку подій немає дедлайну боргу')
    evs = page.evaluate("[...document.querySelectorAll('.cal-list .cal-ev')].map(e=>({t:e.innerText,f:e.classList.contains('future')}))")
    check(evs, 'у календарі немає списку подій')
    for e in evs:
        check(('через' in e['t']) == e['f'], f'подія календаря: .future не відповідає даті: {e}')
    if t.day < 28:
        check(cal.locator('.cal-cell.future').count() > 0, 'майбутні дні в сітці не приглушені')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg')


CHECKS = [
    ('Прогноз: повзунок, дедлайн боргу, майбутнє', 'desktop', chart),
    ('Календар: А/З, борг 25-го, майбутнє', 'desktop', calendar),
]
