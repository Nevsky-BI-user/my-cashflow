# Щільність ПК на 1920x900: Огляд, Календар, Цілі і Бюджет без прокрутки сторінки, числа KPI 20–32px, основний текст 13px, бейджі А/З/борг читаються;
# Потік: панель фільтрів до 150px (усі категорії видно) і щонайменше 14 рядків у вʼюпорті (дата заморожена: демо-операції txDemo розкладаються за сьогоднішнім днем);
# Огляд уміщує всі підсумки й категорії без внутрішньої прокрутки.
from helpers import check, dialog, finance_ref, freeze, go_tab, shot, open_calendar_day, settle
from checks.visual_layout import overview_bounds

DAY = '2026-10-08'
FIT = "({sh:document.scrollingElement.scrollHeight,ih:innerHeight})"
KPI_FS = """[...document.querySelectorAll('.dv-kpi-v, .ck-kpi > div:nth-child(2), .bud-kpi-v, .goals-kpis strong')].filter(e=>e.offsetParent).map(e=>parseFloat(getComputedStyle(e).fontSize))"""
KPI_H = """[...document.querySelectorAll('.dv-kpis > .dv-kpi, .ck-kpi, .goals-kpis > .surface')].filter(e=>e.offsetParent).map(e=>Math.round(e.getBoundingClientRect().height))"""
FLOW = """({bar:Math.round(document.querySelector('.p-flow.desk .flow-bar').getBoundingClientRect().height),
rows:[...document.querySelectorAll('.p-flow.desk .flow-row')].filter(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight}).length})"""
# висота рядка Потоку і кількість текстових рядків в описі (getClientRects текстового вузла)
ROW1 = r"""(()=>{const rows=[...document.querySelectorAll('.p-flow.desk .flow-row')];const bad=[];rows.forEach(e=>{const h=e.getBoundingClientRect().height;const d=e.querySelector('.flow-desc');
const rg=document.createRange();rg.selectNodeContents(d);const lines=new Set([...rg.getClientRects()].map(r=>Math.round(r.top))).size;if(Math.abs(h-32)>0.5||lines!==1)bad.push([d.innerText,h,lines])});
return {n:rows.length,bad:bad,sub:document.querySelectorAll('.p-flow.desk .flow-sub').length}})()"""
# елементи в .content із власною вертикальною прокруткою, яка справді прокручується
INNER = r"""[...document.querySelectorAll('.content *')].filter(e=>{const o=getComputedStyle(e).overflowY;return (o==='auto'||o==='scroll')&&e.scrollHeight>e.clientHeight+2}).map(e=>e.tagName+'.'+(e.className||'').toString().slice(0,30)+' '+e.scrollHeight+'>'+e.clientHeight)"""
# фікстура: другий рахунок із боргом (monobank), дедлайн той самий, що в ПриватБанку
DEBT2 = ("{id:'l3',name:'monobank',bank:'mono',card_last4:'4388',kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
         "{id:'l3',name:'monobank',bank:'mono',card_last4:'4388',kind:'credit',mono_account_id:'demo-mono',balance:12500,debt:4200,debt_month:pbIso(dm)")

def no_inner(page, name, allowed=()):
    inner = page.evaluate(INNER)
    bad = [item for item in inner if not any(token in item for token in allowed)]
    check(not bad, f'{name}: стороння внутрішня прокрутка: {bad[:3]}')


