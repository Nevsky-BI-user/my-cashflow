# Гроші по рахунках (DESIGN.md, третя редакція 08.10.2026): паритет cashCore з еталоном scripts/budget_pool.py,
# поріг мінімальних витрат Ощаду (п. 11), обовʼязковий рахунок у формі операції, чип «Без рахунку», обмежений готівкою бюджет, підписи прогнозу без накладань.
import re
from helpers import check, finance_ref, finance_state, dialog, freeze, go_tab, num, shot

DAY = '2026-10-08'
# фікстура: операції сьогодні (txDemo стискає день 31 до 8 жовтня, 12:00 UTC, тобто після мітки балансу 09:00):
# без рахунку з Telegram (витрата і дохід), з рахунком Ощадбанку і з кредитки ПриватБанку
ROWS = ("[31,'Ринок',300,'out','telegram',null,'food',0,null],[31,'Кава',120,'out','manual',5814,'cafe',0,'l1'],"
        "[31,'Rozetka',450,'out','manual',null,null,0,'l2'],[31,'Повернули',100,'in','telegram',null,null,0,null],")
PATCH = [('TX_DEMO_ROWS=[', 'TX_DEMO_ROWS=[' + ROWS)]
def parity(page):
    page.set_viewport_size({'width':1920,'height':900})
    freeze(page,DAY,PATCH)
    r=finance_ref(page,verify_ts=True)
    check(len(finance_state(page)['data']['transactions'])>=4, 'немає фікстурних операцій')
    check(r['snapshot']['unassignedAdjustmentCents']==-20000, 'без рахунку: 100-300=-200')
    # v145: «доступно після виплати» у підказці плитки «Бюджет періоду»; v151: це A рушія (власні на виплату − резерв − погашення)
    page.locator('.kpi-budget .kpi-i').click()
    tip=page.inner_text('.kpi-tip[data-k=budget]')
    m=re.search(r'= (−?[\d\s  ]+(?:,\d+)?) ₴ \(ліміт не дохід', tip)
    check(m and abs(num(m.group(1))-r['nextPlan']['baseAvailableCents']/100)<=1, f'головна сума не збігається з проєкцією: {[x for x in tip.split(chr(10)) if "Після виплати" in x]!r}')
    page.keyboard.press('Escape')
    check(len({e['id'] for e in r['events']})==len(r['events']), 'події дублюються')
    shot(page,'money-parity-1920.jpg',full=False)


def form_account(page):
    """(б) форма операції: без рахунку витрату не зберегти, Monobank у сегменті не пропонується; дохід бере рахунок зарплати."""
    freeze(page, DAY)
    page.keyboard.press('KeyN')
    page.wait_for_timeout(400)
    dlg = dialog(page, 'Нова операція')
    check(dlg.count() == 1, 'форма нової операції не відкрилась')
    seg = dlg.locator('.acc-seg button')
    names = seg.all_inner_texts()
    accs = seg.evaluate_all('els=>els.map(e=>e.dataset.acc)')
    check(len(names) >= 2, f'у сегменті рахунків {names}')
    check('l3' not in accs and not any('mono' in n.lower() for n in names), f'Monobank у сегменті рахунків: {names} {accs}')
    save = dlg.locator('.tx-save')
    check(save.is_disabled(), '«Зберегти» активне без рахунку для витрати')
    check(dlg.locator('.acc-seg [aria-pressed=true]').count() == 0, 'рахунок витрати вибрано за замовчуванням')
    seg.first.click()
    page.wait_for_timeout(150)
    check(not save.is_disabled(), '«Зберегти» не активувалось після вибору рахунку')
    check(dlg.locator('.acc-seg [aria-pressed=true]').count() == 1, 'вибраний рахунок не позначено')
    shot(page, 'money-form-1280.jpg', full=False)


