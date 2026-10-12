# Поле з повзунком (NumField): зарплата і розподіл бюджету
import re

from helpers import check, go_tab

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""


def _salary_root(page):
    # v142: KPI «Наступна виплата» (ПК) і чип героя (телефон) прибрано з Огляду; зарплата в налаштуваннях:
    # на ПК розділ сторінки налаштувань, на телефоні ⚙ у шапці, пункт «Зарплата» відкриває вікно
    if page.viewport_size['width'] >= 1024:
        page.keyboard.press('s')
        page.wait_for_timeout(400)
        page.locator('.set-page nav button', has_text='Зарплата').first.click()
        page.wait_for_timeout(300)
        root = '.set-page:has(input.nf-range)'
        check(page.locator(root).count() == 1, 'розділ «Зарплата» в налаштуваннях без повзунка')
        return page.locator(root)
    page.click('.hdr-gear')
    page.wait_for_timeout(400)
    page.locator('[role=dialog][aria-label="Налаштування"] button', has_text='Зарплата').first.click()
    page.wait_for_timeout(500)
    root = '[role=dialog]:has(input.nf-range)'
    check(page.locator(root).count() >= 1, 'пункт «Зарплата» не відкрив вікно з повзунком')
    return page.locator(root).last


def salary(page):
    d = _salary_root(page)
    rng = d.locator('input.nf-range').first
    txt = d.locator('input[type=text]').first
    lo, hi = float(rng.get_attribute('min')), float(rng.get_attribute('max'))
    t0 = d.inner_text()
    mid = round((lo + hi) / 2 / 1000) * 1000
    rng.evaluate(SETR, mid)
    page.wait_for_timeout(200)
    check(d.inner_text() != t0, 'повзунок ставки не змінив суму в картці')
    txt.click()
    txt.fill('90000')
    txt.press('Enter')
    page.wait_for_timeout(200)
    check(float(rng.input_value()) == 90000, f'ввід 90000: повзунок {rng.input_value()}')
    txt.click()
    txt.fill(str(int(hi * 10)))
    txt.press('Enter')
    page.wait_for_timeout(200)
    check(float(rng.input_value()) == hi, f'ввід понад межу: {rng.input_value()}, межа {hi}')
    txt.click()
    txt.fill('-5')
    txt.press('Enter')
    page.wait_for_timeout(200)
    check(float(rng.input_value()) == lo, f'ввід менше межі: {rng.input_value()}, межа {lo}')


def budget(page):
    go_tab(page, 1)
    page.click('.dact')
    page.wait_for_timeout(500)
    sh = page.locator('.sheet').last
    total = lambda: int((re.search(r'Розподілено: (\d+)%', sh.inner_text()) or [0, -1])[1])
    # повзунки категорій; «Відсоток» у тому ж вікні до розподілу не входить
    cat = 'input.nf-range:not([aria-label^="Відсоток"])'
    vals = lambda: [float(x) for x in sh.locator(cat).evaluate_all('a=>a.map(x=>x.value)')]
    check(total() == 100, f'на старті розподілено {total()}%')
    v0 = vals()
    free = sh.locator(cat + ':not([disabled])')
    check(free.count() >= 2, 'менше двох категорій для розподілу')
    cur = float(free.first.input_value())
    free.first.evaluate(SETR, cur + 7 if cur <= 80 else cur - 7)
    page.wait_for_timeout(200)
    v1 = vals()
    check(v1 != v0, 'повзунок категорії нічого не змінив')
    check(total() == 100, f'після зміни повзунка розподілено {total()}%')
    check(abs(sum(v1) - 100) < 0.6, f'сума повзунків {sum(v1)}')
    t = sh.locator('input[type=text]:not([disabled])').nth(1)
    t.click()
    t.fill('10')
    t.press('Enter')
    page.wait_for_timeout(200)
    check(total() == 100, f'після вводу 10 розподілено {total()}%')
    check(abs(sum(vals()) - 100) < 0.6, f'сума повзунків після вводу {sum(vals())}')

def unlock_all(page):
    """v148: категорії за замовчуванням розблоковані (кнопки «Розблокувати всі» немає); замок лишається,
    а якщо хоч одна заблокована, кнопка «Розблокувати всі» вгорі вікна знімає всі замки."""
    go_tab(page, 1)
    page.click('.dact')
    page.wait_for_timeout(500)
    sh = page.locator('.sheet').last
    locks = sh.locator('button[aria-label="Розблокувати"]')
    check(locks.count() == 0, f'на старті заблоковано {locks.count()} категорій')
    check(sh.locator('.bud-unlock-all').count() == 0, 'кнопка «Розблокувати всі» без жодного замка')
    sh.locator('button[aria-label="Заблокувати"]').nth(0).click()
    sh.locator('button[aria-label="Заблокувати"]').nth(0).click()
    page.wait_for_timeout(150)
    check(locks.count() == 2, f'після двох кліків заблоковано {locks.count()}')
    btn = sh.locator('.bud-unlock-all button', has_text='Розблокувати всі')
    check(btn.count() == 1, 'немає кнопки «Розблокувати всі» при заблокованих категоріях')
    top = sh.locator('.bud-unlock-all').bounding_box()['y']
    first = sh.locator('button[aria-label="Заблокувати"], button[aria-label="Розблокувати"]').first.bounding_box()['y']
    check(top < first, 'кнопка «Розблокувати всі» не вгорі вікна')
    btn.click()
    page.wait_for_timeout(150)
    check(locks.count() == 0 and sh.locator('.bud-unlock-all').count() == 0, f'після «Розблокувати всі» заблоковано {locks.count()}')


CHECKS = [
    ('Зарплата: повзунок і ввід ставки', 'desktop', salary),
    ('Зарплата: повзунок і ввід ставки', 'mobile', salary),
    ('Розподіл бюджету тримає 100%', 'desktop', budget),
    ('v148: Розподіл бюджету: «Розблокувати всі»', 'desktop', unlock_all),
]
