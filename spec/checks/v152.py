"""v152: «Гроші в часі» і кільце бюджету. v153 доповнення 6 (власник: «раніше було краще по дизайну і мені потрібен саме баланс,
я не хочу бачити лінію за власними грошима»): єдина лінія = баланс (власні мінус борг кредиток), може йти нижче нуля, вісь з мінусом,
заливка під нулем червона (як у v149); окремих ліній «Власні» і «Кредитні» немає; «мін.» у шапці = найменший баланс діапазону
(усі точки за підказкою) = маркер мінімуму на найнижчій точці лінії; прогноз підказки = баланс рушія на кінець дня; кожен діапазон."""
from datetime import date, timedelta
from helpers import check, freeze, go_tab

DAY = '2026-10-12'
MONO_DEBT = [("kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
              "kind:'credit',mono_account_id:'demo-mono',balance:12500,debt:30000,debt_month:'2026-10',credit_limit:30000")]

# стан осі й лінії: нуль, підписи (значення й y), y вершин лінії балансу (факт і прогноз), кліпи заливки (верх і низ прямокутника)
AXIS = r"""(()=>{const s=document.querySelector('.dv-fc .fc-svg');const z=s.querySelector('.fc-zero');const y0=z?+z.getAttribute('y1'):null;
const ticks=[...s.querySelectorAll('.fc-ax')].map(t=>({k:+t.dataset.k,t:t.textContent,y:+t.getAttribute('y')-3.5}));
const ends=d=>(d||'').trim().split(/(?=[MCL])/).filter(Boolean).map(p=>{const v=p.slice(1).trim().split(/[\s,]+/).map(Number);return v[v.length-1]});
const line=[...s.querySelectorAll('path.fc-past,path.fc-fut')].flatMap(p=>ends(p.getAttribute('d')));
const clips=[...s.querySelectorAll('.fc-area g[clip-path]')].map(g=>{const id=g.getAttribute('clip-path').replace(/^url\(#|\)$/g,'');const r=document.getElementById(id).querySelector('rect');return {top:+r.getAttribute('y'),bot:+r.getAttribute('y')+(+r.getAttribute('height'))}});
return {y0,ticks,line,clips,extra:s.querySelectorAll('.fc-debt,.fc-cross-crd').length,from:s.dataset.from,n:+s.dataset.n,past:+s.dataset.past,
 legend:[...document.querySelectorAll('.dv-fc .fc-leg>span')].map(e=>e.textContent),chips:[...document.querySelectorAll('.dv-fc .fc-chips button')].map(b=>b.dataset.r)}})()"""

# точка підказки: індекс, «Баланс», «Власні», «Кредитні» і y кружка перехрестя
TIP = r"""(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;const v=s=>{const e=b.querySelector(s+' .fc-tip-n');if(!e)return null;const t=e.textContent;return (/[−-]/.test(t)?-1:1)*+t.replace(/\D/g,'')};
const c=document.querySelector('.dv-fc .fc-cross circle');return {i:+b.dataset.i,k:b.dataset.k,bal:v('.fc-tip-bal'),own:v('.fc-tip-own'),crd:v('.fc-tip-crd'),cy:c?+c.getAttribute('cy'):null}})()"""

# маркер мінімуму: значення (data-v у копійках), cy і число з підпису «мін.»
MIN = r"""(()=>{const c=document.querySelector('.dv-fc .fc-svg .fc-min');if(!c)return null;
const t=document.querySelector('.dv-fc .fc-sum [data-k=min]').textContent.replace(/^мін\.\s*/,'').replace(/\s*\d{2}\.\d{2}$/,'');
return {v:+c.dataset.v/100,cy:+c.getAttribute('cy'),sum:(/^[−-]/.test(t)?-1:1)*+t.replace(/\D/g,''),label:t}})()"""

# еталон прогнозу: баланс рушія на кінець дня (netCents + balShift) до кінця діапазону, тим самим прогоном, що й графік
REF = r"""to=>{const r=financeProjection(window.__financeInput,Object.assign({},window.__financeOptions,{through:to}));const s=r.snapshot,sh=s.positiveOwnCents-s.cashCents;
const o={};r.days.forEach(d=>{o[d.date]=(d.netCents+sh)/100});return {bal:o,now:(s.positiveOwnCents-s.creditDebtCents)/100}}"""


