# v150: модель «власні кошти не мінус» на екранах і Платежі на ПК без прокрутки
from datetime import date, timedelta

from helpers import check, freeze, go_tab

DAY = '2026-10-12'
# демо з боргом Mono за жовтень (план погашення за правилом місяця 20.11) і лімітом: погашення 21.10 лише за правилом «максимум, лишити 15 000»
MONO_DEBT = [("kind:'debit',mono_account_id:'demo-mono',balance:12500,debt:0,debt_month:null",
              "kind:'credit',mono_account_id:'demo-mono',balance:0,debt:20000,credit_limit:30000,debt_month:pbIso(new Date(t.getFullYear(),t.getMonth(),1))")]

DRAWER = r"""(()=>{const c=document.querySelector('.ck-day');if(!c)return null;return [...c.querySelectorAll('.ck-day-events .ck-bd-row')].map(r=>({n:r.querySelector('.ce-n')?.textContent||'',a:r.querySelector('.ce-a')?.textContent||''}))})()"""

MODEL = r"""(()=>{const p=window.__financeProjection,D='2026-10-21';const rep=p.events.filter(e=>e.kind==='repay'&&e.date===D);const per=p.periods.find(q=>q.start===D);
const prev=p.days.find(d=>d.date==='2026-10-20');const accs=window.__financeInput.accounts;
return {rep:rep.map(e=>({id:e.id,acc:String(e.accountId),mono:!!(accs.find(a=>String(a.id)===String(e.accountId))||{}).mono_account_id,name:e.name,c:e.amountCents})),
 per:per?{own:per.ownCents,reserve:per.reserveCents,repay:per.repayCents,offset:per.monoOffsetCents,A:per.availableCents,target:per.targetCents}:null,debtBefore:prev?prev.debtCents:null}})()"""


def _num(t):
    import re
    s = re.sub(r'[\s  ₴]', '', t).replace('−', '-').replace(',', '.')
    m = re.search(r'[-+]?\d+(?:\.\d+)?', s)
    return float(m.group()) if m else None


def pay_repay_mono(page):
    """Власник: «чому тут немає погашення кредитки моно?»: 21.10 гасимо максимум (обовʼязкове, далі Приват, далі Mono), лишаючи 15 000 на життя.
    Розклад дня 21.10 у Платежах має рядок погашення Mono; сума погашень = формула моделі:
    repay − offset = max(належне, min(борг, max(0, власні − резерв − 15 000))), але не більше власні − резерв."""
    page.set_viewport_size({'width': 1600, 'height': 900})
    freeze(page, DAY, MONO_DEBT)
    go_tab(page, 3)
    page.wait_for_selector('.cal-cell[data-date="2026-10-21"]')
    m = page.evaluate(MODEL)
    check(m['per'], 'немає періоду з виплати 21.10 у проєкції')
    per, rep = m['per'], m['rep']
    s = sum(r['c'] for r in rep)
    check(s == per['repay'], f'сума погашень 21.10 {s} != repayCents {per["repay"]}')
    base = per['repay'] - per['offset']
    rule = min(m['debtBefore'], max(0, per['own'] - per['reserve'] - 1500000))
    check(base >= rule and base <= per['own'] - per['reserve'], f'погашення {base} не за формулою: min(борг {m["debtBefore"]}, max(0, {per["own"]} − {per["reserve"]} − 1 500 000)) = {rule}')
    check(per['A'] == per['own'] - per['reserve'] - base, f'A {per["A"]} != власні − резерв − погашення')
    monos = [r for r in rep if r['mono']]
    check(monos, f'немає події погашення Mono 21.10: {rep}')
    page.click('.cal-cell[data-date="2026-10-21"]')
    page.wait_for_timeout(250)
    rows = page.evaluate(DRAWER)
    check(rows, 'розклад дня 21.10 не відкрився')
    rp = [r for r in rows if r['n'].startswith('Погашення ')]
    mono_rows = [r for r in rp if r['n'].startswith('Погашення Mono · ')]
    check(mono_rows, f'у розкладі 21.10 немає рядка погашення Mono: {[r["n"] for r in rows]}')
    # v151 (знахідка 6): рядки погашення розрізняються: банк і вид (обовʼязкове, додатково, прострочене)
    import re
    check(all(re.fullmatch(r'Погашення .+? · (обовʼязкове|додатково|прострочене)', r['n']) for r in rp), f'підпис погашення без банку чи виду: {[r["n"] for r in rp]}')
    check(len({r['n'] for r in rp}) == len(rp), f'однакові підписи погашень 21.10: {[r["n"] for r in rp]}')
    ui = round(sum(-_num(r['a']) for r in rp) * 100)  # у розкладі суми цілими гривнями: допуск 0,50 ₴ на рядок
    check(abs(ui - s) <= 50 * len(rp), f'сума рядків погашення в розкладі {ui} != {s}')
    print(f'      21.10: власні {per["own"] / 100:.2f}, резерв {per["reserve"] / 100:.2f}, погашення {s / 100:.2f} (Mono offset {per["offset"] / 100:.2f}), A {per["A"] / 100:.2f}; рядки: '
          + '; '.join(r['n'] + ' ' + r['a'] for r in rp))


