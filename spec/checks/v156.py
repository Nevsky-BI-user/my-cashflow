"""v156 (власник 13.10 на знімку меню v154: «тут добрий дизайн а на самій сторінці жахливі кольори»; обрав «Індиго всюди»): єдиний акцент
застосунку знову індиго-фіолетовий з v154. Кнопка «+ Операція», смужка активного пункту меню (на телефоні активної вкладки) і основна кнопка
мають один градієнт акценту, саме v154 (три зупинки); активний пункт меню і натиснутий перемикач мають один тон (--tab-grad на --acc-bg) і колір
акценту; посилання «Усі платежі →» кольору акценту."""
from helpers import check, freeze, go_tab, settle

DAY = '2026-10-13'
# v154: зупинки градієнта акценту і колір акценту; у темній на ПК акцент #7c93f5, на телефоні #8b9ff7
STOPS = {'light': ['rgb(59, 91, 219)', 'rgb(103, 65, 217)', 'rgb(156, 54, 181)'],
         'dark': ['rgb(79, 91, 213)', 'rgb(122, 70, 214)', 'rgb(162, 59, 191)']}
ACC = {('light', True): 'rgb(59, 91, 219)', ('light', False): 'rgb(59, 91, 219)',
       ('dark', True): 'rgb(124, 147, 245)', ('dark', False): 'rgb(139, 159, 247)'}

PROBE = r"""()=>{
 const probe=(p,v,e)=>{const d=document.createElement('div');d.style[p]=v;(e?.closest('.p-overview')||document.body).appendChild(d);const c=getComputedStyle(d)[p];d.remove();return c};
 const vis=e=>!!e&&e.getBoundingClientRect().width>0&&getComputedStyle(e).visibility!=='hidden';
 const st=(e,ps)=>{if(!vis(e))return null;const s=getComputedStyle(e,ps||null);return {bi:s.backgroundImage,bg:s.backgroundColor,c:s.color,acc:probe('color','var(--indigo)',e),tab:probe('backgroundImage','var(--tab-grad)',e),accBg:probe('backgroundColor','var(--acc-bg)',e)}};
 const ops=[...document.querySelectorAll('button')].filter(b=>vis(b)&&b.textContent.replace(/\s+/g,' ').trim()==='+ Операція').map(b=>({cls:b.className,...st(b)}));
 const item=document.querySelector('.side-item[aria-current=page],.side-item.on');
 return {acc:probe('color','var(--acc)'),ind:probe('color','var(--indigo)'),grad:probe('backgroundImage','var(--grad-accent)'),tab:probe('backgroundImage','var(--tab-grad)'),
  accBg:probe('backgroundColor','var(--acc-bg)'),ops,item:st(item),itemBar:st(item,'::before'),
  tabBar:st(document.querySelector('.tab-bar .tab-btn[aria-current=page]'),'::before'),
  dact:st([...document.querySelectorAll('.dact')].find(vis)),fab:st(document.querySelector('button.fab')),
  chip:st(document.querySelector('.dv-fc .fc-chips button[aria-pressed=true]')),
  chipOff:st(document.querySelector('.dv-fc .fc-chips button[aria-pressed=false]')),
  link:st(document.querySelector('.dv-all-payments'))}
}"""


def _stops(bi):
    import re
    return re.findall(r'(?:rgba?|color)\([^)]*\)', bi or '')


