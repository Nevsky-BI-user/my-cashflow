# Кільце бюджету з багатьма категоріями: видима легенда, графік не нижче 240px,
# без внутрішньої прокрутки колонок; якщо не вміщається й так, Огляд прокручується сторінкою (клас ov-scroll), нічого не прибрано.
from helpers import check, finance_ref, freeze, go_tab, num

DAY = '2026-10-12'
# демо: ще вісім категорій витрат (дні 25-31 стискаються в 10-12 жовтня, тобто в поточний період), кожна понад 3% факту, тож у кільці окремі сегменти, а не «Інші»
MANY = [("const TX_DEMO_ROWS=[", "const TX_DEMO_ROWS=[" + ",".join(
    f"[{d},'Тест {c}',{a},'out','manual',null,'{c}']" for d, c, a in (
        (25, 'cafe', 900), (26, 'auto', 1400), (27, 'child', 1100), (28, 'health', 800),
        (29, 'clothes', 1300), (30, 'home', 1000), (31, 'fun', 700), (31, 'gifts', 1200))) + ",")]

STATE = """(()=>{const q=s=>document.querySelector(s);const leg=q('.dv-bud .bd-desk .bd-leg');const cols=leg?getComputedStyle(leg).gridTemplateColumns.split(' ').length:0;
const inner=[...document.querySelectorAll('.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')].filter(e=>e.offsetParent).map(e=>e.scrollHeight-e.clientHeight);
return {cols,rows:document.querySelectorAll('.dv-bud .bd-row').length,inner,svg:Math.round(q('.dv-fc svg').getBoundingClientRect().height),
clipped:[...document.querySelectorAll('.dv-bud .bd-row')].filter(e=>{const r=e.getBoundingClientRect(),p=q('.dv-bud').getBoundingClientRect();return r.width<=0||getComputedStyle(e).visibility==='hidden'||r.bottom>p.bottom+1||[...e.querySelectorAll('.bd-sum,.bd-pct')].some(n=>n.scrollWidth>n.clientWidth+1)}).map(e=>e.textContent),doc:document.documentElement.scrollHeight,vh:innerHeight,scroll:q('.p-overview').classList.contains('ov-scroll')}})()"""


def _check(page, tag, many):
    st = page.evaluate(STATE)
    check(st['cols'] >= 1, f'{tag}: легенда в {st["cols"]} колонку {st}')
    check(len(st['inner']) >= 5 and not st['clipped'], f'{tag}: missing cards or clipped budget legend {st}')
    check(all(v <= 2 for v in st['inner']), f'{tag}: внутрішня прокрутка колонок {st}')
    check(st['svg'] >= (160 if st['vh'] < 900 else 180 if st['vh'] < 1000 else 260), f'{tag}: графік нижчий за адаптивний мінімум {st}')
    if st['doc'] > st['vh'] + 1:
        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
        page.wait_for_timeout(150)
        b = page.evaluate("Math.round(document.querySelector('.dv-bud').getBoundingClientRect().bottom)")
        check(b <= st['vh'], f'{tag}: картка бюджету недосяжна прокруткою сторінки: низ {b}, екран {st["vh"]}')
        page.evaluate('window.scrollTo(0, 0)')
    else:
        # Клас може лишитися після зміни ширини; фактичний розмір сторінки вже перевірено вище.
        check(st['doc'] <= st['vh'] + 1, f'{tag}: сторінка виходить за екран {st}')
    if many:
        check(st['rows'] >= 9, f'{tag}: у легенді лише {st["rows"]} рядків, категорії не всі')
    return st


