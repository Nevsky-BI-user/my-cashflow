# Стартове завантаження: без БД одразу демо без скелетонів; з підміненим supabase (запити «висять» 1,5 с і повертають
# порожні дані) спершу скелетони, а не демо-суми, після відповіді скелетони зникають; помилка запиту дає банер «Повторити».
from helpers import check, shot

DELAY = 1500
# клієнт-заглушка supabase: будь-який ланцюжок .from(...).select().eq()... відповідає через DELAY мс
MOCK = """(()=>{const st={fail:%(fail)s,calls:{}};window.__sbMock=st;
const q=function(table){let single=false;const self=new Proxy({},{get:function(_,k){
 if(k==='then')return function(res,rej){st.calls[table]=(st.calls[table]||0)+1;const n=st.calls[table];
  setTimeout(function(){const bad=st.fail===table&&n===1;res({data:bad?null:(single?null:[]),error:bad?{message:'mock: '+table}:null})},%(delay)d)};
 if(k==='maybeSingle'||k==='single')return function(){single=true;return self};
 return function(){return self}}});return self};
window.supabase={createClient:function(){return{
 from:q,
 auth:{getSession:function(){return Promise.resolve({data:{session:{user:{id:'spec-user',email:'gotnewmess@gmail.com'}}}})},
  onAuthStateChange:function(){return{data:{subscription:{unsubscribe:function(){}}}}},signOut:function(){return Promise.resolve({})}},
 storage:{from:function(){return{createSignedUrls:function(){return Promise.resolve({data:[]})},createSignedUrl:function(){return Promise.resolve({data:null})},upload:function(){return Promise.resolve({})},remove:function(){return Promise.resolve({})}}}},
 functions:{invoke:function(){return Promise.resolve({data:null,error:null})}}}}};})();"""


def _with_mock(page, fail='null'):
    """Перезавантаження з підміненим supabase і короткою заставкою (SPLASH_MAX 700 мс замість 6 с)."""
    url = page.url
    page.add_init_script(MOCK % {'fail': fail, 'delay': DELAY})

    def fix(route):
        r = route.fetch()
        body = r.text()
        a = 'SPLASH_MIN=600,SPLASH_MAX=6000'
        check(body.count(a) == 1, 'константи заставки не знайдено')
        route.fulfill(response=r, body=body.replace(a, 'SPLASH_MIN=600,SPLASH_MAX=700'))
    page.route(url, fix)
    page.reload()
    page.wait_for_selector('.side' if page.viewport_size['width'] >= 1024 else '.tab-bar', timeout=5000)


def demo_no_skel(page):
    check(page.locator('.skel').count() == 0, 'у превʼю без БД видно скелетони')
    check(page.locator('.dv-kpi').count() == 3, 'у превʼю без БД немає KPI Огляду')
    check(page.locator('.ld-err').count() == 0, 'банер помилки без БД')


def _skel_then_data(page, name, kpi_sel):
    _with_mock(page)
    page.wait_for_selector('.skel', timeout=1000)
    t = page.inner_text('.content')
    check('₴' not in t, f'під час завантаження на екрані суми: {t[:120]!r}')
    check(page.locator(kpi_sel).count() == 0, 'під час завантаження видно блоки з даними')
    check(page.locator('[role=status][aria-busy=true]').count() == 1, 'скелетон без role=status і aria-busy')
    shot(page, name)
    page.wait_for_selector('.skel', state='detached', timeout=DELAY + 2500)
    check(page.locator(kpi_sel).count() > 0, 'після відповіді не зʼявився вміст')
    check(page.locator('.ld-err').count() == 0, 'банер помилки без помилки')


def skel_desktop(page):
    _skel_then_data(page, 'skeleton-1280.jpg', '.dv-kpi')


def skel_mobile(page):
    _skel_then_data(page, 'skeleton-375.jpg', '.o-hero')


def error_banner(page):
    _with_mock(page, "'credits'")
    page.wait_for_selector('.ld-err', timeout=DELAY + 2500)
    t = page.inner_text('.ld-err')
    check('Не вдалося завантажити розстрочки' in t and 'Повторити' in t, f'текст банера: {t!r}')
    page.locator('.ld-err button', has_text='Повторити').click()
    check(page.locator('.ld-err').count() == 0, 'банер не сховався після «Повторити»')
    page.wait_for_timeout(DELAY + 400)
    calls = page.evaluate('window.__sbMock.calls.credits')
    check(calls == 2, f'«Повторити» не перезапустив запит розстрочок: викликів {calls}')
    check(page.locator('.ld-err').count() == 0, 'банер повернувся після вдалого повтору')


CHECKS = [
    ('Без БД: демо одразу, без скелетонів', 'desktop', demo_no_skel),
    ('З БД: скелетони замість сум, потім вміст (ПК)', 'desktop', skel_desktop),
    ('З БД: скелетони замість сум, потім вміст (телефон)', 'mobile', skel_mobile),
    ('Помилка запиту: банер «Повторити» перезапускає', 'desktop', error_banner),
]
