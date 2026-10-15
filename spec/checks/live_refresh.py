"""Справжній App із підміною Supabase: зовнішні події, гонки, помилки, без фонових записів."""
from helpers import check, freeze, go_tab, num
from checks.v157 import _nav

DAY = '2026-10-15'
MOCK = r"""(()=>{
 const m=window.__liveMock={reads:[],writes:[],handlers:{},pending:[],hold:false,pendingWrites:[],holdWrites:false,monoFail:false,fail:null,removed:0,channels:0};
 m.data={accounts:[{id:1,name:'Synthetic cash',kind:'debit',bank:'cash',balance:1000,debt:0,active:true,sort_order:0,balance_updated_at:'2026-10-15T00:00:00Z'}],categories:[{id:'food',name:'Продукти',icon:'🛒',color:'#7066e0',budget_limit:1,group_id:1,sort_order:0}],category_groups:[{id:1,name:'Побут',sort_order:0}],salary_config:[{id:1,rate:0,advance_day:21,salary_day:6,split_day:15,advance_amount:50000,salary_amount:60000,savings_pct:20}],fixed_payments:[],credits:[],goals:[{id:1,name:'Synthetic goal',target_amount:1000,sort_order:0}],savings_log:[],transactions:[{id:1,date:'2026-10-15',created_at:'2026-10-15T10:00:00Z',type:'expense',amount:10,account_id:1,category_id:'food',description:'Initial mock row',source:'manual',categories:{name:'Продукти',icon:'🛒',color:'#7066e0'}}],exchange_rates:[]};
 const clone=x=>JSON.parse(JSON.stringify(x));
 const sb={from(table){const q={table,ops:[],mode:'read'};for(const method of ['select','order','eq','neq','not','gte','lte','or','in','limit','range','maybeSingle','single'])q[method]=(...args)=>{q.ops.push([method,...args]);return q};for(const method of ['insert','update','delete'])q[method]=(...args)=>{q.mode=method;q.ops.push([method,...args]);return q};
 q.then=(resolve,reject)=>{
  if(q.mode!=='read'){m.writes.push({table,mode:q.mode,ops:clone(q.ops)});const apply=()=>{const update=q.ops.find(x=>x[0]==='update'),eq=q.ops.find(x=>x[0]==='eq');if(update)(m.data[table]||[]).forEach(row=>{if(!eq||row[eq[1]]===eq[2])Object.assign(row,update[1])});return{data:[],error:null}};if(m.holdWrites)return new Promise(r=>m.pendingWrites.push(()=>r(apply()))).then(resolve,reject);return Promise.resolve(apply()).then(resolve,reject)}
  m.reads.push({table,ops:clone(q.ops)});let rows=clone(m.data[table]||[]);
  for(const [method,a,b] of q.ops){if(method==='gte')rows=rows.filter(r=>String(r[a])>=String(b));if(method==='lte')rows=rows.filter(r=>String(r[a])<=String(b));if(method==='eq')rows=rows.filter(r=>r[a]===b);if(method==='in')rows=rows.filter(r=>b.includes(r[a]));if(method==='order')rows.sort((x,y)=>String(x[a]).localeCompare(String(y[a]))*((b&&b.ascending===false)?-1:1));if(method==='range')rows=rows.slice(a,b+1);if(method==='limit')rows=rows.slice(0,a)}
  const result=table==='profiles'?{data:{id:'mock-family',onboarded_at:'2020-01-01',telegram_chat_id:null}}:m.fail===table?{error:{message:'Synthetic read failure'}}:{data:rows};
  if(m.hold&&table==='transactions'&&q.ops.some(x=>x[0]==='range'))return new Promise(r=>m.pending.push(()=>r(result))).then(resolve,reject);
  return Promise.resolve(result).then(resolve,reject);
 };return q},
 auth:{getSession:()=>Promise.resolve({data:{session:{user:{id:'mock-family',email:ALLOWED_EMAILS[0]}}}}),onAuthStateChange:cb=>{m.auth=cb;return{data:{subscription:{unsubscribe(){}}}}},signOut:()=>{m.auth('SIGNED_OUT',null);return Promise.resolve({})}},
 channel(){m.channels++;return{on(event,filter,cb){m.handlers[filter.table]=cb;return this},subscribe(cb){m.channelStatus=cb;queueMicrotask(()=>cb('SUBSCRIBED'));return this}}},removeChannel:()=>{m.removed++;return Promise.resolve()},storage:{from:()=>({createSignedUrls:paths=>Promise.resolve({data:paths.map(path=>({path,signedUrl:'mock://'+path}))})})},functions:{invoke:()=>Promise.resolve({data:m.monoFail?{ok:false,reason:'no_token'}:{ok:true,cached:true,account:clone(m.data.accounts[0])}})}};
 m.releaseWrites=()=>{m.holdWrites=false;m.pendingWrites.splice(0).forEach(f=>f())};m.event=table=>m.handlers[table]&&m.handlers[table]({});m.release=()=>{m.hold=false;m.pending.splice(0).forEach(f=>f())};window.supabase={createClient:()=>sb};
})()"""


