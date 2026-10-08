# План проти фактів: новий постійний платіж із вікна «Платежі» одразу видно в «Найближче» Огляду і в Потоці
from datetime import date, timedelta

from helpers import check, dialog, go_tab, open_payout

FAB = "()=>{const b=[...document.querySelectorAll('button')].filter(x=>getComputedStyle(x).position==='fixed'&&!x.closest('.tab-bar'));b[b.length-1].click()}"
NAME = 'Спортзал тест'


def fixed_appears(page):
    t = date.today()
    # день у переглядуваному періоді (за замовчуванням поточний, відкритий останньою виплатою) і не раніше сьогодні:
    # завтра, якщо воно ще в періоді й у цьому місяці, інакше сьогодні
    start, kind = open_payout(t)
    end = min(d for d, _ in (open_payout(t + timedelta(days=k)) for k in range(1, 40)) if d > start)
    nxt = t + timedelta(days=1)
    day = nxt.day if nxt < end and nxt.month == t.month else t.day
    strip0 = page.inner_text('.o-strip')
    go_tab(page, 3)
    page.evaluate(FAB)
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    d.locator('[aria-label="Тип платежів"] button', has_text='Постійні').click()
    d.locator('button', has_text='+ Додати').click()
    page.wait_for_timeout(200)
    d.locator('input[placeholder="Напр. Інтернет"]').fill(NAME)
    for lbl, v in (('Сума', '1234'), ('День місяця', str(day))):
        f = d.locator(f'input[type=text][aria-label="{lbl}"]')
        f.fill(v)
        f.press('Tab')  # Enter у полі форми тепер зберігає її (hotkeys.py), тут лише комітимо значення
    d.locator('button', has_text='Зберегти').first.click()
    page.wait_for_timeout(300)
    if d.count():
        d.locator('[aria-label="Закрити"]').first.click()
        page.wait_for_timeout(300)
    go_tab(page, 0)
    nxt = page.inner_text('.o-next')
    check(NAME in nxt, f'новий постійний платіж не зʼявився в «Найближчих операціях»: {nxt[:200]!r}')
    row = page.locator('.o-next .o-next-row', has_text=NAME)
    if day > t.day:
        check('через' in row.inner_text() and 'future' in (row.get_attribute('class') or ''), 'майбутній плановий рядок не приглушений або без «через N дн.»')
    # факти не змінились: план не входить у «Дохід / Витрати / Залишок» (герой «Вільно до виплати» від плану залежить, бо бюджет періоду мінус обовʼязкові)
    check(page.inner_text('.o-strip') == strip0, 'плановий платіж змінив фактичні суми «Дохід / Витрати / Залишок»')
    go_tab(page, 2)
    flow = page.locator('.panel.p-flow .row-plan', has_text=NAME)
    check(flow.count() == 1, 'у Потоці немає планового рядка')
    ft = flow.inner_text()
    # v139: замість «через N дн.» сірий прогноз балансу після платежу («план», якщо дата за горизонтом прогнозу)
    check('прогноз' in ft or 'план' in ft, f'плановий рядок у Потоці без прогнозу балансу: {ft!r}')


CHECKS = [
    ('Новий постійний платіж одразу в «Найближчих»', 'mobile', fixed_appears),
]
