"""Історичні знімки на демо-даних; сервер і браузер закриваються після прогону."""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from preview import Server, SWAPS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'spec/.out/history-reference'
REFS = ('6c64a08', '8deb5c2', '2c56c55')
VIEWPORTS = ((1440, 900), (1920, 900), (390, 844))
CDN = {}
sys.stdout.reconfigure(encoding='utf-8')


def git_file(ref, name):
    return subprocess.check_output(['git', 'show', f'{ref}:{name}'], cwd=ROOT)


def build(ref):
    directory = OUT / ref
    directory.mkdir(parents=True, exist_ok=True)
    source = git_file(ref, 'index.html').decode('utf-8')
    source, count = re.subn(r'<script\b[^>]*src=["\'][^"\']*supabase[^"\']*["\'][^>]*>\s*</script>', '', source)
    assert count == 1, (ref, 'Supabase script count', count)
    source, count = re.subn(r"if\(\s*['\"]serviceWorker['\"]\s+in\s+navigator\s*\)\s*\{", 'if(false){', source)
    assert count == 1, (ref, 'SW registration count', count)
    for old, new in SWAPS:
        if 'supabase' not in old and 'serviceWorker' not in old:
            source = source.replace(old, new)
    # Публічний конфіг зайвий у локальній копії; відсутній SDK лишає sb=null.
    source = re.sub(r"(const\s+SUPABASE_(?:URL|ANON_KEY)\s*=\s*)['\"][^'\"]*['\"]", r"\1''", source)
    source = re.sub(r"try\{sb=supabase\.createClient\([^\n]*?\)\}catch\(e\)\{\}", '/* Демо: Supabase вимкнено. */', source)
    (directory / 'index.html').write_text(source, encoding='utf-8')
    for name in ('manifest.json', 'icon-192.svg', 'icon-512.svg'):
        (directory / name).write_bytes(git_file(ref, name))


def network(route):
    url = route.request.url
    host = urlparse(url).hostname or ''
    if host == '127.0.0.1':
        return route.continue_()
    # Дозволені лише шрифти та бібліотеки, навіть невідомий API блокується.
    if host not in ('cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'unpkg.com', 'fonts.googleapis.com', 'fonts.gstatic.com') or route.request.method != 'GET':
        return route.abort()
    if url not in CDN:
        response = route.fetch(timeout=20000)
        CDN[url] = {'status': response.status, 'headers': response.headers, 'body': response.body()}
    hit = CDN[url]
    route.fulfill(**hit)


MEASURE = """() => ({theme:document.documentElement.dataset.theme,
 viewport:{width:innerWidth,height:innerHeight}, scrollHeight:document.documentElement.scrollHeight,
 bodyHeight:document.body.scrollHeight, scrollWidth:document.documentElement.scrollWidth,
 blocks:[...document.querySelectorAll('main h1,main h2,main h3,.card,.card-label,.dv-accs,.dv-kpi,.dv-fc,.dv-bud,.dv-near,.dv-recent,.o-recent,.bud-kpis,.ck-kpis')].map(e=>{
 const b=e.getBoundingClientRect();return {className:e.className,text:e.innerText.slice(0,140),
 top:Math.round(b.top),bottom:Math.round(b.bottom),visible:b.width>0&&b.height>0&&b.top<innerHeight&&b.bottom>0,
 fullyVisible:b.width>0&&b.height>0&&b.top>=0&&b.bottom<=innerHeight}})})"""


def capture(page, ref, theme, width, height, view, errors):
    stem = f'{view}-{theme}-{width}x{height}'
    directory = OUT / ref
    page.screenshot(path=str(directory / f'{stem}.png'))
    page.screenshot(path=str(directory / f'{stem}-full.png'), full_page=True)
    result = page.evaluate(MEASURE)
    result.update(ref=ref, view=view, synthetic=True, errors=list(errors), screenshot=f'{ref}/{stem}.png')
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for ref in REFS:
        build(ref)
    server = Server(OUT)
    results = []
    server.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for ref in REFS:
                    for theme in ('dark', 'light'):
                        for width, height in VIEWPORTS:
                            context = browser.new_context(viewport={'width': width, 'height': height},
                                is_mobile=width < 500, has_touch=width < 500, timezone_id='Europe/Kyiv',
                                color_scheme=theme, service_workers='block')
                            try:
                                context.route('**/*', network)
                                context.add_init_script(f"localStorage.setItem('theme','{theme}');localStorage.setItem('tour_done','1');localStorage.setItem('gestures_seen','1');")
                                page = context.new_page()
                                page.clock.set_fixed_time('2026-10-10T12:00:00+03:00')
                                errors = []
                                page.on('pageerror', lambda error: errors.append(str(error)))
                                page.goto(f'http://127.0.0.1:{server.port}/{ref}/index.html', wait_until='networkidle', timeout=60000)
                                page.wait_for_selector('.side' if width > 500 else '.tab-bar', timeout=20000)
                                page.evaluate('document.fonts.ready')
                                page.wait_for_timeout(500)
                                assert page.locator('html').get_attribute('data-theme') == theme
                                results.append(capture(page, ref, theme, width, height, 'overview', errors))
                                print(f'READY {ref} {theme} {width}x{height}', flush=True)
                                if ref == '6c64a08' and width == 1440:
                                    for label, view in (('Бюджет', 'budget'), ('Календар', 'calendar')):
                                        button = page.locator('.side-nav button').filter(has_text=label)
                                        if button.count():
                                            button.click()
                                            page.wait_for_timeout(500)
                                            results.append(capture(page, ref, theme, width, height, view, errors))
                            finally:
                                context.close()
            finally:
                browser.close()
    finally:
        server.stop()
        (OUT / 'metadata.json').write_text(json.dumps({'synthetic': True, 'fixedDate':'2026-10-10',
            'network':'localhost and React/font CDN only; all other domains aborted', 'results':results}, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not any(item['errors'] for item in results), 'Historical render has JS errors; see metadata.json'
    print(f'PASS {len(results)} views; browser and server stopped', flush=True)


if __name__ == '__main__':
    main()
