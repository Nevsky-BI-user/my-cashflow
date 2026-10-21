# Рахунки: банківські картки на ПК-Огляді (1280, 1920), форма рахунку, зарплатний рахунок лише один; колода карток на телефоні
import re as _re
from datetime import datetime as _dt

from helpers import check, dialog, shot, touch_drag

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
KPI_H = "[...document.querySelectorAll('.dv-kpis .dv-kpi')].map(e=>Math.round(e.getBoundingClientRect().height))"
# текстові вузли ПК-Огляду поза банківськими картками, дрібніші за 11.5px (підписи 11.5, основний 13; дизайн ПК v135);
# підписи мін./макс. і осі всередині графіка прогнозу 11px за рішенням власника (svg text), їх не рахуємо
SMALL = """[...document.querySelectorAll('.p-overview.desk *')].filter(e=>!e.closest('.bcard')&&!e.closest('svg')&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))
.map(e=>[e.textContent.trim().slice(0,20),parseFloat(getComputedStyle(e).fontSize)]).filter(x=>x[1]<11.5)"""


def num(t):
    return t.replace(' ', ' ').replace(' ', ' ').strip()


def desktop(page):
    cards = page.locator('.dv-cards .bcard')
    check(cards.count() == 3, f'на ПК {cards.count()} карток замість 3')
    # Непримітний «+» стоїть праворуч після всіх рахунків.
    check(page.locator('.dv-cards .bcard-add').count() == 1, 'у ряду немає одного «+» додавання рахунку')
    add = page.locator('.dv-cards .dv-acc-add')
    check(add.count() == 1 and add.inner_text().strip() == '+', 'немає малого «+» після карток')
    check(page.locator('.dv-acc-head .dv-acc-add').count() == 0, 'додавання рахунку лишилось у заголовку')
    last, plus = cards.last.bounding_box(), add.bounding_box()
    check(plus['x'] >= last['x'] + last['width'] - 1 and plus['width'] <= 64, '«+» не праворуч від усіх карток або завеликий')
    for i in range(3):
        w = cards.nth(i).bounding_box()
        check(w['width'] >= 240 and w['height'] >= 142, f'картка {i + 1}: {w["width"]:.0f}x{w["height"]:.0f}, замала для підписів')
        metrics = cards.nth(i).evaluate("""e=>{const r=e.getBoundingClientRect(),name=e.querySelector('.bcard-bank').getBoundingClientRect(),sum=e.querySelector('.bcard-sum').getBoundingClientRect();return {gap:sum.top-name.bottom,clipped:[...e.querySelectorAll('.bcard-bank,.bcard-sum,.ms-txt,.ms-warn')].some(x=>{const b=x.getBoundingClientRect();return b.bottom>r.bottom+1||b.right>r.right+1||x.scrollWidth>x.clientWidth+1||x.scrollHeight>x.clientHeight+1})}}""")
        check(metrics['gap'] >= 10 and not metrics['clipped'], f'картка {i + 1}: замалий відступ або обрізані підписи: {metrics}')
    check(cards.first.locator('.ms-wrap').count() == 1 and page.locator('.o-ms-list').count() == 0, 'поріг витрат має бути всередині картки Ощаду')
    # monobank: світла картка, «дебетова», кнопка ↻ без БД не падає й оновлює час
    mono = page.locator('.dv-cards .bcard-mono')
    check(mono.count() == 1, 'немає картки monobank')
    mt = mono.inner_text().lower()
    check('monobank' in mt and 'дебетова' in mt and 'оновлено' in mt, f'картка monobank: {mt!r}')
    # Білі картки; банк визначають кольоровий край і монограма.
    materials = cards.evaluate_all("""es=>es.map(e=>{const s=getComputedStyle(e);return {
      edge:s.getPropertyValue('--bank-edge').trim(),mark:e.querySelector('.bank-mark')?.textContent,
      background:s.backgroundColor,white:(s.backgroundColor.match(/[\\d.]+/g)||[]).slice(0,3).every(v=>Number(v)>=230)
    }})""")
    check(all(m['white'] and m['mark'] and m['edge'] for m in materials)
          and len({m['edge'] for m in materials}) == 3,
          f'Bank material, monogram or identifying edge missing: {materials}')
    paint = mono.evaluate("""e=>{const probe=document.createElement('span');
      probe.style.color='var(--head)';e.appendChild(probe);
      const expected=getComputedStyle(probe).color;probe.remove();
      return {expected,actual:getComputedStyle(e.querySelector('.bcard-sum')).color,
        shadow:getComputedStyle(e).boxShadow};}""")
    check(paint['shadow'] != 'none' and paint['actual'] == paint['expected'],
          f'Bank amount differs from its text token or has no shadow: {paint}')
    upd = page.locator('.dtitle .dv-mono-upd')
    check(upd.count() == 1 and 'Оновити рахунки' in upd.inner_text(), 'немає кнопки «Оновити рахунки» вгорі')
    upd.click()
    page.wait_for_timeout(300)
    hm = _re.search(r'оновлено (\d\d:\d\d)', mono.inner_text())
    now = _dt.now()
    check(hm and abs((now.hour * 60 + now.minute) - (int(hm.group(1)[:2]) * 60 + int(hm.group(1)[3:]))) <= 1,
          f'↻ без БД не оновив час: {hm.group(1) if hm else None}, зараз {now:%H:%M}')
    check(page.locator('.dv-mono-msg').count() == 0, 'без БД зʼявилось повідомлення про помилку monobank')
    hs = page.evaluate(KPI_H)
    check(len(hs) == 3 and max(hs) - min(hs) <= 1, f'KPI не 3 однакової висоти: {hs}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    page.mouse.move(2, 2)
    shot(page, 'ov-1280.jpg', full=False)
    # баланс Ощадбанку: повзунок 7300 і «Зберегти»
    cards.first.click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    check(d.count() == 1, 'клік по картці не відкрив форму рахунку')
    rng = d.locator('input.nf-range').first
    rng.evaluate(SETR, 7300)
    page.wait_for_timeout(150)
    shot(page, 'acc-edit-1280.jpg')
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(300)
    check(d.count() == 0, 'форма не закрилась після «Зберегти»')
    s = num(cards.first.locator('.bcard-sum').inner_text())
    check(s == '7 300 ₴', f'після збереження на картці «{s}», а не «7 300 ₴»')
    # зарплатний рахунок лише один: увімкнути на monobank
    cards.nth(2).click()
    page.wait_for_timeout(300)
    d.locator('[role=switch]').click()
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(300)
    gold = [cards.nth(i).inner_text().count('зарплата сюди') for i in range(3)]
    check(gold == [0, 0, 1], f'позначка «зарплата сюди» по картках: {gold}, очікували лише на третій')
    # Esc закриває форму
    cards.first.click()
    page.wait_for_timeout(300)
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив форму рахунку')


def wide(page):
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(400)
    cw = page.evaluate("document.querySelector('.content').getBoundingClientRect().width")
    check(page.evaluate(NO_HSCROLL) and cw <= page.evaluate('innerWidth - 220'), f'ширина контенту {cw:.0f}px виходить за доступну область')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    fs = page.evaluate("getComputedStyle(document.querySelector('.content')).fontSize")
    check(fs == '13px', f'базовий шрифт .content {fs}, а не 13px')
    small = page.evaluate(SMALL)
    check(not small, f'на ПК-Огляді є текст дрібніший за 12px: {small[:5]}')
    page.mouse.move(2, 2)
    shot(page, 'ov-1920.jpg', full=False)


def mobile(page):
    # Картки гортаються жестом без прокрутки й відкривають історію.
    row = page.locator('.o-account-deck')
    check(row.count() == 1, 'на телефоні немає ряду рахунків')
    check(row.locator('.o-bank-card').count() == 3, 'у ряду не 3 рахунки')
    check(row.get_attribute('data-noswipe') == '1', 'ряд рахунків без data-noswipe')
    cards = row.locator('.o-bank-card')
    cards.first.scroll_into_view_if_needed()
    check(row.evaluate("e=>getComputedStyle(e).overflowX") == 'hidden', 'Карусель має приховувати прокрутку')
    check('Гортайте' not in page.locator('.o-account-section').inner_text(), 'Лишилася підказка гортання')
    check('Операції' not in row.inner_text(), 'На картках лишився підпис операцій')
    identities = []
    # Демореквізити належать рахунку; банк більше не визначає номер картки.
    for account in page.evaluate('ACCOUNTS_DEMO.map(a=>({bank:a.bank,card_last4:a.card_last4}))'):
        bank, suffix = account['bank'], account['card_last4']
        card = row.locator('.bank-' + bank)
        check(card.locator('.o-bank-number').inner_text() == '**** **** **** ' + suffix, bank + ': невірна маска номера')
        material = card.evaluate("""e=>({paint:getComputedStyle(e).backgroundImage,mark:e.querySelector('.bank-mark')?.textContent})""")
        check('gradient' in material['paint'] and material['mark'], bank + ': bank surface or mark missing')
        identities.append(material['paint'])
    check(len(set(identities)) == 3, 'Banks must retain distinct colored surfaces')
    check(row.locator('.bank-oschad .ms-wrap').count() == 1 and page.locator('.o-ms-list').count() == 0, 'поріг витрат має бути всередині картки Ощаду')
    rect = row.bounding_box()
    first = cards.first.bounding_box()
    second = cards.nth(1).bounding_box()
    check(first['x'] >= rect['x'] and first['x'] + first['width'] <= rect['x'] + rect['width'], 'Основна картка обрізана')
    check(second['x'] < rect['x'] + rect['width'] and second['x'] < first['x'] + first['width'], 'Немає видимого краю сусідньої картки')
    x, y = first['x'] + first['width'] * .75, first['y'] + first['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 150, y, steps=12)
    page.mouse.up()
    page.wait_for_timeout(550)
    check(cards.nth(1).get_attribute('aria-current') == 'true', 'Жест не перемкнув картку')
    check(page.locator('.account-history-sheet').count() == 0, 'Жест помилково відкрив історію')
    check(row.evaluate('e=>e.scrollLeft') == 0, 'Карусель створила прокрутку')
    touch_drag(page, rect['x'] + 70, y, rect['x'] + 240, y, after=550)
    check(cards.first.get_attribute('aria-current') == 'true', 'Дотик не повернув першу картку')
    check(page.locator('.account-history-sheet').count() == 0, 'Дотик помилково відкрив історію')
    cards.first.focus()
    page.keyboard.press('ArrowRight')
    page.wait_for_timeout(550)
    page.keyboard.press('ArrowRight')
    page.wait_for_timeout(550)
    check(cards.nth(2).get_attribute('aria-current') == 'true', 'Стрілка не перемкнула картку')
    page.emulate_media(reduced_motion='reduce')
    check(row.locator('.o-stack-item').first.evaluate('e=>getComputedStyle(e).transitionDuration') in ('0s', '1e-05s'), 'Рух не вимкнений при reduced-motion')
    page.keyboard.press('ArrowLeft')
    page.keyboard.press('ArrowLeft')
    page.wait_for_timeout(100)
    check(cards.first.get_attribute('aria-current') == 'true', 'Не вдалося повернути першу картку')
    page.emulate_media(reduced_motion='no-preference')
    cards.first.click()
    history = page.locator('.account-history-sheet')
    history.wait_for(state='visible')
    check('Усі операції' in history.inner_text(), 'картка не відкрила історію операцій')
    check(history.locator('.account-amounts').count() == 1, 'історія без балансу і боргу')
    rows = history.locator('.account-history-row')
    rows.first.wait_for(state='visible')
    check(rows.count() > 0, 'історія Ощаду не показала демооперації')
    rows.first.click()
    check(history.count() == 0, 'історія лишилася відкритою під операцією та може показати застарілі дані')
    check(dialog(page, 'Операція').count() == 1, 'з історії не відкрилася операція')
    dialog(page, 'Операція').get_by_role('button', name='Закрити', exact=True).click()
    cards.first.click()
    history.wait_for(state='visible')
    history.locator('.account-history-edit').click()
    check(dialog(page, 'Рахунок').count() == 1, 'історія не відкрила редагування')
    page.keyboard.press('Escape')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол сторінки на 375')
    # v145: на початку екрана плитки KPI; «Бюджет періоду» з періодом DD.MM-DD.MM і рядком «Доступно до» (раніше «Доступно після виплати», .dv-free)
    first = page.evaluate("(document.querySelector('.p-overview')||{}).firstElementChild?.className||''")
    check('projection-summary' in first, f'першим на Огляді не підсумок доступних коштів: {first!r}')
    free = page.locator('.p-overview .projection-summary .kpi-budget').inner_text().lower()  # підпис у верхньому регістрі (text-transform)
    # v148: без дат періоду; рядки «Доступно» і «Щоденні витрати ... /день»
    check('бюджет періоду' in free and '₴' in free and 'доступно' in free and '/день' in free and not _re.search(r'\d\d\.\d\d-\d\d\.\d\d', free), f'«Бюджет періоду» без рядків «Доступно» і «/день»: {free!r}')
    shot(page, 'ov-375.jpg')


IN_VIEW = "e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=0&&r.bottom<=innerHeight+1&&r.left>=0&&r.right<=innerWidth+1}"


def _add_cash(page, add, count, where):
    # «+» відкриває форму «Новий рахунок»; вид «Готівка» доступний, збережений рахунок зʼявляється в ряду
    before = count()
    add.click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    check(d.count() == 1 and 'Новий рахунок' in d.inner_text(), f'{where}: «+» не відкрив форму «Новий рахунок»')
    kind = d.locator('[role=group][aria-label="Тип"] button', has_text='Готівка')
    check(kind.count() == 1, f'{where}: у формі немає виду «Готівка»')
    kind.click()
    check(kind.get_attribute('aria-pressed') == 'true', f'{where}: вид «Готівка» не вибрався')
    d.locator('input[type=text]').first.fill('Готівка вдома')
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(400)
    check(d.count() == 0, f'{where}: форма не закрилась після «Зберегти»')
    check(count() == before + 1, f'{where}: рахунків у ряду {count()}, очікували {before + 1}')


def cash_desktop(page):
    # картки рахунків на ПК-Огляді видно без прокрутки на 1280×800 і 1920×1080, «+ Рахунок» поруч
    for w, hh in ((1920, 1080), (1280, 800)):
        page.set_viewport_size({'width': w, 'height': hh})
        page.wait_for_timeout(400)
        row = page.locator('.p-overview .dv-accs')
        check(row.count() == 1, f'{w}×{hh}: на Огляді немає ряду карток рахунків')
        check(page.locator('.dv-cards .bcard').count() == 3, f'{w}×{hh}: у ряду не 3 картки')
        check(row.evaluate(IN_VIEW), f'{w}×{hh}: ряд карток рахунків не в межах екрана')
        check(page.locator('.dv-acc-add').evaluate(IN_VIEW), f'{w}×{hh}: «+ Рахунок» не видно')
    _add_cash(page, page.locator('.dv-acc-add'), lambda: page.locator('.dv-cards .bcard').count(), 'ПК')
    check(page.locator('.dv-cards .bcard', has_text='Готівка вдома').count() == 1, 'ПК: картки «Готівка вдома» немає в ряду')
    # вид зберігся: повторне відкриття картки показує «Готівка» вибраною
    page.locator('.dv-cards .bcard', has_text='Готівка вдома').click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    pressed = d.locator('[role=group][aria-label="Тип"] button[aria-pressed=true]').inner_text()
    check(pressed == 'Готівка', f'ПК: збережений рахунок має вид «{pressed}», а не «Готівка»')
    page.keyboard.press('Escape')


def cash_mobile(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(400)
    row = page.locator('.p-overview .o-account-section')
    cards = row.locator('.o-bank-card')
    check(row.count() == 1, '390: немає секції рахунків')
    cards.first.scroll_into_view_if_needed()
    check(cards.first.evaluate(IN_VIEW), '390: до картки рахунку не можна догортати без обрізання')
    add = row.locator('.o-stack-add button')
    check(add.count() == 1, '390: у ряду рахунків немає «+»')
    cards.first.focus()
    page.keyboard.press('End')
    page.wait_for_timeout(550)
    add.scroll_into_view_if_needed()
    _add_cash(page, add, cards.count, '390')
    check(row.locator('.o-bank-card', has_text='Готівка вдома').count() == 1, 'нової картки немає в колоді')


CHECKS = [
    ('Картки на ПК, форма, баланс, зарплатний один', 'desktop', desktop),
    ('ПК 1920: адаптивна ширина, шрифт 14, без дрібного', 'desktop', wide),
    ('Картки на телефоні: жест, номери, кольорова колода та історія', 'mobile', mobile),
    ('Рахунки на ПК 1280×800 і 1920×1080: ряд видно, «+» додає готівку', 'desktop', cash_desktop),
    ('Рахунки на телефоні 390: ряд видно, «+» додає готівку', 'mobile', cash_mobile),
]
