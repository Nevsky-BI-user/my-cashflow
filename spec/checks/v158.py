"""v158 (власник 12.10.2026, бриф анімацій; картка «Розподіл виплати» з монетою перенесена у v159): анімації від функції.
2) «Внести оплату»: рядок згасає 300 мс, «баланс після» докручується без блимання кінцевого значення.
3) Графік: лінія малюється при першій появі, тривалості 0,2-0,6 с; зміна теми не додає анімацій.
4) Нова операція: спалах рядка лише для нових id (не на першому завантаженні), в «Останні операції» і в Потоці.
5) Кільце бюджету: росте лише сегмент категорії, без перемонтування.
reduced-motion: без руху, одразу кінцевий стан."""
import re
from helpers import ROOT, check, dialog, freeze, go_tab, settle

DAY = '2026-10-13'

# записувач анімацій (CSS і WAAPI) і спалахів рядків; ставиться до завантаження сторінки
REC = r"""(()=>{window.__AN=[];window.__FLASH=[];const seen=new WeakSet();
 const tick=()=>{try{document.getAnimations().forEach(a=>{if(seen.has(a))return;seen.add(a);const t=a.effect&&a.effect.target,tm=a.effect?a.effect.getTiming():{};
  window.__AN.push({n:a.animationName||(a.transitionProperty?'transition:'+a.transitionProperty:'waapi'),d:tm.duration,del:tm.delay||0,c:t&&t.getAttribute?(t.getAttribute('class')||t.tagName):'',ts:performance.now()})})}catch(e){}requestAnimationFrame(tick)};requestAnimationFrame(tick);
 new MutationObserver(ms=>{ms.forEach(m=>{const e=m.target;if(m.attributeName==='class'&&e.classList&&e.classList.contains('tx-flash'))window.__FLASH.push({id:e.getAttribute('data-tx-id'),ts:performance.now()})})}).observe(document,{subtree:true,attributes:true,attributeFilter:['class']});})()"""


def _desk(page, w=1440, hh=900, reduce=False, patch=None):
    page.set_viewport_size({'width': w, 'height': hh})
    if reduce:
        page.emulate_media(reduced_motion='reduce')
    page.add_init_script(REC)
    freeze(page, DAY, patch)
    go_tab(page, 0)
    page.wait_for_timeout(300)
    settle(page)


SADOK = [("{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false}",
          "{id:'f2',name:'Садочок',amount:3500,day_of_month:10,type:'payment',color:'#f6d06f',active:true,credit_ok:false,variable:true}")]
PICK = """(name)=>{for(const b of document.querySelectorAll('.pay-done')){let e=b;while(e&&e.querySelectorAll('.pay-done').length<=1){if(e.textContent.includes(name)){b.setAttribute('data-pick','1');return true}e=e.parentElement}}return false}"""
BA_OBS = r"""()=>{window.__BA={};const rec=()=>window.__BA&&document.querySelectorAll('[data-ba]').forEach(e=>{const k=e.getAttribute('data-ba'),t=e.lastChild;if(!t||t.nodeType!==3)return;const a=window.__BA[k]=window.__BA[k]||[];if(a[a.length-1]!==t.nodeValue)a.push(t.nodeValue)});
 rec();const tick=()=>{rec();if(window.__BA)requestAnimationFrame(tick)};requestAnimationFrame(tick)}"""


def _pay_flow(page, reduce):
    page.set_viewport_size({'width': 1920, 'height': 1080})
    if reduce:
        page.emulate_media(reduced_motion='reduce')
    page.add_init_script(REC)
    freeze(page, '2026-10-08', SADOK)
    go_tab(page, 2)
    check(page.evaluate(PICK, 'Садочок'), 'немає «Внести оплату» у Садочка')
    page.evaluate("()=>{const b=document.querySelector('[data-pick]');b.closest('.flow-row').setAttribute('data-probe','1')}")
    page.locator('[data-pick="1"]').click()
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    dlg.locator('input[placeholder="Сума"]').fill('3400')
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    page.evaluate(BA_OBS)
    n0 = page.evaluate('()=>window.__AN.length')
    dlg.locator('.tx-save').click()
    page.wait_for_timeout(120)
    # hover-перехід фону (курсор після діалогу над рядком) не є згасанням
    fade = page.evaluate("()=>{const r=document.querySelector('[data-probe]');return r?r.getAnimations().filter(a=>a.transitionProperty!=='background-color').map(a=>{const t=a.effect.getTiming();return t.duration}):null}")
    page.wait_for_timeout(1300)
    ba = page.evaluate('()=>{const b=window.__BA;window.__BA=null;return b}')
    gone = page.evaluate("()=>!document.querySelector('[data-probe]')")
    return fade, ba, gone, page.evaluate('()=>window.__AN')[n0:]


