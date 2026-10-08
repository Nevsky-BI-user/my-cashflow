# Оформлення ПК (v135): шрифт Inter, плоскі картки банків без кіл, суцільна кнопка «+ Операція», лінія прогнозу 1.5px;
# період у шапці сторінки (Огляд, Бюджет, Потік, Календар), «Налаштування» пунктом панелі і сторінкою (не діалогом);
# сьогоднішній день у Потоці (ПК і телефон) і в Календарі; прогноз балансу в клітинках Календаря; знімки ov-1920, ov-dark-1920, ov-375
from helpers import check, dialog, freeze, go_tab, shot

DAY = '2026-10-08'
# фікстура: остання демо-операція на «31-ше» число, txDemo стискає дати поточного місяця до сьогодні, тож вона лягає саме на 08.10
TODAY_OP = [("[24,'Сільпо',2133,", "[31,'Сільпо',2133,")]

FONT = """(async()=>{await document.fonts.ready;
const ff=getComputedStyle(document.querySelector('.content')).fontFamily;
const loaded=[...document.fonts].some(f=>f.family.replace(/["']/g,'')==='Inter'&&f.status==='loaded');
const link=!!document.querySelector('link[rel=stylesheet][href*="fonts.googleapis.com"][href*="Inter"]');
return {ff,loaded,link}})()"""
CARDS = """[...document.querySelectorAll('.dv-cards .bcard')].map(e=>{const s=getComputedStyle(e);
return {bi:s.backgroundImage,h:Math.round(e.getBoundingClientRect().height),sh:s.boxShadow,deco:e.querySelectorAll(':scope > span[aria-hidden]').length}})"""
BTN = "(sel)=>{const e=document.querySelector(sel);if(!e)return null;const s=getComputedStyle(e);return {bi:s.backgroundImage,bg:s.backgroundColor,fw:s.fontWeight}}"


def fonts_cards_buttons(page):
    """Inter (або фолбек без мережі, але з посиланням на Google Fonts), картки банків без кіл, кнопки без градієнтів, лінія прогнозу 1.5"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.evaluate("document.documentElement.setAttribute('data-theme','light')")
    page.wait_for_timeout(300)
    f = page.evaluate(FONT)
    print(f'      шрифт: {f}')
    check(f['link'], 'немає <link> на Inter з fonts.googleapis.com')
    check('Inter' in f['ff'], f'font-family .content без Inter: {f["ff"]}')
    if not f['loaded']:
        print('      Inter не завантажився (превʼю без мережі?): допущено фолбек system-ui')
    cards = page.evaluate(CARDS)
    check(len(cards) >= 3, f'карток банків {len(cards)}')
    for c in cards:
        check(c['bi'] == 'none' or ('linear-gradient' in c['bi'] and 'radial' not in c['bi'] and 'conic' not in c['bi']), f'картка банку з декоративним фоном: {c["bi"][:80]}')
        check(c['deco'] == 0, f'у картці банку лишились декоративні кола: {c}')
        check(c['h'] == 96, f'картка банку {c["h"]}px, а не 96')
        check(c['sh'] == 'none', f'картка банку з тінню: {c["sh"]}')
    for sel in ('.side-add', '.dact'):
        b = page.evaluate(BTN, sel)
        check(b and b['bi'] == 'none', f'{sel}: градієнт {b}')
        check(b['fw'] in ('500', '600'), f'{sel}: вага {b["fw"]}, а не 500/600')
    sw = page.evaluate("(()=>{const e=document.querySelector('.fc-line');return e?getComputedStyle(e).strokeWidth:null})()")
    check(sw == '1.5px', f'лінія прогнозу {sw}, а не 1.5px')
    # ваги 700+ на ПК не вживаються (видимі текстові вузли в .content і .side)
    heavy = page.evaluate("""[...document.querySelectorAll('.content *, .side *')].filter(e=>e.offsetParent&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&+getComputedStyle(e).fontWeight>=700).map(e=>e.textContent.trim().slice(0,20)).slice(0,5)""")
    check(not heavy, f'текст із вагою 700+: {heavy}')
    page.mouse.move(2, 2)
    shot(page, 'ov-1920.jpg', full=False)
    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(300)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    check(bg == 'rgb(15, 17, 21)', f'фон ПК у темній темі {bg}, а не #0f1115')
    shot(page, 'ov-dark-1920.jpg', full=False)


def period_header(page):
    """Перемикач періоду в шапці Огляду, Бюджету, Потоку і Календаря; у бічній панелі блоку «Період» немає"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    check(page.locator('.side .side-per, .side .side-pname').count() == 0, 'блок «Період» лишився в бічній панелі')
    for i, nm in ((0, 'Огляд'), (1, 'Бюджет'), (2, 'Потік'), (3, 'Календар')):
        go_tab(page, i)
        per = page.locator('.dtitle .side-per')
        check(per.count() == 1 and per.is_visible(), f'{nm}: немає перемикача періоду в шапці')
        hb, pb = page.locator('.dtitle h1').bounding_box(), per.bounding_box()
        check(pb['x'] > hb['x'] + hb['width'] and abs((pb['y'] + pb['height'] / 2) - (hb['y'] + hb['height'] / 2)) < 8, f'{nm}: період не праворуч від заголовка: {hb} {pb}')
        check(pb['y'] + pb['height'] < 80, f'{nm}: період не у верхньому рядку: {pb}')
        check(page.locator('.dtitle .side-arr').count() == 2 and 'зарплата' in page.inner_text('.dtitle .dtitle-sub'), f'{nm}: стрілки або підпис періоду')
    # стрілки клавіатури і кнопка › міняють період
    go_tab(page, 0)
    p0 = page.inner_text('.dtitle .side-pname')
    page.locator('.dtitle .side-arr').nth(1).click()
    page.wait_for_timeout(250)
    check(page.inner_text('.dtitle .side-pname') != p0, 'кнопка › у шапці не змінила період')
    page.keyboard.press('ArrowLeft')
    page.wait_for_timeout(250)
    check(page.inner_text('.dtitle .side-pname') == p0, '← не повернула період')


