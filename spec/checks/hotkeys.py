# Гарячі клавіші на ПК: N, Esc, S, T, ?, і поле вводу їх не віддає
import re

from helpers import check, dialog, go_tab

ADD = '.sheet:has-text("Нова транзакція")'


def add_and_esc(page):
    page.keyboard.press('n')
    page.wait_for_timeout(300)
    check(page.locator(ADD).count() == 1, 'N не відкрила «Нова транзакція»')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(page.locator(ADD).count() == 0, 'Esc не закрив «Нова транзакція»')


def settings_menu(page):
    # на ПК налаштування окремою сторінкою (не діалог); Esc повертає на вкладку
    page.keyboard.press('s')
    page.wait_for_timeout(400)
    d = page.locator('.set-page')
    check(d.count() == 1 and dialog(page, 'Налаштування').count() == 0, 'S не відкрила сторінку налаштувань')
    n = d.locator('nav button').count()
    check(n == 9, f'у меню {n} пунктів, а не 9')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив сторінку налаштувань')


def theme_cycle(page):
    order = ['dark', 'light', 'auto']
    start = page.evaluate("localStorage.getItem('theme')") or 'dark'
    check(start in order, f'початкова тема {start!r}')
    seen = []
    for _ in range(3):
        page.keyboard.press('t')
        page.wait_for_timeout(150)
        seen.append((page.evaluate("localStorage.getItem('theme')"),
                     page.evaluate("document.documentElement.getAttribute('data-theme')")))
    vals = [s[0] for s in seen]
    i = order.index(start)
    want = [order[(i + k) % 3] for k in (1, 2, 3)]
    check(vals == want, f'T: тема по колу {vals}, очікували {want}')
    # контекст із color_scheme=dark, тож auto дає dark
    eff = {'dark': 'dark', 'light': 'light', 'auto': 'dark'}
    got = [s[1] for s in seen]
    check(got == [eff[v] for v in want], f'T: data-theme {got}')


def tour(page):
    page.keyboard.press('Shift+Slash')
    page.wait_for_timeout(400)
    d = dialog(page, 'Підказки')
    check(d.count() == 1, '? не відкрив тур')
    check('1 з 5' in d.inner_text(), 'тур не з 5 кроків (немає «1 з 5»)')
    for _ in range(4):
        d.locator('button', has_text='Далі').click()
        page.wait_for_timeout(150)
    check('5 з 5' in d.inner_text(), 'після 4 «Далі» не крок 5 з 5')
    d.locator('button', has_text='Готово').click()
    page.wait_for_timeout(300)
    check(d.count() == 0, '«Готово» не закрило тур')
    check(page.evaluate("localStorage.getItem('tour_done')") is not None, 'після «Готово» немає tour_done')


def field_keeps_keys(page):
    # поле пошуку на ПК-Операціях (v142: поле «Що як» на Заощадженнях прибрано разом із прогнозом строків,
    # docs/redesign/projection-contract.md); цифри й літери в полі не перемикають екран і не відкривають вікон
    go_tab(page, 2)
    inp = page.locator('.content input[type=search][aria-label="Пошук операцій"]')
    check(inp.count() == 1, 'на екрані Операції немає поля «Пошук операцій»')
    inp.click()
    inp.press('End')
    before = inp.input_value()
    theme0 = page.evaluate("localStorage.getItem('theme')")
    for k in ('Digit1', 'n', 's', 't'):
        page.keyboard.press(k)
    page.wait_for_timeout(300)
    check(page.inner_text('.dtitle h1').strip() == 'Операції', 'клавіша 1 у полі перемкнула екран')
    check(page.locator(ADD).count() == 0 and dialog(page, 'Налаштування').count() == 0 and page.locator('.set-page').count() == 0,
          'N або S у полі відкрили вікно')
    check(page.evaluate("localStorage.getItem('theme')") == theme0, 'T у полі змінила тему')
    check(inp.input_value() == before + '1nst', f'символи не потрапили в поле: {inp.input_value()!r}')


