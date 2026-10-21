"""v153: «Гроші в часі»: у рядку під заголовком «у заощадження +X ₴», X = сума подій «Накопичення» рушія у видимому майбутньому
відрізку кожного діапазону (0 теж показується), у підказці дня виплати рядок «У заощадження»; легенда кільця бюджету на ПК
(власник: «поганий дизайн»): кожен пункт в один рядок однакової висоти, емодзі на лінії назви, суми й відсотки рівно праворуч,
без стрілок перевитрати; телефон без переповнення рядків."""
from helpers import check, freeze, go_tab

DAY = '2026-10-12'
# як у v149: ще вісім категорій витрат у поточному періоді, кожна понад 3% факту, тож у легенді багато окремих пунктів
MANY = [("const TX_DEMO_ROWS=[", "const TX_DEMO_ROWS=[" + ",".join(
    f"[{d},'Тест {c}',{a},'out','manual',null,'{c}']" for d, c, a in (
        (25, 'cafe', 900), (26, 'auto', 1400), (27, 'child', 1100), (28, 'health', 800),
        (29, 'clothes', 1300), (30, 'home', 1000), (31, 'fun', 700), (31, 'gifts', 1200))) + ",")]

# шапка графіка і еталон: події «Накопичення» прогону рушія з тими самими вхідними даними до кінця осі, дати (сьогодні; кінець осі]
SAV = r"""(()=>{const s=document.querySelector('.dv-fc .fc-svg'),e=document.querySelector('.dv-fc .fc-sum [data-k=sav]');if(!s||!e)return null;
const to=s.dataset.to,today=window.__financeOptions.asof;const through=window.__financeProjection.days.slice(-1)[0].date>=to?null:to;
const pr=through?financeProjection(window.__financeInput,Object.assign({},window.__financeOptions,{through:through})):window.__financeProjection;
const ev=pr.events.filter(x=>x.kind==='savings'&&x.date>today&&x.date<=to);
return {to,today,text:e.textContent,v:+e.dataset.v,color:getComputedStyle(e).color,green:getComputedStyle(e).getPropertyValue('--green-t').trim(),
ref:ev.reduce((n,x)=>n+x.amountCents,0),dates:ev.map(x=>[x.date,x.amountCents]),from:s.dataset.from,
sumRight:Math.round(document.querySelector('.dv-fc .fc-sum').getBoundingClientRect().right),cardRight:Math.round(document.querySelector('.dv-fc').getBoundingClientRect().right),
cut:[...document.querySelectorAll('.dv-fc .fc-sum span[data-k]')].some(x=>x.scrollWidth>x.clientWidth+1)}})()"""

TIPROWS = r"""(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;return [...b.querySelectorAll('.fc-tip-ev')].map(r=>[r.querySelector('.fc-tip-l').textContent,r.querySelector('.fc-tip-n').textContent])})()"""


def _hex_rgb(c):
    c = c.lstrip('#')
    return 'rgb(%d, %d, %d)' % tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _uah(c):
    return f'{round(c / 100):,}'.replace(',', ' ') + ' ₴'


