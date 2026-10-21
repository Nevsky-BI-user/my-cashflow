"""Незалежні суми й паритет екранів; дати та межі обчислюються в Python."""
from datetime import date, timedelta
from helpers import check, freeze, go_tab, num
from checks.v157 import _nav, _snap, _bud_card

DAY='2026-10-13'

def assert_unsaved_salary(page, start='2026-10-01'):
    """Незбережений місяць: зарплата й сирі зобов'язання, без прогнозних витрат."""
    raw=page.evaluate("""()=>{const b=window.__calendarBudget,s=window.__cashSnap(),d=b.start.split('-').map(Number);return{budget:b,envelope:monthlySalaryEnvelope(s.salary,s.fixed,s.credits,d[0],d[1]-1)}}""")
    b,e=raw['budget'],raw['envelope']
    mandatory=sum(i['amount_cents'] for i in e['mandatory_items'])
    net=max(0,e['total_cents']-mandatory)
    check(b['start']==start and b['gross']==e['total_cents'] and b['mandatory']==mandatory,'calendar salary or mandatory total differs from raw monthly envelope')
    check(b['plan']==net and b['unallocated']==net and b['remaining']==net-b['fact'],'unsaved calendar capacity must equal salary minus mandatory payments')
    check(num(page.locator('.bud-pool .bud-kpi-v').inner_text())==e['total_cents']/100,'salary KPI differs from calendar payouts')
    check(num(page.locator('.bud-mandatory .bud-kpi-v').inner_text())==mandatory/100,'mandatory payment KPI differs from raw commitments')
    check(num(page.locator('.bud-avail .bud-kpi-v').inner_text())==(net-b['fact'])/100,'available KPI differs from salary minus commitments and actual category spending')
    check(page.locator('.bud-day,.bud-alloc').count()==0,'allocation summary belongs only in editor')
    return b

def verify(page):
    raw=page.evaluate("()=>({tx:window.__cashSnap().transactions,periods:window.__cashCore.projection.periods,pbs:window.__periodBudget,view:window.__budgetView})")
    v=raw['view']; start,end=v['start'],v['end']
    tx={str(t['id']):t for t in raw['tx']}.values()
    tx=[t for t in tx if start<=t['date']<end and t['date']<=DAY]
    cents=lambda t:round(float(t['amount'])*100)
    income=sum(cents(t) for t in tx if t['type']=='income')
    expense=sum(cents(t) for t in tx if t['type']=='expense')
    fact=sum(cents(t) for t in tx if t['type']=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None)
    month=start.endswith('-01') and end.endswith('-01')
    cur=start<=DAY<end
    if end<=DAY: plan=None
    elif month: plan=fact+sum(d['spendCents'] for p in raw['periods'] for d in p['schedule'] if start<=d['date']<end and d['date']>DAY)
    elif cur: plan=raw['pbs']['budget']
    else: plan=next(p['targetCents'] for p in raw['periods'] if p['start']==start)
    check((v['fact'],v['plan'],v['income'],v['expense'],v['balance'])==(fact,plan,income,expense,income-expense), f'range {start}..{end}: adapter differs from raw sums')
    cursor=date.fromisoformat(start);total=0
    for w in v['weeks']:
        stop=min(cursor+timedelta(days=7),date.fromisoformat(end)); last=stop-timedelta(days=1)
        label=cursor.strftime('%d.%m')+'-'+last.strftime('%d.%m')
        check((w['start'],w['end'],w['label'])==(cursor.isoformat(),stop.isoformat(),label),'week date boundaries/label')
        expected=sum(cents(t) for t in tx if t['type']=='expense' and w['start']<=t['date']<w['end'])
        check(w['cents']==expected,'week amount');total+=w['cents'];cursor=stop
    check(cursor.isoformat()==end and total==expense,'weeks do not partition entire selected range')
    vp='desktop' if page.viewport_size['width']>=1024 else 'mobile'
    got=_snap(page);a,b=_bud_card(got,vp)
    if month and plan is not None: check(got['budLbl']=='Бюджет місяця','monthly budget label')
    check(abs(a-fact/100)<.51 and ((b is None and plan is None) or (b is not None and plan is not None and abs(b-plan/100)<.51)),f'{vp} Overview {got["bud"]}, expected {fact}/{plan}')
    if vp=='mobile':
        labels=page.locator('.o-weeks').inner_text()
        check(all(w['label'] in labels for w in v['weeks']),'week UI is not selected range')
        check(page.locator('.o-strip,.o-ccy').count()==0,'removed mobile bottom totals or rates returned')
    go_tab(page,1)
    monthly=page.evaluate("()=>({v:window.__calendarBudget,tx:txDemo(2026,9)})")
    mb=monthly['v']
    actual_month=sum(cents(t) for t in monthly['tx'] if t['type']=='expense' and t.get('fixed_id') is None and t.get('credit_id') is None and '2026-10-01'<=t['date'][:10]<=DAY)
    check(mb['start']=='2026-10-01' and mb['fact']==actual_month,'Budget must use its own current calendar month')
    assert_unsaved_salary(page)
    check(abs(num(page.locator('.bud-spent .bud-kpi-v').inner_text())-actual_month/100)<.01,'monthly Budget fact differs from raw rows')
    print(f'      {vp} {start}..{end}: fact {fact/100}, plan {None if plan is None else plan/100}, weekly {total/100}')
    go_tab(page,0)