def form_keys(page):
    # форма операції: Enter без суми лишає форму з помилкою, +/- перемикають тип, 1-5 у полі суми не перемикають екран
    page.keyboard.press('n')
    page.wait_for_timeout(300)
    amt = page.locator(ADD + ' .amt-in')
    check(amt.evaluate('e=>e===document.activeElement'), 'поле суми не у фокусі')
    amt.press('Enter')
    page.wait_for_timeout(300)
    check(page.locator(ADD).count() == 1 and 'Введіть суму' in page.inner_text(ADD), 'Enter без суми не показав «Введіть суму»')
    page.keyboard.press('Digit2')
    page.wait_for_timeout(200)
    check(page.inner_text('.dtitle h1').strip() == 'Огляд', 'клавіша 2 у полі суми перемкнула екран')
    check(amt.input_value() == '2', f'цифра не потрапила в поле суми: {amt.input_value()!r}')
    page.keyboard.press('+')
    page.wait_for_timeout(150)
    check(page.locator('.amt-zone.in.on').count() == 1 and amt.input_value() == '2', '+ не перемкнув на «Дохід» або потрапив у поле')
    page.keyboard.press('-')
    page.wait_for_timeout(150)
    check(page.locator('.amt-zone.out.on').count() == 1 and amt.input_value() == '2', '- не перемкнув на «Витрата»')
    desc = page.locator(ADD + ' input[type=text]')
    desc.click()
    desc.type('a+b-c')
    check(desc.input_value() == 'a+b-c' and page.locator('.amt-zone.out.on').count() == 1, '+/- в описі перехоплені')
    # категорія і Enter у полі суми: зберегти (превʼю без БД пише в локальний стан), операція в Потоці
    page.locator(ADD + ' button', has_text='Продукти').click()
    # рахунок витрати обовʼязковий (DESIGN.md п. 1): без нього Enter не зберігає
    amt.fill('321')
    amt.press('Enter')
    page.wait_for_timeout(300)
    check(page.locator(ADD).count() == 1, 'Enter зберіг витрату без рахунку')
    page.locator(ADD + ' .acc-seg button').first.click()
    amt.fill('321')
    amt.press('Enter')
    page.wait_for_timeout(400)
    check(page.locator(ADD).count() == 0, 'Enter у полі суми не зберіг форму')
    go_tab(page, 2)
    check(page.locator('.p-flow.desk .flow-row.tx:has-text("a+b-c")').count() == 1, 'збережена операція не зʼявилась у Потоці')
    # Esc закриває іншу форму: рахунок (Enter у полі назви зберігає)
    page.keyboard.press('n')
    page.wait_for_timeout(200)
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)
    check(page.locator(ADD).count() == 0, 'Esc не закрив форму')


# найближчий предок із власною вертикальною прокруткою (або документ): колесо над повзунком не має його прокрутити
SCROLLER = """e=>{for(let x=e.parentElement;x;x=x.parentElement){const o=getComputedStyle(x).overflowY;if((o==='auto'||o==='scroll')&&x.scrollHeight>x.clientHeight)return x.scrollTop}return document.scrollingElement.scrollTop}"""


def wheel_and_arrows(page):
    # NumField «Ставка на місяць» на сторінці налаштувань (v142: повзунок «Що як» прибрано разом із прогнозом строків)
    page.keyboard.press('s')
    page.wait_for_timeout(400)
    page.locator('.set-page nav button', has_text='Зарплата').first.click()
    page.wait_for_timeout(300)
    inp = page.locator('.set-page input[type=text][aria-label="Ставка на місяць"]')
    rng = page.locator('.set-page input[type=range][aria-label="Ставка на місяць: повзунок"]')
    check(inp.count() == 1, 'немає поля «Ставка на місяць»')
    check(rng.count() == 1, 'немає повзунка «Ставка на місяць»')
    step = float(rng.get_attribute('step') or 1)
    num = lambda: float(re.sub(r'\s', '', inp.input_value()).replace(',', '.'))
    v0 = num()
    rng.scroll_into_view_if_needed()
    rng.hover()
    y0 = rng.evaluate(SCROLLER)
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(200)
    v1 = num()
    check(v1 == v0 + step, f'колесо вгору над повзунком: {v0} -> {v1}, крок {step}')
    check(rng.evaluate(SCROLLER) == y0, 'колесо над повзунком прокрутило сторінку')
    page.mouse.wheel(0, 100)
    page.wait_for_timeout(200)
    check(num() == v0, 'колесо вниз не повернуло значення')
    # поза повзунком (над заголовком сторінки) колесо значення не міняє
    hb = page.locator('.dtitle h1').bounding_box()
    rb = rng.bounding_box()
    check(hb and rb and (hb['y'] + hb['height'] <= rb['y'] or hb['x'] + hb['width'] <= rb['x']), 'заголовок перекривається з повзунком')
    page.mouse.move(hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2)
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(200)
    check(num() == v0, 'колесо поза повзунком змінило значення')
    # ↑/↓ у текстовому полі NumField: крок, з Shift більше
    inp.click()
    inp.press('ArrowUp')
    page.wait_for_timeout(150)
    check(num() == v0 + step, f'↑ у полі: {inp.input_value()}')
    inp.press('ArrowDown')
    inp.press('Shift+ArrowUp')
    page.wait_for_timeout(150)
    big = num() - v0
    check(big >= 100 and big >= 10 * step, f'Shift+↑ змінив лише на {big}')


CHECKS = [
    ('N відкриває, Esc закриває транзакцію', 'desktop', add_and_esc),
    ('S відкриває меню з 9 пунктів', 'desktop', settings_menu),
    ('T перемикає тему по колу', 'desktop', theme_cycle),
    # тур без tour_done у localStorage: автозапуск туру потребує сесії Supabase, тут лише ?
    ('? відкриває тур із 5 кроків', 'desktop', tour, {'tour': True}),
    ('Клавіші в полі вводу не перехоплюються', 'desktop', field_keeps_keys),
    ('Форма: Enter зберігає, +/- тип, Esc, 1-5 у полі', 'desktop', form_keys),
    ('Колесо над повзунком, ↑/↓ у числовому полі', 'desktop', wheel_and_arrows),
]
