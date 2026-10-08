# ПК-Календар v139 (DESIGN.md п. 12): KPI, компактна сітка місяця 7 колонок (повні назви подій, до 2 рядків, інакше «+N»),
# минулі дні приглушеним тлом, сьогодні виділене; праворуч таблиця «Події і баланс» на всю висоту (каса по датах);
# клік по дню: розклад балансу; червона рамка дня, де каса після білого платежу нижче нуля; 1920x1080 без прокрутки
from datetime import date

from helpers import check, freeze, go_tab, shot

MO = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень', 'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
INNER_SCROLL = r"""[...document.querySelectorAll('.content *')].filter(e=>{const o=getComputedStyle(e).overflowY;return o==='auto'||o==='scroll'}).length"""
# найменший кегль тексту в сітці й таблиці (лише елементи з власним текстом)
MIN_FS = """sel=>Math.min(...[...document.querySelectorAll(sel+' *')].filter(e=>e.offsetParent&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).map(e=>parseFloat(getComputedStyle(e).fontSize)))"""
ROWS = """[...document.querySelectorAll('.ck-day .cal-tbl .cal-ev')].map(r=>({d:r.dataset.date,b:r.dataset.bal==null?null:Number(r.dataset.bal),
h:r.getBoundingClientRect().height,c:r.className,n:r.querySelector('.ce-n').textContent,a:r.querySelector('.ce-b').textContent}))"""