def _val(ax, y):
    """значення в гривнях для y за двома підписами осі (лінійна шкала)"""
    a, b = ax['ticks'][0], ax['ticks'][-1]
    return a['k'] + (y - a['y']) * (b['k'] - a['k']) / (b['y'] - a['y'])


def _credit(page, label):
    if label == 'ПК':
        page.set_viewport_size({'width': 1440, 'height': 900})
    freeze(page, DAY, MONO_DEBT)
    go_tab(page, 0)
    page.wait_for_selector('.dv-fc .fc-svg')
    ax = page.evaluate(AXIS)
    check(ax['legend'] == ['Баланс', 'нижче нуля'], f'легенда графіка {ax["legend"]}, а не «Баланс», «нижче нуля»')
    for r in [c for c in ['m', 'm2', 'q', 'y'] if c in ax['chips']]:
        page.locator(f'.dv-fc .fc-chips button[data-r={r}]').click()
        page.wait_for_timeout(250)
        ax = page.evaluate(AXIS)
        y0 = ax['y0']
        check(y0 is not None, f'{r}: немає лінії нуля')
        check(ax['extra'] == 0, f'{r}: лишилась окрема лінія чи точка «Кредитні»')
        neg = [t for t in ax['ticks'] if t['k'] < 0]
        check(neg and all(t['t'].startswith('−') for t in neg), f'{r}: вісь без мінусових підписів {ax["ticks"]}')
        check(ax['line'] and max(ax['line']) > y0 + 1, f'{r}: лінія балансу не йде нижче нуля: max y {max(ax["line"] or [0])}, нуль {y0}')
        # заливка: зелена над нулем (кліп до y0), червона під нулем (кліп від y0)
        check(len(ax['clips']) == 2 and abs(ax['clips'][0]['bot'] - y0) <= 0.5 and abs(ax['clips'][1]['top'] - y0) <= 0.5,
              f'{r}: кліпи заливки {ax["clips"]}, нуль {y0}')
        # підказка по всіх точках діапазону: баланс = власні + кредитні; прогноз = баланс рушія; відʼємний баланс нижче нуля і на своїй висоті
        ref = page.evaluate(REF, (date.fromisoformat(ax['from']) + timedelta(days=ax['n'] - 1)).isoformat())
        page.locator('.dv-fc .fc-plot').focus()
        page.keyboard.press('Home')
        bals, fut, negs = [], 0, 0
        for _ in range(ax['n']):
            t = page.evaluate(TIP)
            check(t is not None and t['bal'] is not None, f'{r}: немає підказки з рядком «Баланс»')
            d = (date.fromisoformat(ax['from']) + timedelta(days=t['i'])).isoformat()
            bals.append(t['bal'])
            check(abs(t['own'] + t['crd'] - t['bal']) <= 1, f'{r} {d}: власні {t["own"]} + кредитні {t["crd"]} ≠ баланс {t["bal"]}')
            if t['k'] == 'f':
                fut += 1
                check(abs(t['bal'] - ref['bal'][d]) <= 1, f'{r} {d}: баланс підказки {t["bal"]}, а рушія {ref["bal"][d]:.2f}')
            if t['i'] == ax['past'] - 1:
                check(abs(t['bal'] - ref['now']) <= 1, f'{r}: сьогодні {t["bal"]}, а плитка «Баланс» {ref["now"]:.2f}')
            if t['bal'] < 0:
                negs += 1
                # строго нижче нуля (малий мінус дає частку пікселя), висота за шкалою осі нижче
                check(t['cy'] > y0 + 0.05, f'{r} {d}: баланс {t["bal"]} не нижче нуля: cy {t["cy"]}, нуль {y0}')
                v = _val(ax, t['cy'])
                check(abs(v - t['bal']) <= max(50, abs(t['bal']) * 0.01), f'{r} {d}: точка {v:.0f} ₴ не на висоті балансу {t["bal"]}')
            page.keyboard.press('ArrowRight')
        page.keyboard.press('Escape')
        check(len(bals) == ax['n'] and fut > 0 and negs > 0, f'{r}: точок {len(bals)} з {ax["n"]}, прогнозу {fut}, відʼємних {negs}: перевірка не показова')
        # «мін.» у шапці = найменший баланс діапазону = маркер на найнижчій точці лінії
        mn = page.evaluate(MIN)
        check(mn is not None, f'{r}: немає маркера мінімуму')
        check(abs(mn['sum'] - min(bals)) <= 1, f'{r}: «мін.» {mn["label"]}, а найменший баланс діапазону {min(bals)}')
        check(abs(mn['sum'] - mn['v']) <= 1, f'{r}: підпис «мін.» {mn["label"]} не дорівнює маркеру {mn["v"]}')
        check(abs(mn['cy'] - max(ax['line'])) <= 0.5, f'{r}: маркер мінімуму не на найнижчій точці лінії: cy {mn["cy"]}, лінія {max(ax["line"])}')
        mv = _val(ax, mn['cy'])
        check(abs(mv - mn['v']) <= max(50, abs(mn['v']) * 0.01), f'{r}: маркер мінімуму {mv:.0f} ₴ не на осі, значення {mn["v"]}')
        print(f'      {label} {r}: точок {len(bals)} (прогноз {fut}, мінус {negs}), мін. {mn["label"]} y={mn["cy"]:.1f}, нуль y={y0:.1f}, підписи {[t["t"] for t in ax["ticks"]]}')


