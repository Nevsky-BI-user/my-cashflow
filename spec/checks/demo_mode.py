# Демо-режим (v181): перемикач у налаштуваннях, вигадані дані в памʼяті замість Supabase.
# Превʼю прибирає supabase-js, тому перевірка повертає тег бібліотеки в index.html і кладе локальну сесію
# (email з ALLOWED_EMAILS сторінки, токен вигаданий), а всі запити до *.supabase.co перехоплює й обриває.
# Увімкнений режим: плашка «Демо», 5 вкладок з демо-даними, жодного запиту до Supabase, запис лише в памʼяті,
# підсумки на Огляді й Бюджеті дорівнюють сумам показаних рядків. Вимкнення перемикачем повертає справжній шлях даних.
import json
import time

from helpers import check, expand_groups, go_tab, num, settle, shot

LIB = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>'
ANCHOR = '<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>'
STORE_KEY = 'sb-lisedsqwdzshsxydghag-auth-token'
# вимкнений режим без бібліотеки: клієнт-замінник записує кожне звернення до даних у window.__sbCalls
FAKE = r"""(()=>{if(window.supabase)return;window.__sbCalls=[];const rec=k=>window.__sbCalls.push(k);
const chain=()=>{let one=false;const p=new Proxy(function(){},{get(t,k){if(k==='then'){const v=one?{data:null,error:null}:{data:[],error:null};return (ok,bad)=>Promise.resolve(v).then(ok,bad)}
if(k==='single'||k==='maybeSingle')return ()=>{one=true;return p};return ()=>p}});return p};
const session={access_token:'demo',user:{id:'00000000-0000-4000-8000-0000000000d1',get email(){return ALLOWED_EMAILS[0]}}};
window.supabase={createClient(){return{auth:{getSession:()=>Promise.resolve({data:{session}}),onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:()=>Promise.resolve({error:null}),signInWithOAuth:()=>Promise.resolve({})},
from:t=>{rec('from:'+t);return chain()},functions:{invoke:n=>{rec('fn:'+n);return Promise.resolve({data:null,error:{message:'off',context:{json:()=>Promise.resolve({})}}})}},
storage:{from:b=>{rec('storage:'+b);return{createSignedUrls:()=>Promise.resolve({data:[],error:null}),createSignedUrl:()=>Promise.resolve({data:null})}}},
channel:n=>{rec('channel:'+n);const c={on:()=>c,subscribe:()=>c};return c},removeChannel:()=>Promise.resolve('ok')}}}})()"""
# рядки демо-даних, які мають бути на вкладках (вигадані назви з demoSeed)
MARKS = {0: ['Ощадбанк', 'monobank'], 1: ['Їжа', 'Транспорт'], 2: ['Аванс'], 3: [], 4: ['Подушка безпеки']}
# Платежі: на телефоні обираємо позначений день і перевіряємо назву платежу в його деталях.
PAYS = ['Пральна машина', 'Ноутбук для навчання', 'Смартфон', 'Оренда квартири', 'Садочок', 'Інтернет', 'Мобільний звʼязок', 'Стрімінги', 'Комунальні', 'Спортзал', 'Страховка авто']


def _setup(page, lib):
    """Маршрут index.html (з бібліотекою або без), перехоплення *.supabase.co; повертає список запитів до Supabase."""
    url = page.url
    state = {'lib': lib}
    hits = []

    def serve(route):
        r = route.fetch()
        body = r.text()
        if state['lib']:
            check(body.count(ANCHOR) == 1, 'немає тегу React для вставки supabase-js')
            body = body.replace(ANCHOR, LIB + '\n' + ANCHOR)
        route.fulfill(response=r, body=body)

    def block(route):
        hits.append(route.request.url)
        route.abort()
    page.route(url, serve)
    page.route('**/*supabase.co/**', block)
    page.on('websocket', lambda ws: hits.append(ws.url) if 'supabase.co' in ws.url else None)
    page.add_init_script(FAKE)
    return state, hits


