# v146 (рішення власника 12.10.2026): графік «Гроші в часі» без недоступних періодів (вісь і крива минулого від першої
# операції на власних рахунках, чип-дубль прихований), «сьогодні» на графіку = баланс плитки «Баланс» (v153 доповнення 6), як у боті;
# дата погашення кредитки на чипі рахунку = подія рушія (виплата 21-го наступного місяця); новий борг у формі в поточному місяці.
from datetime import date, timedelta

from helpers import check, dialog, finance_ref, freeze, num, settle

DAY = '2026-10-12'
# v149: ± календарних місяців від сьогодні (назад, уперед); «Уся історія» від першої операції і 3 місяці вперед
RANGES = {'m': (1, 1), 'm2': (2, 2), 'q': (3, 3), 'y': (12, 12), 'all': (None, 3)}


def _mon(t, n):
    # без модуля calendar: у spec/checks є власний calendar.py
    y, m = divmod(t.month - 1 + n, 12)
    y += t.year
    nxt = date(y + 1, 1, 1) if m == 11 else date(y, m + 2, 1)
    return date(y, m + 1, min(t.day, (nxt - date(y, m + 1, 1)).days))


def _days(t, r):
    """Дні від t до меж діапазону r: (назад або None, уперед)."""
    a, b = RANGES[r]
    return (None if a is None else (_mon(t, -a) - t).days, (_mon(t, b) - t).days)
# демо лише з даними поточного місяця: 01.10-12.10, тобто останні два тижні
ONLY_RECENT = [('if(k>cur||k<cur-1)return[];', 'if(k>cur||k<cur)return[];')]
# monobank у мінусі: каса (сума балансів) менша за власні кошти (лише додатні баланси)
NEG_MONO = [("{id:'l3',name:'monobank',bank:'mono',card_last4:'4388',kind:'debit',mono_account_id:'demo-mono',balance:12500,",
             "{id:'l3',name:'monobank',bank:'mono',card_last4:'4388',kind:'debit',mono_account_id:'demo-mono',balance:-3000,")]
OLD_TX = [("dbTx,dbTxN):(function(){const p=new Date(now.getFullYear(),now.getMonth()-1,1);return demoTx(p.getFullYear(),p.getMonth()).concat(demoTx(now.getFullYear(),now.getMonth()))",
           "dbTx,dbTxN):(function(){const p=new Date(now.getFullYear(),now.getMonth()-1,1);return [{id:'old1',date:'2026-05-04',created_at:'2026-05-04T12:00:00.000Z',account_id:'l1',description:'Стара операція',amount:500,type:'expense',source:'manual'}].concat(demoTx(p.getFullYear(),p.getMonth())).concat(demoTx(now.getFullYear(),now.getMonth()))")]
INFO = """(()=>{const s=document.querySelector('.dv-fc .fc-svg');const t=e=>e?e.textContent:null;
 const fi=window.__financeInput,own=new Set(fi.accounts.filter(a=>a.active!==false&&a.kind!=='credit').map(a=>String(a.id)));
 const st=fi.accounts.filter(a=>!a.mono_account_id&&a.balance_updated_at).map(a=>Date.parse(a.balance_updated_at)).filter(Number.isFinite),stamp=st.length?Math.min(...st):null;
 const rows=(fi.transactions||[]).filter(x=>x.account_id!=null?own.has(String(x.account_id)):stamp!=null&&x.source!=='mono'&&Date.parse(x.created_at)>stamp);
 return {from:s.dataset.from,to:s.dataset.to,n:+s.dataset.n,past:+s.dataset.past,chips:[...document.querySelectorAll('.dv-fc .fc-chips button')].map(b=>b.dataset.r),
  pressed:[...document.querySelectorAll('.dv-fc .fc-chips button[aria-pressed=true]')].map(b=>b.dataset.r),today:t(document.querySelector('.dv-fc .fc-today')),
  sum:t(document.querySelector('.dv-fc .fc-sum')),first:rows.map(x=>String(x.date).slice(0,10)).filter(d=>d.length===10).sort()[0]||null}})()"""


def _money(c):
    return ('−' if c < 0 else '') + f'{round(abs(c) / 100):,}'.replace(',', ' ') + ' ₴'


def _norm(t):
    return (t or '').replace(' ', ' ').replace(' ', ' ')


