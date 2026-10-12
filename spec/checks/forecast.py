# «Гроші в часі» на Огляді (v145, рішення власника 12.10.2026): чипи діапазону, факт і прогноз, мітка «Сьогодні»,
# маркери виплат і мінімуму, перехрестя з боксом (миша, дотик, клавіатура), reduced-motion; календар із виплатами й дедлайном боргу
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta

from helpers import ROOT, check, finance_ref, finance_state, go_tab, num, shot

RANGES = {'m': (-7, 30), 'q': (-90, 90), 'y': (-180, 180), 'all': (None, 90)}
INFO = """(()=>{const s=document.querySelector('.dv-fc .fc-svg');const t=e=>e?e.textContent:null;return {from:s.dataset.from,to:s.dataset.to,n:+s.dataset.n,past:+s.dataset.past,
 pastD:(document.querySelector('.dv-fc .fc-past')||{getAttribute:()=>''}).getAttribute('d')||'',fut:!!document.querySelector('.dv-fc .fc-fut'),
 pressed:[...document.querySelectorAll('.dv-fc .fc-chips button[aria-pressed=true]')].map(b=>b.dataset.r),today:t(document.querySelector('.dv-fc .fc-today')),
 sum:t(document.querySelector('.dv-fc .fc-sum')),minV:+document.querySelector('.dv-fc .fc-min').dataset.v,pays:document.querySelectorAll('.dv-fc .fc-pay').length,
 circles:[...document.querySelectorAll('.dv-fc svg circle')].map(c=>c.getAttribute('class')).filter(c=>!/^fc-(pay|min|today-dot)$/.test(c||'')),
 first:(()=>{const fi=window.__financeInput,own=new Set(fi.accounts.filter(a=>a.active!==false&&a.kind!=='credit').map(a=>String(a.id)));
  const st=fi.accounts.filter(a=>!a.mono_account_id&&a.balance_updated_at).map(a=>Date.parse(a.balance_updated_at)).filter(Number.isFinite),stamp=st.length?Math.min(...st):null;
  return (fi.transactions||[]).filter(x=>x.account_id!=null?own.has(String(x.account_id)):stamp!=null&&x.source!=='mono'&&Date.parse(x.created_at)>stamp).map(x=>String(x.date).slice(0,10)).filter(d=>d.length===10).sort()[0]})()}})()"""
BOXES = """[...document.querySelectorAll('.dv-fc .fc-today,.dv-fc .fc-min-l,.dv-fc .fc-ax,.dv-fc .fc-xl')].map(e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom,e.getAttribute('class')+':'+e.textContent]})"""


def _iso(d):
    return d.isoformat()


def _money(c):
    return ('−' if c < 0 else '') + f'{round(abs(c) / 100):,}'.replace(',', ' ') + ' ₴'


def _no_overlap(page, tag):
    bb = page.evaluate(BOXES)
    for i in range(len(bb)):
        for j in range(i + 1, len(bb)):
            a, b = bb[i], bb[j]
            hit = a[0] < b[2] - 1 and b[0] < a[2] - 1 and a[1] < b[3] - 1 and b[1] < a[3] - 1
            check(not hit, f'{tag}: підписи графіка накладаються: {a[4]!r} і {b[4]!r}')


def _visible(first, t):
    """v146: чипи після обрізання лівої межі до першої операції на власних рахунках; дубль вужчого чипа прихований."""
    key = lambda r: (max(first, _iso(t + timedelta(days=RANGES[r][0]))) if RANGES[r][0] is not None else first, RANGES[r][1])
    out = []
    for r in RANGES:
        if all(key(q) != key(r) for q in out):
            out.append(r)
    return out


def _payouts_through(page, iso):
    """Дати виплат з еталона Python на тому самому вході, з горизонтом до iso (Рік: графік має власний довший прогін рушія)."""
    st = finance_state(page)
    opts = dict(st['options'] or {}, through=iso)
    out = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), '--finance'],
                         input=json.dumps([{'data': st['data'], 'options': opts}], ensure_ascii=False), cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8', timeout=30, check=True, env={**os.environ, 'PYTHONUTF8': '1'})
    return sorted({e['date'] for e in json.loads(out.stdout)[0]['events'] if e['kind'] == 'payout'})