def _session(page):
    """Локальна сесія для supabase-js: справжній email зі списку сторінки, вигаданий токен, строк дії в майбутньому."""
    page.evaluate("""k=>{const exp=Math.floor(Date.now()/1000)+86400*30;localStorage.setItem(k,JSON.stringify({access_token:'demo.token.local',refresh_token:'demo-refresh',
expires_in:86400*30,expires_at:exp,token_type:'bearer',user:{id:'00000000-0000-4000-8000-0000000000d1',aud:'authenticated',role:'authenticated',email:ALLOWED_EMAILS[0],app_metadata:{},user_metadata:{},created_at:'2026-01-01T00:00:00Z'}}));localStorage.setItem('demo_mode','1')}""", STORE_KEY)


def _load(page):
    sel = '.side' if page.viewport_size['width'] >= 1024 else '.tab-bar'
    page.reload()
    page.wait_for_selector(sel, timeout=20000)
    page.wait_for_function("()=>!document.querySelector('.skel-page')", timeout=15000)
    page.wait_for_timeout(500)
    settle(page)


def _tabs(page, tag):
    for i, marks in MARKS.items():
        go_tab(page, i)
        page.wait_for_timeout(250)
        txt = page.locator('.tab-page').inner_text()
        shot(page, f'demo-{tag}-{i + 1}.jpg', full=False)
        miss = [m for m in marks if m not in txt]
        check(not miss, f'вкладка {i + 1}: немає демо-рядків {miss}')
        if i == 3:
            if page.viewport_size['width'] < 1024:
                days = page.locator('.cm-calendar .cal-cell:has(.cm-count)')
                check(days.count() > 0, 'вкладка 4: немає днів із демо-подіями')
                names = []
                for n in range(days.count()):
                    day = days.nth(n)
                    day.click()
                    page.wait_for_timeout(100)
                    check('sel' in (day.get_attribute('class') or '').split(), 'натискання дня не змінило вибір календаря')
                    detail = page.locator('.cm-details').inner_text()
                    names = [m for m in PAYS if m in detail]
                    if names:
                        break
                check(names, 'вкладка 4: позначені дні не показують демо-платежів у деталях')
                shot(page, f'demo-{tag}-{i + 1}.jpg', full=False)
            else:
                names = [m for m in PAYS if m in txt]
                check(len(names) >= 3 or (names and txt.count('•') >= 5), f'вкладка 4: немає демо-платежів ({names}, {txt.count("•")} позначок подій)')
        check(page.locator('.skel-page').count() == 0, f'вкладка {i + 1}: скелетон замість даних')


def _budget_sums(page):
    """Бюджет: факт у KPI = сума фактів показаних рядків категорій (групи розгорнуто)."""
    go_tab(page, 1)
    expand_groups(page)
    page.wait_for_timeout(200)
    kpi = num(page.locator('.bud-spent .bud-kpi-v').first.inner_text())
    vals = [num(t) for t in page.locator('.bud-cat .bud-value[data-label="Факт"]').all_inner_texts()]
    s = round(sum(vals), 2)
    print(f'      Бюджет: факт KPI {kpi} = сума {len(vals)} рядків категорій {s}')
    check(vals and abs(kpi - s) < 0.01, f'Бюджет: KPI факт {kpi} не дорівнює сумі рядків {s}')
    return kpi, s


def _overview_sums(page):
    """Огляд (ПК): «Баланс» = «Власні» + «Мінусові»; «Власні» = сума власних рахунків, «Мінусові» = борг кредитних карток з карток рахунків."""
    go_tab(page, 0)
    t = page.locator('.kpi-balance')
    check(t.count() == 1, 'немає плитки «Баланс»')
    bal = num(t.locator('.dv-kpi-v').inner_text())
    own = num(t.locator('[data-r=own] .kpi-rv').inner_text())
    minus = num(t.locator('[data-r=minus] .kpi-rv').inner_text())
    print(f'      Огляд: Баланс {bal} = власні {own} + мінусові {minus} = {round(own + minus, 2)}')
    check(abs(bal - (own + minus)) <= 1, f'Баланс {bal} не дорівнює власні {own} + мінусові {minus}')
    # звірка з джерелом: рядки рахунків демо-копії (сума власних і борг кредиток)
    accs = page.evaluate("async()=>(await sb.from('accounts').select('*').eq('active',true)).data")
    src_own = round(sum(a['balance'] for a in accs if a['kind'] != 'credit'), 2)
    src_debt = round(sum(a['debt'] for a in accs if a['kind'] == 'credit'), 2)
    print(f'      Огляд: демо-рахунки власні {src_own}, борг {src_debt}')
    check(abs(own - src_own) <= 1 and abs(abs(minus) - src_debt) <= 1, f'Огляд: власні {own} / мінусові {minus} не з рядків рахунків ({src_own} / {src_debt})')
    return bal, own, minus


