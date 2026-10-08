# Жести на телефоні: свайп вкладок, свайп по операції, шит донизу, довге натискання «+», сума на тип, монетка на ціль,
# порядок цілей, банер-підказка. Рухи справжнім дотиком через CDP (helpers.touch_drag), а не мишею.
from helpers import SHOTS, TABS, check, center, go_tab, touch_drag

ACTIVE_TAB = "[...document.querySelectorAll('.tab-bar .tab-btn')].findIndex(b=>b.style.color==='var(--indigo)')"
FAB = "()=>{const b=document.querySelector('button.fab');const r=b.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}"
ADD = '.sheet:has-text("Нова транзакція")'


def vshot(page, name):
    """Кадр вʼюпорта (шити й банери fixed, full_page їх зсуває)."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), quality=80, type='jpeg')


def tab_idx(page):
    return page.evaluate(ACTIVE_TAB)


def swipe_tabs(page):
    check(tab_idx(page) == 0, 'старт не з Огляду')
    x, y = center(page, '.o-hero')
    # свайп вліво: наступна вкладка; кадр посеред анімації зсуву (150 мс)
    touch_drag(page, x + 120, y, x - 120, y + 8, after=40)
    vshot(page, 'gest-swipe-375.jpg')
    page.wait_for_timeout(300)
    check(tab_idx(page) == 1, f'свайп вліво не відкрив «{TABS[1][1]}»: вкладка {tab_idx(page)}')
    check(page.locator('.tab-page.swipe-l').count() == 1, 'немає анімації зсуву .swipe-l')
    # свайп вправо: назад
    x, y = 187, 420
    touch_drag(page, x - 120, y, x + 120, y)
    page.wait_for_timeout(300)
    check(tab_idx(page) == 0, 'свайп вправо не повернув на Огляд')
    # короткий рух (менше 60px) і вертикальний рух не перемикають
    x, y = center(page, '.o-hero')
    touch_drag(page, x + 25, y, x - 25, y)
    check(tab_idx(page) == 0, 'рух на 50px перемкнув вкладку')
    touch_drag(page, x + 40, y - 100, x - 40, y + 100)
    check(tab_idx(page) == 0, 'вертикальний рух перемкнув вкладку')
    # горизонтальний ряд рахунків (чипи) прокручується сам, вкладки не перемикає
    b = page.locator('.o-accs').first.bounding_box()
    check(b, 'немає ряду рахунків')
    touch_drag(page, b['x'] + b['width'] - 40, b['y'] + b['height'] / 2, b['x'] + 40, b['y'] + b['height'] / 2)
    check(tab_idx(page) == 0, 'свайп по ряду карток перемкнув вкладку')


def row_swipe(page):
    go_tab(page, 2)
    rows = page.locator('.p-flow .swipe-row')
    n0 = rows.count()
    check(n0 >= 5, f'у мобільному Потоці лише {n0} рядків зі свайпом')
    # демо постійних платежів стоїть вище за операції: рядок спершу в кадр
    rows.first.scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    b = rows.first.bounding_box()
    y = b['y'] + b['height'] / 2
    touch_drag(page, b['x'] + b['width'] - 30, y, b['x'] + 60, y)
    check(page.locator('.swipe-row.open').count() == 1, 'свайп вліво не відкрив дії рядка')
    acts = page.locator('.swipe-row.open .swipe-acts')
    ab = acts.bounding_box()
    check(ab and ab['x'] + ab['width'] <= 376 and ab['x'] > 150, f'дії рядка не видно праворуч: {ab}')
    check('Категорія' in acts.inner_text() and 'Видалити' in acts.inner_text(), 'немає «Категорія» і «Видалити»')
    check(tab_idx(page) == 2, 'свайп по рядку перемкнув вкладку')
    vshot(page, 'gest-row-375.jpg')
    # тап по рядку закриває дії, а не відкриває модалку
    page.locator('.swipe-row.open .swipe-main').click(position={'x': 250, 'y': 20})  # зсунутий на 168px: лівий край за екраном
    page.wait_for_timeout(300)
    check(page.locator('.swipe-row.open').count() == 0, 'тап не закрив дії рядка')
    check(page.locator('.overlay').count() == 0, 'тап по відкритому рядку відкрив модалку')
    # «Категорія» відкриває модалку операції
    touch_drag(page, b['x'] + b['width'] - 30, y, b['x'] + 60, y)
    page.locator('.swipe-row.open .swipe-cat').click()
    page.wait_for_timeout(300)
    check(page.locator('.overlay .sheet').count() == 1, '«Категорія» не відкрила модалку операції')
    page.locator('.overlay').click(position={'x': 10, 'y': 10})
    page.wait_for_timeout(300)
    # свайп вправо по відкритому рядку закриває
    touch_drag(page, b['x'] + b['width'] - 30, y, b['x'] + 60, y)
    touch_drag(page, b['x'] + 60, y, b['x'] + b['width'] - 30, y)
    check(page.locator('.swipe-row.open').count() == 0, 'свайп вправо не закрив дії рядка')
    check(tab_idx(page) == 2, 'закриття рядка свайпом вправо перемкнуло вкладку')
    # «Видалити» (підтвердження раннер приймає): рядків на один менше
    touch_drag(page, b['x'] + b['width'] - 30, y, b['x'] + 60, y)
    page.locator('.swipe-row.open .swipe-del').click()
    page.wait_for_timeout(400)
    check(rows.count() == n0 - 1, f'після «Видалити» рядків {rows.count()}, а не {n0 - 1}')
    # свайп вправо по закритому рядку: попередня вкладка
    b = rows.first.bounding_box()
    y = b['y'] + b['height'] / 2
    touch_drag(page, b['x'] + 40, y, b['x'] + b['width'] - 40, y)
    page.wait_for_timeout(250)
    check(tab_idx(page) == 1, 'свайп вправо по закритому рядку не перемкнув на Бюджет')


def sheet_drag(page):
    go_tab(page, 2)
    page.locator('button.fab').click()
    page.wait_for_timeout(400)
    check(page.locator(ADD).count() == 1, 'FAB у Потоці не відкрила форму операції')
    x, y = center(page, ADD + ' .sheet-grip')
    # короткий рух (40px): шит повертається
    touch_drag(page, x, y, x, y + 40)
    page.wait_for_timeout(250)
    check(page.locator(ADD).count() == 1, 'рух на 40px закрив шит')
    t = page.evaluate("getComputedStyle(document.querySelector('.sheet')).transform")
    check(t in ('none', 'matrix(1, 0, 0, 1, 0, 0)'), f'шит не повернувся: {t}')
    # більше 80px: закрито
    touch_drag(page, x, y, x, y + 160)
    page.wait_for_timeout(300)
    check(page.locator(ADD).count() == 0, 'потягування ручки на 160px не закрило шит')


def fab_long(page):
    go_tab(page, 2)
    x, y = page.evaluate(FAB)
    # довге натискання 650 мс без руху
    touch_drag(page, x, y, x, y, steps=1, hold=650)
    page.wait_for_timeout(300)
    q = page.locator('[role=dialog][aria-label="Швидке додавання"]')
    check(q.count() == 1, 'довге натискання FAB не відкрило мінішит')
    txt = q.inner_text()
    for t in ('Витрата', 'Дохід', 'Поповнення цілі'):
        check(t in txt, f'у мінішиті немає «{t}»')
    check(page.locator(ADD).count() == 0, 'довге натискання відкрило ще й форму операції')
    vshot(page, 'gest-fab-375.jpg')
    q.locator('button', has_text='Дохід').click()
    page.wait_for_timeout(400)
    check(page.locator(ADD).count() == 1, '«Дохід» не відкрив форму операції')
    check(page.locator('.amt-zone.in.on').count() == 1, 'форма відкрилась не з типом «Дохід»')
    page.locator(ADD + ' button', has_text='×').click()
    page.wait_for_timeout(300)
    # «Поповнення цілі» з мінішита
    touch_drag(page, x, y, x, y, steps=1, hold=650, after=500)
    page.locator('[aria-label="Швидке додавання"] button', has_text='Поповнення цілі').click()
    page.wait_for_timeout(400)
    check(page.locator('.sheet:has-text("Додати накопичення")').count() == 1, '«Поповнення цілі» не відкрило поповнення')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    # звичайний тап після довгого: форма операції, а не мінішит
    page.locator('button.fab').tap()
    page.wait_for_timeout(400)
    check(page.locator(ADD).count() == 1 and q.count() == 0, 'тап по FAB після довгого натискання не відкрив форму')


def amount_drop(page):
    go_tab(page, 2)
    page.locator('button.fab').click()
    page.wait_for_timeout(400)
    check(page.locator('.amt-zone.out.on').count() == 1, 'нова операція не з типом «Витрата»')
    page.fill('.amt-in', '1500')
    x0, y0 = center(page, '.amt-card')
    x1, y1 = center(page, '.amt-zone.in')

    def mid(pg):
        check(pg.locator('.amt-zone.in.hov').count() == 1, 'зона «Дохід» не підсвітилась під карткою')
        vshot(pg, 'gest-amount-375.jpg')
    touch_drag(page, x0, y0, x1, y1, steps=10, before_end=mid)
    check(page.locator('.amt-zone.in.on').count() == 1, 'перетягування суми на «Дохід» не поставило тип')
    check(page.locator('.amt-card.in').count() == 1, 'картка суми не стала «доходом»')
    t = page.evaluate("document.querySelector('.amt-card').style.transform")
    check(not t, f'картка суми не повернулась: {t!r}')
    check(page.input_value('.amt-in') == '1500', 'сума загубилась після перетягування')
    # назад на «Витрата» (шит прикріплений знизу і став нижчим: менше категорій доходу, тож координати заново) і тап по зоні
    x0, y0 = center(page, '.amt-card')
    x2, y2 = center(page, '.amt-zone.out')
    touch_drag(page, x0, y0, x2, y2, steps=10)
    check(page.locator('.amt-zone.out.on').count() == 1, 'перетягування на «Витрата» не поставило тип')
    page.locator('.amt-zone.in').click()
    page.wait_for_timeout(200)
    check(page.locator('.amt-zone.in.on').count() == 1, 'тап по зоні «Дохід» не працює')


def coin_goal(page):
    go_tab(page, 4)
    check(page.locator('.coin').count() == 1, 'на Цілях немає монетки')
    tile = page.locator('[data-gid]').nth(1)
    name = tile.get_attribute('aria-label').split(',')[0]
    tile.scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    x0, y0 = center(page, '.coin')
    b = tile.bounding_box()
    x1, y1 = b['x'] + b['width'] / 2, b['y'] + min(b['height'] / 2, 812 - b['y'] - 20)

    def mid(pg):
        check(pg.locator('.drop-hov').count() == 1, 'плитка цілі не підсвітилась під монеткою')
        vshot(pg, 'gest-coin-375.jpg')
    touch_drag(page, x0, y0, x1, y1, steps=12, before_end=mid)
    page.wait_for_timeout(300)
    sv = page.locator('.sheet:has-text("Поповнення цілі")')
    check(sv.count() == 1, 'монетка на ціль не відкрила поповнення')
    check(name in sv.inner_text(), f'поповнення не для цілі «{name}»')
    check(page.locator('.drop-hov').count() == 0, 'підсвітка плитки лишилась після відпускання')
    # сума і Enter: запис у локальний журнал (превʼю без БД)
    sv.locator('input[type=number]').fill('700')
    sv.locator('input[type=number]').press('Enter')
    page.wait_for_timeout(400)
    check(sv.count() == 0, 'Enter не зберіг поповнення')


def goal_order(page):
    go_tab(page, 4)
    names = lambda: [x.split(',')[0] for x in page.eval_on_selector_all('[data-gid]', 'els=>els.map(e=>e.getAttribute("aria-label"))')]
    n0 = names()
    check(len(n0) >= 2, f'цілей лише {len(n0)}')
    a = page.locator('[data-gid]').nth(0)
    a.scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    ba = a.bounding_box()
    bb = page.locator('[data-gid]').nth(1).bounding_box()
    x = ba['x'] + ba['width'] / 2
    # довге натискання на першу плитку і перетягування на другу
    touch_drag(page, x, ba['y'] + 40, x, bb['y'] + bb['height'] / 2, steps=12, hold=650)
    page.wait_for_timeout(300)
    n1 = names()
    check(n1[0] == n0[1] and n1[1] == n0[0], f'порядок не змінився: {n0} -> {n1}')
    check(page.locator('.overlay').count() == 0, 'перетягування плитки відкрило ціль')
    check(page.locator('.gtile.lift').count() == 0, 'плитка лишилась піднятою')


def banner_once(page):
    tip = page.locator('.gest-tip')
    check(tip.count() == 1, 'банер жестів не показався при першому вході')
    t = tip.inner_text()
    for w in ('Свайп', 'шит', 'утримуйте +'):
        check(w in t, f'у банері немає «{w}»')
    vshot(page, 'gest-banner-375.jpg')
    tip.locator('button', has_text='Зрозуміло').click()
    page.wait_for_timeout(200)
    check(tip.count() == 0, '«Зрозуміло» не прибрало банер')
    check(page.evaluate("localStorage.getItem('gestures_seen')") == '1', 'немає gestures_seen')
    page.reload()
    page.wait_for_selector('.tab-bar', timeout=20000)
    page.wait_for_timeout(400)
    check(tip.count() == 0, 'банер показався вдруге')


CHECKS = [
    ('Свайп вліво/вправо перемикає вкладки', 'mobile', swipe_tabs),
    ('Свайп по операції: Категорія і Видалити', 'mobile', row_swipe),
    ('Шит закривається потягуванням ручки', 'mobile', sheet_drag),
    ('Довге натискання + відкриває мінішит', 'mobile', fab_long),
    ('Сума на «Дохід» перетягуванням', 'mobile', amount_drop),
    ('Монетка на ціль відкриває поповнення', 'mobile', coin_goal),
    ('Порядок цілей довгим натисканням', 'mobile', goal_order),
    ('Банер жестів показується раз', 'mobile', banner_once, {'gestures': True}),
]
