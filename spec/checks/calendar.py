# ПК-Календар v139 (DESIGN.md п. 12): KPI, компактна сітка місяця 7 колонок (повні назви подій, до 2 рядків, інакше «+N»),
# минулі дні приглушеним тлом, сьогодні виділене; праворуч таблиця «Події і баланс» на всю висоту (каса по датах);
# клік по дню: розклад балансу; v149 без червоних рамок, мінус червоним лише в колонці балансу; 1920x1080 без прокрутки
import re
from datetime import date

from helpers import check, finance_ref, freeze, go_tab, shot

MO = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень', 'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
NO_HSCROLL = 'document.documentElement.scrollWidth <= document.documentElement.clientWidth'
# найменший кегль тексту в сітці й таблиці (лише елементи з власним текстом)
MIN_FS = """sel=>Math.min(...[...document.querySelectorAll(sel+' *')].filter(e=>e.offsetParent&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).map(e=>parseFloat(getComputedStyle(e).fontSize)))"""
ROWS = """[...document.querySelectorAll('.ck-day .cal-tbl .cal-ev')].map(r=>({d:r.dataset.date,b:r.dataset.bal==null?null:Number(r.dataset.bal),
h:r.getBoundingClientRect().height,top:r.getBoundingClientRect().top,bot:r.getBoundingClientRect().bottom,o:r.scrollHeight>r.clientHeight+1,c:r.className,n:r.querySelector('.ce-n').textContent,a:r.querySelector('.ce-b').textContent}))"""