def desktop(page):
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits.desk')
    check(cal.count() == 1, 'на ПК немає окремого Календаря')
    t = date.today()
    kpis = cal.locator('.ck-kpis .ck-kpi')
    check(kpis.count() == 3, f'KPI {kpis.count()}, а не 3')
    kt = cal.locator('.ck-kpis').inner_text().lower()
    for s in ('Обовʼязкові до наступної виплати', 'Розстрочки', 'Борги', '/міс', 'залишок'):
        check(s.lower() in kt, f'у рядку KPI немає «{s}»')
    check('до 25.' not in kt, f'у KPI лишилось «до 25»: {kt!r}')
    # картки розстрочок і постійних платежів з ПК прибрано
    check(cal.locator('.ck-crs, .ck-fixed, .ck-under, .cal-fc').count() == 0, 'на ПК лишились картки розстрочок, постійних або повзунок')
    cols = page.evaluate("getComputedStyle(document.querySelector('.ck-cal .cal-days')).gridTemplateColumns.split(' ').length")
    check(cols == 7, f'у сітці {cols} колонок')
    hs = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.getBoundingClientRect().height)")
    check(len(hs) >= 28 and min(hs) >= 64, f'клітинки нижчі за 64px: {min(hs) if hs else None}')
    many = page.evaluate("Math.max(0,...[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.querySelectorAll('.cal-ln').length))")
    check(many <= 2, f'у клітинці {many} рядків подій, а не до 2')
    # повні назви без «...»: назва переноситься, не обрізається
    cut = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-nm')].filter(e=>getComputedStyle(e).textOverflow==='ellipsis'||getComputedStyle(e).whiteSpace==='nowrap'||e.closest('.cal-cell').scrollHeight>e.closest('.cal-cell').clientHeight+1).map(e=>e.textContent)")
    check(not cut, f'назви подій обрізані: {cut}')
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', f'заголовок місяця: {page.inner_text(".ck-month")!r}')
    today = cal.locator('.cal-cell.today')
    check(today.count() == 1, 'немає клітинки «сьогодні»')
    sh = today.evaluate("e=>getComputedStyle(e).boxShadow")
    check('inset' in sh and '2px 0px 0px' in sh, f'сьогодні без лівої смуги акценту: {sh}')
    check(today.locator('.cal-dn').inner_text() == str(t.day), 'обведене не сьогоднішнє число')
    # минулі дні: приглушене тло, відмінне від майбутніх і від сьогодні
    past = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell.past')].map(e=>Number(e.querySelector('.cal-dn').textContent))")
    check(sorted(past) == list(range(1, t.day)), f'минулі дні не позначені: {past}')
    bg = page.evaluate("""(()=>{const g=s=>{const e=document.querySelector(s);return e?getComputedStyle(e).backgroundColor:null};
return{past:g('.ck-cal .cal-cell.past:not(.we)'),fut:g('.ck-cal .cal-cell.future:not(.we)'),today:g('.ck-cal .cal-cell.today')}})()""")
    check(bg['past'] and bg['past'] != bg['fut'] and bg['past'] != bg['today'] and bg['past'] not in ('rgba(0, 0, 0, 0)', 'transparent'), f'тло минулих днів не відрізняється: {bg}')
    check(cal.locator('.cal-badge', has_text='А').count() == 1 and cal.locator('.cal-badge', has_text='З').count() == 1, 'немає бейджів А і З')
    # погашення кредитки 24-го (п. 12): подія в клітинці 24-го
    if t.day <= 24:
        c24 = page.inner_text(f'.ck-cal .cal-cell[data-date="{t.year}-{t.month:02d}-24"]')
        check('Погашення кредитки' in c24, f'у клітинці 24-го немає погашення кредитки: {c24!r}')
    check(page.evaluate(MIN_FS, '.p-credits.desk .ck-cols') >= 13, f'текст у Календарі дрібніший за 13px: {page.evaluate(MIN_FS, ".p-credits.desk .ck-cols")}')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg', full=False)
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    page.wait_for_timeout(200)
    n = date(t.year + (t.month == 12), t.month % 12 + 1, 1)
    check(page.inner_text('.ck-month') == f'{MO[n.month - 1]} {n.year}', '→ не перейшов на наступний місяць')
    check(cal.locator('.cal-cell.today').count() == 0, 'у наступному місяці є «сьогодні»')
    check(cal.locator('.cal-cell.past').count() == 0, 'у наступному місяці є минулі дні')
    page.click('.ck-arr[aria-label="Попередній місяць"]')
    page.wait_for_timeout(200)
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', '← не повернув місяць')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    w = page.evaluate("document.querySelector('.panel.p-credits').getBoundingClientRect().width")
    check(w <= 1600, f'на 1920 Календар ширший за 1600: {w}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    table_1920(page, t)
    breakdown(page, t)


PAYDAYS = """sel=>[...document.querySelectorAll(sel)].filter(c=>[...c.querySelectorAll('.cal-badge')].some(b=>/^[АЗ]$/.test(b.textContent.trim()))).map(c=>c.querySelector('.cal-dn')?c.querySelector('.cal-dn').textContent.trim():c.firstChild.textContent.trim())"""
CELLBAL = """d=>{const c=[...document.querySelectorAll('.ck-cal .cal-cell')].find(c=>c.querySelector('.cal-dn')&&c.querySelector('.cal-dn').textContent.trim()===d);const b=c&&c.querySelector('.cal-bal');return b?b.textContent:''}"""


def table_1920(page, t):
    """Сітка ліворуч, таблиця праворуч на всю висоту, 1920x1080 і 1920x900 без прокрутки й без внутрішніх скролів."""
    cal = page.locator('.panel.p-credits.desk')
    wr = page.evaluate("document.querySelector('.ck-cal').getBoundingClientRect().width/document.querySelector('.ck-cols').getBoundingClientRect().width")
    check(0.5 <= wr <= 0.65, f'сітка займає {wr:.2f} ширини, а не 50-65 %')
    # таблиця на всю висоту колонки: нижній край картки таблиці = нижній край сітки
    gap = page.evaluate("Math.abs(document.querySelector('.ck-day').getBoundingClientRect().bottom-document.querySelector('.ck-cal').getBoundingClientRect().bottom)")
    check(gap <= 2, f'таблиця не на всю висоту: різниця {gap}px')
    pays = set(page.evaluate(PAYDAYS, '.ck-cal .cal-cell'))
    check(len(pays) == 2, f'у сітці не два дні виплат: {pays}')
    withbal = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-bal')).map(c=>c.querySelector('.cal-dn').textContent.trim())")
    allowed = pays | {str(t.day)}
    check(withbal and set(withbal) <= allowed, f'каса в клітинці не лише в дні виплат і сьогодні: {withbal}, дозволено {sorted(allowed)}')
    check(str(t.day) in withbal, 'у клітинці «сьогодні» немає каси')
    evdays = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-ln,.cal-more')).map(c=>Number(c.querySelector('.cal-dn').textContent))")
    rows = page.evaluate(ROWS)
    dates = {int(r['d'][8:]) for r in rows}
    check(set(evdays) <= dates, f'у таблиці немає дат з подіями: {sorted(set(evdays) - dates)}')
    check(t.day in dates and any('today' in r['c'] for r in rows), 'у таблиці немає підсвіченого рядка «сьогодні»')
    hd = page.evaluate("document.querySelector('.ck-day').innerText")
    for s in ('Дата', 'Подія', 'Сума', 'Баланс після'):
        check(s in hd, f'у таблиці немає колонки «{s}»')
    for d in sorted(dates):
        rr = [r for r in rows if int(r['d'][8:]) == d]
        if d >= t.day:
            check(rr[-1]['b'] is not None and rr[-1]['a'].strip() != '', f'{d}: немає балансу після на останньому рядку дня')
        else:
            check(all(r['b'] is None and 'past' in r['c'] for r in rr), f'{d}: минулий рядок не приглушений або з балансом')
    check(all(abs(r['h'] - 28) <= 1 for r in rows), f'рядки таблиці не 28px: {sorted({round(r["h"]) for r in rows})}')
    # кредитні обовʼязкові касу в дату не рухають (п. 12): баланс як у попереднього рядка, позначка «гасимо 24.MM»
    for i, r in enumerate(rows):
        if ' cr' in f" {r['c']}" and i and rows[i - 1]['b'] is not None and r['b'] is not None:
            check(r['b'] == rows[i - 1]['b'], f"{r['d']} {r['n']}: кредитний рядок змінив касу {rows[i - 1]['b']} -> {r['b']}")
            check('гасимо 24.' in r['n'], f"{r['d']} {r['n']}: без позначки «гасимо 24.MM»")
    if t.day <= 24:
        rep = [r for r in rows if r['d'].endswith('-24') and 'Погашення кредитки' in r['n']]
        check(len(rep) == 1, f'у таблиці немає погашення кредитки 24-го: {[r["n"] for r in rows if r["d"].endswith("-24")]}')
    for d in pays:
        if int(d) >= t.day:
            cb = page.evaluate(CELLBAL, d)
            tb = [r for r in rows if int(r['d'][8:]) == int(d)][-1]['b']
            v = int(''.join(ch for ch in cb if ch.isdigit()) or 0) * (-1 if '−' in cb else 1)
            check(abs(v - tb) <= 1, f'{d}: у клітинці {cb!r}, у таблиці {tb}')
    check(page.evaluate(INNER_SCROLL) == 0, 'у Календарі є внутрішній скрол')
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 1080, f'Календар не вміщається в 1920x1080: {sh}')
    page.mouse.move(2, 2)
    shot(page, 'v139-cal-1920.jpg', full=False)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 900, f'Календар не вміщається в 1920x900: {sh}')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)


