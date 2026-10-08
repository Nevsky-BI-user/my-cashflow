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


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / name
    page.screenshot(path=str(path), quality=80, type='jpeg', full_page=True)
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
    """Знімок у форматі scripts/budget_pool.py з демо-констант сторінки (рахунки, розстрочки, зарплата, 20%)."""
    return page.evaluate("""()=>({accounts:ACCOUNTS_DEMO,fixed:[],credits:CREDITS.map(c=>({name:c.name,monthly_amount:c.amount,
payment_day:c.day,start_year:c.sy,start_month:c.sm,total_payments:c.total})),salary:{rate:SAL_RATE,split_day:SAL_SPLIT,
advance_day:SAL_ADV_DAY,salary_day:SAL_MAIN_DAY,savings_pct:20}})""")


def pool_ref(snap, today):
    """JSON-рядок еталона scripts/budget_pool.py для знімка snap і дати today (YYYY-MM-DD)."""
    tmp = SPEC / '.out' / 'demo_snapshot.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(_json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    out = _sp.run([_sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), str(tmp), today], capture_output=True,
                  text=True, encoding='utf-8', check=True, env={**_os.environ, 'PYTHONUTF8': '1'}).stdout
    line = [x for x in out.splitlines() if x.startswith('JSON ')]
    check(line, f'еталон не надрукував JSON для {today}')
    return _json.loads(line[-1][5:])


def current_ref(snap, today):
    """Еталон поточного періоду (відкритого останньою виплатою не пізніше today): budget_pool на день перед виплатою."""
    d, _ = open_payout(_date.fromisoformat(today) if isinstance(today, str) else today)
    return pool_ref(snap, str(d - _td(days=1)))


def num(text):
    """'37 268 ₴' -> 37268 (пробіли й нерозривні пробіли тисяч, мінус U+2212)."""
    t = ''.join(ch for ch in text if ch.isdigit() or ch in '-−')
    return -int(t.strip('-−')) if t.startswith(('-', '−')) else int(t)
