"""Desktop Overview: shared grid edges and fully visible financial text without scrolling."""
from helpers import check, freeze, go_tab, settle
from checks.visual_layout import overview_bounds

DAY = '2026-10-12'
VIEWPORTS = ((1280, 720), (1366, 768), (1536, 760), (1280, 800), (1280, 860), (1440, 900), (1920, 940), (1920, 1080))

GEOMETRY = r"""()=>{
 const q=s=>document.querySelector(s),box=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
 const textBox=el=>{if(!el)return null;const nodes=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;while(node=nodes.nextNode()){if(!node.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(node);const r=range.getBoundingClientRect();if(r.width>0&&r.height>0)return {top:r.top,bottom:r.bottom,height:r.height};}return null;};
 const grid=q('.dv-cols.ov-grid');
 const sels={forecast:'.dv-fc',near:'.dv-near',budget:'.dv-bud',inst:'.ov-grid>.kpi-t.kpi-inst',recent:'.dv-recent'};
 const cards=Object.fromEntries(Object.entries(sels).map(([k,s])=>[k,box(q(s))]));
 const kpis=[...document.querySelectorAll('.dv-kpis>.kpi-t')].map(e=>({key:e.dataset.k,...box(e),head:box(e.querySelector('.kpi-head')),value:box(e.querySelector('.dv-kpi-v'))}));
 const cardEls=Object.values(sels).map(q).filter(Boolean);
 const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const money=[...document.querySelectorAll('.p-overview .dv-kpi-v,.p-overview .kpi-rv,.p-overview .kpi-iv,.p-overview .kpi-ie,.p-overview .dv-ev-a,.p-overview .dv-bud-v,.p-overview .bd-sum,.p-overview .bd-pct')].filter(visible);
 const clipped=money.filter(e=>{const b=e.getBoundingClientRect(),host=e.closest('.surface'),p=host&&host.getBoundingClientRect();return e.scrollWidth>e.clientWidth+1||p&&(b.left<p.left-1||b.right>p.right+1||b.top<p.top-1||b.bottom>p.bottom+1)}).map(e=>e.textContent);
 const inner=cardEls.flatMap(e=>[e,...e.querySelectorAll('*')]).filter(e=>visible(e)&&/auto|scroll/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+2).map(e=>e.className);
 const banks=[...document.querySelectorAll('.dv-cards>.bcard')].filter(visible).map(e=>({...box(e),amount:box(e.querySelector('.bcard-sum'))}));
 const titles=[q('.dv-bud>:first-child>:first-child'),q('.ov-grid>.kpi-inst .kpi-head .lbl-ico>span:last-child'),q('.dv-recent>:first-child>button')].map(textBox);
 const inlineAdvice=[...document.querySelectorAll('.dv-cards>.bcard .bank-advice')].some(e=>visible(e)&&e.textContent.trim().length>0);
 const badge=q('.budget-unassigned');
 return {cards,kpis,banks,titles,inlineAdvice,bankrow:box(q('.dv-cards')),add:box(q('.dv-cards>.bcard-add')),grid:box(grid),wallet:box(q('.dv-accs')),unas:box(q('.dv-unas')),badge:badge?{...box(badge),text:badge.textContent,label:badge.getAttribute('aria-label')}:null,wide:document.documentElement.scrollWidth,doc:document.documentElement.scrollHeight,clipped,inner};
}"""


def _equal(values, message):
    check(all(v is not None for v in values) and max(values) - min(values) <= 1, f'{message}: {values}')


