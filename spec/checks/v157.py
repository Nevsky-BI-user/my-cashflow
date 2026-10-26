"""v157 (скарга власника на живому v155: «зі зміною періоду нічого не змінюється»): Огляд показує обраний період, однаково на ПК і телефоні.
Відрізок [S, E): у режимі періоду від виплати до наступної, у режимі місяця від 1-го числа до 1-го наступного; T = сьогодні.
А) поточний (S <= T < E): усі числа як у v156 (spec/fixtures/overview-cur.json знято з v156 до правок).
Б) майбутній (S > T): плитки KPI на кінець дня S з projection.days, бюджет періоду = план періоду (targetCents), «Платежі періоду» з рушія в [S, E),
   смуга періоду на графіку, шапка бюджету й рядки кільця з одного періоду.
В) минулий або без плану: плитки на кінець дня E-1 з історії, бюджет лише фактом («Фактичні витрати періоду»), «Платежі періоду» з фактичних
   обовʼязкових і кредитних операцій періоду."""
import calendar
import json
import os
from datetime import date, datetime, timedelta

from helpers import ROOT, check, freeze, go_tab, num, open_payout, settle
from checks.visual_layout import overview_bounds

DAY = '2026-10-13'
FIX = ROOT / 'spec' / 'fixtures' / 'overview-cur.json'


def _expected(page=None):
    """Поточні числа v156; прогноз враховує погашення боргів перед заощадженнями."""
    data = json.loads(FIX.read_text(encoding='utf-8'))
    for snapshot in data.values():
        funds = snapshot.get('kpis', {}).get('kpi-funds', {})
        funds['rows'] = ['Невикористаний кредит' + row[len('Кредитні'):] if row.startswith('Кредитні') else row
                         for row in funds.get('rows', [])]
    if page is not None:
        # v195: борги гасяться перед єдиною сумою заощаджень. Історичні
        # числа знімка незмінні; прогноз перевіряємо за сирими днями й подіями.
        raw = page.evaluate("""()=>{const svg=[...document.querySelectorAll('.fc-svg')].find(e=>e.getBoundingClientRect().width>0);
        const to=svg.dataset.to,from=window.__financeOptions.asof;
        const p=financeProjection(window.__financeInput,Object.assign({},window.__financeOptions,{through:to}));
        return {days:p.days.filter(d=>d.date>from&&d.date<=to).map(d=>({date:d.date,cents:d.netCents})),
          savings:p.events.filter(e=>e.kind==='savings'&&e.date>from&&e.date<=to).reduce((s,e)=>s+e.amountCents,0)}}""")
        peak = max(raw['days'], key=lambda d:d['cents'])
        money = lambda cents: f'{int(abs(cents)/100+0.5):,}'.replace(',', ' ') + ' ₴'
        for snapshot in data.values():
            parts = snapshot['fc'].split(' · ')
            # Фікстура має історичний мінімум; новий прогноз його не перевищує вниз.
            check(min(d['cents'] for d in raw['days']) > -18982400, 'forecast crossed historical fixture minimum')
            check(peak['cents'] > 750000, 'forecast maximum no longer exceeds fixture current balance')
            parts[1] = 'макс. ' + ('−' if peak['cents'] < 0 else '+') + money(peak['cents']) + ' ' + _dm(peak['date'])
            parts[-1] = 'у заощадження ' + ('+' if raw['savings'] > 0 else '') + money(raw['savings'])
            snapshot['fc'] = ' · '.join(parts)
    return data
VP = {'desktop': (1440, 900), 'mobile': (390, 844)}

# усе видиме на Огляді, що залежить від періоду: плитки KPI з рядками, шапка бюджету, кільце, «Найближче», підсумок графіка
CAPTURE = r"""()=>{
 const T=e=>e?e.textContent.replace(/\s+/g,' ').trim():null;
 const vis=e=>!!e&&e.getBoundingClientRect().width>0;
 const pick=sel=>[...document.querySelectorAll(sel)].find(vis)||null;
 const rowText=e=>{const name=e.querySelector('.kpi-in'),amount=e.querySelector('.kpi-iv');
  if(e.matches('[data-r=inst]')&&name&&amount){const end=e.querySelector('.kpi-ie');let text=T(name)+' · '+T(amount).replace(/^·\s*/,'')+(end?' '+T(end):'');
   const dates=(e.title||'').match(/\d{2}\.\d{2}\.\d{4}/g)||[];
   if(dates.length)text=text.replace(/ · \d{2}\.\d{2}\.\d{2}(?= |$)/,' · до '+dates[0]);
   if(dates.length>1)text=text.replace(/ → \d{2}\.\d{2}\.\d{2}$/,' → '+dates[1]);return text}
  return T(e)};
 const kpis={};document.querySelectorAll('.kpi-t').forEach(k=>{if(!vis(k))return;const c=[...k.classList].find(x=>/^kpi-(funds|budget|balance|inst)$/.test(x));
  kpis[c]={v:T(k.querySelector('.dv-kpi-v')),sub:T(k.querySelector('.kpi-asof')),rows:[...k.querySelectorAll('.kpi-row,.kpi-inst')].map(rowText)}});
 const bv=pick('.dv-bud-v,.o-bud-v');const card=bv?bv.closest('.dv-bud,.o-budget'):null;
 const bd=card?card.querySelector('.bd'):null;
 const near=pick('.dv-near,.o-next');
 /* підпис картки: перший текстовий блок її першого рядка (DvLbl на ПК, CardLabel чи рядок шапки на телефоні) */
 const lbl=e=>{const f=e&&e.firstElementChild;return T(f&&f.firstElementChild?f.firstElementChild:f)};
 return {kpis,bud:bv?T(bv.parentElement):null,budLbl:lbl(card),nearLbl:lbl(near),
  ring:{c:T(bd&&bd.querySelector('.bd-c')),rows:bd?[...bd.querySelectorAll('.bd-row')].map(T):[]},
  nearRows:near?[...near.querySelectorAll('.dv-ev,.o-next-row')].map(T):[],fc:T(pick('.fc-sum'))};
}"""


