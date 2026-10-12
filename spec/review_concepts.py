"""Перевіряє локальні ескізи, зберігає скриншоти; закриває Chromium."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'spec' / '.out' / 'redesign'
OUT.mkdir(parents=True, exist_ok=True)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for theme in ('light', 'dark'):
                for width in (360, 390, 768, 1280, 1440, 1920):
                    context = browser.new_context(
                        viewport={'width': width, 'height': 844 if width < 600 else 1000},
                        is_mobile=width < 600, has_touch=width < 600,
                        reduced_motion='reduce', timezone_id='Europe/Kyiv')
                    try:
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto((ROOT / 'docs/redesign/concepts.html').as_uri() + '?theme=' + theme)
                        page.wait_for_load_state('networkidle')
                        assert page.locator('html').get_attribute('data-theme') == theme
                        for section in ('overview', 'plan', 'operations', 'payments', 'savings'):
                            page.locator(f'nav [data-page="{section}"]:visible').first.click()
                            assert page.locator('#' + section).is_visible()
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (theme, width, section, 'overflow')
                            if width in (390, 1440):
                                page.screenshot(path=str(OUT / f'{theme}-{width}-{section}.png'))
                                if section == 'overview':
                                    page.screenshot(path=str(OUT / f'{theme}-{width}-overview-full.png'), full_page=True)
                                    page.locator('section').filter(has=page.get_by_role('heading', name='Гроші протягом періоду', exact=True)).screenshot(path=str(OUT / f'{theme}-{width}-forecast.png'))
                        page.locator('nav [data-page="overview"]:visible').first.click()
                        explanation = page.get_by_role('button', name='Як пораховано', exact=True)
                        explanation.click()
                        assert page.locator('#explanation').is_visible()
                        page.keyboard.press('Escape')
                        assert not page.locator('#explanation').is_visible()
                        assert explanation.evaluate('(el)=>el===document.activeElement')
                        page.locator('[data-action="credit"]:visible').first.click()
                        assert page.locator('#credit-option').is_visible()
                        page.keyboard.press('Escape')
                        assert not errors, errors
                        results.append({'theme': theme, 'width': width, 'pages': 5, 'passed': True})
                    finally:
                        context.close()
        finally:
            browser.close()
    (OUT / 'verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'PASS: {len(results)} viewport/theme combinations, 60 pages, dialogs and focus.')
    print(str(OUT))


if __name__ == '__main__':
    main()
