# Щільність ПК на 1920x900: Огляд, Календар, Цілі і Бюджет без прокрутки сторінки, числа KPI до 24px, основний текст 13px, бейджі А/З/борг читаються;
# Потік: панель фільтрів до 150px (усі категорії видно) і щонайменше 14 рядків у вʼюпорті (дата заморожена: демо-операції txDemo розкладаються за сьогоднішнім днем);
# жодної внутрішньої прокрутки в .content на пʼяти екранах; Календар із реальними обсягами (5 постійних, 4 розстрочки, 2 рахунки з боргом) вміщається в 1920x900 цілком
from helpers import check, dialog, freeze, go_tab, shot

DAY = '2026-10-08'
FIT = "({sh:document.scrollingElement.scrollHeight,ih:innerHeight})"
KPI_FS = """[...document.querySelectorAll('.dv-kpi-v, .ck-kpi > div:nth-child(2), .bud-kpi-v, .goals-kpi-v')].filter(e=>e.offsetParent).map(e=>parseFloat(getComputedStyle(e).fontSize))"""
KPI_H = """[...document.querySelectorAll('.dv-kpi, .ck-kpi, .goals-kpi')].filter(e=>e.offsetParent).map(e=>Math.round(e.getBoundingClientRect().height))"""
FLOW = """({bar:Math.round(document.querySelector('.p-flow.desk .flow-bar').getBoundingClientRect().height),
rows:[...document.querySelectorAll('.p-flow.desk .flow-row')].filter(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight}).length})"""
# висота рядка Потоку і кількість текстових рядків в описі (getClientRects текстового вузла)
ROW1 = r"""(()=>{const rows=[...document.querySelectorAll('.p-flow.desk .flow-row')];const bad=[];rows.forEach(e=>{const h=e.getBoundingClientRect().height;const d=e.querySelector('.flow-desc');
const rg=document.createRange();rg.selectNodeContents(d);const lines=new Set([...rg.getClientRects()].map(r=>Math.round(r.top))).size;if(Math.abs(h-32)>0.5||lines!==1)bad.push([d.innerText,h,lines])});
return {n:rows.length,bad:bad,sub:document.querySelectorAll('.p-flow.desk .flow-sub').length}})()"""
# елементи в .content із власною вертикальною прокруткою, яка справді прокручується
INNER = r"""[...document.querySelectorAll('.content *')].filter(e=>{const o=getComputedStyle(e).overflowY;return (o==='auto'||o==='scroll')&&e.scrollHeight>e.clientHeight+2}).map(e=>e.tagName+'.'+(e.className||'').toString().slice(0,30)+' '+e.scrollHeight+'>'+e.clientHeight)"""
# фікстура: другий рахунок із боргом (monobank), дедлайн той самий, що в ПриватБанку
DEBT2 = ("{id:'l3',name:'monobank',bank:'mono',kind:'debit',balance:12500,debt:0,debt_month:null",
         "{id:'l3',name:'monobank',bank:'mono',kind:'debit',balance:12500,debt:4200,debt_month:pbIso(dm)")
CAL = """({sh:document.documentElement.scrollHeight,ih:innerHeight,
fx:[...document.querySelectorAll('.ck-fixed .ck-fx')].map(e=>Math.round(e.getBoundingClientRect().height)),
cr:[...document.querySelectorAll('.ck-crs .ck-cr')].map(e=>Math.round(e.getBoundingClientRect().height)),
ev:[...document.querySelectorAll('.ck-day .cal-ev')].map(e=>Math.round(e.getBoundingClientRect().height)),
debt:document.querySelectorAll('.ck-day .cal-ev-debt').length,more:(document.querySelector('.ck-day .ck-more')||{}).innerText||'',
cards:document.querySelectorAll('.ck-side .ck-debts').length,
side:[...document.querySelectorAll('.ck-side > *')].map(e=>{const r=e.getBoundingClientRect();return [e.className.split(' ').pop(),Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.bottom)]})})"""


def no_inner(page, name):
    inner = page.evaluate(INNER)
    check(not inner, f'{name}: внутрішня прокрутка: {inner[:3]}')


