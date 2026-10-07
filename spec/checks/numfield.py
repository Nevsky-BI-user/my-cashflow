# Поле з повзунком (NumField): зарплата і розподіл бюджету
import re

from helpers import check, go_tab

SETR = """(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,String(v));el.dispatchEvent(new Event('input',{bubbles:true}))}"""


def _salary_root(page):
    page.click('.dv-pay-btn' if page.viewport_size['width'] >= 1024 else '.o-chip')
    page.wait_for_timeout(500)
    root = '[role=dialog]:has(input.nf-range)'
    check(page.locator(root).count() >= 1, 'чип зарплати не відкрив вікно з повзунком')
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


CHECKS = [
    ('Зарплата: повзунок і ввід ставки', 'desktop', salary),
    ('Зарплата: повзунок і ввід ставки', 'mobile', salary),
    ('Розподіл бюджету тримає 100%', 'desktop', budget),
]
