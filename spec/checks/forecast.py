# Прогноз балансу на ПК-Огляді, приглушене майбутнє, календар із виплатами й дедлайном боргу
import re
from datetime import date

from helpers import check, go_tab, shot

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""


def chart(page):
    rng = page.locator('.dv-fc input.fc-range')
    check(rng.count() == 1, 'немає повзунка дат прогнозу')
    check(rng.get_attribute('max') == '59', f'повзунок до {rng.get_attribute("max")}, а не 59')
    r0 = page.inner_text('.fc-readout')
    check('власні ≈' in r0 and 'мінус борг ≈' in r0, f'readout без двох ліній (власні, мінус борг): {r0!r}')
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
    # v139 (DESIGN.md п. 12): борг кредитки гаситься 24-го наступного місяця, подія «Погашення кредитки» з тегом «погашення»
    if t.day <= 24:
        d24 = f'{t.year}-{t.month:02d}-24'
        check('Погашення кредитки' in page.inner_text(f'.ck-cal .cal-cell[data-date="{d24}"]'), 'у сітці немає погашення кредитки 24-го')
        rep = page.evaluate("d=>[...document.querySelectorAll('.cal-tbl .cal-ev[data-date=\"'+d+'\"] .ce-tg')].map(e=>e.textContent)", d24)
        check('погашення' in rep, f'у таблиці подій немає погашення 24-го: {rep}')
    evs = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev')].map(e=>({d:e.dataset.date,p:e.classList.contains('past'),td:e.classList.contains('today'),b:e.dataset.bal}))")
    check(evs, 'у календарі немає таблиці подій')
    iso = t.isoformat()
    for e in evs:
        check(e['p'] == (e['d'] < iso) and e['td'] == (e['d'] == iso), f'подія календаря: минуле/сьогодні не відповідає даті: {e}')
        check(e['b'] is None or e['d'] >= iso, f'баланс після в минулому рядку: {e}')
    if t.day < 28:
        check(cal.locator('.cal-cell.future').count() > 0, 'майбутні дні в сітці не приглушені')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg', full=False)


def hover(page):
    """Наведення: курсор і підказка «день дата · ≈ сума» без затримки, readout не міняється;
    клік фіксує день (readout і повзунок на ньому), ←/→ на фокусі графіка міняють день, повторний клік знімає фіксацію"""
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    svg = page.locator('.dv-fc svg[role=img]')
    b = svg.bounding_box()
    n = 60
    x_of = lambda i: b['x'] + 12 + i / (n - 1) * (b['width'] - 24)
    y = b['y'] + b['height'] / 2
    r0 = page.inner_text('.fc-readout')
    page.mouse.move(x_of(17), y)
    page.wait_for_timeout(60)
    tip = page.locator('.dv-fc .fc-tip')
    check(tip.count() == 1, 'наведення не показало підказку')
    tt = tip.inner_text()
    check(re.search(r'^(Пн|Вт|Ср|Чт|Пт|Сб|Нд) \d\d\.\d\d · ≈ −?[\d\s]+ ₴', tt), f'підказка без дня, дати й суми: {tt!r}')
    check(page.locator('.dv-fc .fc-cur').count() == 1, 'немає лінії-курсора під мишею')
    check(page.inner_text('.fc-readout') == r0, 'наведення змінило readout')
    page.mouse.move(x_of(40), y)
    page.wait_for_timeout(60)
    shot(page, 'ov-hover-1920.jpg', full=False)
    # клік фіксує
    page.mouse.move(x_of(17), y)
    page.mouse.click(x_of(17), y)
    page.wait_for_timeout(100)
    r1 = page.inner_text('.fc-readout')
    check(r1 != r0 and 'зафіксовано' in r1, f'клік не зафіксував день: {r1!r}')
    check(tt.split(' · ')[0] in r1, f'зафіксовано не той день: підказка {tt!r}, readout {r1!r}')
    check(page.locator('.dv-fc input.fc-range').input_value() == '17', 'повзунок не перейшов на зафіксований день')
    check(page.locator('.dv-fc .fc-tip').count() == 0, 'підказка дублює readout на зафіксованому дні')
    # ←/→ на фокусі графіка міняють день і не перемикають період
    p0 = page.inner_text('.dtitle')
    page.keyboard.press('ArrowRight')
    page.wait_for_timeout(100)
    check(page.locator('.dv-fc input.fc-range').input_value() == '18', '→ на графіку не пересунув день')
    check(page.inner_text('.dtitle') == p0, '→ на графіку перемкнув період')
    page.keyboard.press('ArrowLeft')
    page.wait_for_timeout(100)
    check(page.inner_text('.fc-readout') == r1, '← не повернув день')
    # повторний клік по тому ж дню знімає фіксацію
    page.mouse.click(x_of(17), y)
    page.wait_for_timeout(100)
    check(page.inner_text('.fc-readout') == r0, f'повторний клік не зняв фіксацію: {page.inner_text(".fc-readout")!r}')


CHECKS = [
    ('Прогноз: повзунок, дедлайн боргу, майбутнє', 'desktop', chart),
    ('Прогноз: наведення, клік фіксує, ←/→, повторний клік', 'desktop', hover),
    ('Календар: А/З, борг 25-го, майбутнє', 'desktop', calendar),
]
