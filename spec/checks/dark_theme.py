"""Справжня темна палітра: усі вкладки, форми, системна тема й контраст."""
from helpers import check, freeze, go_tab, settle, shot

DAY = '2026-10-15'

AUDIT = r"""theme=>{
 const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const rgb=s=>{const m=(s.match(/[\d.]+/g)||[]).map(Number);return s.startsWith('color(srgb')?m.map((v,i)=>i<3?v*255:v):m};
 const lum=c=>{const v=c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]};
 const cr=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
 const base=theme==='dark'?[14,23,30]:[240,245,247];
 const bg=e=>{const layers=[];for(let p=e;p;p=p.parentElement){const c=rgb(getComputedStyle(p).backgroundColor);if(c.length>=3)layers.push(c)}let b=base;for(const c of layers.reverse()){const a=c.length>3?c[3]:1;b=c.slice(0,3).map((v,i)=>v*a+b[i]*(1-a))}return b};
 const texts=[...document.querySelectorAll('h1,h2,.dv-kpi-v,.kpi-rv,.kpi-rl,.bud-kpi-v,.dtitle-sub,.fc-sum [data-k],.pd-title,.pd-label,.pd-money,.monthly-category>label,.monthly-free,.set-page h3,.goals-log-a,.kpi-tip')].filter(visible);
 const badText=texts.map(e=>({cls:e.className,text:e.textContent.slice(0,45),ratio:cr(rgb(getComputedStyle(e).color),bg(e))})).filter(x=>x.ratio<4.5);
 const surfaces=[...document.querySelectorAll('.surface,.card-x,.modal,.drawer,.sheet,dialog[open],.set-page')].filter(visible);
 const lightSurfaces=theme==='dark'?surfaces.filter(e=>!e.matches('.bcard')&&lum(bg(e))>.16).map(e=>e.className):[];
 const fields=[...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]),select,textarea')].filter(visible);
 const badFields=fields.map(e=>{const s=getComputedStyle(e),b=bg(e);return {tag:e.tagName,type:e.type,scheme:s.colorScheme,text:cr(rgb(s.color),b),border:cr(rgb(s.borderTopColor),b),placeholder:e.placeholder?cr(rgb(getComputedStyle(e,'::placeholder').color),b):null}}).filter(x=>x.scheme!==theme||x.text<4.5||(theme==='dark'&&x.border<3)||(theme==='dark'&&x.placeholder!==null&&x.placeholder<4.5));
 return {badText,lightSurfaces,badFields,fields:fields.length,surfaces:surfaces.length,scheme:getComputedStyle(document.documentElement).colorScheme,card:getComputedStyle(document.documentElement).getPropertyValue('--card').trim(),wide:document.documentElement.scrollWidth,viewport:innerWidth};
}"""


def audit(page, theme, label):
    r = page.evaluate(AUDIT, theme)
    check(r['scheme'] == theme, f'{label}: native scheme {r}')
    check(r['card'] == ('#16222c' if theme == 'dark' else '#fff'), f'{label}: wrong theme surface {r}')
    check(not r['badText'], f'{label}: text contrast below4.5 {r["badText"][:5]}')
    check(not r['lightSurfaces'], f'{label}: light surfaces in dark {r["lightSurfaces"]}')
    check(not r['badFields'], f'{label}: native control contrast/scheme {r["badFields"][:5]}')
    check(r['wide'] <= r['viewport'], f'{label}: horizontal clipping {r}')
    return r


def navigate(page, tab):
    if tab == 5 and page.viewport_size['width'] >= 1024:
        page.locator('.side-item', has_text='Налаштування').click()
        page.locator('.set-page').wait_for()
    else:
        go_tab(page, tab)


def choose(page, theme):
    navigate(page, 5)
    if page.viewport_size['width'] >= 1024:
        page.locator('.set-page nav button', has_text='Тема').click()
    page.get_by_role('button', name='Темна' if theme == 'dark' else 'Світла', exact=True).click()
    check(page.evaluate('localStorage.getItem("theme")') == theme, 'settings did not persist selected theme')
    freeze(page, DAY)
    page.wait_for_function('(t)=>document.documentElement.dataset.theme===t', arg=theme)