def fc_savings(page):
    desk = page.viewport_size['width'] >= 1024
    freeze(page, DAY)
    go_tab(page, 0)
    chips = page.evaluate("[...document.querySelectorAll('.dv-fc .fc-chips button')].map(b=>b.dataset.r)")
    seen = 0
    for r in [c for c in ['m', 'm2', 'q', 'y'] if c in chips]:
        page.locator(f'.dv-fc .fc-chips button[data-r={r}]').click()
        page.wait_for_timeout(250)
        st = page.evaluate(SAV)
        check(st, f'{r}: немає «у заощадження» в рядку графіка')
        txt = st['text'].replace(' ', ' ').replace(' ', ' ')
        print(f'      {r}: {st["from"]}..{st["to"]}: «{txt}», події рушія {st["dates"]}')
        check(st['v'] == st['ref'], f'{r}: у шапці {st["v"]}, а сума подій «Накопичення» {st["ref"]}')
        want = 'у заощадження ' + ('+' if st['ref'] > 0 else '') + _uah(st['ref'])
        check(txt == want, f'{r}: текст «{txt}», а не «{want}»')
        check(st['color'] == _hex_rgb(st['green']), f'{r}: колір {st["color"]}, а не зелений {st["green"]}')
        check(not st['cut'] and st['sumRight'] <= st['cardRight'], f'{r}: рядок підсумку обрізано або виходить за картку')
        seen += st['ref'] > 0
        # підказка дня з накопиченням: рядок «У заощадження» з тією самою сумою (стрілками від сьогодні)
        if st['dates'] and r == 'q':
            date, cents = st['dates'][0]
            from datetime import date as _d
            steps = (_d.fromisoformat(date) - _d.fromisoformat(DAY)).days
            page.locator('.dv-fc .fc-plot').focus()
            page.keyboard.press('ArrowRight')
            page.keyboard.press('ArrowLeft')
            for _ in range(steps):
                page.keyboard.press('ArrowRight')
            rows = page.evaluate(TIPROWS) or []
            rows = [[a, b.replace(' ', ' ').replace(' ', ' ')] for a, b in rows]
            print(f'      підказка {date}: {rows}')
            check(['У заощадження', _uah(cents)] in rows, f'підказка {date} без «У заощадження {_uah(cents)}»: {rows}')
            page.keyboard.press('Escape')
    check(seen > 0, 'жоден діапазон не має накопичень: перевірка не показова')
    print(f'      {"ПК" if desk else "телефон"}: діапазонів з накопиченнями {seen}')


# легенда кільця: рядки, назва, рамки першого (емодзі) і останнього символу назви, сума, відсоток
LEG = r"""scope=>{const rr=e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]};const ch=(e,a,b)=>{const t=e.firstChild;const g=document.createRange();g.setStart(t,a);g.setEnd(t,b);return rr(g)};
return [...document.querySelectorAll(scope+' .bd-row')].map(r=>{const n=r.querySelector('.bd-nm'),t=n.textContent,cp=[...t];const first=cp[0].length,emo=/\p{Extended_Pictographic}/u.test(cp[0]);
return {id:r.dataset.id,t,row:rr(r),nm:rr(n),cut:n.scrollWidth>n.clientWidth+1,lh:parseFloat(getComputedStyle(n).lineHeight)||16,emo,a:ch(n,0,first),z:ch(n,t.length-1,t.length),
sum:rr(r.querySelector('.bd-sum')),pct:rr(r.querySelector('.bd-pct')),txt:r.textContent,over:r.classList.contains('over'),rowOver:r.scrollWidth>r.clientWidth+1}})}"""


