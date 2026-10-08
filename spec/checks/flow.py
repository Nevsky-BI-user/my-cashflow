# ПК-Потік: фільтри, підсумок вибірки, таблиця по днях, дровер деталей зі стрілками; телефон: мобільний список і модалка
from helpers import SHOTS, check, dialog, freeze, go_tab, shot

ROWS = '.p-flow.desk .flow-row.tx'
DESCS = "[...document.querySelectorAll('.p-flow.desk .flow-row.tx .flow-desc')].map(e=>e.innerText)"


def _search(page, text):
    page.fill('.flow-q', text)
    page.wait_for_timeout(450)


def desktop(page):
    go_tab(page, 2)
    check(page.locator('.p-flow.desk .flow-table').count() == 1, 'на ПК немає таблиці Потоку')
    check(page.locator('.p-flow.desk .flow-bar .flow-q').count() == 1, 'немає поля пошуку в панелі фільтрів')
    n0 = page.locator(ROWS).count()
    check(n0 >= 5, f'у таблиці лише {n0} операцій')
    check(page.locator('.flow-reset').count() == 0, '«Скинути» видно без вибраних фільтрів')
    s0 = page.inner_text('.flow-sum')
    check(f'{n0} операц' in s0, f'підсумок не про {n0} операцій: {s0!r}')
    days = page.locator('.p-flow.desk .flow-day').all_inner_texts()
    check(days and ',' in days[0], f'заголовок дня без дня тижня: {days[:1]}')
    page.mouse.move(2, 2)
    shot(page, 'flow-full-1280.jpg')
    # пошук звужує рядки, підсумок перераховується
    _search(page, 'Сільпо')
    descs = page.evaluate(DESCS)
    check(0 < len(descs) < n0, f'пошук не звузив рядки: {len(descs)} з {n0}')
    check(all('Сільпо' in d for d in descs), f'у вибірці зайві рядки: {descs}')
    s1 = page.inner_text('.flow-sum')
    check(s1 != s0 and f'{len(descs)} операц' in s1, f'підсумок не перерахувався: {s1!r}')
    check(page.locator('.flow-reset').count() == 1, 'немає кнопки «Скинути» при активному пошуку')
    page.click('.flow-reset')
    page.wait_for_timeout(300)
    check(page.locator(ROWS).count() == n0, 'після «Скинути» рядків не стільки, як було')
    # сегмент «Доходи»: лише зелені суми
    page.locator('.flow-kind button', has_text='Доходи').click()
    page.wait_for_timeout(250)
    amts = page.evaluate("[...document.querySelectorAll('.p-flow.desk .flow-row .flow-amt')].map(e=>e.style.color)")
    check(amts and all(c == 'var(--green-t)' for c in amts), f'у «Доходах» не лише зелені суми: {amts}')
    check('доходи +' in page.inner_text('.flow-sum'), 'підсумок без доходів')
    page.locator('.flow-kind button', has_text='Усі').click()
    page.wait_for_timeout(250)
    # дровер: клік по рядку, ↓ до наступного, Esc закриває
    descs = page.evaluate(DESCS)
    page.locator(ROWS).first.click()
    page.wait_for_timeout(400)
    drw = page.locator('.drawer[role=dialog]')
    check(drw.count() == 1, 'клік по рядку не відкрив дровер')
    check(page.locator('.overlay').count() == 0, 'на ПК відкрилась центрована модалка замість дровера')
    box = drw.bounding_box()
    check(abs(box['width'] - 420) < 1 and abs(box['x'] + box['width'] - 1280) < 1, f'дровер не 420 праворуч: {box}')
    check(descs[0] in drw.inner_text(), 'дровер не про вибрану операцію')
    check(page.locator('.flow-row.sel').count() == 1, 'вибраний рядок не підсвічений')
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / 'flow-drawer-1280.jpg'), quality=80, type='jpeg')  # дровер fixed: кадр вʼюпорта, не full_page
    page.keyboard.press('ArrowDown')
    page.wait_for_timeout(300)
    t2 = drw.inner_text().lower()
    check(descs[1].lower() in t2 and '2 з' in t2, f'↓ не перейшов до наступної операції: {t2[:80]!r}')
    page.keyboard.press('ArrowUp')
    page.wait_for_timeout(300)
    check('1 з' in drw.inner_text().lower(), '↑ не повернув до попередньої')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(drw.count() == 0, 'Esc не закрив дровер')
    # порожній стан і «Скинути фільтри»
    _search(page, 'жодної такої операції')
    check('Нічого не знайдено' in page.inner_text('.p-flow.desk'), 'немає порожнього стану')
    page.locator('.flow-reset-big').click()
    page.wait_for_timeout(300)
    check(page.locator(ROWS).count() == n0, '«Скинути фільтри» не повернув рядки')