def ring_many(page):
    out = []
    for many in (False, True):
        freeze(page, DAY, MANY if many else None)
        go_tab(page, 0)
        for w, hgt in ((1920, 1080), (1440, 900), (1280, 860), (1280, 800)):
            page.set_viewport_size({'width': w, 'height': hgt})
            page.wait_for_timeout(350)
            st = _check(page, f'{"багато" if many else "звичайно"}/{w}x{hgt}', many)
            out.append(f'{w}x{hgt}:{st["cols"]}к,{"гортання" if st["doc"] > st["vh"] + 1 else "вміщ."}')
    # звичайний день на 1280x860 (після зміни розмірів вікна) вміщається без прокрутки сторінки
    check(any(o.startswith('1280x860') and 'вміщ.' in o for o in out[:4]), f'звичайний день на 1280x860 не вміщається: {out[:4]}')
    print('      ' + ' '.join(out))


KPI = """(()=>{const tiles=[...document.querySelectorAll('.dv-kpis>.kpi-t,.projection-summary>.kpi-t')].filter(e=>e.offsetParent);
return tiles.map(t=>{const r=t.getBoundingClientRect(),hd=t.querySelector('.kpi-head').getBoundingClientRect(),v=t.querySelector('.dv-kpi-v').getBoundingClientRect();
return {k:t.dataset.k||t.className,top:Math.round(r.top),h:Math.round(r.height),head:Math.round(hd.top-r.top),hb:Math.round(hd.bottom-r.top),val:Math.round(v.top-r.top)}})})()"""


def kpi_plan(page):
    """п. 4: плитки KPI в одному ряду однакової висоти, вміст угорі; v151 (знахідка 2): «За планом» у «Доступні кошти» = бюджет
    періоду з наступної виплати за правилом рушія: A = nextPlan.baseAvailableCents, бюджет min(20 000, A), якщо A > 15 000, інакше 15 000;
    розклад у підказці «i»."""
    freeze(page, DAY)
    go_tab(page, 0)
    ref = finance_ref(page)
    n = ref['nextPlan']
    a = n['baseAvailableCents']
    plan = min(2000000, a) if a > 1500000 else 1500000
    check(n['targetCents'] == plan, f'ціль наступного періоду {n["targetCents"]} не за правилом від A {a}')
    v = num(page.inner_text('.kpi-funds [data-r=plan] .kpi-rv'))
    check(abs(v - plan / 100) <= 1, f'«За планом» {v}, а за рушієм {plan / 100}')
    page.locator('.kpi-funds .kpi-i').click()
    page.wait_for_selector('.kpi-tip[data-k=funds]')
    tip = page.inner_text('.kpi-tip[data-k=funds]')
    check('За планом: бюджет періоду' in tip and '= A ' in tip and 'інакше 15 000' in tip, f'у підказці немає розкладу «За планом»: {tip!r}')
    page.keyboard.press('Escape')
    rows = {}
    for t in page.evaluate(KPI):
        rows.setdefault(t['top'], []).append(t)
    for top, ts in rows.items():
        hs = {t['h'] for t in ts}
        check(len(ts) < 2 or max(hs) - min(hs) <= 1, f'плитки ряду {top} різної висоти {ts}')
        # вміст угорі: шапка біля верхнього краю, число одразу під шапкою (на телефоні довгий підпис може перенестися в два рядки)
        check(all(t['head'] <= 14 and 0 <= t['val'] - t['hb'] <= 10 for t in ts), f'вміст плиток не вгорі {ts}')
    print(f'      «За планом» {v} ₴ = правило від A {a} (коп.); рядів плиток {len(rows)}')


