"""v152: «Гроші в часі»: лінія «Кредитні» малюється відʼємними значеннями (борг униз від нуля), вісь Y охоплює мінус,
заливка власних не заходить під нуль; кожен діапазон (1 міс., 2 міс., 3 міс., Рік) і тултіп узгоджені з віссю."""
from helpers import check, freeze, go_tab

DAY = '2026-10-12'
MONO_DEBT = [("kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
              "kind:'credit',mono_account_id:'demo-mono',balance:12500,debt:30000,debt_month:'2026-10',credit_limit:30000")]

# стан осі й ліній: нуль, підписи (значення й y), y вершин лінії боргу, кліпи заливки власних
AXIS = r"""(()=>{const s=document.querySelector('.dv-fc .fc-svg');const z=s.querySelector('.fc-zero');const y0=z?+z.getAttribute('y1'):null;
const ticks=[...s.querySelectorAll('.fc-ax')].map(t=>({k:+t.dataset.k,t:t.textContent,y:+t.getAttribute('y')-3.5}));
const ends=d=>{const a=(d||'').trim().split(/(?=[MC])/);return a.map(p=>{const v=p.slice(1).trim().split(/[\s,]+/).map(Number);return v[v.length-1]})};
const debt=s.querySelector('.fc-debt');const clips=[...s.querySelectorAll('.fc-area g[clip-path]')].map(g=>{const id=g.getAttribute('clip-path').replace(/^url\(#|\)$/g,'');const r=document.getElementById(id).querySelector('rect');return +r.getAttribute('y')+(+r.getAttribute('height'))});
return {y0,ticks,debtY:debt?ends(debt.getAttribute('d')):[],clips,chips:[...document.querySelectorAll('.dv-fc .fc-chips button')].map(b=>b.dataset.r)}})()"""

# точка тултіпа: сума «Кредитні» з бокса і y кружка на лінії боргу
TIP = r"""(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;const e=b.querySelector('.fc-tip-crd .fc-tip-n');const t=e.textContent;const c=document.querySelector('.dv-fc .fc-cross-crd');
return {i:+b.dataset.i,crd:(/[−-]/.test(t)?-1:1)*+t.replace(/\D/g,''),cy:c?+c.getAttribute('cy'):null}})()"""


# маркер мінімуму власних: значення (data-v у копійках), cy, число з підпису «мін.» і найнижча точка лінії власних
# (вузли шляхів fc-past і fc-draw без fc-debt: монотонна крива проходить через точки ряду)
MIN = r"""(()=>{const s=document.querySelector('.dv-fc .fc-svg');const c=s.querySelector('.fc-min');if(!c)return null;
const t=document.querySelector('.dv-fc .fc-sum [data-k=min]').textContent.replace(/^мін\.\s*/,'').replace(/\s*\d{2}\.\d{2}$/,'');
const ends=d=>(d||'').trim().split(/(?=[MCL])/).map(p=>{const v=p.slice(1).trim().split(/[\s,]+/).map(Number);return v[v.length-1]});
const own=[...s.querySelectorAll('path.fc-past,path.fc-draw')].filter(p=>!p.classList.contains('fc-debt')).flatMap(p=>ends(p.getAttribute('d')));
return {v:+c.dataset.v/100,cy:+c.getAttribute('cy'),sum:(/^[−-]/.test(t)?-1:1)*+t.replace(/\D/g,''),label:t,ownLowY:own.length?Math.max(...own):null}})()"""

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
    chips = page.evaluate(AXIS)['chips']
    for r in [c for c in ['m', 'm2', 'q', 'y'] if c in chips]:
        page.locator(f'.dv-fc .fc-chips button[data-r={r}]').click()
        page.wait_for_timeout(250)
        ax = page.evaluate(AXIS)
        y0 = ax['y0']
        check(y0 is not None, f'{r}: немає лінії нуля')
        neg = [t for t in ax['ticks'] if t['k'] < 0]
        check(neg and all(t['t'].startswith('−') for t in neg), f'{r}: вісь без мінусових підписів {ax["ticks"]}')
        check(ax['debtY'] and max(ax['debtY']) > y0 + 1, f'{r}: лінія боргу не нижче нуля: max y {max(ax["debtY"] or [0])}, нуль {y0}')
        check(min(ax['debtY']) >= y0 - 0.5, f'{r}: лінія боргу вище нуля: min y {min(ax["debtY"])}, нуль {y0}')
        check(ax['clips'] and all(c <= y0 + 0.5 for c in ax['clips']), f'{r}: заливка власних під нулем, кліпи {ax["clips"]}, нуль {y0}')
        # маркер мінімуму: з ряду власних (не −борг), на висоті свого значення за шкалою осі, підпис «мін.» той самий
        mn = page.evaluate(MIN)
        check(mn is not None, f'{r}: немає маркера мінімуму')
        mv = _val(ax, mn['cy'])
        check(abs(mv - mn['v']) <= max(50, abs(mn['v']) * 0.01), f'{r}: маркер мінімуму {mv:.0f} ₴ не на осі, значення {mn["v"]}')
        check(mn['ownLowY'] is not None and abs(mn['cy'] - mn['ownLowY']) <= 0.5, f'{r}: маркер мінімуму не на найнижчій точці лінії власних: cy {mn["cy"]}, лінія {mn["ownLowY"]}')
        check(abs(mn['sum'] - mn['v']) <= 1, f'{r}: підпис «мін.» {mn["label"]} не дорівнює маркеру {mn["v"]}')
        # тултіп: перший день з боргом; кружок на лінії боргу нижче нуля і на висоті −борг за шкалою осі
        page.locator('.dv-fc .fc-plot').focus()
        page.keyboard.press('Home')
        tip, seen = None, 0
        for _ in range(400):
            t = page.evaluate(TIP)
            if t and t['crd'] < 0:
                tip = t
                break
            page.keyboard.press('ArrowRight')
            seen += 1
        check(tip is not None, f'{r}: немає дня з боргом за {seen} кроків')
        check(tip['cy'] is not None and tip['cy'] > y0 + 1, f'{r}: точка кредитної серії не нижче нуля: {tip}, нуль {y0}')
        v = _val(ax, tip['cy'])
        check(abs(v - tip['crd']) <= max(50, abs(tip['crd']) * 0.01), f'{r}: точка {v:.0f} ₴ не збігається з тултіпом {tip["crd"]} ₴')
        page.keyboard.press('Escape')
        print(f'      {label} {r}: мін. власних {mn["label"]} y={mn["cy"]:.1f} (за віссю {mv:.0f}); нуль y={y0:.1f}, борг y={tip["cy"]:.1f} ({tip["crd"]} ₴, за віссю {v:.0f}), підписи {[t["t"] for t in ax["ticks"]]}')


