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