def fit(page):
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    for i, name, kmax in ((0, 'Огляд', 96), (3, 'Календар', 90), (4, 'Цілі', 90)):
        go_tab(page, i)
        page.wait_for_timeout(300)
        m = page.evaluate(FIT)
        check(m['sh'] <= m['ih'] + 8, f'{name} на 1920x900 прокручується: {m["sh"]} > {m["ih"]}')
        no_inner(page, name)
        fs = page.evaluate(KPI_FS)
        check(fs and max(fs) <= 24, f'{name}: число KPI {max(fs) if fs else None}px, а не до 24')
        hs = page.evaluate(KPI_H)
        check(hs and max(hs) <= kmax + 0.5, f'{name}: KPI заввишки {hs}, а не до {kmax}px')
    page.mouse.move(2, 2)
    shot(page, 'goals-1920.jpg', full=False)
    # основний текст ПК 13px на рядку операції (Огляд, «Останні операції»)
    go_tab(page, 0)
    page.wait_for_timeout(200)
    row = page.evaluate("getComputedStyle(document.querySelector('.dv-recent div[style*=\"cursor\"] span:nth-child(2)')).fontSize")
    check(row == '13px', f'рядок операції {row}, а не 13px')
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
    no_inner(page, 'Потік')
    check(f['rows'] >= 14, f'у вʼюпорті лише {f["rows"]} рядків Потоку, а не 14+')
    # кожен рядок Потоку рівно 32px, опис в один текстовий рядок, без підрядка (MCC лише в дровері)
    rr = page.evaluate(ROW1)
    check(rr['n'] >= 14 and not rr['bad'], f'рядки Потоку не 32px або опис не в один рядок: {rr["bad"][:3]} (з {rr["n"]})')
    check(rr['sub'] == 0, f'у рядках Потоку лишився підрядок: {rr["sub"]}')
    page.mouse.move(2, 2)
    shot(page, 'flow-1920.jpg', full=False)


def calendar_real(page):
    """Календар 1920x900 з реальними обсягами: без прокрутки сторінки і внутрішніх прокруток, компактні рядки, борги лише в KPI"""
    freeze(page, DAY, patch=[DEBT2])
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    go_tab(page, 3)
    page.wait_for_timeout(300)
    c = page.evaluate(CAL)
    print(f'      Календар 1920x900: сторінка {c["sh"]}/{c["ih"]}, права колонка {c["side"]}')
    check(len(c['fx']) >= 5 and len(c['cr']) >= 4, f'фікстура не реальна: постійних {len(c["fx"])}, розстрочок {len(c["cr"])}')
    check(c['sh'] <= c['ih'], f'Календар на 1920x900 прокручується: {c["sh"]} > {c["ih"]}')
    no_inner(page, 'Календар')
    check(c['cards'] == 0, 'у правій колонці лишилась картка «Борги»')
    check(all(x == 28 for x in c['fx']), f'рядки постійних платежів не 28px: {c["fx"]}')
    check(all(x <= 44 for x in c['cr']), f'рядок розстрочки вищий за 44px: {c["cr"]}')
    check(c['ev'] and len(c['ev']) <= 6 and all(x == 24 for x in c['ev']), f'події: {len(c["ev"])} рядків {c["ev"]}, а не до 6 по 24px')
    check(c['debt'] == 2, f'у подіях {c["debt"]} дедлайнів боргу, а не 2')
    check(c['more'].startswith('+'), f'немає «+N» під подіями: {c["more"]!r}')
    # на 1920 розстрочки і постійні поруч, події на всю ширину під ними
    s = {x[0]: x for x in c['side']}
    check(s['ck-crs'][2] == s['ck-fixed'][2] and s['ck-crs'][1] < s['ck-fixed'][1], f'розстрочки і постійні не поруч: {c["side"]}')
    check(s['ck-day'][2] >= max(s['ck-crs'][4], s['ck-fixed'][4]) and s['ck-day'][3] > s['ck-crs'][3] * 1.8, f'події не під картками на всю ширину: {c["side"]}')
    # «Погасити» в KPI «Борги» відкриває рахунок
    g = page.locator('.ck-kpi.ck-debt .ck-ghost')
    check(g.count() == 1 and g.inner_text() == 'Погасити', 'у KPI «Борги» немає кнопки «Погасити»')
    page.mouse.move(2, 2)
    shot(page, 'cal-1920.jpg', full=False)
    g.click()
    page.wait_for_timeout(400)
    check(dialog(page, 'Рахунок').count() == 1, '«Погасити» не відкрило рахунок')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    # «+N» розгортає всі події, «згорнути» повертає 6
    more = page.locator('.ck-day .ck-more')
    n = int(more.inner_text().lstrip('+'))
    more.click()
    page.wait_for_timeout(250)
    check(page.locator('.ck-day .cal-ev').count() == len(c['ev']) + n, f'«+{n}» не розгорнуло всі події')
    more.click()
    page.wait_for_timeout(250)
    check(page.locator('.ck-day .cal-ev').count() == len(c['ev']), '«згорнути» не повернуло 6 подій')


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