def breakdown(page, t):
    """Клік по дню: розклад балансу (стартова каса, події до дня з балансом після, підсумок = баланс дня в таблиці)."""
    cal = page.locator('.panel.p-credits.desk')
    rows = page.evaluate(ROWS)
    fut = [r for r in rows if int(r['d'][8:]) > t.day and r['b'] is not None]
    check(fut, 'у таблиці немає майбутніх рядків з балансом')
    iso = fut[-1]['d']
    want = [r for r in rows if r['d'] == iso][-1]['b']
    page.click(f'.ck-cal .cal-cell[data-date="{iso}"]')
    page.wait_for_timeout(250)
    check(cal.locator('.cal-cell.sel').count() == 1, 'клік не виділив день')
    side = page.inner_text('.ck-day')
    check(f'РОЗКЛАД БАЛАНСУ · {int(iso[8:])} ' in side.upper(), f'шапка розкладу: {side[:60]!r}')
    st = page.locator('.ck-bd-st').inner_text()
    check('Стартова каса' in st, f'немає стартової каси: {st!r}')
    tot = page.locator('.ck-bd-tot').inner_text()
    v = int(''.join(ch for ch in tot.split('\n')[-1] if ch.isdigit()) or 0) * (-1 if '−' in tot.split('\n')[-1] else 1)
    check('Каса на кінець' in tot and abs(v - want) <= 1, f'підсумок розкладу {tot!r}, у таблиці {want}')
    n = page.locator('.ck-bd-row').count()
    check(n >= 3, f'у розкладі лише {n} рядків')
    page.mouse.move(2, 2)
    shot(page, 'cal-day-1920.jpg', full=False)
    page.click('.ck-day .ck-link')
    page.wait_for_timeout(200)
    check(page.locator('.ck-day .cal-tbl').count() == 1, '«Усі події» не повернули таблицю')