def legend(page):
    desk = page.viewport_size['width'] >= 1024
    if desk:
        page.set_viewport_size({'width': 1440, 'height': 900})
    for theme in ('dark', 'light'):
        freeze(page, DAY, MANY)
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        go_tab(page, 0)
        scope = '.dv-bud' if desk else '.p-overview'
        page.locator(scope + ' .bd').scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        rows = page.evaluate(LEG, scope)
        tag = f'{"ПК 1440x900" if desk else "телефон"}/{theme}'
        check(len(rows) >= 8, f'{tag}: пунктів легенди {len(rows)}, перевірка не показова')
        check(not any('↑' in x['txt'] for x in rows), f'{tag}: стрілки перевитрати в легенді')
        check(not any(x['cut'] or x['rowOver'] for x in rows), f'{tag}: назву обрізано або рядок переповнено: {[x["t"] for x in rows if x["cut"] or x["rowOver"]]}')
        # праві краї сум і відсотків у межах колонки легенди однакові (±1 px)
        cols = {}
        for x in rows:
            cols.setdefault(round(x['row'][0]), []).append(x)
        for left, cs in cols.items():
            for k in ('sum', 'pct'):
                rights = [c[k][2] for c in cs]
                check(max(rights) - min(rights) <= 1, f'{tag}: колонка {left}: праві краї {k} різні {rights}')
        emo = [x for x in rows if x['emo']]
        if desk:
            hs = [round(x['row'][3] - x['row'][1], 1) for x in rows]
            check(max(hs) - min(hs) <= 0.5, f'{tag}: рядки легенди різної висоти {hs}')
            for x in rows:
                nh = x['nm'][3] - x['nm'][1]
                check(nh < x['lh'] * 1.5, f'{tag}: «{x["t"]}» у кілька рядків: висота {nh:.1f} при рядку {x["lh"]}')
                check(abs(x['a'][1] - x['z'][1]) < 4, f'{tag}: «{x["t"]}»: емодзі (верх {x["a"][1]:.1f}) не на лінії назви (верх {x["z"][1]:.1f})')
            check(len(emo) >= 6, f'{tag}: пунктів з емодзі {len(emo)}, перевірка не показова')
            check(len(cols) >= 1, f'{tag}: легенда не має видимих колонок')
        print(f'      {tag}: пунктів {len(rows)}, колонок {len(cols)}, з емодзі {len(emo)}, висоти {sorted(set(round(x["row"][3] - x["row"][1], 1) for x in rows))}')
    if desk:
        page.set_viewport_size({'width': 1280, 'height': 860})



# v153 (власник: «чому після події не змінюється баланс? як ти гасиш кредитку, якщо на це немає білих грошей?»): «Події і баланс» на ПК
MONO_DEBT = [("kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
              "kind:'credit',mono_account_id:'demo-mono',balance:0,debt:20000,credit_limit:30000,debt_month:pbIso(new Date(t.getFullYear(),t.getMonth(),1))")]
EVROWS = r"""(()=>[...document.querySelectorAll('.ck-day .cal-tbl .cal-ev')].map(r=>({c:r.className,d:r.dataset.date||'',n:r.querySelector('.ce-n')?.textContent||'',
a:r.querySelector('.ce-a')?.textContent||'',b:r.dataset.bal==null?null:Number(r.dataset.bal),debt:r.dataset.debt==null?null:Number(r.dataset.debt),
dt:r.querySelector('.ce-dbt')?.textContent||''})))()"""
ENG = r"""(()=>{const p=window.__financeProjection;return {events:p.events.map(e=>({date:e.date,kind:e.kind,funding:e.funding,cash:e.cashAfterCents,debt:e.debtAfterCents,
cd:e.cashDeltaCents||0,amount:e.amountCents||0})),warnings:(p.snapshot.warnings||[]).filter(w=>w.kind==='due_short')}})()"""


def _amt(t):
    s = t.replace(' ', '').replace(' ', '').replace('₴', '').replace(',', '.')
    v = float(''.join(ch for ch in s if ch.isdigit() or ch == '.') or 0)
    return -v if '−' in t or '-' in t else v