FIT = r"""(()=>{const sec=document.querySelector('.p-credits.desk');if(!sec)return null;const cal=sec.querySelector('.ck-cal');const days=sec.querySelector('.cal-days');
const sc=[];for(let el=days;el;el=el.parentElement){const cs=getComputedStyle(el);if(el.scrollHeight>el.clientHeight+1&&/(auto|scroll)/.test(cs.overflowY))sc.push((el.className&&el.className.baseVal==null?el.className:el.tagName)+' '+el.scrollHeight+'/'+el.clientHeight)}
const d=document.scrollingElement;const cells=[...days.querySelectorAll('.cal-cell')];const last=cells[cells.length-1].getBoundingClientRect();const cr=cal.getBoundingClientRect();
const rows=new Set([...days.children].map(c=>Math.round(c.getBoundingClientRect().top))).size;
const cut=cells.filter(c=>{const r=c.getBoundingClientRect();return r.bottom>cr.bottom+0.5||r.bottom>innerHeight+0.5}).map(c=>c.dataset.date);
const clip=cells.filter(c=>c.scrollHeight>c.clientHeight+1).map(c=>c.dataset.date+' '+c.scrollHeight+'/'+c.clientHeight);const nm=[...days.querySelectorAll('.cal-nm')];const ell=nm.filter(n=>n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1);
return {vw:innerWidth,vh:innerHeight,calSH:cal.scrollHeight,calCH:cal.clientHeight,daysSH:days.scrollHeight,daysCH:days.clientHeight,doc:d.scrollHeight-d.clientHeight,sc,rows,weeks:Math.ceil(((new Date(+days.querySelector('.cal-cell').dataset.date.slice(0,4),+days.querySelector('.cal-cell').dataset.date.slice(5,7)-1,1).getDay()+6)%7+cells.length)/7),
 clip,lastBottom:Math.round(last.bottom),calBottom:Math.round(cr.bottom),cut,cellH:Math.round(cells[0].getBoundingClientRect().height),ell:ell.length,ellTitled:ell.filter(n=>(n.title||n.closest('[title]')?.title||'').length>0).length,
 nmLines:nm.map(n=>Math.round(n.getBoundingClientRect().height/(parseFloat(getComputedStyle(n).lineHeight)||14))).reduce((a,b)=>Math.max(a,b),0)}})()"""