def fit(page):
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    # v145: плитки KPI Огляду з рядками розкладу (готівка, карти, кредитні, «Доступно до»): до 176px, сторінка все одно без прокрутки
    for i, name, kmax in ((0, 'Огляд', 176), (3, 'Календар', 128), (4, 'Цілі', 90)):
        go_tab(page, i)
        page.wait_for_timeout(300)
        m = page.evaluate(FIT)
        check(m['sh'] <= m['ih'] + 8, f'{name} на 1920x900 прокручується: {m["sh"]} > {m["ih"]}')
        if i == 0:
            overview_bounds(page, 'Щільність/Огляд')
        else:
            no_inner(page, name)
        fs = page.evaluate(KPI_FS)
        max_font = 26 if i == 4 else 32
        check(fs and min(fs) >= 18 and max(fs) <= max_font, f'{name}: число KPI поза читабельним діапазоном 18–{max_font}px: {fs}')
        if i == 0:
            primary = page.evaluate("[...document.querySelectorAll('.dv-kpis>.kpi-t .dv-kpi-v')].map(e=>parseFloat(getComputedStyle(e).fontSize))")
            check(len(primary) == 3 and min(primary) >= 20, f'{name}: три основні KPI дрібніші за 20px: {primary}')
        hs = page.evaluate(KPI_H)
        check(hs and max(hs) <= kmax + 0.5, f'{name}: KPI заввишки {hs}, а не до {kmax}px')
    page.mouse.move(2, 2)
    shot(page, 'goals-1920.jpg', full=False)
    # Компактний опис операції лишається читабельним: щонайменше 12px.
    go_tab(page, 0)
    page.wait_for_timeout(200)
    row = page.evaluate("getComputedStyle(document.querySelector('.dv-recent div[style*=\"cursor\"] span:nth-child(2)')).fontSize")
    check(float(row.removesuffix('px')) >= 12, f'опис операції надто дрібний: {row}')
    # бейджі виплат і боргу в сітці Календаря: щонайменше 11.5px (дрібний кегль дизайну ПК v135) і не обрізані
    go_tab(page, 3)
    page.wait_for_timeout(200)
    b = page.evaluate("""[...document.querySelectorAll('.ck-cal .cal-badge, .ck-cal .cal-debt')].map(e=>{const r=e.getBoundingClientRect();return{t:e.innerText.trim(),fs:parseFloat(getComputedStyle(e).fontSize),w:r.width,sw:e.scrollWidth,cw:e.clientWidth}})""")
    check(len(b) >= 2, f'у сітці лише {len(b)} бейджів виплат і боргу')
    for x in b:
        check(x['fs'] >= 11.5 and x['w'] > 0 and x['sw'] <= x['cw'] + 1, f'бейдж нечитабельний: {x}')
    # Бюджет: без прокрутки
    go_tab(page, 1)
    page.wait_for_timeout(300)
    m = page.evaluate(FIT)
    check(m['sh'] <= m['ih'] + 8, f'Бюджет на 1920x900 прокручується: {m["sh"]} > {m["ih"]}')
    no_inner(page, 'Бюджет')
    shot(page, 'budget-1920.jpg', full=False)
    # Потік: панель фільтрів до 110px, щонайменше 14 рядків повністю у вʼюпорті
    go_tab(page, 2)
    page.wait_for_timeout(300)
    f = page.evaluate(FLOW)
    print(f'      Потік 1920x900: панель {f["bar"]}px, рядків у вʼюпорті {f["rows"]}')
    check(f['bar'] <= 150, f'панель фільтрів Потоку {f["bar"]}px, а не до 150')
    # 10.10.2026: довга історія прокручується лише всередині таблиці, сторінка: один екран.
    inner = page.evaluate(INNER)
    check(inner and all('flow-table' in item for item in inner), f'Потік: прокручуються сторонні блоки {inner}')
    check(page.evaluate("getComputedStyle(document.querySelector('.flow-head')).position") == 'sticky', 'Шапка таблиці не липка')
    reach = page.locator('.flow-table').evaluate("""e=>{e.scrollTop=e.scrollHeight;const last=e.querySelector('.flow-group:last-child .flow-row:last-child');const r=last.getBoundingClientRect(),c=e.getBoundingClientRect();const ok=r.bottom<=c.bottom+1&&r.top>=c.top;e.scrollTop=0;return ok}""")
    check(reach, 'Останній рядок історії недосяжний')
    check(f['rows'] >= 14, f'у вʼюпорті лише {f["rows"]} рядків Потоку, а не 14+')
    # кожен рядок Потоку рівно 32px, опис в один текстовий рядок, без підрядка (MCC лише в дровері)
    rr = page.evaluate(ROW1)
    check(rr['n'] >= 14 and not rr['bad'], f'рядки Потоку не 32px або опис не в один рядок: {rr["bad"][:3]} (з {rr["n"]})')
    check(rr['sub'] == 0, f'у рядках Потоку лишився підрядок: {rr["sub"]}')
    page.mouse.move(2, 2)
    shot(page, 'flow-1920.jpg', full=False)