def _snap(page):
    """Знімок чисел Огляду після докруту сум (двічі поспіль однаковий)."""
    last = None
    for _ in range(12):
        settle(page)
        cur = page.evaluate(CAPTURE)
        if cur == last:
            return cur
        last = cur
        page.wait_for_timeout(250)
    return last


def _open(page, vp):
    w, hh = VP[vp]
    page.set_viewport_size({'width': w, 'height': hh})
    freeze(page, DAY)
    go_tab(page, 0)
    page.wait_for_timeout(400)


def current_matches(page):
    vp = 'desktop' if page.viewport_size['width'] >= 1024 else 'mobile'
    snap = os.environ.get('V157_SNAP') == '1'
    data = _expected() if FIX.exists() else {}
    # обидва режими перемикача: між виплатами і календарний місяць (поточний місяць теж випадок А)
    for mode in ('period', 'month'):
        page.evaluate('m=>localStorage.setItem("per_mode",m)', mode)
        _open(page, vp)
        got = _snap(page)
        key = vp if mode == 'period' else vp + '-month'
        if snap:
            data[key] = got
            print(f'      знімок {key}: плиток {len(got["kpis"])}, рядків кільця {len(got["ring"]["rows"])}, «Найближче» {len(got["nearRows"])}, бюджет «{got["bud"]}»')
            continue
        exp = _expected(page)[key]
        for k in exp:
            check(got.get(k) == exp[k], f'{key}: поточний період змінився в «{k}»: було {exp[k]}, стало {got.get(k)}')
        print(f'      {key}: поточний період збігся з v156: {len(exp["kpis"])} плиток, бюджет «{exp["bud"]}», «Найближче» {len(exp["nearRows"])}')
    page.evaluate('()=>localStorage.setItem("per_mode","period")')
    if snap:
        FIX.write_text(json.dumps(data, ensure_ascii=False, indent=1) + chr(10), encoding='utf-8')


# ---------- Б і В: не поточні періоди ----------
# Еталон рахує сам скрипт із сирих даних превʼю (__cashCore.projection: дні, періоди, події, знімок рахунків; __cashSnap: кредити й операції),
# а не з обʼєкта, який рахує застосунок; межі періоду: зсув від періоду basis==='current' у списку періодів рушія, минулий: за правилом виплат (open_payout)
RAW = r"""()=>{const p=window.__cashCore.projection,s=p.snapshot;return {periods:p.periods.map(q=>({start:q.start,end:q.end,basis:q.basis,target:q.targetCents})),
 days:p.days.map(d=>({date:d.date,cash:d.closingCashCents,debt:d.debtCents,net:d.netCents})),
 snap:{own:s.positiveOwnCents,cash:s.cashCents,debt:s.creditDebtCents,accounts:(s.accounts||[]).map(a=>({kind:a.kind,limit:a.credit_limit,active:a.active}))},
 events:p.events.filter(e=>e.kind!=='variable').map(e=>({date:e.date,name:e.name,kind:e.kind})),fin:window.__cashSnap()}}"""
# рядки «Платежі періоду» / «Найближче»: назва і дата ДД.ММ
NEAR = r"""()=>{const vis=e=>!!e&&e.getBoundingClientRect().width>0;const T=e=>e?e.textContent.replace(/\s+/g,' ').trim():'';
 const near=[...document.querySelectorAll('.dv-near,.o-next')].find(vis);if(!near)return null;
 return [...near.querySelectorAll('.dv-ev,.o-next-row')].map(r=>r.classList.contains('dv-ev')?[T(r.querySelector('.dv-ev-n')),T(r.querySelector('.dv-ev-d'))]:[T(r.children[0]),T(r.children[1]).slice(0,5)])}"""