def _fit(page, w, hgt, months):
    page.set_viewport_size({'width': w, 'height': hgt})
    freeze(page, DAY)
    go_tab(page, 3)
    page.wait_for_selector('.p-credits.desk .cal-days .cal-cell')
    seen = []
    for k in range(months):
        if k:
            page.click('.ck-arr[aria-label="Наступний місяць"]')
            page.wait_for_timeout(300)
        page.evaluate("""()=>{const n=document.querySelector('.p-credits.desk .cal-days .cal-nm');if(n)n.textContent='Дуже довга назва постійного платежу, яка не вміщається в клітинку календаря'}""")
        page.wait_for_timeout(60)
        f = page.evaluate(FIT)
        check(f, 'немає календаря Платежів на ПК')
        tag = f'{w}x{hgt} {page.inner_text(".ck-month")}'
        check(not f['sc'], f'{tag}: прокрутка всередині: {f["sc"]}')
        check(f['calSH'] <= f['calCH'] + 1 and f['daysSH'] <= f['daysCH'] + 1, f'{tag}: календар scrollHeight {f["calSH"]}/{f["daysSH"]} > clientHeight {f["calCH"]}/{f["daysCH"]}')
        check(f['doc'] <= 1, f'{tag}: сторінка прокручується на {f["doc"]} px')
        check(f['rows'] == f['weeks'] and not f['cut'], f'{tag}: видно {f["rows"]} рядків із {f["weeks"]} тижнів, обрізано {f["cut"]}')
        check(not f['clip'], f'{tag}: вміст клітинок обрізано (не вміщається): {f["clip"][:4]}')
        check(f['nmLines'] <= 2, f'{tag}: назва події в клітинці на {f["nmLines"]} рядки')
        check(f['ell'] == f['ellTitled'], f'{tag}: обрізані назви без повної назви в підказці {f["ell"] - f["ellTitled"]}')
        seen.append(f'{page.inner_text(".ck-month")} {f["weeks"]} тиж., клітинка {f["cellH"]} px')
    print(f'      {w}x{hgt}: ' + '; '.join(seen))


def fit_1440(page):
    """Власник: «тут немає бути прокрутки»: Платежі на ПК вміщаються без прокрутки, видно всі тижні місяця (5 і 6 тижнів), назви з «…» і підказкою."""
    _fit(page, 1440, 900, 3)


def fit_2000(page):
    _fit(page, 2000, 1200, 3)


SIDE = r"""(()=>{const side=document.querySelector('.p-credits.desk .ck-side');if(!side)return null;const d=side.querySelector('.ck-day');const sc=[];
for(const el of [side,...side.querySelectorAll('*')]){const cs=getComputedStyle(el);if(el.scrollHeight>el.clientHeight+1&&/(auto|scroll)/.test(cs.overflowY))sc.push(String(el.className).slice(0,30)+' '+el.scrollHeight+'/'+el.clientHeight)}
const b=e=>e?Math.round(e.getBoundingClientRect().bottom):null,list=d&&d.querySelector('.ck-bd-list'),subs=list?[...list.querySelectorAll(':scope > .ck-bd-sub')]:[];
const rows=list?[...list.querySelectorAll(':scope > .ck-bd-row')].map(r=>({c:r.className,n:r.querySelector('.ce-n')?.textContent||'',b:r.querySelector('.ce-b')?.textContent||''})):[];
return {vh:innerHeight,doc:document.documentElement.scrollHeight-document.documentElement.clientHeight,sc,daySH:d?d.scrollHeight:null,dayCH:d?d.clientHeight:null,dayB:b(d),tot:b(list&&list.querySelector('.ck-bd-tot')),foot:b(subs[subs.length-1]),rows}})()"""


