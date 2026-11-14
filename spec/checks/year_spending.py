"""v232 Бюджет: перемикач Місяць | Рік і стовпці витрат за 12 місяців (власник 14.11.2026, «щоденні + обовʼязкові»).
Цифри: незалежний розрахунок на Python із тих самих демо-операцій; поточний місяць = картка «Витрачено»; разом = частини.
Розкладка: картка й перемикач не зсуваються між режимами, колонки закінчуються разом, проміжок між частинами 2 px,
стовпці на нульовій лінії, сітка під стовпцями, підписи місяців не злипаються, підказка в межах графіка."""
import json
import math
import random
import re

from helpers import check, freeze, go_tab, num, shot
from checks.live_refresh import MOCK, updated

TODAY = '2026-11-14'
# 10 місяців демо-даних (два найстаріші без операцій), WOG як постійний платіж, Київстар як розстрочка, один рядок у заощадження
PATCH = [('if(k>cur||k<cur-1)return[];', 'if(k>cur||k<cur-9)return[];'), ("5912,null]", "5912,'savings']"),
         ('receipt_url:null}}).sort(', "receipt_url:null,fixed_id:r[6]==='auto'?7:null,credit_id:r[6]==='comm'?3:null}}).sort(")]
BOX = """(s)=>{const e=document.querySelector(s);if(!e)return null;const b=e.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height,r:b.right,b:b.bottom}}"""


def js_round(x):
    return math.floor(x + 0.5)


def months(today):
    y, m = int(today[:4]), int(today[5:7])
    return [divmod(y * 12 + m - 1 - i, 12) for i in range(11, -1, -1)]


def reference(page):
    """Ті самі демо-операції, що бачить застосунок; правило рахується тут, а не береться з JS."""
    savings = set(page.evaluate("monthlyBudgetModel(null,[],BCAT,2026,10,'2026-11-14',null).savingsCategoryIds"))
    out = []
    for y, m in months(TODAY):
        key, seen = f'{y}-{m + 1:02d}', set()
        rows = [r for r in page.evaluate('([y,m])=>txDemo(y,m)', [y, m]) if not (r['id'] in seen or seen.add(r['id']))]
        ys = [r for r in rows if r['date'][:7] == key and r['date'] <= TODAY and r.get('transfer_id') is None and r['type'] == 'expense']
        cents = lambda r: js_round(float(r['amount']) * 100)
        expense = sum(cents(r) for r in ys)
        var = [r for r in ys if r.get('fixed_id') is None and r.get('credit_id') is None]
        fact = sum(cents(r) for r in var)
        sav = sum(cents(r) for r in var if str(r.get('category_id')) in savings and float(r['amount']) > 0)
        has = expense > 0
        out.append({'start': key + '-01', 'daily': fact - sav if has else None, 'paid': expense - fact if has else None})
    return out


def open_year(page):
    page.locator('.bud-range button', has_text='Рік').click()
    page.wait_for_selector('.bud-year[role=slider]')
    page.wait_for_timeout(150)


def layout(page, w):
    """Картка, перемикач і колонки однакові в обох режимах; шари й геометрія стовпців."""
    before = {k: page.evaluate(BOX, s) for k, s in (('pace', '.bud-pace'), ('sw', '.bud-range'), ('cat', '.bud-catcard'), ('top', '.bud-top'))}
    open_year(page)
    after = {k: page.evaluate(BOX, s) for k, s in (('pace', '.bud-pace'), ('sw', '.bud-range'), ('cat', '.bud-catcard'), ('top', '.bud-top'))}
    for k in ('pace', 'sw'):
        for side in ('x', 'y', 'r', 'b'):
            check(abs(before[k][side] - after[k][side]) <= 1, f'{w}: {k}.{side} зсунувся між режимами: {before[k][side]:.1f} -> {after[k][side]:.1f}')
    if w >= 1024:
        diff = abs(after['cat']['b'] - after['top']['b'])
        check(diff <= 1, f'{w}: колонки закінчуються на різній висоті в режимі «Рік», {diff:.1f}px')
    geo = page.evaluate("""()=>{const svg=document.querySelector('.bud-year');const kids=[...svg.children];const idx=s=>kids.findIndex(e=>e.matches(s));
const lines=[...svg.querySelectorAll('line')].map(l=>l.getBoundingClientRect().y);const zero=Math.max(...lines);
const bars=[...svg.querySelectorAll('.bud-yr-bar')].map(g=>{const d=g.querySelector('.bud-yr-daily'),p=g.querySelector('.bud-yr-paid'),db=d&&d.getBoundingClientRect(),pb=p&&p.getBoundingClientRect();
return{bottom:(db||pb).bottom,gap:db&&pb?db.top-pb.bottom:null}});
const lab=[...svg.querySelectorAll('.bud-yr-m')].map(e=>e.getBoundingClientRect());
return{order:[idx('.bud-yr-sel'),idx('g:has(line)'),idx('.bud-yr-bar')],zero,bars,minGap:Math.min(...lab.slice(1).map((b,i)=>b.left-lab[i].right)),labFont:Math.min(...lab.map(b=>b.height)),svgR:svg.getBoundingClientRect().right,labR:Math.max(...lab.map(b=>b.right))}}""")
    o = geo['order']
    check(0 <= o[0] < o[1] < o[2], f'{w}: шари не тло < сітка < стовпці: {o}')
    for b in geo['bars']:
        check(abs(b['bottom'] - geo['zero']) <= 1, f'{w}: стовпець не на нульовій лінії: {b["bottom"]:.1f} проти {geo["zero"]:.1f}')
        if b['gap'] is not None:
            check(1.4 <= b['gap'] <= 2.6, f'{w}: проміжок між частинами {b["gap"]:.2f}px, має бути 2')
    check(geo['minGap'] >= 1, f'{w}: підписи місяців злипаються, проміжок {geo["minGap"]:.1f}px')
    check(geo['labR'] <= geo['svgR'] + .5, f'{w}: підпис місяця за краєм графіка')
    print(f'      {w}: картка {after["pace"]["h"]:.1f}px в обох режимах, перемикач x={after["sw"]["r"]:.1f}, '
          f'проміжок частин {min([b["gap"] for b in geo["bars"] if b["gap"] is not None] or [0]):.2f}px, підписи ±{geo["minGap"]:.1f}px')