def parity(page):
    for mode in ('period','month'):
        page.evaluate('m=>localStorage.setItem("per_mode",m)',mode)
        freeze(page,DAY)
        verify(page)
        _nav(page,1);verify(page)
        _nav(page,-2);verify(page)

def edges(page):
    for start,end in [('2026-02-01','2026-03-01'),('2028-02-01','2028-03-01'),('2026-09-01','2026-10-01'),('2026-09-21','2026-10-06')]:
        s,e=date.fromisoformat(start),date.fromisoformat(end);today=(s+timedelta(days=8)).isoformat()
        rows=[dict(id=str(i),date=(s+timedelta(days=i)).isoformat(),type='expense',amount=i+.25,category_id='unknown') for i in range((e-s).days)]
        rows += [rows[0],dict(id='fixed',date=start,type='expense',amount=300,fixed_id='f'),dict(id='credit',date=start,type='expense',amount=400,credit_id='c'),dict(id='before',date=(s-timedelta(days=1)).isoformat(),type='expense',amount=999),dict(id='after',date=end,type='expense',amount=999)]
        got=page.evaluate('a=>budgetRangeFacts(a.rows,[],a.start,a.end,a.today)',dict(rows=rows,start=start,end=end,today=today))
        expected=sum(round((i+.25)*100) for i in range(9))
        check(got['fact']==expected and got['byCategory']=={'unallocated':expected},'dedup/exclusions/no future facts')
        check(sum(w['cents'] for w in got['weeks'])==expected+70000,'all expense weekly total')
        check(got['weeks'][-1]['end']==end and got['weeks'][-1]['label'].endswith((e-timedelta(days=1)).strftime('%d.%m')),'invalid month end')

def drilldown(page):
    page.evaluate("localStorage.setItem('per_mode','month')")
    freeze(page,DAY)
    page.locator('.bd-row').filter(has_text='Без категорії').click()
    check(num(page.locator('.cat-drw-f').inner_text())==340,'unallocated drawer fact')
    check(page.locator('.cat-op').count()==1 and 'Аптека' in page.locator('.cat-op').inner_text(),'unallocated drawer must show its transaction')
    page.locator('.cat-to-flow').click()
    check('Аптека' in page.locator('.p-flow').inner_text() and 'Сільпо' not in page.locator('.p-flow').inner_text(),'unallocated flow filter')
    if page.viewport_size['width']<1024:
        check('Без категорії' in page.locator('.flow-mobile-filter').inner_text(),'missing active filter explanation')
        page.get_by_role('button',name='Показати всі операції').click()
        check('Сільпо' in page.locator('.p-flow').inner_text(),'clear filter must restore operations')


