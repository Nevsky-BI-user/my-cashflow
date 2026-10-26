"""Повний Огляд і природні фото цілей без прокрутки на ПК."""
import base64
import json
from helpers import check, freeze, go_tab, settle, shot

SIZES = ((1280, 720), (1440, 900), (1536, 864), (1899, 994), (1920, 1080))
PATCHES = [
    ('const BCAT=[', "const BCAT=[{id:'vp1',name:'Побутові речі',limit:500,color:'#769881',icon:'1'},{id:'vp2',name:'Освіта',limit:500,color:'#a27395',icon:'2'},{id:'vp3',name:'Спорт',limit:500,color:'#b39459',icon:'3'},"),
    ('const TX_DEMO_ROWS=[', "ACCOUNTS_DEMO.push(Object.assign({},ACCOUNTS_DEMO[0],{id:'vp4',name:'Тестова дебетова',sort_order:3}),Object.assign({},ACCOUNTS_DEMO[2],{id:'vp5',name:'Тестова додаткова',sort_order:4}));const TX_DEMO_ROWS=["),
    ('return TX_DEMO_ROWS.map(function(r,i)', "return TX_DEMO_ROWS.concat(BCAT.filter(function(c){return !['savings','debt_card','debt_installment'].includes(c.id)}).map(function(c,i){return[31,'Тест '+c.name,101+i,'out','mono',null,c.id,1]})).map(function(r,i)"),
]
GEOMETRY = r"""()=>{
 const selectors='.content,.p-overview,.dv-cards,.dv-kpis,.ov-grid,.dv-bud,.dv-fc,.dv-near,.dv-recent,.ov-grid>.kpi-inst,.dv-bud .bd-leg,.ov-grid>.kpi-inst .kpi-rows';
 const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,b:r.bottom,right:r.right}};
 return {w:innerWidth,h:innerHeight,doc:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
 blocks:[...document.querySelectorAll(selectors)].filter(e=>e.getClientRects().length).map(e=>({c:e.className,...rect(e),sw:e.scrollWidth,cw:e.clientWidth,sh:e.scrollHeight,ch:e.clientHeight})),
 rows:[...document.querySelectorAll('.dv-bud .bd-row,.dv-near .dv-ev,.dv-recent [data-tx-id],.ov-grid>.kpi-inst [data-r=inst],.dv-cards>.bcard,.dv-cards>.bcard-add')].map(e=>{const clips=[];for(let p=e.parentElement;p;p=p.parentElement){if(/hidden|auto|scroll|clip/.test(getComputedStyle(p).overflowY)){clips.push(rect(p))}}return{c:e.className,...rect(e),clips}})}
}
"""

def overview(page):
    failures = []
    for theme in ('light', 'dark'):
        page.evaluate('(v)=>localStorage.setItem("theme",v)', theme)
        freeze(page, '2026-10-26', PATCHES)
        page.unroute(page.url)
        go_tab(page, 0)
        check(page.locator('.dv-cards>.bcard').count() == 5, 'Fixture requires five accounts')
        check(page.locator('.dv-bud .bd-row').count() == 17, 'Fixture requires seventeen categories')
        check(page.locator('.ov-grid>.kpi-inst [data-r=inst]').count() == 4, 'Fixture requires four installments')
        for width, height in SIZES:
            page.set_viewport_size({'width': width, 'height': height})
            settle(page)
            state = page.evaluate(GEOMETRY)
            tag = f'{theme}/{width}x{height}'
            if state['doc'][0] > width or state['doc'][1] > height:
                failures.append([tag, 'document', state['doc']])
            for b in state['blocks']:
                if b['sw'] > b['cw'] + 1 or b['sh'] > b['ch'] + 1 or b['b'] > height + 1:
                    failures.append([tag, 'block', b])
            for r in state['rows']:
                if r['y'] < 0 or r['b'] > height + 1 or r['right'] > width + 1 or any(r['y'] < c['y'] - 1 or r['b'] > c['b'] + 1 for c in r['clips']):
                    failures.append([tag, 'row', r])
            shot(page, f'no-scroll-overview-{theme}-{width}.jpg')
    check(not failures, json.dumps(failures, ensure_ascii=False))

def _photo_patch():
    urls = {}
    for i, (w, h) in enumerate(((1600,900),(1500,1000),(1400,1000))):
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#638b83"/><rect x="5" y="5" width="{w-10}" height="{h-10}" fill="none" stroke="#ffe8ac" stroke-width="10"/></svg>'
        urls['photo-proof-'+str(i)]='data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()
    return [('const[dbGoals,setDbGoals]=useState(null);const[goalUrls,setGoalUrls]=useState({});', 'const[dbGoals,setDbGoals]=useState(GOALS.map(function(g,i){return Object.assign({},g,{image:"photo-proof-"+i})}));const[goalUrls,setGoalUrls]=useState('+json.dumps(urls)+');')]

def goals(page):
    failures=[]
    for theme in ('light','dark'):
        page.evaluate('(v)=>localStorage.setItem("theme",v)',theme)
        freeze(page,'2026-10-26',_photo_patch());page.unroute(page.url);go_tab(page,4)
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height});settle(page)
            for img in page.locator('.board-d img').all():img.evaluate('e=>e.decode()')
            settle(page)
            result=page.evaluate("""()=>({doc:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],cards:[...document.querySelectorAll('.board-d>.gtile')].map(e=>{const r=e.getBoundingClientRect(),im=e.querySelector('img'),i=im?.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,b:r.bottom,h:r.height,iw:i?.width,ih:i?.height,ratio:im?im.naturalWidth/im.naturalHeight:0}})})""")
            c=result['cards'];tag=f'{theme}/{width}x{height}'
            check(len(c)==3 and all(x['ratio'] for x in c),'Photo fixture did not load')
            if result['doc'][0]>width or result['doc'][1]>height or any(x['b']>height+1 or abs(x['iw']-(x['w']-2))>1 or abs(x['iw']/x['ih']-x['ratio'])>.01 for x in c) or c[0]['w']<=c[1]['w'] or abs(c[1]['h']-c[2]['h'])>1 or abs(c[0]['b']-c[2]['b'])>1:
                failures.append([tag,result])
            shot(page,f'no-scroll-goals-{theme}-{width}.jpg')
    check(not failures,json.dumps(failures))

def unassigned(page):
    rows=[dict(id='u'+str(i),date='2026-10-25',created_at='2026-10-25T12:00:00Z',type='expense',amount=100+i,description='Synthetic unassigned '+str(i)) for i in range(6)]
    patch=PATCHES+[('today:now,core:core,msAdv:msAdv','today:now,core:Object.assign({},core,{unassigned:-615,unList:'+json.dumps(rows)+'}),msAdv:msAdv')]
    freeze(page,'2026-10-26',patch);page.unroute(page.url);go_tab(page,0)
    page.set_viewport_size({'width':1280,'height':720});settle(page)
    badge=page.locator('.budget-unassigned')
    check(badge.count()==1 and '6' in badge.inner_text() and '615' in badge.inner_text(),'Unassigned total/count must remain visible')
    check(page.locator('.dv-unas').count()==0,'Auxiliary preview must not overlap the bottom row')
    state=page.evaluate(GEOMETRY)
    check(all(b['sw']<=b['cw']+1 and b['sh']<=b['ch']+1 for b in state['blocks']),'Unassigned badge creates overflow: '+json.dumps(state))
    badge.click();page.wait_for_selector('.p-flow')

CHECKS=[('overview complete no scroll','desktop',overview),('goals featured complete photos','desktop',goals),('unassigned accessible summary','desktop',unassigned)]