def desktop(page):
    go_tab(page, 3)
    cal = page.locator('.panel.p-credits.desk')
    check(cal.count() == 1, 'на ПК немає окремого Календаря')
    t = date.today()
    kpis = cal.locator('.ck-kpis .ck-kpi')
    check(kpis.count() == 3, f'KPI {kpis.count()}, а не 3')
    kt = cal.locator('.ck-kpis').inner_text().lower()
    for s in ('Обовʼязкові до наступної виплати', 'Розстрочки', 'Борги', '/міс', 'залишок'):
        check(s.lower() in kt, f'у рядку KPI немає «{s}»')
    check('до 25.' not in kt, f'у KPI лишилось «до 25»: {kt!r}')
    # картки розстрочок і постійних платежів з ПК прибрано
    check(cal.locator('.ck-crs, .ck-fixed, .ck-under, .cal-fc').count() == 0, 'на ПК лишились картки розстрочок, постійних або повзунок')
    cols = page.evaluate("getComputedStyle(document.querySelector('.ck-cal .cal-days')).gridTemplateColumns.split(' ').length")
    check(cols == 7, f'у сітці {cols} колонок')
    hs = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.getBoundingClientRect().height)")
    check(len(hs) >= 28 and min(hs) >= 64, f'клітинки нижчі за 64px: {min(hs) if hs else None}')
    many = page.evaluate("Math.max(0,...[...document.querySelectorAll('.ck-cal .cal-cell')].map(e=>e.querySelectorAll('.cal-ln').length))")
    check(many <= 2, f'у клітинці {many} рядків подій, а не до 2')
    # 10.10.2026: коротка назва у вузькій клітинці, повна: у доступному розкладі дня.
    names = page.locator('.ck-cal .cal-nm')
    for i in range(names.count()):
        name = names.nth(i).inner_text()
        cell = names.nth(i).locator('xpath=ancestor::*[contains(@class,"cal-cell")][1]')
        if cell.get_attribute('aria-pressed') != 'true':
            cell.click()
        page.wait_for_timeout(100)
        details=page.inner_text('.ck-day-events')
        # v143: змінні витрати в клітинках не показуються (рядок прогнозу на період у таблиці)
        check(not name.startswith('Щоденні витрати'), f'у клітинці лишився рядок змінних витрат: {name}')
        check(name in details, f'Повна назва недоступна після вибору дня: {name}')

    check(page.evaluate("[...document.querySelectorAll('.ck-bd-list .ce-n')].every(e=>e.scrollWidth<=e.clientWidth+1)"), 'Назви розкладу дня обрізані')
    page.locator('.ck-day .ck-link').click()
    _var_rows(page)
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', f'заголовок місяця: {page.inner_text(".ck-month")!r}')
    today = cal.locator('.cal-cell.today')
    check(today.count() == 1, 'немає клітинки «сьогодні»')
    sh = today.evaluate("e=>getComputedStyle(e).boxShadow")
    check('inset' in sh and '2px 0px 0px' in sh, f'сьогодні без лівої смуги акценту: {sh}')
    check(today.locator('.cal-dn').inner_text() == str(t.day), 'обведене не сьогоднішнє число')
    # минулі дні: приглушене тло, відмінне від майбутніх і від сьогодні
    past = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell.past')].map(e=>Number(e.querySelector('.cal-dn').textContent))")
    check(sorted(past) == list(range(1, t.day)), f'минулі дні не позначені: {past}')
    bg = page.evaluate("""(()=>{const g=s=>{const e=document.querySelector(s);return e?getComputedStyle(e).backgroundColor:null};
return{past:g('.ck-cal .cal-cell.past:not(.we)'),fut:g('.ck-cal .cal-cell.future:not(.we)'),today:g('.ck-cal .cal-cell.today')}})()""")
    check(bg['past'] and bg['past'] != bg['fut'] and bg['past'] != bg['today'] and bg['past'] not in ('rgba(0, 0, 0, 0)', 'transparent'), f'тло минулих днів не відрізняється: {bg}')
    check(cal.locator('.cal-badge', has_text='А').count() == 1 and cal.locator('.cal-badge', has_text='З').count() == 1, 'немає бейджів А і З')
    projection=finance_ref(page)
    repay=[e for e in projection['events'] if e['kind']=='repay' and e['date'][:7]==t.isoformat()[:7]]
    check(repay, 'немає погашення в поточному місяці')
    for e in repay:
        check(page.locator('.cal-tbl .cal-ev[data-date="'+e['date']+'"]',has_text='Погашення кредитки').count()>=1, 'погашення не на плановій даті')
    # v149 (власник: «менший шрифт другорядного»): назви в клітинках, баланс дня, факт і тихі мітки статусів від 11px, решта від 13px
    check(page.evaluate(MIN_FS, '.p-credits.desk .ck-cols') >= 11, f'текст у Календарі дрібніший за 11px: {page.evaluate(MIN_FS, ".p-credits.desk .ck-cols")}')
    check(page.evaluate(MIN_FS, '.p-credits.desk .cal-tbl .ce-a') >= 13 and page.evaluate(MIN_FS, '.p-credits.desk .cal-tbl .ce-b') >= 13, 'суми й баланс у таблиці дрібніші за 13px')
    page.mouse.move(2, 2)
    shot(page, 'cal-1280.jpg', full=False)
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1280')
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    page.wait_for_timeout(200)
    n = date(t.year + (t.month == 12), t.month % 12 + 1, 1)
    check(page.inner_text('.ck-month') == f'{MO[n.month - 1]} {n.year}', '→ не перейшов на наступний місяць')
    check(cal.locator('.cal-cell.today').count() == 0, 'у наступному місяці є «сьогодні»')
    check(cal.locator('.cal-cell.past').count() == 0, 'у наступному місяці є минулі дні')
    page.click('.ck-arr[aria-label="Попередній місяць"]')
    page.wait_for_timeout(200)
    check(page.inner_text('.ck-month') == f'{MO[t.month - 1]} {t.year}', '← не повернув місяць')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)
    w = page.evaluate("document.querySelector('.panel.p-credits').getBoundingClientRect().width")
    check(w <= page.evaluate('innerWidth - 220'), f'на 1920 Календар виходить за доступну область: {w}')
    check(page.evaluate(NO_HSCROLL), 'горизонтальний скрол на 1920')
    table_1920(page, t)
    breakdown(page, t)


PAYDAYS = """sel=>[...document.querySelectorAll(sel)].filter(c=>[...c.querySelectorAll('.cal-badge')].some(b=>/^[АЗ]$/.test(b.textContent.trim()))).map(c=>c.querySelector('.cal-dn')?c.querySelector('.cal-dn').textContent.trim():c.firstChild.textContent.trim())"""
CELLBAL = """d=>{const c=[...document.querySelectorAll('.ck-cal .cal-cell')].find(c=>c.querySelector('.cal-dn')&&c.querySelector('.cal-dn').textContent.trim()===d);const b=c&&c.querySelector('.cal-bal');return b?b.textContent:''}"""


