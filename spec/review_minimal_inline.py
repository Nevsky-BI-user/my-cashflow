"""Перевіряє реальний макет у sandbox-обгортці розмови; закриває Chromium."""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'spec' / '.out' / 'redesign'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={'width': 1120, 'height': 1000}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto((OUT / 'minimal-inline-rendered.html').as_uri())
            frame = page.frame_locator('iframe').first
            desktop = frame.locator('#cashflow-minimal-desktop')
            desktop.locator('.hero').wait_for()
            assert desktop.locator('.cf-nav button').count() == 5, 'Пʼять розділів навігації'
            desktop.locator('.cf-nav svg').first.wait_for()
            assert desktop.locator('.cf-nav svg').count() == 5, 'Піктограми runtime завантажені'
            for theme in ('dark', 'light'):
                desktop.locator('#theme').click()
                assert desktop.get_attribute('data-theme') == theme
                for name in ('overview', 'budget', 'operations', 'payments', 'savings'):
                    desktop.locator(f'[data-page="{name}"]').first.click()
                    assert desktop.locator('#content').inner_text().strip()
                desktop.locator('[data-page="overview"]').first.click()
                desktop.screenshot(path=str(OUT / f'minimal-inline-desktop-{theme}.png'))
            desktop.locator('[data-action="formula"]').first.click()
            assert desktop.locator('#dialog').is_visible()
            page.keyboard.press('Escape')
            assert not desktop.locator('#dialog').is_visible()
            assert desktop.locator('[data-action="formula"]').first.evaluate('(el)=>el.getRootNode().activeElement===el')

            inner = page.frames[1]
            # Runtime каруселі лишається власником вибору; тут показуємо другий варіант для тесту.
            inner.evaluate("""()=>{document.querySelector('[data-variant="Компʼютер"]').hidden=true;
                document.querySelector('[data-variant="Телефон"]').hidden=false;}""")
            phone = frame.locator('#cashflow-minimal-phone')
            phone.locator('.hero').wait_for()
            for theme in ('light', 'dark'):
                if theme == 'dark':
                    phone.locator('#theme').click()
                assert phone.get_attribute('data-theme') == theme
                phone.screenshot(path=str(OUT / f'minimal-inline-phone-{theme}.png'))
            for width in (390, 320):
                page.set_viewport_size({'width': width, 'height': 844})
                assert phone.evaluate('(el)=>el.scrollWidth<=el.clientWidth'), f'Телефон: overflow {width}'
                phone.locator('[data-page="budget"]').first.click()
                phone.locator('[data-page="overview"]').first.click()
            assert not errors, errors
            print('PASS inline: themes, five pages, desktop/phone, 320px, icons, dialog and focus.')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
