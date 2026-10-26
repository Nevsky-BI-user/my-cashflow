# Оформлення ПК: 10.10.2026 користувач повернув тіні, шари й виразні KPI, зберігши чинну палітру.
# період у шапці сторінки (Огляд, Бюджет, Потік, Календар), «Налаштування» пунктом панелі і сторінкою (не діалогом);
# сьогоднішній день у Потоці (ПК і телефон) і в Календарі; прогноз балансу в клітинках Календаря; знімки ov-1920, ov-dark-1920, ov-375
from helpers import check, dialog, freeze, go_tab, shot, open_calendar_day

DAY = '2026-10-08'
# фікстура: остання демо-операція на «31-ше» число, txDemo стискає дати поточного місяця до сьогодні, тож вона лягає саме на 08.10
TODAY_OP = [("[24,'Сільпо',2133,", "[31,'Сільпо',2133,")]

FONT = """(async()=>{await document.fonts.ready;
const ff=getComputedStyle(document.querySelector('.content')).fontFamily;
const loaded=[...document.fonts].some(f=>f.family.replace(/["']/g,'')==='Inter'&&f.status==='loaded');
const link=!!document.querySelector('link[rel=stylesheet][href*="fonts.googleapis.com"][href*="Inter"]');
return {ff,loaded,link}})()"""
CARDS = """[...document.querySelectorAll('.dv-cards .bcard')].map(e=>{const s=getComputedStyle(e);
return {bi:s.backgroundImage,bg:s.backgroundColor,h:Math.round(e.getBoundingClientRect().height),sh:s.boxShadow,deco:e.querySelectorAll(':scope > span[aria-hidden]').length}})"""
BTN = "(sel)=>{const e=document.querySelector(sel);if(!e)return null;const s=getComputedStyle(e);return {bi:s.backgroundImage,bg:s.backgroundColor,fw:s.fontWeight}}"


def fonts_cards_buttons(page):
    """Inter з фолбеком, компактні картки з глибиною, виразні KPI, лінія прогнозу 1.5."""
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
        # v181: на ПК картка банку знову в градієнті свого банку.
        check('gradient' in c['bi'], f'картка банку без градієнта банку: {c}')
        check(c['sh'] != 'none', f'картка банку без тіні: {c}')
    bank_content = page.locator('.dv-cards .bcard').evaluate_all("""es=>es.map(e=>{const b=e.getBoundingClientRect();return {height:b.height,visible:[...e.querySelectorAll('.bcard-sum,.bcard-name,.bcard-avail,.bcard-due,.bcard-updated,.ms-compact-warning')].every(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=b.top&&r.bottom<=b.bottom+1&&r.left>=b.left&&r.right<=b.right+1&&n.scrollWidth<=n.clientWidth+1})}})""")
    check(bank_content and all(c['visible'] for c in bank_content), f'підписи банків обрізані: {bank_content}')
    for sel in ('.side-add', '.dact'):
        b = page.evaluate(BTN, sel)
        check(b and b['bg'] != 'rgba(0, 0, 0, 0)', f'{sel}: немає акцентної поверхні {b}')
        check(b['fw'] in ('500', '600'), f'{sel}: вага {b["fw"]}, а не 500/600')
    sw = page.evaluate("(()=>{const e=document.querySelector('.dv-fc .fc-past');return e?getComputedStyle(e).strokeWidth:null})()")
    check(sw == '1.5px', f'лінія прогнозу {sw}, а не 1.5px')
    # Головні суми виділено; допоміжний текст лишається читабельним.
    weights = page.evaluate("""[...document.querySelectorAll('.dv-kpi-v')].map(e=>+getComputedStyle(e).fontWeight)""")
    check(weights and min(weights) >= 650, f'KPI без виразного акценту: {weights}')
    support = page.evaluate("""[...document.querySelectorAll('.dv-wallet,.kpi-rows,.dv-recent')].filter(e=>e.offsetParent).map(e=>parseFloat(getComputedStyle(e).fontSize))""")
    check(support and min(support) >= 11.5, f'допоміжний текст надто дрібний: {support}')
    page.mouse.move(2, 2)
    shot(page, 'ov-1920.jpg', full=False)
    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(300)
    bg = page.evaluate("()=>{const s=getComputedStyle(document.body),b=getComputedStyle(document.body,'::before');return {radial:(s.backgroundImage.match(/radial-gradient\\(/g)||[]).length,glass:b.backgroundImage}}")
    check(bg['radial'] == 2 and bg['glass'] == 'none', f'темне тло має зберігати два делікатні градієнти без білого серпанку: {bg}')
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
        caption='календарний місяць' if i==1 else 'зарплата'
        check(page.locator('.dtitle .side-arr').count() == 2 and caption in page.inner_text('.dtitle .dtitle-sub'), f'{nm}: стрілки або підпис періоду')
        if i==1:
            check(page.locator('.p-budget').get_attribute('data-month')==DAY[:7]+'-01','місяць Бюджету не відповідає його шапці')
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
    check([x.strip() for x in items] == ['Огляд', 'Бюджет', 'Операції', 'Платежі', 'Заощадження', 'Налаштування'], f'пункти навігації: {items}')
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
    page.locator('.side-nav .side-item', has_text='Операції').click()
    page.wait_for_timeout(300)
    check(sp.count() == 0 and page.inner_text('.dtitle h1').strip() == 'Операції', 'перехід на «Потік» не закрив сторінку налаштувань')


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
    # грудень: далі за 60 днів від 08.10, прогноз має покрити весь місяць
    for _ in range(2):
        page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
        page.wait_for_timeout(250)
    check('Грудень' in page.inner_text('.ck-month'), 'не перейшли на грудень')
    n = page.locator('.ck-cal .cal-bal').count()
    check(n == 2, f'у грудні сум прогнозу в клітинках {n}, а не 2 (аванс і зарплата)')
    from helpers import finance_ref, num
    projection=finance_ref(page)
    for cell in page.locator('.ck-cal .cal-cell:has(.cal-bal)').all():
        iso=cell.get_attribute('data-date')
        expected=next(d for d in projection['days'] if d['date']==iso)
        shift=projection['snapshot']['positiveOwnCents']-projection['snapshot']['cashCents']
        check(abs(num(cell.locator('.cal-bal').inner_text())-(expected['netCents']+shift)/100)<=1, f'{iso}: horizon balance not from projection')
    details=open_calendar_day(page,'2026-12-31')
    check(details.is_visible(),'last day beyond 60-day horizon inaccessible')


