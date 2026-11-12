# v216: курс внеску накопичень, «вкладено» проти поточної оцінки і смуга цілі за валютами.
# Ворота розкладки: сегменти в межах смуги, суміжні, ширини пропорційні оцінці; підписи валют не налазять
# один на одного й не вилазять з плитки; ПК 1440 і 1920, телефон 375.
from helpers import center, check, freeze, go_tab, num, shot, touch_drag

DAY = '2026-10-08'
# Пул: 40 000 ₴ + 300 $ (курс внеску 41,75) + 200 € (без курсу). Поточні курси превʼю: USD 41,2, EUR 44,8 (купівля банком)
SAV = ("{id:'s1',date:'2026-10-01',amount:40000,currency:'UAH',description:'Депозит'},"
       "{id:'s2',date:'2026-10-02',amount:300,currency:'USD',rate:41.75,rate_source:'privat',description:'Долари'},"
       "{id:'s3',date:'2026-10-03',amount:200,currency:'EUR',description:'Євро'}")
PATCH = [
    ('const[savingsLog,setSavingsLog]=useState([]);', 'const[savingsLog,setSavingsLog]=useState([' + SAV + ']);'),
    ('const[rateNbu,setRateNbu]=useState({});', "const[rateNbu,setRateNbu]=useState({USD:{buy:41.5,sale:41.5},EUR:{buy:45.2,sale:45.2}});"),
]
USD_V, EUR_V = 41.2, 44.8
POOL = {'UAH': 40000.0, 'USD': 300 * USD_V, 'EUR': 200 * EUR_V}
TOTAL = sum(POOL.values())
INVESTED = 40000 + 300 * 41.75
NOW_SAME = 40000 + 300 * USD_V

BAR = r"""()=>[...document.querySelectorAll('.gtile')].filter(t=>t.querySelector('.gtile-mix')).map(t=>{
 const r=e=>{const b=e.getBoundingClientRect();return{x:b.left,y:b.top,r:b.right,b:b.bottom,w:b.width,h:b.height}};
 const bar=t.querySelector('.gtile-bar'),mix=t.querySelector('.gtile-mix'),info=t.querySelector('.gtile-info');
 return{tile:r(t),info:r(info),bar:r(bar),mix:r(mix),
  segs:[...mix.children].map(s=>Object.assign(r(s),{ccy:s.dataset.ccy,bg:getComputedStyle(s).backgroundColor})),
  labels:[...t.querySelectorAll('.gtile-ccy-i')].map(l=>Object.assign(r(l),{ccy:l.dataset.ccy,txt:l.innerText.trim()})),
  infoOverflow:info.scrollWidth>info.clientWidth+1,gap:parseFloat(getComputedStyle(mix).columnGap)||0}})"""