def _today_point(page):
    """Текст живого регіону для точки «сьогодні»: стрілка праворуч, потім ліворуч з фокусом на графіку."""
    page.locator('.dv-fc .fc-plot').focus()
    page.keyboard.press('ArrowRight')
    page.keyboard.press('ArrowLeft')
    page.wait_for_timeout(150)
    out = _norm(page.inner_text('.dv-fc .fc-sr'))
    page.keyboard.press('Escape')
    return out


def chart_trim(page):
    """Дані лише за останні два тижні: вісь і крива минулого від першої операції на власних рахунках, «Уся історія» = «3 міс.»
    і прихована, збережений вибір «Уся історія» показує «3 міс.»; мін., макс. і сьогодні в підсумку лише з видимого відрізка."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, ONLY_RECENT)
    t = date.fromisoformat(DAY)
    info = page.evaluate(INFO)
    first = info['first']
    check(first is not None and first >= (t - timedelta(days=14)).isoformat(), f'фікстура: перша операція {first}, а не в межах двох тижнів')
    print(f'      перша операція на власних рахунках {first}; чипи {info["chips"]}')
    check(info['chips'] == ['m', 'm2', 'q', 'y'], f'чип-дубль «Уся історія» не прихований: {info["chips"]}')
    for r in info['chips']:
        page.locator(f'.dv-fc .fc-chips button[data-r={r}]').click()
        page.wait_for_timeout(250)
        info = page.evaluate(INFO)
        lo, hi = _days(t, r)
        frm = max(first, (t + timedelta(days=lo)).isoformat())
        check(info['pressed'] == [r], f'{r}: натиснутий {info["pressed"]}')
        check(info['from'] == frm and info['to'] == (t + timedelta(days=hi)).isoformat(), f'{r}: вісь {info["from"]}..{info["to"]}, а не {frm}..')
        past = (t - date.fromisoformat(frm)).days + 1
        check(info['past'] == past and info['n'] == past + hi, f'{r}: точок факту {info["past"]} з {info["n"]}, а не {past} з {past + hi}')
        # мінімум і максимум підсумку лише з видимого відрізка: точка мінімуму не раніше початку осі
        pts = page.evaluate("""()=>{const s=document.querySelector('.dv-fc .fc-sum');return [...s.querySelectorAll('span[data-k]')].map(e=>[e.dataset.k,e.textContent])}""")
        for k, txt in pts:
            if k not in ('min', 'max'):
                continue
            dm = txt.strip()[-5:]
            ok = any(info['from'] <= f'{y}-{dm[3:5]}-{dm[0:2]}' <= info['to'] for y in (t.year - 1, t.year, t.year + 1))
            check(ok, f'{r}: дата {dm} у підсумку поза видимим відрізком {info["from"]}..{info["to"]}')
    # збережений вибір прихованого чипа: показується вужчий з тим самим відрізком
    page.evaluate("localStorage.setItem('fc_range','all')")
    freeze(page, DAY, ONLY_RECENT)
    info = page.evaluate(INFO)
    check(info['pressed'] == ['q'] and info['from'] == info['first'], f'збережене «Уся історія» без чипа: натиснутий {info["pressed"]}, вісь від {info["from"]}')
    page.evaluate("localStorage.removeItem('fc_range')")
    # історія довша за три місяці (стара операція 04.05 на власному рахунку): «Уся історія» видно, вісь від першої операції
    freeze(page, DAY, OLD_TX)
    info = page.evaluate(INFO)
    check(info['first'] == '2026-05-04' and info['chips'] == ['m', 'm2', 'q', 'y', 'all'], f'довга історія: перша {info["first"]}, чипи {info["chips"]}')
    page.locator('.dv-fc .fc-chips button[data-r=all]').click()
    page.wait_for_timeout(250)
    info = page.evaluate(INFO)
    past = (t - date(2026, 5, 4)).days + 1
    check(info['from'] == '2026-05-04' and info['past'] == past, f'«Уся історія»: вісь від {info["from"]}, точок факту {info["past"]}, а не 2026-05-04 і {past}')


def chart_today_own(page):
    """Каса не дорівнює власним (monobank у мінусі). v148: мітка, підсумок, точка «сьогодні» і кінець кривої минулого = плитка «Баланс»
    (власні мінус борг кредиток); власні й кредитні лише в підказці точки."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, NEG_MONO)
    ref = finance_ref(page)
    snap = ref['snapshot']
    own, cash = snap['positiveOwnCents'], snap['cashCents']
    print(f'      власні {own / 100:.2f}, каса {cash / 100:.2f}')
    check(own != cash, f'фікстура: каса {cash} дорівнює власним {own}')
    info = page.evaluate(INFO)
    bal = own - snap['creditDebtCents']
    exp = 'Сьогодні: ' + _money(bal)  # v153 доповнення 6: крива знову в балансі (як у v148-v149), не власні
    check(_norm(info['today']) == exp, f'мітка {info["today"]!r}, а не {exp!r}')
    check(page.locator('.dv-fc .fc-today-bal').count() == 0, 'лишився окремий підпис «баланс» біля мітки')
    # v153: після «сьогодні» в рядку ще «у заощадження +X ₴», тож «сьогодні» шукаємо серед частин рядка
    check('сьогодні ' + _money(bal) in [x.strip() for x in _norm(info['sum']).split('·')], f'підсумок {info["sum"]!r} без «сьогодні {_money(bal)}»')
    sr = _today_point(page)
    want = 'власні ' + _money(own) + ', кредитні ' + _money(-snap['creditDebtCents']) + ', баланс ' + _money(bal)
    check('факт' in sr and sr.endswith(want), f'точка сьогодні {sr!r}, а не {want!r}')
    tile = num(page.locator('.kpi-balance .dv-kpi-v').inner_text())
    check(abs(tile - bal / 100) <= 1, f'плитка «Баланс» {tile}, а еталон {bal / 100:.2f}')
    tile_own = num(page.locator('.kpi-balance [data-r=own] .kpi-rv').inner_text())
    check(abs(tile_own - own / 100) <= 1, f'рядок «Власні» плитки {tile_own}, а власні в підказці точки {own / 100:.2f}')
    kpi = num(page.locator('.kpi-funds [data-r=cards] .kpi-rv').inner_text()) + num(page.locator('.kpi-funds [data-r=cash] .kpi-rv').inner_text())
    check(abs(kpi - own / 100) <= 1, f'плитка: готівка + карти {kpi}, а власні {own / 100:.2f}')