def short_frame(page):
    """Червона рамка дня, де каса після білого платежу нижче нуля: monobank 500 замість 12 500."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, '2026-10-08', [("mono_account_id:'demo-mono',balance:12500,", "mono_account_id:'demo-mono',balance:500,")])
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits.desk')
    sh = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell.short')].map(c=>c.querySelector('.cal-dn').textContent.trim())")
    check(len(sh) >= 1, 'немає червоної рамки дня з нестачею каси')
    bs = cal.locator('.ck-cal .cal-cell.short').first.evaluate("e=>getComputedStyle(e).boxShadow")
    check('inset' in bs and '2px' in bs, f'рамка не червона смуга: {bs}')
    for d in sh:
        sel = f'.ck-day .cal-ev[data-date="2026-10-{int(d):02d}"]'
        tys = page.evaluate("s=>[...document.querySelectorAll(s+'.short .ce-tg')].map(e=>e.textContent)", sel)
        check(tys and all(x in ('біла', 'погашення', 'комісія') for x in tys), f'{d}: рамка без білого платежу {tys}')
        bal = page.evaluate("s=>[...document.querySelectorAll(s+'.short')].map(r=>Number(r.dataset.bal))", sel)
        check(bal and all(b < 0 for b in bal), f'{d}: баланс після не відʼємний: {bal}')
    page.mouse.move(2, 2)
    shot(page, 'cal-short-1920.jpg', full=False)
    page.unroute(page.url)
    freeze(page, '2026-10-08')
    go_tab(page, 3)
    check(cal.locator('.cal-cell.short').count() == 0, 'червона рамка без нестачі')


def mobile(page):
    go_tab(page, 3)
    check(page.locator('.p-credits.desk').count() == 0, 'на телефоні показано ПК-Календар')
    check(page.locator('.panel.p-credits .cal-list .cal-ev').count() >= 1, 'на телефоні зник список подій календаря')
    check(page.locator('.panel.p-credits .cal-badge', has_text='А').count() == 1, 'на телефоні немає бейджа А')
    t = date.today()
    withbal = page.evaluate("[...document.querySelectorAll('.panel.p-credits .cal-bal-m')].map(e=>e.parentElement.firstChild.textContent.trim())")
    pays = set(page.evaluate(PAYDAYS, '.panel.p-credits .cal-cell'))
    check(withbal and set(withbal) <= pays | {str(t.day)}, f'на телефоні сума прогнозу не лише в дні виплат і сьогодні: {withbal}, виплати {pays}')
    # v139: минулі дні приглушеним тлом
    past = page.evaluate("[...document.querySelectorAll('.panel.p-credits .cal-cell.past')].map(e=>getComputedStyle(e).backgroundColor)")
    check(len(past) == t.day - 1, f'на телефоні позначено {len(past)} минулих днів, а не {t.day - 1}')
    check(all(b not in ('rgba(0, 0, 0, 0)', 'transparent') for b in past), f'минулі дні без тла: {set(past)}')
    page.mouse.move(2, 2)
    shot(page, 'v139-cal-375.jpg', full=False)


CHECKS = [
    ('Календар: KPI, сітка, минулі дні, сьогодні, таблиця, розклад дня, 1920x1080', 'desktop', desktop),
    ('Календар на телефоні: як раніше плюс тло минулих днів', 'mobile', mobile),
    ('Календар: червона рамка дня з нестачею каси', 'desktop', short_frame),
]
