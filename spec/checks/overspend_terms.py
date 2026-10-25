"""v183: відʼємний залишок показується як «Перевитрата» з додатною сумою червоним і без мінуса; додатний лишається «Залишок»."""
import re

from helpers import check, expand_groups, go_tab, num, shot
from checks.monthly_budget import seed_demo

DAY = '2026-10-17'
PLAN = 1000  # seed_demo: 30 000 ₴ на місяць, кожна категорія по 1 000 ₴
TOTAL = 30000
# Сільпо (рядок 24) у фікстурі падає на 13.10: і в календарний місяць, і в період виплати 06.10-21.10
OVER = [("[24,'Сільпо',2133,", "[24,'Сільпо',40000,")]
MINUS = re.compile(r'[−-]\s*\d')
RED = """el=>{const p=document.createElement('span');p.style.color='var(--red-t)';el.appendChild(p);const r=getComputedStyle(p).color;p.remove();return getComputedStyle(el).color===r}"""


def facts(page):
    """Факт місяця з сирих демо-операцій (як budget.py): категорія -> ₴, плюс разом."""
    raw = page.evaluate('txDemo(2026,9)')
    valid = [t for t in raw if t['type'] == 'expense' and t.get('fixed_id') is None and t.get('credit_id') is None and '2026-10-01' <= t['date'][:10] <= DAY]
    by = {}
    for t in valid:
        k = str(t.get('category_id')) if t.get('category_id') is not None else 'unallocated'
        by[k] = by.get(k, 0) + round(t['amount'] * 100)
    return {k: v / 100 for k, v in by.items()}, valid


def amount(page, loc, over, label, what, red=True):
    """Перевіряє підпис, суму без знака, відсутність мінуса і червоний колір (лише для перевитрати)."""
    text = loc.text_content()
    check(not MINUS.search(text), f'{what}: мінус перед сумою: {text!r}')
    check(label in text, f'{what}: немає «{label}»: {text!r}')
    check((loc.get_attribute('data-over') == '1') == over, f'{what}: data-over не відповідає {over}')
    if over and red:
        check(loc.evaluate(RED), f'{what}: перевитрата не червона')
    return num(text.split(label, 1)[1] if label else text)