def table_1920(page, t):
    """Сітка й таблиця в межах екрана; довгий список має лише погоджену внутрішню прокрутку."""
    cal = page.locator('.panel.p-credits.desk')
    wr = page.evaluate("document.querySelector('.ck-cal').getBoundingClientRect().width/document.querySelector('.ck-cols').getBoundingClientRect().width")
    check(0.5 <= wr <= 0.65, f'сітка займає {wr:.2f} ширини, а не 50-65 %')
    # таблиця на всю висоту колонки: нижній край картки таблиці = нижній край сітки
    gap = page.evaluate("Math.abs(document.querySelector('.ck-day').getBoundingClientRect().bottom-document.querySelector('.ck-cal').getBoundingClientRect().bottom)")
    check(page.evaluate("[...document.querySelectorAll('.ck-day,.ck-cal')].every(e=>e.getBoundingClientRect().bottom<=innerHeight)"), 'Сітка або розклад виходить за екран')
    check(page.evaluate("[...document.querySelectorAll('.ck-cal .cal-nm')].every(e=>getComputedStyle(e).whiteSpace!=='nowrap'&&e.scrollWidth<=e.clientWidth+1)"), 'На широкому екрані назви не переносяться повністю')
    pays = set(page.evaluate(PAYDAYS, '.ck-cal .cal-cell'))
    check(len(pays) == 2, f'у сітці не два дні виплат: {pays}')
    withbal = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-bal')).map(c=>c.querySelector('.cal-dn').textContent.trim())")
    allowed = pays | {str(t.day)}
    check(withbal and set(withbal) <= allowed, f'каса в клітинці не лише в дні виплат і сьогодні: {withbal}, дозволено {sorted(allowed)}')
    check(str(t.day) in withbal, 'у клітинці «сьогодні» немає каси')
    # v144: список від початку поточного періоду до дня перед наступною зарплатою, тому дні сітки до початку періоду в ньому не показуються
    lo, hi = list_range(finance_ref(page))
    evdays = page.evaluate("[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>c.querySelector('.cal-ln,.cal-more')).map(c=>c.dataset.date)")
    rows = page.evaluate(ROWS)
    isos = {r['d'] for r in rows}
    want = {d for d in evdays if lo <= d <= hi}
    check(want <= isos, f'у таблиці немає дат з подіями: {sorted(want - isos)}')
    check(all(lo <= d <= hi for d in isos), f'у таблиці дати поза {lo}..{hi}: {sorted(d for d in isos if not lo <= d <= hi)}')
    check(t.isoformat() in isos and any('today' in r['c'] for r in rows), 'у таблиці немає підсвіченого рядка «сьогодні»')
    hd = page.evaluate("document.querySelector('.ck-day').innerText")
    for s in ('Дата', 'Подія', 'Сума', 'Баланс після'):  # v149: баланс = власні мінус борг кредиток (як плитка «Баланс»)
        check(s in hd, f'у таблиці немає колонки «{s}»')
    for d in sorted(isos):
        # рядок прогнозу щоденних витрат (cal-ev-var) підсумовує період і балансу не має
        rr = [r for r in rows if r['d'] == d and 'cal-ev-var' not in r['c']]
        if not rr:
            continue
        if d >= t.isoformat():
            check(rr[-1]['b'] is not None and rr[-1]['a'].strip() != '', f'{d}: немає балансу після на останньому рядку дня')
        else:
            check(all(r['b'] is None and 'past' in r['c'] for r in rr), f'{d}: минулий рядок не приглушений або з балансом')
    # v149: рядки ростуть у висоту з довгою назвою, нічого не налазить і не обрізано
    check(all(r['h'] >= 27 and not r['o'] for r in rows), f'рядки таблиці нижчі за 28px або з переповненням: {sorted({round(r["h"]) for r in rows})}')
    check(all(rows[i + 1]['top'] >= rows[i]['bot'] - 1 for i in range(len(rows) - 1)), 'рядки таблиці налазять один на одного')
    projection=finance_ref(page)
    check(not any(e['funding']=='credit' for e in projection['events']), 'база автоматично переносить платежі на кредитку')
    days={d['date']:d for d in projection['days']}
    sh=projection['snapshot']['positiveOwnCents']-projection['snapshot']['cashCents']
    for d in sorted({r['d'] for r in rows if r['d']>=t.isoformat() and 'cal-ev-var' not in r['c']}):
        last=[r for r in rows if r['d']==d and 'cal-ev-var' not in r['c']][-1]
        if 'cal-ev-end' in last['c']:
            # v144: підсумковий рядок списку; v149: баланс на кінець дня перед зарплатою
            check(abs(last['b']-(days[d]['netCents']+sh)/100)<=1, 'баланс перед зарплатою не з проєкції '+d)
            continue
        # v149: «Баланс після» = каса мінус борг після останньої незмінної події дня плюс зсув (змінні витрати дня: у розкладі)
        evs=[e for e in projection['events'] if e['date']==d and e['kind']!='variable']
        want=(evs[-1]['cashAfterCents']-evs[-1]['debtAfterCents']+sh)/100 if evs else (projection['snapshot']['positiveOwnCents']-projection['snapshot']['creditDebtCents'])/100
        check(abs(last['b']-want)<=1, 'баланс календаря не з єдиної проєкції '+d)
    for d in pays:
        if int(d) >= t.day:
            cb = page.evaluate(CELLBAL, d)
            # v143: каса в клітинці = на кінець дня (зі змінними витратами дня), таблиця показує баланс після подій
            tb = (days[f"{t.isoformat()[:8]}{int(d):02d}"]['netCents'] + sh) / 100
            v = int(''.join(ch for ch in cb if ch.isdigit()) or 0) * (-1 if '−' in cb else 1)
            check(abs(v - tb) <= 1, f'{d}: у клітинці {cb!r}, у таблиці {tb}')
    scrollers=page.evaluate("""[...document.querySelectorAll('.content *')].filter(e=>e.offsetParent&&/auto|scroll/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+2).map(e=>({cls:e.className,allowed:e.matches('.ck-day,.ck-side'),bottom:e.getBoundingClientRect().bottom}))""")
    check(all(e['allowed'] and e['bottom']<=1081 for e in scrollers), f'непогоджені або необмежені скроли: {scrollers}')
    last=page.locator('.ck-day .cal-ev').last
    last.scroll_into_view_if_needed()
    check(last.evaluate("e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight+1}"), 'останній рядок недосяжний у межах екрана')
    check(page.evaluate('window.scrollY')==0, 'до останнього рядка прокрутилася вся сторінка')
    page.locator('.ck-day').evaluate('e=>e.scrollTop=0')
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 1080, f'Календар не вміщається в 1920x1080: {sh}')
    page.mouse.move(2, 2)
    shot(page, 'v139-cal-1920.jpg', full=False)
    page.set_viewport_size({'width': 1920, 'height': 900})
    page.wait_for_timeout(300)
    sh = page.evaluate('document.documentElement.scrollHeight')
    check(sh <= 900, f'Календар не вміщається в 1920x900: {sh}')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.wait_for_timeout(300)