CHART = r"""()=>{const vis=e=>!!e&&e.getBoundingClientRect().width>0;const svg=[...document.querySelectorAll('.fc-svg')].find(vis);if(!svg)return null;
 const b=svg.querySelector('.fc-band'),per=svg.closest('.dv-fc').querySelector('.fc-sum [data-k=per]');
 return {from:svg.dataset.from,to:svg.dataset.to,band:b?[b.dataset.s,b.dataset.e,+b.getAttribute('width')]:null,per:per?[per.dataset.d,per.textContent]:null}}"""
# підписи місяців перемикача періоду (MO_G в index.html)
MO_G = ['січ.', 'лют.', 'бер.', 'квіт.', 'трав.', 'черв.', 'лип.', 'серп.', 'вер.', 'жовт.', 'лист.', 'груд.']
PILL_T = "()=>{const e=[...document.querySelectorAll('.side-pname,.pp-t')].find(x=>x.getBoundingClientRect().width>0);return e?e.firstChild.textContent:null}"
PER_T = "()=>{const e=[...document.querySelectorAll('.ov-per-t')].find(x=>x.getBoundingClientRect().width>0);return e?e.textContent:null}"
# минулий період: синтетичні фактичні платежі (обовʼязковий і розстрочка) у демо-правках; третій поза періодом, щоб перевірити межі
_TX = ("{{id:'{id}',date:'{d}',created_at:'{d}T12:00:00.000Z',account_id:'l1',description:'{n}',amount:{a},type:'expense',source:'manual',mcc:null,"
       "category_id:null,categories:null,fixed_id:{f},credit_id:{c},auto_categorized:false,receipt_url:null}}")
PAST_TX = [("useState({add:[],del:{},acc:{},fx:{},cr:{},due:{},transfers:{}})",
            "useState({add:[" + ','.join([
                _TX.format(id='s157a', d='2026-09-25', n='Оренда', a=12000, f="'f1'", c='null'),
                _TX.format(id='s157b', d='2026-10-02', n='Ланцюжок', a=3731.88, f='null', c="'l1'"),
                _TX.format(id='s157c', d='2026-09-15', n='Оренда', a=12000, f="'f1'", c='null')]) + "],del:{},acc:{},fx:{},cr:{},due:{},transfers:{}})")]


def _pill(page, S, E, tag):
    """Перемикач періоду підписує той самий відрізок, що рушій: від виплати S до виплати E, якою період закінчується
    (до v157 кінець авансу брався з дня зарплати цього місяця: «21 вер.-7 жовт.» при виплаті 06.10)."""
    s, e = date.fromisoformat(S), date.fromisoformat(E)
    exp = f'{s.day}-{e.day} {MO_G[e.month - 1]}' if s.month == e.month else f'{s.day} {MO_G[s.month - 1]}-{e.day} {MO_G[e.month - 1]}'
    got = page.evaluate(PILL_T)
    check(got == exp, f'{tag}: перемикач періоду «{got}», рушій {S}..{E}, очікували «{exp}»')


def _iso(d):
    return d.isoformat()


def _dm(iso):
    return iso[8:10] + '.' + iso[5:7]


def _vp(page):
    return 'desktop' if page.viewport_size['width'] >= 1024 else 'mobile'


def _nav(page, n):
    """n кліків стрілкою періоду (n > 0 вперед, n < 0 назад): шапка сторінки на ПК, пігулка на телефоні."""
    lab = 'Наступний період' if n > 0 else 'Попередній період'
    sel = (f'.dtitle .side-arr[aria-label="{lab}"]' if _vp(page) == 'desktop' else f'.header .pp-arr[aria-label="{lab}"]')
    for _ in range(abs(n)):
        page.locator(sel).click()
        page.wait_for_timeout(150)


def _round(x):
    """Math.round(x*100) для сум у гривнях."""
    return int(x * 100 + 0.5) if x >= 0 else -int(-x * 100 + 0.5)


def _inst(fin, today, upto=None):
    """Залишок розстрочок (коп.): платежі з датою після today, крім місяців, оплачених фактом з credit_id (для минулого лише операції до upto включно)."""
    txs = [t for t in fin.get('transactions') or [] if upto is None or str(t.get('date') or t.get('created_at'))[:10] <= upto]
    paid = {str(t['credit_id']) + '|' + str(t.get('date') or t.get('created_at'))[:7] for t in txs if t.get('type') == 'expense' and t.get('credit_id') is not None}
    tot = 0
    for c in fin.get('credits') or []:
        first = int(c['start_year']) * 12 + int(c['start_month'])
        for k in range(first, first + int(c['total_payments'])):
            y, m = divmod(k, 12)
            d = f'{y}-{m + 1:02d}-{min(int(c["payment_day"]), calendar.monthrange(y, m + 1)[1]):02d}'
            if d > today and f'{c["id"]}|{d[:7]}' not in paid:
                tot += _round(float(c['monthly_amount']))
    return tot


