# Стартове атомарне завантаження: скелетон тримається до останнього ресурсу;
# помилка однієї таблиці дає банер, retry завантажує повний snapshot.
from helpers import check, shot

DELAY = 1500
TABLES = ['transactions', 'accounts', 'fixed_payments', 'credits', 'categories',
          'category_groups', 'salary_config', 'savings_log', 'goals', 'monthly_budgets']
# Початкова пачка має затримку; фінальний goals read відпускається тестом.
# Решта стадій виконується без штучного множення 1,5 с на кожен послідовний read.
MOCK = """(()=>{const st={fail:%(fail)s,calls:{},completed:{},functions:[],handlers:{},pendingGoals:[],holdGoals:%(hold)s};window.__sbMock=st;
const account={id:1,name:'Synthetic mono',bank:'mono',kind:'debit',balance:1234,debt:0,active:true,mono_account_id:'synthetic-mono',sort_order:0};
const data={accounts:[account],categories:[],category_groups:[],salary_config:[{id:1,rate:10000,advance_day:21,salary_day:6,split_day:15,savings_pct:20}],fixed_payments:[],credits:[],transactions:[],savings_log:[],goals:[{id:1,name:'Synthetic goal',target_amount:1000,sort_order:0}],profiles:{id:'spec-user',onboarded_at:'2020-01-01',telegram_chat_id:null}};
const base=['categories','category_groups','salary_config','accounts','fixed_payments','credits'];
const q=function(table){const self=new Proxy({},{get:function(_,k){
 if(k==='then')return function(res,rej){st.calls[table]=(st.calls[table]||0)+1;const n=st.calls[table];
  const finish=function(){st.completed[table]=(st.completed[table]||0)+1;const bad=st.fail===table&&n===1;res({data:bad?null:(data[table]||[]),error:bad?{message:'mock: '+table}:null})};
  if(table==='goals'&&st.holdGoals)st.pendingGoals.push(finish);else setTimeout(finish,base.includes(table)||table==='profiles'?%(delay)d:0)};
 return function(){return self}}});return self};
st.releaseGoals=function(){st.holdGoals=false;st.pendingGoals.splice(0).forEach(function(f){f()})};
window.supabase={createClient:function(){return{
 from:q,
 channel:function(){return{on:function(event,filter,fn){st.handlers[filter.table]=fn;return this},subscribe:function(fn){queueMicrotask(function(){fn('SUBSCRIBED')});return this}}},removeChannel:function(){return Promise.resolve()},
 auth:{getSession:function(){return Promise.resolve({data:{session:{user:{id:'spec-user',email:ALLOWED_EMAILS[0]}}}})},
  onAuthStateChange:function(){return{data:{subscription:{unsubscribe:function(){}}}}},signOut:function(){return Promise.resolve({})}},
 storage:{from:function(){return{createSignedUrls:function(){return Promise.resolve({data:[]})},createSignedUrl:function(){return Promise.resolve({data:null})},upload:function(){return Promise.resolve({})},remove:function(){return Promise.resolve({})}}}},
 functions:{invoke:function(name){st.functions.push(name);return Promise.resolve({data:{ok:true,cached:true,account:account},error:null})}}}}};})();"""


def _with_mock(page, fail='null', hold_goals=True):
    """Перезавантаження з підміненим supabase і короткою заставкою (SPLASH_MAX 700 мс замість 6 с)."""
    url = page.url
    page.add_init_script(MOCK % {'fail': fail, 'delay': DELAY, 'hold': str(hold_goals).lower()})

    def fix(route):
        r = route.fetch()
        body = r.text()
        a = 'SPLASH_MIN=600,SPLASH_MAX=6000'
        check(body.count(a) == 1, 'константи заставки не знайдено')
        route.fulfill(response=r, body=body.replace(a, 'SPLASH_MIN=600,SPLASH_MAX=700'))
    page.route(url, fix)
    page.reload()
    page.wait_for_selector('.side' if page.viewport_size['width'] >= 1024 else '.tab-bar', timeout=5000)