NEAR = r"""(()=>{const desk=!!document.querySelector('.dv-near');const rows=[...document.querySelectorAll(desk?'.dv-near .dv-ev':'.o-next .o-next-row')];
return rows.map((r,i)=>{const n=r.children[0],m=r.children[1],a=r.lastElementChild;if(i===0)n.textContent='Дуже довга назва постійного платежу, яка не вміщається в один рядок і має переноситися повністю';
const cs=getComputedStyle(n),nb=n.getBoundingClientRect(),mb=m.getBoundingClientRect(),ab=a.getBoundingClientRect(),rb=r.getBoundingClientRect(),lh=parseFloat(cs.lineHeight)||16;
return {i,meta:m.innerText,amt:a.innerText,ell:cs.textOverflow==='ellipsis'||cs.whiteSpace==='nowrap',cut:n.scrollWidth>n.clientWidth+1,lines:Math.round(nb.height/lh),
amtTop:Math.round(ab.top-nb.top),amtRight:Math.round(rb.right-ab.right),metaBelow:Math.round(mb.top-nb.bottom),metaSz:parseFloat(getComputedStyle(m).fontSize),nameSz:parseFloat(cs.fontSize),h:Math.round(rb.height)}})})()"""


def near_rows(page):
    """п. 6: «Найближче» у два рядки: повна назва з переносом (без «…»), сума праворуч у першому рядку; нижче дрібніше: дата · через N дн. · джерело."""
    import re
    freeze(page, DAY)
    go_tab(page, 0)
    rows = page.evaluate(NEAR)
    check(len(rows) >= 3, f'у «Найближче» {len(rows)} рядків')
    for r in rows:
        check(not r['ell'] and not r['cut'], f'назва обрізана або в один рядок: {r}')
        check(re.match(r'^\d\d\.\d\d · (сьогодні|через \d+ дн\.)( · з (картки|кредитки))?$', r['meta'].strip()), f'другий рядок не «дата · строк · джерело»: {r["meta"]!r}')
        check(abs(r['amtTop']) <= 4 and r['amtRight'] <= 1, f'сума не праворуч у першому рядку: {r}')
        check(r['metaBelow'] >= -1 and r['metaSz'] < r['nameSz'], f'другий рядок не нижче або не дрібніший: {r}')
        check(r['h'] >= 38, f'рядок затісний: {r}')
    check(rows[0]['lines'] >= 2, f'довга назва не перенеслася: {rows[0]}')
    print('      ' + ' | '.join(r['meta'] + ' ' + r['amt'] for r in rows[1:4]))


TIP = """(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;const rb=b.getBoundingClientRect();
const n=s=>{const t=s.replace(/[\\s\\u00a0\\u202f]/g,'');const m=t.match(/\\d+/g);return m?m.length:0};
const rows=[...b.querySelectorAll('.fc-tip-r')].map(r=>{const v=r.querySelector('.fc-tip-n'),l=r.querySelector('.fc-tip-l'),vr=v.getBoundingClientRect(),lr=l.getBoundingClientRect();
 return {c:r.className,l:l.textContent,v:v.textContent,nums:n(v.textContent),right:vr.right,vt:vr.top,lt:lr.top,vh:vr.height,lh:parseFloat(getComputedStyle(v).lineHeight)||vr.height,d:r.dataset.d!=null?+r.dataset.d:null}});
return {k:b.dataset.k,i:+b.dataset.i,w:rb.width,l:rb.left,r:rb.right,vw:innerWidth,rows,
 own:(()=>{const e=b.querySelector('.fc-tip-own .fc-tip-n');if(!e)return null;const t=e.textContent;return (/[\u2212-]/.test(t)?-1:1)*+t.replace(/\\D/g,'')})()}})()"""


