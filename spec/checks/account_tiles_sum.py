"""v219: картки рахунків на Огляді сходяться з «Доступні кошти» і «Баланс».
Кредитна картка без боргу з власними коштами (Monobank без ліміту) показує власні кошти, а не 0.
Ворота цифр: «На картках» = сума додатних карток без готівки; «Власні» = готівка + на картках;
«Мінусові» = сума боргів карток; Баланс = Власні - Мінусові."""
import json
import re

from helpers import check, freeze, shot
from checks.live_refresh import MOCK, updated

ACCOUNTS = [
    {'id': 1, 'name': 'Synthetic cash', 'bank': 'cash', 'kind': 'cash', 'balance': 1000, 'debt': 0,
     'active': True, 'sort_order': 0, 'balance_updated_at': '2026-10-10T00:00:00Z'},
    {'id': 2, 'name': 'Synthetic debit', 'bank': 'oschad', 'kind': 'debit', 'balance': 2000, 'debt': 0,
     'active': True, 'sort_order': 1, 'balance_updated_at': '2026-10-10T00:00:00Z'},
    {'id': 3, 'name': 'Synthetic mono own', 'bank': 'mono', 'kind': 'credit', 'balance': 571.22, 'debt': 0,
     'credit_limit': 0, 'mono_account_id': 'syn-own', 'active': True, 'sort_order': 2, 'balance_updated_at': '2026-10-10T00:00:00Z'},
    {'id': 4, 'name': 'Synthetic privat credit', 'bank': 'privat', 'kind': 'credit', 'balance': 0, 'debt': 300,
     'credit_limit': 1000, 'active': True, 'sort_order': 3, 'balance_updated_at': '2026-10-10T00:00:00Z'},
]


def money(t):
    t = t.replace('−', '-').replace('\xa0', ' ')
    m = re.search(r'-?[\d ]+(?:,\d+)?', t)
    return round(float(m.group(0).replace(' ', '').replace(',', '.')) * 100)


def tiles(page):
    page.emulate_media(reduced_motion='reduce')
    mock = MOCK.replace('window.supabase={createClient:()=>sb};',
                        'm.data.accounts=' + json.dumps(ACCOUNTS) + ';window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, '2026-10-12')
    updated(page)
    page.wait_for_selector('.kpi-funds [data-r=cards] .kpi-rv')
    page.wait_for_timeout(1500)
    cards = page.evaluate("""()=>[...document.querySelectorAll('.bcard')].map(c=>({t:c.innerText,s:c.querySelector('.bcard-sum').innerText}))""")
    by = {}
    for a in ACCOUNTS:
        hit = [c for c in cards if a['name'] in c['t']]
        check(len(hit) >= 1, f'немає картки {a["name"]}')
        by[a['id']] = money(hit[0]['s'])
    check(by == {1: 100000, 2: 200000, 3: 57100, 4: -30000}, f'суми карток (цілі гривні) {by}')
    by = {1: 100000, 2: 200000, 3: 57122, 4: -30000}  # точні суми рахунків для панелей з копійками
    row = lambda r: money(page.locator(f'.kpi-funds [data-r={r}] .kpi-rv').first.inner_text())
    on_cards = sum(v for k, v in by.items() if k != 1 and v > 0)
    check(row('cash') == by[1], f'Готівка {row("cash")} != картка {by[1]}')
    check(row('cards') == on_cards, f'На картках {row("cards")} != сума карток {on_cards}')
    bal = page.locator('.kpi-balance')
    own = money(bal.locator('[data-r=own] .kpi-rv').inner_text())
    minus = money(bal.locator('[data-r=minus] .kpi-rv').inner_text())
    total = money(bal.locator('.kpi-v, .kpi-value').first.inner_text()) if bal.locator('.kpi-v, .kpi-value').count() else None
    check(own == by[1] + on_cards, f'Власні {own} != готівка + на картках {by[1] + on_cards}')
    check(minus == sum(v for v in by.values() if v < 0), f'Мінусові {minus}')
    if total is not None:
        check(total == own + minus, f'Баланс {total} != {own} + {minus}')
    shot(page, 'account-tiles-sum-' + ('desktop' if page.viewport_size['width'] >= 1024 else 'mobile') + '.jpg', full=False)


CHECKS = [
    ('Огляд: картки рахунків = доступні кошти і баланс, власні кошти кредитки без боргу (ПК)', 'desktop', tiles),
]
