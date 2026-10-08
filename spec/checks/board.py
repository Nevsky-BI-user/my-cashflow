# Карта цілей: рівна сітка на ПК (3 колонки) і стек на телефоні
from helpers import check, dialog, go_tab, shot

LAYOUT = r"""()=>{const g=document.querySelector('.board-d');if(!g)return null;return [...g.children].map(e=>{const r=e.getBoundingClientRect();
return {add:e.classList.contains('gtile-add'),big:(e.style.gridColumn||'').includes('span 2'),x:r.left,y:r.top,w:r.width,h:r.height}})}"""
TOL = 2


def layout(page):
    tiles = page.evaluate(LAYOUT)
    check(tiles, 'на ПК немає сітки .board-d')
    return tiles


def verify(page, n, tag):
    """Перевіряє сітку з n цілей (поточна велика + решта + «+ Ціль» останньою)."""
    # прибрати курсор: hover збільшує плитку на 1%
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    t = layout(page)
    check(len(t) == n + 1, f'{tag}: {len(t) - 1} плиток цілей замість {n}')
    check(t[-1]['add'] and sum(x['add'] for x in t) == 1, f'{tag}: «+ Ціль» не остання в сітці')
    big = [x for x in t if x['big']]
    small = [x for x in t if not x['big']]
    col = small[0]['w']
    for x in small:
        check(abs(x['w'] - col) <= TOL, f'{tag}: ширини плиток різні {[round(s["w"]) for s in small]}')
        want = x['w'] * 10 / 16
        check(abs(x['h'] - want) <= TOL, f'{tag}: висота плитки {x["h"]:.0f} замість {want:.0f} (16:10)')
    hs = [round(x['h']) for x in small]
    check(max(hs) - min(hs) <= TOL, f'{tag}: висоти звичайних плиток різні {hs}')
    add = t[-1]
    goals_h = [x['h'] for x in small if not x['add']] or [add['w'] * 10 / 16]
    check(add['h'] <= max(goals_h) + TOL, f'{tag}: «+ Ціль» вища за плитки')
    if big:
        b = big[0]
        if n - 1 >= 2:
            want = 2 * small[0]['h'] + 16
            check(abs(b['h'] - want) <= TOL, f'{tag}: велика {b["h"]:.0f}px, очікували 2 ряди + gap = {want:.0f}')
        else:
            check(abs(b['w'] / b['h'] - 16 / 9) < 0.03, f'{tag}: велика не 16:9 ({b["w"]:.0f}x{b["h"]:.0f})')
            check(abs(add['y'] - b['y']) <= TOL or n == 2, f'{tag}: «+ Ціль» не в першому ряду поруч із великою')
    # жодна плитка не накладається на іншу
    for i, a in enumerate(t):
        for c in t[i + 1:]:
            ov = min(a['x'] + a['w'], c['x'] + c['w']) - max(a['x'], c['x']) > TOL and \
                min(a['y'] + a['h'], c['y'] + c['h']) - max(a['y'], c['y']) > TOL
            check(not ov, f'{tag}: плитки накладаються')


def both_widths(page, n, name):
    verify(page, n, f'1280, {n} ціл.')
    shot(page, name)
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    verify(page, n, f'1920, {n} ціл.')
    page.set_viewport_size({'width': 1280, 'height': 860})
    page.wait_for_timeout(300)


def delete_one(page):
    # видаляємо першу не поточну ціль через модалку (confirm приймає раннер)
    tiles = page.locator('.board-d > .gtile[role=button]')
    for i in range(tiles.count()):
        st = tiles.nth(i).get_attribute('style') or ''
        if 'span 2' not in st:
            tiles.nth(i).click()
            break
    page.wait_for_timeout(300)
    d = dialog(page, 'Ціль')
    d.locator('button', has_text='Видалити').click()
    page.wait_for_timeout(400)


def columns(page):
    # ПК-Цілі: ліворуч карта і горизонт, праворуч «Що як», історія, фактичні накопичення; між колонками 24px
    main = page.locator('.goals-main').inner_text().lower()
    side = page.locator('.goals-side').inner_text().lower()
    check(page.locator('.goals-main .board-d').count() == 1, 'карта цілей не в лівій колонці')
    check('горизонт подій' in main and 'горизонт подій' not in side, '«Горизонт подій» не в лівій колонці')
    for t in ('Що як', 'Історія накопичень', 'Фактичні накопичення'):
        check(t.lower() in side and t.lower() not in main, f'«{t}» не в правій колонці')
    gap = page.evaluate("getComputedStyle(document.querySelector('.goals-cols')).columnGap")
    check(gap == '24px', f'проміжок між колонками {gap}')


def desktop(page):
    go_tab(page, 4)
    columns(page)
    both_widths(page, 3, 'goals-1280-3.jpg')
    page.locator('.board-d .gtile-add').click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Ціль')
    d.locator("input[aria-label='Назва']").fill('Відпустка')
    d.locator('button', has_text='Зберегти').click()
    page.wait_for_timeout(400)
    check(d.count() == 0, 'модалка нової цілі не закрилась')
    both_widths(page, 4, 'goals-1280-4.jpg')
    delete_one(page)
    delete_one(page)
    verify(page, 2, '1280, 2 ціл.')
    delete_one(page)
    both_widths(page, 1, 'goals-1280-1.jpg')


def mobile(page):
    go_tab(page, 4)
    r = page.evaluate(r"""[...document.querySelectorAll('.gtile[role=button]')].map(e=>{const b=e.getBoundingClientRect();return [b.left,b.top,b.width,b.height]})""")
    check(len(r) >= 3, f'на телефоні {len(r)} плиток')
    xs = {round(a[0]) for a in r}
    ws = {round(a[2]) for a in r}
    check(len(xs) == 1 and len(ws) == 1, f'плитки не стеком однакової ширини: x {xs}, w {ws}')
    tops = [a[1] for a in r]
    check(tops == sorted(tops), 'плитки не одна під одною')


CHECKS = [
    ('Карта цілей: 3, 4, 2, 1 ціль, 1280 і 1920', 'desktop', desktop),
    ('Карта цілей: стек на телефоні', 'mobile', mobile),
]