def tooltip(page):
    """v149 (власник: «цифри та підписи розʼїхалися»): тултіп графіка сіткою, у кожного рядка одне число, праві краї чисел збігаються (±1 px),
    ширина від 200 px і в межах екрана.
    v150 (модель «власні ≥ 0»): перші рядки Власні, Кредитні, Баланс; на днях прогнозу власні(d-1) + сума подій(d) = власні(d): погашення кредитки
    зменшує власні, частина в кредит і нестача сірими рядками з нулем; власні не мінус"""
    if page.viewport_size['width'] >= 1024:
        page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    go_tab(page, 0)
    page.wait_for_selector('.dv-fc .fc-svg')
    page.locator('.dv-fc .fc-plot').focus()
    prev, seen, chain, var_rows, rp_rows = None, 0, 0, 0, 0
    for step in range(40):
        page.keyboard.press('ArrowRight')
        page.wait_for_timeout(40)
        t = page.evaluate(TIP)
        check(t, f'крок {step}: тултіп не показано')
        rows = t['rows']
        check(t['w'] >= 199.5 and t['l'] >= -0.5 and t['r'] <= t['vw'] + 0.5, f'день {t["i"]}: ширина {t["w"]:.0f} або виходить за екран {t["l"]:.0f}..{t["r"]:.0f} з {t["vw"]}')
        check(all(r['nums'] == 1 for r in rows), f'день {t["i"]}: рядки не з одним числом {[(r["l"], r["v"]) for r in rows if r["nums"] != 1]}')
        rs = [r['right'] for r in rows]
        check(max(rs) - min(rs) <= 1, f'день {t["i"]}: праві краї чисел розходяться {min(rs):.1f}..{max(rs):.1f}')
        check(all(r['vh'] <= r['lh'] * 1.5 for r in rows), f'день {t["i"]}: число переноситься {[(r["v"], r["vh"]) for r in rows if r["vh"] > r["lh"] * 1.5]}')
        check(all(abs(r['vt'] - r['lt']) <= 2 for r in rows), f'день {t["i"]}: число не в рядку свого підпису')
        cls = [r['c'] for r in rows[:3]]
        check(all(s in c for s, c in zip(('fc-tip-own', 'fc-tip-crd', 'fc-tip-bal'), cls)), f'день {t["i"]}: перші рядки не Власні, Кредитні, Баланс: {cls}')
        check(t['own'] is not None and t['own'] >= 0, f'день {t["i"]}: власні мінус {t["own"]}')
        ev = rows[3:]
        nv = sum(r['l'] in ('Щоденні витрати', 'Щоденні витрати · у кредит') for r in ev)
        check(sum(r['l'] == 'Щоденні витрати' for r in ev) <= 1, f'день {t["i"]}: кілька рядків «Щоденні витрати»')
        var_rows += nv
        rp_rows += sum('fc-tip-rp' in r['c'] for r in ev)
        if t['k'] == 'f' and prev is not None and prev['k'] == 'f':
            s = sum(r['d'] for r in ev if r['d'] is not None)
            check(abs(prev['own'] + s / 100 - t['own']) <= 1.01, f'день {t["i"]}: власні {prev["own"]} + події {s / 100} != {t["own"]}: {[(r["l"], r["v"], r["d"]) for r in ev]}')
            chain += 1
        prev = t
        seen += 1
    print(f'      днів {seen}, перевірено ланцюжком власних {chain}, рядків «Щоденні витрати» {var_rows}, погашень {rp_rows}')
    check(chain >= 20, f'ланцюжок власних перевірено лише на {chain} днях')
    check(var_rows >= 10, f'рядок «Щоденні витрати» лише в {var_rows} днях прогнозу')
    page.keyboard.press('Escape')


