"""Перевірка справжнього входу та версії: без входу в Google й без приватних даних."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from preview import ROOT, Server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    parser.add_argument('--version')
    args = parser.parse_args()
    server = None if args.url else Server(directory=ROOT)
    url = args.url or server.start()
    shots = ROOT / 'spec' / '.out' / 'shots'
    shots.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for width, height in [(1280, 800), (390, 844)]:
                    context = browser.new_context(viewport={'width': width, 'height': height}, color_scheme='dark')
                    try:
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
                        page.goto(url, wait_until='networkidle', timeout=45000)
                        button = page.get_by_role('button', name='Увійти через Google', exact=True)
                        button.wait_for(state='visible', timeout=20000)
                        assert button.count() == 1
                        assert page.locator('input[type=password],input[type=email]').count() == 0
                        assert page.locator('.p-overview').count() == 0, 'private dashboard visible without login'
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert not errors, errors
                        version = page.evaluate('APP_VER')
                        if args.version:
                            assert version == args.version, (version, args.version)
                        page.screenshot(path=str(shots / f'release-login-{width}.png'))
                        results.append({'width': width, 'version': version, 'login': 'Google only', 'errors': 0})
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        if server:
            server.stop()
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