def gate_bar(page, tag):
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    tiles = page.evaluate(BAR)
    check(len(tiles) >= 1, f'{tag}: жодна плитка цілі не має смуги за валютами')
    t = tiles[0]
    bar, mix, segs, labels = t['bar'], t['mix'], t['segs'], t['labels']
    check([s['ccy'] for s in segs] == ['UAH', 'USD', 'EUR'], f'{tag}: сегменти {[s["ccy"] for s in segs]}')
    check(len({s['bg'] for s in segs}) == 3, f'{tag}: кольори сегментів не різні {[s["bg"] for s in segs]}')
    # смуга і сегменти: одна висота й top, заповнення від лівого краю смуги, без виходу за смугу
    check(abs(mix['x'] - bar['x']) <= 1 and mix['r'] <= bar['r'] + 1, f'{tag}: заповнення поза смугою {mix} / {bar}')
    for s in segs:
        check(abs(s['y'] - bar['y']) <= 1 and abs(s['h'] - bar['h']) <= 1, f'{tag}: сегмент {s["ccy"]} не на висоті смуги')
    check(abs(segs[0]['x'] - mix['x']) <= 1 and abs(segs[-1]['r'] - mix['r']) <= 1, f'{tag}: сегменти не від краю до краю заповнення')
    for a, b in zip(segs, segs[1:]):
        check(abs(b['x'] - a['r'] - t['gap']) <= 1, f'{tag}: між {a["ccy"]} і {b["ccy"]} проміжок {b["x"] - a["r"]:.1f} замість {t["gap"]}')
    # ширина заповнення = частка цілі; сегменти пропорційні оцінці валют у ₴ (за вирахуванням проміжків)
    goal_pct = round(TOTAL / 240000 * 100)
    check(abs(mix['w'] - bar['w'] * goal_pct / 100) <= 1, f'{tag}: заповнення {mix["w"]:.1f} замість {goal_pct}% від {bar["w"]:.1f}')
    free = mix['w'] - t['gap'] * (len(segs) - 1)
    for s in segs:
        want = free * POOL[s['ccy']] / TOTAL
        check(abs(s['w'] - want) <= 1, f'{tag}: {s["ccy"]} ширина {s["w"]:.1f} замість {want:.1f}')
    # підписи: валюта і сума у валюті, не налазять один на одного, в межах плитки
    check([(l['ccy'], num(l['txt'])) for l in labels] == [('UAH', 40000), ('USD', 300), ('EUR', 200)], f'{tag}: підписи {[l["txt"] for l in labels]}')
    for i, a in enumerate(labels):
        check(a['x'] >= t['info']['x'] - 0.5 and a['r'] <= t['info']['r'] + 0.5, f'{tag}: підпис {a["txt"]} виходить за плитку')
        for b in labels[i + 1:]:
            apart = a['r'] <= b['x'] + 0.5 or b['r'] <= a['x'] + 0.5 or a['b'] <= b['y'] + 0.5 or b['b'] <= a['y'] + 0.5
            check(apart, f'{tag}: підписи {a["txt"]} і {b["txt"]} перекриваються')
    check(labels[0]['y'] >= bar['b'] - 0.5, f'{tag}: підписи не під смугою')
    check(not t['infoOverflow'], f'{tag}: підписи розширюють нижню частину плитки')
    check(t['info']['b'] <= t['tile']['b'] + 1, f'{tag}: нижня частина плитки вилазить за плитку')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{tag}: горизонтальна прокрутка сторінки')


def cost_line(page, root, tag):
    txt = page.locator(root).first.inner_text()
    check('вкладено' in txt, f'{tag}: немає «вкладено»')
    line = page.locator(root + ' .sav-cost').first.inner_text()
    parts = [p for p in line.replace('\n', ' ').split('₴')]
    check(abs(num(parts[0]) - INVESTED) < 0.6, f'{tag}: вкладено {parts[0]!r} замість {INVESTED}')
    check(abs(num(parts[1]) - NOW_SAME) < 0.6, f'{tag}: поточна оцінка {parts[1]!r} замість {NOW_SAME}')
    check('без курсу: 1' in line, f'{tag}: немає лічильника внесків без курсу')
    rates = page.locator(root + ' .sav-rate').all_inner_texts()
    check(len(rates) == 1 and 'за курсом 41,75' in rates[0] and abs(num(rates[0].split('·')[1]) - 300 * 41.75) < 0.6,
          f'{tag}: рядок курсу {rates}')


def desktop(page):
    for w, hgt in ((1440, 900), (1920, 1080)):
        page.set_viewport_size({'width': w, 'height': hgt})
        freeze(page, DAY, patch=PATCH)
        go_tab(page, 4)
        gate_bar(page, f'ПК {w}')
        cost_line(page, '.goals-log', f'ПК {w}')
        shot(page, f'savings-rates-bar-{w}.jpg', full=False)
    # третя поверхня списку: Налаштування, «Накопичення» (ті самі числа)
    page.locator('.dtitle .goals-cfg').click()
    page.wait_for_timeout(400)
    cost_line(page, '.set-page', 'Налаштування')


