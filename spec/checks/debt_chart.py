"""v218: графік боргу за весь строк у панелі «Борг станом на сьогодні».
Числа: точка сьогодні = числа панелі; залишок розстрочок на кожну дату = незалежний розрахунок графіка внесків тут.
Знімок кредиток пишеться за сьогодні, минулі знімки лишаються. Розкладка: ПК 1440 і 1920, телефон 375."""
import json

from helpers import check, freeze, go_tab, shot
from checks.live_refresh import MOCK, updated
from checks.overspend_sync import wait_money

TODAY = '2026-10-10'
# розстрочка 10 ₴ на місяць, 5 внесків 15-го; start_month у рушії відлічується від нуля: 9 = жовтень
CREDIT = {'id': 5, 'name': 'Synthetic installments', 'monthly_amount': 10, 'payment_day': 15,
          'start_year': 2026, 'start_month': 9, 'total_payments': 5, 'active': True}
PAST_SNAP = {'day': '2026-10-05', 'card_debt': 80}


def expected_series():
    """Незалежно від застосунку: залишок = сума внесків із датою після дня."""
    dues = []
    for k in range(5):
        y, m = 2026 + (9 + k) // 12, (9 + k) % 12 + 1
        dues.append(f'{y}-{m:02d}-15')
    days = sorted({'2026-10-01', '2026-10-05', TODAY, *dues})
    return {d: sum(1000 for x in dues if x > d) for d in days}