def unassigned_chip(page):
    """(в) операції без рахунку: чип «Без рахунку (N)» у Потоці, картка на Огляді ПК; вибір рахунку прибирає операцію з переліку."""
    freeze(page, DAY, PATCH)
    n0 = page.evaluate('window.__cashCore.unList.length')
    check(n0 >= 2, f'фікстура: без рахунку {n0}')
    check(page.locator('.dv-unas').count() == 1, 'на Огляді ПК немає картки операцій без рахунку')
    go_tab(page, 2)
    chip = page.locator('.flow-chip.flow-unas')
    check(chip.count() == 1, 'у Потоці немає чипа «Без рахунку»')
    t = chip.inner_text()
    check(t.startswith('Без рахунку (') and int(t.split('(')[1].rstrip(')')) >= n0 and 'warn' in (chip.get_attribute('class') or ''),
          f'чип без рахунку: {t!r}')
    chip.click()
    page.wait_for_timeout(250)
    pick = page.locator('.p-flow .pick-acc')
    k0 = pick.count()
    check(k0 >= n0, f'у відфільтрованому Потоці кнопок «Вибрати» {k0}, а без рахунку {n0}')
    # операція з фікстури (після мітки балансу): вибір рахунку прибирає її і з чипа, і з «без рахунку» у cashCore
    page.locator('.p-flow .flow-row:has-text("Ринок") .pick-acc').first.click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок операції')
    check(d.count() == 1, '«Вибрати» не відкрило діалог рахунку')
    d.locator('button[data-acc]').first.click()
    page.wait_for_timeout(400)
    n1 = page.evaluate('window.__cashCore.unList.length')
    check(n1 == n0 - 1, f'після вибору рахунку без рахунку {n1}, а не {n0 - 1}')
    check(page.locator('.p-flow .pick-acc').count() == k0 - 1, 'операція з вибраним рахунком лишилась у фільтрі «Без рахунку»')
    t1 = page.locator('.flow-chip.flow-unas').inner_text()
    check(int(t1.split('(')[1].rstrip(')')) == int(t.split('(')[1].rstrip(')')) - 1, f'чип після вибору: {t1!r}, був {t!r}')


def unassigned_phone(page):
    """(в) телефон: першим у ряді рахунків чип «N без рахунку · вибрати»."""
    freeze(page, DAY, PATCH)
    c = page.locator('.o-account-section > .o-unas')
    check(c.count() == 1 and 'без рахунку' in c.inner_text(), 'на телефоні немає чипа «без рахунку»')
    first = page.evaluate("document.querySelector('.o-account-section').firstElementChild.className")
    check('o-unas' in first, f'чип «без рахунку» не першим: {first}')


