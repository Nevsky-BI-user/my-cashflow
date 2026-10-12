# v148: «Розподіл бюджету» керує лімітами: перемикач «% / ₴» у рядку кожної категорії витрат (за sort_order, без окремого блоку
# ₴-лімітів і без напису «змінити: на Бюджеті»), «Розподілено» рахує ₴-ліміти як частку змінних; «Розблокувати всі» на телефоні.
import re

from helpers import check, dialog, finance_state, freeze, go_tab

DAY = '2026-10-12'
# як у проді: Здоровʼя з лімітом у гривнях
HEALTH_ABS = [("{id:'health',groupId:4,name:'Здоровʼя',limit:2000,", "{id:'health',groupId:4,name:'Здоровʼя',limit:0,limitAbs:10000,")]


def _open(page):
    """ПК: кнопка «Розподіл бюджету» на вкладці Бюджет (аркуш); телефон: вкладка «Налаштування» (v149), рядок «Розподіл бюджету»."""
    if page.viewport_size['width'] >= 1024:
        go_tab(page, 1)
        page.click('.dact')
    else:
        page.locator('.tab-bar .tab-btn').nth(5).click()
        page.wait_for_timeout(400)
        page.locator('.set-mpage button', has_text='Розподіл бюджету').first.click()
        page.wait_for_timeout(500)
        # v150: на телефоні розділ відкривається на всю сторінку з «Назад», без аркуша
        sh = page.locator('.set-mpage .set-msec[data-sec=budget]')
        check(sh.count() == 1 and dialog(page, 'Розподіл бюджету').count() == 0, 'сторінка «Розподіл бюджету» не відкрилась (або відкрився аркуш)')
        return sh
    page.wait_for_timeout(500)
    sh = dialog(page, 'Розподіл бюджету')
    check(sh.count() == 1, 'аркуш «Розподіл бюджету» не відкрився')
    return sh


def _total(sh):
    m = re.search(r'Розподілено(?:: | [^(]*\()(\d+)%', sh.inner_text())
    return int(m[1]) if m else -1


def _cur_cat(page, cid):
    r = finance_state(page)['result']
    cur = next(p for p in r['periods'] if p['basis'] == 'current')
    return next(c for c in cur['categories'] if c['id'] == cid)


def alloc_units(page):
    """Здоровʼя з ₴ на %, потім назад на ₴ 8 000, зберегти: у вході рушія limit_abs 8000 і вага 0, план категорії в рушії 8 000 ₴."""
    freeze(page, DAY, HEALTH_ABS)
    sh = _open(page)
    txt = sh.inner_text()
    check('змінити: на Бюджеті' not in txt and sh.locator('.bud-abs-row').count() == 0, 'лишився окремий блок ₴-лімітів з написом «змінити: на Бюджеті»')
    order = page.evaluate("BCAT.filter(c=>!c.isIncome).map(c=>String(c.id))")
    rows = sh.locator('.bud-cat-row').evaluate_all('a=>a.map(e=>e.dataset.cat)')
    check(rows == order, f'категорії не в порядку sort_order: {rows} проти {order}')
    row = sh.locator('.bud-cat-row[data-cat=health]')
    seg = row.locator('.cat-lim-seg')
    check('abs' in row.get_attribute('class') and seg.locator('button[aria-pressed=true]').inner_text() == '₴', 'Здоровʼя відкрилось не в режимі ₴')
    t0 = _total(sh)
    print(f'      на старті: Розподілено {t0}%, Здоровʼя {row.locator("input[type=text]").input_value()} ₴')
    check(abs(t0 - 100) <= 1, f'на старті з ₴-лімітом розподілено {t0}%')
    seg.locator('button', has_text='%').click()
    page.wait_for_timeout(200)
    check('abs' not in row.get_attribute('class') and row.locator('.nf-range').count() == 1, 'після «%» рядок не в режимі відсотка')
    t1 = _total(sh)
    check(abs(t1 - 100) <= 1, f'після переходу на % розподілено {t1}%')
    seg.locator('button', has_text='₴').click()
    page.wait_for_timeout(200)
    inp = row.locator('input[type=text]')
    inp.click()
    inp.fill('8000')
    inp.press('Enter')
    page.wait_for_timeout(200)
    check(inp.input_value().replace(' ', '').replace(' ', '') == '8000', f'поле суми {inp.input_value()!r}')
    t2 = _total(sh)
    print(f'      після % і назад ₴ 8 000: Розподілено {t1}% -> {t2}%')
    check(abs(t2 - 100) <= 1, f'після ₴ 8 000 розподілено {t2}%')
    sh.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(500)
    cat = next(c for c in finance_state(page)['data']['categories'] if str(c['id']) == 'health')
    check(cat.get('limit_abs') == 8000 and not cat.get('budget_limit'), f'у вході рушія Здоровʼя {cat}')
    ec = _cur_cat(page, 'health')
    print(f'      рушій: Здоровʼя limitAbsCents {ec.get("limitAbsCents")}, частка {ec.get("totalCents")}')
    check(ec.get('limitAbsCents') == 800000, f'план Здоровʼя в рушії {ec.get("limitAbsCents")}, а не 800000')