def settings_page(page):
    """«Налаштування» шостим пунктом навігації: відкриває сторінку (не діалог) з 9 розділами і темою всередині"""
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(200)
    items = page.locator('.side-nav .side-item').all_inner_texts()
    check([x.strip() for x in items] == ['Огляд', 'Бюджет', 'Потік', 'Календар', 'Цілі', 'Налаштування'], f'пункти навігації: {items}')
    check(page.locator('.side-seg').count() == 0, 'перемикач теми лишився в бічній панелі')
    page.locator('.side-nav .side-item', has_text='Налаштування').click()
    page.wait_for_timeout(400)
    sp = page.locator('.set-page')
    check(sp.count() == 1 and sp.is_visible(), 'сторінка налаштувань не відкрилась')
    check(dialog(page, 'Налаштування').count() == 0 and page.locator('.overlay').count() == 0, 'налаштування відкрились діалогом')
    check(page.inner_text('.dtitle h1').strip() == 'Налаштування', 'заголовок сторінки не «Налаштування»')
    check(page.locator('.side-nav .side-item[aria-current=page]').inner_text().strip() == 'Налаштування', 'пункт «Налаштування» не активний')
    check(sp.locator('nav button').count() == 9, 'у налаштуваннях не 9 розділів')
    tp = page.evaluate("(()=>{const t=document.querySelector('.tab-page');return {vis:!!(t&&t.offsetParent),sh:document.documentElement.scrollHeight}})()")
    check(not tp['vis'] and tp['sh'] <= 900, f'під сторінкою налаштувань видно вкладку або сторінка прокручується: {tp}')
    sp.locator('nav button', has_text='Тема').click()
    page.wait_for_timeout(250)
    check(sp.locator('button[aria-pressed]').count() == 3, 'у розділі «Тема» немає перемикача теми')
    shot(page, 'settings-1920.jpg', full=False)
    page.locator('.side-nav .side-item', has_text='Потік').click()
    page.wait_for_timeout(300)
    check(sp.count() == 0 and page.inner_text('.dtitle h1').strip() == 'Потік', 'перехід на «Потік» не закрив сторінку налаштувань')


