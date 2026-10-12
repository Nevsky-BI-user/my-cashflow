# v149 (міграція 29): постійний дохід або витрата з останньою датою. Після end_date (включно) подій немає ніде:
# рушій (браузер = еталон Python), «Найближче», Потік, календар Платежів; доходи мають вигляд доходу (+, колір доходу).
# Форма: перемикач «Витрата / Дохід», необовʼязкова «Остання дата», у списку «до ДД.ММ.РРРР».
from helpers import check, dialog, finance_ref, freeze, go_tab

DAY = '2026-10-12'
# демо: щомісячний дохід 14-го до 14.11.2026, щотижнева витрата щосереди до 28.10.2026; уже завершені: щовівторка до 05.10 і 3-го числа до 02.10
PATCH = [("const FIXED_DEMO=[", "const FIXED_DEMO=[{id:'f8',name:'Оренда гаража',amount:2500,day_of_month:14,type:'income',color:'#6fd3b0',active:true,credit_ok:false,end_date:'2026-11-14'},"
          "{id:'f9',name:'Прибирання',amount:400,day_of_month:1,period:'week',weekday:3,type:'payment',color:'#7fa8f2',active:true,credit_ok:false,end_date:'2026-10-28'},"
          "{id:'f10',name:'Басейн',amount:350,day_of_month:1,period:'week',weekday:2,type:'payment',color:'#7fa8f2',active:true,credit_ok:false,end_date:'2026-10-05'},"
          "{id:'f11',name:'Курси',amount:1200,day_of_month:3,type:'payment',color:'#f09ac0',active:true,credit_ok:false,end_date:'2026-10-02'},")]
GREEN = "e=>{const m=getComputedStyle(e).color.match(/[\\d.]+/g).map(Number);return m[1]>m[0]+30&&m[1]>m[2]}"
CELLS = r"""(()=>[...document.querySelectorAll('.p-credits .cal-cell')].map(c=>({d:(c.innerText.match(/^\d+/)||[''])[0],t:c.innerText.replace(/\n/g,' | ')})))()"""
FAB = "()=>{const b=[...document.querySelectorAll('button')].filter(x=>getComputedStyle(x).position==='fixed'&&!x.closest('.tab-bar'));b[b.length-1].click()}"


def display(page):
    freeze(page, DAY, PATCH)
    go_tab(page, 0)
    ref = finance_ref(page)  # браузер = Python на тих самих даних із end_date
    inc = [e for e in ref['events'] if e['id'].startswith('fixed:f8:')]
    wk = [e for e in ref['events'] if e['id'].startswith('fixed:f9:')]
    check([e['date'] for e in inc] == ['2026-10-14', '2026-11-14'], f'дохід не до 14.11 включно: {[e["date"] for e in inc]}')
    check(all(e['kind'] == 'income' and e['cashDeltaCents'] == 250000 for e in inc), f'дохід не як надходження: {inc[:1]}')
    check([e['date'] for e in wk] == ['2026-10-14', '2026-10-21', '2026-10-28'], f'щотижнева не до 28.10 включно: {[e["date"] for e in wk]}')
    days = {d['date']: d for d in ref['days']}
    d14 = days['2026-10-14']
    check(d14['closingCashCents'] - d14['openingCashCents'] == sum(e['cashDeltaCents'] for e in ref['events'] if e['date'] == '2026-10-14'), 'каса дня не сходиться з подіями')
    # «Найближче»: дохід із плюсом і кольором доходу
    row = page.locator('.dv-near .dv-ev', has_text='Оренда гаража').first
    amt = row.locator('.dv-ev-a')
    check(amt.inner_text().startswith('+') and amt.evaluate(GREEN), f'дохід у «Найближче» не як дохід: {row.inner_text()!r}')
    # Потік: плановий рядок доходу; завершені до сьогодні платежі не показуються і в минулих днях місяця
    go_tab(page, 2)
    flow = page.inner_text('.panel.p-flow')
    check('Басейн' not in flow and 'Курси' not in flow, 'у Потоці завершений постійний платіж (після його останньої дати)')
    fr = page.locator('.flow-row.row-plan', has_text='Оренда гаража').first
    check(fr.get_attribute('data-type') == 'in' and '+2' in fr.inner_text() and 'Постійний дохід' in fr.inner_text(), f'дохід у Потоці не як дохід: {fr.inner_text()!r}')
    # календар Платежів: жовтень і листопад з доходом 14-го; щосереди до 28.10, у листопаді прибирання немає; у грудні доходу немає
    go_tab(page, 3)
    oct_ = {c['d']: c['t'] for c in page.evaluate(CELLS)}
    check(not any('Басейн' in t or 'Курси' in t for t in oct_.values()), f'у календарі жовтня завершений платіж: {[t for t in oct_.values() if "Басейн" in t or "Курси" in t][:2]}')
    check('Оренда гаража' in oct_.get('14', '') and 'Прибирання' in oct_.get('28', ''), f'жовтень без доходу 14-го або прибирання 28-го: {oct_.get("14")!r} {oct_.get("28")!r}')
    page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
    page.wait_for_timeout(300)
    nov = page.evaluate(CELLS)
    check(any(c['d'] == '14' and 'Оренда гаража' in c['t'] for c in nov), 'у листопаді немає доходу в останню дату 14.11')
    check(not any('Прибирання' in c['t'] for c in nov), f'щотижнева витрата після 28.10: {[c for c in nov if "Прибирання" in c["t"]][:2]}')
    page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
    page.wait_for_timeout(300)
    dec = page.evaluate(CELLS)
    check(not any('Оренда гаража' in c['t'] for c in dec), 'дохід у грудні, після останньої дати')
    print(f'      дохід {[e["date"] for e in inc]}, щосереди {[e["date"] for e in wk]}')


