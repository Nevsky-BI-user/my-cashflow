# Раннер перевірок у браузері: python spec/run.py [--headed] [--only <назва>] [--keep]
# Збирає превʼю без Supabase, запускає Chromium і проганяє CHECKS з spec/checks/*.py.
# Кожна перевірка: свіжий контекст (чистий localStorage), помилки консолі = провал.
import argparse
import importlib.util
import sys
import time
import traceback
from pathlib import Path

SPEC = Path(__file__).resolve().parent
sys.path.insert(0, str(SPEC))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

import preview  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

VIEWPORTS = {'desktop': (1280, 860), 'mobile': (375, 812)}
# перевірки без tour_done у localStorage (сам тур)
NO_TOUR_FLAG = 'tour'
# відповіді CDN (React, шрифти) в памʼяті між контекстами, щоб не тягнути їх щоразу
_CDN = {}


def _cdn_cache(route):
    url = route.request.url
    if url.startswith('http://127.0.0.1') or route.request.method != 'GET':
        return route.continue_()
    hit = _CDN.get(url)
    if hit is None:
        try:
            r = route.fetch()
        except Exception:
            return route.abort()
        hit = {'status': r.status, 'headers': r.headers, 'body': r.body()}
        if r.status == 200:
            _CDN[url] = hit
    route.fulfill(status=hit['status'], headers=hit['headers'], body=hit['body'])


def load_checks():
    """Збирає CHECKS з усіх spec/checks/*.py (крім _*.py) у порядку імен файлів."""
    out = []
    for f in sorted((SPEC / 'checks').glob('*.py')):
        if f.name.startswith('_'):
            continue
        sp = importlib.util.spec_from_file_location('checks_' + f.stem, f)
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
        for item in getattr(mod, 'CHECKS', []):
            name, vp, fn = item[:3]
            opts = item[3] if len(item) > 3 else {}
            if vp not in VIEWPORTS:
                raise ValueError(f'{f.name}: невідомий viewport {vp!r} у {name}')
            out.append((f.stem, name, vp, fn, opts))
    return out


def run_one(browser, url, vp, fn, opts):
    w, hgt = VIEWPORTS[vp]
    mob = vp == 'mobile'
    ctx = browser.new_context(viewport={'width': w, 'height': hgt}, is_mobile=mob, has_touch=mob,
                              color_scheme='dark', device_scale_factor=1)
    ctx.route('**/*', _cdn_cache)
    if not opts.get(NO_TOUR_FLAG):
        ctx.add_init_script("try{localStorage.setItem('tour_done','1')}catch(e){}")
    page = ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    page.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' else None)
    page.on('dialog', lambda d: d.accept())
    try:
        page.goto(url)
        page.wait_for_selector('.side' if not mob else '.tab-bar', timeout=20000)
        page.wait_for_timeout(400)
        fn(page)
        if errs:
            raise AssertionError('помилки консолі: ' + ' | '.join(errs[:3]))
    finally:
        ctx.close()


def main():
    ap = argparse.ArgumentParser(description='Перевірки index.html у Chromium (Playwright)')
    ap.add_argument('--headed', action='store_true', help='показувати вікно браузера')
    ap.add_argument('--only', help='лише перевірки, у назві яких (або назві модуля) є цей текст')
    ap.add_argument('--keep', action='store_true', help='не зупиняти превʼю-сервер після прогону')
    a = ap.parse_args()

    checks = load_checks()
    if a.only:
        checks = [c for c in checks if a.only in c[1] or a.only == c[0]]
        if not checks:
            print('Немає перевірок за фільтром', a.only)
            return 2
    t0 = time.time()
    srv = preview.start()
    rows = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not a.headed)
            try:
                for mod, name, vp, fn, opts in checks:
                    t1 = time.time()
                    try:
                        run_one(browser, srv.url, vp, fn, opts)
                        rows.append((mod, name, vp, 'PASS', '', time.time() - t1))
                    except Exception as e:
                        msg = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                        if not isinstance(e, AssertionError):
                            msg = type(e).__name__ + ': ' + msg
                            if a.only:
                                traceback.print_exc()
                        rows.append((mod, name, vp, 'FAIL', msg[:160], time.time() - t1))
            finally:
                browser.close()
        # таблиця до очікування --keep, щоб результат було видно одразу
        report(rows, t0)
        if a.keep:
            print('Превʼю лишається:', srv.url, '(Ctrl+C зупиняє)', flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    finally:
        srv.stop()
    return 1 if any(r[3] == 'FAIL' for r in rows) else 0


def report(rows, t0):
    if not rows:
        return
    wn = max(len(r[1]) for r in rows)
    wm = max(len(r[0]) for r in rows)
    for mod, name, vp, st, msg, dt in rows:
        print(f'{st}  {mod:<{wm}}  {name:<{wn}}  {vp:<7}  {dt:5.1f}s  {msg}')
    fails = sum(1 for r in rows if r[3] == 'FAIL')
    print(f'\nУсього {len(rows)}, PASS {len(rows) - fails}, FAIL {fails}, час {time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    sys.exit(main())