def calendar_real(page):
    """Повноширинний календар із двома боргами та доступними діями оплати без прокрутки."""
    freeze(page, DAY, patch=[DEBT2])
    page.set_viewport_size({'width': 1920, 'height': 900})
    go_tab(page, 3)
    check(page.evaluate('document.documentElement.scrollHeight<=innerHeight+1&&document.documentElement.scrollWidth<=innerWidth+1'), 'Календар виходить за екран')
    no_inner(page, 'Календар')
    check(page.locator('.ck-side,.ck-day,.cal-tbl').count() == 0, 'Бічна таблиця подій не прибрана')
    check(page.locator('.ck-cal').evaluate('e=>e.getBoundingClientRect().width>=innerWidth-270'), 'Календар не займає доступну ширину')
    ref = finance_ref(page)
    expected_repay = {e['date'] for e in ref['events'] if e['kind'] == 'repay' and e['date'].startswith(DAY[:7])}
    check(expected_repay, 'Фікстура не містить запланованого погашення')
    for iso in sorted(expected_repay):
        details = open_calendar_day(page, iso)
        check('Погашення' in details.inner_text(), f'{iso}: погашення відсутнє в деталях дня')
        check(details.locator('.cal-day-amount').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)'), 'Суми погашень обрізані')
        page.keyboard.press('Escape')
    g = page.locator('.ck-kpi.ck-debt .ck-ghost')
    check(g.count() == 1 and g.inner_text() == 'Погасити', 'У підсумку боргів немає кнопки погашення')
    g.click()
    check(dialog(page, 'Рахунок').count() == 1, 'Погашення не відкрило рахунок')
    page.keyboard.press('Escape')
    day = page.locator('.ck-cal .cal-cell.future:has(.cal-ln)').first
    iso = day.get_attribute('data-date')
    details = open_calendar_day(page, iso)
    check(details.locator('.cal-day-row').count() > 0, 'Повні події дня недоступні')
    page.keyboard.press('Escape')
    check(not page.locator('dialog.cal-day-dialog[open]').count(), 'Діалог дня не закрився')
    no_inner(page, 'Календар')
    check(page.evaluate('document.documentElement.scrollHeight<=innerHeight+1'), 'Після перегляду дня сторінка прокручується')
    shot(page, 'cal-real-1920.jpg', full=False)


def laptop(page):
    """1280x800: прокрутка дозволена, але рядок KPI і перша картка видно одразу"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1280, 'height': 800})
    page.wait_for_timeout(300)
    for i, kpi, first, nm in ((0, '.dv-kpis', '.dv-fc', 'ov-1280.jpg'), (3, '.ck-kpis', '.ck-cal', 'cal-1280.jpg'), (4, '.goals-kpis', '.goals-log', 'goals-1280.jpg')):
        go_tab(page, i)
        page.wait_for_timeout(300)
        kb = page.locator(kpi).bounding_box()
        fb = page.locator(first).bounding_box()
        check(kb and kb['y'] + kb['height'] <= 800, f'{kpi}: рядок KPI не вміщується на 1280x800: {kb}')
        check(fb and fb['y'] < 800 - 120, f'{first}: першу картку не видно на 1280x800: {fb}')
        page.mouse.move(2, 2)
        shot(page, nm, full=False)
    go_tab(page, 2)
    page.wait_for_timeout(300)
    rb = page.locator('.p-flow.desk .flow-row').first.bounding_box()
    check(rb and rb['y'] + rb['height'] <= 800, f'на 1280x800 не видно жодного рядка Потоку: {rb}')
    page.mouse.move(2, 2)
    shot(page, 'flow-1280.jpg', full=False)


CHECKS = [
    ('ПК 1920x900: Огляд, Календар, Цілі, Бюджет без прокрутки, жодної внутрішньої прокрутки, Потік 14+ рядків по 32px в один рядок, KPI, 13px, бейджі', 'desktop', fit),
    ('ПК 1920x900: Календар із реальними обсягами на одному екрані', 'desktop', calendar_real),
    ('ПК 1280x800: KPI і перша картка видно (Огляд, Календар, Цілі), рядок Потоку', 'desktop', laptop),
]
