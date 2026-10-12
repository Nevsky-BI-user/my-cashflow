# Finance contract: independent amounts, full parity, explicit scenarios.
import json
import re
from helpers import check, expand_groups, finance_ref, finance_state, freeze, go_tab, num

DAY = '2026-10-10'
FIXTURE = {
 'accounts':[{'id':1,'kind':'debit','balance':2800,'debt':0}, {'id':2,'name':'Кредитка','kind':'credit','balance':0,'debt':16000,'credit_limit':20000}],
 'fixed':[{'id':1,'name':'Платіж','type':'expense','amount':28000,'day_of_month':25,'credit_ok':True}],
 'credits':[], 'transactions':[],
 'salary':{'rate':0,'advance_day':21,'salary_day':6,'split_day':15,'advance_amount':50000,'salary_amount':50000},
 'categories':[{'id':str(i+1),'name':'Category '+str(i),'type':'expense','budget_limit':w} for i,w in enumerate([40,20,15,10,10,5])]
}

def fixture(page, data=None):
    # Патч лише локальної демо-відповіді; файли та база не змінюються.
    freeze(page, DAY, [('const baseProjection=financeProjection(financeInput,', 'Object.assign(financeInput,'+json.dumps(data or FIXTURE, ensure_ascii=False)+');const baseProjection=financeProjection(financeInput,')])

def _budget_tip(page):
    """v145: відкриває підказку плитки «Бюджет періоду» кнопкою «i» (як на телефоні), повертає її текст."""
    page.locator('.kpi-budget .kpi-i').click()
    page.wait_for_selector('.kpi-tip[data-k=budget]')
    return page.inner_text('.kpi-tip[data-k=budget]')

def contract(page):
    fixture(page)
    r=finance_ref(page, verify_ts=True)
    n=r['nextPlan']
    check([n[k] for k in ('baseAvailableCents','targetCents','gapCents','days','averageDailyCents')]==[880000,1500000,620000,16,93750], '8800/15000/6200/16/937.50 acceptance example failed')
    check([c['totalCents'] for c in n['categories']]==[600000,300000,225000,150000,150000,75000], 'category allocation differs from 40/20/15/10/10/5')
    check(not any(e['funding']=='credit' for e in r['events']), 'base projection automatically used credit')
    check(any(d['closingCashCents']<0 for d in r['days']), 'signed cash shortfall was hidden')
    # v145: «доступно після виплати» живе в підказці плитки «Бюджет періоду»; кнопки там же
    tip=_budget_tip(page)
    m=re.search(r'= ([\d\s  ]+(?:,\d+)?) ₴ \(власні', tip)
    check(m and num(m.group(1))==8800, f'overview does not show8800: {tip!r}')
    page.locator('.kpi-tip[data-k=budget]').get_by_role('button',name='Як пораховано',exact=True).click()
    check('28' in page.locator('dialog[open]').inner_text(), 'explanation omits mandatory28000')
    page.locator('dialog[open]').get_by_role('button',name='Закрити',exact=True).click()