def list_range(p):
    """v144: межі списку «Події і баланс» поточного місяця: початок поточного періоду і день перед наступною зарплатою."""
    from datetime import timedelta
    n = p['nextPlan']
    sal = n['nextPayout']['date'] if n['nextPayout']['kind'] == 'salary' else n['followingPayout']['date']
    return p['currentPeriod']['start'], (date.fromisoformat(sal) - timedelta(days=1)).isoformat()


def _var_rows(page):
    """Таблиця «Події і баланс»: один рядок прогнозу на кожен період у межах списку (до дня перед зарплатою), сума й діапазон за подіями рушія."""
    from collections import OrderedDict
    p = finance_ref(page)
    lo, hi = list_range(p)
    groups = OrderedDict()
    for e in p['events']:
        if e['kind'] != 'variable' or not lo <= e['date'] <= hi:
            continue
        q = next((q for q in p['periods'] if q['start'] <= e['date'] < q['end']), None)
        g = groups.setdefault(q['start'] if q else month, {'from': e['date'], 'to': e['date'], 'c': 0})
        g['c'] += e['amountCents']; g['from'] = min(g['from'], e['date']); g['to'] = max(g['to'], e['date'])
    rows = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev.cal-ev-var')].map(r=>({d:r.dataset.date,b:r.dataset.bal,n:r.querySelector('.ce-n').textContent,a:r.querySelector('.ce-a').textContent}))")
    check(len(rows) == len(groups), f'рядків прогнозу {len(rows)}, періодів зі змінними витратами {len(groups)}')
    dm = lambda s: s[8:10] + '.' + s[5:7]
    for r, g in zip(rows, groups.values()):
        amount = f"{round(g['c'] / 100):,}".replace(',', ' ')
        want = f"Щоденні витрати, прогноз: {amount} ₴ ({dm(g['from'])}-{dm(g['to'])})"
        check(r['d'] == g['from'] and r['b'] is None, f'рядок прогнозу не на першій даті або з балансом: {r}')
        check(r['n'].replace(' ', ' ') == want, f'рядок прогнозу {r["n"]!r}, очікувано {want!r}')
    last = page.evaluate("[...document.querySelectorAll('.cal-tbl .cal-ev')].map(r=>r.dataset.date).sort().pop()")
    check(last <= hi and rows and max(g['to'] for g in groups.values()) == hi, f'список не доходить до {hi}: останній рядок {last}')
    print(f'      рядки прогнозу: {[r["n"] for r in rows]}, список {lo}..{hi}')