def screens(page):
    mobile = page.viewport_size['width'] < 1024
    widths = [(390, 844)] if mobile else [(1280, 720), (1920, 1080)]
    for width, height in widths:
        page.set_viewport_size(dict(width=width, height=height))
        bank = None
        for theme in ('light', 'dark'):
            choose(page, theme)
            meta = page.locator('meta[name=theme-color]').get_attribute('content')
            check(meta == ('#0e171e' if theme == 'dark' else '#f4f5fb'), f'theme chrome {theme}: {meta}')
            cards = page.locator('.dv-cards .bcard' if not mobile else '.o-bank-card').evaluate_all('els=>els.map(e=>getComputedStyle(e).backgroundImage)')
            check(cards and all('gradient' in c for c in cards), 'bank gradients missing')
            if bank is not None:
                check(cards == bank, 'theme changed bank gradient stops')
            bank = cards
            for tab in range(6):
                navigate(page, tab)
                audit(page, theme, f'{theme}/{width}/tab{tab}')
            go_tab(page, 0)
            shot(page, f'dark-theme-{theme}-{width}.jpg', full=False)
            page.locator('.pd-trigger:visible').click()
            page.locator('.pd-dialog[open]').wait_for()
            audit(page, theme, 'payout')
            shot(page, f'dark-theme-payout-{theme}-{width}.jpg', full=False)
            page.locator('.pd-dialog[open] .pd-close').click()
            page.locator('.kpi-funds .kpi-i:visible').click()
            audit(page, theme, 'funds tooltip')
            page.keyboard.press('Escape')
            go_tab(page, 1)
            page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
            page.locator('.monthly-editor').wait_for()
            check(audit(page, theme, 'monthly editor')['fields'] > 1, 'monthly controls not inspected')
            page.get_by_role('button', name='Закрити', exact=True).last.click()
            go_tab(page, 2)
            if mobile:
                page.locator('button.fab:visible').last.click()
            else:
                page.locator('.side-add').click()
            page.locator('.tx-sheet').wait_for()
            check(audit(page, theme, 'transaction')['fields'] >= 3, 'transaction fields not inspected')
            shot(page, f'dark-theme-transaction-{theme}-{width}.jpg', full=False)
            page.keyboard.press('Escape')
            go_tab(page, 3)
            page.locator('button.fab:visible' if mobile else '.dtitle .dact').last.click()
            payment = page.get_by_role('dialog', name='Платежі', exact=True)
            payment.wait_for()
            audit(page, theme, 'payments')
            payment.get_by_role('button', name='Закрити', exact=True).first.click()
            go_tab(page, 4)
            if mobile:
                page.locator('button.fab:visible').last.click()
            else:
                page.locator('.goals-log').get_by_role('button', name='+ Внесок', exact=True).click()
            page.get_by_role('dialog', name='Поповнення', exact=True).wait_for()
            check(audit(page, theme, 'savings')['fields'] >= 3, 'savings fields not inspected')
            page.keyboard.press('Escape')


def system_theme(page):
    page.emulate_media(color_scheme='dark')
    navigate(page, 5)
    page.locator('.set-page nav button', has_text='Тема').click()
    page.get_by_role('button', name='Авто', exact=True).click()
    freeze(page, DAY)
    for theme in ('dark', 'light', 'dark'):
        page.emulate_media(color_scheme=theme)
        page.wait_for_function('(t)=>document.documentElement.dataset.theme===t', arg=theme)
        settle(page)
        audit(page, theme, 'system theme')
        check(page.locator('meta[name=theme-color]').get_attribute('content') == ('#0e171e' if theme == 'dark' else '#f4f5fb'), 'auto chrome stale')
    page.reload()
    page.wait_for_selector('.side')
    check(page.evaluate('localStorage.getItem("theme")') == 'auto', 'auto preference lost')
    audit(page, 'dark', 'auto persisted')


CHECKS = [
    ('Dark theme: all pages and financial dialogs1280/1920, contrast and native controls', 'desktop', screens),
    ('Dark theme: all pages and financial dialogs390, contrast and native controls', 'mobile', screens),
    ('Dark theme: automatic system changes and persistence', 'desktop', system_theme),
]