def scenario(page):
    fixture(page)
    before=finance_state(page)['data']
    writes=[]
    page.on('request',lambda q:writes.append(q.url) if q.method not in ('GET','HEAD','OPTIONS') else None)
    _budget_tip(page)
    page.locator('.kpi-tip[data-k=budget]').get_by_role('button',name='Сценарій кредитки',exact=True).click()
    d=page.locator('dialog[open]')
    d.get_by_label('Дозволений платіж').select_option('fixed:1:2026-10')
    d.get_by_label('Кредитний рахунок').select_option('2')
    for amount,plan,gap in [(6200,1500000,0),(4000,1280000,220000)]:
        d.get_by_label('Сума перенесення',exact=True).fill(str(amount))
        d.get_by_role('button',name='Переглянути сценарій').click()
        r=finance_ref(page,verify_ts=True)
        s=r['scenario']
        check((s['newDebtCents'],s['cashPlanCents'],s['gapCents'])==(amount*100,plan,gap), 'scenario debt/plan/gap mismatch')
        check(s['repayments'][0]['date']=='2026-11-24' and not s['errors'], 'scenario repayment date or errors mismatch')
        check(r['nextPlan']['baseAvailableCents']==880000, 'scenario replaced base headline')
    d.get_by_label('Сума перенесення',exact=True).fill('21000')
    d.get_by_role('button',name='Переглянути сценарій').click()
    r=finance_ref(page)
    check(r['scenario']['newDebtCents']==0 and r['scenario']['errors'] and d.locator('[role=alert]').count(), 'credit limit overflow accepted')
    d.get_by_role('button',name='Скинути сценарій').click()
    check(finance_ref(page)['scenario'] is None, 'reset did not restore base')
    check(finance_state(page)['data']==before and not writes, 'scenario mutated input or sent network write')

def weights(page):
    freeze(page,DAY)
    old=finance_ref(page)
    freeze(page,DAY, [("id:'food',groupId:1,name:'Продукти',limit:15000", "id:'food',groupId:1,name:'Продукти',limit:30000")])
    r=finance_ref(page,verify_ts=True)
    food=lambda p:next(c['totalCents'] for c in p['nextPlan']['categories'] if c['id']=='food')
    check(food(r)>food(old), 'подвоєна вага не збільшила план категорії')
    check(r['nextPlan']['targetCents']==old['nextPlan']['targetCents'], 'зміна ваги змінила загальну ціль')
    for period in r['periods']:
        check(sum(c['totalCents'] for c in period['categories'])==sum(d['spendCents'] for d in period['schedule']), 'ваги втратили копійки')
    go_tab(page,1)
    page.locator('.side-arr').nth(1).click()
    page.wait_for_timeout(200)
    expand_groups(page)
    row=page.locator('.bud-cat',has_text='Продукти')
    check(abs(num(row.locator('.bud-nums').inner_text().split('/')[1])-food(r)/100)<=1, 'екран категорії не оновив план')

def unavailable(page):
    data=json.loads(json.dumps(FIXTURE));data['fixed'][0]['credit_ok']=False;del data['accounts'][1]['credit_limit']
    fixture(page,data)
    _budget_tip(page)
    page.locator('.kpi-tip[data-k=budget]').get_by_role('button',name='Сценарій кредитки',exact=True).click()
    d=page.locator('dialog[open]')
    check(d.get_by_label('Дозволений платіж').locator('option').count()==1, 'непридатний платіж доступний')
    check(d.get_by_label('Кредитний рахунок').locator('option').count()==1, 'невідомий ліміт доступний')
    check(d.get_by_role('button',name='Переглянути сценарій').is_disabled(), 'неповний сценарій доступний')
    check(finance_ref(page)['scenario'] is None, 'недоступний сценарій застосовано')

def no_salary(page):
    data=json.loads(json.dumps(FIXTURE));data['salary']=None
    fixture(page,data)
    r=finance_ref(page,verify_ts=True)
    check(r['nextPlan'] is None and r['reason']=='no_next_payout', 'невідомий графік породив план')
    check('Немає графіка майбутніх виплат' in page.inner_text('.projection-summary'), 'немає порожнього стану графіка')
    for tab in range(5):
        go_tab(page,tab)
        check('NaN' not in page.inner_text('.content'), 'невідомий графік спричинив NaN')

CHECKS=[('Finance: independent amounts and full browser/TS/Python parity','desktop',contract),
 ('Finance: explicit scenario, limits and no writes','desktop',scenario),
 ('Finance: changed category weight reaches screen and exact schedule','desktop',weights),
 ('Finance: unknown limit and ineligible payment unavailable','desktop',unavailable),
 ('Finance: absent salary has no invented payout','desktop',no_salary)]
