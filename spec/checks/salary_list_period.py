"""Телефон, Платежі, «Платежі до зарплати»: як таблиця ПК, від початку поточного періоду; сплачене лишається."""
import re
from helpers import check, freeze, go_tab, open_calendar_day

DAY = '2026-10-22'
LO = (10, 21)  # початок поточного періоду (аванс 21-го)


def run(page):
    # The period report was removed; month cells retain access to earlier and future events.
    from helpers import finance_ref
    from checks.calendar import day_events
    freeze(page, DAY)
    go_tab(page, 3)
    check(page.locator('.cm-month,.cm-event').count() == 0, 'removed period report remains')
    projection=finance_ref(page)
    check(projection['currentPeriod']['start']=='2026-10-21', 'current period changed')
    day_events(page,projection,'2026-10')
    day_events(page,projection,'2026-11')


CHECKS = [
    ('Платежі телефон: до зарплати без неоплаченого до початку періоду', 'mobile', run),
]
