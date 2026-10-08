# ПК-Календар: KPI, сітка місяця 7 колонок (прогноз лише в дні виплат і сьогодні), сьогодні, бейджі виплат і боргу, ← → місяць,
# праворуч таблиця «Події і баланс» на весь місяць; червона рамка дня з непокритим білим платежем; сторінка вміщається в 1920x900
from datetime import date

from helpers import check, freeze, go_tab, shot

MO = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень', 'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'


def desktop(page):
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits.desk')
    check(cal.count() == 1, 'на ПК немає окремого Календаря')
    t = date.today()
    # KPI на всю ширину
    kpis = cal.locator('.ck-kpis .ck-kpi')
    check(kpis.count() == 3, f'KPI {kpis.count()}, а не 3')
    kt = cal.locator('.ck-kpis').inner_text().lower()
    for s in ('Обовʼязкові до наступної виплати', 'Розстрочки', 'Борги', '/міс', 'залишок'):
        check(s.lower() in kt, f'у рядку KPI немає «{s}»')
    # сітка: 7 колонок, компактні клітинки (від 54px, у місяці з 6 тижнів від 46px), сьогодні обведене
    cols = page.evaluate("getComputedStyle(document.querySelector('.ck-cal .cal-days')).gridTemplateColumns.split(' ').length")
    check(cols == 7, f'у сітці {cols} колонок')
    hs = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.getBoundingClientRect().height)")
    r6 = cal.locator('.cal-days.r6').count() == 1
    check(len(hs) >= 28 and min(hs) >= (46 if r6 else 54), f'клітинки нижчі за {46 if r6 else 54}px: {min(hs) if hs else None}')
    # у клітинці не більше 2 рядків подій, решта «+N»
    many = page.evaluate("Math.max(0,...[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.querySelectorAll('.cal-ln').length))")
    check(many <= 2, f'у клітинці {many} рядків подій, а не до 2')
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', f'заголовок місяця: {page.inner_text(".ck-month")!r}')
    today = cal.locator('.cal-cell.today')
    check(today.count() == 1, 'немає клітинки «сьогодні»')
    # дизайн ПК v135: сьогодні тим самим маркером, що в Потоці (тло акценту і ліва смуга 2px)
    sh = today.evaluate("e=>getComputedStyle(e).boxShadow")
    check('inset' in sh and '2px 0px 0px' in sh, f'сьогодні без лівої смуги акценту: {sh}')
    check(today.locator('.cal-dn').inner_text() == str(t.day), 'обведене не сьогоднішнє число')
    # бейджі виплат і боргу
    check(cal.locator('.cal-badge', has_text='А').count() == 1 and cal.locator('.cal-badge', has_text='З').count() == 1, 'немає бейджів А і З')
    if t.day <= 25:
        check(cal.locator('.cal-debt').count() == 1, 'немає бейджа «борг»')
    # прогноз під сіткою
    r0 = page.inner_text('.cal-fc-readout')
    check(r0.startswith('Баланс на') and '≈' in r0, f'повзунок прогнозу: {r0!r}')
    page.locator('.cal-fc-range').evaluate(SETR, 12)
    page.wait_for_timeout(150)
    check(page.inner_text('.cal-fc-readout') != r0, 'повзунок не змінив баланс')
    # клік по дню: виділення в сітці й підсвічені рядки цього дня в таблиці праворуч
    day = cal.locator('.cal-cell:has(.cal-ln)').first
    dn = day.locator('.cal-dn').inner_text()
    day.click()
    page.wait_for_timeout(250)
    check(cal.locator('.cal-cell.sel').count() == 1, 'клік не виділив день')
    side = page.inner_text('.ck-day')
    check(f'ПОДІЇ І БАЛАНС · {dn} ' in side.upper(), f'у шапці таблиці не вибраний день: {side[:60]!r}')
    iso = f'{t.year}-{t.month:02d}-{int(dn):02d}'
    sel = cal.locator('.ck-day .cal-ev.sel')
    check(sel.count() >= 1 and sel.count() == cal.locator(f'.ck-day .cal-ev[data-date="{iso}"]').count(), 'рядки вибраного дня не підсвічені')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg', full=False)
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    # ← → міняють місяць календаря
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    page.wait_for_timeout(200)
    n = date(t.year + (t.month == 12), t.month % 12 + 1, 1)
    check(page.inner_text('.ck-month') == f'{MO[n.month - 1]} {n.year}', '→ не перейшов на наступний місяць')
    check(cal.locator('.cal-cell.today').count() == 0, 'у наступному місяці є «сьогодні»')
    page.click('.ck-arr[aria-label="Попередній місяць"]')
    page.wait_for_timeout(200)
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', '← не повернув місяць')
    # 1920x900: контент до 1600, без скролу
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    w = page.evaluate("document.querySelector('.panel.p-credits').getBoundingClientRect().width")
    check(w <= 1600, f'на 1920 Календар ширший за 1600: {w}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    table_1920(page, t)
    page.mouse.move(2, 2)
    shot(page, 'cal-1920.jpg', full=False)


# дні виплат (бейджі А і З): лише в них і сьогодні сума прогнозу в клітинці
PAYDAYS = """sel=>[...document.querySelectorAll(sel)].filter(c=>[...c.querySelectorAll('.cal-badge')].some(b=>/^[АЗ]$/.test(b.textContent.trim()))).map(c=>c.querySelector('.cal-dn')?c.querySelector('.cal-dn').textContent.trim():c.firstChild.textContent.trim())"""
CELLBAL = """d=>{const c=[...document.querySelectorAll('.ck-cal .cal-cell')].find(c=>c.querySelector('.cal-dn')&&c.querySelector('.cal-dn').textContent.trim()===d);const b=c&&c.querySelector('.cal-bal');return b?b.textContent:''}"""


def table_1920(page, t):
    """Відгук власника 08.10: сітка вужча (45-50 %), суми лише в дні виплат і сьогодні, таблиця на весь місяць з балансом, усе в 1920x900."""
    cal = page.locator('.panel.p-credits.desk')
    wr = page.evaluate("document.querySelector('.ck-cal').getBoundingClientRect().width/document.querySelector('.ck-cols').getBoundingClientRect().width")
    check(0.42 <= wr <= 0.52, f'сітка займає {wr:.2f} ширини, а не 45-50 %')
    pays = set(page.evaluate(PAYDAYS, '.ck-cal .cal-cell'))
    check(len(pays) == 2, f'у сітці не два дні виплат: {pays}')
    withbal = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-bal')).map(c=>c.querySelector('.cal-dn').textContent.trim())")
    allowed = pays | {str(t.day)}
    check(withbal and set(withbal) <= allowed, f'сума прогнозу не лише в дні виплат і сьогодні: {withbal}, дозволено {sorted(allowed)}')
    check(str(t.day) in withbal, 'у клітинці «сьогодні» немає суми прогнозу')
    # таблиця: рядок на кожну дату з подією (клітинки з рядками подій або «+N»), баланс на останньому рядку дат від сьогодні
    evdays = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-ln,.cal-more')).map(c=>Number(c.querySelector('.cal-dn').textContent))")
    rows = page.evaluate("""[...document.querySelectorAll('.ck-day .cal-tbl .cal-ev')].map(r=>({d:r.dataset.date,b:r.dataset.bal==null?null:Number(r.dataset.bal),
h:r.getBoundingClientRect().height,c:r.className,a:r.querySelector('.ce-b').textContent}))""")
    dates = {int(r['d'][8:]) for r in rows}
    check(set(evdays) <= dates, f'у таблиці немає дат з подіями: {sorted(set(evdays) - dates)}')
    check(t.day in dates and any('today' in r['c'] for r in rows), 'у таблиці немає підсвіченого рядка «сьогодні»')
    hd = page.evaluate("document.querySelector('.ck-day').innerText")
    for s in ('Дата', 'Подія', 'Тип', 'Сума', 'Баланс після'):
        check(s in hd, f'у таблиці немає колонки «{s}»')
    for d in sorted(dates):
        rr = [r for r in rows if int(r['d'][8:]) == d]
        if d >= t.day:
            check(rr[-1]['b'] is not None and rr[-1]['a'].strip() != '', f'{d}: немає балансу після на останньому рядку дня')
        else:
            check(all(r['b'] is None and 'past' in r['c'] for r in rr), f'{d}: минулий рядок не приглушений або з балансом')
    check(all(abs(r['h'] - 28) <= 1 for r in rows), f'рядки таблиці не 28px: {sorted({round(r["h"]) for r in rows})}')
    check(page.evaluate("document.querySelector('.ck-day .cal-tbl').scrollHeight<=document.querySelector('.ck-day .cal-tbl').clientHeight+1"), 'таблиця має внутрішній скрол')
    check(cal.locator('.ck-more').count() == 0, 'у таблиці лишилось «+N»')
    # баланс у клітинці виплати = баланс після цього дня в таблиці (та сама лінія прогнозу)
    for d in pays:
        if int(d) >= t.day:
            cb = page.evaluate(CELLBAL, d)
            tb = [r for r in rows if int(r['d'][8:]) == int(d)][-1]['b']
            v = int(''.join(ch for ch in cb if ch.isdigit()) or 0) * (-1 if cb.strip().startswith('−') else 1)
            check(abs(v - tb) <= 1, f'{d}: у клітинці {cb!r}, у таблиці {tb}')
    # розстрочки й постійні під сіткою поруч, сторінка без вертикального скролу
    check(page.evaluate("(()=>{const a=document.querySelector('.ck-cal').getBoundingClientRect(),c=document.querySelector('.ck-crs').getBoundingClientRect(),f=document.querySelector('.ck-fixed').getBoundingClientRect();return c.top>=a.bottom&&f.top>=a.bottom&&Math.abs(c.top-f.top)<2})()"), 'Розстрочки й Постійні не під сіткою поруч')
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 900, f'Календар не вміщається в 1920x900: {sh}')