def calendar_forecast_mobile(page):
    """Телефон 390: баланс на кінець дня у тисячах («к») у кожній клітинці від сьогодні (v149, раніше лише сьогодні і в дні виплат), клітинки не ширші за сітку"""
    page.set_viewport_size({'width': 390, 'height': 844})
    freeze(page, DAY)
    go_tab(page, 3)
    page.wait_for_timeout(300)
    # окремий мобільний календар v142 (.cm-calendar): сума прогнозу в .cal-bal (раніше .cal-bal-m)
    t = _tomorrow_cell(page, '.cm-calendar .cal-bal', '8')
    print(f'      сьогодні (телефон): {t!r}')
    check(t and t.endswith('к') and any(ch.isdigit() for ch in t), f'у клітинці сьогоднішнього дня немає суми «к»: {t!r}')
    n9 = _tomorrow_cell(page, '.cm-calendar .cal-bal')
    check(n9 and n9.endswith('к'), f'у клітинці звичайного дня (9-го) немає балансу на кінець дня (v149): {n9!r}')
    w = page.evaluate("""(()=>{const c=[...document.querySelectorAll('.cm-calendar .cal-bal')].map(e=>e.closest('.cal-cell'));const g=c[0].parentElement.getBoundingClientRect();
return {gl:g.left,gr:g.right,l:Math.min(...c.map(x=>x.getBoundingClientRect().left)),r:Math.max(...c.map(x=>x.getBoundingClientRect().right)),clip:[...document.querySelectorAll('.cm-calendar .cal-bal')].filter(e=>e.scrollWidth>e.clientWidth+0.5).length,sw:document.documentElement.scrollWidth}})()""")
    print(f'      сітка: {w}')
    check(w['l'] >= w['gl'] - 0.5 and w['r'] <= w['gr'] + 0.5, f'клітинки виходять за ширину сітки: {w}')
    check(w['clip'] == 0, f'сума прогнозу обрізана в {w["clip"]} клітинках')
    check(w['sw'] <= 390, f'горизонтальна прокрутка сторінки: {w["sw"]}')


ST = "(e)=>{const s=getComputedStyle(e),p=document.createElement('span');p.style.borderColor='var(--border)';e.appendChild(p);const border=getComputedStyle(p).borderTopColor;p.remove();return {bg:s.backgroundColor,bl:s.borderLeftWidth+' '+s.borderLeftColor,bt:s.borderTopWidth+' '+s.borderTopColor,border,sh:s.boxShadow}}"


def drawer_sheet(page):
    """ПК, світла тема: дровер операції і модалка «Нова операція» білі, з волосяною межею #E5E5EA (v155, Apple; було #e6e8ec) і тінню 0 8px 24px"""
    freeze(page, DAY)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.evaluate("document.documentElement.setAttribute('data-theme','light')")
    go_tab(page, 2)
    page.wait_for_timeout(300)
    page.locator('.p-flow.desk .flow-row.tx').first.click()
    page.wait_for_timeout(400)
    d = page.locator('.drawer').first.evaluate(ST)
    check(d['bg'] == 'rgb(255, 255, 255)' and d['bl'] == '1px ' + d['border'] and d['sh'] != 'none' and 'inset' in d['sh'], f'дровер: {d}')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    page.keyboard.press('n')
    page.wait_for_timeout(500)
    m = page.locator('.sheet').first.evaluate(ST)
    check(m['bg'] == 'rgb(255, 255, 255)' and m['bt'] == '1px ' + m['border'] and m['sh'] != 'none', f'модалка: {m}')
    page.keyboard.press('Escape')


CHECKS = [
    ('ПК 1920: Inter, компактні картки з шарами й тінями, виразні KPI, лінія прогнозу 1.5', 'desktop', fonts_cards_buttons),
    ('ПК: перемикач періоду в шапці сторінки, не в панелі', 'desktop', period_header),
    ('ПК: «Налаштування» пунктом панелі відкриває сторінку', 'desktop', settings_page),
    ('ПК: дровер і модалка білі з волосяною межею і мʼякою тінню', 'desktop', drawer_sheet),
    ('ПК: сьогоднішній день у Потоці і Календарі', 'desktop', today_desktop),
    ('Телефон: сьогоднішній день у Потоці', 'mobile', today_mobile),
    ('Телефон 375: Огляд без змін шрифту, знімок', 'mobile', phone_shot),
    ('ПК: прогноз балансу в клітинках Календаря, горизонт до кінця видимого місяця', 'desktop', calendar_forecast_desktop),
    ('Телефон 390: прогноз у клітинках Календаря в тисячах, без розповзання', 'mobile', calendar_forecast_mobile),
]