def credit_desk(page):
    _credit(page, 'ПК')


def credit_mob(page):
    _credit(page, 'телефон')


# --- кільце бюджету (v152, власник: «ні по кольорах, ні по формі») ---
RING = r"""scope=>{const ring=document.querySelector(scope+' .bd-ring');if(!ring)return null;const svg=ring.querySelector('svg'),sz=+svg.getAttribute('width'),R=sz/2,r0=+ring.dataset.r0,ro=R-1;
const hue=c=>{const n=(c.match(/[\d.]+/g)||[]).map(Number);const [r,g,b]=n.slice(0,3).map(v=>v/255),mx=Math.max(r,g,b),d=mx-Math.min(r,g,b);if(d<0.15)return null;/* сірі «Інші» й «Без категорії» без тону */const h=mx===r?((g-b)/d)%6:mx===g?(b-r)/d+2:(r-g)/d+4;return (h*60+360)%360};
const segs=[...ring.querySelectorAll('.bd-seg')].map(e=>{const d=e.getAttribute('d');const nums=t=>t.trim().split(/[\s,]+/).map(Number);const cmds=d.match(/[MALZ][^MALZ]*/g);const pts=[],radii=[];
cmds.forEach(c=>{const v=nums(c.slice(1));if(c[0]==='M'||c[0]==='L')pts.push([v[0],v[1]]);if(c[0]==='A'){radii.push(v[0]);pts.push([v[5],v[6]])}});
/* v155: сегмент плаский, суцільна заливка кольором категорії (без linearGradient) */const fill=getComputedStyle(e).fill;
return {id:e.dataset.id,cmd:cmds.map(c=>c[0]).join(''),radii,pts,fill,flat:!/url\(/.test(fill),hues:[hue(fill)]}});
const sw=[...document.querySelectorAll(scope+' .bd-row')].map(r=>{const c=getComputedStyle(r.querySelector('.bd-sw'));return {id:r.dataset.id,bg:c.backgroundColor,bi:c.backgroundImage}});
const rgb=c=>'rgb('+[1,3,5].map(i=>parseInt(c.slice(i,i+2),16)).join(', ')+')';
const pal=BUD_PAL.map(p=>p.map(c=>hue(rgb(c))));
const dark=document.documentElement.getAttribute('data-theme')!=='light';
const lab=BUD_PAL.map(p=>p.map(hexLab));
return {R,r0,ro,segs,sw,pal,lab,dark,theme:BUD_PAL.map(p=>rgb(p[dark?1:0])).concat([BUD_OTH,BUD_NONE].map(p=>rgb(p[dark?1:0])))}}"""


def _dh(a, b):
    x = abs(a - b) % 360
    return min(x, 360 - x)