def setup(page):
    page.emulate_media(reduced_motion='reduce')
    data = {
        'accounts': [
            {'id': 1, 'name': 'Synthetic cash', 'bank': 'cash', 'kind': 'cash', 'balance': 1000,
             'debt': 0, 'active': True, 'balance_updated_at': '2026-10-01T00:00:00Z'},
            {'id': 2, 'name': 'Synthetic card', 'bank': 'privat', 'kind': 'credit', 'balance': 0,
             'debt': 60, 'credit_limit': 100, 'active': True, 'balance_updated_at': '2026-10-01T00:00:00Z'}],
        'credits': [CREDIT], 'transactions': [], 'monthly_budgets': [], 'debt_snapshots': [PAST_SNAP]}
    mock = MOCK.replace("['insert','update','delete']", "['insert','update','delete','upsert']")
    mock = mock.replace('const apply=()=>{const update=',
                        "const apply=()=>{const up=q.ops.find(x=>x[0]==='upsert');if(up){const rows=m.data[table]=m.data[table]||[];const i=rows.findIndex(r=>r.day===up[1].day);if(i>=0)rows[i]=clone(up[1]);else rows.push(clone(up[1]));return{data:[clone(up[1])],error:null}}const update=")
    assign = ''.join('m.data.' + k + '=' + json.dumps(v, ensure_ascii=False) + ';' for k, v in data.items())
    mock = mock.replace('window.supabase={createClient:()=>sb};', assign + 'window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, TODAY, patch=[('if(!sb){window.__financeProjection=', '{window.__financeProjection=')])
    updated(page)
    page.wait_for_function('window.__liveMock&&__liveMock.data.debt_snapshots.some(r=>r.day==="%s")' % TODAY)
    go_tab(page, 1)
    wait_money(page, '[data-debt-total=total]', 11000)
    page.wait_for_selector('.debt-chart .debt-now-inst')


def numbers(page, tag):
    snaps = page.evaluate('__liveMock.data.debt_snapshots')
    check(sorted(r['day'] for r in snaps) == ['2026-10-05', TODAY], f'{tag}: знімки {snaps}')
    check([r['card_debt'] for r in snaps if r['day'] == TODAY] == [60], f'{tag}: знімок кредиток сьогодні {snaps}')
    cents = lambda sel: int(page.locator(sel).first.get_attribute('data-cents'))
    panel = lambda k: page.locator(f'[data-debt-total={k}]').first.inner_text()
    check(cents('.debt-now-inst') == 5000 and '50' in panel('installment'), f'{tag}: точка розстрочок {cents(".debt-now-inst")} / панель {panel("installment")}')
    tot = int(page.locator('.debt-now-inst').first.get_attribute('data-total'))
    check(tot == 11000 and '110' in panel('total'), f'{tag}: разом у точці сьогодні {tot} / панель {panel("total")}')
    pts = page.evaluate("debtHistory(window.__financeInput,'%s',__liveMock.data.debt_snapshots,6000)" % TODAY)
    exp = expected_series()
    got = {x['date']: x['inst'] for x in pts}
    check(got == exp, f'{tag}: ряд розстрочок {got} замість {exp}')
    totals = {x['date']: x['total'] for x in pts if x['total'] is not None}
    check(totals == {'2026-10-05': 5000 + 8000, TODAY: 11000}, f'{tag}: ряд разом {totals}')
    # v222: підписи лише максимуму й мінімуму кожного року, значення = незалежний ряд
    ext = page.evaluate("[...document.querySelectorAll('.debt-chart .debt-ext')].map(t=>[t.dataset.date,+t.dataset.cents,t.dataset.kind])")
    allowed, maxes = set(), {}
    for y in sorted({d[:4] for d in exp}):
        vals = {d: v for d, v in exp.items() if d[:4] == y}
        mx, mn = max(vals.values()), min(vals.values())
        maxes[y] = mx
        allowed |= {(d, v) for d, v in vals.items() if v in (mx, mn)}
    check(all((d, c) in allowed for d, c, _ in ext), f'{tag}: підпис не максимум і не мінімум року {ext}')
    check(all(any(d[:4] == y and c == mx for d, c, _ in ext) for y, mx in maxes.items()), f'{tag}: немає максимуму року {ext} / {maxes}')
    check(page.locator('.debt-chart .debt-line').count() == 1 and page.locator('.debt-chart polyline').count() == 0, f'{tag}: має бути одна лінія')
    # підказка на будь-якій точці: дата й сума з ряду
    page.locator('.debt-chart').scroll_into_view_if_needed()
    box = page.locator('.debt-chart svg').bounding_box()
    for fx in (0.05, 0.5, 0.95):
        page.mouse.move(box['x'] + box['width'] * fx, box['y'] + box['height'] / 2)
        page.wait_for_selector('.debt-tip .fc-tip-h')
        tip = page.evaluate("(()=>{const e=document.querySelector('.debt-tip');return e?[+e.dataset.cents,e.querySelector('.fc-tip-h').textContent]:null})()")
        check(tip is not None, f'{tag}: підказка зникла')
        c, hd = tip[0], tip[1][:10]
        iso = hd[6:10] + '-' + hd[3:5] + '-' + hd[0:2]
        check(exp.get(iso) == c, f'{tag}: підказка {hd} {c} != ряд {exp.get(iso)}')
        tb = page.locator('.debt-tip').bounding_box()
        card = page.locator('.bud-debt').bounding_box()
        check(tb['x'] >= card['x'] - 0.5 and tb['x'] + tb['width'] <= card['x'] + card['width'] + 0.5, f'{tag}: підказка за карткою {tb}')
    page.mouse.move(0, 0)


def layout(page, tag):
    g = page.evaluate("""()=>{const r=e=>{const b=e.getBoundingClientRect();return{x:b.left,y:b.top,r:b.right,b:b.bottom,w:b.width}};
      const card=document.querySelector('.bud-debt'),fig=document.querySelector('.debt-chart'),svg=fig.querySelector('svg'),now=document.querySelector('.bud-debt-now');
      const texts=[...svg.querySelectorAll('text')].map(r);
      return{card:r(card),fig:r(fig),svg:r(svg),now:r(now),texts:texts,scroll:document.documentElement.scrollWidth<=innerWidth}}""")
    check(g['scroll'], f'{tag}: горизонтальна прокрутка')
    c, f, s = g['card'], g['fig'], g['svg']
    check(f['x'] >= c['x'] - 0.5 and f['r'] <= c['r'] + 0.5 and f['b'] <= c['b'] + 0.5, f'{tag}: графік виходить за картку {f} / {c}')
    check(abs(s['w'] - f['w']) <= 1, f'{tag}: svg {s["w"]:.1f} не на всю ширину блоку {f["w"]:.1f}')
    for t in g['texts']:
        check(t['x'] >= c['x'] - 0.5 and t['r'] <= c['r'] + 0.5, f'{tag}: підпис осі за карткою {t}')
    xs = sorted([t for t in g['texts'] if t['y'] > s['b'] - 20], key=lambda t: t['x'])
    for a, b in zip(xs, xs[1:]):
        check(b['x'] >= a['r'] + 4, f'{tag}: підписи дат налазять {a} {b}')


def desktop(page):
    for w, hgt in ((1440, 900), (1920, 1080)):
        page.set_viewport_size({'width': w, 'height': hgt})
        setup(page)
        numbers(page, f'ПК {w}')
        layout(page, f'ПК {w}')
        g = page.evaluate("()=>{const a=document.querySelector('.bud-debt-now').getBoundingClientRect(),b=document.querySelector('.debt-chart').getBoundingClientRect();return{a:a.right,b:b.left,at:a.top,bt:b.top}}")
        check(g['b'] > g['a'], f'ПК {w}: графік не праворуч від чисел {g}')
        # v220: графік на всю висоту картки поруч із рядком розрахунку, без порожнечі зверху і знизу
        v = page.evaluate("""()=>{const r=s=>document.querySelector(s).getBoundingClientRect();const c=r('.bud-debt'),now=r('.bud-debt-now'),f=r('.debt-chart'),rec=r('.budget-reconciliation'),cs=getComputedStyle(document.querySelector('.bud-debt'));
          return{ct:c.top+parseFloat(cs.paddingTop),cb:c.bottom-parseFloat(cs.paddingBottom),nt:now.top,nb:now.bottom,ft:f.top,fb:f.bottom,rt:rec.top}}""")
        check(abs(v['ft'] - v['rt']) <= 1 and abs(v['nt'] - v['ct']) <= 1, f'ПК {w}: верх графіка не на рівні рядка розрахунку {v}')
        check(abs(v['fb'] - v['nb']) <= 1, f'ПК {w}: низ графіка {v["fb"]:.1f} != низ лівої колонки {v["nb"]:.1f}')
        check(v['cb'] - max(v['fb'], v['nb']) <= 1, f'ПК {w}: порожнеча внизу картки {v}')
        page.locator('.bud-debt').scroll_into_view_if_needed()
        shot(page, f'debt-chart-{w}.jpg', full=False)


def mobile(page):
    setup(page)
    numbers(page, 'телефон 375')
    layout(page, 'телефон 375')
    page.locator('.debt-chart').scroll_into_view_if_needed()
    shot(page, 'debt-chart-375.jpg', full=False)


CHECKS = [
    ('Борг: графік за весь строк, точка сьогодні = панель, знімок кредиток (ПК 1440, 1920)', 'desktop', desktop),
    ('Борг: графік за весь строк на телефоні 375', 'mobile', mobile),
]