def today_desktop(page):
    """ПК: сьогоднішня група Потоку з підписом «Сьогодні» (одна), у Календарі сьогоднішня клітинка з маркером"""
    freeze(page, DAY, patch=TODAY_OP)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    go_tab(page, 2)
    g = page.locator('.p-flow.desk .flow-group.today')
    check(g.count() == 1, f'груп «сьогодні» {g.count()}, а не 1')
    t = g.locator('.flow-day.today').inner_text().lower()
    check('сьогодні' in t and t.startswith('8 жовтня'), f'заголовок сьогоднішнього дня: {t!r}')
    check(g.locator('.flow-row.tx').count() >= 1, 'у сьогоднішній групі немає операцій')
    st = page.evaluate("(()=>{const s=getComputedStyle(document.querySelector('.p-flow.desk .flow-group.today'));return {bg:s.backgroundColor,sh:s.boxShadow}})()")
    check(st['bg'] not in ('rgba(0, 0, 0, 0)', 'transparent') and 'inset' in st['sh'], f'сьогоднішня група без тла або лівої смуги: {st}')
    check(page.locator('.p-flow.desk .flow-today').count() == 1, 'підпис «Сьогодні» не один')
    go_tab(page, 3)
    c = page.evaluate("(()=>{const e=document.querySelectorAll('.ck-cal .cal-cell.today');return {n:e.length,sh:e[0]?getComputedStyle(e[0]).boxShadow:''}})()")
    check(c['n'] == 1 and 'inset' in c['sh'], f'у Календарі сьогоднішня клітинка без маркера: {c}')


def today_mobile(page):
    """Телефон: у Потоці одна сьогоднішня група з підписом «Сьогодні»"""
    freeze(page, DAY, patch=TODAY_OP)
    go_tab(page, 2)
    page.wait_for_timeout(200)
    g = page.locator('.m-day.today')
    check(g.count() == 1, f'груп «сьогодні» на телефоні {g.count()}, а не 1')
    check('Сьогодні' in g.locator('.flow-day-m').inner_text(), 'немає підпису «Сьогодні» на телефоні')


def phone_shot(page):
    """Телефон 375: знімок Огляду для контролю, що розмітка не змінилась (системний шрифт, без Inter)"""
    freeze(page, DAY)
    ff = page.evaluate("getComputedStyle(document.querySelector('.content')).fontFamily")
    check(ff.startswith('-apple-system'), f'на телефоні змінився font-family: {ff}')
    shot(page, 'ov-375.jpg')


def _tomorrow_cell(page, sel, day='9'):
    # клітинка дня (за замовчуванням 9-го, завтра від DAY) у сітці Календаря: текст рядка прогнозу
    return page.evaluate("""([sel,d])=>{const c=[...document.querySelectorAll(sel)].find(e=>{const n=e.closest('.cal-cell');if(!n)return false;const dn=n.querySelector('.cal-dn');return (dn||n.firstChild).textContent.trim()===d});return c?c.textContent:null}""", [sel, day])