def budget_capped(page):
    """План цілі не стискається до поточної каси; дефіцит лишається явним."""
    page.set_viewport_size({'width':1920,'height':900})
    freeze(page,DAY)
    r=finance_ref(page)
    # v143: ціль поточного періоду = факт + прогноз на дні, що лишились; прогноз не нижче частки 15 000 ₴ на ці дні
    c=r['currentPeriod']
    check(c['targetCents']==c['actualVariableCents']+c['remainingTargetCents'], 'ціль не дорівнює факту плюс прогноз')
    check(c['leftDays']==0 or c['remainingTargetCents']>=1500000*c['leftDays']//c['periodDays'], 'прогноз нижче мінімального темпу')
    # v150 (модель «власні ≥ 0»): дефіцит власних іде в борг кредитки до ліміту, далі нестачею (shortfallCents); власні не мінус
    d0 = r['days'][0]['debtCents']
    check(all(d['closingCashCents']>=0 for d in r['days']), 'власні кошти пішли в мінус')
    check(any(d['shortfallCents']>0 or d['debtCents']>d0 for d in r['days']), 'демо не показує розриву: ні боргу кредитки, ні нестачі')
    go_tab(page,0)
    # v150: плитка «Бюджет періоду» = повний бюджет періоду від виплати (periodBudgetStart), не ціль рушія від сьогодні
    pb=page.evaluate('window.__periodBudget')
    from checks.v157 import _snap, _bud_card
    _,plan_ui=_bud_card(_snap(page),'desktop')
    check(plan_ui is not None and abs(plan_ui-pb['budget']/100)<=1, 'картка Огляду не показує повний бюджет періоду')
    check('обмежено готівкою' not in page.inner_text('.dv-bud'), 'мовчазне обмеження готівкою')
    shot(page,'budget-1920.jpg',full=False)


def forecast_labels(page):
    """Графік «Гроші в часі» на ПК (v145): підписи «Сьогодні» і «мін.», без накладань один на одного."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    bb = page.evaluate("[...document.querySelectorAll('.dv-fc .fc-today,.dv-fc .fc-min-l')].map(e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom,e.textContent]})")
    check(len(bb) >= 2, f'підписів сьогодні/мін. {len(bb)}')
    check(any('мін.' in b[4] for b in bb), f'немає підпису глобального мінімуму «мін.»: {[b[4] for b in bb]}')
    for i in range(len(bb)):
        for j in range(i + 1, len(bb)):
            a, b = bb[i], bb[j]
            check(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], f'підписи накладаються: {a[4]!r} і {b[4]!r}')


def reconcile(page):
    """Рахунки в налаштуваннях: рядок звірки «Ощадбанк 4 880 = вказано 5 000 о 09:00 − 1 операція 120», «Звірити» фіксує баланс."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, PATCH)
    page.locator('.side-item', has_text='Налаштування').click()
    page.wait_for_timeout(400)
    page.get_by_text('Рахунки', exact=True).first.click()
    page.wait_for_timeout(400)
    a = page.evaluate("window.__cashCore.accounts.find(x=>x.id==='l1')")
    d = a['drv']
    line = page.locator('.acc-rec[data-acc="l1"]')
    t = line.inner_text().replace(' ', ' ')
    want = f"{round(a['balance']):,} = вказано {round(d['base']):,} о 09:00".replace(',', ' ')
    print(f'      звірка: {t!r}')
    check(want in t and f"{d['n']} операці" in t and f"{round(d['exp'] - d['inc'])}" in t, f'рядок звірки {t!r}, очікували {want!r}')
    check(d['n'] >= 1 and line.locator('.acc-rec-btn').is_enabled(), '«Звірити» неактивне за наявних операцій')
    # демо-операції мають час 12:00 UTC, а годинник стоїть на 12:00 за Києвом (09:00 UTC): звіряємо ввечері, після операції
    page.clock.set_fixed_time(DAY + 'T23:00:00')
    line.locator('.acc-rec-btn').click()
    page.wait_for_timeout(300)
    b = page.evaluate("window.__cashCore.accounts.find(x=>x.id==='l1')")
    check(abs(b['balance'] - a['balance']) <= 0.01 and b['drv']['n'] == 0, f'після «Звірити» баланс {b["balance"]}, операцій {b["drv"]["n"]}')
    check(line.locator('.acc-rec-btn').is_disabled(), '«Звірити» лишилось активним після звірки')


# п. 11: поріг мінімальних витрат Ощаду (15 000 на місяць, інакше комісія 400 1-го числа наступного місяця)
# велика витрата з Ощаду в поточному місяці: поріг досягнуто
MET = [('TX_DEMO_ROWS=[', "TX_DEMO_ROWS=[[31,'Пральна машина',15000,'out','manual',null,'home',0,'l1'],")]


def _sp(t):
    return t.replace('\xa0', ' ').replace('\u202f', ' ')


def min_spend(page):
    """Поріг Ощаду: прогрес на картці ПК, подія комісії 01.11 у Календарі, паритет з еталоном; поріг досягнуто: подія зникає."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    ref = finance_ref(page)
    js = {'ms':ref['minSpend']}
    check(len(js['ms'])==1 and js['ms'][0]['accountId']=='l1' and js['ms'][0]['left']>0, 'демо без порогу')
    fees=[e for e in ref['events'] if e['id']=='fee:l1:2026-10']
    check(len(fees)==1 and fees[0]['date']=='2026-11-01' and fees[0]['amountCents']==40000 and fees[0]['certainty']=='conditional', 'комісія не одна умовна400')
    # картка Ощаду на Огляді ПК
    card = page.locator('.p-overview .bcard .ms-wrap[data-acc="l1"]')
    check(card.count() == 1 and card.is_visible(), 'на картці Ощаду немає прогресу порогу')
    t = _sp(card.inner_text())
    want = f"витрачено {round(js['ms'][0]['spent']):,} з 15 000 у жовтні".replace(',', ' ')
    check(want in t, f'текст прогресу {t!r}, очікували {want!r}')
    check(card.locator('.ms-warn').count() == 0, 'плашка «ще N до 31.10», хоча до кінця місяця більше 10 днів')
    adv = page.locator('.p-overview .ms-adv')
    check(adv.count() == 1 and 'до порогу бракує' in adv.inner_text() and 'Ощадбанк' in adv.inner_text(), f'порада: {adv.all_inner_texts()}')
    page.mouse.move(2, 2)
    shot(page, 'ms-ov-1920.jpg', full=False)
    # Календар, листопад: подія комісії 01.11 у таблиці «Події і баланс», біла
    go_tab(page, 3)
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    page.wait_for_timeout(300)
    row = page.locator('.ck-day .cal-ev[data-date="2026-11-01"]', has_text='Комісія')
    check(row.count() == 1, 'у таблиці Календаря немає події комісії 01.11')
    rt = _sp(row.inner_text())
    check('400 ₴' in rt and 'комісія' in rt.lower(), f'рядок комісії: {rt!r}')
    page.mouse.move(2, 2)
    shot(page, 'ms-cal-1920.jpg', full=False)
    # поріг досягнуто: події немає ні в ядрі, ні в Календарі, на картці «без комісії»
    freeze(page, DAY, MET)
    ref2 = finance_ref(page)
    check(ref2['minSpend'][0]['left']==0 and not any(e['id']=='fee:l1:2026-10' for e in ref2['events']), 'комісія поточного місяця лишилась після факту15000')
    check(ref['nextPlan']['mandatoryCents']-ref2['nextPlan']['mandatoryCents']==40000, 'резерв не зменшився на400')
    check(page.locator('.p-overview .ms-wrap[data-acc="l1"] .ms-ok').count() == 1, 'немає позначки «без комісії»')
    check(page.locator('.p-overview .ms-adv').count() == 0, 'порада лишилась після досягнення порогу')
    go_tab(page, 3)
    page.click('.ck-arr[aria-label="Наступний місяць"]')
    page.wait_for_timeout(300)
    check(page.locator('.ck-day .cal-ev[data-date="2026-11-01"]', has_text='Комісія').count() == 0, 'подія комісії лишилась у Календарі')


def min_spend_late(page):
    """За 10 днів і менше до кінця місяця: бурштинова плашка «ще N до 31.10, інакше комісія 400 ₴»; 01.11 у поточному періоді."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    day = '2026-10-25'
    freeze(page, day)
    ref=finance_ref(page)
    fee=[e for e in ref['events'] if e['id']=='fee:l1:2026-10']
    check(len(fee)==1 and fee[0]['date']=='2026-11-01', 'немає комісії01.11')
    w = page.locator('.p-overview .ms-wrap[data-acc="l1"] .ms-warn')
    check(w.count() == 1, 'немає бурштинової плашки')
    t = _sp(w.inner_text())
    check(t.startswith('ще ') and 'до 31.10, інакше комісія 400 ₴' in t, f'плашка: {t!r}')


def min_spend_phone(page):
    """Телефон: смужка на картці Ощаду, рядок порогу під рахунками і порада."""
    freeze(page, DAY)
    card = page.locator('.o-bank-card', has_text='Ощад')
    check(card.count() == 1 and card.locator('.o-bank-progress-track').count() == 1, 'на картці Ощаду немає смужки порогу')
    ms = page.evaluate("window.__cashCore.minSpend.find(x=>x.accountId==='l1')")
    summary = card.locator('.o-bank-progress').inner_text()
    expected = page.evaluate("r=>'Витрати '+fmtM(r.spent)+' / '+fmtM(r.min)+' ₴'", ms)
    check(summary == expected, f'поріг картки {summary!r}, очікували {expected!r}')
    row = page.locator('.o-ms-list .ms-wrap[data-acc="l1"]')
    check(row.count() == 1 and 'у жовтні' in row.inner_text(), 'під рахунками немає рядка порогу')
    check(page.locator('.o-ms-list .ms-adv').count() == 1, 'на телефоні немає поради')
    check(page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), 'горизонтальна прокрутка на 375')
    shot(page, 'ms-ov-375.jpg', full=False)