def mobile(page):
    freeze(page, DAY, patch=PATCH)
    go_tab(page, 4)
    gate_bar(page, 'телефон 375')
    cost_line(page, '.p-goals', 'телефон 375')
    page.locator('.gtile').first.scroll_into_view_if_needed()
    shot(page, 'savings-rates-bar-375.jpg', full=False)


def row_gate(dlg, tag):
    box = dlg.locator('#sav-rate').bounding_box()
    dbox = dlg.bounding_box()
    check(box and dbox, f'{tag}: немає поля курсу')
    check(box['x'] >= dbox['x'] and box['x'] + box['width'] <= dbox['x'] + dbox['width'] + 1, f'{tag}: поле курсу виходить за форму')


def form(page):
    """Форма поповнення: курс вписує користувач (поле порожнє, курси банків лише в підказці), без курсу не зберігається."""
    freeze(page, DAY, patch=PATCH)
    go_tab(page, 4)
    page.locator('.goals-log').get_by_role('button', name='+ Внесок', exact=True).click()
    page.wait_for_timeout(300)
    dlg = page.locator('[role=dialog]').last
    check(dlg.locator('#sav-rate').count() == 0, 'поле курсу для гривні')
    dlg.get_by_role('button', name='$ USD').click()
    rate = dlg.locator('#sav-rate')
    check(rate.input_value() == '', f'курс підставлено сам {rate.input_value()!r}: його вписує користувач')
    check(rate.get_attribute('placeholder') == 'ПриватБанк 41,80 · НБУ 41,50', f'підказка курсів {rate.get_attribute("placeholder")!r}')
    check(dlg.locator('.sav-rate-chip').count() == 0, 'лишились чипи автозаповнення')
    row_gate(dlg, 'ПК 1280')
    dlg.get_by_placeholder('Сума').fill('100')
    dlg.get_by_role('button', name='Зберегти').click()
    page.wait_for_timeout(200)
    check('Вкажіть курс' in dlg.inner_text(), 'порожній курс зберігся без помилки')
    rate.fill('41,5')
    check('Вкажіть курс' not in dlg.inner_text(), 'помилка курсу лишилась після введення')
    check(num(dlg.locator('.sav-rate-cost').inner_text()) == 4150, f'собівартість {dlg.locator(".sav-rate-cost").inner_text()!r}')
    shot(page, 'savings-rates-form-1280.jpg', full=False)
    dlg.get_by_role('button', name='Зберегти').click()
    page.wait_for_timeout(400)
    rows = page.locator('.goals-log .sav-rate').all_inner_texts()
    check(any('за курсом 41,50' in r and num(r.split('·')[1]) == 4150 for r in rows), f'новий внесок без курсу 41,50 у списку: {rows}')


def form_mobile(page):
    """Телефон 375: порожнє поле курсу в межах вікна, без горизонтальної прокрутки."""
    freeze(page, DAY, patch=PATCH)
    go_tab(page, 4)
    # довге натискання FAB: мінішит «Швидке додавання», далі «Поповнення цілі»
    x, y = center(page, 'button.fab')
    touch_drag(page, x, y, x, y, steps=1, hold=650, after=500)
    page.locator('[aria-label="Швидке додавання"] button', has_text='Поповнення цілі').click()
    page.wait_for_timeout(400)
    dlg = page.locator('[role=dialog]').last
    check(dlg.count() == 1, 'на телефоні не відкрилось поповнення')
    dlg.get_by_role('button', name='€ EUR').click()
    row_gate(dlg, 'телефон 375')
    check(dlg.evaluate('e=>e.scrollWidth<=e.clientWidth+1'), 'вікно поповнення ширше за екран')
    check(dlg.locator('#sav-rate').input_value() == '', f'EUR курс підставлено сам {dlg.locator("#sav-rate").input_value()!r}')
    shot(page, 'savings-rates-form-375.jpg', full=False)