def form(page):
    freeze(page, DAY)
    go_tab(page, 3)
    page.evaluate(FAB)
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    d.locator('[aria-label="Тип платежів"] button', has_text='Постійні').click()
    d.locator('button', has_text='+ Додати').click()
    page.wait_for_timeout(200)
    d.locator('input[placeholder="Напр. Інтернет"]').fill('Підробіток тест')
    for lbl, v in (('Сума', '3000'), ('День місяця', '13')):
        f = d.locator(f'input[type=text][aria-label="{lbl}"]')
        f.fill(v)
        f.press('Tab')
    d.locator('[aria-label="Тип"] button', has_text='Дохід').click()
    end = d.locator('input[type=date][aria-label="Остання дата"]')
    check(end.input_value() == '', 'нова форма не безстрокова за замовчуванням')
    check('Порожньо: безстроково' in d.inner_text(), 'немає підказки про безстроковий платіж')
    end.fill('2026-11-20')
    page.wait_for_timeout(150)
    check('востаннє 20.11.2026' in d.inner_text(), 'немає підказки про останню дату')
    d.locator('button', has_text='Зберегти').first.click()
    page.wait_for_timeout(400)
    if not d.count():
        page.evaluate(FAB)
        page.wait_for_timeout(400)
        d = dialog(page, 'Платежі')
        d.locator('[aria-label="Тип платежів"] button', has_text='Постійні').click()
    item = d.get_by_text('Підробіток тест').first
    check(item.count() == 1, 'збережений дохід не в списку')
    rowt = d.locator('button,div[role=button],.pay-row', has_text='Підробіток тест').last.inner_text()
    check('до 20.11.2026' in rowt and 'дохід' in rowt and '+3' in rowt, f'у списку немає «до ДД.ММ.РРРР» або позначки доходу: {rowt!r}')
    # повторне відкриття: дата збережена; «Безстроково» очищає
    item.click()
    page.wait_for_timeout(250)
    end = d.locator('input[type=date][aria-label="Остання дата"]')
    check(end.input_value() == '2026-11-20', f'остання дата не збереглась: {end.input_value()!r}')
    d.locator('button', has_text='Безстроково').click()
    check(end.input_value() == '', '«Безстроково» не очистило дату')
    d.locator('button', has_text='Зберегти').first.click()
    page.wait_for_timeout(400)
    if d.count():
        rowt = d.locator('button,div[role=button],.pay-row', has_text='Підробіток тест').last.inner_text()
        check('до 20.11.2026' not in rowt, f'після «Безстроково» у списку лишилась дата: {rowt!r}')
        d.locator('[aria-label="Закрити"]').first.click()
        page.wait_for_timeout(300)
    go_tab(page, 0)
    nx = page.locator('.o-next .o-next-row', has_text='Підробіток тест')
    check(nx.count() == 1 and '+3' in nx.inner_text(), f'дохід не в «Найближче» телефона як дохід: {page.inner_text(".o-next")[:200]!r}')


CHECKS = [
    ('v149: постійний дохід і остання дата: рушій, «Найближче», Потік, календар', 'desktop', display),
    ('v149: форма постійного платежу: «Дохід», «Остання дата», «до ДД.ММ.РРРР»', 'mobile', form),
]