def chart(page):
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    t = date.today()
    ref = finance_ref(page)
    snap = ref['snapshot']
    check(page.inner_text('.dv-fc .fc-title') == 'Гроші в часі', 'заголовок картки не «Гроші в часі»')
    check(page.locator('.dv-fc input[type=range]').count() == 0 and page.locator('.fc-readout,.fc-day').count() == 0, 'лишились повзунок або панель дня')
    chips = page.evaluate("[...document.querySelectorAll('.dv-fc .fc-chips button')].map(b=>[b.dataset.r,b.textContent])")
    info = page.evaluate(INFO)
    # v146: «Уся історія» видно, лише коли історія довша за «±3 міс.»
    names = {'m': 'Місяць', 'q': '±3 міс.', 'y': 'Рік', 'all': 'Уся історія'}
    vis = _visible(info['first'], t)
    check(chips == [[r, names[r]] for r in vis], f'чипи діапазону: {chips}, а не {vis}')
    check(info['pressed'] == ['q'], f'за замовчуванням не «±3 міс.»: {info["pressed"]}')
    # v148: крива в балансі (власні мінус борг кредиток), постійна мітка лише «Сьогодні: баланс»
    bal, shift = snap['positiveOwnCents'] - snap['creditDebtCents'], snap['positiveOwnCents'] - snap['cashCents']
    exp = 'Сьогодні: ' + _money(bal)
    check(info['today'] == exp, f'мітка сьогодні {info["today"]!r}, а не {exp!r}')
    payouts = sorted({e['date'] for e in ref['events'] if e['kind'] == 'payout'})
    for r in vis:
        lo, hi = RANGES[r]
        page.locator(f'.dv-fc .fc-chips button[data-r={r}]').click()
        page.wait_for_timeout(250)
        info = page.evaluate(INFO)
        check(info['pressed'] == [r], f'чип {r} не натиснутий: {info["pressed"]}')
        frm = info['first'] if lo is None else max(info['first'], _iso(t + timedelta(days=lo)))  # v146: не раніше першої операції
        check(info['from'] == frm and info['to'] == _iso(t + timedelta(days=hi)), f'{r}: діапазон {info["from"]}..{info["to"]}, а не {frm}..{_iso(t + timedelta(days=hi))}')
        past = (t - max(date.fromisoformat(frm), date.fromisoformat(info['first']))).days + 1
        check(info['past'] == past and info['n'] == past + hi, f'{r}: точок факту {info["past"]} з {info["n"]}, а не {past} з {past + hi}')
        check(info['pastD'].startswith('M') and info['fut'], f'{r}: немає суцільної лінії факту або пунктиру прогнозу')
        # маркери лише виплат і мінімуму
        check(not info['circles'], f'{r}: зайві маркери на графіку: {info["circles"]}')
        pays = [d for d in (payouts if info['to'] <= ref['days'][-1]['date'] else _payouts_through(page, info['to'])) if _iso(t) < d <= info['to']]
        check(info['pays'] == len(pays), f'{r}: маркерів виплат {info["pays"]}, а не {len(pays)}')
        # мінімум у підсумку = червона точка; не вище каси прогнозу в діапазоні
        mins = [d['netCents'] + shift for d in ref['days'] if _iso(t) < d['date'] <= info['to']] + [bal]  # v148: баланс, точка сьогодні = плитка «Баланс»
        check(info['minV'] <= min(mins), f'{r}: мінімум {info["minV"]} вище мінімуму прогнозу {min(mins)}')
        s = info['sum']
        check(re.match(r'^мін\. [−+][\d ]+ ₴ \d\d\.\d\d · макс\. [−+][\d ]+ ₴ \d\d\.\d\d · сьогодні −?[\d ]+ ₴', s), f'{r}: рядок підсумку {s!r}')
        check(round(num(s.split('·')[0]) * 100) == info['minV'], f'{r}: мінімум у підсумку {s!r} не дорівнює точці {info["minV"]}')
        _no_overlap(page, r)
    # найширший видимий чип: минуле від першої операції, кілька днів факту
    check(info['past'] >= 2, f'«{names[vis[-1]]}» без кривої минулого: {info["past"]} точок')
    # вибір памʼятається
    check(page.evaluate("localStorage.getItem('fc_range')") == vis[-1], 'вибір діапазону не збережено')
    page.reload()
    page.wait_for_selector('.dv-fc .fc-svg')
    check(page.evaluate(INFO)['pressed'] == [vis[-1]], 'після перезавантаження діапазон не відновлено')
    page.locator('.dv-fc .fc-chips button[data-r=q]').click()
    page.wait_for_timeout(200)
    # погашення кредитки: подія в боксі дня на плановій даті (клавіатура від сьогодні)
    rep = next((e for e in ref['events'] if e['kind'] == 'repay' and e['date'] > _iso(t)), None)
    if rep:
        page.locator('.dv-fc .fc-plot').focus()
        page.keyboard.press('ArrowRight')
        for _ in range((date.fromisoformat(rep['date']) - t).days - 1):
            page.keyboard.press('ArrowRight')
        box = page.inner_text('.dv-fc .fc-box')
        check('Погашення кредитки' in box and 'прогноз' in box, f'бокс дня {rep["date"]} без погашення: {box!r}')
        page.keyboard.press('Escape')
    # «Найближче»: майбутні не приглушені, із строком
    rows = page.evaluate("[...document.querySelectorAll('.dv-near .dv-ev')].map(e=>({t:e.innerText,f:e.classList.contains('future'),o:getComputedStyle(e).opacity}))")
    want = 5 if page.viewport_size['width'] < 1400 or page.viewport_size['height'] < 860 else 8  # compactNear: 5, інакше 8
    check(len(rows) == want, f'у «Найближче» {len(rows)} подій, а не {want}')
    check('Щоденні витрати' not in page.inner_text('.dv-near'), 'у «Найближче» лишився рядок «Щоденні витрати, прогноз» (v148: прибрано)')
    for r in rows:
        fut = 'через' in r['t']
        check(fut == r['f'], f'клас .future не відповідає даті: {r}')
        if fut:
            check(float(r['o']) == 1, f'майбутня подія нечитабельна: opacity {r["o"]}')