def numbers(page, w):
    """Модель = Python; поточний місяць = «Витрачено»; підказка кожного місяця: частини, разом = сума показаних."""
    want = reference(page)
    got = page.evaluate('window.__yearSpend')
    check([(x['start'], x['daily'], x['paid']) for x in got] == [(x['start'], x['daily'], x['paid']) for x in want],
          f'{w}: модель року не збігається з розрахунком Python:\n{got}\n{want}')
    check(sum(1 for x in want if x['daily'] is None) == 2 and any(x['paid'] for x in want), f'{w}: фікстура без порожніх місяців чи обовʼязкових')
    spent = round(num(page.locator('.bud-spent .bud-kpi-v').inner_text()) * 100)
    check(want[-1]['daily'] == spent, f'{w}: стовпець поточного місяця {want[-1]["daily"]} != «Витрачено» {spent}')
    bars = {b['m']: b for b in page.locator('.bud-yr-bar').evaluate_all("es=>es.map(e=>({m:e.dataset.month,d:+e.dataset.daily,p:+e.dataset.paid}))")}
    for x in want:
        if x['daily'] is None:
            check(x['start'] not in bars, f'{w}: стовпець для порожнього місяця {x["start"]}')
        else:
            check(bars[x['start']]['d'] == x['daily'] and bars[x['start']]['p'] == x['paid'], f'{w}: стовпець {x["start"]} {bars[x["start"]]} != {x}')
    svg = page.locator('.bud-year')
    svg.focus()
    page.keyboard.press('Home')
    box = page.evaluate(BOX, '.bud-year-box')
    for i, x in enumerate(want):
        if i:
            page.keyboard.press('ArrowRight')
        tip = page.locator('.bud-year-tip')
        check(tip.count() == 1, f'{w}: немає підказки для {x["start"]}')
        tb = tip.bounding_box()
        check(tb['x'] >= box['x'] - .5 and tb['x'] + tb['width'] <= box['r'] + .5 and tb['y'] >= box['y'] - .5,
              f'{w}: підказка {x["start"]} за межами графіка')
        check(svg.get_attribute('aria-valuenow') == str(i + 1), f'{w}: aria-valuenow {svg.get_attribute("aria-valuenow")} != {i + 1}')
        if x['daily'] is None:
            check('н/д' in tip.inner_text() and 'н/д' in svg.get_attribute('aria-valuetext'), f'{w}: {x["start"]} без «н/д»')
            continue
        d = num(tip.locator('[data-part=daily]').inner_text())
        p = num(tip.locator('[data-part=paid]').inner_text())
        t = num(tip.locator('[data-part=total]').inner_text())
        check(abs(d * 100 - x['daily']) < .5 and abs(p * 100 - x['paid']) < .5, f'{w}: підказка {x["start"]} {d}/{p} != {x}')
        check(abs(t - d - p) < .005, f'{w}: разом {t} != {d} + {p}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(80)
    total = num(page.locator('.bud-yr-total').text_content())
    check(abs(total * 100 - (want[-1]['daily'] + want[-1]['paid'])) < .5, f'{w}: сума над стовпцем {total} != {want[-1]}')
    page.keyboard.press('ArrowRight')
    check(page.locator('.bud-yr-total').count() == 0, f'{w}: сума над стовпцем під підказкою')


def desktop(page):
    for w, hh in ((1440, 900), (1920, 1080)):
        page.set_viewport_size({'width': w, 'height': hh})
        freeze(page, TODAY, PATCH)
        go_tab(page, 1)
        layout(page, w)
        numbers(page, w)
        shot(page, f'year-spending-{w}.jpg', full=False)
        page.locator('.bud-range button', has_text='Місяць').click()
        page.wait_for_timeout(150)
        check(page.locator('.bud-chart[role=slider]:not(.bud-year)').count() == 1, f'{w}: графік місяця не повернувся')
        check(page.locator('.bud-pace .bud-legend').count() == 0 and page.locator('.bud-chart-readout').count() == 1, f'{w}: легенда чи зайвий readout')


def colors(page):
    """Дві частини різняться в обох темах: колір обовʼязкових = 70% акценту на тлі картки."""
    page.set_viewport_size({'width': 1440, 'height': 900})
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        freeze(page, TODAY, PATCH)
        go_tab(page, 1)
        open_year(page)
        c = page.evaluate("""()=>{const f=s=>{const p=document.createElement('span');p.style.color=s;document.body.appendChild(p);const v=getComputedStyle(p).color;p.remove();return v};
const d=document.querySelector('.bud-yr-daily'),p=document.querySelector('.bud-yr-paid');return{daily:getComputedStyle(d).fill,paid:getComputedStyle(p).fill,acc:f('var(--indigo)'),card:f('var(--card)')}}""")
        nums = {k: [float(v) for v in re.findall(r'[\d.]+', c[k])][:3] for k in c}
        if 'srgb' in c['paid']:
            nums['paid'] = [v * 255 for v in nums['paid']]
        want = [a * .7 + b * .3 for a, b in zip(nums['acc'], nums['card'])]
        check(nums['daily'] == nums['acc'], f'{theme}: щоденні не кольору акценту {c}')
        check(max(abs(a - b) for a, b in zip(nums['paid'], want)) <= 2, f'{theme}: обовʼязкові {c["paid"]} != 70% акценту {want}')
        check(max(abs(a - b) for a, b in zip(nums['paid'], nums['daily'])) >= 30, f'{theme}: частини майже однакові {c}')
        print(f'      {theme}: щоденні {c["daily"]}, обовʼязкові {c["paid"]}')


def mobile(page):
    freeze(page, TODAY, PATCH)
    go_tab(page, 1)
    page.locator('.bud-pace').scroll_into_view_if_needed()
    layout(page, page.viewport_size['width'])
    bars = page.locator('.bud-yr-bar')
    b = bars.nth(bars.count() - 4).bounding_box()
    page.touchscreen.tap(b['x'] + b['width'] / 2, b['y'] + 4)
    page.wait_for_timeout(150)
    tip, box = page.locator('.bud-year-tip'), page.evaluate(BOX, '.bud-year-box')
    check(tip.count() == 1, 'телефон: дотик до стовпця не показав підказку')
    tb = tip.bounding_box()
    check(tb['x'] >= box['x'] - .5 and tb['x'] + tb['width'] <= box['r'] + .5 and tb['y'] >= box['y'] - .5 and tb['y'] + tb['height'] <= box['b'] + .5,
          f'телефон: підказка за межами графіка {tb} / {box}')
    shot(page, 'year-spending-mobile.jpg', full=False)
    print(f'      375: підказка {tb["width"]:.0f}x{tb["height"]:.0f} в межах графіка')


SAV = {'id': 'sav', 'name': 'Заощадження', 'icon': '•', 'color': '#7066e0', 'budget_limit': 1, 'group_id': 1, 'sort_order': 1}


def live_rows():
    """Понад 1000 витрат за 13 місяців (запит року йде двома сторінками); березень без операцій; є майбутні рядки й поза вікном."""
    rng, out = random.Random(232), []
    for i in range(1500):
        y, m = divmod(2025 * 12 + 10 + i % 13, 12)
        if (y, m) == (2026, 2):
            continue
        d = f'{y}-{m + 1:02d}-{1 + rng.randrange(28):02d}'
        r = {'id': 5000 + i, 'date': d, 'created_at': d + 'T10:00:00Z', 'type': 'expense', 'amount': round(rng.uniform(1, 900), 2),
             'account_id': 1, 'category_id': rng.choice(['food', 'sav', None]), 'description': 'Synthetic row', 'source': 'manual'}
        k = rng.random()
        if k < .12:
            r['fixed_id'] = 1 + rng.randrange(5)
        elif k < .2:
            r['credit_id'] = 1 + rng.randrange(3)
        elif k < .3:
            r['type'] = 'income'
        elif k < .33:
            r['amount'] = -r['amount']
        out.append(r)
    return out


def live_reference(rows):
    out = []
    for y, m in months(TODAY):
        key = f'{y}-{m + 1:02d}'
        ys = [r for r in rows if r['date'][:7] == key and r['date'] <= TODAY and r.get('transfer_id') is None and r['type'] == 'expense']
        cents = lambda r: js_round(float(r['amount']) * 100)
        expense = sum(cents(r) for r in ys)
        var = [r for r in ys if r.get('fixed_id') is None and r.get('credit_id') is None]
        fact = sum(cents(r) for r in var)
        sav = sum(cents(r) for r in var if r['category_id'] == 'sav' and float(r['amount']) > 0)
        has = expense > 0
        out.append({'start': key + '-01', 'daily': fact - sav if has else None, 'paid': expense - fact if has else None})
    return out


def live_mount(page, rows):
    page.add_init_script(MOCK.replace('window.supabase={createClient:()=>sb};', 'm.data.categories=m.data.categories.concat(' + json.dumps([SAV], ensure_ascii=False)
                                      + ');m.data.transactions=' + json.dumps(rows, ensure_ascii=False) + ';window.supabase={createClient:()=>sb};'))
    freeze(page, TODAY)
    updated(page)
    go_tab(page, 1)
    page.wait_for_selector('.bud-range')


def signed_in(page):
    """З увійденим користувачем: «Завантажуємо…», дві сторінки запиту, стовпці = Python, поточний = «Витрачено», помилка без збою."""
    page.set_viewport_size({'width': 1440, 'height': 900})
    rows = live_rows()
    live_mount(page, rows)
    check(page.locator('.bud-year').count() == 0, 'рік завантажився без натискання «Рік»')
    page.evaluate('__liveMock.hold=true')
    page.locator('.bud-range button', has_text='Рік').click()
    page.wait_for_selector('.bud-year[aria-hidden=true]')
    check(page.locator('.bud-chart-readout[role=status]').inner_text() == 'Завантажуємо витрати за рік', 'немає стану завантаження')
    page.evaluate('__liveMock.release()')
    page.wait_for_selector('.bud-year[role=slider]')
    reads = page.evaluate("""()=>__liveMock.reads.filter(r=>r.table==='transactions'&&r.ops.some(o=>o[0]==='gte'&&o[2]==='2025-12-01')).map(r=>r.ops.find(o=>o[0]==='range'))""")
    check([x[1] for x in reads] == [0, 1000], f'запит року не пройшов двома сторінками: {reads}')
    want = live_reference(rows)
    check(sum(1 for x in want if x['daily'] is None) == 1 and all(x['paid'] for x in want if x['daily'] is not None), f'фікстура: {want}')
    bars = {b['m']: b for b in page.locator('.bud-yr-bar').evaluate_all("es=>es.map(e=>({m:e.dataset.month,d:+e.dataset.daily,p:+e.dataset.paid}))")}
    got = [(x['start'], bars[x['start']]['d'], bars[x['start']]['p']) if x['start'] in bars else (x['start'], None, None) for x in want]
    check(got == [(x['start'], x['daily'], x['paid']) for x in want], f'стовпці не збігаються з Python: {got} / {want}')
    spent = round(num(page.locator('.bud-spent .bud-kpi-v').inner_text()) * 100)
    check(want[-1]['daily'] == spent, f'поточний місяць {want[-1]["daily"]} != «Витрачено» {spent}')
    print(f'      рядків {len(rows)}, сторінок запиту {len(reads)}, місяців н/д {sum(1 for x in want if x["daily"] is None)}, поточний = «Витрачено» {spent / 100:.2f}')
    # помилка запиту: текст замість графіка, перемикач на місці
    live_mount(page, rows)
    page.evaluate("__liveMock.fail='transactions'")
    page.locator('.bud-range button', has_text='Рік').click()
    page.wait_for_selector('.bud-chart-readout[role=alert]')
    check(page.locator('.bud-chart-readout[role=alert]').inner_text() == 'Не вдалося завантажити витрати за рік', 'немає тексту помилки')
    check(page.locator('.bud-year text').text_content() == 'Не вдалося завантажити витрати за рік', 'графік без тексту помилки')
    page.locator('.bud-range button', has_text='Місяць').click()
    page.wait_for_selector('.bud-chart[role=slider]:not(.bud-year)')


CHECKS = [('Бюджет ПК: рік за місяцями, цифри = Python і «Витрачено», картка не зсувається', 'desktop', desktop),
          ('Бюджет ПК: кольори частин року в обох темах', 'desktop', colors),
          ('Бюджет телефон: рік, підказка дотиком у межах графіка', 'mobile', mobile),
          ('Бюджет ПК з входом: завантаження, дві сторінки запиту, цифри = Python, помилка', 'desktop', signed_in)]