def unlock_all_phone(page):
    """Телефон (шестерня → «Розподіл бюджету»): за замовчуванням замків немає; два замки, «Розблокувати всі» вгорі знімає обидва."""
    freeze(page, DAY)
    sh = _open(page)
    locks = sh.locator('button[aria-label="Розблокувати"]')
    check(locks.count() == 0 and sh.locator('.bud-unlock-all').count() == 0, f'на старті заблоковано {locks.count()}')
    sh.locator('button[aria-label="Заблокувати"]').nth(0).click()
    sh.locator('button[aria-label="Заблокувати"]').nth(0).click()
    page.wait_for_timeout(150)
    btn = sh.locator('.bud-unlock-all button', has_text='Розблокувати всі')
    check(locks.count() == 2 and btn.count() == 1, f'заблоковано {locks.count()}, кнопок «Розблокувати всі» {btn.count()}')
    btn.click()
    page.wait_for_timeout(150)
    check(locks.count() == 0 and sh.locator('.bud-unlock-all').count() == 0, f'після «Розблокувати всі» заблоковано {locks.count()}')


# v148, кільце бюджету: сегменти без обводок (v150: насичені градієнти замість пастелі), число в центрі всередині внутрішнього кола, підказка в межах вʼюпорту, легенда з контрастом AA
RING = r"""scope=>{const ring=document.querySelector(scope+' .bd-ring');if(!ring)return null;const r0=+ring.dataset.r0,c=ring.getBoundingClientRect(),cx=c.left+c.width/2,cy=c.top+c.height/2;
const out=[...ring.querySelectorAll('.bd-c b,.bd-c span')].map(e=>{const r=e.getBoundingClientRect(),dx=Math.max(Math.abs(r.left-cx),Math.abs(r.right-cx)),dy=Math.max(Math.abs(r.top-cy),Math.abs(r.bottom-cy));return [e.textContent,Math.round(Math.hypot(dx,dy)*10)/10,r0,parseFloat(getComputedStyle(e).fontSize),e.scrollWidth<=e.clientWidth+1]});
const rgb=s=>{const n=(s.match(/[\d.]+/g)||[]).map(Number);return /^color\(/.test(s)?n.map((v,i)=>i<3?v*255:v):n};const lum=a=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(a[0])+0.7152*f(a[1])+0.0722*f(a[2])};
const bgOf=e=>{const base=rgb(getComputedStyle(document.documentElement).backgroundColor);let n=e;while(n&&n!==document.documentElement){const b=rgb(getComputedStyle(n).backgroundColor);if(b.length>=3&&(b.length<4||b[3]>0)){const a=b.length>3?b[3]:1;return [0,1,2].map(i=>b[i]*a+(base[i]||0)*(1-a))}n=n.parentElement}return base};
const cr=e=>{const f=lum(rgb(getComputedStyle(e).color)),b=lum(bgOf(e));return Math.round((Math.max(f,b)+0.05)/(Math.min(f,b)+0.05)*100)/100};
const leg=[...document.querySelectorAll(scope+' .bd-sum,'+scope+' .bd-pct,'+scope+' .bd-nm')].filter(e=>e.offsetParent).map(e=>[e.className,e.textContent,cr(e)]);
const hsl=c=>{const f=rgb(c);const mx=Math.max(...f.slice(0,3)),mn=Math.min(...f.slice(0,3));return [Math.round((mx+mn)/2/255*100)/100,Math.round((mx-mn)/255*100)/100]};
const segs=[...document.querySelectorAll(scope+' .bd-seg')].map(e=>{const s=getComputedStyle(e);const id=(s.fill.match(/url\("?#([^")]+)"?\)/)||[])[1];const g=id?document.getElementById(id):null;
const stops=g?[...g.querySelectorAll('stop')].map(x=>hsl(getComputedStyle(x).stopColor)):[hsl(s.fill)];return [e.dataset.id,s.fill,s.stroke,parseFloat(s.strokeWidth)||0,stops,!!g]});
return {out,leg,segs}}"""
TIPBOX = """()=>{const t=document.querySelector('.bd-tip');if(!t)return null;const r=t.getBoundingClientRect(),h=t.querySelector('.bd-tip-h');return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom),document.documentElement.clientWidth,innerHeight,h?h.scrollWidth<=h.clientWidth+1:true,t.textContent]}"""


