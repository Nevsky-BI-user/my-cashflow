# Гарячі клавіші на ПК: N, Esc, S, T, ?, і поле вводу їх не віддає
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
    go_tab(page, 4)
    # поле «Що як» на ПК-Цілях (налаштування % накопичень тепер у вікні «Налаштувати накопичення»)
    inp = page.locator('input[type=text][aria-label="Відкладати більше на місяць"]')
    check(inp.count() == 1, 'на екрані Цілі немає поля «Відкладати більше на місяць»')
    inp.click()
    inp.press('End')
    before = inp.input_value()
    theme0 = page.evaluate("localStorage.getItem('theme')")
    for k in ('Digit1', 'n', 's', 't'):
        page.keyboard.press(k)
    page.wait_for_timeout(300)
    check(page.inner_text('.dtitle h1').strip() == 'Цілі', 'клавіша 1 у полі перемкнула екран')
    check(page.locator(ADD).count() == 0 and dialog(page, 'Налаштування').count() == 0 and page.locator('.set-page').count() == 0,
          'N або S у полі відкрили вікно')
    check(page.evaluate("localStorage.getItem('theme')") == theme0, 'T у полі змінила тему')
    check(inp.input_value() != before and '1' in inp.input_value(), f'цифра не потрапила в поле: {inp.input_value()!r}')


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


def wheel_and_arrows(page):
    go_tab(page, 4)
    inp = page.locator('input[type=text][aria-label="Відкладати більше на місяць"]')
    rng = page.locator('input[type=range][aria-label="Відкладати більше на місяць: повзунок"]')
    check(rng.count() == 1, 'немає повзунка «Що як»')
    step = float(rng.get_attribute('step') or 1)
    v0 = float(inp.input_value())
    rng.scroll_into_view_if_needed()
    rng.hover()
    y0 = page.evaluate('scrollY')
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(200)
    v1 = float(inp.input_value())
    check(v1 == v0 + step, f'колесо вгору над повзунком: {v0} -> {v1}, крок {step}')
    check(page.evaluate('scrollY') == y0, 'колесо над повзунком прокрутило сторінку')
    page.mouse.wheel(0, 100)
    page.wait_for_timeout(200)
    check(float(inp.input_value()) == v0, 'колесо вниз не повернуло значення')
    # поза повзунком колесо значення не міняє
    page.mouse.move(700, 120)
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(200)
    check(float(inp.input_value()) == v0, 'колесо поза повзунком змінило значення')
    # ↑/↓ у текстовому полі NumField: крок, з Shift більше
    inp.click()
    inp.press('ArrowUp')
    page.wait_for_timeout(150)
    check(float(inp.input_value()) == v0 + step, f'↑ у полі: {inp.input_value()}')
    inp.press('ArrowDown')
    inp.press('Shift+ArrowUp')
    page.wait_for_timeout(150)
    big = float(inp.input_value()) - v0
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