def _limit(raw):
    return sum(_round(float(a['limit'])) for a in raw['snap']['accounts'] if a['active'] is not False and a['kind'] == 'credit' and a['limit'] and float(a['limit']) > 0)


def _hist(raw, d_iso):
    """Власні й баланс на кінець дня d_iso з історії: від знімка сьогодні назад, мінус операції після d_iso до сьогодні
    (рахунки знімка; операції без рахунку лише створені після найранішої мітки балансу ручних рахунків і не з mono)."""
    fin = raw['fin']

    def ts(v):
        return datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp()
    accs = fin['accounts']
    stamps = [ts(a['balance_updated_at']) for a in accs if not a.get('mono_account_id') and a.get('balance_updated_at')]
    stamp = min(stamps) if stamps else None
    all_ids = {str(a['id']) for a in accs} | {''}
    own_ids = {str(a['id']) for a in accs if a.get('kind') != 'credit'} | {''}
    seen, txs = set(), []
    for t in fin['transactions']:
        if t.get('id') is not None:
            if str(t['id']) in seen:
                continue
            seen.add(str(t['id']))
        if t.get('account_id') is None and (stamp is None or t.get('source') == 'mono' or not ts(t['created_at']) > stamp):
            continue
        txs.append(t)

    def moved(ids):
        return sum((1 if t['type'] == 'income' else -1) * _round(float(t['amount'] or 0)) for t in txs
                   if d_iso < str(t['date'])[:10] <= DAY and ('' if t.get('account_id') is None else str(t['account_id'])) in ids)
    s = raw['snap']
    return s['own'] - moved(own_ids), s['own'] - s['debt'] - moved(all_ids)


def _tiles_equal(got, exp, tag):
    for k, (v, rows) in exp.items():
        t = got['kpis'].get('kpi-' + k)
        check(t, f'{tag}: немає плитки {k}')
        check(abs(num(t['v']) - v / 100) < 0.006, f'{tag}: плитка {k}: «{t["v"]}», очікували {v / 100:.2f}')
        for lbl, rv in rows:
            r = next((x for x in t['rows'] if x.startswith(lbl)), None)
            check(r is not None, f'{tag}: у плитці {k} немає рядка «{lbl}»: {t["rows"]}')
            check(abs(num(r[len(lbl):]) - rv / 100) < 0.006, f'{tag}: {k}/{lbl}: «{r}», очікували {rv / 100:.2f}')


GEO = r"""()=>{const svg=document.querySelector('.dv-fc svg'),pan=document.querySelector('.p-overview'),t=document.querySelector('.dtitle'),o=document.querySelector('.dtitle .ov-per');
 return {chart:svg.getBoundingClientRect().height,inner:[...document.querySelectorAll('.dv-cols .dv-fc,.dv-cols .dv-bud,.dv-cols .dv-near,.dv-cols>.kpi-inst,.dv-cols .dv-recent,.dv-cols .dv-unas')].filter(e=>e.offsetParent).some(e=>e.scrollHeight>e.clientHeight+2),
  scroll:pan.classList.contains('ov-scroll'),recent:document.querySelector('.dv-recent').getBoundingClientRect().bottom,wide:document.documentElement.scrollWidth,
  clipped:[...document.querySelectorAll('.kpi-rv,.dv-kpi-v,.kpi-asof,.ov-per-t')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent),
  title:t.getBoundingClientRect().height,per:o?o.getBoundingClientRect().bottom:null}}"""
GEO_VP = ((1280, 860), (1280, 800), (1440, 900))


def _cur_scroll(page):
    """Стан ov-scroll поточного періоду на трьох розмірах ПК (еталон для не поточних)."""
    out = {}
    for w, hh in GEO_VP:
        page.set_viewport_size({'width': w, 'height': hh})
        page.wait_for_timeout(350)
        settle(page)
        out[(w, hh)] = page.evaluate("document.querySelector('.p-overview').classList.contains('ov-scroll')")
    page.set_viewport_size({'width': VP['desktop'][0], 'height': VP['desktop'][1]})
    page.wait_for_timeout(300)
    return out


