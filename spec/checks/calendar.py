# ПК-Календар: KPI, сітка місяця 7 колонок, сьогодні, бейджі виплат і боргу, ← → місяць, події дня праворуч; телефон без змін
from datetime import date

from helpers import check, go_tab, shot

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
    # сітка: 7 колонок, клітинки від 92px, сьогодні обведене
    cols = page.evaluate("getComputedStyle(document.querySelector('.ck-cal .cal-days')).gridTemplateColumns.split(' ').length")
    check(cols == 7, f'у сітці {cols} колонок')
    hs = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.getBoundingClientRect().height)")
    check(len(hs) >= 28 and min(hs) >= 92, f'клітинки нижчі за 92px: {min(hs) if hs else None}')
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', f'заголовок місяця: {page.inner_text(".ck-month")!r}')
    today = cal.locator('.cal-cell.today')
    check(today.count() == 1, 'немає клітинки «сьогодні»')
    bw = today.evaluate("e=>getComputedStyle(e).borderTopWidth")
    check(bw == '2px', f'сьогодні не обведене: {bw}')
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
    # клік по дню: виділення і події праворуч
    day = cal.locator('.cal-cell:has(.cal-ln)').first
    dn = day.locator('.cal-dn').inner_text()
    day.click()
    page.wait_for_timeout(250)
    check(cal.locator('.cal-cell.sel').count() == 1, 'клік не виділив день')
    side = page.inner_text('.ck-day')
    check(f'ПОДІЇ {dn} ' in side.upper(), f'праворуч не події вибраного дня: {side[:60]!r}')
    check(cal.locator('.ck-day .cal-ev').count() >= 1, 'у подіях дня порожньо')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg')
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
    # 1920: контент до 1400, без скролу
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    w = page.evaluate("document.querySelector('.panel.p-credits').getBoundingClientRect().width")
    check(w <= 1400, f'на 1920 Календар ширший за 1400: {w}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    shot(page, 'cal-1920.jpg')


def mobile(page):
    go_tab(page, 3)
    check(page.locator('.p-credits.desk').count() == 0, 'на телефоні показано ПК-Календар')
    check(page.locator('.panel.p-credits .cal-list .cal-ev').count() >= 1, 'на телефоні зник список подій календаря')
    check(page.locator('.panel.p-credits .cal-badge', has_text='А').count() == 1, 'на телефоні немає бейджа А')


CHECKS = [
    ('Календар: KPI, сітка, сьогодні, бейджі, місяць, день', 'desktop', desktop),
    ('Календар на телефоні без змін', 'mobile', mobile),
]
