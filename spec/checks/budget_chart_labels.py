"""Бюджет на ПК: колонки на одному рівні; підписи графіка збігаються з картками зверху."""
import re
from helpers import check, freeze, go_tab, num, shot


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
        plan = num(re.search(r'Бюджет: ([^·]+)', page.locator('.bud-chart-readout').inner_text()).group(1))
        lbl_spent = num(page.locator('.bud-lbl-spent tspan').first.text_content())
        lbl_rest = num(page.locator('.bud-lbl-rest tspan').nth(1).text_content())
        lbl_pct = int(re.match(r'(\d+)%', page.locator('.bud-lbl-pct').text_content()).group(1))
        check(abs(lbl_spent - spent) < .005, f'{width}: підпис витрат {lbl_spent} != {spent}')
        check(abs(lbl_rest - rest) < .005, f'{width}: підпис залишку {lbl_rest} != {rest}')
        check(abs(plan - spent - rest) < .005, f'{width}: бюджет {plan} != витрачено {spent} + залишок {rest}')
        check(lbl_pct == round(spent / plan * 100), f'{width}: відсоток {lbl_pct} != {spent}/{plan}')
        fonts = page.locator('.bud-chart-labels tspan').evaluate_all('es=>es.map(e=>parseFloat(getComputedStyle(e).fontSize)*e.ownerSVGElement.getBoundingClientRect().width/520)')
        check(min(fonts) >= 10.5, f'{width}: задрібні підписи графіка {fonts}')
        print(f'      {day} {width}: витрачено {spent}, залишок {rest}, бюджет {plan}, {lbl_pct}%, колонки ±{diff:.1f}px')
        shot(page, f'budget-chart-labels-{width}.jpg', full=False)


CHECKS = [('Бюджет ПК: рівні колонки, підписи графіка = картки', 'desktop', labels)]