def min_spend_settings(page):
    """Налаштування → Рахунки: у формі Ощаду поля «Мін. витрати на місяць» і «Комісія, якщо менше» зі значеннями рахунку."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    page.locator('.side-item', has_text='Налаштування').click()
    page.wait_for_timeout(400)
    page.get_by_text('Рахунки', exact=True).first.click()
    page.wait_for_timeout(400)
    page.locator('.acc-list .bcard', has_text='Ощадбанк').first.click()
    page.wait_for_timeout(300)
    dlg = dialog(page, 'Рахунок')
    check(dlg.count() == 1, 'форма рахунку не відкрилась')
    f = dlg.locator('.acc-ms')
    ft = f.inner_text() if f.count() else ''
    check(f.count() == 1 and 'Мін. витрати на місяць' in ft and 'Комісія, якщо менше' in ft, 'немає полів порогу')
    vals = [_sp(v) for v in f.locator('input:not([type=range])').evaluate_all('els=>els.map(e=>e.value)')]
    print(f'      поля: {vals}')
    check(any(v.replace(' ', '') == '15000' for v in vals) and any(v.replace(' ', '') == '400' for v in vals), f'поля не показують 15 000 і 400: {vals}')
    shot(page, 'ms-settings-acc-1920.jpg', full=False)


CHECKS = [
    ('Гроші: повний паритет проєкції (ПК, демо з операціями)', 'desktop', parity),
    ('Гроші: форма вимагає рахунок, без Monobank', 'desktop', form_account),
    ('Гроші: чип «Без рахунку» і вибір рахунку (ПК)', 'desktop', unassigned_chip),
    ('Гроші: чип «без рахунку» першим (телефон)', 'mobile', unassigned_phone),
    ('Гроші: ціль без стискання готівкою та явний розрив', 'desktop', budget_capped),
    ('Гроші: підписи мін./макс. прогнозу без накладань', 'desktop', forecast_labels),
    ('Гроші: звірка ручного рахунку в налаштуваннях', 'desktop', reconcile),
    ('Гроші: поріг Ощаду, комісія в Календарі і зникнення при 15 000', 'desktop', min_spend),
    ('Гроші: плашка порогу за 10 днів до кінця місяця', 'desktop', min_spend_late),
    ('Гроші: поріг Ощаду на телефоні', 'mobile', min_spend_phone),
    ('Гроші: поля порогу в налаштуваннях рахунку', 'desktop', min_spend_settings),
]
