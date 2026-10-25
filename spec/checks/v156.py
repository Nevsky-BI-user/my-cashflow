"""Ролі акценту: бірюзові посилання й активні елементи, темні кнопки з білим текстом.
Світла палітра та точні зупинки градієнта збережені; темна має яскравіший колір текстових акцентів."""
import re

from helpers import check, freeze, go_tab, settle
from checks.a11y import CONTRAST

DAY = '2026-10-13'
# Градієнт кнопок спільний; текстовий акцент темної теми світліший за заливку кнопок.
STOPS = {theme: ['rgb(18, 110, 112)', 'rgb(33, 119, 122)'] for theme in ('light', 'dark')}
ACC = {(theme, desktop): ('rgb(18, 110, 112)' if theme == 'light' else 'rgb(112, 207, 202)') for theme in ('light', 'dark') for desktop in (True, False)}
SOLID = 'rgb(18, 110, 112)'

PROBE = r"""()=>{
 const probe=(p,v,e)=>{const d=document.createElement('div');d.style[p]=v;(e?.closest('.p-overview')||e?.closest('.shell.overview-active')||document.body).appendChild(d);const c=getComputedStyle(d)[p];d.remove();return c};
 const vis=e=>!!e&&e.getBoundingClientRect().width>0&&getComputedStyle(e).visibility!=='hidden';
 const st=(e,ps)=>{if(!vis(e))return null;const s=getComputedStyle(e,ps||null);return {bi:s.backgroundImage,bg:s.backgroundColor,c:s.color,acc:probe('color','var(--indigo)',e),solid:probe('backgroundColor','var(--acc-solid)',e),onAccent:probe('color','var(--on-accent)',e),tab:probe('backgroundImage','var(--tab-grad)',e),accBg:probe('backgroundColor','var(--acc-bg)',e)}};
 const ops=[...document.querySelectorAll('button')].filter(b=>vis(b)&&b.textContent.replace(/\s+/g,' ').trim()==='+ Операція').map(b=>({cls:b.className,...st(b)}));
 const item=document.querySelector('.side-item[aria-current=page],.side-item.on');
 return {acc:probe('color','var(--acc)'),ind:probe('color','var(--indigo)'),grad:probe('backgroundImage','var(--grad-accent)'),tab:probe('backgroundImage','var(--tab-grad)'),
  accBg:probe('backgroundColor','var(--acc-bg)'),ops,item:st(item),itemBar:st(item,'::before'),
  tabBar:st(document.querySelector('.tab-bar .tab-btn[aria-current=page]'),'::before'),
  dact:st([...document.querySelectorAll('.dact')].find(vis)),fab:st(document.querySelector('button.fab')),allocation:st(document.querySelector('.budget-mobile-head button')),
  chip:st(document.querySelector('.dv-fc .fc-chips button[aria-pressed=true]')),
  chipOff:st(document.querySelector('.dv-fc .fc-chips button[aria-pressed=false]')),
  link:st(document.querySelector('.dv-all-payments'))}
}"""


def _stops(bi):
    import re
    return re.findall(r'(?:rgba?|color)\([^)]*\)', bi or '')