def _ring(page, scope, tag):
    import math
    st = page.evaluate(RING, scope)
    check(st and st['segs'], f'{tag}: кільця немає')
    R, r0, ro, segs = st['R'], st['r0'], st['ro'], st['segs']
    # палітра (v155, кольори Apple): світлий і темний варіант слота одного тону; замість «усі тони попарно ≥ 25°»:
    # усі пари Lab CIE76 ≥ 15 і пʼять головних слотів (5, 7, 2, 0, 3) попарно ≥ 30° за тоном, в обох темах
    for i, (a, b) in enumerate(st['pal']):
        check(_dh(a, b) <= 3, f'палітра: слот {i}, світлий і темний різних тонів {a:.0f}/{b:.0f}')
    N = len(st['pal'])
    for t in (0, 1):
        lw = min(math.dist(st['lab'][i][t], st['lab'][j][t]) for i in range(N) for j in range(i + 1, N))
        check(lw >= 15, f'палітра ({"темна" if t else "світла"}): два слоти ближче Lab 15 ({lw:.1f})')
        mw = min(_dh(st['pal'][i][t], st['pal'][j][t]) for i in (5, 7, 2, 0, 3) for j in (5, 7, 2, 0, 3) if i < j)
        check(mw >= 30, f'палітра ({"темна" if t else "світла"}): головні слоти ближче 30° ({mw:.1f})')
    # сегменти пласкі й кольору своєї теми
    for s in segs:
        check(s['flat'] and s['fill'] in st['theme'], f'{tag}: сегмент {s["id"]} не пласкої заливки кольором теми ({"темна" if st["dark"] else "світла"}): {s["fill"]}')
    n = len(segs)
    if n > 1:
        for s in segs:
            # плоскі кінці: лише дуги зовнішнього й внутрішнього кола, краї прямі (M A L A Z)
            check(s['cmd'] == 'MALAZ' and sorted(round(x, 1) for x in s['radii']) == sorted([round(r0, 1), round(ro, 1)]), f'{tag}: сегмент {s["id"]} не плоский: {s["cmd"]} {s["radii"]}')
            (o0, o1, i1, i0) = s['pts'][:4]
            check(math.dist(i0, i1) >= 2.9, f'{tag}: сегмент {s["id"]} коротший за мінімальну дугу: {math.dist(i0, i1):.2f} px')
        gaps = []
        for k in range(n):
            a, b = segs[k], segs[(k + 1) % n]
            go, gi = math.dist(a['pts'][1], b['pts'][0]), math.dist(a['pts'][2], b['pts'][3])
            gaps.append((round(go, 2), round(gi, 2)))
            # однаковий розрив 2-3 px і по зовнішньому, і по внутрішньому краю: без перекриттів
            check(2 <= go <= 3 and 2 <= gi <= 3, f'{tag}: розрив між {a["id"]} і {b["id"]}: зовні {go:.2f}, всередині {gi:.2f}')
            ha, hb = a['hues'][0], b['hues'][0]
            if ha is not None and hb is not None:
                check(_dh(ha, hb) >= 40, f'{tag}: сусіди {a["id"]} і {b["id"]} одного тону: {ha:.0f}° і {hb:.0f}°')
        print(f'      {tag}: сегментів {n}, розриви {sorted(set(gaps))}, сусідні тони {[round(_dh(segs[k]["hues"][0] or 0, segs[(k + 1) % n]["hues"][0] or 0)) for k in range(n)]}')
    # легенда: пласка мітка того самого кольору, що сегмент (v155: суцільний колір сегмента = колір мітки)
    sw = {x['id']: x for x in st['sw']}
    for s in segs:
        check(s['id'] in sw and sw[s['id']]['bi'] == 'none' and sw[s['id']]['bg'] == s['fill'], f'{tag}: мітка легенди {s["id"]} іншого кольору або з градієнтом: {sw.get(s["id"])} проти {s["fill"]}')


def ring_v152(page):
    desk = page.viewport_size['width'] >= 1024
    scope = '.dv-bud' if desk else '.p-overview'
    for theme in ('dark', 'light'):
        freeze(page, DAY)
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        go_tab(page, 0)
        page.locator(scope + ' .bd').scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        _ring(page, scope, f'{"ПК" if desk else "телефон"}/{theme}')


CHECKS = [
    ('v153: «Гроші в часі»: лінія балансу нижче нуля, мін. = найменший баланс, прогноз = рушій, усі діапазони (ПК)', 'desktop', credit_desk),
    ('v153: «Гроші в часі»: лінія балансу нижче нуля, мін. = найменший баланс, прогноз = рушій, усі діапазони (телефон)', 'mobile', credit_mob),
    ('v152: кільце бюджету: плоскі кінці, рівні розриви, сусіди різного тону, легенда тих самих кольорів (ПК)', 'desktop', ring_v152),
    ('v152: кільце бюджету: плоскі кінці, рівні розриви, сусіди різного тону, легенда тих самих кольорів (телефон)', 'mobile', ring_v152),
]