def repay_chip(page):
    """Телефон: дата на картці кредитки = подія погашення рушія (виплата 21-го наступного місяця, як у боті)."""
    freeze(page, DAY)
    ref = finance_ref(page)
    accs = [a for a in ref['snapshot']['accounts'] if a.get('debtCents', 0) > 0]
    check(accs, 'фікстура: немає рахунку з боргом')
    exp = []
    for a in accs:
        ev = next(e for e in ref['events'] if e['kind'] == 'repay' and str(e['id']).startswith(f'repay:{a["id"]}:'))
        print(f'      {a.get("name")}: кошики {a["debt_months"]}, погашення {ev["date"]}, договірний строк {ev["contractualDueDate"]}')
        check(ev['date'][8:10] in ('20', '21', '22') or ev['date'] == DAY, f'{a.get("name")}: погашення {ev["date"]} не з виплати 21-го')
        if a.get('kind') == 'credit':
            exp.append('План погашення ' + ev['date'][8:10] + '.' + ev['date'][5:7])
    got = sorted(_norm(x) for x in page.locator('.o-account-deck .o-bank-card .o-bank-due').all_inner_texts())
    check(got == sorted(exp), f'дати на картках кредиток {got}, а не {sorted(exp)}')


def debt_month_form(page):
    """Новий рахунок, вид «Кредитна»: місяць боргу за замовчуванням поточний, не попередній."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    page.locator('.dv-acc-add').click()
    page.wait_for_timeout(300)
    d = dialog(page, 'Рахунок')
    d.locator('[role=group][aria-label="Тип"] button', has_text='Кредитна').click()
    page.wait_for_timeout(150)
    v = d.locator('select').last.input_value()
    check(v == DAY[:8] + '01', f'місяць боргу за замовчуванням {v}, а не {DAY[:8]}01')
    page.keyboard.press('Escape')
    settle(page)


CHECKS = [
    ('v146: графік без недоступних періодів, чип-дубль прихований', 'desktop', chart_trim),
    ('v146: сьогодні на графіку = баланс з плитки, власні в підказці (каса інша)', 'desktop', chart_today_own),
    ('v146: дата погашення на чипі кредитки = подія рушія', 'mobile', repay_chip),
    ('v146: форма рахунку: новий борг у поточному місяці', 'desktop', debt_month_form),
]
