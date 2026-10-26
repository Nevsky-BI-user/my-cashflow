"""Calendar UI contracts: exact day events, navigation and unchanged projection."""
from datetime import date
from collections import defaultdict
from helpers import check, finance_ref, freeze, go_tab, shot, num, open_calendar_day

DAY = '2026-10-13'
MO = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень', 'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'


def list_range(p):
    """Projection period boundary retained for other financial checks."""
    from datetime import timedelta
    n = p['nextPlan']
    sal = n['nextPayout']['date'] if n['nextPayout']['kind'] == 'salary' else n['followingPayout']['date']
    return p['currentPeriod']['start'], (date.fromisoformat(sal) - timedelta(days=1)).isoformat()


def day_events(page, projection, month):
    """Compare exact displayed planned amounts and daily forecast with reference.

    Period rollups and cumulative balance report were explicitly removed. Daily
    details replace those presentation assertions; the reference is not changed.
    """
    groups = defaultdict(list)
    for event in projection['events']:
        if event['date'].startswith(month):
            groups[event['date']].append(event)
    check(groups, 'fixture has no calendar events')
    for iso, events in sorted(groups.items()):
        details = open_calendar_day(page, iso)
        rows = details.locator('.cal-day-events .cal-day-row')
        rendered = rows.evaluate_all("es=>es.map(e=>({name:e.querySelector('.cal-day-name b').textContent,amount:e.querySelector('.cal-day-amount').textContent,kind:e.dataset.eventKind}))")
        for event in events:
            if event['kind'] in ('variable', 'repay') or (event['id'].startswith('budget-savings:') and not event['amountCents']):
                continue
            matches = [r for r in rendered if r['name'].removesuffix(' (розстрочка)') == event['name'].removesuffix(' (розстрочка)')]
            check(matches, f'{iso}: missing event {event["name"]}: {rendered}')
            check(any(abs(round(abs(num(r['amount']))*100)-abs(event['amountCents'])) <= 1 for r in matches), f'{iso}: amount differs from projection: {event}, {matches}')
        repayments = [e for e in events if e['kind'] == 'repay']
        repaid = [r for r in rendered if r['kind'] == 'repay' and r['name'].startswith('Погашення ')]
        check(sorted(round(num(r['amount'])*100) for r in repaid) == sorted(-abs(e['amountCents'] or e['debtDeltaCents']) for e in repayments), f'{iso}: repayment count or exact amount differs from projection: {repaid}, {repayments}')
        for event in repayments:
            planned = event.get('plannedRepaymentDate') or iso
            label = 'додатково' if iso < planned else 'прострочене' if iso > planned else 'обовʼязкове'
            check(any(r['name'].endswith(' · '+label) and round(abs(num(r['amount']))*100) == abs(event['amountCents'] or event['debtDeltaCents']) for r in repaid), f'{iso}: repayment schedule label incorrect')
        variables = [e for e in events if e['kind'] == 'variable']
        forecasts = [r for r in rendered if r['name'] == 'Щоденні витрати, прогноз']
        check(len(forecasts) == bool(variables), f'{iso}: daily forecast duplicated or missing')
        if variables:
            check(round(num(forecasts[0]['amount'])*100) == -sum(e['amountCents'] for e in variables), f'{iso}: daily forecast sum differs from projection')
        check(rows.locator('.cal-day-amount').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)'), f'{iso}: amount clipped')
        check(rows.locator('.cal-day-name').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)'), f'{iso}: event name clipped')
    page.keyboard.press('Escape')


