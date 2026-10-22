"""Телефон, Платежі, «Платежі до зарплати»: як таблиця ПК, від початку поточного періоду; сплачене лишається."""
import re
from helpers import check, freeze, go_tab

DAY = '2026-10-22'
LO = (10, 21)  # початок поточного періоду (аванс 21-го)


def _rows(page):
    return page.locator('.cm-event').evaluate_all(
        "rs=>rs.map(r=>({d:r.querySelector('.cm-date').textContent,n:r.querySelector('.cm-name span').textContent,"
        "paid:!!r.querySelector('.fx-paid')}))")


def _dm(t):
    m = re.match(r'(\d{1,2})\.(\d{2})', t.strip())
    check(m, f'дата рядка {t!r}')
    return int(m.group(2)), int(m.group(1))


def run(page):
    freeze(page, DAY)
    go_tab(page, 3)
    page.wait_for_timeout(300)
    page.locator('.cm-month summary').click()
    rows = _rows(page)
    check(rows, 'список подій порожній')
    early = [r for r in rows if _dm(r['d']) < LO and not r['paid']]
    check(not early, f'неоплачене до початку періоду в списку: {early}')
    check(any(_dm(r['d']) >= LO for r in rows), f'немає подій поточного періоду: {rows}')


CHECKS = [
    ('Платежі телефон: до зарплати без неоплаченого до початку періоду', 'mobile', run),
]
