# Карта цілей: рівна сітка на ПК (3 колонки) і стек на телефоні
import re

from helpers import check, dialog, go_tab, shot

LAYOUT = r"""()=>{const g=document.querySelector('.board-d');if(!g)return null;return [...g.children].map(e=>{const r=e.getBoundingClientRect();
return {add:e.classList.contains('gtile-add'),big:(e.style.gridColumn||'').includes('span 2'),x:r.left,y:r.top,w:r.width,h:r.height}})}"""
TOL = 2


def layout(page):
    tiles = page.evaluate(LAYOUT)
    check(tiles, 'на ПК немає сітки .board-d')
    return tiles


def verify(page, n, tag):
    """Перевіряє сітку з n цілей (поточна велика + решта); пунктирної плитки «+ Ціль» немає, кнопка в шапці сторінки."""
    # прибрати курсор: hover збільшує плитку на 1%
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    t = layout(page)
    check(len(t) == n, f'{tag}: {len(t)} плиток у сітці замість {n} цілей')
    check(not any(x['add'] for x in t), f'{tag}: пунктирна плитка «+ Ціль» на дошці')
    big = [x for x in t if x['big']]
    small = [x for x in t if not x['big']]
    for x in small:
        check(abs(x['w'] - small[0]['w']) <= TOL, f'{tag}: ширини плиток різні {[round(s["w"]) for s in small]}')
        check(150 <= x['h'] <= 230, f'{tag}: плитка поза адаптивною висотою: {x["h"]:.0f}')
    hs = [round(x['h']) for x in small]
    check(not hs or max(hs) - min(hs) <= TOL, f'{tag}: висоти звичайних плиток різні {hs}')
    if big:
        b = big[0]
        if n - 1 >= 2:
            want = 2 * small[0]['h'] + 16
            check(abs(b['h'] - want) <= TOL, f'{tag}: велика {b["h"]:.0f}px, очікували 2 ряди + gap = {want:.0f}')
        else:
            check(150 <= b['h'] <= 230, f'{tag}: висота поточної цілі поза адаптивним рядом ({b["h"]:.0f})')
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
    # Фактичні накопичення — четверта картка одного верхнього ряду.
    # «Горизонт подій», «Що як» та «Історія накопичень» прибрано свідомо: це прогноз строків зі старої
    # формули надлишку (docs/redesign/projection-contract.md, розділ «Заощадження»)
    main = page.locator('.goals-main').inner_text().lower()
    check(page.locator('.goals-main .board-d').count() == 1, 'немає карти цілей')
    log = page.locator('.goals-log').bounding_box()
    cards = page.locator('.goals-kpis > .surface')
    check(cards.count() == 4 and cards.nth(3).locator('.goals-log-tot').count() == 1,
          'фактичні накопичення не четверта верхня картка')
    boxes = [cards.nth(i).bounding_box() for i in range(4)]
    check(max(b['y'] for b in boxes) - min(b['y'] for b in boxes) <= 1,
          'верхні чотири картки не в одному ряду')
    check(max(b['height'] for b in boxes) - min(b['height'] for b in boxes) <= 1,
          'верхні чотири картки різної висоти')
    board = page.locator('.board-d').bounding_box()
    check(log and board and log['y'] + log['height'] <= board['y'], 'фактичні накопичення не над картками')
    coin = page.locator('.board-wrap .coin').bounding_box()
    check(coin and coin['y'] + coin['height'] <= board['y'], 'монетка перекриває картки або їхні дії')
    check('фактичні накопичення' not in main, 'журнал потрапив у дошку цілей')
    check(page.evaluate("[...document.querySelectorAll('.goals-main,.goals-cols,.board-d')].every(e=>e.scrollWidth<=e.clientWidth+1&&e.scrollHeight<=e.clientHeight+1)"), 'внутрішня прокрутка або переповнення дошки')
    page_txt = page.locator('.p-goals').inner_text().lower()
    for t in ('Горизонт подій', 'Що як', 'Історія накопичень'):
        # межі слова: «що якщо» в інших текстах не рахується
        check(not re.search(r'\b' + t.lower() + r'\b', page_txt), f'на екрані лишився прогноз строків «{t}»')
    gap = page.evaluate("getComputedStyle(document.querySelector('.goals-cols')).columnGap")
    check(12 <= float(gap.removesuffix('px')) <= 14, f'проміжок між колонками {gap}')


def desktop(page):
    go_tab(page, 4)
    for width, height in ((1280, 800), (1910, 917)):
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(300)
        columns(page)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight+1'), f'{width}: стандартний екран заощаджень потребує прокрутки')
        shot(page, f'goals-aligned-{width}.jpg', full=False)
    page.set_viewport_size({'width': 1280, 'height': 860})
    page.wait_for_timeout(300)
    page.locator('.board-d > .gtile').nth(1).hover()
    edit = page.locator('.board-d > .gtile').nth(1).get_by_role('button', name='Редагувати', exact=True)
    check(edit.evaluate('e=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.right-8,b.top+b.height/2))}'), 'кнопку редагування перекрито')
    edit.click(position={'x': 80, 'y': 14})
    check(dialog(page, 'Ціль').count() == 1, 'редагування правої верхньої цілі відкрило іншу дію')
    page.keyboard.press('Escape')
    columns(page)
    both_widths(page, 3, 'goals-1280-3.jpg')
    page.locator('.dtitle .goals-add').click()
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
