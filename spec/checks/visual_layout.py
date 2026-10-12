"""Щільність, палітра й доступність компонування без зміни фінансової логіки."""
import json
from pathlib import Path
from helpers import check, finance_ref, freeze, go_tab

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'spec/.out'
PALETTE = ['--bg', '--html-bg', '--card', '--card2', '--border', '--border2', '--text', '--text2', '--head', '--muted', '--muted2', '--indigo', '--blue', '--green', '--green-t', '--red', '--red-t', '--yellow', '--yellow-t', '--shadow', '--acc-bg', '--inc-bg', '--exp-bg', '--debt-bg']
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
            expected = palettes[('desktop' if width >= 1024 else 'mobile') + '-' + theme]
            palette = page.evaluate("""expected=>{const now=getComputedStyle(document.documentElement);return Object.entries(expected).filter(([k,v])=>now.getPropertyValue(k).trim()!==v).map(([k,v])=>[k,v,now.getPropertyValue(k)])}""", expected)
            check(not palette, f'Змінено палітру {theme}/{width}: {palette}')
            for i, tab in enumerate(('overview', 'budget', 'operations', 'payments', 'savings')):
                go_tab(page, i)
                geometry = page.evaluate(GEOMETRY)
                rows.append({'theme': theme, 'width': width, 'tab': i, **geometry})
                check(geometry['width'] <= width, f'{theme}/{width}/{tab}: горизонтальне переповнення {geometry}')
                if width >= 1024:
                    check(geometry['height'] <= height + 1, f'{theme}/{width}/{tab}: сторінка вища за екран {geometry}')
                    clipped = page.evaluate("""[...document.querySelectorAll('.balc-v,.dv-kpi-v,.bud-kpi-v,.flow-amt,.ce-a,.ce-b,.goals-log-a')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>[e.className,e.innerText,e.scrollWidth,e.clientWidth])""")
                    check(not clipped, f'{theme}/{width}/{tab}: обрізані суми {clipped[:3]}')
                    if i == 0:
                        bottom = page.locator('.dv-recent').evaluate('e=>e.getBoundingClientRect().bottom')
                        check(page.evaluate("[...document.querySelectorAll('.dv-main,.dv-side')].filter(e=>e.offsetParent).every(e=>e.scrollHeight<=e.clientHeight+2)"), f'{width}: внутрішня прокрутка огляду')
                        check(bottom <= height, f'{width}: останні операції нижче екрана: {bottom}')
                elif i == 0:
                    # рядок «Доступно до» (data-b=until) займає всю ширину і не має суми .bal-v
                    overlap = page.evaluate("""[...document.querySelectorAll('.bal-row')].filter(e=>e.querySelector('.bal-v')).filter(e=>{const l=e.querySelector('.bal-l').getBoundingClientRect(),v=e.querySelector('.bal-v').getBoundingClientRect();return l.right>v.left+1&&l.bottom>v.top+1}).map(e=>e.innerText)""")
                    check(not overlap, f'{width}: злиті підписи балансу {overlap}')
                    check(page.evaluate("[...document.querySelectorAll('.bal-sub')].every(e=>getComputedStyle(e).display==='block')"), 'Пояснення балансу не на окремих рядках')
                    check(page.locator('.o-next').bounding_box()['y'] < page.locator('.o-bal').bounding_box()['y'], 'Найближчі платежі мають передувати балансу')
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
        check(page.evaluate("[...document.querySelectorAll('.dv-main,.dv-side')].filter(e=>e.offsetParent).every(e=>e.scrollHeight<=e.clientHeight+2)"), f'Today/{width}/{height}: внутрішня прокрутка огляду')
        check(page.locator('.dv-recent').evaluate('e=>e.getBoundingClientRect().bottom<=innerHeight'), 'Нижня картка обрізана')
        check(page.locator('.dv-near .dv-ev').count() == (5 if width < 1400 or height < 860 else 8), 'Неправильна кількість найближчих подій')
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
            check(page.locator('.ck-day-events .ck-bd-row').count()==len(events), 'деталі не містять усіх канонічних подій вибраного дня')
            detail_text=page.inner_text('.ck-day-events')
            check(all(e['name'] in detail_text for e in events), 'повна назва прихованої події недоступна')
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


# Стан колонок ПК-Огляду: переповнення, причина, з якою його допускає контракт, досяжність останньої картки після прокрутки
COLS = """(()=>{const col=s=>{const e=document.querySelector(s);const ov=e.scrollHeight-e.clientHeight;e.scrollTop=e.scrollHeight;const last=e.lastElementChild.getBoundingClientRect().bottom<=e.getBoundingClientRect().bottom+1;e.scrollTop=0;return{ov:ov,auto:/auto|scroll/.test(getComputedStyle(e).overflowY),last:last}};
const cats=document.querySelector('.dv-bud-cats');
return{main:col('.dv-main'),side:col('.dv-side'),unas:!!document.querySelector('.dv-side .unas-card'),dayEv:document.querySelectorAll('.dv-main .fc-day .fc-ev').length,
cats:cats?[getComputedStyle(cats).display,cats.children.length,Math.round(cats.getBoundingClientRect().bottom-document.querySelector('.dv-main').getBoundingClientRect().bottom)]:null}})()"""


def overview_days(page):
    # звичайні дні: Огляд на 1280×800 і 1280×860 без внутрішньої прокрутки, категорії бюджету видно (не ховаємо, вміщаємо розмірами);
    # прокрутка колонки дозволена лише з причиною: картка «Без рахунку» в правій (1-ше число) або дві й більше подій дня прогнозу в лівій (24-те)
    seen = {'normal': 0, 'unas': 0, 'dayEv': 0}
    for iso in ('2026-10-08', '2026-10-12', '2026-10-23', '2026-11-15', '2026-11-01', '2026-10-24'):
        freeze(page, iso)
        go_tab(page, 0)
        for width, height in ((1280, 800), (1280, 860)):
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(200)
            st = page.evaluate(COLS)
            tag = f'{iso}/{width}x{height}'
            check(st['cats'] and st['cats'][0] != 'none' and st['cats'][1] > 0, f'{tag}: категорії бюджету приховані {st["cats"]}')
            for name, why in (('side', 'unas'), ('main', 'dayEv')):
                c = st[name]
                if c['ov'] <= 2:
                    continue
                allowed = st['unas'] if why == 'unas' else st['dayEv'] >= 2
                check(allowed, f'{tag}: колонка {name} прокручується на {c["ov"]}px без причини {st}')
                check(c['auto'] and c['last'], f'{tag}: у колонці {name} остання картка недосяжна прокруткою {c}')
                seen[why] += 1
            if st['main']['ov'] <= 2 and st['side']['ov'] <= 2:
                seen['normal'] += 1
                check(st['cats'][2] <= 1, f'{tag}: категорії бюджету нижче колонки на {st["cats"][2]}px')
    check(seen['normal'] >= 8, f'звичайних станів без прокрутки лише {seen["normal"]} із 8')
    print(f'      станів без прокрутки {seen["normal"]}, з карткою «Без рахунку» {seen["unas"]}, з подіями дня прогнозу {seen["dayEv"]}')


CHECKS = [('visual_layout geometry', 'desktop', audit), ('visual_layout current overview', 'desktop', current_overview), ('visual_layout overview days', 'desktop', overview_days), ('visual_layout calendar geometry', 'desktop', calendar_geometry)]
