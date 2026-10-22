"""Бюджет на ПК: колонки на одному рівні; підписи графіка збігаються з картками зверху; відсоток біля витраченого з кольором за порогом."""
from io import BytesIO
import re

from PIL import Image

from helpers import check, freeze, go_tab, num, shot

FILL = {'ok': '--green-t', 'warn': '--yellow-t', 'over': '--red-t'}


def luminance(rgb):
    linear = [v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def svg_contrast(page, loc):
    """Мінімальний контраст тексту SVG до реальних пікселів під ним: знімок з текстом і без (fill прозорий)."""
    fg = [float(v) for v in re.findall(r'[\d.]+', loc.evaluate('e=>getComputedStyle(e).fill'))][:3]
    box = loc.bounding_box()
    clip = {'x': box['x'] - 1, 'y': box['y'] - 1, 'width': box['width'] + 2, 'height': box['height'] + 2}
    ink = Image.open(BytesIO(page.screenshot(clip=clip))).convert('RGB')
    old = loc.get_attribute('fill')
    loc.evaluate('e=>e.setAttribute("fill","transparent")')
    try:
        bg = Image.open(BytesIO(page.screenshot(clip=clip))).convert('RGB')
    finally:
        loc.evaluate('(e,f)=>e.setAttribute("fill",f)', old)
    backs = {b for a, b in zip(ink.getdata(), bg.getdata()) if max(abs(x - y) for x, y in zip(a, b)) > 16}
    check(backs, 'немає пікселів тексту відсотка')
    ratios = []
    for b in backs:
        lo, hi = sorted((luminance(fg), luminance(b)))
        ratios.append((hi + .05) / (lo + .05))
    return min(ratios)


def labels(page):
    # 10.10: частина демо-операцій місяця в майбутньому, підписи й картки мають їх однаково не рахувати.
    for width, height, day in ((1280, 800, '2026-10-17'), (1440, 900, '2026-10-17'), (1905, 940, '2026-10-17'), (1280, 800, '2026-10-10')):
        page.set_viewport_size({'width': width, 'height': height})
        freeze(page, day)
        go_tab(page, 1)
        cat, top = page.locator('.bud-catcard').bounding_box(), page.locator('.bud-top').bounding_box()
        diff = abs(cat['y'] + cat['height'] - top['y'] - top['height'])
        check(diff <= 1, f'{width}: колонки закінчуються на різній висоті, різниця {diff:.1f}px')
        spent = num(page.locator('.bud-spent .bud-kpi-v').inner_text())
        rest = num(page.locator('.bud-avail .bud-kpi-v').inner_text())
        if page.locator('.bud-avail .bud-kpi-v').get_attribute('data-over') == '1':
            rest = -rest
        plan = page.evaluate('window.__calendarBudget.plan') / 100
        lbl_spent = num(page.locator('.bud-lbl-spent tspan').first.text_content())
        lbl_rest = num(page.locator('.bud-lbl-rest tspan').nth(1).text_content())
        lbl_pct = int(re.match(r'(\d+)%$', page.locator('.bud-lbl-pct').text_content()).group(1))
        check(abs(lbl_spent - spent) < .005, f'{width}: підпис витрат {lbl_spent} != {spent}')
        check(abs(lbl_rest - abs(rest)) < .005, f'{width}: підпис залишку {lbl_rest} != {abs(rest)}')
        check(abs(plan - spent - rest) < .005, f'{width}: бюджет {plan} != витрачено {spent} + залишок {rest}')
        check(lbl_pct == round(spent / plan * 100), f'{width}: відсоток {lbl_pct} != {spent}/{plan}')
        fonts = page.locator('.bud-chart-labels tspan').evaluate_all('es=>es.map(e=>parseFloat(getComputedStyle(e).fontSize)*e.ownerSVGElement.getBoundingClientRect().width/520)')
        check(min(fonts) >= 10.5, f'{width}: задрібні підписи графіка {fonts}')
        print(f'      {day} {width}: витрачено {spent}, залишок {rest}, бюджет {plan}, {lbl_pct}%, колонки ±{diff:.1f}px')
        shot(page, f'budget-chart-labels-{width}.jpg', full=False)


def no_captions(page):
    """v183: під графіком немає легенди й видимого readout; readout лишається для скринрідера."""
    check(page.locator('.calendar-budget .bud-pace .bud-legend').count() == 0, 'легенда під графіком лишилась')
    rd = page.locator('.bud-chart-readout')
    check(rd.count() == 1 and rd.get_attribute('aria-live') == 'polite', 'readout для скринрідера зник')
    box = rd.bounding_box()
    check(box['width'] <= 1 and box['height'] <= 1, f'readout видимий: {box}')
    check('Бюджет:' in rd.text_content(), 'readout без тексту')


def percent(page):
    """v183: «N%» без слова «бюджету» одразу після суми витраченого; колір за порогами 80 і 100; контраст ≥ 4.5 в обох темах."""
    seen = set()
    for tone, amount in (('ok', None), ('warn', 62000), ('over', 80000)):
        patch = None if amount is None else [("[24,'Сільпо',2133,", f"[24,'Сільпо',{amount},")]
        for theme in ('dark', 'light'):
            page.set_viewport_size({'width': 1280, 'height': 800})
            page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
            freeze(page, '2026-10-17', patch)
            check(page.evaluate('document.documentElement.dataset.theme') == theme, f'тема {theme} не застосована')
            go_tab(page, 1)
            page.wait_for_timeout(300)
            no_captions(page)
            b = page.evaluate('window.__calendarBudget')
            pct = page.locator('.bud-lbl-pct')
            txt = pct.text_content()
            check(re.fullmatch(r'\d+%', txt) is not None, f'{tone}: відсоток з зайвим текстом {txt!r}')
            check('бюджету' not in page.locator('.bud-chart-labels').text_content(), f'{tone}: лишилось слово «бюджету»')
            spent_now = b['fact']
            value = round(spent_now / b['plan'] * 100)
            check(int(txt[:-1]) == value, f'{tone}: {txt} != {value}%')
            want = 'over' if spent_now > b['plan'] or value > 100 else 'warn' if value >= 80 else 'ok'
            check(want == tone, f'сценарій {tone} дав {value}% ({want})')
            check(pct.get_attribute('data-tone') == tone, f'{tone}: data-tone {pct.get_attribute("data-tone")}')
            token = page.evaluate("v=>{const p=document.createElement('span');p.style.color='var('+v+')';document.body.appendChild(p);const c=getComputedStyle(p).color;p.remove();return c}", FILL[tone])
            check(pct.evaluate('e=>getComputedStyle(e).fill') == token, f'{tone}: колір відсотка не {FILL[tone]}')
            # поруч із сумою: той самий рядок, зазор 0-16 px праворуч
            amt = page.locator('.bud-lbl-spent tspan').first.bounding_box()
            pb = pct.bounding_box()
            gap = pb['x'] - (amt['x'] + amt['width'])
            check(0 <= gap <= 16 and abs((pb['y'] + pb['height'] / 2) - (amt['y'] + amt['height'] / 2)) <= 3, f'{tone}: відсоток не біля суми, зазор {gap:.1f}')
            svg = page.locator('.bud-chart').bounding_box()
            check(pb['x'] >= svg['x'] and pb['x'] + pb['width'] <= svg['x'] + svg['width'] + .5 and pb['y'] >= svg['y'], f'{tone}: відсоток виходить за графік')
            c = svg_contrast(page, pct)
            check(c >= 4.5, f'{tone}/{theme}: контраст відсотка {c:.2f} < 4.5')
            seen.add(tone)
            print(f'      {tone}/{theme}: {txt} ({spent_now / 100:.2f} з {b["plan"] / 100:.2f}), зазор {gap:.1f}px, контраст {c:.2f}')
            shot(page, f'budget-chart-pct-{tone}-{theme}.jpg', full=False)
    check(seen == {'ok', 'warn', 'over'}, f'не всі пороги: {seen}')


CHECKS = [('Бюджет ПК: рівні колонки, підписи графіка = картки', 'desktop', labels),
          ('Бюджет ПК: відсоток біля витраченого, колір за порогами, без легенди', 'desktop', percent)]