def mount(page):
    page.add_init_script(MOCK)
    freeze(page, DAY)
    page.wait_for_selector('.sync-status[data-state=updated]', timeout=20000)
    check(page.evaluate('Object.keys(__liveMock.handlers).length') == 9, 'nine finance subscriptions required')
    check(page.evaluate('__liveMock.channels') == 1, 'duplicate auth channel')


def updated(page):
    page.wait_for_selector('.sync-status[data-state=updated]', timeout=15000)


def external_updates(page):
    mount(page)
    before = num(page.locator('.kpi-funds .dv-kpi-v').inner_text())
    initial_reads = page.evaluate('__liveMock.reads.filter(x=>x.table==="accounts").length')
    page.evaluate("""()=>{const m=__liveMock;m.data.accounts[0].balance=2500;m.data.transactions.push({...m.data.transactions[0],id:2,amount:55,description:'External family transaction'});for(let i=0;i<20;i++)m.event(i%2?'accounts':'transactions')}""")
    page.wait_for_timeout(100)
    check(page.evaluate('__liveMock.reads.filter(x=>x.table==="accounts").length') == initial_reads, 'DB burst bypassed debounce')
    page.wait_for_function('n=>__liveMock.reads.filter(x=>x.table==="accounts").length===n+1', arg=initial_reads)
    updated(page)
    after = num(page.locator('.kpi-funds .dv-kpi-v').inner_text())
    check(abs(after - before - 1445) < .01, f'account/transaction facts not reflected: {before} -> {after}')
    go_tab(page, 2)
    check('External family transaction' in page.locator('.p-flow').inner_text(), 'external transaction row absent')
    check(page.evaluate('__liveMock.writes.length') == 0, 'background event wrote to DB')
    check(page.evaluate('__liveMock.reads.filter(x=>x.table==="accounts").length') == initial_reads + 1, 'one burst produced duplicate finance batches')


def logout_pending(page):
    mount(page)
    page.evaluate("__liveMock.hold=true;__liveMock.event('transactions')")
    page.wait_for_function('__liveMock.pending.length===1')
    page.evaluate("__liveMock.auth('SIGNED_OUT',null)")
    page.wait_for_function('__liveMock.removed===1')
    page.evaluate('__liveMock.release()')
    page.wait_for_timeout(500)
    check(page.locator('.sync-status').count() == 0 and page.locator('.kpi-funds').count() == 0, 'old read republished authenticated UI after logout')
    check(page.evaluate('__liveMock.writes.length') == 0, 'logout cleanup wrote data')


def view_pending(page):
    mount(page)
    page.evaluate("""()=>{const m=__liveMock;m.hold=true;m.data.transactions.push({...m.data.transactions[0],id:10,date:'2026-09-15',created_at:'2026-09-15T10:00:00Z',description:'Previous month correct'});m.event('transactions')}""")
    page.wait_for_function('__liveMock.pending.length===1')
    _nav(page, -1)
    page.evaluate('__liveMock.release()')
    updated(page)
    go_tab(page, 2)
    text = page.locator('.p-flow').inner_text()
    check('Previous month correct' in text and 'Initial mock row' not in text, 'late old view replaced selected month rows')


