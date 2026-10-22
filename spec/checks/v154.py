"""v154: підказка «Гроші в часі» без трикрапки (власник: назви подій обрізані): повна назва події, ширина росте до межі, далі
перенос на другий рядок, сума праворуч по верхньому краю; підказка в межах графіка й екрана, зокрема біля правого краю і на 375 px.
Демо з боргом Mono (два погашення в день виплати) і довгою назвою обовʼязкового платежу."""
from helpers import check, freeze, go_tab

DAY = '2026-10-12'
LONG = 'Підписки сервісів навчання дітей і родинний пакет хмарного сховища'
FIX = [("kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
        "kind:'credit',mono_account_id:'demo-mono',balance:0,debt:20000,credit_limit:30000,debt_month:pbIso(new Date(t.getFullYear(),t.getMonth(),1))"),
       ("{id:'f5',name:'Підписки',", "{id:'f5',name:'" + LONG + "',")]

# усі рядки підказки: підпис, обрізання, трикрапка, стиль, верх підпису й суми; рамки підказки, графіка й екрана
TIP = r"""(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;const R=e=>e.getBoundingClientRect();const c=document.querySelector('.dv-fc'),bb=R(b),cb=R(c);
return {date:b.querySelector('.fc-tip-h')?.textContent||'',box:[bb.left,bb.top,bb.right,bb.bottom],card:[cb.left,cb.top,cb.right,cb.bottom],vw:document.documentElement.clientWidth,
text:b.textContent,rp:b.querySelectorAll('.fc-tip-rp').length,rows:[...b.querySelectorAll('.fc-tip-r')].map(r=>{const l=r.querySelector('.fc-tip-l'),n=r.querySelector('.fc-tip-n'),s=getComputedStyle(l);
const lh=parseFloat(s.lineHeight)||16;return {l:l.textContent,cut:l.scrollWidth>l.clientWidth+1||l.scrollHeight>l.clientHeight+1,to:s.textOverflow,ws:s.whiteSpace,lines:Math.round(R(l).height/lh),
lt:R(l).top,nt:R(n).top,nr:R(n).right,br:bb.right}})}})()"""


def tip_full(page):
    desk = page.viewport_size['width'] >= 1024
    freeze(page, DAY, FIX)
    go_tab(page, 0)
    page.locator('.dv-fc .fc-chips button[data-r=m]').click()
    page.wait_for_timeout(250)
    to = page.evaluate("document.querySelector('.dv-fc .fc-svg').dataset.to")
    from datetime import date as _d
    steps = (_d.fromisoformat(to) - _d.fromisoformat(DAY)).days
    page.locator('.dv-fc .fc-plot').focus()
    page.keyboard.press('ArrowRight')
    page.keyboard.press('ArrowLeft')
    seen_rp = seen_long = wrapped = 0
    last = None
    for i in range(steps + 1):
        if i:
            page.keyboard.press('ArrowRight')
        t = page.evaluate(TIP)
        if not t:
            continue
        last = t
        tag = f'{"ПК" if desk else "телефон"} {t["date"]}'
        check('…' not in t['text'], f'{tag}: трикрапка в підказці: {t["text"]}')
        for r in t['rows']:
            check(not r['cut'], f'{tag}: підпис «{r["l"]}» обрізано')
            check(r['to'] != 'ellipsis' and r['ws'] != 'nowrap', f'{tag}: «{r["l"]}» з text-overflow {r["to"]}, white-space {r["ws"]}')
            check(abs(r['lt'] - r['nt']) <= 1.5, f'{tag}: сума «{r["l"]}» не по верхньому краю ({r["lt"]} і {r["nt"]})')
            check(r['nr'] <= r['br'] + 0.5, f'{tag}: сума «{r["l"]}» виходить за підказку')
            if LONG in r['l']:
                seen_long += 1
                wrapped += r['lines'] >= 2
                w, cw = t['box'][2] - t['box'][0], t['card'][2] - t['card'][0]
                check(w >= min(300, cw) - 1.5, f'{tag}: довга назва переноситься, хоча підказка вужча за межу: {w} з {min(300, cw)}')
                print(f'      {tag}: ширина підказки з довгою назвою {w:.0f}, рядків {r["lines"]}')
        b, c = t['box'], t['card']
        check(b[0] >= c[0] - 0.5 and b[2] <= c[2] + 0.5 and b[0] >= 0 and b[2] <= t['vw'] + 0.5, f'{tag}: підказка поза графіком чи екраном: {b} {c} {t["vw"]}')
        seen_rp += t['rp'] >= 2
    check(seen_rp > 0, 'немає дня з двома погашеннями: перевірка не показова')
    check(seen_long > 0 and wrapped > 0, f'довга назва не трапилась або не перенеслась: {seen_long} {wrapped}')
    # останній крок = кінець осі, тобто крайня права точка графіка
    check(last and steps >= 20, f'пройдено лише {steps} днів: перевірка не показова')
    print(f'      днів з двома погашеннями {seen_rp}, довга назва {seen_long} раз(и), з переносом {wrapped}; останній {last["date"]}: {last["box"]} у {last["card"]}')


CHECKS = [
    ('v154: підказка «Гроші в часі»: повні назви без трикрапки, перенос, сума вгорі праворуч, у межах графіка (ПК)', 'desktop', tip_full),
    ('v154: підказка «Гроші в часі»: повні назви без трикрапки, перенос, сума вгорі праворуч, у межах екрана (телефон 375)', 'mobile', tip_full),
]