def pay_fade(page):
    """«Внести оплату» в Потоці ПК: рядок згасає за 300 мс, «баланс після» наступних платежів докручується від старого до нового значення."""
    fade, ba, gone, _ = _pay_flow(page, False)
    check(fade == [300], f'рядок оплати не згасає 300 мс: {fade}')
    check(gone, 'сплачений план лишився в Потоці')
    moved = {k: v for k, v in ba.items() if len(v) >= 3}
    print(f'      докручено «баланс після»: {len(moved)} з {len(ba)}; приклад {next(iter(moved.items()), None)}')
    check(moved, f'«баланс після» не докручується: {ba}')
    # до докрутки кінцеве значення не показується (докрутка стартує до відмальовки, layout-ефект)
    flick = {k: v[:3] for k, v in moved.items() if v[-1] in v[1:-1]}
    check(not flick, f'кінцеве значення блимнуло до докрутки: {flick}')
    final = page.evaluate("()=>{const o={};document.querySelectorAll('[data-ba]').forEach(e=>{const t=e.lastChild;if(t&&t.nodeType===3)o[e.getAttribute('data-ba')]=t.nodeValue});return o}")
    check(all(final.get(k) == v[-1] for k, v in moved.items() if k in final), 'після докрутки текст не кінцевий')


def pay_fade_reduced(page):
    """reduced-motion: без згасання і без проміжних значень, одразу кінцевий стан."""
    fade, ba, gone, new = _pay_flow(page, True)
    check(not fade, f'reduced-motion: рядок анімується: {fade}')
    check(gone and all(len(v) <= 2 for v in ba.values()), f'reduced-motion: проміжні значення: {[v for v in ba.values() if len(v) > 2][:2]}')


def _new_tx(page, amount, cat):
    page.keyboard.press('n')
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, 'форма нової операції не відкрилась')
    dlg.locator('input[placeholder="Сума"]').fill(str(amount))
    dlg.locator('button', has_text=cat).first.click()
    dlg.locator('.acc-seg button[data-acc="l1"]').click()
    dlg.locator('.tx-save').click()


RING = r"""()=>{const b=document.querySelector('.dv-bud .bd, .bd');const ps=[...b.querySelectorAll('path.bd-seg')];window.__RING=ps;return ps.map(p=>p.getAttribute('data-id'))}"""


