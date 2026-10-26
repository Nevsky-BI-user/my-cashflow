"""Огляд: цілі картки в межах екрана, повні візуали й досяжні довгі списки."""
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
 return {wide:document.documentElement.scrollWidth,doc:document.documentElement.scrollHeight,
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


def _rows_reachable(page, selector, tag):
    rows = page.locator(selector)
    if not rows.count():
        return
    for index in (0, rows.count() - 1):
        row = rows.nth(index)
        row.scroll_into_view_if_needed()
        state = row.evaluate(REACHABLE)
        check(state['row']['top'] >= -1 and state['row']['bottom'] <= page.viewport_size['height'] + 1,
              f'{tag}: рядок поза екраном після прокрутки: {state}')
        check(all(state['row']['top'] >= c['top'] - 1 and state['row']['bottom'] <= c['bottom'] + 1 for c in state['clips']),
              f'{tag}: рядок обрізаний контейнером після прокрутки: {state}')
    page.evaluate('window.scrollTo(0,0)')


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
                _rows_reachable(page, selector, tag)
            if unassigned:
                region = page.locator('.dv-unas')
                check(region.count() == 1 and region.is_visible(), f'{tag}: картку без рахунку приховано')
                check(region.locator('.unas-row').count() == 4, f'{tag}: показано не чотири операції')
                more = region.locator(':scope > .dv-lbl-btn')
                check(more.count() == 1 and 'ще 2' in more.inner_text(), f'{tag}: немає переходу до решти операцій')
                check(region.get_attribute('role') == 'region' and region.get_attribute('aria-label') == 'Операції без рахунку' and region.evaluate('e=>e.tabIndex>=0'), f'{tag}: регіон без рахунку недоступний з клавіатури')
                if region.evaluate('e=>e.scrollHeight>e.clientHeight+2'):
                    check(region.evaluate('e=>["auto","scroll"].includes(getComputedStyle(e).overflowY)'), f'{tag}: операції обрізані замість прокрутки')
                    region.focus()
                    region.press('Home')
                    region.press('End')
                    page.wait_for_function('e=>e.scrollTop>0', arg=region.element_handle())
                _rows_reachable(page, '.dv-unas .unas-row', tag)
                _rows_reachable(page, '.dv-unas > .dv-lbl-btn', tag)
                clipped = region.locator('.unas-row > span:last-of-type').evaluate_all('es=>es.filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)')
                check(not clipped, f'{tag}: суми операцій обрізані горизонтально {clipped}')
                for row in region.locator('.unas-row').all():
                    row.scroll_into_view_if_needed()
                    bounds = row.evaluate(r"""e=>{
                      const r=e.getBoundingClientRect(),c=e.closest('.dv-unas').getBoundingClientRect(),description=e.querySelector('span:nth-child(2)'),amount=e.querySelector('span:nth-child(3)'),pick=e.querySelector('.pick-acc');
                      const rect=x=>{const b=x.getBoundingClientRect();return{left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,height:b.height}};
                      return{row:rect(e),card:rect(e.closest('.dv-unas')),overflow:e.scrollWidth-e.clientWidth,description:description?rect(description):null,amount:amount?rect(amount):null,pick:pick?rect(pick):null};
                    }""")
                    check(bounds['overflow'] <= 1, f'{tag}: рядок операції переповнюється горизонтально {bounds}')
                    check(bounds['description'] and bounds['description']['width'] > 0, f'{tag}: зник опис операції {bounds}')
                    for field in ('amount', 'pick'):
                        child = bounds[field]
                        check(child and child['width'] > 0 and child['height'] > 0, f'{tag}: відсутня сума або кнопка вибору {bounds}')
                        check(all(child['left'] >= parent['left'] - 1 and child['right'] <= parent['right'] + 1 and child['top'] >= parent['top'] - 1 and child['bottom'] <= parent['bottom'] + 1 for parent in (bounds['row'], bounds['card'])), f'{tag}: сума або кнопка виходить за рядок/картку {bounds}')
                region.evaluate('e=>e.scrollTop=0')
                page.evaluate('document.activeElement.blur()')
            check(page.evaluate('document.documentElement.scrollHeight<=innerHeight+1'), f'{tag}: досяжність рядків розширила сторінку')
            if width in (1899, 1280):
                shot(page, f'overview-viewport-{theme}-{width}-{height}-{"unas" if unassigned else "many" if many else "demo"}.jpg', full=False)


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
    ('Overview: 17 category rows reachable within viewport', 'desktop', many_categories),
    ('Overview: unassigned operations share the visible bottom row', 'desktop', unassigned_operations),
    ('Overview: mobile keeps normal document scrolling', 'mobile', mobile),
]