# елементи з назвою події чи погашення (довга назва фікстури або «Погашення ...»), обрізані трикрапкою;
# виняток: клітинка сітки календаря Платежів, де рядок має title з повною назвою
CUT = r"""(()=>{const out=[];for(const e of document.querySelectorAll('body *')){if(!e.offsetParent||e.children.length>2)continue;const t=e.textContent;
if(!(t.includes('Підписки сервісів')||/^Погашення /.test(t.trim())))continue;const s=getComputedStyle(e);
const cut=(s.textOverflow==='ellipsis'&&s.overflow!=='visible'&&e.scrollWidth>e.clientWidth+1)||t.includes('…')||(s.webkitLineClamp!=='none'&&e.scrollHeight>e.clientHeight+1);
/* клітинка сітки календаря: назва скорочена, повна в title рядка і в розкладі дня; поза скоупом v154, лише вимога title */const cell=e.closest('.cal-cell .cal-ln');if(cut&&cell&&(cell.title||'').includes(t.trim()))continue;if(cut)out.push({cls:e.className,t:t.slice(0,60),sw:e.scrollWidth,cw:e.clientWidth})}return out})()"""


def names_full(page):
    tag = 'ПК' if page.viewport_size['width'] >= 1024 else 'телефон'
    freeze(page, DAY, FIX)
    bad = []
    for i, nm in ((0, 'Огляд'), (3, 'Платежі')):
        go_tab(page, i)
        page.wait_for_timeout(500)
        got = page.evaluate(CUT)
        print(f'      {tag} {nm}: обрізаних назв {len(got)} {got[:6]}')
        bad += [(nm, g) for g in got]
    check(not bad, f'{tag}: назви подій обрізані: {bad[:6]}')


CHECKS += [
    ('v154: назви подій і погашень без трикрапки на Огляді («Найближче») і в Платежах (ПК)', 'desktop', names_full),
    ('v154: назви подій і погашень без трикрапки на Огляді («Найближче») і в Платежах (телефон)', 'mobile', names_full),
]


# пояснення KPI (власник: «відкривається лише при наведенні на i»): плитка, числа й рядки не відкривають; з «i» і з підказки геть: закривається
KEYS = ('funds', 'budget', 'balance', 'inst')
NO_TIP = ('balance', 'inst')


def _tips(page):
    return page.locator('.kpi-tip').count()


def kpi_i_desktop(page):
    freeze(page, DAY)
    go_tab(page, 0)
    for k in KEYS:
        tile = page.locator(f'.p-overview.desk .kpi-t.kpi-{k}')
        i = tile.locator('.kpi-i')
        for sel in ('', ' .dv-kpi-v', ' .kpi-rows'):
            loc = page.locator(f'.p-overview.desk .kpi-t.kpi-{k}{sel}').first
            if not loc.count():
                continue
            loc.hover()
            page.wait_for_timeout(350)
            check(_tips(page) == 0, f'{k}: наведення на «{sel or "центр плитки"}» відкрило пояснення')
        # v183: «i» лише там, де пояснення не порожнє (баланс без боргів кредиток, розстрочки без платежів)
        if i.count() == 0:
            check(k in NO_TIP, f'{k}: немає «i», хоча пояснення є')
            continue
        i.hover()
        page.wait_for_selector(f'.kpi-tip[data-k={k}]')
        tile.locator('.dv-kpi-v').hover()
        page.wait_for_timeout(400)
        check(_tips(page) == 0, f'{k}: пояснення не закрилось, коли курсор пішов з «i» на плитку')
        # з «i» у саму підказку: лишається; з підказки геть: закривається
        i.hover()
        page.wait_for_selector(f'.kpi-tip[data-k={k}]')
        b = page.locator(f'.kpi-tip[data-k={k}]').bounding_box()
        page.mouse.move(b['x'] + b['width'] / 2, b['y'] + 6, steps=4)
        page.wait_for_timeout(300)
        check(_tips(page) == 1, f'{k}: пояснення зникло, коли курсор перейшов у нього')
        page.mouse.move(2, 2)
        page.wait_for_timeout(400)
        check(_tips(page) == 0, f'{k}: пояснення не закрилось, коли курсор пішов з нього')
    print(f'      ПК: {len(KEYS)} плитки, наведення лише на «i»')


def kpi_i_mobile(page):
    freeze(page, DAY)
    go_tab(page, 0)
    for k in KEYS:
        tile = page.locator(f'.projection-summary .kpi-{k}')
        if not tile.count():
            tile = page.locator(f'.kpi-{k}').first
        i = tile.locator('.kpi-i')
        tile.locator('.dv-kpi-v').click()
        page.wait_for_timeout(250)
        check(_tips(page) == 0, f'{k}: дотик до числа плитки відкрив пояснення')
        if i.count() == 0:
            check(k in NO_TIP, f'{k}: немає «i», хоча пояснення є')
            continue
        i.click()
        page.wait_for_selector(f'.kpi-tip[data-k={k}]')
        page.mouse.click(5, 5)
        page.wait_for_timeout(250)
        check(_tips(page) == 0, f'{k}: дотик поза поясненням не закрив його')
        i.click()
        page.wait_for_selector(f'.kpi-tip[data-k={k}]')
        i.click()
        page.wait_for_timeout(250)
        check(_tips(page) == 0, f'{k}: другий дотик до «i» не закрив пояснення')
    print(f'      телефон: {len(KEYS)} плитки, лише дотик до «i»')


CHECKS += [
    ('v154: пояснення KPI лише наведенням на «i»: плитка й числа не відкривають, курсор геть з «i» чи підказки закриває (ПК)', 'desktop', kpi_i_desktop),
    ('v154: пояснення KPI лише дотиком до «i»: дотик до плитки не відкриває, другий дотик і дотик поза закривають (телефон)', 'mobile', kpi_i_mobile),
]