def tx_flash_ring(page):
    """Перше завантаження без спалаху; нова витрата: спалах її рядка в «Останні операції» (і в Потоці), сегмент категорії кільця росте 400 мс без перемонтування решти."""
    _desk(page)
    page.wait_for_timeout(800)
    check(page.evaluate('()=>window.__FLASH.length') == 0, 'спалах на першому завантаженні')
    ids0 = page.evaluate(RING)
    cat = page.evaluate("()=>String((CATEGORIES||[]).find(c=>c.name==='Продукти').id)") if page.evaluate("()=>typeof CATEGORIES!=='undefined'") else None
    n0 = page.evaluate('()=>window.__AN.length')
    page.evaluate(r"""()=>{window.__D=[];window.__G=[];const tick=()=>{if(!window.__RING)return;const g=document.querySelector('path.bd-seg.bd-grow');if(g){window.__G.push(g.getAttribute('data-id'));const d=g.getAttribute('d');if(window.__D[window.__D.length-1]!==d)window.__D.push(d)}if(window.__D.length<200)requestAnimationFrame(tick)};requestAnimationFrame(tick)}""")
    _new_tx(page, 700, 'Продукти')
    page.wait_for_timeout(1200)
    fl = page.evaluate('()=>window.__FLASH')
    nid = page.evaluate("()=>{const r=document.querySelector('.dv-recent [data-tx-id]');return r?r.getAttribute('data-tx-id'):null}")
    print(f'      спалахи: {fl}; новий рядок {nid}')
    check(nid and nid.startswith('l') and [f['id'] for f in fl] == [nid], f'спалах не лише нового рядка: {fl}, новий {nid}')
    grow = page.evaluate("()=>[new Set(window.__G).size?[...new Set(window.__G)]:[],window.__D.length,window.__RING.every(p=>p.isConnected),document.querySelectorAll('path.bd-seg.bd-grow').length]")
    print(f'      кільце: сегмент {grow[0]}, кадрів шляху {grow[1]}, старі шляхи на місці {grow[2]}')
    check(len(grow[0]) == 1 and grow[1] >= 4 and grow[2] and grow[3] == 0, f'кільце: росте не один сегмент плавно або перемонтовано: {grow}')
    if cat:
        check(grow[0][0] == cat or grow[0][0] == '__other', f'росте не сегмент Продуктів: {grow[0]} проти {cat}')
    check(page.evaluate(RING) == ids0, 'набір сегментів змінився')
    new = [a for a in page.evaluate('()=>window.__AN')[n0:] if a['n'] == 'bd-in']
    check(not new, f'кільце перемальоване (bd-in): {new}')
    go_tab(page, 2)
    page.wait_for_timeout(300)
    fl2 = page.evaluate('()=>window.__FLASH')
    check(len(fl2) == 2 and fl2[1]['id'] == nid, f'у Потоці новий рядок не спалахнув один раз: {fl2}')
    tf = [a for a in page.evaluate('()=>window.__AN') if a['n'] == 'tx-flash']
    check(tf and all(a['d'] == 600 for a in tf), f'тривалість спалаху: {tf}')


def tx_flash_reduced(page):
    """reduced-motion: нова операція без спалаху, кільце без росту (одразу кінцевий стан)."""
    _desk(page, reduce=True)
    page.evaluate(RING)
    _new_tx(page, 700, 'Продукти')
    page.wait_for_timeout(900)
    check(page.evaluate("()=>[window.__FLASH.length,document.querySelectorAll('.bd-grow').length]") == [0, 0], 'reduced-motion: спалах або ріст кільця')


def chart_theme(page):
    """Графік: лінія малюється 0,2-0,6 с при першій появі, заливка проявляється; зміна теми не додає анімацій."""
    _desk(page)
    an = page.evaluate('()=>window.__AN')
    fc = [a for a in an if a['n'] in ('fc-draw', 'fc-fade')]
    check(any(a['n'] == 'fc-draw' for a in fc) and any(a['n'] == 'fc-fade' for a in fc), f'графік без анімації появи: {fc}')
    check(all(200 <= a['d'] <= 600 for a in fc), f'тривалість анімацій графіка: {fc}')
    n0 = len(an)
    page.keyboard.press('t')
    page.wait_for_timeout(700)
    new = [a for a in page.evaluate('()=>window.__AN')[n0:] if not a['n'].startswith('transition:')]
    check(not new, f'зміна теми додала анімації: {new}')

def version(page):
    """Версії sw.js і застосунку узгоджені; відкладена картка розподілу та монета відсутні."""
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    sw = (ROOT / 'sw.js').read_text(encoding='utf-8')
    app = re.search(r"APP_VER='(v[0-9]+)'", html)
    cache = re.search(r"const CACHE = 'cashflow-(v[0-9]+)'", sw)
    check(app and cache and app.group(1) == cache.group(1), 'версії застосунку й кешу не збігаються')
    check('assets/coin' not in sw and 'assets/coin' not in html, 'файли монети в ASSETS або в index.html')
    _desk(page)
    check(page.locator('.pyo, .pyo-slot, .coin-fly').count() == 0, 'відкладена картка розподілу присутня')


CHECKS = [
    ('v158: «Внести оплату»: згасання рядка і докрутка балансу після', 'desktop', pay_fade),
    ('v158: «Внести оплату»: reduced-motion', 'desktop', pay_fade_reduced),
    ('v158: нова операція: спалах і ріст сегмента кільця', 'desktop', tx_flash_ring),
    ('v158: нова операція: reduced-motion', 'desktop', tx_flash_reduced),
    ('v158: графік і зміна теми', 'desktop', chart_theme),
    ('v158: версія, без картки розподілу і файлів монети', 'desktop', version),
]