def _ring_state(page, scope, tag):
    st = page.evaluate(RING, scope)
    check(st, f'{tag}: кільця немає')
    for txt, dist, r0, fs, whole in st['out']:
        check(dist <= r0 and whole, f'{tag}: «{txt}» виходить за внутрішнє коло: відстань кута {dist} > r0 {r0} (шрифт {fs})')
    for cls, txt, cr in st['leg']:
        check(cr >= 4.5, f'{tag}: контраст легенди {cls} «{txt}» {cr} < 4,5')
    for sid, fill, stroke, sw, stops, grad in st['segs']:
        check(sw == 0 or stroke in ('none', 'rgba(0, 0, 0, 0)'), f'{tag}: сегмент {sid} з обводкою {stroke} {sw}')
        # v150 (власник: «кольори як у монобанку»): замість пастелі насичений градієнт; сегмент заливає власний градієнт з 2+ кольоровими зупинками
        check(grad and len(stops) >= 2, f'{tag}: сегмент {sid} без градієнта {fill}: {stops}')
        # службові сегменти (__none: без категорії) лишаються сірими навмисно
        check(sid.startswith('__') or all(0.2 <= l <= 0.9 and c >= 0.2 for l, c in stops), f'{tag}: сегмент {sid}: зупинки градієнта не кольорові (світлість, насиченість) {stops}')
    return st


def _tip_in_view(page, tag):
    b = page.evaluate(TIPBOX)
    check(b, f'{tag}: підказка не зʼявилась')
    l, t, r, btm, vw, vh, whole, txt = b
    check(l >= 0 and t >= 0 and r <= vw and btm <= vh and whole, f'{tag}: підказка за межами вʼюпорту або обрізана {b}')


def ring_readable(page):
    import math
    desk = page.viewport_size['width'] >= 1024
    sizes = ((1920, 1080), (1280, 800), (1280, 860)) if desk else ((375, 812), (390, 844))
    scope = '.dv-main' if desk else '.p-overview'
    for theme in ('dark', 'light'):
        for w, hgt in sizes:
            page.set_viewport_size({'width': w, 'height': hgt})
            freeze(page, DAY)
            page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
            go_tab(page, 0)
            page.locator(scope + ' .bd').scroll_into_view_if_needed()
            page.wait_for_timeout(250)
            tag = f'{theme}/{w}x{hgt}'
            st = _ring_state(page, scope, tag)
            if desk:
                segs = page.evaluate(f"[...document.querySelectorAll('{scope} .bd-seg')].map(e=>+e.dataset.pct)")
                box = page.locator(scope + ' .bd-ring svg').bounding_box()
                acc = 0
                for k, pct in enumerate(segs):
                    a = -math.pi / 2 + 2 * math.pi * (acc + pct / 2) / 100
                    acc += pct
                    if pct < 3:
                        continue
                    rr = box['width'] / 2 * 0.85
                    page.mouse.move(box['x'] + box['width'] / 2 + rr * math.cos(a), box['y'] + box['height'] / 2 + rr * math.sin(a))
                    page.wait_for_timeout(120)
                    _tip_in_view(page, f'{tag} сегмент {k}')
                page.mouse.move(2, 2)
            rows = page.locator(scope + ' .bd-row')
            for k in range(rows.count()):
                rows.nth(k).focus()
                page.wait_for_timeout(60)
                _tip_in_view(page, f'{tag} рядок легенди {k}')
            page.evaluate('document.activeElement.blur()')
            if w in (1280, 375):
                from helpers import shot
                page.locator(scope + ' .bd').scroll_into_view_if_needed()
                shot(page, f'v148-ring-{theme}-{w}.jpg', full=False)
    print(f'      центр {st["out"]}, сегментів {len(st["segs"])}, мінімальний контраст легенди {min(c for _, _, c in st["leg"])}')


CHECKS = [
    ('v148: Розподіл бюджету: % / ₴ у рядку категорії', 'desktop', alloc_units),
    ('v148: Розподіл бюджету: % / ₴ у рядку категорії', 'mobile', alloc_units),
    ('v148: Розподіл бюджету: «Розблокувати всі» на телефоні', 'mobile', unlock_all_phone),
    ('v148: кільце бюджету на ПК: градієнт (v150), центр у колі, підказка у вʼюпорті, контраст легенди', 'desktop', ring_readable),
    ('v148: кільце бюджету на телефоні: градієнт (v150), центр у колі, підказка у вʼюпорті, контраст легенди', 'mobile', ring_readable),
]