def _side(page, w, hgt):
    """v151 (знахідка 3, варіант А): розклад вибраного дня в бічній панелі Платежів вміщається без прокрутки: події від сьогодні до дня
    перед вибраним згорнуто в один підсумковий рядок «Події ДД.ММ-ДД.ММ: N подій» із сумою і балансом після, окремо лише події вибраного дня;
    «Баланс на кінець» і рядок надходжень видно. Дні: сьогодні (без згортання), 21.10 (виплата й погашення), 31.10 (найбільше подій до дня)."""
    page.set_viewport_size({'width': w, 'height': hgt})
    freeze(page, DAY, MONO_DEBT)
    go_tab(page, 3)
    page.wait_for_selector('.p-credits.desk .cal-days .cal-cell')
    seen = []
    for d in ['2026-10-12', '2026-10-21', '2026-10-31']:
        page.click(f'.cal-cell[data-date="{d}"]')
        page.wait_for_timeout(250)
        if not page.locator('.ck-day .ck-bd-tot').count():  # повторний клік знімає вибір
            page.click(f'.cal-cell[data-date="{d}"]')
            page.wait_for_timeout(250)
        s = page.evaluate(SIDE)
        tag = f'{w}x{hgt} {d}'
        check(s and s['tot'] is not None, f'{tag}: розклад дня не відкрився')
        check(not s['sc'] and s['daySH'] <= s['dayCH'] + 1 and s['doc'] <= 1, f'{tag}: бічна панель прокручується: {s["sc"]}, {s["daySH"]}/{s["dayCH"]}, сторінка {s["doc"]}')
        check(s['tot'] <= s['dayB'] and s['foot'] <= s['dayB'] and s['foot'] <= s['vh'], f'{tag}: «Баланс на кінець» чи підсумок надходжень поза панеллю: {s}')
        early = [r for r in s['rows'] if 'ck-bd-early' in r['c']]
        if d == DAY:
            check(not early, f'{tag}: для сьогодні нічого не згортається: {early}')
        else:
            check(len(early) == 1, f'{tag}: дні до вибраного не згорнуто в один рядок: {[r["n"] for r in s["rows"]]}')
            e = early[0]
            check(e['n'].startswith('Події 12.10-') and not e['n'].startswith('Погашення'), f'{tag}: підпис підсумку {e["n"]!r}')
            prev = date.fromisoformat(d) - timedelta(days=1)
            want = page.evaluate(f"(()=>{{const p=window.__financeProjection;const x=p.days.find(v=>v.date==='{prev.isoformat()}');return x?(x.netCents+balShift(p))/100:null}})()")
            check(want is not None and abs(_num(e['b']) - want) <= 1, f'{tag}: баланс після підсумку {e["b"]}, а на кінець {prev} {want}')
            check(all(r['n'][:5] == d[8:] + '.' + d[5:7] for r in s['rows'] if 'ck-bd-early' not in r['c'] and 'ck-bd-st' not in r['c'] and 'ck-bd-tot' not in r['c']), f'{tag}: окремі рядки не лише вибраного дня: {[r["n"] for r in s["rows"]]}')
        seen.append(f'{d[8:]}.{d[5:7]}: рядків {len(s["rows"])}, панель {s["daySH"]}/{s["dayCH"]}')
    print(f'      {w}x{hgt}: ' + '; '.join(seen))


def side_1440(page):
    _side(page, 1440, 900)


def side_2000(page):
    _side(page, 2000, 1200)


OWN_TIP = r"""(()=>{const b=document.querySelector('.dv-fc .fc-box');if(!b)return null;const v=s=>{const e=b.querySelector(s+' .fc-tip-n');if(!e)return null;const t=e.textContent;return (/[−-]/.test(t)?-1:1)*+t.replace(/\D/g,'')};
return {k:b.dataset.k,i:+b.dataset.i,own:v('.fc-tip-own'),debt:v('.fc-tip-crd'),rows:[...b.querySelectorAll('.fc-tip-ev')].map(r=>({l:r.querySelector('.fc-tip-l').textContent,c:r.className,d:r.dataset.d!=null?+r.dataset.d:null}))}})()"""

CHART = r"""(()=>{const s=document.querySelector('.dv-fc .fc-svg');const z=s.querySelector('.fc-zero');const y0=z?+z.getAttribute('y1'):null;
const ys=d=>(d||'').replace(/[MLC]/g,' ').trim().split(/[\s,]+/).map(Number).filter((_,i)=>i%2===1);
const fut=ys(s.querySelector('.fc-fut')?.getAttribute('d')),debt=ys(s.querySelector('.fc-debt')?.getAttribute('d'));
return {y0,futMaxY:Math.max(...fut),debtMaxY:debt.length?Math.max(...debt):null,n:+s.dataset.n,past:+s.dataset.past,from:s.dataset.from,to:s.dataset.to}})()"""


