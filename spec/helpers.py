# Спільні помічники для spec/checks/*.py
from pathlib import Path

SPEC = Path(__file__).resolve().parent
ROOT = SPEC.parent
SHOTS = SPEC / '.out' / 'shots'
TABS = [('overview', 'Огляд'), ('budget', 'Бюджет'), ('flow', 'Потік'), ('credits', 'Календар'), ('goals', 'Цілі')]


def check(cond, msg):
    """assert, що не зникає з python -O."""
    if not cond:
        raise AssertionError(msg)


def go_tab(page, i):
    """Перехід на вкладку i (0-4): клавіша на ПК, нижня вкладка на телефоні."""
    if page.viewport_size['width'] >= 1024:
        page.keyboard.press(f'Digit{i + 1}')
    else:
        page.locator('.tab-bar .tab-btn').nth(i).click()
    page.wait_for_timeout(350)


def dialog(page, label):
    return page.locator(f'[role=dialog][aria-label="{label}"]')


def touch_drag(page, x0, y0, x1, y1, steps=8, hold=0, step_ms=16, before_end=None, after=250):
    """Справжній дотик через CDP (Input.dispatchTouchEvent): touchStart, hold мс без руху, steps кроків touchMove, touchEnd.
    before_end(page): виклик перед відпусканням (наприклад, скриншот посеред перетягування)."""
    cdp = page.context.new_cdp_session(page)

    def ev(kind, pts):
        cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': pts})
    try:
        ev('touchStart', [{'x': x0, 'y': y0}])
        if hold:
            page.wait_for_timeout(hold)
        for i in range(1, steps + 1):
            ev('touchMove', [{'x': x0 + (x1 - x0) * i / steps, 'y': y0 + (y1 - y0) * i / steps}])
            page.wait_for_timeout(step_ms)
        if before_end:
            before_end(page)
        ev('touchEnd', [])
    finally:
        cdp.detach()
    page.wait_for_timeout(after)


def center(page, selector, nth=0):
    """Центр елемента (x, y) у координатах вʼюпорта."""
    b = page.locator(selector).nth(nth).bounding_box()
    check(b, f'немає елемента {selector}')
    return b['x'] + b['width'] / 2, b['y'] + b['height'] / 2


def shot(page, name, full=True):
    """full=False: лише видима область (екран як його бачить людина)"""
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / name
    page.screenshot(path=str(path), quality=80, type='jpeg', full_page=full)
    return path


# --- заморожена дата і демо-знімок для перевірок Бюджету й Цілей ---
import calendar as _cal
import json as _json
import os as _os
import subprocess as _sp
import sys as _sys
from datetime import date as _date, timedelta as _td

ADV_DAY, SAL_DAY = 21, 6  # SAL_ADV_DAY, SAL_MAIN_DAY з index.html (демо без БД)


def freeze(page, iso, patch=None):
    """Перезавантажує сторінку із замороженою датою iso (YYYY-MM-DD, полудень); patch: [(старе, нове)] заміни в index.html."""
    page.clock.set_fixed_time(iso + 'T12:00:00')
    if patch:
        url = page.url

        def fix(route):
            r = route.fetch()
            body = r.text()
            for a, b in patch:
                check(body.count(a) == 1, f'заміна для фікстури не знайдена: {a[:40]}')
                body = body.replace(a, b)
            route.fulfill(response=r, body=body)
        page.route(url, fix)
    page.reload()
    page.wait_for_selector('.side' if page.viewport_size['width'] >= 1024 else '.tab-bar', timeout=20000)
    page.wait_for_timeout(400)


def _adj(y, m, d):
    w = _date(y, m, d).weekday()
    return _date(y, m, d - 1 if w == 5 else d + 1 if w == 6 else d)


def open_payout(today):
    """Остання виплата не пізніше today (те саме правило, що pbOpen): (дата, 'advance'|'salary')."""
    out = []
    for k in range(-2, 2):
        y, m = divmod(today.year * 12 + today.month - 1 + k, 12)
        out += [(_adj(y, m + 1, ADV_DAY), 'advance'), (_adj(y, m + 1, SAL_DAY), 'salary')]
    return max(p for p in out if p[0] <= today)


def demo_snapshot(page):
    """Знімок у форматі scripts/budget_pool.py з демо-констант сторінки (рахунки, постійні, розстрочки з source, зарплата, 20%)."""
    return page.evaluate("""()=>({accounts:ACCOUNTS_DEMO,fixed:FIXED_DEMO,credits:CREDITS.map(c=>({name:c.name,monthly_amount:c.amount,
payment_day:c.day,start_year:c.sy,start_month:c.sm,total_payments:c.total,source:c.src})),salary:{rate:SAL_RATE,split_day:SAL_SPLIT,
advance_day:SAL_ADV_DAY,salary_day:SAL_MAIN_DAY,savings_pct:20}})""")


def pool_ref(snap, today, now=None):
    """JSON-рядок еталона scripts/budget_pool.py для знімка snap і дати today (YYYY-MM-DD)."""
    tmp = SPEC / '.out' / 'demo_snapshot.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(_json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    out = _sp.run([_sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), str(tmp), today] + ([str(now)] if now else []), capture_output=True,
                  text=True, encoding='utf-8', check=True, env={**_os.environ, 'PYTHONUTF8': '1'}).stdout
    line = [x for x in out.splitlines() if x.startswith('JSON ')]
    check(line, f'еталон не надрукував JSON для {today}')
    return _json.loads(line[-1][5:])


def current_ref(snap, today, now=None):
    """Еталон поточного періоду (відкритого останньою виплатою не пізніше today): budget_pool на день перед виплатою."""
    d, _ = open_payout(_date.fromisoformat(today) if isinstance(today, str) else today)
    return pool_ref(snap, str(d - _td(days=1)), now)


def num(text):
    """'37 268 ₴' -> 37268 (пробіли й нерозривні пробіли тисяч, мінус U+2212)."""
    t = ''.join(ch for ch in text if ch.isdigit() or ch in '-−')
    return -int(t.strip('-−')) if t.startswith(('-', '−')) else int(t)