# Завантаження курсів із БД: рядки за джерелом, застарілі (12 год+) або неповні кличуть rates-refresh один раз і перечитуються
RMOCK = """(()=>{const st={functions:[],reads:0,rows:%(rows)s,fresh:%(fresh)s};window.__rMock=st;
const account={id:1,name:'Synthetic',bank:'cash',kind:'debit',balance:1000,debt:0,active:true,sort_order:0};
const data={accounts:[account],categories:[],category_groups:[],salary_config:[{id:1,rate:10000,advance_day:21,salary_day:6,split_day:15,savings_pct:20}],fixed_payments:[],credits:[],transactions:[],savings_log:[],goals:[],monthly_budgets:[],profiles:{id:'spec-user',onboarded_at:'2020-01-01',telegram_chat_id:null}};
const q=function(table){const self=new Proxy({},{get:function(_,k){
 if(k==='then')return function(res){if(table==='exchange_rates'){st.reads++;res({data:JSON.parse(JSON.stringify(st.rows)),error:null});return}res({data:data[table]||[],error:null})};
 return function(){return self}}});return self};
window.supabase={createClient:function(){return{from:q,
 channel:function(){return{on:function(){return this},subscribe:function(fn){queueMicrotask(function(){fn('SUBSCRIBED')});return this}}},removeChannel:function(){return Promise.resolve()},
 auth:{getSession:function(){return Promise.resolve({data:{session:{user:{id:'spec-user',email:ALLOWED_EMAILS[0]}}}})},onAuthStateChange:function(){return{data:{subscription:{unsubscribe:function(){}}}}},signOut:function(){return Promise.resolve({})}},
 storage:{from:function(){return{createSignedUrls:function(){return Promise.resolve({data:[]})},createSignedUrl:function(){return Promise.resolve({data:null})}}}},
 functions:{invoke:function(name){st.functions.push(name);if(name==='rates-refresh'){st.rows=st.fresh}return Promise.resolve({data:{ok:true},error:null})}}}}};})();"""


def _rows(at, nbu=True):
    r = [{'ccy': 'USD', 'source': 'privat', 'buy': 45.35, 'sale': 45.95, 'updated_at': at},
         {'ccy': 'EUR', 'source': 'privat', 'buy': 50.45, 'sale': 51.45, 'updated_at': at}]
    if nbu:
        r += [{'ccy': 'USD', 'source': 'nbu', 'buy': 45.3222, 'sale': 45.3222, 'updated_at': at},
              {'ccy': 'EUR', 'source': 'nbu', 'buy': 50.4823, 'sale': 50.4823, 'updated_at': at}]
    return r


def _load(page, rows, fresh):
    import json
    page.add_init_script(RMOCK % {'rows': json.dumps(rows), 'fresh': json.dumps(fresh)})
    page.reload()
    page.wait_for_selector('.side', timeout=15000)
    page.wait_for_function('()=>window.__rMock&&window.__rMock.reads>0', timeout=5000)
    page.wait_for_timeout(600)
    return page.evaluate('({functions:__rMock.functions,reads:__rMock.reads})')


def loader(page):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    iso = lambda d: d.isoformat().replace('+00:00', 'Z')
    # до міграції: рядки без source, квітень; функція повертає свіжі курси обох джерел
    legacy = [{'ccy': 'USD', 'buy': 43.85, 'sale': 44.25, 'updated_at': '2026-04-17T10:00:00Z'}, {'ccy': 'EUR', 'buy': 51.7, 'sale': 52.63, 'updated_at': '2026-04-17T10:00:00Z'}]
    st = _load(page, legacy, _rows(iso(now)))
    check(st['functions'].count('rates-refresh') == 1 and st['reads'] == 2, f'застарілі курси: {st}')
    page.keyboard.press('Digit5')
    page.wait_for_timeout(400)
    page.locator('.dtitle .dact').click()
    page.wait_for_timeout(300)
    dlg = page.locator('[role=dialog]').last
    dlg.get_by_role('button', name='$ USD').click()
    ph = dlg.locator('#sav-rate').get_attribute('placeholder')
    check(ph == 'ПриватБанк 45,95 · НБУ 45,3222', f'підказка після оновлення курсів: {ph!r}')
    check(dlg.locator('#sav-rate').input_value() == '', 'курс підставлено сам після оновлення курсів')


