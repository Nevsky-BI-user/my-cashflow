"""Щільність, палітра й доступність компонування без зміни фінансової логіки."""
import json
from pathlib import Path
from helpers import check, finance_ref, freeze, go_tab
from checks.a11y import CONTRAST

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'spec/.out'
PALETTE = ['--bg', '--html-bg', '--card', '--card2', '--border', '--border2', '--text', '--text2', '--head', '--muted', '--muted2', '--indigo', '--blue', '--green', '--green-t', '--red', '--red-t', '--yellow', '--yellow-t', '--shadow', '--acc-bg', '--inc-bg', '--exp-bg', '--debt-bg']
LIQUID_PALETTE = {'--bg':'#e7f0f4','--html-bg':'#e7f0f4','--card':'#fff','--card2':'#f7fafb','--border':'#d8e3e7','--border2':'#e8eef1','--text':'#253744','--text2':'#253744','--head':'#142a36','--muted':'#526775','--muted2':'#5f7180','--indigo':'#126e70','--blue':'#126e70','--green':'#21754f','--green-t':'#21754f','--red':'#b54149','--red-t':'#b54149','--yellow':'#9b640f','--yellow-t':'#8e5b0b','--shadow':'rgba(30,65,80,.12)','--acc-bg':'#e6f3f1'}
DARK_PALETTE = {'--bg':'#0e171e','--html-bg':'#0b131a','--card':'#16222c','--card2':'#1d2e3a','--border':'#3b4f5d','--border2':'#2d414e','--text':'#e4edf0','--text2':'#e7eff4','--head':'#f0f6f8','--muted':'#b1c0ca','--muted2':'#9db0bd','--indigo':'#70cfca','--blue':'#70cfca','--green':'#72d5a0','--green-t':'#8ee0b5','--red':'#f78f95','--red-t':'#ffadb2','--yellow':'#e5bf75','--yellow-t':'#f3cd87','--shadow':'rgba(0,0,0,.35)','--acc-bg':'#203f45'}
GEOMETRY = """({height:document.documentElement.scrollHeight,width:document.documentElement.scrollWidth,viewport:innerHeight,cards:[...document.querySelectorAll('.panel.desk > *, .dv-cols > *, .ck-cols > *, .bud-cols > *, .goals-cols > *')].map(e=>({cls:e.className,y:Math.round(e.getBoundingClientRect().y),h:Math.round(e.getBoundingClientRect().height)}))})"""