def _geometry(page, tag, base):
    """Не поточний період зберігає адаптивний графік, цілі картки, доступні списки та рядок періоду в шапці."""
    for (w, hh), cur_scroll in base.items():
        page.set_viewport_size({'width': w, 'height': hh})
        page.wait_for_timeout(350)
        settle(page)
        g = page.evaluate(GEO)
        check(g['chart'] >= (159.5 if hh < 900 else 179.5 if hh < 1000 else 259.5), f'{tag} {w}x{hh}: графік нижчий за адаптивний мінімум: {g}')
        overview_bounds(page, f'{tag}/{w}x{hh}')
        # без НОВОГО ov-scroll: не поточний період не прокручується там, де поточний вміщається; легший період може вміститись
        # і тоді, коли поточний прокручується (вищий вміст поточного періоду не робить помилкою вільніший інший)
        check(cur_scroll or not g['scroll'], f'{tag} {w}x{hh}: зʼявилась прокрутка Огляду, якої немає в поточному періоді ({cur_scroll} -> {g["scroll"]})')
        check(hh < 840 or g['recent'] <= hh, f'{tag} {w}x{hh}: «Останні операції» нижче екрана: {g}')
        check(g['wide'] <= w, f'{tag} {w}x{hh}: горизонтальне переповнення: {g}')
        check(not g['clipped'], f'{tag} {w}x{hh}: обрізані тексти: {g["clipped"]}')
        check(g['per'] is not None and g['per'] < 80 and g['title'] <= 44, f'{tag} {w}x{hh}: рядок періоду не в шапці сторінки: {g}')
    page.set_viewport_size({'width': VP['desktop'][0], 'height': VP['desktop'][1]})
    page.wait_for_timeout(300)


def _bud_card(got, vp):
    """Шапка картки бюджету: (факт, план або None)."""
    b = got['bud']
    if vp == 'mobile':
        b = b.replace(got['budLbl'] or '', '', 1)
    if '/' not in b:
        return num(b), None
    f, rest = b.split('/', 1)
    return num(f), num(rest)


def _ring_total(got):
    c = got['ring']['c']
    return num(c) if c else 0.0


def future_periods(page):
    vp = _vp(page)
    _open(page, vp)
    raw = page.evaluate(RAW)
    base = _cur_scroll(page) if vp == 'desktop' else None
    ps = raw['periods']
    ci = next(i for i, q in enumerate(ps) if q['basis'] == 'current')
    shift = raw['snap']['own'] - raw['snap']['cash']
    lim = 5 if vp == 'desktop' else 3   # 1440x900: висота нижче 1000px, тож 5 рядків, як «Найближче»; телефон 3
    done = 0
    for off in (1, 7):
        _nav(page, off - done)
        done = off
        q = ps[ci + off]
        S, E = q['start'], q['end']
        last = _iso(date.fromisoformat(E) - timedelta(days=1))
        tag = f'{vp} +{off} ({S}..{E})'
        got = _snap(page)
        per = page.evaluate(PER_T)
        check(per == f'Прогноз на період {_dm(S)}-{_dm(E)}', f'{tag}: рядок періоду «{per}»')
        _pill(page, S, E, tag)
        day = next(d for d in raw['days'] if d['date'] == S)
        own, bal = day['cash'] + shift, day['net'] + shift
        debt = own - bal
        days = (date.fromisoformat(E) - date.fromisoformat(S)).days
        fact = _ring_total(got)
        plan = q['target']
        exp = {'funds': (max(0, own) + max(0, _limit(raw) - debt), [('Власні', own), ('Борг кредиток', -debt)]),
               'budget': (plan, [('Доступно', plan - _round(fact)), ('План на день', int(plan / days + 0.5))]),
               'balance': (bal, [('Власні', own), ('Мінусові', -debt)]),
               'inst': (_inst(raw['fin'], S), [])}
        _tiles_equal(got, exp, tag)
        for k, t in got['kpis'].items():
            check(t['sub'] == f'прогноз на {_dm(S)}', f'{tag}: {k}: позначка «{t["sub"]}»')
        # шапка картки бюджету: план = план періоду рушія, факт = сума кільця (рядки категорій і «Без категорії»)
        bf, bp = _bud_card(got, vp)
        check(bp is not None and abs(bp - plan / 100) < 0.5, f'{tag}: шапка бюджету «{got["bud"]}», план періоду {plan / 100}')
        check(abs(bf - fact) < 0.5, f'{tag}: факт шапки «{got["bud"]}» не дорівнює факту кільця {fact}')
        # «Платежі періоду»: події рушія в [S, E), той самий ліміт рядків, порядок за датою
        ev = sorted([e for e in raw['events'] if S <= e['date'] < E], key=lambda e: e['date'])
        rows = page.evaluate(NEAR)
        check(got['nearLbl'] == 'Платежі періоду', f'{tag}: підпис картки «{got["nearLbl"]}»')
        check(len(ev) >= 1 and len(rows) == min(lim, len(ev)), f'{tag}: рядків {len(rows)}, подій рушія в періоді {len(ev)}, ліміт {lim}')
        for (n, d), e in zip(rows, ev):
            check(d == _dm(e['date']), f'{tag}: рядок «{n}» {d}, очікували {_dm(e["date"])} ({e["name"]})')
            check(e['kind'] == 'repay' or n == e['name'], f'{tag}: рядок «{n}», очікували «{e["name"]}»')
        # графік: смуга [S, E) і значення на S у заголовку, те саме, що плитка «Баланс»
        ch = page.evaluate(CHART)
        check(ch['band'] and ch['band'][0] == S and ch['band'][1] == last and ch['band'][2] > 0, f'{tag}: смуга графіка {ch}')
        check(ch['from'] <= S and ch['to'] >= last, f'{tag}: діапазон графіка {ch["from"]}..{ch["to"]} не покриває період')
        check(ch['per'] and ch['per'][0] == S and ch['per'][1].startswith(f'прогноз на {_dm(S)} ') and abs(num(ch['per'][1].split(' ', 3)[3]) - bal / 100) <= 1,
              f'{tag}: заголовок графіка {ch["per"]}, баланс плитки {bal / 100}')
        print(f'      {tag}: плитки {[got["kpis"]["kpi-" + k]["v"] for k in ("funds", "budget", "balance", "inst")]}, бюджет «{got["bud"]}», '
              f'платежі {len(rows)} з {len(ev)}, смуга {ch["band"][:2]}, графік «{ch["per"][1]}»')
        if vp == 'desktop':
            _geometry(page, tag, base)
    # повернення до поточного: «зараз» знову є, числа як у v156
    page.locator('.ov-back:visible').click()
    page.wait_for_timeout(300)
    check(page.locator('.pp-now:visible').count() == 1, 'після «До поточного» немає позначки «зараз»')
    check(page.locator('.ov-per:visible').count() == 0, 'після «До поточного» лишився рядок не поточного періоду')
    exp = _expected(page)[vp]
    got = _snap(page)
    for k in exp:
        check(got.get(k) == exp[k], f'{vp}: після «До поточного» «{k}» не як у v156: {got.get(k)}')
    print(f'      {vp}: «До поточного» повернуло поточний період, числа як у v156')