def loader_fresh(page):
    from datetime import datetime, timedelta, timezone
    at = (datetime.now(timezone.utc) - timedelta(hours=11)).isoformat().replace('+00:00', 'Z')
    st = _load(page, _rows(at), _rows(at))
    check(st['functions'].count('rates-refresh') == 0 and st['reads'] == 1, f'свіжі курси (11 год) кличуть оновлення: {st}')


def loader_partial(page):
    from datetime import datetime, timezone
    at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    # свіжий ПриватБанк без НБУ: неповно, одне оновлення; функція не дала НБУ: другого виклику немає
    st = _load(page, _rows(at, nbu=False), _rows(at, nbu=False))
    check(st['functions'].count('rates-refresh') == 1 and st['reads'] == 2, f'неповні курси: {st}')



def _photo_patch():
    """Фікстура фото цілей з goal_photos.py (featured-дошка з фіксованою висотою нижньої частини)."""
    import importlib.util
    from pathlib import Path
    sp = importlib.util.spec_from_file_location('goal_photos_fx', Path(__file__).with_name('goal_photos.py'))
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod.PHOTO_PATCH


INFO_FIT = r"""()=>[...document.querySelectorAll('.gtile-info')].map(e=>({sh:e.scrollHeight,ch:e.clientHeight,sw:e.scrollWidth,cw:e.clientWidth,b:e.getBoundingClientRect().bottom,pb:e.closest('.gtile').getBoundingClientRect().bottom}))"""


def _photos(page, widths, tag):
    freeze(page, DAY, patch=PATCH + _photo_patch())
    go_tab(page, 4)
    for w, hgt in widths:
        page.set_viewport_size({'width': w, 'height': hgt})
        page.wait_for_timeout(500)
        gate_bar(page, f'{tag} {w} фото')
        for i, f in enumerate(page.evaluate(INFO_FIT)):
            check(f['sh'] <= f['ch'] + 1 and f['sw'] <= f['cw'] + 1, f'{tag} {w}: нижня частина плитки {i} з фото переповнена {f}')
            check(f['b'] <= f['pb'] + 1, f'{tag} {w}: нижня частина плитки {i} нижче за плитку')
        page.locator('.gtile').first.scroll_into_view_if_needed()
        shot(page, f'savings-rates-photo-{w}.jpg', full=False)


def photos_desktop(page):
    _photos(page, ((1440, 900), (1920, 1080)), 'ПК')


def photos_mobile(page):
    _photos(page, ((375, 812),), 'телефон')


CHECKS = [
    ('Накопичення: смуга цілі за валютами, вкладено і курс внеску (ПК 1440, 1920)', 'desktop', desktop),
    ('Накопичення: смуга цілі за валютами, вкладено і курс внеску (телефон 375)', 'mobile', mobile),
    ('Накопичення: курс у формі поповнення, НБУ, вручну, запис з курсом', 'desktop', form),
    ('Накопичення: курс у формі поповнення на телефоні 375', 'mobile', form_mobile),
    ('Накопичення: смуга за валютами на дошці з фото (ПК 1440, 1920)', 'desktop', photos_desktop),
    ('Накопичення: смуга за валютами на плитці з фото (телефон 375)', 'mobile', photos_mobile),
    ('Курси: застарілі без джерела, одне оновлення, чипи ПриватБанку й НБУ', 'desktop', loader),
    ('Курси: свіжі за 12 год без оновлення', 'desktop', loader_fresh),
    ('Курси: без НБУ одне оновлення за сесію', 'desktop', loader_partial),
]
