# Щільність ПК на 1920x900: Огляд і Календар без прокрутки сторінки, числа KPI до 30px, основний текст 14px, бейджі А/З/борг читаються
from helpers import check, go_tab, shot

FIT = "({sh:document.scrollingElement.scrollHeight,ih:innerHeight})"
KPI_FS = """[...document.querySelectorAll('.dv-kpi-v, .ck-kpi > div:nth-child(2), .bud-kpi-v')].filter(e=>e.offsetParent).map(e=>parseFloat(getComputedStyle(e).fontSize))"""
KPI_H = """[...document.querySelectorAll('.dv-kpi, .ck-kpi')].filter(e=>e.offsetParent).map(e=>Math.round(e.getBoundingClientRect().height))"""


def fit(page):
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    for i, name, kmax in ((0, 'Огляд', 96), (3, 'Календар', 90)):
        go_tab(page, i)
        page.wait_for_timeout(300)
        m = page.evaluate(FIT)
        check(m['sh'] <= m['ih'] + 8, f'{name} на 1920x900 прокручується: {m["sh"]} > {m["ih"]}')
        fs = page.evaluate(KPI_FS)
        check(fs and max(fs) <= 30, f'{name}: число KPI {max(fs) if fs else None}px, а не до 30')
        hs = page.evaluate(KPI_H)
        check(hs and max(hs) <= kmax + 0.5, f'{name}: KPI заввишки {hs}, а не до {kmax}px')
    # основний текст ПК 14px на рядку операції (Огляд, «Останні операції»)
    go_tab(page, 0)
    page.wait_for_timeout(200)
    row = page.evaluate("getComputedStyle(document.querySelector('.dv-recent div[style*=\"cursor\"] span:nth-child(2)')).fontSize")
    check(row == '14px', f'рядок операції {row}, а не 14px')
    # бейджі виплат і боргу в сітці Календаря: щонайменше 12px і не обрізані
    go_tab(page, 3)
    page.wait_for_timeout(200)
    b = page.evaluate("""[...document.querySelectorAll('.ck-cal .cal-badge, .ck-cal .cal-debt')].map(e=>{const r=e.getBoundingClientRect();return{t:e.innerText.trim(),fs:parseFloat(getComputedStyle(e).fontSize),w:r.width,sw:e.scrollWidth,cw:e.clientWidth}})""")
    check(len(b) >= 2, f'у сітці лише {len(b)} бейджів виплат і боргу')
    for x in b:
        check(x['fs'] >= 12 and x['w'] > 0 and x['sw'] <= x['cw'] + 1, f'бейдж нечитабельний: {x}')
    page.mouse.move(2, 2)
    shot(page, 'cal-1920.jpg', full=False)
    go_tab(page, 1)
    page.wait_for_timeout(300)
    shot(page, 'budget-1920.jpg', full=False)


def laptop(page):
    """1280x800: прокрутка дозволена, але рядок KPI і перша картка видно одразу"""
    page.set_viewport_size({'width': 1280, 'height': 800})
    page.wait_for_timeout(300)
    for i, kpi, first, nm in ((0, '.dv-kpis', '.dv-fc', 'ov-1280.jpg'), (3, '.ck-kpis', '.ck-cal', 'cal-1280.jpg')):
        go_tab(page, i)
        page.wait_for_timeout(300)
        kb = page.locator(kpi).bounding_box()
        fb = page.locator(first).bounding_box()
        check(kb and kb['y'] + kb['height'] <= 800, f'{kpi}: рядок KPI не вміщується на 1280x800: {kb}')
        check(fb and fb['y'] < 800 - 120, f'{first}: першу картку не видно на 1280x800: {fb}')
        page.mouse.move(2, 2)
        shot(page, nm, full=False)


CHECKS = [
    ('ПК 1920x900: Огляд і Календар без прокрутки, KPI, 14px, бейджі', 'desktop', fit),
    ('ПК 1280x800: KPI і перша картка видно', 'desktop', laptop),
]