def _button_contrast(style, where):
    """Білий текст перевіряємо проти реальної заливки, включно з обома краями градієнта."""
    def luminance(color):
        rgb = [float(v) / 255 for v in re.findall(r'[\d.]+', color)[:3]]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))

    check(style['c'] == 'rgb(255, 255, 255)', f'{where}: primary action text must remain white: {style}')
    backgrounds = _stops(style['bi']) if style['bi'] != 'none' else [style['bg']]
    check(backgrounds, f'{where}: primary action has no painted background')
    foreground = luminance(style['c'])
    ratios = [(max(foreground, luminance(bg)) + .05) / (min(foreground, luminance(bg)) + .05) for bg in backgrounds]
    check(min(ratios) >= 4.5, f'{where}: primary action contrast below 4.5: {ratios}')


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
        # Точний акцент теми, узгоджені псевдоніми й незмінні зупинки градієнта кнопок.
        check(r['acc'] == ACC[(theme, desk)] and r['ind'] == r['acc'], f'{w}: акцент {r["acc"]} / --indigo {r["ind"]}, а не індиго v154 {ACC[(theme, desk)]}')
        check(_stops(r['grad']) == STOPS[theme] and r['grad'].startswith('linear-gradient(135deg'), f'{w}: градієнт акценту не v154: {r["grad"]}')
        check(r['tab'] == 'none', f'{w}: активний пункт має бути пласким на спільному --acc-bg: {r["tab"]}')
        # «+ Операція»: на ПК бічна і верхня (обидві видимі), одним градієнтом акценту; на телефоні кругла кнопка «+» на Потоці (нижче)
        if desk:
            check(len(r['ops']) >= 2, f'{w}: на Огляді не видно бічної і верхньої «+ Операція»: {r["ops"]}')
        for b in r['ops']:
            check((b['bi'] == r['grad'] if r['grad'] != 'none' else b['bi'] == 'none' and b['bg'] == b['solid']) and b['c'] == b['onAccent'], f'{w}: operation button differs from its accent role: {b}')
            _button_contrast(b, f'{w}/operation')
        if desk:
            check(r['item'] and r['itemBar'], f'{w}: немає активного пункту меню')
            check(page.locator('.side-item.on').evaluate("e=>getComputedStyle(e).boxShadow.includes('inset')"), f'{w}: active navigation has no inset accent')
            check(r['item']['bi'] == 'none' and r['item']['bg'] == r['item']['accBg'] and r['item']['c'] == r['item']['acc'], f'{w}: active navigation differs from its accent role: {r["item"]}')
            check(r['link'] and r['link']['c'] == r['link']['acc'], f'{w}: посилання «Усі платежі →» не кольору акценту: {r["link"]}')
            for selector in ('.side-item[aria-current=page]', '.dv-all-payments'):
                contrast = page.locator(selector).first.evaluate('(e,fn)=>eval(fn)(e)', CONTRAST)
                check(contrast['r'] >= 4.5, f'{w}/{selector}: accent text contrast below 4.5: {contrast}')
        else:
            check(r['tabBar'] and r['tabBar']['bi'] == r['grad'], f'{w}: смужка активної вкладки не градієнтом акценту: {r["tabBar"]}')
            contrast = page.locator('.tab-btn[aria-current=page] span').first.evaluate('(e,fn)=>eval(fn)(e)', CONTRAST)
            check(contrast['r'] >= 4.5, f'{w}: active tab text contrast below 4.5: {contrast}')
        # перемикач діапазону графіка: натиснутий тоном і кольором активного пункту меню, ненатиснутий без тону
        check(r['chip'] and r['chip']['bi'] == r['chip']['tab'] and r['chip']['bg'] == r['chip']['accBg'] and r['chip']['c'] == r['chip']['acc'], f'{w}: натиснутий перемикач графіка не тоном акценту: {r["chip"]}')
        if desk:
            check(all(r['chip'][k] == r['item'][k] for k in ('bi', 'bg', 'c')) if r['chip']['acc'] == r['item']['acc'] else r['chip']['tab'] == 'none', f'{w}: натиснутий перемикач і активний пункт меню різного тону: {r["chip"]} / {r["item"]}')
        check(r['chipOff'] and r['chipOff']['bi'] == 'none' and r['chipOff']['c'] != r['chipOff']['acc'], f'{w}: ненатиснутий перемикач графіка з тоном акценту: {r["chipOff"]}')
        # На ПК градієнт шапки, на телефоні — єдина верхня кнопка кольору акценту.
        go_tab(page, 1)
        page.wait_for_timeout(450)
        b = page.evaluate(PROBE)
        pb = b['dact'] if desk else b['allocation']
        check(pb and (pb['bi'] == r['grad'] if desk else pb['bi'] == 'none' and pb['solid'] == SOLID and pb['bg'] == pb['solid'] and pb['c'] == pb['onAccent']), f'{w}: основна кнопка Бюджету не відповідає акценту: {pb}')
        _button_contrast(pb, f'{w}/budget')
        if not desk:
            check(b['fab'] is None and page.get_by_role('button',name='Розподіл бюджету',exact=True).count()==1,'мобільний розподіл дублюється поза шапкою')
        if not desk:
            go_tab(page, 2)
            page.wait_for_timeout(450)
            f = page.evaluate(PROBE)
            check(f['fab'] and f['fab']['bi'] == r['grad'], f'{w}: кнопка «+» (додати операцію) на Потоці не градієнтом акценту: {f["fab"]}')
            _button_contrast(f['fab'], f'{w}/flow-add')
        go_tab(page, 0)
        print(f'      {w}: акцент {r["acc"]}, кнопок «+ Операція» {len(r["ops"])}, градієнт {_stops(r["grad"])}')


CHECKS = [
    ('v156: індиго-акцент v154: «+ Операція», активний пункт меню, перемикач і основна кнопка одним акцентом (ПК)', 'desktop', one_accent),
    ('v156: індиго-акцент v154: «+ Операція», активна вкладка, перемикач і основна кнопка одним акцентом (телефон)', 'mobile', one_accent),
]
