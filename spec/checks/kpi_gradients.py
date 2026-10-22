"""v183: KPI-картки Бюджету й плитки Огляду з мʼяким градієнтом за змістом; текст читається на реальних пікселях в обох темах, 1280 і 390."""
from io import BytesIO
import re

from PIL import Image

from helpers import check, freeze, go_tab, shot
from checks.monthly_budget import seed_demo

DAY = '2026-10-17'
# позначає видимі елементи з власним текстом у картці; повертає їх кількість
MARK = """e=>{let n=0;for(const x of e.querySelectorAll('*')){const own=[...x.childNodes].some(c=>c.nodeType===3&&c.textContent.trim());const r=x.getBoundingClientRect();
if(own&&r.width>0&&r.height>0&&getComputedStyle(x).visibility!=='hidden'&&r.top>=0&&r.bottom<=innerHeight){x.setAttribute('data-cx',n++)}}return n}"""
KG = "e=>getComputedStyle(e).getPropertyValue('--kg').trim()"
TOKEN = "v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim()"


def luminance(rgb):
    linear = [v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def contrast(page, el):
    """Мінімальний контраст тексту до пікселів під ним: знімок із текстом і з прозорим текстом."""
    fg = [float(v) for v in re.findall(r'[\d.]+', el.evaluate('e=>getComputedStyle(e).color'))]
    alpha = fg[3] if len(fg) > 3 else 1
    box = el.bounding_box()
    ink = Image.open(BytesIO(page.screenshot(clip=box))).convert('RGB')
    old = el.get_attribute('style')
    el.evaluate('e=>e.style.setProperty("color","transparent","important")')
    try:
        bg = Image.open(BytesIO(page.screenshot(clip=box))).convert('RGB')
    finally:
        el.evaluate('(e,s)=>s===null?e.removeAttribute("style"):e.setAttribute("style",s)', old)
    backs = {b for a, b in zip(ink.getdata(), bg.getdata()) if max(abs(x - y) for x, y in zip(a, b)) > 16}
    if not backs:
        return None
    out = []
    for b in backs:
        blend = [f * alpha + c * (1 - alpha) for f, c in zip(fg[:3], b)]
        lo, hi = sorted((luminance(blend), luminance(b)))
        out.append((hi + .05) / (lo + .05))
    return min(out)


def cards(page, sel, tag, want):
    loc = page.locator(sel)
    check(loc.count() >= want, f'{tag}: карток {loc.count()} < {want}')
    paints = loc.evaluate_all('es=>es.map(e=>getComputedStyle(e).backgroundImage)')
    check(all('gradient' in p for p in paints), f'{tag}: немає градієнта {paints}')
    check(len(set(paints)) == len(paints), f'{tag}: однакові градієнти у різних карток')
    worst = 99
    for i in range(loc.count()):
        card = loc.nth(i)
        if not card.is_visible():
            continue
        n = card.evaluate(MARK)
        for j in range(n):
            el = card.locator(f'[data-cx="{j}"]')
            c = contrast(page, el)
            if c is None:
                continue
            check(c >= 4.5, f'{tag}: «{el.inner_text()[:30]}» контраст {c:.2f} < 4.5')
            worst = min(worst, c)
        card.evaluate("e=>e.querySelectorAll('[data-cx]').forEach(x=>x.removeAttribute('data-cx'))")
    return worst


def run(page, sizes, kind):
    for theme in ('light', 'dark'):
        for w, hgt in sizes:
            page.set_viewport_size({'width': w, 'height': hgt})
            page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
            freeze(page, DAY)
            check(page.evaluate('document.documentElement.dataset.theme') == theme, f'тема {theme} не застосована')
            go_tab(page, 1)
            page.mouse.move(2, 2)
            b = cards(page, '.bud-kpis .bud-kpi', f'{theme}/{w} Бюджет', 4)
            shot(page, f'kpi-gradients-budget-{kind}-{w}-{theme}.jpg', full=False)
            go_tab(page, 0)
            page.mouse.move(2, 2)
            o = cards(page, '.dv-kpi.kpi-t', f'{theme}/{w} Огляд', 4)
            shot(page, f'kpi-gradients-overview-{kind}-{w}-{theme}.jpg', full=False)
            print(f'      {theme}/{w}: мінімальний контраст Бюджет {b:.2f}, Огляд {o:.2f}')
    # перевитрата: залишок бюджету і плитка Огляду переходять у червонуватий тон
    w, hgt = sizes[0]
    page.set_viewport_size({'width': w, 'height': hgt})
    seed_demo(page, DAY, [("[24,'Сільпо',2133,", "[24,'Сільпо',40000,")])
    over = page.evaluate(TOKEN, '--kg-over')
    go_tab(page, 1)
    check(page.locator('.bud-avail .bud-kpi-v').get_attribute('data-over') == '1', 'сценарій без перевитрати')
    check(page.locator('.bud-kpi.bud-avail').evaluate(KG) == over, 'залишок у перевитраті без червонуватого тону')
    worst = cards(page, '.bud-kpis .bud-kpi', f'{w} перевитрата', 4)
    go_tab(page, 0)
    tile = page.locator('.dv-kpi.kpi-budget').first
    if tile.locator('.kpi-row[data-over]').count():
        check(tile.evaluate(KG) == over, 'плитка «Бюджет періоду» у перевитраті без червонуватого тону')
    print(f'      перевитрата/{w}: тон {over}, мінімальний контраст {worst:.2f}')


def desktop(page):
    run(page, [(1280, 800)], 'desktop')


def mobile(page):
    run(page, [(390, 844)], 'mobile')


CHECKS = [('KPI-градієнти Бюджету й Огляду: ПК 1280, обидві теми, контраст', 'desktop', desktop),
          ('KPI-градієнти Бюджету й Огляду: телефон 390, обидві теми, контраст', 'mobile', mobile)]
