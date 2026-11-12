"""v220: «Топ-5 місць» на Бюджеті (календарний місяць, ПК).
Лише операції з описом; час «· 10:54» у кінці опису не розділяє місце; останній рядок не обрізаний карткою.
Суми: незалежний розрахунок тут."""
import json

from helpers import check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated

TODAY = '2026-10-20'
ROWS = [  # (опис, сума)
    ('Synthetic clinic · 10:54', 3900), ('Synthetic clinic · 11:15', 3800), ('synthetic clinic', 600),
    (None, 4700), ('Synthetic shop', 1500), ('Synthetic cafe · 9:05', 900), ('Synthetic taxi', 700),
    ('Synthetic kiosk', 300), ('Synthetic pharmacy', 2000),
]


CATS = [{'id': 'c%d' % i, 'name': 'Synthetic cat %d' % i, 'icon': '•', 'color': '#7066e0', 'budget_limit': 1000,
         'group_id': 1, 'sort_order': i} for i in range(11)]


def tx(i, d, a):
    return {'id': 900 + i, 'date': '2026-10-1%d' % (i % 9), 'created_at': '2026-10-10T10:00:00Z', 'type': 'expense',
            'amount': a, 'account_id': 1, 'category_id': 'c%d' % (i % 11), 'description': d, 'source': 'manual',
            'categories': {'name': 'Продукти', 'icon': '🛒', 'color': '#7066e0'}}


def expected():
    import re
    top = {}
    for d, a in ROWS:
        if not d:
            continue
        n = re.sub(r'\s*·\s*\d{1,2}:\d{2}\s*$', '', d).strip()
        k = n.lower()
        top.setdefault(k, [n, 0])[1] += a
    return sorted(((v[0].lower(), v[1] * 100) for v in top.values()), key=lambda x: -x[1])[:5]


def places(page):
    page.set_viewport_size({'width': 1440, 'height': 640})
    page.emulate_media(reduced_motion='reduce')
    rows = [tx(i, d, a) for i, (d, a) in enumerate(ROWS)]
    mock = MOCK.replace('window.supabase={createClient:()=>sb};',
                        'm.data.categories=m.data.categories.concat(' + json.dumps(CATS) + ');m.data.transactions=m.data.transactions.concat(' + json.dumps(rows, ensure_ascii=False) + ');window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, TODAY)
    updated(page)
    go_tab(page, 1)
    page.wait_for_selector('.calendar-budget .bud-top .bud-top-row')
    page.wait_for_timeout(800)
    got = page.evaluate("""()=>[...document.querySelectorAll('.calendar-budget .bud-top .bud-top-row')].map(r=>[r.querySelector('.bud-rn').textContent.toLowerCase(),+r.querySelector('b').dataset.cents])""")
    exp = expected()
    got_cmp = [(n, c) for n, c in got]
    check(got_cmp == exp, f'топ-5 {got_cmp} замість {exp}')
    check(not any('·' in n for n, _ in got), f'час у назві {got}')
    g = page.evaluate("""()=>{const c=document.querySelector('.calendar-budget .bud-top'),rows=[...c.querySelectorAll('.bud-top-row')];const cb=c.getBoundingClientRect();
      return{cb:cb.bottom,cr:cb.right,last:rows[rows.length-1].getBoundingClientRect().bottom,over:rows.some(r=>r.getBoundingClientRect().right>cb.right+0.5),sh:c.scrollHeight,ch:c.clientHeight}}""")
    check(g['last'] <= g['cb'] + 0.5 and g['sh'] <= g['ch'] + 1, f'останній рядок обрізано {g}')
    check(not g['over'], f'рядок виходить за картку {g}')
    # останній рядок досяжний: або видно у вікні, або сторінка прокручується до нього
    page.locator('.calendar-budget .bud-top .bud-top-row').last.scroll_into_view_if_needed()
    vis = page.evaluate("""()=>{const r=[...document.querySelectorAll('.calendar-budget .bud-top .bud-top-row')].pop().getBoundingClientRect();return r.bottom<=innerHeight+0.5&&r.top>=0}""")
    check(vis, 'останній рядок топ-5 недосяжний у вікні')
    page.locator('.calendar-budget .bud-top').scroll_into_view_if_needed()
    shot(page, 'budget-top-places-1440.jpg', full=False)


CHECKS = [
    ('Бюджет: топ-5 місць без часу в назві, без операцій без опису, не обрізано (ПК 1440)', 'desktop', places),
]