def events_own(page):
    """ПК 1440x900, демо і демо з боргом Mono, три місяці «Події і баланс»: шапка «Власні після» і «Борг», підпис над таблицею;
    після рядка погашення «Власні після» менше за попередній рядок того ж дня рівно на суму погашення, а борг менший на неї ж (з DOM);
    жоден рядок погашення не лишає власних менше, ніж відтоки власних до наступної виплати (резерв обовʼязкових і щоденних витрат)."""
    page.set_viewport_size({'width': 1440, 'height': 900})
    pairs, guarded = [], []
    for name, patch in (('демо', None), ('борг Mono', MONO_DEBT)):
        freeze(page, DAY, patch)
        go_tab(page, 3)
        page.wait_for_selector('.p-credits.desk .cal-days .cal-cell')
        hd = page.inner_text('.ck-day')
        for s in ('Власні після', 'Борг', 'власні після події; борг кредиток окремо; клік по дню: розклад'):
            check(s in hd, f'{name}: немає «{s}» у «Події і баланс»')
        check('Баланс після' not in hd, f'{name}: лишилась колонка «Баланс після»')
        eng = page.evaluate(ENG)
        evs = eng['events']
        pays = sorted({e['date'] for e in evs if e['kind'] == 'payout'})
        for k in range(3):
            if k:
                page.click('.ck-arr[aria-label="Наступний місяць"]')
                page.wait_for_timeout(300)
            rows = page.evaluate(EVROWS)
            for i, r in enumerate(rows):
                if not r['n'].startswith('Погашення') or r['b'] is None or ' paid' in r['c']:
                    continue
                prev = next((q for q in reversed(rows[:i]) if q['b'] is not None), None)
                a = abs(_amt(r['a']))
                if prev and prev['d'] == r['d']:
                    # з DOM: власні після погашення = попередні власні мінус погашення; борг після = попередній борг мінус погашення
                    check(abs(prev['b'] - a - r['b']) <= 1, f'{name} міс.{k + 1} {r["d"]} {r["n"]}: власні {prev["b"]} − {a} ≠ {r["b"]}')
                    check(prev['debt'] is not None and r['debt'] is not None and abs(prev['debt'] - a - r['debt']) <= 1,
                          f'{name} міс.{k + 1} {r["d"]} {r["n"]}: борг {prev["debt"]} − {a} ≠ {r["debt"]}')
                    pairs.append(f'{r["d"][8:]}.{r["d"][5:7]} {prev["b"]:.0f}−{a:.0f}={r["b"]:.0f}')
                # рушій: та сама подія погашення (дата, власні після, сума); відтоки власних після неї до наступної виплати
                j = next((j for j, e in enumerate(evs) if e['kind'] == 'repay' and e['date'] == r['d'] and abs(e['cash'] / 100 - r['b']) <= 1 and abs(abs(e['amount']) / 100 - a) <= 1), None)
                check(j is not None, f'{name} міс.{k + 1}: погашення {r["d"]} {r["n"]} {a} без події рушія')
                nxt = next((d for d in pays if d > r['d']), '9999-12-31')
                need = sum(max(0, -e['cd']) for e in evs[j + 1:] if e['date'] < nxt)
                check(r['b'] * 100 >= need - 100, f'{name} {r["d"]} {r["n"]}: власні після {r["b"]} менше за відтоки до {nxt} {need / 100:.2f}')
                guarded.append(f'{r["d"][8:]}.{r["d"][5:7]} {r["b"]:.0f}≥{need / 100:.0f}')
            # витрата з кредитки не змінює власних: рядок «з кредитки» має власні як попередній рядок того ж дня
            for i, r in enumerate(rows):
                prev = rows[i - 1] if i else None
                if prev and r['b'] is not None and prev['b'] is not None and prev['d'] == r['d'] and r['debt'] is not None and prev['debt'] is not None and r['debt'] > prev['debt'] + 0.5:
                    check(abs(r['b'] - prev['b']) <= 1, f'{name} {r["d"]} {r["n"]}: витрата з кредитки змінила власні {prev["b"]} -> {r["b"]}')
            # борг червоним у вузькій колонці, коли він є
            red = page.evaluate("""[...document.querySelectorAll('.ck-day .cal-tbl .ce-dbt')].filter(e=>e.textContent.trim()).map(e=>{const c=getComputedStyle(e).color.match(/[\\d.]+/g).map(Number);return c[0]>c[1]+60&&c[0]>c[2]+60&&parseFloat(getComputedStyle(e).fontSize)>=13})""")
            check(all(red), f'{name} міс.{k + 1}: борг не червоним або дрібніше 13px')
    check(pairs, 'на демо немає жодного погашення після події того ж дня: перевірка нічого не перевіряє')
    check(guarded, 'жодного рядка погашення з власними після: перевірка резерву нічого не перевіряє')
    print(f'      погашення (власні до − сума = після): {pairs}; резерв до виплати: {guarded}')


