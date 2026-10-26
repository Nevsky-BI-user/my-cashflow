"""Огляд: усі картки й рядки одночасно видимі без прокрутки на ПК."""
import json

from helpers import check, freeze, go_tab, settle, shot


DAY = '2026-10-26'
VIEWPORTS = ((1899, 994), (1920, 1080), (1440, 900), (1280, 800), (1280, 720))
CARDS = '.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas'

# Лише синтетичні демо-дані: 17 витратних категорій, пʼять рахунків і операції поточного періоду.
MANY = [
    ('const BCAT=[', "const BCAT=[{id:'vp1',name:'Побутові речі',limit:500,color:'#769881',icon:'1'},{id:'vp2',name:'Освіта',limit:500,color:'#a27395',icon:'2'},{id:'vp3',name:'Спорт',limit:500,color:'#b39459',icon:'3'},"),
    ('const TX_DEMO_ROWS=[', "ACCOUNTS_DEMO.push(Object.assign({},ACCOUNTS_DEMO[0],{id:'vp4',name:'Тестова дебетова',sort_order:3}),Object.assign({},ACCOUNTS_DEMO[2],{id:'vp5',name:'Тестова додаткова',sort_order:4}));const TX_DEMO_ROWS=["),
    ('return TX_DEMO_ROWS.map(function(r,i)', "return TX_DEMO_ROWS.concat(BCAT.filter(function(c){return !['savings','debt_card','debt_installment'].includes(c.id)}).map(function(c,i){return[31,'Тест '+c.name,101+i,'out','mono',null,c.id,1]})).map(function(r,i)"),
]


BASIC = [('return TX_DEMO_ROWS.map(function(r,i)', "return TX_DEMO_ROWS.concat([[31,'Тестова покупка поточного періоду',1000,'out','mono',null,'food',1]]).map(function(r,i)")]

UNASSIGNED_ROWS = [dict(id='u' + str(i), date='2026-10-25', created_at='2026-10-25T12:00:00Z', type='expense', amount=amount, description='Synthetic unassigned ' + str(i)) for i, amount in enumerate((100, 1100, 12345, 123456.78, 999, 50))]
UNASSIGNED = MANY + [('today:now,core:core,msAdv:msAdv', 'today:now,core:Object.assign({},core,{unassigned:-138050.78,unList:' + json.dumps(UNASSIGNED_ROWS) + '}),msAdv:msAdv')]


GEOMETRY = r"""selectors=>{
 const visible=e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden';
 const rect=e=>{const r=e.getBoundingClientRect();return{top:r.top,left:r.left,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
 const blocks=[...document.querySelectorAll('.p-overview,.dv-cards,.dv-kpis,.ov-grid,.dv-cols .surface,.dv-bud .bd-leg,.dv-cols>.kpi-inst .kpi-rows')].filter(visible);
 return {wide:document.documentElement.scrollWidth,doc:document.documentElement.scrollHeight,
 overflow:blocks.filter(e=>e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1).map(e=>({cls:e.className,width:[e.scrollWidth,e.clientWidth],height:[e.scrollHeight,e.clientHeight]})),
 cards:[...document.querySelectorAll(selectors)].filter(visible).map(e=>({cls:e.className,...rect(e)})),
 donut:[...document.querySelectorAll('.dv-bud .bd-desk svg')].filter(visible).map(rect),
 chart:[...document.querySelectorAll('.dv-fc svg')].filter(visible).map(rect),
 font:[...document.querySelectorAll('.dv-bud .bd-row')].filter(visible).map(e=>parseFloat(getComputedStyle(e).fontSize))};
}"""


REACHABLE = r"""e=>{
 const row=e.getBoundingClientRect(), clips=[];
 for(let p=e.parentElement;p;p=p.parentElement){
  const s=getComputedStyle(p),r=p.getBoundingClientRect();
  if(/auto|scroll|hidden|clip/.test(s.overflowY))clips.push({cls:p.className,top:r.top,bottom:r.bottom,overflow:s.overflowY});
 }
 return {row:{top:row.top,bottom:row.bottom},clips};
}"""


def _rows_visible(page, selector, tag):
    rows = page.locator(selector)
    if not rows.count():
        return
    for row in rows.all():
        state = row.evaluate(REACHABLE)
        check(state['row']['top'] >= -1 and state['row']['bottom'] <= page.viewport_size['height'] + 1,
              f'{tag}: рядок поза екраном без прокрутки: {state}')
        check(all(state['row']['top'] >= c['top'] - 1 and state['row']['bottom'] <= c['bottom'] + 1 for c in state['clips']),
              f'{tag}: рядок обрізаний контейнером: {state}')
        bounds = row.evaluate(r"""e=>{
          const r=e.getBoundingClientRect(),card=e.closest('.surface')?.getBoundingClientRect();
          return{row:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},card:card?{left:card.left,right:card.right,top:card.top,bottom:card.bottom}:null,
          clipped:[...e.querySelectorAll('.bd-sum,.bd-pct,.dv-ev-a,.kpi-iv,.kpi-ie,span:last-child')].filter(x=>{const b=x.getBoundingClientRect();return x.scrollWidth>x.clientWidth+1||b.left<r.left-1||b.right>r.right+1}).map(x=>x.textContent)};
        }""")
        check(not bounds['clipped'], f'{tag}: сума чи поле рядка обрізані: {bounds}')
        check(not bounds['card'] or all(bounds['row'][k] >= bounds['card'][k] - 1 for k in ('left', 'top')) and all(bounds['row'][k] <= bounds['card'][k] + 1 for k in ('right', 'bottom')), f'{tag}: рядок виходить за власну картку: {bounds}')