def desktop(page):
    freeze(page, DAY)
    go_tab(page, 3)
    cal=page.locator('.panel.p-credits.desk')
    check(cal.locator('.ck-kpis .ck-kpi').count()==3,'missing top KPIs')
    kt=cal.locator('.ck-kpis').inner_text().lower()
    for label in ('Обовʼязкові до наступної виплати','Розстрочки','Борги','/міс','залишок'):
        check(label.lower() in kt,f'missing KPI {label}')
    check('до 25.' not in kt,'obsolete due date')
    check(cal.locator('.ck-side,.ck-day,.cal-tbl,.ck-crs,.ck-fixed,.ck-under,.cal-fc').count()==0,'removed reports remain')
    check(page.evaluate("getComputedStyle(document.querySelector('.cal-days')).gridTemplateColumns.split(' ').length")==7,'calendar is not seven columns')
    check(page.locator('.cal-cell').count()==31,'October days missing')
    check(page.evaluate("Math.max(...[...document.querySelectorAll('.cal-cell')].map(e=>e.querySelectorAll('.cal-ln').length))")<=2,'too many preview rows')
    today=cal.locator('.cal-cell.today')
    check(today.count()==1 and today.locator('.cal-dn').inner_text()=='13','today date incorrect')
    check('inset' in today.evaluate('e=>getComputedStyle(e).boxShadow'),'today is not highlighted')
    past=page.locator('.cal-cell.past .cal-dn').all_inner_texts()
    check([int(x) for x in past]==list(range(1,13)),'past dates incorrect')
    bg=page.evaluate("""()=>{const g=s=>getComputedStyle(document.querySelector(s)).backgroundColor;return [g('.cal-cell.past:not(.we)'),g('.cal-cell.future:not(.we)'),g('.cal-cell.today')]}""")
    check(bg[0]!=bg[1] and bg[0]!=bg[2] and bg[0] not in ('transparent','rgba(0, 0, 0, 0)'),f'past background not distinct: {bg}')
    check(cal.locator('.cal-badge',has_text='А').count()==1 and cal.locator('.cal-badge',has_text='З').count()==1,'payout badges missing')
    projection=finance_ref(page)
    check(any(e['kind']=='repay' and e['date'].startswith(DAY[:7]) for e in projection['events']),'fixture has no repayment')
    check(not any(e['funding']=='credit' for e in projection['events']),'payments moved to credit automatically')
    day_events(page,projection,DAY[:7])
    page.locator('.ck-arr[aria-label="Наступний місяць"]').click()
    check(page.locator('.ck-month').inner_text()=='Листопад 2026','next month incorrect')
    check(page.locator('.cal-cell.today,.cal-cell.past').count()==0,'future month has past/today dates')
    page.locator('.ck-arr[aria-label="Попередній місяць"]').click()
    check(page.locator('.ck-month').inner_text()=='Жовтень 2026','previous month incorrect')
    days={d['date']:d for d in projection['days']}
    shift=projection['snapshot']['positiveOwnCents']-projection['snapshot']['cashCents']
    for cell in page.locator('.cal-cell:has(.cal-bal)').all():
        iso=cell.get_attribute('data-date')
        if iso>=DAY:
            value=num(cell.locator('.cal-bal').inner_text())
            check(abs(value-(days[iso]['netCents']+shift)/100)<=1,f'{iso}: calendar balance differs from projection')
    for width,height in ((1280,720),(1920,1080),(1920,900)):
        page.set_viewport_size(dict(width=width,height=height))
        page.wait_for_timeout(200)
        check(page.evaluate(NO_HSCROLL),'horizontal page scroll')
        check(page.evaluate('document.documentElement.scrollHeight<=innerHeight+1'),'vertical page scroll')
        check(page.locator('.ck-cal').evaluate('e=>e.getBoundingClientRect().bottom<=innerHeight+1'),'calendar clipped')
        check(page.locator('.ck-cal').evaluate('e=>e.getBoundingClientRect().width>=document.querySelector(".calendar-only").getBoundingClientRect().width-2'),'calendar not full width')
    shot(page,'cal-1920.jpg',full=False)


def short_frame(page):
    page.set_viewport_size(dict(width=1920,height=900))
    freeze(page,'2026-10-08',[("mono_account_id:'demo-mono',balance:12500,","mono_account_id:'demo-mono',balance:500,")])
    go_tab(page,3)
    projection=finance_ref(page)
    check(any(d['shortfallCents']>0 for d in projection['days'] if d['date'].startswith('2026-10')),'fixture has no shortfall')
    check(page.locator('.cal-cell.short').count()==0,'red shortage frames remain')
    check(page.evaluate("""()=>[...document.querySelectorAll('.cal-cell:not(.today):not(.sel)')].every(e=>!getComputedStyle(e).boxShadow.includes('inset'))"""),'shortage adds inset frames')
    negatives=page.locator('.cal-bal.neg')
    check(negatives.count()>0,'fixture renders no negative balance')
    check(negatives.evaluate_all("es=>es.every(e=>{const c=getComputedStyle(e).color.match(/[\\d.]+/g).map(Number);return c[0]>c[1]+60&&c[0]>c[2]+60})"),'negative balance not red')
    day_events(page,projection,'2026-10')


def mobile(page):
    freeze(page,DAY)
    go_tab(page,3)
    check(page.locator('.cal-cell').count()==31,'mobile grid missing dates')
    check(page.locator('.cal-cell.past').count()==12,'past dates incorrect')
    check(page.evaluate(NO_HSCROLL),'mobile calendar wider than screen')
    projection=finance_ref(page)
    day_events(page,projection,DAY[:7])
    details=open_calendar_day(page,DAY)
    check(details.is_visible(),'today details inaccessible')
    check(page.evaluate(NO_HSCROLL),'details wider than phone')
    shot(page,'cal-mobile.jpg',full=False)


CHECKS=[
    ('Календар: KPI, дати, точні події, навігація, баланс і повна ширина','desktop',desktop),
    ('Календар телефону: точні події та деталі дня','mobile',mobile),
    ('Календар: нестача без червоних рамок, точні суми','desktop',short_frame),
]