def _bopen(page):
    page.locator('.side-item',has_text='Налаштування').click()
    page.get_by_role('navigation',name='Розділи налаштувань').get_by_role('button',name='Розподіл бюджету').click()
    return page.locator('.set-page')


PB = r"""(()=>{const p=window.__financeProjection,q=p.periods.find(x=>x.start==='2026-10-21');const b=window.__periodBudget;
return {target:q.targetCents,repay:q.repayCents,sav:q.savingsCents,cats:q.categories.reduce((s,c)=>s+c.totalCents,0),pb:b?b.budget:null,man:b?b.manual:null}})()"""


def budget_manual(page):
    """v153 (власник: «має бути можливість встановлювати суму, яка розподіляється»): Налаштування, «Розподіл бюджету» на ПК:
    сума в заголовку є полем, «Авто» за замовчуванням; «Вручну» і 12 000: бюджет рушія на виплату 21.10, план категорій, «Розподілено X з Y»
    і плитка «Бюджет періоду» = 12 000, погашення разом із накопиченням змінились рівно на різницю; 90 000: бурштинове попередження;
    відʼємна сума: помилка без зміни; «Авто» повертає все як було."""
    page.set_viewport_size({'width': 1440, 'height': 900})
    freeze(page, DAY, MONO_DEBT)
    a0 = page.evaluate(PB)
    sh = _bopen(page)
    inp = sh.locator('[data-k=bud-man]')
    check(inp.count() == 1 and sh.locator('[data-k=bud-auto]').get_attribute('aria-pressed') == 'true', 'немає поля суми або «Авто» не за замовчуванням')
    check(abs(_amt(inp.input_value()) * 100 - a0['pb']) <= 100, f'у полі {inp.input_value()!r}, а бюджет періоду {a0["pb"]}')
    sh.locator('[data-k=bud-manual]').click()
    page.wait_for_timeout(200)
    check(sh.locator('[data-k=bud-manual]').get_attribute('aria-pressed') == 'true', '«Вручну» не ввімкнулось')
    inp.fill('12000')
    inp.press('Enter')
    page.wait_for_timeout(400)
    m = page.evaluate(PB)
    txt = sh.inner_text().replace(' ', ' ')
    print(f'      авто {a0}; вручну 12 000 {m}')
    check(m['target'] == 1200000 and m['cats'] == 1200000, f'бюджет рушія на 21.10 {m["target"]}, план категорій {m["cats"]}, очікували 1 200 000')
    check(m['pb'] == 1200000 and m['man'] == 1200000, f'бюджет періоду (плитка, План на день) {m["pb"]}, ручна {m["man"]}')
    check((m['repay'] + m['sav']) - (a0['repay'] + a0['sav']) == a0['target'] - m['target'],
          f'погашення {a0["repay"]}->{m["repay"]}, накопичення {a0["sav"]}->{m["sav"]}: не рівно на різницю бюджетів {a0["target"] - m["target"]}')
    check('з 12 000 ₴' in txt and 'вручну' in txt, f'«Розподілено ... з 12 000 ₴» чи підпис «вручну» не оновились: {txt[:300]!r}')
    fr = page.evaluate("(()=>{const q=window.__financeProjection.periods.find(p=>p.basis!=='current');return {start:q.start,own:q.ownCents,reserve:q.reserveCents,free:q.ownCents-q.reserveCents}})()")
    check(fr['start'] == '2026-10-21' and fr['free'] > 1200000 and fr['free'] < 9000000, f'фікстура: вільне з виплати 21.10 не між 12 000 і 90 000: {fr}')
    check(sh.locator('[data-k=bud-over]').count() == 0, f'попередження при сумі в межах вільного з виплати після обовʼязкових: {fr}')
    inp.fill('90000')
    inp.press('Enter')
    page.wait_for_timeout(400)
    w = sh.locator('[data-k=bud-over]')
    check(w.count() == 1 and 'погашення кредиток буде меншим' in w.inner_text(), 'немає бурштинового попередження для 90 000')
    col = w.evaluate("e=>getComputedStyle(e).color")
    yel = page.evaluate("(()=>{const d=document.createElement('i');d.style.color='var(--yellow-t)';document.body.appendChild(d);const c=getComputedStyle(d).color;d.remove();return c})()")
    check(col == yel, f'попередження не бурштинове: {col} vs {yel}')
    check(page.evaluate(PB)['target'] == 9000000, 'сума понад вільне не дозволена')
    inp.fill('-5')
    inp.press('Enter')
    page.wait_for_timeout(300)
    check(sh.locator('.bud-man-err').count() == 1 and page.evaluate(PB)['target'] == 9000000, 'відʼємна сума без помилки або змінила бюджет')
    sh.locator('[data-k=bud-auto]').click()
    page.wait_for_timeout(400)
    b = page.evaluate(PB)
    check(b == a0, f'«Авто» не повернуло бюджет: {b} vs {a0}')
    check(sh.locator('[data-k=bud-over]').count() == 0 and sh.locator('[data-k=bud-auto]').get_attribute('aria-pressed') == 'true', '«Авто» не ввімкнулось або лишилось попередження')