def one_accent(page):
    desk = page.viewport_size['width'] >= 1024
    tag = 'ПК' if desk else 'телефон'
    freeze(page, DAY)
    for theme in ('light', 'dark'):
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        go_tab(page, 0)
        page.wait_for_timeout(450)
        settle(page)
        r = page.evaluate(PROBE)
        w = f'{tag}/{theme}'
        # токени: акцент v154, усі псевдоніми однакові, градієнт із трьох різних зупинок v154
        check(r['acc'] == ACC[(theme, desk)] and r['ind'] == r['acc'], f'{w}: акцент {r["acc"]} / --indigo {r["ind"]}, а не індиго v154 {ACC[(theme, desk)]}')
        check(_stops(r['grad']) == STOPS[theme] and r['grad'].startswith('linear-gradient(135deg'), f'{w}: градієнт акценту не v154: {r["grad"]}')
        check(len(set(_stops(r['tab']))) == 2, f'{w}: тон активного пункту (--tab-grad) не двоколірний: {r["tab"]}')
        # «+ Операція»: на ПК бічна і верхня (обидві видимі), одним градієнтом акценту; на телефоні кругла кнопка «+» на Потоці (нижче)
        if desk:
            check(len(r['ops']) >= 2, f'{w}: на Огляді не видно бічної і верхньої «+ Операція»: {r["ops"]}')
        for b in r['ops']:
            check(b['bi'] == r['grad'], f'{w}: кнопка «+ Операція» ({b["cls"]}) не градієнтом акценту: {b["bi"]}')
        if desk:
            check(r['item'] and r['itemBar'], f'{w}: немає активного пункту меню')
            check(r['itemBar']['bi'] == r['grad'], f'{w}: смужка активного пункту меню не градієнтом акценту: {r["itemBar"]}')
            check(r['item']['bi'] == r['tab'] and r['item']['bg'] == r['accBg'] and r['item']['c'] == r['acc'], f'{w}: активний пункт меню не тоном акценту: {r["item"]}')
            check(r['link'] and r['link']['c'] == r['link']['acc'], f'{w}: посилання «Усі платежі →» не кольору акценту: {r["link"]}')
        else:
            check(r['tabBar'] and r['tabBar']['bi'] == r['grad'], f'{w}: смужка активної вкладки не градієнтом акценту: {r["tabBar"]}')
        # перемикач діапазону графіка: натиснутий тоном і кольором активного пункту меню, ненатиснутий без тону
        check(r['chip'] and r['chip']['bi'] == r['chip']['tab'] and r['chip']['bg'] == r['chip']['accBg'] and r['chip']['c'] == r['chip']['acc'], f'{w}: натиснутий перемикач графіка не тоном акценту: {r["chip"]}')
        if desk:
            check(all(r['chip'][k] == r['item'][k] for k in ('bi', 'bg', 'c')) if r['chip']['acc'] == r['item']['acc'] else r['chip']['tab'] == 'none', f'{w}: натиснутий перемикач і активний пункт меню різного тону: {r["chip"]} / {r["item"]}')
        check(r['chipOff'] and r['chipOff']['bi'] == 'none' and r['chipOff']['c'] != r['chipOff']['acc'], f'{w}: ненатиснутий перемикач графіка з тоном акценту: {r["chipOff"]}')
        # основна кнопка «Розподіл бюджету» на Бюджеті: той самий градієнт
        go_tab(page, 1)
        page.wait_for_timeout(450)
        b = page.evaluate(PROBE)
        # на ПК кнопка «Розподіл бюджету» в шапці і в картці, на телефоні кругла кнопка тієї ж дії
        pb = b['dact'] if desk else b['fab']
        check(pb and pb['bi'] == r['grad'], f'{w}: основна кнопка Бюджету («Розподіл бюджету») не градієнтом акценту: {pb}')
        if not desk:
            go_tab(page, 2)
            page.wait_for_timeout(450)
            f = page.evaluate(PROBE)
            check(f['fab'] and f['fab']['bi'] == r['grad'], f'{w}: кнопка «+» (додати операцію) на Потоці не градієнтом акценту: {f["fab"]}')
        go_tab(page, 0)
        print(f'      {w}: акцент {r["acc"]}, кнопок «+ Операція» {len(r["ops"])}, градієнт {_stops(r["grad"])}')


CHECKS = [
    ('v156: індиго-акцент v154: «+ Операція», активний пункт меню, перемикач і основна кнопка одним акцентом (ПК)', 'desktop', one_accent),
    ('v156: індиго-акцент v154: «+ Операція», активна вкладка, перемикач і основна кнопка одним акцентом (телефон)', 'mobile', one_accent),
]