# вміст Огляду після відповіді: підсумок доступних коштів (з KPI або, без графіка виплат у порожній БД, з поясненням) і прогноз
CONTENT = '.p-overview .projection-summary, .p-overview .dv-kpis, .p-overview .dv-fc'


def _complete_snapshot(page):
    state = page.evaluate('({calls:__sbMock.calls,completed:__sbMock.completed,handlers:Object.keys(__sbMock.handlers),functions:__sbMock.functions})')
    check(all(state['completed'].get(t, 0) > 0 for t in TABLES), f'не прочитано повний snapshot: {state}')
    check(state['completed'].get('profiles', 0) > 0, 'профіль не завантажено')
    check(set(state['handlers']) == set(TABLES), f'не підписано повний набір таблиць: {state["handlers"]}')
    check('mono-balance' in state['functions'], 'початковий snapshot оминув Monobank')


def demo_no_skel(page):
    check(page.locator('.skel').count() == 0, 'у превʼю без БД видно скелетони')
    check(page.locator('.dv-kpi').count() == 4, 'у превʼю без БД немає 4 KPI Огляду')
    check(page.locator('.ld-err').count() == 0, 'банер помилки без БД')


def _skel_then_data(page, name, kpi_sel):
    _with_mock(page)
    page.wait_for_selector('.skel', timeout=1000)
    t = page.inner_text('.content')
    check('₴' not in t, f'під час завантаження на екрані суми: {t[:120]!r}')
    check(page.locator(kpi_sel).count() == 0, 'під час завантаження видно блоки з даними')
    check(page.locator('[role=status][aria-busy=true]').count() == 1, 'скелетон без role=status і aria-busy')
    shot(page, name)
    page.wait_for_function('__sbMock.pendingGoals.length===1', timeout=DELAY + 2500)
    check(page.locator('.skel').count() > 0, 'скелетон зник до останнього ресурсу snapshot')
    check(page.locator(kpi_sel).count() == 0, 'часткова відповідь показала фінансові дані')
    page.evaluate('__sbMock.releaseGoals()')
    page.wait_for_selector('.skel', state='detached', timeout=2500)
    page.wait_for_selector('.sync-status[data-state=updated]', timeout=2500)
    _complete_snapshot(page)
    check(page.locator(kpi_sel).count() > 0, 'після відповіді не зʼявився вміст')
    check(page.locator('.ld-err').count() == 0, 'банер помилки без помилки')


def skel_desktop(page):
    _skel_then_data(page, 'skeleton-1280.jpg', CONTENT)


def skel_mobile(page):
    _skel_then_data(page, 'skeleton-375.jpg', CONTENT)


def error_banner(page):
    _with_mock(page, "'credits'", hold_goals=False)
    page.wait_for_selector('.ld-err', timeout=DELAY + 2500)
    t = page.inner_text('.ld-err')
    check('Не вдалося завантажити' in t and 'Не вдалося оновити фінансові дані' in t and 'Повторити' in t, f'текст банера: {t!r}')
    check(page.locator('.sync-status').get_attribute('data-state') == 'degraded', 'невдалий snapshot показав успішне оновлення')
    page.locator('.ld-err button', has_text='Повторити').click()
    page.wait_for_selector('.ld-err', state='detached', timeout=1000)
    page.wait_for_selector('.sync-status[data-state=updated]', timeout=DELAY + 2500)
    page.wait_for_selector(CONTENT, timeout=2500)
    _complete_snapshot(page)
    calls = page.evaluate('window.__sbMock.calls.credits')
    check(calls == 2, f'«Повторити» не перезапустив запит розстрочок: викликів {calls}')
    check(page.locator('.ld-err').count() == 0, 'банер повернувся після вдалого повтору')


CHECKS = [
    ('Без БД: демо одразу, без скелетонів', 'desktop', demo_no_skel),
    ('З БД: скелетони замість сум, потім вміст (ПК)', 'desktop', skel_desktop),
    ('З БД: скелетони замість сум, потім вміст (телефон)', 'mobile', skel_mobile),
    ('Помилка запиту: банер «Повторити» перезапускає', 'desktop', error_banner),
]