def past_period(page):
    vp = _vp(page)
    w, hh = VP[vp]
    page.set_viewport_size({'width': w, 'height': hh})
    freeze(page, DAY, PAST_TX)
    go_tab(page, 0)
    page.wait_for_timeout(400)
    raw = page.evaluate(RAW)
    base = _cur_scroll(page) if vp == 'desktop' else None
    cur = next(q for q in raw['periods'] if q['basis'] == 'current')
    E = cur['start']
    S = _iso(open_payout(date.fromisoformat(E) - timedelta(days=1))[0])
    last = _iso(date.fromisoformat(E) - timedelta(days=1))
    tag = f'{vp} минулий ({S}..{E})'
    _nav(page, -1)
    got = _snap(page)
    per = page.evaluate(PER_T)
    check(per == f'Минулий період {_dm(S)}-{_dm(E)}', f'{tag}: рядок періоду «{per}»')
    _pill(page, S, E, tag)
    own, bal = _hist(raw, last)
    debt = own - bal
    exp = {'funds': (max(0, own) + max(0, _limit(raw) - debt), [('Власні', own), ('Борг кредиток', -debt)]),
           'balance': (bal, [('Власні', own), ('Мінусові', -debt)]),
           'inst': (_inst(raw['fin'], last, last), [])}
    _tiles_equal(got, exp, tag)
    for k, t in got['kpis'].items():
        check(t['sub'] == f'на {_dm(last)}', f'{tag}: {k}: позначка «{t["sub"]}»')
    # бюджет лише фактом, тими самими словами, що вкладка «Бюджет» без плану
    fact = _ring_total(got)
    check(fact > 0, f'{tag}: у минулому періоді немає факту витрат, перевірка порожня')
    bf, bp = _bud_card(got, vp)
    check(bp is None and abs(bf - fact) < 0.5, f'{tag}: картка бюджету «{got["bud"]}», факт кільця {fact}')
    check(got['budLbl'] == 'Фактичні витрати періоду', f'{tag}: підпис картки бюджету «{got["budLbl"]}»')
    kb = got['kpis']['kpi-budget']
    check(abs(num(kb['v']) - fact) < 0.5 and 'без плану' in ' '.join(kb['rows']), f'{tag}: плитка бюджету {kb}')
    # «Платежі періоду»: фактичні обовʼязкові й кредитні операції в [S, E): дві синтетичні в періоді, третя (15.09) поза ним
    rows = page.evaluate(NEAR)
    check(got['nearLbl'] == 'Платежі періоду', f'{tag}: підпис картки «{got["nearLbl"]}»')
    check([d for _, d in rows] == ['25.09', '02.10'] and all(n for n, _ in rows), f'{tag}: рядки платежів {rows}')
    ch = page.evaluate(CHART)
    check(ch['band'] and ch['band'][0] == S and ch['band'][1] == last, f'{tag}: смуга графіка {ch}')
    check(ch['from'] <= S, f'{tag}: графік від {ch["from"]}, період від {S}')
    check(ch['per'] and ch['per'][0] == last and ch['per'][1].startswith(f'на {_dm(last)} ') and abs(num(ch['per'][1].split(' ', 2)[2]) - bal / 100) <= 1,
          f'{tag}: заголовок графіка {ch["per"]}, баланс плитки {bal / 100}')
    print(f'      {tag}: плитки {[got["kpis"]["kpi-" + k]["v"] for k in ("funds", "budget", "balance", "inst")]}, бюджет «{got["bud"]}», платежі {rows}, графік «{ch["per"][1]}»')
    if vp == 'desktop':
        _geometry(page, tag, base)
    # Бюджет відкриває власний поточний місяць; його історію гортати окремо.
    go_tab(page, 1)
    check(page.locator('.p-budget').get_attribute('data-month')==DAY[:7]+'-01','минулий період Огляду змінив місяць Бюджету')
    _nav(page,-1)
    budget=page.locator('.p-budget')
    check(budget.get_attribute('data-month')=='2026-09-01','не відкрився минулий календарний місяць')
    tx=list({str(t['id']):t for t in raw['fin']['transactions']}.values())
    monthly_fact=sum(_round(t['amount']) for t in tx if t['type']=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None and '2026-09-01'<=t['date'][:10]<'2026-10-01')/100
    check(abs(num(budget.locator('.bud-spent .bud-kpi-v').inner_text())-monthly_fact)<.01,'історичний місячний факт не відповідає сирим операціям')
    from checks.budget_period_parity import assert_unsaved_salary
    assert_unsaved_salary(page,'2026-09-01')
    go_tab(page,0)
    check(page.evaluate(PER_T)==per,'навігація Бюджету змінила історичний період Огляду')