def calendar(page):
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits')
    check(cal.locator('.cal-badge', has_text='А').count() == 1 and cal.locator('.cal-badge', has_text='З').count() == 1,
          'у сітці місяця немає бейджів виплат А і З')
    t = date.today()
    projection = finance_ref(page)
    for e in projection['events']:
        if e['kind'] == 'repay' and e['date'][:7] == t.isoformat()[:7]:
            check(page.locator('.cal-tbl .cal-ev[data-date="' + e['date'] + '"]', has_text='Погашення кредитки').count() >= 1, 'погашення відсутнє на плановій даті')
    evs = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev')].map(e=>({d:e.dataset.date,p:e.classList.contains('past'),td:e.classList.contains('today'),b:e.dataset.bal}))")
    check(evs, 'у календарі немає таблиці подій')
    iso = t.isoformat()
    for e in evs:
        check(e['p'] == (e['d'] < iso) and e['td'] == (e['d'] == iso), f'подія календаря: минуле/сьогодні не відповідає даті: {e}')
        check(e['b'] is None or e['d'] >= iso, f'баланс після в минулому рядку: {e}')
    if t.day < 28:
        check(cal.locator('.cal-cell.future').count() > 0, 'майбутні дні в сітці не приглушені')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg', full=False)


def hover(page):
    """Перехрестя: миша показує бокс «факт» у минулому і «прогноз» у майбутньому, без затримки; ←/→ на фокусі міняють день і не перемикають період; Escape ховає"""
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    svg = page.locator('.dv-fc .fc-svg')
    b = svg.bounding_box()
    y = b['y'] + b['height'] / 2
    left = float(page.evaluate("(()=>{const l=document.querySelector('.dv-fc .fc-grid,.dv-fc .fc-zero');return l.x1.baseVal.value})()"))
    now_x = float(page.evaluate("document.querySelector('.dv-fc .fc-now').x1.baseVal.value"))
    page.mouse.move(b['x'] + (left + now_x) / 2, y)
    page.wait_for_timeout(60)
    box = page.locator('.dv-fc .fc-box')
    check(box.count() == 1 and page.locator('.dv-fc .fc-cross').count() == 1, 'наведення не показало перехрестя з боксом')
    tt = box.inner_text()
    split = lambda s: 'Баланс ' in s and 'Власні ' in s and 'Кредитні ' in s  # v148: баланс, власні й кредитні лише в підказці
    check(re.search(r'^(Пн|Вт|Ср|Чт|Пт|Сб|Нд) \d\d\.\d\d', tt) and split(tt) and 'факт' in tt, f'бокс минулого дня: {tt!r}')
    page.mouse.move(b['x'] + b['width'] - 20, y)
    page.wait_for_timeout(60)
    tt = box.inner_text()
    check('прогноз' in tt and split(tt), f'бокс майбутнього дня: {tt!r}')
    shot(page, 'ov-hover-1920.jpg', full=False)
    page.mouse.move(2, 2)
    page.wait_for_timeout(60)
    check(box.count() == 0, 'бокс не сховався, коли миша пішла')
    p0 = page.inner_text('.dtitle')
    page.locator('.dv-fc .fc-plot').focus()
    page.keyboard.press('ArrowRight')
    page.wait_for_timeout(60)
    check('прогноз' in box.inner_text(), '→ від сьогодні не дав день прогнозу')
    page.keyboard.press('ArrowLeft')
    page.keyboard.press('ArrowLeft')
    page.wait_for_timeout(60)
    check(box.get_attribute('data-k') == 'p' and 'факт' in box.inner_text() and 'сьогодні' not in box.inner_text(), f'← не повернув у минуле: {box.inner_text()!r}')
    check(page.inner_text('.dtitle') == p0, 'стрілки на графіку перемкнули період')
    page.keyboard.press('Escape')
    page.wait_for_timeout(60)
    check(box.count() == 0, 'Escape не сховав бокс')