def failure_retry_and_goals(page):
    mount(page)
    old_stamp = page.locator('.sync-status').get_attribute('data-updated')
    old_funds = page.locator('.kpi-funds .dv-kpi-v').inner_text()
    page.clock.set_fixed_time(DAY + 'T12:01:00')
    page.evaluate("__liveMock.fail='transactions';__liveMock.data.accounts[0].balance=8888;__liveMock.event('accounts')")
    page.wait_for_selector('.sync-status[data-state=degraded]')
    check(page.locator('.sync-status').get_attribute('data-updated') == old_stamp, 'failed read advertised freshness')
    check(page.locator('.kpi-funds .dv-kpi-v').inner_text() == old_funds, 'failed read partially committed accounts')
    page.evaluate("__liveMock.fail=null;__liveMock.data.goals=[]")
    page.locator('.sync-status').get_by_role('button', name='Повторити').click()
    updated(page)
    check(num(page.locator('.kpi-funds .dv-kpi-v').inner_text()) > 8000, 'retry did not load new account')
    page.evaluate("__liveMock.event('goals')")
    page.wait_for_timeout(650)
    updated(page)
    check(page.evaluate('__liveMock.writes.length') == 0, 'empty background goals seeded records')
    page.evaluate("__liveMock.channelStatus('TIMED_OUT')")
    check('Автооновлення недоступне' in page.locator('.sync-status').inner_text(), 'channel fallback not visible')
    stamp = page.locator('.sync-status').get_attribute('data-updated')
    page.evaluate("__liveMock.channelStatus('SUBSCRIBED')")
    check(page.locator('.sync-status').get_attribute('data-updated') == stamp, 'SUBSCRIBED faked update timestamp')
    updated(page)


CHECKS = [
    ('live_refresh: actual App external event changes financial facts', 'desktop', external_updates),
    ('live_refresh: logout invalidates pending actual App response', 'desktop', logout_pending),
    ('live_refresh: selected month rejects older pending response', 'desktop', view_pending),
    ('live_refresh: atomic error retry and read-only empty goals', 'desktop', failure_retry_and_goals),
]


def pending_config(page):
    mount(page)
    go_tab(page, 1)
    page.get_by_role('button', name='Розподіл бюджету', exact=True).first.click()
    field = page.locator('.bud-man-in')
    field.fill('25000')
    field.blur()
    page.evaluate("__liveMock.data.accounts[0].balance=2500;__liveMock.event('accounts')")
    page.wait_for_timeout(470)
    check(num(field.input_value()) == 25000, 'snapshot clobbered pending budget before 600ms')
    page.wait_for_function('__liveMock.writes.some(x=>x.table==="salary_config")')
    updated(page)
    check(page.evaluate('__liveMock.data.salary_config[0].budget_manual') == 25000, 'snapshot canceled debounce write')
    page.evaluate('__liveMock.holdWrites=true')
    field.fill('30000');field.blur()
    page.wait_for_function('__liveMock.pendingWrites.length===1')
    field.fill('40000');field.blur()
    page.evaluate("__liveMock.event('accounts')")
    page.wait_for_timeout(700)
    check(num(field.input_value()) == 40000, 'older server state replaced latest draft while write pending')
    page.evaluate('__liveMock.releaseWrites()')
    page.wait_for_function('__liveMock.data.salary_config[0].budget_manual===40000')
    updated(page)
    check(num(field.input_value()) == 40000, 'old acknowledgement cleared latest pending value')


def mono_failure(page):
    page.add_init_script(MOCK.replace("bank:'cash'", "bank:'mono'").replace('monoFail:false', 'monoFail:true'))
    freeze(page, DAY)
    page.wait_for_selector('.sync-status[data-state=degraded]', timeout=20000)
    check(page.locator('.kpi-funds .dv-kpi-v').count() == 1, 'Mono failure blanked database finance cards')
    check(num(page.locator('.kpi-funds .dv-kpi-v').inner_text()) > 0, 'Mono failure discarded successful database rows')
    check(page.locator('.sync-status').get_attribute('data-updated') == '', 'failed initial bank refresh advertised freshness')
    check(page.evaluate('__liveMock.writes.length') == 0, 'Mono fallback wrote finance data')


CHECKS += [('live_refresh: background snapshot preserves pending manual budget', 'desktop', pending_config),
           ('live_refresh: failed bank refresh retains database snapshot honestly', 'desktop', mono_failure)]