def surfaces(page, over, tag):
    by, valid = facts(page)
    savings_ids={str(c['id']) for c in page.evaluate('BCAT') if str(c['id'])=='savings' or c['name'].strip().casefold()=='заощадження'}
    # Загальний конверт незмінний; KPI витрат виключає ще не виконаний резерв заощаджень.
    total=TOTAL-max(0,PLAN*len(savings_ids)-sum(by.get(cid,0) for cid in savings_ids))
    seen = []
    go_tab(page, 1)
    expand_groups(page)
    # клітинки категорій і «Без категорії»
    for c in page.locator('.bud-cat[data-cat]').all():
        cid = c.get_attribute('data-cat')
        plan = 0 if cid == 'unallocated' else PLAN
        fact = by.get(cid, 0)
        o = fact > plan
        cell = c.locator('.bud-remaining')
        v = amount(page, cell, o, 'Перевитрата' if o else 'Залишок', f'{tag} категорія {cid}')
        check(abs(v - abs(plan - fact)) < .005, f'{tag} категорія {cid}: {v} != |{plan} - {fact}|')
        seen.append(('unallocated' if cid == 'unallocated' else 'cat', o))
    # рядки груп: план і факт = суми категорій групи
    for g in page.locator('.bud-grp').all():
        ids = [x.get_attribute('data-cat') for x in g.locator('.bud-cat[data-cat]').all()]
        if not ids:
            continue
        plan = sum(0 if i == 'unallocated' else PLAN for i in ids)
        fact = sum(by.get(i, 0) for i in ids)
        o = fact > plan
        cell = g.locator('.bud-grp-h .bud-remaining')
        v = amount(page, cell, o, 'Перевитрата' if o else 'Залишок', f'{tag} група {ids}')
        check(abs(v - abs(plan - fact)) < .005, f'{tag} група {ids}: {v} != |{plan} - {fact}|')
        seen.append(('group', o))
    fact = round(sum(by.values()), 2)
    o = fact > total
    check(o == over, f'{tag}: сценарій не дав очікуваного знака ({fact} проти {total})')
    # KPI
    card = page.locator('.bud-avail')
    check(('Перевитрата бюджету' if o else 'Залишок бюджету') in card.text_content(), f'{tag}: підпис KPI {card.text_content()!r}')
    v = amount(page, card.locator('.bud-kpi-v'), o, '', f'{tag} KPI')
    check(abs(v - abs(total - fact)) < .005, f'{tag} KPI: {v} != |{total} - {fact}|')
    seen.append(('kpi', o))
    # readout графіка і підпис на графіку
    rd = page.locator('.bud-chart-readout')
    if rd.count():
        lab = 'Перевитрата' if o else 'Залишок'
        part = rd.locator('[data-over]') if o else rd
        v = amount(page, part, o, lab + ':', f'{tag} readout')
        check(abs(v - abs(total - fact)) < .005, f'{tag} readout: {v} != |{total} - {fact}|')
        check(not MINUS.search(rd.text_content()), f'{tag} readout: мінус {rd.text_content()!r}')
        lbl = page.locator('.bud-lbl-rest')
        t = lbl.text_content()
        check(t.startswith('перевитрата' if o else 'залишок') and not MINUS.search(t), f'{tag} підпис графіка {t!r}')
        check(abs(num(lbl.locator('tspan').nth(1).text_content()) - abs(total - fact)) < .005, f'{tag} підпис графіка {t!r}')
        if o:
            check(lbl.locator('tspan').nth(1).get_attribute('fill') == 'var(--red-t)', f'{tag} підпис графіка не червоний')
        seen.append(('chart', o))
    # підказка шухляди категорії: продукти (перевитрата у сценарії OVER) і кафе (залишок)
    for cid in ('food', 'cafe'):
        page.locator(f'.bud-cat[data-cat={cid}]').click()
        page.wait_for_timeout(350)
        hint = page.locator('.cat-lim-hint')
        f = by.get(cid, 0)
        co = f > PLAN
        v = amount(page, hint, co, 'Перевитрата:' if co else 'Залишок:', f'{tag} шухляда {cid}')
        check(abs(v - abs(PLAN - f)) < .005, f'{tag} шухляда {cid}: {v} != |{PLAN} - {f}|')
        seen.append(('drawer', co))
        page.keyboard.press('Escape')
        page.wait_for_timeout(350)
    shot(page, f'overspend-terms-{tag}-budget.jpg', full=False)
    # Огляд: назва, знак і колір відображають перевитрату або залишок у межах місячних категорій.
    go_tab(page, 0)
    pb = page.evaluate('window.__periodBudget')
    pfact = sum(round(t['amount'] * 100) for t in valid if pb['start'] <= t['date'][:10] <= DAY and str(t.get('category_id')) not in savings_ids)
    check(pb['spent']==pfact, f'{tag}: consumable facts include savings')
    raw = -pb['overrun'] if pb['overrun'] > 0 else pb['avail']
    po = raw < 0
    row = page.locator('.kpi-row[data-r=avail]').first
    v = amount(page, row, po, 'Перевитрата' if po else 'Доступно', f'{tag} Огляд', red=False)
    check(abs(v * 100 - abs(raw)) < .5, f'{tag} Огляд: {v} != |{raw}| / 100')
    if po:
        check(row.locator('.kpi-rv').evaluate(RED), f'{tag} Огляд: сума не червона')
    seen.append(('overview', po))
    shot(page, f'overspend-terms-{tag}-overview.jpg', full=False)
    kinds = sorted({k for k, _ in seen})
    summary = ', '.join(f'{k} {sum(o for x, o in seen if x == k)}/{sum(x == k for x, _ in seen)}' for k in kinds)
    print(f'      {tag}: факт {fact} проти {TOTAL}, період {pfact / 100} проти {pb["budget"] / 100}; перевитрата/усього: {summary}')
    return seen


def run(page, tag):
    seed_demo(page, DAY, OVER)
    over = {k for k, o in surfaces(page, True, tag + '-over') if o}
    need = {'cat', 'unallocated', 'group', 'kpi', 'drawer', 'overview'}
    check(over >= need, f'{tag}: перевитрата не на всіх поверхнях: {need - over}')
    seed_demo(page, DAY)
    rest = {k for k, o in surfaces(page, False, tag + '-rest') if not o}
    need = {'cat', 'group', 'kpi', 'drawer', 'overview'}
    check(rest >= need, f'{tag}: залишок не на всіх поверхнях: {need - rest}')
    return over, rest


def desktop(page):
    ver = page.evaluate('APP_VER')
    check(int(ver.lstrip('v')) >= 183, f'APP_VER {ver} нижче v183')
    over, rest = run(page, 'desktop')
    check('chart' in over and 'chart' in rest, 'на ПК графік не перевірено')


def mobile(page):
    run(page, 'mobile')


CHECKS = [
    ('Перевитрата замість відʼємного залишку: ПК', 'desktop', desktop),
    ('Перевитрата замість відʼємного залишку: телефон', 'mobile', mobile),
]