def touch(page):
    """Телефон: дотик і протягування пальцем ведуть перехрестя, вертикальна прокрутка лишається (touch-action pan-y); без горизонтальної прокрутки"""
    plot = page.locator('.dv-fc .fc-svg')
    plot.scroll_into_view_if_needed()
    check(page.evaluate("getComputedStyle(document.querySelector('.dv-fc .fc-svg')).touchAction") == 'pan-y', 'графік без touch-action pan-y')
    b = plot.bounding_box()
    y = b['y'] + b['height'] / 2
    for k, ev in enumerate(('pointerdown', 'pointermove', 'pointermove')):
        plot.dispatch_event(ev, {'pointerType': 'touch', 'clientX': b['x'] + b['width'] * (0.3 + 0.25 * k), 'clientY': y, 'bubbles': True, 'isPrimary': True})
        page.wait_for_timeout(60)
        if k == 0:
            i0 = page.get_attribute('.dv-fc .fc-box', 'data-i')
    i1 = page.get_attribute('.dv-fc .fc-box', 'data-i')
    check(i0 is not None and i1 is not None and int(i1) > int(i0), f'протягування не пересунуло перехрестя: {i0} -> {i1}')
    plot.dispatch_event('pointerout', {'pointerType': 'touch', 'bubbles': True})  # React синтезує onPointerLeave з pointerout
    page.wait_for_timeout(60)
    check(page.locator('.dv-fc .fc-box').count() == 1, 'бокс зник одразу після дотику')
    page.mouse.click(5, 5)
    page.wait_for_timeout(60)
    check(page.locator('.dv-fc .fc-box').count() == 0, 'дотик поза графіком не сховав бокс')
    sw = page.evaluate('[document.scrollingElement.scrollWidth,innerWidth]')
    check(sw[0] <= sw[1], f'горизонтальна прокрутка на телефоні: {sw}')
    r = page.locator('.dv-fc').bounding_box()
    c = page.locator('.dv-fc .fc-chips').bounding_box()
    check(c['x'] + c['width'] <= r['x'] + r['width'] + 0.5, 'чипи виходять за картку')


def reduced(page):
    """prefers-reduced-motion: лінія одразу намальована, заливка видима, кільце бюджету без анімації; без reduce лінія малюється"""
    st = "(()=>{const p=getComputedStyle(document.querySelector('.dv-fc .fc-past'));const a=getComputedStyle(document.querySelector('.dv-fc .fc-area'));const s=document.querySelector('.bd-seg');return [p.animationName,p.strokeDashoffset,a.animationName,a.opacity,s?getComputedStyle(s).animationName:'none']})()"
    v = page.evaluate(st)
    check(v[0] == 'fc-draw' and v[2] == 'fc-fade', f'без reduce лінія не малюється: {v}')
    page.emulate_media(reduced_motion='reduce')
    page.locator('.dv-fc .fc-chips button[data-r=m]').click()
    page.wait_for_timeout(100)
    v = page.evaluate(st)
    check(v[0] == 'none' and v[1] in ('0', '0px') and v[2] == 'none' and v[3] == '1' and v[4] == 'none', f'reduced-motion: {v}')


CHECKS = [
    ('Гроші в часі: чипи, факт і прогноз, мітка сьогодні, маркери, без накладань', 'desktop', chart),
    ('Гроші в часі: перехрестя миша і клавіатура', 'desktop', hover),
    ('Гроші в часі: дотик і протягування на телефоні', 'mobile', touch),
    ('Гроші в часі: reduced-motion', 'desktop', reduced),
    ('Календар: А/З, планова дата погашення, майбутнє', 'desktop', calendar),
]