def period_follow(page):
    """v149 (власник: «чому вгорі грудень, а на календарі жовтень?»): Календар іде за періодом шапки; стрілки календаря міняють період шапки;
    дні періоду підсвічені; для не поточного періоду плитка «Обовʼязкові за період»"""
    page.set_viewport_size({'width': 1600, 'height': 900})
    freeze(page, DAY)
    go_tab(page, 3)
    page.wait_for_selector('.ck-month')
    check(page.inner_text('.ck-month').startswith('Жовтень 2026'), f'календар не на жовтні: {page.inner_text(".ck-month")!r}')
    for _ in range(12):
        if 'гру' in page.text_content('.side-pname').lower() and 'лис' not in page.text_content('.side-pname').lower():
            break
        page.locator('button[aria-label="Наступний період"]:visible').first.click()
        page.wait_for_timeout(120)
    pn = page.text_content('.side-pname')
    check('гру' in pn.lower(), f'шапку не перемкнуто на грудень: {pn!r}')
    check(page.inner_text('.ck-month').startswith('Грудень 2026'), f'вгорі {pn!r}, а календар {page.inner_text(".ck-month")!r}')
    check('Обовʼязкові за період' in page.text_content('.p-credits'), 'для не поточного періоду немає плитки «Обовʼязкові за період»')
    inper = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell.inper')].map(c=>(c.querySelector('.cal-dn')||c.firstChild).textContent.trim())")
    print(f'      шапка {pn!r}, дні періоду в сітці: {inper}')
    check(len(inper) >= 10, f'дні періоду не підсвічені: {inper}')
    page.locator('.ck-arr[aria-label="Попередній місяць"]').click()
    page.wait_for_timeout(150)
    check(page.inner_text('.ck-month').startswith('Листопад 2026') and 'лис' in page.text_content('.side-pname').lower(),
          f'стрілка календаря не змінила період шапки: {page.text_content(".side-pname")!r}, {page.inner_text(".ck-month")!r}')


def pay_balance_mobile(page):
    """v149 (власник: «чому на мобільному я не бачу балансу в платежах»): телефон 375x812, «Платежі»: «Баланс сьогодні» = плитка «Баланс» Огляду,
    у рядках подій баланс після, у клітинках від сьогодні баланс на кінець дня; без горизонтальної прокрутки"""
    page.set_viewport_size({'width': 375, 'height': 812})
    freeze(page, DAY)
    go_tab(page, 0)
    tile = num(page.locator('.kpi-balance .dv-kpi-v').inner_text())
    go_tab(page, 3)
    page.wait_for_selector('.ck-bal')
    kb = page.locator('.ck-bal').text_content()
    check('Баланс сьогодні' in kb, f'немає плитки «Баланс сьогодні»: {kb!r}')
    val = num(kb.split('Баланс сьогодні', 1)[1])
    print(f'      Огляд «Баланс» {tile}, Платежі «Баланс сьогодні» {val}')
    check(abs(val - tile) <= 1, f'«Баланс сьогодні» {val} не дорівнює плитці Огляду {tile}')
    rows = page.evaluate("""[...document.querySelectorAll('.cm-event')].map(e=>{const a=e.querySelector('.cm-amt-col'),n=e.querySelector('.cm-name'),b=e.querySelector('.cm-bal');
      const ar=a.getBoundingClientRect(),nr=n.getBoundingClientRect();return {bal:e.dataset.bal,t:b?b.textContent:null,ov:nr.right>ar.left+0.5}})""")
    withb = [r for r in rows if r['bal'] is not None]
    check(len(withb) >= 3 and all(r['t'] and r['t'].startswith('баланс ') for r in withb), f'у рядках подій немає балансу після: {rows[:6]}')
    check(not any(r['ov'] for r in rows), 'назва події налазить на суму')
    cells = page.evaluate("document.querySelectorAll('.cm-calendar .cal-cell .cal-bal').length")
    check(cells >= 15, f'у клітинках телефона баланс лише в {cells} днях')
    sw = page.evaluate('document.scrollingElement.scrollWidth')
    check(sw <= 375, f'горизонтальна прокрутка: {sw}')


FLOW_POS = """(()=>{const t=document.querySelector('.p-flow .flow-day.today,.p-flow .flow-day-m.today');if(!t)return null;const h=document.querySelector('.p-flow .flow-head')||document.querySelector('.header');
return {t:t.getBoundingClientRect().top,h:h.getBoundingClientRect().bottom}})()"""