def month_mode(page):
    """Режим «місяць»: наступний місяць (Б) і попередній (В) тими самими правилами, що й період між виплатами; потім «До поточного»."""
    vp = _vp(page)
    lim = 5 if vp == 'desktop' else 3
    page.evaluate('()=>localStorage.setItem("per_mode","month")')
    _open(page, vp)
    raw = page.evaluate(RAW)
    shift = raw['snap']['own'] - raw['snap']['cash']
    t = date.fromisoformat(DAY)
    # Б: наступний календарний місяць [1-ше, 1-ше наступного)
    s = date(t.year + (t.month == 12), t.month % 12 + 1, 1)
    e = date(s.year + (s.month == 12), s.month % 12 + 1, 1)
    S, E, last = _iso(s), _iso(e), _iso(e - timedelta(days=1))
    tag = f'{vp} місяць +1 ({S}..{E})'
    _nav(page, 1)
    got = _snap(page)
    per = page.evaluate(PER_T)
    check(per == f'Прогноз на місяць {_dm(S)}-{_dm(last)}', f'{tag}: рядок періоду «{per}»')
    day = next(d for d in raw['days'] if d['date'] == S)
    own, bal = day['cash'] + shift, day['net'] + shift
    debt = own - bal
    fact = _ring_total(got)
    bf, bp = _bud_card(got, vp)
    # план місяця рахує застосунок (пул бюджету місяця); тут перевірка, що плитка, шапка й «Доступно» з одного плану
    check(bp is not None and bp > 0, f'{tag}: шапка бюджету без плану «{got["bud"]}»')
    plan = _round(bp or 0)
    days = (e - s).days
    exp = {'funds': (max(0, own) + max(0, _limit(raw) - debt), [('Власні', own), ('Борг кредиток', -debt)]),
           'balance': (bal, [('Власні', own), ('Мінусові', -debt)]),
           'inst': (_inst(raw['fin'], S), [])}
    _tiles_equal(got, exp, tag)
    kb = got['kpis']['kpi-budget']
    pv = _round(num(kb['v']))
    check(abs(pv - plan) <= 100, f'{tag}: плитка бюджету «{kb["v"]}», шапка «{got["bud"]}»')
    _tiles_equal(got, {'budget': (pv, [('Доступно', pv - _round(fact)), ('План на день', int(pv / days + 0.5))])}, tag)
    check(abs(bf - fact) < 0.5, f'{tag}: факт шапки «{got["bud"]}» не дорівнює факту кільця {fact}')
    for k, x in got['kpis'].items():
        check(x['sub'] == f'прогноз на {_dm(S)}', f'{tag}: {k}: позначка «{x["sub"]}»')
    ev = sorted([x for x in raw['events'] if S <= x['date'] < E], key=lambda x: x['date'])
    rows = page.evaluate(NEAR)
    check(got['nearLbl'] == 'Платежі періоду', f'{tag}: підпис картки «{got["nearLbl"]}»')
    check(len(ev) >= 1 and len(rows) == min(lim, len(ev)), f'{tag}: рядків {len(rows)}, подій рушія в місяці {len(ev)}, ліміт {lim}')
    for (n, d), x in zip(rows, ev):
        check(d == _dm(x['date']), f'{tag}: рядок «{n}» {d}, очікували {_dm(x["date"])} ({x["name"]})')
    ch = page.evaluate(CHART)
    check(ch['band'] and ch['band'][0] == S and ch['band'][1] == last, f'{tag}: смуга графіка {ch}')
    check(ch['per'] and ch['per'][0] == S and abs(num(ch['per'][1].split(' ', 3)[3]) - bal / 100) <= 1, f'{tag}: заголовок графіка {ch["per"]}')
    print(f'      {tag}: плитки {[got["kpis"]["kpi-" + k]["v"] for k in ("funds", "budget", "balance", "inst")]}, бюджет «{got["bud"]}», '
          f'платежі {len(rows)} з {len(ev)}, смуга {ch["band"][:2]}')
    # «До поточного» з майбутнього місяця: числа як у v156 у режимі місяця
    page.locator('.ov-back:visible').click()
    page.wait_for_timeout(300)
    check(page.locator('.ov-per:visible').count() == 0, f'{vp} місяць: після «До поточного» лишився рядок не поточного періоду')
    expc = _expected(page)[vp + '-month']
    gotc = _snap(page)
    for k in expc:
        check(gotc.get(k) == expc[k], f'{vp} місяць: після «До поточного» «{k}» не як у v156: {gotc.get(k)}')
    # В: попередній місяць з історії, синтетичні платежі 15.09 і 25.09 у місяці, 02.10 поза ним
    freeze(page, DAY, PAST_TX)
    go_tab(page, 0)
    page.wait_for_timeout(400)
    raw = page.evaluate(RAW)
    e = date(t.year, t.month, 1)
    s = date(e.year - (e.month == 1), (e.month - 2) % 12 + 1, 1)
    S, E, last = _iso(s), _iso(e), _iso(e - timedelta(days=1))
    tag = f'{vp} місяць -1 ({S}..{E})'
    _nav(page, -1)
    got = _snap(page)
    per = page.evaluate(PER_T)
    check(per == f'Минулий місяць {_dm(S)}-{_dm(last)}', f'{tag}: рядок періоду «{per}»')
    own, bal = _hist(raw, last)
    debt = own - bal
    _tiles_equal(got, {'funds': (max(0, own) + max(0, _limit(raw) - debt), [('Власні', own), ('Борг кредиток', -debt)]),
                       'balance': (bal, [('Власні', own), ('Мінусові', -debt)]),
                       'inst': (_inst(raw['fin'], last, last), [])}, tag)
    for k, x in got['kpis'].items():
        check(x['sub'] == f'на {_dm(last)}', f'{tag}: {k}: позначка «{x["sub"]}»')
    fact = _ring_total(got)
    bf, bp = _bud_card(got, vp)
    check(fact > 0 and bp is None and abs(bf - fact) < 0.5, f'{tag}: картка бюджету «{got["bud"]}», факт кільця {fact}')
    check(got['budLbl'] == 'Фактичні витрати періоду', f'{tag}: підпис картки бюджету «{got["budLbl"]}»')
    rows = page.evaluate(NEAR)
    check([d for _, d in rows] == ['15.09', '25.09'], f'{tag}: рядки платежів {rows}')
    ch = page.evaluate(CHART)
    check(ch['band'] and ch['band'][0] == S and ch['band'][1] == last, f'{tag}: смуга графіка {ch}')
    check(ch['per'] and ch['per'][0] == last and abs(num(ch['per'][1].split(' ', 2)[2]) - bal / 100) <= 1, f'{tag}: заголовок графіка {ch["per"]}')
    print(f'      {tag}: плитки {[got["kpis"]["kpi-" + k]["v"] for k in ("funds", "budget", "balance", "inst")]}, бюджет «{got["bud"]}», платежі {rows}')
    page.evaluate('()=>localStorage.setItem("per_mode","period")')


CHECKS = [
    ('v157: поточний період: числа Огляду як у v156 (ПК)', 'desktop', current_matches),
    ('v157: поточний період: числа Огляду як у v156 (телефон)', 'mobile', current_matches),
    ('v157: майбутні періоди (+1 і +7): плитки, бюджет, платежі, смуга графіка, «До поточного» (ПК)', 'desktop', future_periods),
    ('v157: майбутні періоди (+1 і +7): плитки, бюджет, платежі, смуга графіка, «До поточного» (телефон)', 'mobile', future_periods),
    ('v157: минулий період: плитки з історії, бюджет лише фактом, фактичні платежі (ПК)', 'desktop', past_period),
    ('v157: минулий період: плитки з історії, бюджет лише фактом, фактичні платежі (телефон)', 'mobile', past_period),
    ('v157: режим місяця: наступний і попередній місяць, «До поточного» (ПК)', 'desktop', month_mode),
    ('v157: режим місяця: наступний і попередній місяць, «До поточного» (телефон)', 'mobile', month_mode),
]