def audit(page):
    freeze(page, '2026-10-08')
    rows = []
    # Незмінний еталон отримано з CSS до компонування 10.10.2026, а не з поточного UI.
    palettes = json.loads((ROOT / 'spec/fixtures/visual-palette.json').read_text(encoding='utf-8'))
    shots = OUT / 'shots'
    shots.mkdir(exist_ok=True)
    for theme in ('light', 'dark'):
        for width, height in ((320, 812), (360, 812), (390, 844), (768, 1000), (1280, 800), (1440, 900), (1920, 900)):
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('(theme)=>document.documentElement.dataset.theme=theme', theme)
            page.wait_for_timeout(100)
            expected = {**palettes[('desktop' if width >= 1024 else 'mobile') + '-' + theme], **(LIQUID_PALETTE if theme == 'light' else DARK_PALETTE)}
            palette = page.evaluate("""expected=>{const now=getComputedStyle(document.documentElement);return Object.entries(expected).filter(([k,v])=>now.getPropertyValue(k).trim()!==v).map(([k,v])=>[k,v,now.getPropertyValue(k)])}""", expected)
            check(not palette, f'Змінено палітру {theme}/{width}: {palette}')
            for i, tab in enumerate(('overview', 'budget', 'operations', 'payments', 'savings')):
                go_tab(page, i)
                geometry = page.evaluate(GEOMETRY)
                title = page.locator('.dtitle h1:visible' if width >= 1024 else '.header .pp-t:visible,.budget-mobile-head h1:visible').first
                check(title.count() == 1, f'{theme}/{width}/{tab}: page heading missing')
                contrast = title.evaluate('(e,fn)=>eval(fn)(e)', CONTRAST)
                check(contrast['r'] >= 4.5, f'{theme}/{width}/{tab}: heading contrast below 4.5: {contrast}')
                rows.append({'theme': theme, 'width': width, 'tab': i, **geometry})
                check(geometry['width'] <= width, f'{theme}/{width}/{tab}: горизонтальне переповнення {geometry}')
                if width >= 1024:
                    # v159: мінімум графіка 180px на низькому ПК; стандартні картки вміщуються.
                    check(geometry['height'] <= height + 1, f'{theme}/{width}/{tab}: сторінка вища за екран {geometry}')
                    clipped = page.evaluate("""[...document.querySelectorAll('.kpi-rv,.dv-kpi-v,.bud-kpi-v,.flow-amt,.ce-a,.ce-b,.goals-log-a')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>[e.className,e.innerText,e.scrollWidth,e.clientWidth])""")
                    check(not clipped, f'{theme}/{width}/{tab}: обрізані суми {clipped[:3]}')
                    if i == 0:
                        bottom = page.locator('.dv-recent').evaluate('e=>e.getBoundingClientRect().bottom')
                        check(page.evaluate("[...document.querySelectorAll('.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')].filter(e=>e.offsetParent).every(e=>e.scrollHeight<=e.clientHeight+2)"), f'{width}: внутрішня прокрутка огляду')
                        check(bottom <= height, f'{width}: останні операції нижче екрана: {bottom}')
                        check(page.locator('.dv-fc svg').first.evaluate('e=>e.getBoundingClientRect().height') >= (159.5 if height < 900 else 179.5 if height < 1000 else 259.5), f'{width}x{height}: графік нижчий за адаптивний мінімум')
                elif i == 0:
                    # v145: рядки плиток KPI: підпис і сума не зливаються; рядок «Доступно до» (data-r=until) окремим блоком на всю ширину
                    overlap = page.evaluate("""[...document.querySelectorAll('.kpi-row')].filter(e=>e.offsetParent).filter(e=>{const l=e.querySelector('.kpi-rl').getBoundingClientRect(),v=e.querySelector('.kpi-rv').getBoundingClientRect();return l.right>v.left+1&&l.bottom>v.top+1}).map(e=>e.innerText)""")
                    check(not overlap, f'{width}: злиті підписи плиток KPI {overlap}')
                    # v148: рядок «Доступно до» з плитки бюджету прибрано (п. 5)
                    check(page.locator('.kpi-budget [data-r=until]').count() == 0, '«Доступно до» лишився в плитці бюджету')
                    check(page.locator('.projection-summary').bounding_box()['y'] < page.locator('.o-next').bounding_box()['y'], 'Плитки KPI мають передувати найближчим платежам')
                    check(page.evaluate("[...document.querySelectorAll('.o-next-row')].every(e=>getComputedStyle(e).opacity==='1')"), 'Суми найближчих платежів надто приглушені')
                if width in (390, 1440) or (width == 1920 and i == 0):
                    page.evaluate('document.activeElement.blur()')
                    page.mouse.move(2, 2)
                    page.screenshot(path=str(shots / f'redesign-v4-{theme}-{width}-{tab}.png'), full_page=width < 1024)
            if width >= 1024:
                page.locator('.side-item').first.click()
                check(page.locator('.p-overview.desk').is_visible(), 'Клік меню не відкрив огляд')
                page.keyboard.press('Digit2')
                check(page.locator('.p-budget.desk').is_visible(), 'Клавіатурна навігація не працює')
                page.keyboard.press('Digit1')
                page.locator('.bcard').first.click()
                check(page.locator('[role=dialog]').count() > 0, 'Картка не відкриває діалог')
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                check(page.locator('[role=dialog]').count() == 0, 'Escape не закриває діалог')
    page.emulate_media(reduced_motion='reduce')
    page.keyboard.press('Digit2')
    page.wait_for_timeout(100)
    check(page.locator('.p-budget.desk').is_visible(), 'Reduced motion приховує сторінку')
    check(page.evaluate("getComputedStyle(document.querySelector('.tab-page')).opacity") == '1', 'Reduced motion: непрозорість не остаточна')
    (OUT / 'visual-layout-geometry.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print('      70 станів, палітра до/після, повні суми, мобільний баланс, клавіатура, діалоги й reduced motion')


def current_overview(page):
    for width, height in ((1280, 800), (1280, 860), (1440, 900)):
        page.set_viewport_size({'width': width, 'height': height})
        go_tab(page, 0)
        page.wait_for_timeout(150)
        check(page.evaluate("[...document.querySelectorAll('.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')].filter(e=>e.offsetParent).every(e=>e.scrollHeight<=e.clientHeight+2)"), f'Today/{width}/{height}: внутрішня прокрутка огляду')
        # Стандартний Огляд повністю вміщується, включно з низьким ПК.
        check(page.locator('.dv-recent').evaluate('e=>e.getBoundingClientRect().bottom<=innerHeight'), 'Нижня картка обрізана')
        check(page.locator('.dv-fc svg').first.evaluate('e=>e.getBoundingClientRect().height') >= (159.5 if height < 900 else 179.5 if height < 1000 else 259.5), f'Today/{width}/{height}: графік нижчий за адаптивний мінімум')
        check(page.locator('.dv-near .dv-ev').count() == (5 if width < 1400 or height < 1000 else 8), 'Неправильна кількість найближчих подій')
        if width == 1280 and height == 800:
            page.screenshot(path=str(OUT / 'shots/redesign-v4-today-1280-overview.png'))
        page.locator('.dv-all-payments').click()
        check(page.locator('.p-credits.desk').is_visible(), 'Усі платежі не відкриває вкладку')
    for width in (1280, 1920):
        page.set_viewport_size({'width': width, 'height': 900})
        page.wait_for_timeout(250)
        check(page.locator('.tab-page').evaluate("e=>getComputedStyle(e).opacity") == '1', 'Знімок календаря до завершення анімації')
        check(page.locator('.cal-cell.today').evaluate("e=>{const c=e.getBoundingClientRect(),t=e.querySelector('.cal-td').getBoundingClientRect();return t.width<=1||t.right<=c.right}"), 'Сьогодні виходить за клітинку')
        page.screenshot(path=str(OUT / f'shots/redesign-v4-today-{width}-payments.png'))


def calendar_geometry(page):
    freeze(page, '2026-10-10')
    go_tab(page, 3)
    for width, height in ((1280, 800), (1920, 900)):
        page.set_viewport_size({'width': width, 'height': height})
        cell = page.locator('.cal-cell[data-date="2026-10-24"]')
        cell.focus()
        page.keyboard.press('Enter')
        check(page.locator('.ck-day-events').is_visible(), 'Клавіатура не відкриває повні події дня')
        check(page.evaluate("[...document.querySelectorAll('.ck-day-events .ce-n,.ck-day-events .ce-a')].every(e=>e.scrollWidth<=e.clientWidth+1)"), 'Назва або сума дня обрізана')
        page.locator('.ck-day .ck-link').click()
        page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
        check(page.locator('.cal-days.r6').count() == 1, 'Листопад 2026 має шість тижнів')
        if width < 1400:
            hidden = page.locator('.cal-cell').filter(has=page.locator('.cal-more')).first
            visible = hidden.locator('.cal-ln').count()
            more = int(hidden.locator('.cal-more').inner_text().split()[0].lstrip('+'))
            selected_date=hidden.get_attribute('data-date')
            events=[e for e in finance_ref(page)['events'] if e['date']==selected_date]
            grouped=sum(e['kind']!='variable' for e in events)  # v143: змінні витрати в клітинках не показуються
            check(visible==1 and visible+more==grouped, f'лічильник {visible}+{more}, згрупованих подій {grouped}')
            hidden.click()
            # v149: щоденні витрати дня одним рядком «Щоденні витрати»
            want = sum(e['kind'] != 'variable' for e in events) + (1 if any(e['kind'] == 'variable' for e in events) else 0)
            check(page.locator('.ck-day-events .ck-bd-row').count()==want, 'деталі не містять усіх канонічних подій вибраного дня')
            detail_text=page.inner_text('.ck-day-events')
            check(all(e['name'] in detail_text for e in events if e['kind'] != 'variable'), 'повна назва прихованої події недоступна')
            check(page.evaluate("[...document.querySelectorAll('.ck-day-events .ce-n')].every(e=>e.scrollWidth<=e.clientWidth+1)"), 'Прихована подія недоступна повністю')
            page.locator('.ck-day .ck-link').click()

        check(page.evaluate("document.documentElement.scrollHeight<=innerHeight+1&&[...document.querySelectorAll('.ck-left,.ck-side,.ck-day')].filter(e=>e.offsetParent).every(e=>e.getBoundingClientRect().bottom<=innerHeight+1)"), f'{width}: шість тижнів виходять за екран')
        scrollers=page.evaluate("""[...document.querySelectorAll('.content *')].filter(e=>e.offsetParent&&/auto|scroll/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+2).map(e=>({cls:e.className,allowed:e.matches('.ck-day,.ck-side')}))""")
        check(all(e['allowed'] for e in scrollers), f'зайві внутрішні скроли {scrollers}')
        last=page.locator('.ck-day .cal-ev').last
        last.scroll_into_view_if_needed()
        check(last.evaluate('e=>e.getBoundingClientRect().bottom<=innerHeight+1'), 'останній платіж недоступний')
        check(page.evaluate('window.scrollY==0&&document.documentElement.scrollHeight<=innerHeight+1'), 'прокручується вся сторінка')
        page.locator('.ck-arr[aria-label="Попередній місяць"]').click()


# Всі картки доступні прокруткою сторінки; всередині карток немає окремих скролів.
COLS = r"""()=>{const cards=[...document.querySelectorAll('.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')];
const bud=document.querySelector('.dv-bud'),cats=bud.querySelector('.bd-desk .bd-leg,.bd-empty');
return {cards:cards.map(e=>({cls:e.className,ov:e.scrollHeight-e.clientHeight,bottom:e.getBoundingClientRect().bottom+scrollY})),
cats:cats?{display:getComputedStyle(cats).display,count:cats.classList.contains('bd-empty')?1:cats.children.length,over:cats.getBoundingClientRect().bottom-bud.getBoundingClientRect().bottom}:null,
wide:document.documentElement.scrollWidth,doc:document.documentElement.scrollHeight,vh:innerHeight}}"""


def overview_days(page):
    seen = 0
    for iso in ('2026-10-08', '2026-10-12', '2026-10-23', '2026-11-15', '2026-11-01', '2026-10-24'):
        freeze(page, iso)
        go_tab(page, 0)
        for width, height in ((1280, 800), (1280, 860)):
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(200)
            st = page.evaluate(COLS)
            tag = f'{iso}/{width}x{height}'
            check(len(st['cards']) >= 5, f'{tag}: основні картки відсутні {st}')
            check(st['cats'] and st['cats']['display'] != 'none' and st['cats']['count'] > 0, f'{tag}: категорії бюджету приховані {st}')
            check(st['cats']['over'] <= 1, f'{tag}: категорії виходять за картку бюджету {st}')
            check(all(c['ov'] <= 2 for c in st['cards']), f'{tag}: внутрішнє переповнення карток {st}')
            check(st['wide'] <= width, f'{tag}: горизонтальне переповнення {st}')
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            check(page.evaluate("[...document.querySelectorAll('.dv-cols .dv-bud,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')].every(e=>e.getBoundingClientRect().bottom<=innerHeight+1)"), f'{tag}: нижні картки недоступні прокруткою сторінки')
            page.evaluate('window.scrollTo(0,0)')
            seen += 1
    check(seen == 12, f'перевірено станів {seen} замість 12')


CHECKS = [('visual_layout geometry', 'desktop', audit), ('visual_layout current overview', 'desktop', current_overview), ('visual_layout overview days', 'desktop', overview_days), ('visual_layout calendar geometry', 'desktop', calendar_geometry)]