def breakdown(page, t):
    """Клік по дню: розклад балансу (v149: баланс сьогодні = плитка «Баланс», події до дня з балансом після, підсумок = баланс дня з рушія;
    баланс сьогодні + надходження − відтоки = баланс на кінець; щоденні витрати дня одним рядком)."""
    cal = page.locator('.panel.p-credits.desk')
    rows = page.evaluate(ROWS)
    fut = [r for r in rows if int(r['d'][8:]) > t.day and r['b'] is not None]
    check(fut, 'у таблиці немає майбутніх рядків з балансом')
    iso = fut[-1]['d']
    # v143: підсумок розкладу = каса на кінець дня з рушія (змінні витрати дня в таблиці підсумовані рядком прогнозу)
    ref = finance_ref(page)
    sh = ref['snapshot']['positiveOwnCents'] - ref['snapshot']['cashCents']
    want = (next(d for d in ref['days'] if d['date'] == iso)['netCents'] + sh) / 100
    now_bal = (ref['snapshot']['positiveOwnCents'] - ref['snapshot']['creditDebtCents']) / 100
    page.click(f'.ck-cal .cal-cell[data-date="{iso}"]')
    page.wait_for_timeout(250)
    check(cal.locator('.cal-cell.sel').count() == 1, 'клік не виділив день')
    side = page.inner_text('.ck-day')
    check(f'РОЗКЛАД БАЛАНСУ · {int(iso[8:])} ' in side.upper(), f'шапка розкладу: {side[:60]!r}')
    check('Каса' not in side and 'каса' not in side, f'у розкладі лишилась «каса»: {side[:300]!r}')
    st = page.locator('.ck-bd-st').inner_text()
    sv = int(''.join(ch for ch in st.split('\n')[-1] if ch.isdigit()) or 0) * (-1 if '−' in st.split('\n')[-1] else 1)
    check('Баланс сьогодні' in st and abs(sv - now_bal) <= 1, f'немає «Баланс сьогодні» = плитка «Баланс» {now_bal}: {st!r}')
    tot = page.locator('.ck-bd-tot').inner_text()
    v = int(''.join(ch for ch in tot.split('\n')[-1] if ch.isdigit()) or 0) * (-1 if '−' in tot.split('\n')[-1] else 1)
    check('Баланс на кінець' in tot and abs(v - want) <= 1, f'підсумок розкладу {tot!r}, у рушії {want}')
    m = re.search(r'Надходження \+([\d\s\u00a0]+) ₴, відтоки −([\d\s\u00a0]+) ₴', side)
    check(m, f'немає рядка «Надходження/відтоки»: {side[-200:]!r}')
    n_in, n_out = (int(re.sub(r'\D', '', g)) for g in m.groups())
    check(abs(sv + n_in - n_out - v) <= 2, f'баланс сьогодні {sv} + надходження {n_in} − відтоки {n_out} ≠ баланс на кінець {v}')
    ev = page.locator('.ck-day-events .ck-bd-row')
    names = [ev.nth(i).locator('.ce-n').inner_text() for i in range(ev.count())]
    nvar = sum(1 for e in ref['events'] if e['date'] == iso and e['kind'] == 'variable')
    check((names.count('Щоденні витрати') == (1 if nvar else 0)) and len(names) == sum(1 for e in ref['events'] if e['date'] == iso and e['kind'] != 'variable') + (1 if nvar else 0), f'події дня не з одним рядком «Щоденні витрати»: {names}')
    n = page.locator('.ck-bd-row').count()
    check(n >= 3, f'у розкладі лише {n} рядків')
    page.mouse.move(2, 2)
    shot(page, 'cal-day-1920.jpg', full=False)
    page.click('.ck-day .ck-link')
    page.wait_for_timeout(200)
    check(page.locator('.ck-day .cal-tbl').count() == 1, '«Усі події» не повернули таблицю')