def flow_today(page):
    """v149 (власник): «Операції» відкриваються на «Сьогодні» під липкою шапкою: після холодного старту і після перемикання вкладки;
    мета-рядок операції переноситься, дата коротко (ДД.ММ); на телефоні остання сума прокручується вище «+»"""
    mob = page.viewport_size['width'] < 1024
    page.set_viewport_size({'width': 375, 'height': 812} if mob else {'width': 1280, 'height': 860})
    freeze(page, DAY)
    for k in ('холодний старт', 'після перемикання'):
        go_tab(page, 2)
        page.wait_for_timeout(900)
        p = page.evaluate(FLOW_POS)
        print(f'      {k}: «Сьогодні» {p}')
        check(p and 0 <= p['t'] - p['h'] <= 12, f'{k}: «Сьогодні» не під шапкою: {p}')
        go_tab(page, 0)
        page.wait_for_timeout(300)
    go_tab(page, 2)
    page.wait_for_timeout(900)
    meta = page.evaluate("""[...document.querySelectorAll('.p-flow .row-meta')].map(e=>({t:e.textContent,o:e.scrollWidth>e.clientWidth+1,l:Math.round(e.getBoundingClientRect().height/(parseFloat(getComputedStyle(e).lineHeight)||12))}))""")
    check((meta or not mob) and not any(m['o'] for m in meta), f'мета-рядок обрізано або його немає: {[m["t"] for m in meta if m["o"]]}')
    check(not any('жовт' in m['t'] or 'листоп' in m['t'] for m in meta), f'у мета-рядку лишилась назва місяця: {[m["t"] for m in meta][:4]}')
    if mob:
        page.evaluate('window.scrollTo(0, document.scrollingElement.scrollHeight)')
        page.wait_for_timeout(200)
        r = page.evaluate("""(()=>{const f=document.querySelector('.fab').getBoundingClientRect();const a=[...document.querySelectorAll('.p-flow .m-day')].pop().querySelectorAll('[style*="text-align: right"]');const b=a[a.length-1].getBoundingClientRect();
          return {fab:f.top,amt:b.bottom,sw:document.scrollingElement.scrollWidth}})()""")
        check(r['amt'] <= r['fab'] - 4, f'остання сума під кнопкою «+»: {r}')
        check(r['sw'] <= 375, f'горизонтальна прокрутка: {r}')