def unavailable(page):
    page.evaluate("localStorage.setItem('per_mode','month')")
    freeze(page,DAY,[("const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:financeThrough});", "const baseProjection=financeProjection(financeInput,{asof:financeOptions.asof,through:'2026-11-05'});")])
    _nav(page,1)
    check(page.evaluate('window.__budgetView.plan') is None,'partial future month cannot have complete zero/partial plan')
    check('/' not in page.locator('.dv-bud-v,.o-bud-v').inner_text(),'unavailable Overview shows a numeric plan')
    go_tab(page,1)
    assert_unsaved_salary(page)
    check(page.locator('.bud-mandatory').count()==1,'independent monthly Budget lacks mandatory payment explanation')


CHECKS=[('budget_period_parity: all selected ranges desktop','desktop',parity),('budget_period_parity: all selected ranges mobile','mobile',parity),('budget_period_parity: February September crossmonth boundaries and exclusions','desktop',edges)]

CHECKS += [('budget_period_parity: unallocated drawer and flow desktop','desktop',drilldown),('budget_period_parity: unallocated drawer and flow mobile','mobile',drilldown),('budget_period_parity: incomplete projection month unavailable','desktop',unavailable)]


def responsive(page):
    freeze(page,DAY)
    for width,height in [(320,812),(1280,800),(1440,900)]:
        page.set_viewport_size(dict(width=width,height=height))
        page.wait_for_timeout(700)
        from helpers import settle
        settle(page)
        geo=page.evaluate("""()=>({wide:document.documentElement.scrollWidth,clipped:[...document.querySelectorAll('.dv-kpi-v,.kpi-rv')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent),main:(()=>{const e=document.querySelector('.dv-cols');return e?{height:e.clientHeight,scroll:e.scrollHeight,bottom:e.getBoundingClientRect().bottom}:null})(),budget:(()=>{const e=document.querySelector('.dv-bud');return e?e.getBoundingClientRect().bottom:null})(),chart:(()=>{const e=document.querySelector('.dv-fc svg');return e?e.getBoundingClientRect().height:null})()})""")
        check(geo['wide']<=width and not geo['clipped'],f'{width}: cropped money or horizontal overflow {geo}')
        if width>=1024:
            check(geo['main']['scroll']<=geo['main']['height']+2 and geo['budget']<=height and geo['budget']<=geo['main']['bottom']+1,f'{width}: Budget outside visible column {geo}')
            check(geo['chart']>=(159.5 if height<900 else 179.5 if height<1000 else 259.5),f'{width}: graph too short {geo}')
        from helpers import ROOT
        page.screenshot(path=str(ROOT / 'spec' / '.out' / f'budget-parity-final-{width}.png'),full_page=True)
        print(f'      responsive {width}x{height}: {geo}')

CHECKS += [('budget_period_parity: responsive full money and visible Budget','desktop',responsive)]


def historical_geometry(page):
    from checks.v157 import PAST_TX
    from helpers import ROOT, settle
    freeze(page,DAY,PAST_TX)
    _nav(page,-1)
    page.set_viewport_size(dict(width=1280,height=800));page.wait_for_timeout(500);settle(page)
    geo=page.evaluate("""()=>{const o={};for(const sel of ['.dtitle','.p-overview','.dv-cols','.dv-near','.dv-fc','.dv-fc svg','.dv-bud']){const e=document.querySelector(sel),r=e.getBoundingClientRect();o[sel]={top:r.top,bottom:r.bottom,height:r.height,client:e.clientHeight,scroll:e.scrollHeight}}return o}""")
    check(geo['.dv-cols']['scroll']<=geo['.dv-cols']['client']+2 and geo['.dv-bud']['bottom']<=geo['.dv-cols']['bottom']+1,'historical Budget must remain fully visible without inner scroll')
    print('      historical exact geometry:',geo)
    page.screenshot(path=str(ROOT/'spec'/'.out'/'budget-parity-historical-1280.png'),full_page=True)

CHECKS += [('budget_period_parity: historical exact geometry','desktop',historical_geometry)]