def short_frame(page):
    """v149 (власник: «без червоних рамок»): навіть за нестачі (monobank 500 замість 12 500) у сітці немає червоних рамок,
    мінус червоним лише в колонці балансу таблиці, суми подій не червоні."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, '2026-10-08', [("mono_account_id:'demo-mono',balance:12500,", "mono_account_id:'demo-mono',balance:500,")])
    go_tab(page, 3)
    projection = finance_ref(page)
    check(any(d['shortfallCents'] > 0 for d in projection['days'] if d['date'].startswith('2026-10')), 'фікстура без нестачі, тест нічого не перевіряє')
    red = page.evaluate("""[...document.querySelectorAll('.ck-cal .cal-cell')].filter(c=>{const s=getComputedStyle(c);return /inset/.test(s.boxShadow)&&/2px/.test(s.boxShadow)&&!c.classList.contains('today')&&!c.classList.contains('sel')}).length""")
    check(page.locator('.ck-cal .cal-cell.short').count() == 0 and red == 0, f'червоні рамки в сітці: {red}')
    reds = page.evaluate("""(()=>{const rgb=e=>getComputedStyle(e).color.match(/[\\d.]+/g).map(Number);const isRed=e=>{const c=rgb(e);return c[0]>c[1]+60&&c[0]>c[2]+60};
      return {amt:[...document.querySelectorAll('.cal-tbl .ce-a')].filter(e=>e.textContent.trim()&&isRed(e)).length,
              bal:[...document.querySelectorAll('.cal-tbl .ce-b')].filter(e=>/−/.test(e.textContent)&&isRed(e)).length,
              neg:[...document.querySelectorAll('.cal-tbl .ce-b')].filter(e=>/−/.test(e.textContent)).length}})()""")
    check(reds['amt'] == 0, f'червоні суми подій: {reds}')
    check(reds['neg'] == reds['bal'], f'мінусовий баланс не червоний: {reds}')
    page.mouse.move(2, 2)
    shot(page, 'cal-short-1920.jpg', full=False)


def mobile(page):
    """Одна проєкція: мобільна сітка, відкриття дня і читабельні деталі без горизонтального скролу."""
    go_tab(page,3)
    check(page.locator('.panel.p-credits .cal-cell').count()>=28, 'немає мобільної сітки')
    check(page.evaluate(NO_HSCROLL), 'мобільний календар ширший за екран')
    projection=finance_ref(page)
    pays=[e for e in projection['events'] if e['kind']=='payout' and e['date'][:7]==date.today().isoformat()[:7]]
    check(pays, 'немає майбутніх виплат')
    for e in pays:
        check(page.locator('.cal-cell[data-date="'+e['date']+'"]').count()==1, 'немає дня виплати')
    t=date.today()
    past=page.locator('.cal-cell.past')
    check(past.count()==t.day-1, 'минулі дні не позначені')
    cell=page.locator('.cal-cell.today')
    if cell.get_attribute('aria-pressed')!='true':
        cell.click()
    page.wait_for_timeout(200)
    check(page.locator('.ck-day-events').count()==1, 'сьогодні не відкрило деталі')
    check(page.evaluate(NO_HSCROLL), 'деталі дня ширші за телефон')
    finance_ref(page)
    shot(page,'v139-cal-375.jpg',full=False)


CHECKS = [
    ('Календар: KPI, сітка, минулі дні, сьогодні, таблиця, розклад дня, 1920x1080', 'desktop', desktop),
    ('Календар на телефоні: як раніше плюс тло минулих днів', 'mobile', mobile),
    ('Календар: без червоних рамок, мінус червоним лише в балансі', 'desktop', short_frame),
]