MON_GEN = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
DAYS = "[...document.querySelectorAll('.p-flow.desk .flow-group .flow-day span:first-child')].map(e=>e.innerText)"
CHIPS = """(()=>{const bar=document.querySelector('.p-flow.desk .flow-bar').getBoundingClientRect();const box=document.querySelector('.flow-cats');
return {sw:box.scrollWidth,cw:box.clientWidth,bar:{l:bar.left,r:bar.right,t:bar.top,b:bar.bottom},
chips:[...box.querySelectorAll('.flow-chip')].map(e=>{const r=e.getBoundingClientRect();return {t:e.innerText.trim(),l:r.left,r:r.right,t0:r.top,b:r.bottom,sw:e.scrollWidth,cw:e.clientWidth,h:r.height}}),
names:BCAT.map(b=>b.name)}})()"""
CHIPS_N = "document.querySelectorAll('.flow-cats .flow-chip').length - 1"


def _keys(page):
    """Дати груп по днях у порядку показу: (місяць, день)."""
    out = []
    for d in page.evaluate(DAYS):
        day, mon = d.split(',')[0].split(' ')
        out.append((MON_GEN.index(mon), int(day)))
    return out


def sort_chips(page):
    """ПК 1920x900: усі чипи категорій видно без обрізання і скролу; за замовчуванням від старіших до новіших, перемикач міняє порядок."""
    freeze(page, '2026-10-08')
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    go_tab(page, 2)
    c = page.evaluate(CHIPS)
    check(c['sw'] <= c['cw'] + 1, f'ряд категорій прокручується: {c["sw"]} > {c["cw"]}')
    txt = [x['t'] for x in c['chips']]
    check(txt and txt[0] == 'Усі', f'перший чип категорій не «Усі»: {txt[:2]}')
    missing = [n for n in c['names'] if not any(n in t for t in txt)]
    check(not missing, f'немає чипів категорій: {missing}')
    b = c['bar']
    for x in c['chips']:
        inside = x['l'] >= b['l'] - 0.5 and x['r'] <= b['r'] + 0.5 and x['t0'] >= b['t'] - 0.5 and x['b'] <= b['b'] + 0.5
        check(inside, f'чип поза панеллю: {x}')
        check(x['sw'] <= x['cw'] + 1 and x['h'] <= 24.5, f'чип обрізаний або вищий за 24px: {x}')
    check(page.locator('.flow-cats .flow-chip.on').all_inner_texts() == ['Усі'], 'без фільтра підсвічений не лише «Усі»')
    on = page.locator('.flow-sort button[aria-pressed=true]').inner_text()
    check('Старіші' in on, f'порядок за замовчуванням «{on}», а не «Старіші»')
    k = _keys(page)
    check(len(k) >= 3 and k[0] < k[-1] and k == sorted(k), f'групи не від старіших до новіших: {k}')
    rows0 = page.evaluate(DESCS)
    page.locator('.flow-sort button', has_text='Новіші').click()
    page.wait_for_timeout(300)
    k2 = _keys(page)
    check(k2 == sorted(k2, reverse=True) and k2[0] > k2[-1], f'«Новіші» не перевернуло групи: {k2}')
    check(sorted(page.evaluate(DESCS)) == sorted(rows0), 'після зміни порядку інший набір операцій')
    page.locator('.flow-sort button', has_text='Старіші').click()
    page.wait_for_timeout(300)
    check(_keys(page) == k, 'повернення до «Старіші» не відновило порядок')
    # вибраний чип підсвічений, «Усі» ні; «Усі» знімає фільтр
    page.locator('.flow-cats .flow-chip', has_text='Продукти').click()
    page.wait_for_timeout(300)
    on = page.locator('.flow-cats .flow-chip.on').all_inner_texts()
    check(len(on) == 1 and 'Продукти' in on[0], f'після вибору підсвічено {on}')
    cats = page.locator(ROWS + ' .flow-cat').all_inner_texts()
    check(cats and all('Продукти' in t for t in cats), f'фільтр «Продукти» пропустив інші категорії: {cats}')
    page.locator('.flow-cats .flow-chip', has_text='Усі').first.click()
    page.wait_for_timeout(300)
    check(page.locator('.flow-cats .flow-chip.on').all_inner_texts() == ['Усі'], '«Усі» не зняло фільтр категорій')