def short_frame(page):
    """(д) червона рамка дня з білим платежем, який не покривають власні кошти: monobank 500 замість 12 500."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, '2026-10-08', [("mono_account_id:'demo-mono',balance:12500,", "mono_account_id:'demo-mono',balance:500,")])
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits.desk')
    sh = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell.short')].map(c=>c.querySelector('.cal-dn').textContent.trim())")
    check(len(sh) >= 1, 'немає червоної рамки дня з непокритим білим платежем')
    bs = cal.locator('.ck-cal .cal-cell.short').first.evaluate("e=>getComputedStyle(e).boxShadow")
    check('inset' in bs and '2px' in bs, f'рамка не червона смуга: {bs}')
    for d in sh:
        sel = f'.ck-day .cal-ev[data-date="2026-10-{int(d):02d}"]'
        tys = page.evaluate("s=>[...document.querySelectorAll(s+' .ce-t')].map(e=>e.textContent)", sel)
        check('біла' in tys or 'погашення' in tys, f'{d}: рамка без білого платежу {tys}')
        last = page.evaluate("s=>{const r=[...document.querySelectorAll(s)].pop();return r&&r.dataset.bal!=null?Number(r.dataset.bal):null}", sel)
        check(last is not None and last < 0, f'{d}: баланс після не відʼємний: {last}')
        check(cal.locator(sel + '.short').count() == 1, f'{d}: рядок таблиці без позначки нестачі')
    page.mouse.move(2, 2)
    shot(page, 'cal-short-1920.jpg', full=False)
    # без нестачі (звичайне демо) рамок немає
    page.unroute(page.url)
    freeze(page, '2026-10-08')
    go_tab(page, 3)
    check(cal.locator('.cal-cell.short').count() == 0, 'червона рамка без нестачі')


def mobile(page):
    go_tab(page, 3)
    check(page.locator('.p-credits.desk').count() == 0, 'на телефоні показано ПК-Календар')
    check(page.locator('.panel.p-credits .cal-list .cal-ev').count() >= 1, 'на телефоні зник список подій календаря')
    check(page.locator('.panel.p-credits .cal-badge', has_text='А').count() == 1, 'на телефоні немає бейджа А')
    # сума прогнозу лише в дні виплат і сьогодні
    t = date.today()
    withbal = page.evaluate("[...document.querySelectorAll('.panel.p-credits .cal-bal-m')].map(e=>e.parentElement.firstChild.textContent.trim())")
    pays = set(page.evaluate(PAYDAYS, '.panel.p-credits .cal-cell'))
    check(withbal and set(withbal) <= pays | {str(t.day)}, f'на телефоні сума прогнозу не лише в дні виплат і сьогодні: {withbal}, виплати {pays}')


CHECKS = [
    ('Календар: KPI, сітка, сьогодні, бейджі, місяць, день', 'desktop', desktop),
    ('Календар на телефоні без змін', 'mobile', mobile),
    ('Календар: червона рамка дня з непокритим білим платежем', 'desktop', short_frame),
]