def _writes(page):
    """Запис у памʼяті: операція і ціль додаються, мережі немає; після перезавантаження демо-дані вихідні."""
    r = page.evaluate("""async()=>{const n0=(await sb.from('transactions').select('id')).data.length;
const ins=await sb.from('transactions').insert({amount:123.45,type:'expense',category_id:1,account_id:903,description:'Перевірка демо',source:'manual',date:pbIso(new Date())}).select().single();
const n1=(await sb.from('transactions').select('id')).data.length;const g=await sb.from('goals').insert({name:'Демо-ціль',target_amount:1000,sort_order:9}).select('id').single();
const gl=(await sb.from('goals').select('*').eq('id',g.data.id)).data;await sb.from('goals').delete().eq('id',g.data.id);const gl2=(await sb.from('goals').select('*').eq('id',g.data.id)).data;
return{n0,n1,id:ins.data&&ins.data.id,err:ins.error,goal:gl.length,goalAfterDelete:gl2.length}}""")
    print(f'      запис у памʼяті: {json.dumps(r, ensure_ascii=False)}')
    check(r['n1'] == r['n0'] + 1 and r['id'] and not r['err'], f'операція не записалась у демо-копію: {r}')
    check(r['goal'] == 1 and r['goalAfterDelete'] == 0, f'ціль не записалась або не видалилась: {r}')
    return r


def _run(page, tag):
    state, hits = _setup(page, True)
    _session(page)
    _load(page)
    badge = page.locator('.demo-badge')
    check(badge.count() == 1 and badge.is_visible(), 'немає плашки «Демо»')
    _tabs(page, tag)
    sums = _budget_sums(page)
    if page.viewport_size['width'] >= 1024:
        _overview_sums(page)
    _writes(page)
    page.wait_for_timeout(300)
    check(not hits, f'запити до Supabase у демо-режимі: {hits[:3]}')
    print(f'      запитів до Supabase у демо: {len(hits)}')
    # вимкнення перемикачем у налаштуваннях: без бібліотеки, клієнт-замінник показує, що дані знову йдуть у клієнт Supabase
    state['lib'] = False
    if page.viewport_size['width'] >= 1024:
        page.keyboard.press('s')
        page.wait_for_timeout(400)
        page.locator('.set-page nav button', has_text='Демо-режим').first.click()
    else:
        go_tab(page, 5)
    page.wait_for_timeout(300)
    sw = page.locator('[role=switch][aria-label="Демо-режим"]')
    check(sw.count() == 1 and sw.get_attribute('aria-checked') == 'true', 'перемикач демо-режиму не увімкнений')
    sel = '.side' if page.viewport_size['width'] >= 1024 else '.tab-bar'
    with page.expect_navigation():
        sw.click()
    page.wait_for_selector(sel, timeout=20000)
    page.wait_for_timeout(800)
    check(page.evaluate("localStorage.getItem('demo_mode')") is None, 'demo_mode лишився в localStorage')
    check(page.locator('.demo-badge').count() == 0, 'плашка «Демо» після вимкнення')
    calls = page.evaluate('window.__sbCalls||[]')
    print(f'      після вимкнення звернень до клієнта Supabase: {len(calls)} ({", ".join(sorted(set(calls))[:4])}...)')
    check(any(c == 'from:transactions' for c in calls), f'після вимкнення дані не йдуть у клієнт Supabase: {calls[:5]}')
    return sums


def desktop(page):
    """ПК: демо-режим, суми Огляду й Бюджету, вимкнення з налаштувань"""
    _run(page, 'desk')


def mobile(page):
    """Телефон: демо-режим, суми Бюджету, вимкнення з налаштувань"""
    _run(page, 'mob')


CHECKS = [
    ('демо-режим ПК', 'desktop', desktop),
    ('демо-режим телефон', 'mobile', mobile),
]