def budget_manual_phone(page):
    """Телефон 375: Налаштування, «Розподіл бюджету»: поле суми і перемикач без горизонтальної прокрутки і без обрізання."""
    freeze(page, DAY)
    page.locator('.tab-bar .tab-btn').nth(5).click()
    page.wait_for_timeout(400)
    page.locator('.set-mpage button', has_text='Розподіл бюджету').first.click()
    page.wait_for_timeout(500)
    sec = page.locator('.set-mpage .set-msec[data-sec=budget]')
    check(sec.count() == 1 and sec.locator('[data-k=bud-man]').count() == 1, 'на телефоні немає поля суми')
    sec.locator('[data-k=bud-manual]').click()
    page.wait_for_timeout(300)
    g = page.evaluate("""(()=>{const vw=document.documentElement.clientWidth;const els=[...document.querySelectorAll('.bud-man-row, .bud-man-row *')].filter(e=>e.offsetParent);
return {vw,sw:document.documentElement.scrollWidth,out:els.filter(e=>e.getBoundingClientRect().right>vw+0.5).map(e=>e.className),cut:els.filter(e=>e.scrollWidth>e.clientWidth+1&&e.tagName!=='INPUT').map(e=>e.className)}})()""")
    check(g['sw'] <= g['vw'] and not g['out'] and not g['cut'], f'рядок суми на телефоні виходить за екран чи обрізаний: {g}')

CHECKS = [
    ('v153: «Гроші в часі»: «у заощадження +X ₴» = сума подій «Накопичення» рушія діапазону, рядок у підказці (ПК)', 'desktop', fc_savings),
    ('v153: «Гроші в часі»: «у заощадження +X ₴» = сума подій «Накопичення» рушія діапазону, рядок у підказці (телефон)', 'mobile', fc_savings),
    ('v153: легенда кільця: пункт в один рядок, емодзі на лінії назви, суми й відсотки рівно праворуч, без стрілок (ПК 1440x900)', 'desktop', legend),
    ('v153: легенда кільця на телефоні: без переповнення, суми й відсотки рівно праворуч, без стрілок', 'mobile', legend),
    ('v153: «Події і баланс»: власні після події, борг окремо; погашення зменшує власні рівно на суму і не йде в резерв до виплати', 'desktop', events_own),
    ('v153: «Розподіл бюджету»: ручна сума = бюджет рушія, плитки й плану; попередження понад вільне; «Авто» повертає', 'desktop', budget_manual),
    ('v153: «Розподіл бюджету» на телефоні: поле суми без переповнення', 'mobile', budget_manual_phone),
]