def all_chips(page):
    """17 категорій (фікстура: 4 додаткові в BCAT): усі 17 чипів видно одразу, кнопки «ще N» / «згорнути» немає."""
    extra = ''.join("{id:'x%d',name:'Тест %d',limit:100,color:'#999999',icon:'*'}," % (i, i) for i in range(4))
    freeze(page, '2026-10-08', patch=[('const BCAT=[', 'const BCAT=[' + extra)])
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    go_tab(page, 2)
    names = page.evaluate('BCAT.map(b=>b.name)')
    check(len(names) == 17, f'у фікстурі {len(names)} категорій, а не 17')
    check(page.locator('.flow-cats .flow-more').count() == 0, 'є кнопка «ще N» / «згорнути»')
    shown = page.evaluate(CHIPS_N)
    check(shown == 17, f'видно {shown} чипів категорій, а не 17')
    vis = page.evaluate("[...document.querySelectorAll('.flow-cats .flow-chip')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom<=innerHeight}).length")
    check(vis == 18, f'у вʼюпорті {vis} чипів разом з «Усі», а не 18')
    txt = page.locator('.flow-cats .flow-chip').all_inner_texts()
    check(all(any(n in x for x in txt) for n in names), 'не всі категорії мають чип')
    bar = page.evaluate("Math.round(document.querySelector('.p-flow.desk .flow-bar').getBoundingClientRect().height)")
    print(f'      Потік 1920x900, 17 категорій: панель фільтрів {bar}px')
    check(bar <= 150, f'панель фільтрів {bar}px, а не до 150')
    page.mouse.move(2, 2)
    shot(page, 'flow-17-1920.jpg', full=False)


def subscription(page):
    go_tab(page, 2)
    hint = page.locator('.flow-hint')
    check(hint.count() == 1 and 'Spotify' in hint.inner_text(), 'немає підказки про підписку Spotify')
    hint.locator('button').click()
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'кнопка підказки не відкрила вікно платежів')
    check(d.locator('input[placeholder="Напр. Інтернет"]').input_value() == 'Spotify', 'чернетка платежу без назви Spotify')


def mobile(page):
    go_tab(page, 2)
    check(page.locator('.p-flow.desk').count() == 0, 'на телефоні показано ПК-Потік')
    check(page.locator('.flow-hint').count() == 0, 'на телефоні є підказка про підписку')
    row = page.locator('.panel.p-flow div', has_text='Сільпо').last
    check(row.count() == 1, 'у мобільному списку немає операції')
    shot(page, 'flow-375.jpg')
    row.click()
    page.wait_for_timeout(400)
    check(page.locator('.drawer').count() == 0, 'на телефоні відкрився дровер')
    check(page.locator('.overlay .sheet', has_text='Транзакція').count() == 1, 'на телефоні не відкрилась модалка txView')


CHECKS = [
    ('Потік: фільтри, підсумок, дровер, стрілки', 'desktop', desktop),
    ('Потік: підказка про підписку', 'desktop', subscription),
    ('Потік 1920: усі категорії видно, від старіших до новіших, перемикач порядку', 'desktop', sort_chips),
    ('Потік: 17 категорій, усі видно без «ще N»', 'desktop', all_chips),
    ('Потік на телефоні: список і модалка', 'mobile', mobile),
]
