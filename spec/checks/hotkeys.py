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
    page.keyboard.press('s')
    page.wait_for_timeout(400)
    d = dialog(page, 'Налаштування')
    check(d.count() == 1, 'S не відкрила меню налаштувань')
    n = d.locator('nav button').count()
    check(n == 9, f'у меню {n} пунктів, а не 9')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(d.count() == 0, 'Esc не закрив меню')


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
    inp = page.locator('input[aria-label="% накопичень з доходу"]')
    check(inp.count() == 1, 'на екрані Цілі немає поля «% накопичень з доходу»')
    inp.click()
    inp.press('End')
    before = inp.input_value()
    theme0 = page.evaluate("localStorage.getItem('theme')")
    for k in ('Digit1', 'n', 's', 't'):
        page.keyboard.press(k)
    page.wait_for_timeout(300)
    check(page.inner_text('.dtitle h1').strip() == 'Цілі', 'клавіша 1 у полі перемкнула екран')
    check(page.locator(ADD).count() == 0 and dialog(page, 'Налаштування').count() == 0,
          'N або S у полі відкрили вікно')
    check(page.evaluate("localStorage.getItem('theme')") == theme0, 'T у полі змінила тему')
    check(inp.input_value() != before and '1' in inp.input_value(), f'цифра не потрапила в поле: {inp.input_value()!r}')


CHECKS = [
    ('N відкриває, Esc закриває транзакцію', 'desktop', add_and_esc),
    ('S відкриває меню з 9 пунктів', 'desktop', settings_menu),
    ('T перемикає тему по колу', 'desktop', theme_cycle),
    # тур без tour_done у localStorage: автозапуск туру потребує сесії Supabase, тут лише ?
    ('? відкриває тур із 5 кроків', 'desktop', tour, {'tour': True}),
    ('Клавіші в полі вводу не перехоплюються', 'desktop', field_keeps_keys),
]