def no_gear(page):
    """v149 (власник: «чому не прибрав шестерню вгорі»): шестерні немає ні в коді, ні на сторінці; на телефоні шоста вкладка «Налаштування»
    відкриває сторінку (не діалог), нижня панель без переповнення і обрізаних підписів на 375; на ПК пункт меню ліворуч лишається"""
    from helpers import ROOT
    src = (ROOT / 'index.html').read_text(encoding='utf-8')
    check('⚙' not in src and '\\u2699' not in src and 'hdr-gear' not in src and 'Шестерн' not in src, 'у index.html лишилась шестерня або згадка про неї')
    freeze(page, DAY)
    check('⚙' not in page.content(), 'шестерня на сторінці')
    if page.viewport_size['width'] >= 1024:
        check(page.locator('.side-nav .side-item', has_text='Налаштування').count() == 1, 'на ПК немає пункту «Налаштування» в меню')
        check(page.locator('.tab-bar').count() == 0, 'на ПК нижня панель')
        return
    page.set_viewport_size({'width': 375, 'height': 812})
    page.wait_for_timeout(200)
    bar = page.evaluate("""(()=>{const b=[...document.querySelectorAll('.tab-bar .tab-btn')],bar=document.querySelector('.tab-bar');
      return {l:b.map(e=>e.innerText.trim()),cut:b.filter(e=>{const s=e.querySelector('span');return s.scrollWidth>s.clientWidth+0.5||getComputedStyle(s).textOverflow==='ellipsis'&&s.scrollWidth>s.clientWidth}).length,
      fs:b.map(e=>parseFloat(getComputedStyle(e.querySelector('span')).fontSize)),ic:b.map(e=>Math.round(e.querySelector('svg').getBoundingClientRect().width)),
      sw:bar.scrollWidth,cw:bar.clientWidth,r:Math.max(...b.map(e=>e.getBoundingClientRect().right)),l0:Math.min(...b.map(e=>e.getBoundingClientRect().left)),doc:document.scrollingElement.scrollWidth}})()""")
    print(f'      вкладки {bar["l"]}, шрифт {set(bar["fs"])}, іконки {set(bar["ic"])}, ширина {bar["sw"]}/{bar["cw"]}')
    check(bar['l'] == ['Огляд', 'Бюджет', 'Операції', 'Платежі', 'Заощадження', 'Налаштування'], f'вкладки телефона: {bar["l"]}')
    check(bar['cut'] == 0 and all(10 <= f <= 11 for f in bar['fs']) and all(i == 22 for i in bar['ic']), f'підписи обрізані або не 10-11px, іконки не 22px: {bar}')
    check(bar['sw'] <= bar['cw'] and bar['l0'] >= 0 and bar['r'] <= 375 and bar['doc'] <= 375, f'нижня панель переповнена: {bar}')
    go_tab(page, 5)
    check(page.locator('.set-mpage').count() == 1 and page.locator('[role=dialog]').count() == 0, 'шоста вкладка не сторінка або відкрила діалог')
    check(page.locator('.fab').count() == 0, 'на сторінці налаштувань лишилась кнопка «+»')
    page.locator('.set-mpage button', has_text='Інтеграції').first.click()
    page.wait_for_timeout(250)
    check('Назад' in page.inner_text('.set-mpage') and page.locator('[role=dialog]').count() == 0, '«Інтеграції» не відкрились на всю сторінку з «Назад»')
    page.locator('.set-mpage button', has_text='Назад').click()
    page.wait_for_timeout(250)
    check('Зарплата' in page.inner_text('.set-mpage'), '«Назад» не повернув до списку розділів')
    go_tab(page, 0)
    check(page.locator('.set-mpage').count() == 0 and page.locator('.p-overview').count() == 1, 'з налаштувань не повернулись на Огляд')


