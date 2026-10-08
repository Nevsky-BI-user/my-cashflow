# ПК-Потік: фільтри, підсумок вибірки, таблиця по днях, дровер деталей зі стрілками; телефон: мобільний список і модалка
from helpers import SHOTS, check, dialog, go_tab, shot

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
    shot(page, 'flow-1280.jpg')
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
    ('Потік на телефоні: список і модалка', 'mobile', mobile),
]