def credit_desk(page):
    _credit(page, 'ПК')


def credit_mob(page):
    _credit(page, 'телефон')


# --- кільце бюджету (v152, власник: «ні по кольорах, ні по формі») ---
RING = r"""scope=>{const ring=document.querySelector(scope+' .bd-ring');if(!ring)return null;const svg=ring.querySelector('svg'),sz=+svg.getAttribute('width'),R=sz/2,r0=+ring.dataset.r0,ro=R-1;
const hue=c=>{const n=(c.match(/[\d.]+/g)||[]).map(Number);const [r,g,b]=n.slice(0,3).map(v=>v/255),mx=Math.max(r,g,b),d=mx-Math.min(r,g,b);if(d<0.15)return null;/* сірі «Інші» й «Без категорії» без тону */const h=mx===r?((g-b)/d)%6:mx===g?(b-r)/d+2:(r-g)/d+4;return (h*60+360)%360};
const segs=[...ring.querySelectorAll('.bd-seg')].map(e=>{const d=e.getAttribute('d');const nums=t=>t.trim().split(/[\s,]+/).map(Number);const cmds=d.match(/[MALZ][^MALZ]*/g);const pts=[],radii=[];
cmds.forEach(c=>{const v=nums(c.slice(1));if(c[0]==='M'||c[0]==='L')pts.push([v[0],v[1]]);if(c[0]==='A'){radii.push(v[0]);pts.push([v[5],v[6]])}});
const id=(getComputedStyle(e).fill.match(/url\("?#([^")]+)"?\)/)||[])[1];const st=id?[...document.getElementById(id).querySelectorAll('stop')].map(x=>getComputedStyle(x).stopColor):[];
return {id:e.dataset.id,cmd:cmds.map(c=>c[0]).join(''),radii,pts,stops:st,hues:st.map(hue)}});
const sw=[...document.querySelectorAll(scope+' .bd-row')].map(r=>({id:r.dataset.id,bg:getComputedStyle(r.querySelector('.bd-sw')).backgroundImage}));
const pal=BUD_PAL.map(p=>p.map(c=>{const n=[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));return hue('rgb('+n.join(',')+')')}));
return {R,r0,ro,segs,sw,pal}}"""


def _dh(a, b):
    x = abs(a - b) % 360
    return min(x, 360 - x)


def _ring(page, scope, tag):
    import math
    st = page.evaluate(RING, scope)
    check(st and st['segs'], f'{tag}: кільця немає')
    R, r0, ro, segs = st['R'], st['r0'], st['ro'], st['segs']
    # палітра: тон однаковий у межах пари, різні тони попарно ≥ 25°
    for i, (a, b) in enumerate(st['pal']):
        check(_dh(a, b) <= 3, f'палітра: пара {i} градієнт поза тоном {a:.0f}/{b:.0f}')
    pw = min(_dh(st['pal'][i][0], st['pal'][j][0]) for i in range(len(st['pal'])) for j in range(i + 1, len(st['pal'])))
    check(pw >= 25, f'палітра: два тони ближче 25° ({pw:.1f})')
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
    # легенда бере ті самі кольори
    sw = {x['id']: x['bg'] for x in st['sw']}
    for s in segs:
        check(s['id'] in sw and all(c in sw[s['id']] for c in s['stops']), f'{tag}: легенда {s["id"]} іншого кольору: {sw.get(s["id"])} проти {s["stops"]}')


def ring_v152(page):
    desk = page.viewport_size['width'] >= 1024
    scope = '.dv-main' if desk else '.p-overview'
    for theme in ('dark', 'light'):
        freeze(page, DAY)
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        go_tab(page, 0)
        page.locator(scope + ' .bd').scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        _ring(page, scope, f'{"ПК" if desk else "телефон"}/{theme}')


CHECKS = [
    ('v152: «Гроші в часі»: лінія «Кредитні» нижче нуля, вісь з мінусом, усі діапазони (ПК)', 'desktop', credit_desk),
    ('v152: «Гроші в часі»: лінія «Кредитні» нижче нуля, вісь з мінусом, усі діапазони (телефон)', 'mobile', credit_mob),
    ('v152: кільце бюджету: плоскі кінці, рівні розриви, сусіди різного тону, легенда тих самих кольорів (ПК)', 'desktop', ring_v152),
    ('v152: кільце бюджету: плоскі кінці, рівні розриви, сусіди різного тону, легенда тих самих кольорів (телефон)', 'mobile', ring_v152),
]
