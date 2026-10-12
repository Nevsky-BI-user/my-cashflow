"""Перевірки окремого локального ескізу. Chromium закривається у finally."""
import json
import re
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / 'docs/redesign/minimal-concepts.html'
OUT = ROOT / 'spec/.out/redesign'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    script = re.findall(r'<script[^>]*>([\s\S]*?)</script>', HTML.read_text(encoding='utf-8'))[-1]
    subprocess.run(['node', '-e', 'new Function(require("fs").readFileSync(0,"utf8"));console.log("JS syntax PASS")'], input=script, text=True, encoding='utf-8', check=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for theme in ('light', 'dark'):
                for width in (320, 360, 390, 768, 1280, 1440, 1920):
                    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                    try:
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(HTML.as_uri())
                        if theme == 'dark':
                            page.locator('#theme').click()
                        assert page.locator('html').get_attribute('data-theme') == theme
                        for view in ('overview', 'budget', 'operations', 'payments', 'savings'):
                            page.locator(f'nav [data-page="{view}"]').click()
                            assert page.locator('main h1').is_visible()
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (theme, width, view, 'overflow')
                            assert '???' not in page.locator('main').inner_text()
                            if view in ('overview', 'budget'):
                                assert page.locator('.chart .balance').is_visible()
                                assert page.locator('.chart .balance').get_attribute('d').startswith('M')
                                if width in (390, 1440):
                                    page.screenshot(path=str(OUT / f'minimal-{theme}-{width}-{view}.png'), full_page=True)
                        page.locator('nav [data-page="overview"]').click()
                        assert '8\xa0800' in page.locator('#hero-value').inner_text()
                        button = page.locator('[data-action="formula"]').first
                        button.click()
                        assert page.locator('dialog').is_visible()
                        assert '6\xa0200' in page.locator('dialog').inner_text()
                        page.keyboard.press('Escape')
                        assert not page.locator('dialog').is_visible()
                        assert button.evaluate('(el)=>el===document.activeElement')
                        page.locator('#day-select').select_option('15')
                        assert '-6\xa0200' in page.locator('#day-remaining').inner_text()
                        page.locator('[data-action="credit"]').click()
                        page.locator('[data-action="credit-on"]').click()
                        assert page.locator('[data-action="credit"]').evaluate('(el)=>el===document.activeElement')
                        assert '15\xa0000' in page.locator('#hero-value').inner_text()
                        assert page.locator('#day-remaining').inner_text() == '0,00 ₴'
                        assert page.evaluate('plan().newDebtCents') == 620000
                        assert page.evaluate('plan().schedule.reduce((s,d)=>s+d.spendCents,0)') == 1500000
                        assert page.evaluate('plan().days') == 16
                        page.locator('#example').select_option('rich')
                        assert '26\xa0800' in page.locator('#hero-value').inner_text()
                        assert page.evaluate('plan().averageDailyCents') == 167500
                        assert page.evaluate('plan().endingCents') == 0
                        page.locator('#example').select_option('negative')
                        assert page.evaluate('plan().baseAvailableCents') < 0
                        page.locator('#example').select_option('normal')
                        page.locator('nav [data-page="budget"]').click()
                        before = page.locator('.chart rect').first.get_attribute('height')
                        page.locator('[data-action="edit"]').click()
                        page.locator('#weight-food').fill('50')
                        page.locator('#weights-form button').click()
                        assert page.locator('dialog').is_visible()
                        assert page.locator('#weights-error').inner_text()
                        page.locator('#weight-transport').fill('10')
                        page.locator('#weights-form button').click()
                        assert not page.locator('dialog').is_visible()
                        assert page.locator('[data-action="edit"]').evaluate('(el)=>el===document.activeElement')
                        assert page.locator('.chart rect').first.get_attribute('height') != before
                        assert page.evaluate('plan().categories[0].totalCents') == 750000
                        page.locator('nav [data-page="operations"]').click()
                        page.locator('#search').fill('крамниця')
                        assert page.locator('#operation-rows .row').count() == 1
                        page.locator('#search').fill('')
                        page.locator('#op-filter').select_option('income')
                        assert page.locator('#operation-rows .row').count() == 1
                        page.locator('nav [data-page="payments"]').click()
                        page.locator('[data-payment="paid"]').click()
                        assert page.locator('.paymentrow').count() == 1
                        page.locator('nav [data-page="savings"]').click()
                        page.locator('[data-goal="0"]').click()
                        page.locator('#contribution').fill('-1')
                        page.locator('#goal-form button').click()
                        assert page.locator('dialog').is_visible()
                        page.locator('#contribution').fill('3000')
                        page.locator('#goal-form button').click()
                        assert page.locator('dialog').is_visible()
                        page.locator('#contribution').fill('500')
                        page.locator('#goal-form button').click()
                        assert '42\xa0500' in page.locator('.goal-amount').first.inner_text()
                        assert page.evaluate('plan().baseAvailableCents') == 830000
                        assert page.locator('[data-goal="0"]').evaluate('(el)=>el===document.activeElement')
                        assert not errors, errors
                        results.append({'theme': theme, 'width': width, 'pages': 5, 'passed': True})
                    finally:
                        context.close()
        finally:
            browser.close()
    (OUT / 'minimal-verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'PASS: {len(results)} viewport/theme combinations, 70 pages; calculations, editing, filters, dialogs, focus, reduced motion.')


if __name__ == '__main__':
    main()
