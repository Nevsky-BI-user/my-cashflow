"""Незалежний еталон місячного бюджету з налаштуваннями."""
import calendar
import math
from datetime import date, timedelta


def normalize_monthly_budgets(rows, data, asof, through, salary_amount):
    cfg = data.get('salary')
    if not cfg:
        return rows or []
    idx = lambda s: int(s[:4])*12+int(s[5:7])-1
    iso = lambda k, d=1: date(k//12, k%12+1, d).isoformat()
    cents = lambda n: math.floor(float(n or 0)*100+.5)
    current = asof[:7]+'-01'
    saved = sorted(rows or [], key=lambda r:r['month_start'])
    out = [r for r in saved if r['month_start']<current]
    last = max([idx(through)]+[idx(r['month_start']) for r in saved if r['month_start']>=current])
    def shifted(k, day):
        d=date(k//12,k%12+1,int(day))
        return (d+timedelta(days=-1 if d.weekday()==5 else 1 if d.weekday()==6 else 0)).isoformat()
    for k in range(idx(current),last+1):
        start,end=iso(k),iso(k+1)
        source=next((r for r in reversed(saved) if r['month_start']<=start),None)
        if not source: continue
        if source.get('income_basis_cents') is None:
            if source['month_start']==start: out.append(source)
            continue
        income=0
        for j in range(k-1,k+2):
            y,m=j//12,j%12+1; py,pm=(j-1)//12,(j-1)%12+1; split=int(cfg.get('split_day') or 15)
            for when,amount in [(shifted(j,cfg['advance_day']),salary_amount(cfg,y,m,1,split,cfg.get('advance_amount'))),(shifted(j,cfg['salary_day']),salary_amount(cfg,py,pm,split+1,calendar.monthrange(py,pm)[1],cfg.get('salary_amount')))]:
                if start<=when<end: income+=cents(amount)
        items=[dict(x) for x in source.get('mandatory_items',[]) if x['date']<asof] if source['month_start']==start==current else []
        cut=asof if start==current and source['month_start']==start else start
        def add(kind,ident,when,name,amount,estimated=False):
            if cut<=when<end: items.append(dict(key=f'{kind}:{ident}:{when}',date=when,name=str(name or 'Платіж')[:240],amount_cents=cents(amount),kind=kind,estimated=estimated))
        last_day=calendar.monthrange(k//12,k%12+1)[1]
        for i,f in enumerate(data.get('fixed') or []):
            if f.get('active') is False or f.get('type')=='income': continue
            ended=lambda s: f.get('end_date') and s>f['end_date'][:10]
            if f.get('period')=='week':
                for day in range(1,last_day+1):
                    when=iso(k,day)
                    if date.fromisoformat(when).isoweekday()==int(f.get('weekday') or 0) and not ended(when): add('fixed',f.get('id',i+1),when,f.get('name'),f.get('amount'),bool(f.get('variable')))
            elif f.get('period')!='year' or int(f.get('month_of_year') or 0)==k%12+1:
                when=iso(k,min(int(f['day_of_month']),last_day))
                if not ended(when): add('fixed',f.get('id',i+1),when,f.get('name'),f.get('amount'),bool(f.get('variable')))
        for i,c in enumerate(data.get('credits') or []):
            if c.get('active') is False: continue
            first=int(c.get('start_year',c.get('sy',0)))*12+int(c.get('start_month',c.get('sm',0)))
            if not first<=k<first+int(c.get('total_payments',c.get('total',0))): continue
            add('installment',c.get('id',i+1),iso(k,min(int(c.get('payment_day',c.get('day',0))),last_day)),str(c.get('name') or '')+' (розстрочка)',c.get('monthly_amount',c.get('amount')))
        items.sort(key=lambda x:(x['date'],x['name']))
        raw=int(source.get('settings_total_cents',source['total_cents']))+income-int(source['income_basis_cents'])
        deficit=max(0,sum(x['amount_cents'] for x in items)+sum(source.get('allocations',{}).values())-raw)
        copied=dict(source)
        if source['month_start']!=start:
            for field in ['id','created_at','updated_at']: copied.pop(field,None)
        out.append({**copied,'month_start':start,'total_cents':max(0,raw),'income_basis_cents':income,'mandatory_items':items,'allocations':dict(source.get('allocations',{})),'settings_deficit_cents':deficit,'settings_total_cents':raw})
    return out