def own_120(page):
    """Модель «власні ≥ 0» (координатор: «min(власні) ≥ 0 у моделі, тултіпі й графіку за 120 днів»): демо з боргом Mono і лімітом, тож прогноз бере в кредит.
    Модель: 121 день, власні дня й після кожної події не мінус; графік (Рік): пунктир прогнозу й лінія боргу не нижче нуля;
    тултіп: 120 днів кроками, власні не мінус, власні(d-1) + сума рядків(d) = власні(d); є рядки «у кредит» і погашення Mono 21.10."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, MONO_DEBT)
    go_tab(page, 0)
    m = page.evaluate("""()=>{const t=new Date(Date.parse('2026-10-12T00:00:00Z')+120*864e5).toISOString().slice(0,10);
const r=financeProjection(window.__financeInput,Object.assign({},window.__financeOptions,{through:t}));
return {n:r.days.length,minDay:Math.min(...r.days.map(d=>d.closingCashCents)),minDayLow:Math.min(...r.days.map(d=>d.minCashCents)),minEv:Math.min(...r.events.filter(e=>e.cashAfterCents!=null).map(e=>e.cashAfterCents)),
 borrowed:r.events.filter(e=>e.kind!=='repay'&&e.debtDeltaCents>0).length,maxDebt:Math.max(...r.days.map(d=>d.debtCents))}}""")
    check(m['n'] == 121, f'модель: {m["n"]} днів замість 121')
    check(min(m['minDay'], m['minDayLow'], m['minEv']) >= 0, f'модель: власні мінус {m}')
    check(m['borrowed'] > 0, f'демо не бере в кредит, перевірка не показова: {m}')
    page.locator('.dv-fc .fc-chips button[data-r=y]').click()
    page.wait_for_timeout(300)
    c = page.evaluate(CHART)
    check(c['y0'] is not None and c['futMaxY'] <= c['y0'] + 0.5, f'графік: прогноз власних нижче нуля {c}')
    check(c['debtMaxY'] is None or c['debtMaxY'] <= c['y0'] + 0.5, f'графік: лінія боргу нижче нуля {c}')
    page.locator('.dv-fc .fc-plot').focus()
    prev, chain, credit_rows, mono_rp, low = None, 0, 0, 0, None
    for step in range(120):
        page.keyboard.press('ArrowRight')
        t = page.evaluate(OWN_TIP)
        check(t and t['k'] == 'f', f'крок {step}: немає тултіпа прогнозу')
        check(t['own'] >= 0, f'день {t["i"]}: власні в тултіпі мінус {t["own"]}')
        low = t['own'] if low is None else min(low, t['own'])
        credit_rows += sum('fc-tip-cr' in r['c'] for r in t['rows'])
        mono_rp += sum('fc-tip-rp' in r['c'] and 'mono' in r['l'].lower() for r in t['rows'])
        if prev is not None:
            s = sum(r['d'] for r in t['rows'] if r['d'] is not None)
            check(abs(prev['own'] + s / 100 - t['own']) <= 1.01, f'день {t["i"]}: власні {prev["own"]} + {s / 100} != {t["own"]}: {t["rows"]}')
            chain += 1
        prev = t
    page.keyboard.press('Escape')
    check(chain == 119, f'ланцюжок власних лише {chain} днів')
    check(credit_rows > 0, 'у тултіпі немає рядків «у кредит», хоча модель бере в кредит')
    check(mono_rp > 0, 'у тултіпі немає погашення Mono')
    print(f'      модель: мін. власних {m["minDay"] / 100:.2f}, подій у кредит {m["borrowed"]}, макс. борг {m["maxDebt"] / 100:.2f}; тултіп: 120 днів, мін. {low}, рядків «у кредит» {credit_rows}, погашень Mono {mono_rp}')


CHECKS = [
    ('v150: власні не мінус 120 днів: модель, графік, тултіп', 'desktop', own_120),
    ('v150: Платежі 21.10: погашення Mono в розкладі дня, сума за формулою моделі', 'desktop', pay_repay_mono),
    ('v150: Платежі на ПК без прокрутки 1440x900', 'desktop', fit_1440),
    ('v150: Платежі на ПК без прокрутки 2000x1200', 'desktop', fit_2000),
    ('v151: розклад дня в Платежах без прокрутки 1440x900', 'desktop', side_1440),
    ('v151: розклад дня в Платежах без прокрутки 2000x1200', 'desktop', side_2000),
]