def desktop_grid(page):
    for theme in ('dark', 'light'):
        freeze(page, DAY)
        go_tab(page, 0)
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        for width, height in VIEWPORTS:
            page.set_viewport_size(dict(width=width, height=height))
            page.wait_for_timeout(450)
            settle(page)
            page.evaluate('window.scrollTo(0,0)')
            g = page.evaluate(GEOMETRY)
            tag = f'{theme}/{width}x{height}'
            k = g['kpis']
            check([x['key'] for x in k] == ['funds', 'budget', 'balance'], f'{tag}: головні KPI {k}')
            for edge in ('top', 'bottom', 'width'):
                _equal([x[edge] for x in k], f'{tag}: KPI {edge}')
            for part in ('head', 'value'):
                _equal([x[part]['top'] for x in k], f'{tag}: KPI {part} baseline')
            check(len(g['banks']) == 3, f'{tag}: expected three bank cards {g["banks"]}')
            _equal([bank['amount']['top'] for bank in g['banks']], f'{tag}: bank amount baselines')
            _equal([g['bankrow']['left'], k[0]['left']], f'{tag}: account row left grid edge')
            _equal([g['bankrow']['right'], k[-1]['right']], f'{tag}: account row right grid edge')
            _equal([bank['width'] for bank in g['banks']], f'{tag}: equal bank card widths')
            _equal([bank['top'] for bank in g['banks']], f'{tag}: bank card top edge')
            check(g['add'] and 32 <= g['add']['width'] <= 48 and g['add']['height'] >= 32 and g['add']['left'] >= g['bankrow']['left'] and g['add']['right'] <= g['bankrow']['right'] + 1 and g['add']['top'] >= g['bankrow']['top'] and g['add']['bottom'] <= g['bankrow']['bottom'] + 1, f'{tag}: add button outside account row or too small {g["add"]}')
            check(page.get_by_role('button', name='Додати рахунок', exact=True).count() == 1, f'{tag}: add account action has no accessible name')
            for left, right in zip(g['banks'], g['banks'][1:] + [g['add']]):
                check(left['right'] <= right['left'] + 1, f'{tag}: accounts or add button overlap')
            check(all(t and t['height'] > 0 for t in g['titles']), f'{tag}: bottom card titles must be visible {g["titles"]}')
            # Назви нижніх карток мають спільний початок, навіть коли довга назва переноситься.
            for edge in ('top',):
                _equal([t[edge] for t in g['titles']], f'{tag}: bottom card title {edge}')
            c = g['cards']
            check(all(r and r['width'] > 0 and r['height'] > 0 for r in c.values()), f'{tag}: картка відсутня {c}')
            f, n, b, i, r = (c[key] for key in ('forecast', 'near', 'budget', 'inst', 'recent'))
            check(r['bottom'] <= height + 1, f'{tag}: нижні картки виходять за екран {r}')
            for edge in ('top', 'bottom'):
                _equal([f[edge], n[edge]], f'{tag}: перший ряд {edge}')
                _equal([b[edge], i[edge], r[edge]], f'{tag}: другий ряд {edge}')
            check(g['unas'] is None, f'{tag}: старий додатковий ряд без рахунку повернувся')
            gap = i['left'] - b['right']
            _equal([i['width'], r['width']], f'{tag}: ширина двох правих нижніх карток')
            _equal([b['width'], 2 * i['width'] + gap], f'{tag}: бюджет займає половину нижнього ряду')
            _equal([f['left'], b['left'], k[0]['left'], g['wallet']['left'], g['grid']['left']], f'{tag}: лівий край')
            track = (g['grid']['width'] - 11 * gap) / 12
            for name, card, span in (('прогноз', f, 8), ('найближче', n, 4), ('бюджет', b, 6), ('розстрочки', i, 3), ('операції', r, 3)):
                _equal([card['width'], span * track + (span - 1) * gap], f'{tag}: {name}, ширина {span} треків')
            _equal([n['right'], r['right'], k[-1]['right'], g['wallet']['right'], g['grid']['right']], f'{tag}: правий край')
            _equal([gap, r['left']-i['right'], n['left']-f['right']], f'{tag}: проміжки колонок')
            if g['badge']:
                u = g['badge']
                check(u['width'] > 0 and u['height'] > 0 and u['left'] >= b['left'] and u['right'] <= b['right'] + 1 and u['top'] >= b['top'] and u['bottom'] <= b['bottom'] + 1, f'{tag}: сума без рахунку обрізана {u}')
                check('Без рахунку' in u['text'] and 'Коригування власних коштів' in u['label'], f'{tag}: загублено зміст коригування без рахунку {u}')
            check(b['top'] >= f['bottom'] + 1, f'{tag}: ряди перетинаються {c}')
            check(g['wide'] <= width and g['doc'] <= height + 1 and not g['clipped'] and not g['inner'], f'{tag}: обрізані суми або прокрутка {g}')
            overview_bounds(page, tag)
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            check(page.evaluate('scrollY<=1'), f'{tag}: Огляд можна прокрутити вертикально')
            page.evaluate('window.scrollTo(0,0)')
            print(f'      {tag}: 3 KPI, спільні краї двох рядів, суми видимі')


CHECKS = [('overview_alignment: desktop shared grid in both themes', 'desktop', desktop_grid)]
