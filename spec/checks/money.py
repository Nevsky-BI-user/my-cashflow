# Гроші по рахунках (DESIGN.md, третя редакція 08.10.2026): паритет cashCore з еталоном scripts/budget_pool.py,
# обовʼязковий рахунок у формі операції, чип «Без рахунку», обмежений готівкою бюджет, підписи прогнозу без накладань.
from datetime import date, timedelta

from helpers import check, dialog, freeze, go_tab, num, open_payout, pool_ref, shot

DAY = '2026-10-08'
# фікстура: операції сьогодні (txDemo стискає день 31 до 8 жовтня, 12:00 UTC, тобто після мітки балансу 09:00):
# без рахунку з Telegram (витрата і дохід), з рахунком Ощадбанку і з кредитки ПриватБанку
ROWS = ("[31,'Ринок',300,'out','telegram',null,'food',0,null],[31,'Кава',120,'out','manual',5814,'cafe',0,'l1'],"
        "[31,'Rozetka',450,'out','manual',null,null,0,'l2'],[31,'Повернули',100,'in','telegram',null,null,0,null],")
PATCH = [('TX_DEMO_ROWS=[', 'TX_DEMO_ROWS=[' + ROWS)]
# поля cashCore, які звіряються з еталоном (допуск 1 ₴)
FIELDS = ['own', 'ownDebit', 'debt', 'whiteDue', 'unassigned', 'cashNow', 'planCur', 'varPoolCur', 'spent', 'freeNow', 'perDay',
          'shortage', 'planNext', 'whiteNext', 'cardRepayNext', 'cashAtPayout', 'varPoolNext']
CORE = """()=>{const c=window.__cashCore;return {own:c.own,ownDebit:c.ownDebit,debt:c.debt,whiteDue:c.whiteDue,unassigned:c.unassigned,
cashNow:c.cashNow,planCur:c.planCur,varPoolCur:c.varPoolCur,spent:c.spent,freeNow:c.freeNow,perDay:c.perDay,shortage:c.shortage,
planNext:c.planNext,whiteNext:c.whiteNext,cardRepayNext:c.cardRepayNext!=null?c.cardRepayNext:(c.repayNext?c.repayNext.total:null),
cashAtPayout:c.cashAtPayout,varPoolNext:c.varPoolNext,unN:c.unList.length}}"""


def _ref(page):
    snap = page.evaluate('window.__cashSnap()')
    d, _ = open_payout(date.fromisoformat(DAY))
    return snap, pool_ref(snap, str(d - timedelta(days=1)), DAY)


def parity(page):
    """(а) ПК: cashCore на демо з операціями з рахунком і без проти budget_pool.py; ті самі числа в рядку-поясненні й KPI."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, PATCH)
    snap, ref = _ref(page)
    check(len(snap['account_tx']) >= 4, f'у знімку немає операцій: {len(snap["account_tx"])}')
    js = page.evaluate(CORE)
    missing = [k for k in FIELDS if k not in ref]
    check(not missing, f'еталон budget_pool.py не друкує полів {missing}')
    print('      поле            застосунок       еталон')
    for k in FIELDS:
        print(f'      {k:<14}{js[k]:>12.2f}{ref[k]:>14.2f}')
    for k in FIELDS:
        check(js[k] is not None and abs(js[k] - ref[k]) <= 1, f'{k}: застосунок {js[k]}, еталон {ref[k]}')
    check(abs(ref['unassigned']) >= 1 and js['unN'] >= 2, f'фікстура без операцій без рахунку: {ref["unassigned"]}, {js["unN"]}')
    # ті самі числа в DOM: рядок-пояснення під «Вільно до виплати» і KPI
    go_tab(page, 0)
    dom = page.evaluate("Object.fromEntries([...document.querySelectorAll('.p-overview [data-k]')].map(e=>[e.dataset.k,e.textContent]))")
    print(f'      DOM: {dom}')
    exp = {'own': ref['ownDebit'], 'unas': abs(ref['unassigned']), 'white': ref['whiteDue'], 'cash': ref['cashNow'],
           'bud': ref['varPoolCur'], 'spent': ref['spent'], 'next': ref['varPoolNext']}
    for k, v in exp.items():
        check(k in dom, f'у DOM немає data-k={k}')
        check(abs(num(dom[k]) - v) <= 1, f'DOM {k}: {dom[k]!r}, еталон {v:.2f}')
    if ref['shortage'] <= 0:
        fv = page.inner_text('.dv-kpi.dv-free .dv-kpi-v')
        check(abs(num(fv) - ref['freeNow']) <= 1, f'KPI «Вільно»: {fv!r}, еталон {ref["freeNow"]:.2f}')
        aside = page.inner_text('.dv-kpi.dv-free')
        pd = aside.split('на день')[1].split('₴')[0] if 'на день' in aside else ''
        check(pd and abs(num(pd) - ref['perDay']) <= 1, f'«на день» {pd!r}, еталон {ref["perDay"]:.2f}')
    page.mouse.move(2, 2)
    shot(page, 'money-parity-1920.jpg', full=False)


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
    c = page.locator('.o-accs .o-unas')
    check(c.count() == 1 and 'без рахунку' in c.inner_text(), 'на телефоні немає чипа «без рахунку»')
    first = page.evaluate("document.querySelector('.o-accs').firstElementChild.className")
    check('o-unas' in first, f'чип «без рахунку» не першим: {first}')


def budget_capped(page):
    """(г) ПК-Бюджет: поточний період показує бюджет, обмежений готівкою, з підписом і плановим дрібно."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    c = page.evaluate('({cur:window.__cashCore.varPoolCur,plan:window.__cashCore.planCur})')
    check(c['cur'] < c['plan'] - 1, f'демо не обмежене готівкою: {c}')
    go_tab(page, 1)
    v = page.inner_text('.bud-kpi.bud-pool .bud-kpi-v') if page.locator('.bud-kpi.bud-pool .bud-kpi-v').count() else page.inner_text('.bud-pool')
    check(abs(num(v.split('₴')[0]) - c['cur']) <= 1, f'«Бюджет періоду» {v!r}, а не обмежений {c["cur"]:.0f}')
    cap = page.locator('.bud-pool .bud-cap')
    check(cap.count() == 1 and 'обмежено готівкою' in cap.inner_text(), 'немає підпису «обмежено готівкою»')
    check(abs(num(page.inner_text('.bud-pool .bud-plan')) - c['plan']) <= 1, 'плановий бюджет у підписі не той')
    page.mouse.move(2, 2)
    shot(page, 'budget-1920.jpg', full=False)


def forecast_labels(page):
    """Графік прогнозу на ПК: щонайменше два підписи мін./макс., без накладань один на одного."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    bb = page.evaluate("[...document.querySelectorAll('.fc-lbl')].map(e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom,e.textContent]})")
    check(len(bb) >= 2, f'підписів мін./макс. {len(bb)}')
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


CHECKS = [
    ('Гроші: паритет cashCore з budget_pool.py (ПК, демо з операціями)', 'desktop', parity),
    ('Гроші: форма вимагає рахунок, без Monobank', 'desktop', form_account),
    ('Гроші: чип «Без рахунку» і вибір рахунку (ПК)', 'desktop', unassigned_chip),
    ('Гроші: чип «без рахунку» першим (телефон)', 'mobile', unassigned_phone),
    ('Гроші: Бюджет обмежений готівкою з підписом', 'desktop', budget_capped),
    ('Гроші: підписи мін./макс. прогнозу без накладань', 'desktop', forecast_labels),
    ('Гроші: звірка ручного рахунку в налаштуваннях', 'desktop', reconcile),
]