def pill(page):
    """v149 (власник: «чому не зробив дизайн вибору періоду для мобільних»): пігулка періоду 44px на всю ширину, стрілки всередині,
    по центру «6-21 жовт.» і «зарплата · 2026», «зараз» лише для поточного періоду, дотик по центру відкриває список, свайп міняє період і не вкладку;
    на ПК той самий стиль у шапці сторінки"""
    freeze(page, DAY)
    if page.viewport_size['width'] >= 1024:
        dp = page.locator('.dtitle .dper')
        check(dp.locator('.pp-now').count() == 1 and dp.locator('.side-pname').inner_text().startswith('6-21 жовт.'), f'шапка ПК: {dp.inner_text()!r}')
        page.locator('.dtitle .side-arr').nth(1).click()
        page.wait_for_timeout(200)
        check(dp.locator('.pp-now').count() == 0, '«зараз» на не поточному періоді (ПК)')
        return
    page.set_viewport_size({'width': 375, 'height': 812})
    page.wait_for_timeout(200)
    p = page.locator('.header .per-pill')
    b = p.bounding_box()
    print(f'      пігулка {b}, текст {p.inner_text()!r}')
    check(p.count() == 1 and abs(b['height'] - 44) <= 1 and b['width'] >= 375 - 2 * 16 - 1, f'пігулка не 44px на всю ширину: {b}')
    check(p.locator('.pp-t').inner_text().replace('\n', ' ').startswith('6-21 жовт.') and p.locator('.pp-now').count() == 1, f'центр пігулки: {p.inner_text()!r}')
    check(p.locator('.pp-s').inner_text() == 'зарплата · 2026', f'підпис пігулки: {p.locator(".pp-s").inner_text()!r}')
    check(page.locator('.header .pp-arr[aria-label="Попередній період"]').count() == 1 and page.locator('.header .pp-arr[aria-label="Наступний період"]').count() == 1, 'стрілки не в пігулці')
    t0 = p.locator('.pp-t').inner_text()
    page.locator('.header .pp-arr[aria-label="Наступний період"]').click()
    page.wait_for_timeout(200)
    t1 = p.locator('.pp-t').inner_text()
    check(t1 != t0 and p.locator('.pp-now').count() == 0, f'стрілка не змінила період або «зараз» лишилось: {t0!r} -> {t1!r}')
    page.locator('.header .pp-arr[aria-label="Попередній період"]').click()
    page.wait_for_timeout(200)
    check(p.locator('.pp-t').inner_text() == t0, 'стрілка назад не повернула період')
    # свайп по пігулці: наступний період, вкладка та сама
    tab0 = page.locator('.tab-btn[aria-current=page]').inner_text()
    y = b['y'] + b['height'] / 2
    for ev, xx in (('pointerdown', b['x'] + b['width'] * 0.7), ('pointermove', b['x'] + b['width'] * 0.5), ('pointerup', b['x'] + b['width'] * 0.3)):
        p.dispatch_event(ev, {'pointerType': 'touch', 'clientX': xx, 'clientY': y, 'bubbles': True, 'isPrimary': True, 'pointerId': 7})
        page.wait_for_timeout(40)
    page.wait_for_timeout(250)
    check(p.locator('.pp-t').inner_text() == t1, f'свайп ліворуч не дав наступний період: {p.locator(".pp-t").inner_text()!r}')
    check(page.locator('.tab-btn[aria-current=page]').inner_text() == tab0, 'свайп по пігулці перемкнув вкладку')
    p.locator('.pp-mid').click()
    page.wait_for_timeout(300)
    check(page.locator('[role=dialog][aria-label="Період"]').count() == 1, 'дотик по центру пігулки не відкрив список періодів')
    page.keyboard.press('Escape')
    sw = page.evaluate('document.scrollingElement.scrollWidth')
    check(sw <= 375, f'горизонтальна прокрутка: {sw}')


CHECKS = [
    ('v149: «Найближче» у два рядки: назва повністю, сума праворуч, дата · строк · джерело', 'desktop', near_rows),
    ('v149: «Найближче» у два рядки: назва повністю, сума праворуч, дата · строк · джерело', 'mobile', near_rows),
    ('v149: «За планом» у «Доступні кошти», плитки KPI однакової висоти', 'desktop', kpi_plan),
    ('v149: «За планом» у «Доступні кошти», плитки KPI однакової висоти', 'mobile', kpi_plan),
    ('v149: кільце з багатьма категоріями на ПК: колонки легенди, графік від 240px, без внутрішньої прокрутки', 'desktop', ring_many),
    ('v149: тултіп графіка: одне число в рядку, праві краї разом, ланцюжок балансу', 'desktop', tooltip),
    ('v149: тултіп графіка: одне число в рядку, праві краї разом, ланцюжок балансу', 'mobile', tooltip),
    ('v149: Календар іде за періодом шапки, стрілки міняють період', 'desktop', period_follow),
    ('v149: телефон, Платежі: баланс сьогодні = плитка Огляду, баланс після в рядках', 'mobile', pay_balance_mobile),
    ('v149: Операції відкриваються на «Сьогодні», мета-рядок без назви місяця', 'desktop', flow_today),
    ('v149: Операції відкриваються на «Сьогодні», мета-рядок без назви місяця, сума не під «+»', 'mobile', flow_today),
    ('v149: шестерні немає, «Налаштування» пунктом меню ПК', 'desktop', no_gear),
    ('v149: шестерні немає, шоста вкладка «Налаштування» сторінкою, панель вміщається на 375', 'mobile', no_gear),
    ('v149: період у шапці ПК тим самим стилем, «зараз»', 'desktop', pill),
    ('v149: пігулка періоду на телефоні: стрілки, центр, свайп, «зараз»', 'mobile', pill),
]