def calendar_forecast_desktop(page):
    """ПК: прогноз балансу на кінець дня в клітинках лише сьогодні і в дні виплат (відгук власника 08.10), баланс на кожну дату в таблиці; горизонт покриває видимий місяць"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    go_tab(page, 3)
    page.wait_for_timeout(300)
    t = _tomorrow_cell(page, '.ck-cal .cal-bal', '8')
    print(f'      сьогодні (ПК): {t!r}')
    check(t and '₴' in t and any(ch.isdigit() for ch in t), f'у клітинці сьогоднішнього дня немає суми прогнозу з ₴: {t!r}')
    check(_tomorrow_cell(page, '.ck-cal .cal-bal') is None, 'у клітинці звичайного дня (9-го) лишилась сума прогнозу')
    t = _tomorrow_cell(page, '.ck-cal .cal-bal', '21')
    check(t and '₴' in t, f'у клітинці авансу 21-го немає суми прогнозу: {t!r}')
    # прогноз у майбутній клітинці без загального приглушення (контраст тексту як у muted)
    op = page.evaluate("""(()=>{const e=[...document.querySelectorAll('.ck-cal .cal-cell.future .cal-bal')][0];let o=1;for(let x=e;x;x=x.parentElement)o*=+getComputedStyle(x).opacity;return o})()""")
    check(op == 1, f'прогноз у майбутній клітинці приглушений opacity {op}')
    n = page.locator('.ck-cal .cal-bal').count()
    check(n == 2, f'сум прогнозу в жовтні {n}, а не 2 (сьогодні 8-го й аванс 21-го)')
    nb = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev[data-bal]')].map(e=>e.dataset.date)")
    check(len(nb) >= 8 and min(nb) == '2026-10-08', f'у таблиці баланс не на кожну дату від сьогодні: {nb}')
    # грудень: далі за 60 днів від 08.10, прогноз має покрити весь місяць
    for _ in range(2):
        page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
        page.wait_for_timeout(250)
    check('Грудень' in page.inner_text('.ck-month'), 'не перейшли на грудень')
    n = page.locator('.ck-cal .cal-bal').count()
    check(n == 2, f'у грудні сум прогнозу в клітинках {n}, а не 2 (аванс і зарплата)')
    rows = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev')].map(e=>[e.dataset.date,e.dataset.bal])")
    last = {}
    for d, b in rows:
        last[d] = b
    check(rows and all(b is not None for b in last.values()), f'у грудні таблиця без балансу на деякі дати: {last}')


def calendar_forecast_mobile(page):
    """Телефон 390: прогноз у тисячах («к») лише сьогодні і в дні виплат, клітинки не ширші за сітку"""
    page.set_viewport_size({'width': 390, 'height': 844})
    freeze(page, DAY)
    go_tab(page, 3)
    page.wait_for_timeout(300)
    t = _tomorrow_cell(page, '.cal-bal-m', '8')
    print(f'      сьогодні (телефон): {t!r}')
    check(t and t.endswith('к') and any(ch.isdigit() for ch in t), f'у клітинці сьогоднішнього дня немає суми «к»: {t!r}')
    check(_tomorrow_cell(page, '.cal-bal-m') is None, 'у клітинці звичайного дня (9-го) лишилась сума прогнозу')
    w = page.evaluate("""(()=>{const c=[...document.querySelectorAll('.cal-bal-m')].map(e=>e.closest('.cal-cell'));const g=c[0].parentElement.getBoundingClientRect();
return {gl:g.left,gr:g.right,l:Math.min(...c.map(x=>x.getBoundingClientRect().left)),r:Math.max(...c.map(x=>x.getBoundingClientRect().right)),clip:[...document.querySelectorAll('.cal-bal-m')].filter(e=>e.scrollWidth>e.clientWidth+0.5).length,sw:document.documentElement.scrollWidth}})()""")
    print(f'      сітка: {w}')
    check(w['l'] >= w['gl'] - 0.5 and w['r'] <= w['gr'] + 0.5, f'клітинки виходять за ширину сітки: {w}')
    check(w['clip'] == 0, f'сума прогнозу обрізана в {w["clip"]} клітинках')
    check(w['sw'] <= 390, f'горизонтальна прокрутка сторінки: {w["sw"]}')


ST = "(e)=>{const s=getComputedStyle(e);return {bg:s.backgroundColor,bl:s.borderLeftWidth+' '+s.borderLeftColor,bt:s.borderTopWidth+' '+s.borderTopColor,sh:s.boxShadow}}"


def drawer_sheet(page):
    """ПК, світла тема: дровер операції і модалка «Нова операція» білі, з волосяною межею #e6e8ec і тінню 0 8px 24px"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.evaluate("document.documentElement.setAttribute('data-theme','light')")
    go_tab(page, 2)
    page.wait_for_timeout(300)
    page.locator('.p-flow.desk .flow-row.tx').first.click()
    page.wait_for_timeout(400)
    d = page.locator('.drawer').first.evaluate(ST)
    check(d['bg'] == 'rgb(255, 255, 255)' and d['bl'] == '1px rgb(230, 232, 236)' and '0px 8px 24px' in d['sh'], f'дровер: {d}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    page.keyboard.press('n')
    page.wait_for_timeout(500)
    m = page.locator('.sheet').first.evaluate(ST)
    check(m['bg'] == 'rgb(255, 255, 255)' and m['bt'] == '1px rgb(230, 232, 236)' and '0px 8px 24px' in m['sh'], f'модалка: {m}')
    page.keyboard.press('Escape')


CHECKS = [
    ('ПК 1920: Inter, картки банків без кіл, кнопки без градієнтів, лінія прогнозу 1.5, без ваг 700+', 'desktop', fonts_cards_buttons),
    ('ПК: перемикач періоду в шапці сторінки, не в панелі', 'desktop', period_header),
    ('ПК: «Налаштування» пунктом панелі відкриває сторінку', 'desktop', settings_page),
    ('ПК: дровер і модалка білі з волосяною межею і мʼякою тінню', 'desktop', drawer_sheet),
    ('ПК: сьогоднішній день у Потоці і Календарі', 'desktop', today_desktop),
    ('Телефон: сьогоднішній день у Потоці', 'mobile', today_mobile),
    ('Телефон 375: Огляд без змін шрифту, знімок', 'mobile', phone_shot),
    ('ПК: прогноз балансу в клітинках Календаря, горизонт до кінця видимого місяця', 'desktop', calendar_forecast_desktop),
    ('Телефон 390: прогноз у клітинках Календаря в тисячах, без розповзання', 'mobile', calendar_forecast_mobile),
]