def _desktop(page, many, unassigned=False):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        freeze(page, DAY, UNASSIGNED if unassigned else MANY if many else BASIC)
        # Фікстура має діяти лише для цього перезавантаження: наступна тема застосує її знову.
        page.unroute(page.url)
        go_tab(page, 0)
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            # Чекаємо саме React-стан compactNear після matchMedia, а не довільну висоту сторінки.
            ring_size = 96 if width < 1400 or height < 1000 else 112
            page.wait_for_function('(size)=>document.querySelector(".dv-bud .bd-ring svg")?.getAttribute("width")===String(size)', arg=ring_size)
            settle(page)
            page.evaluate('window.scrollTo(0,0)')
            tag = f'{theme}/{width}x{height}/{"без рахунку" if unassigned else "17 категорій" if many else "демо"}'
            if many:
                check(page.locator('.dv-cards .bcard').count() == 5, f'{tag}: фікстура не має пʼяти рахунків')
                check(page.locator('.dv-bud .bd-row').count() == 17, f'{tag}: фікстура не має 17 категорій')
            state = page.evaluate(GEOMETRY, CARDS)
            check(len(state['cards']) >= 5, f'{tag}: відсутні основні картки')
            check(state['wide'] <= width and state['doc'] <= height + 1, f'{tag}: сторінка виходить за екран: {state}')
            check(not state['overflow'], f'{tag}: повернулася прокрутка або приховане переповнення: {state["overflow"]}')
            check(all(c['top'] >= -1 and c['left'] >= -1 and c['right'] <= width + 1 and c['bottom'] <= height + 1 for c in state['cards']),
                  f'{tag}: обрізані краї карток: {state}')
            check(state['donut'] and all(d['width'] >= 80 and d['height'] >= 80 for d in state['donut']), f'{tag}: діаграма прихована або надто мала: {state}')
            budget = page.locator('.dv-bud').bounding_box()
            check(all(d['top'] >= budget['y'] and d['bottom'] <= budget['y'] + budget['height'] for d in state['donut']), f'{tag}: діаграма бюджету обрізана: {state}')
            minimum_chart = 144 if height <= 760 else 150
            check(state['chart'] and state['chart'][0]['height'] >= minimum_chart, f'{tag}: графік надто малий: {state}')
            check(not state['font'] or min(state['font']) >= 11, f'{tag}: шрифт легенди зменшено до нечитабельного: {state}')
            for selector in ('.dv-bud .bd-row', '.dv-cols>.kpi-inst [data-r=inst]', '.dv-near .dv-ev', '.dv-recent [data-tx-id]'):
                check(page.locator(selector).count() > 0, f'{tag}: фікстура не має рядків {selector}')
                _rows_visible(page, selector, tag)
            if unassigned:
                check(page.locator('.dv-unas').count() == 0, f'{tag}: старий додатковий ряд повернувся')
                badge = page.locator('.budget-unassigned')
                check(badge.count() == 1 and badge.is_visible(), f'{tag}: підсумок операцій без рахунку приховано')
                text = badge.inner_text().replace('\xa0', ' ')
                check('Без рахунку 6' in text and '−138 051 ₴' in text, f'{tag}: змінено кількість або підсумок: {text}')
                check(badge.get_attribute('type') == 'button' and 'Відкрити операції та вибрати рахунок' in badge.get_attribute('aria-label'), f'{tag}: перехід до операцій без рахунку недоступний')
                bounds = badge.evaluate(r"""e=>{const r=e.getBoundingClientRect(),p=e.closest('.dv-bud').getBoundingClientRect();return{fit:r.left>=p.left&&r.right<=p.right+1&&r.top>=p.top&&r.bottom<=p.bottom+1,clipped:e.scrollWidth>e.clientWidth+1};}""")
                check(bounds['fit'] and not bounds['clipped'], f'{tag}: підсумок чи кнопка без рахунку обрізані: {bounds}')
            check(page.evaluate('scrollY<=1&&document.documentElement.scrollHeight<=innerHeight+1'), f'{tag}: Огляд потребує вертикальної прокрутки')
            if width in (1899, 1280):
                shot(page, f'overview-viewport-{theme}-{width}-{height}-{"unas" if unassigned else "many" if many else "demo"}.jpg', full=False)
        if unassigned:
            # Підсумок використовує справжній наявний перехід; тестові core-рядки
            # перевіряють представлення, тому не підмінюємо список транзакцій.
            page.locator('.budget-unassigned').focus()
            page.keyboard.press('Enter')
            page.wait_for_selector('.p-flow.desk')
            check(page.locator('.flow-unas[aria-pressed="true"]').count() == 1, f'{theme}: не вибрано фільтр операцій без рахунку')


def desktop(page):
    _desktop(page, False)


def many_categories(page):
    _desktop(page, True)


def unassigned_operations(page):
    _desktop(page, True, True)


def mobile(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    freeze(page, DAY, MANY)
    page.unroute(page.url)
    go_tab(page, 0)
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>document.documentElement.dataset.theme=t', theme)
        settle(page)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{theme}: мобільне горизонтальне переповнення')
        check(page.evaluate('document.documentElement.scrollHeight>innerHeight'), f'{theme}: мобільну сторінку затиснуто у висоту екрана')
        page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
        check(page.evaluate('scrollY>0'), f'{theme}: мобільна прокрутка недоступна')
        page.evaluate('window.scrollTo(0,0)')


CHECKS = [
    ('Overview: visible cards and visuals across desktop heights', 'desktop', desktop),
    ('Overview: all 17 category rows visible without scrolling', 'desktop', many_categories),
    ('Overview: unassigned summary and existing Operations route', 'desktop', unassigned_operations),
    ('Overview: mobile keeps normal document scrolling', 'mobile', mobile),
]
