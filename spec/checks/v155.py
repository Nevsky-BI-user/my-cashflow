"""Спільна система: білі картки на liquid glass градієнті, акцент #126e70.
Колір грошей та перевірки фінансової поведінки збережено."""
from helpers import check, freeze, go_tab, settle

# Огляд на ПК: багатошарові поверхні за явними --ov-* токенами.
# Попередні правила пласких карток лишаються для телефона й інших вкладок.

DAY = '2026-10-13'
TABS = [(0, 'Огляд'), (1, 'Бюджет'), (2, 'Потік'), (3, 'Платежі'), (4, 'Цілі')]

# Усі видимі елементи вкладки: градієнти (фон і SVG-заливка url()), плитки зі значком KPI, насичені кольори тексту.
# Дозволено: картки банків (градієнт банку), ілюстрація монети, затемнення під текстом на фото цілі, рівно градієнт і тон акценту (v156);
# «пласкі» градієнти токенів (усі зупинки одного кольору) градієнтом не вважаються.
SCAN = r"""()=>{
 const root=document.documentElement,cs0=getComputedStyle(root),tok=n=>cs0.getPropertyValue(n).trim();
 const palettes=new Map();
 const palette=e=>{
  const scope=e.closest('.p-overview')||e.closest('.shell.overview-active')||document.body;
  if(palettes.has(scope))return palettes.get(scope);
  const probe=(p,v)=>{const d=document.createElement('div');d.style[p]=v;scope.appendChild(d);const c=getComputedStyle(d)[p];d.remove();return c};
  const desktopOverview=matchMedia('(min-width:1024px)').matches&&!!e.closest('.shell.overview-active');
  const p={scope:scope.classList.contains('p-overview')||desktopOverview?'overview':'app',desktopOverview,
   allowedText:new Set(['--acc','--green','--green-t','--red','--red-t','--orange','--orange-t','--warn','--pos','--neg','--yellow','--yellow-t'].map(n=>probe('color','var('+n+')'))),
   chipText:new Set(['--amber-t','--late-t'].map(n=>probe('color','var('+n+')'))),
   card:probe('backgroundColor','var(--card)'),raised:probe('backgroundColor','var(--ov-raised)'),surfaceGradient:probe('backgroundImage','var(--ov-surface-gradient)'),border:probe('borderTopColor','var(--border)'),accent:probe('borderTopColor','var(--acc)'),
   accG:new Set(['--grad-accent','--tab-grad'].map(n=>probe('backgroundImage','var('+n+')')))};
  palettes.set(scope,p);return p;
 };
 const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};
 const skip=e=>e.closest('[class*="bk-"],.bcard,.o-bank-card,.coin');
 const cols=s=>(s.match(/(rgba?|color)\([^)]*\)/g)||[]);
 const flat=bi=>{const c=cols(bi);return c.length>0&&c.every(x=>x===c[0])};
 const sat=c=>{const n=(c.match(/[\d.]+/g)||[]).map(Number);if(c.startsWith('color('))return 0;const [r,g,b,a]=[n[0]/255,n[1]/255,n[2]/255,n.length>3?n[3]:1];const mx=Math.max(r,g,b),mn=Math.min(r,g,b);return a<0.5?0:(mx-mn)};
 const grads=[],tiles=[],texts={};
 for(const e of document.querySelectorAll('body *')){
  if(!vis(e)||skip(e))continue;
  const s=getComputedStyle(e),bi=s.backgroundImage,p=palette(e);
  const authoredSurface=p.desktopOverview&&e.matches('.p-overview.desk .surface')&&bi===p.surfaceGradient;
  /* v183 (власник 22.10: «для всіх таких карток теж додай приємних градієнтів»): KPI Бюджету й плитки Огляду мають тон-градієнт, що сходить у фон картки */
  const kpiTone=e.matches('.bud-kpi,.dv-kpi.kpi-t')&&/^radial-gradient\(/.test(bi)&&s.backgroundColor===p.card;
  if(bi&&bi.includes('gradient')&&!flat(bi)&&!p.accG.has(bi)&&!authoredSurface&&!kpiTone){
   const scrim=/^linear-gradient\(rgba\(0, 0, 0, 0\)/.test(bi);/* затемнення фото цілі під підписом */
   if(!scrim)grads.push((e.getAttribute('class')||e.tagName)+' '+bi.slice(0,90));
  }
  if(/^(path|rect|circle|polygon|ellipse)$/.test(e.tagName)&&/url\(/.test(s.fill))grads.push('svg '+(e.getAttribute('class')||e.tagName)+' '+s.fill);
  if(e.classList.contains('kpi-ico')){
   let t=e.parentElement;while(t&&t!==document.body&&getComputedStyle(t).backgroundColor==='rgba(0, 0, 0, 0)')t=t.parentElement;
   const ts=getComputedStyle(t),funds=p.scope==='overview'&&!matchMedia('(min-width:1024px)').matches&&t.classList.contains('kpi-funds'),expectedBorder=funds?p.accent:p.border;tiles.push({scope:p.scope,role:funds?'funds':'standard',borderOk:ts.borderTopColor===expectedBorder,cls:(t.getAttribute('class')||t.tagName).slice(0,40),bg:ts.backgroundColor,bi:ts.backgroundImage,bd:ts.borderTopWidth+' '+ts.borderTopColor,bdSat:sat(ts.borderTopColor),ok:ts.backgroundColor===p.card&&(ts.backgroundImage==='none'||t.matches('.bud-kpi,.dv-kpi.kpi-t')&&/^radial-gradient\(/.test(ts.backgroundImage))});
  }
  /* текст: лише елементи з власним текстовим вузлом; кільце, легенда, категорії й цілі мають кольори категорій */
  if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&!e.closest('.bd,.bud-cat,.bud-ico,.gtile,.goal-card,[data-cat]')){
   const c=s.color,chipText=e.matches('.chip-due,.chip-due *,.o-bank-due,.o-bank-due *')&&p.chipText.has(c);if(sat(c)>0.35&&!p.allowedText.has(c)&&!chipText){const k=c;(texts[k]=texts[k]||[]).push((e.getAttribute('class')||e.tagName).slice(0,30)+': '+e.textContent.trim().slice(0,20))}
  }
 }
 return {acc:tok('--acc'),grads:[...new Set(grads)].slice(0,12),tiles,texts:Object.fromEntries(Object.entries(texts).map(([k,v])=>[k,[...new Set(v)].slice(0,4)]))};
}"""


def one_system(page):
    desk = page.viewport_size['width'] >= 1024
    tag = 'ПК' if desk else 'телефон'
    freeze(page, DAY)
    for theme in ('light', 'dark'):
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        seen_tiles, borders = 0, {}
        # Три радіальні плями body та прозорий світловий шар ::before.
        bg = page.evaluate(r"()=>{const s=getComputedStyle(document.body,'::before'),b=getComputedStyle(document.body);return {d:s.display,c:s.content,glass:s.backgroundImage,n:(b.backgroundImage.match(/radial-gradient\(/g)||[]).length}}")
        check(bg['d'] != 'none' and bg['c'] != 'none' and bg['n'] == 3 and 'linear-gradient' in bg['glass'], f'{tag}/{theme}: немає liquid glass фону: {bg}')
        for i, name in TABS:
            go_tab(page, i)
            page.mouse.move(2, 2)
            page.wait_for_timeout(450)
            settle(page)
            r = page.evaluate(SCAN)
            w = f'{tag}/{theme}/{name}'
            exp = '#126e70'
            check(r['acc'].lower() == exp, f'{w}: акцент {r["acc"]}, а не спільний бірюзовий {exp}')
            check(not r['grads'], f'{w}: градієнти поза картками банків і акцентом: {r["grads"]}')
            check(all(t['ok'] for t in r['tiles']), f'{w}: KPI-плитка з кольоровою підкладкою або фоном не картки: {[t for t in r["tiles"] if not t["ok"]]}')
            check(not r['texts'], f'{w}: насичений колір тексту без змісту (не акцент, зелений, червоний чи помаранчевий): {r["texts"]}')
            seen_tiles += len(r['tiles'])
            for t in r['tiles']:
                borders.setdefault((t['scope'], t['role']), set()).add(t['bd'])
            check(all(t['borderOk'] and (t['role'] == 'funds' or t['bdSat'] <= 0.15) for t in r['tiles']), f'{w}: KPI-плитка з кольоровою рамкою: {[t for t in r["tiles"] if not t["borderOk"] or (t["role"] != "funds" and t["bdSat"] > 0.15)]}')
        print(f'      {tag}/{theme}: KPI-плиток зі значком {seen_tiles}, градієнтів поза банками 0')
        check(seen_tiles >= 6, f'{tag}/{theme}: замало KPI-плиток для перевірки: {seen_tiles}')
        check(all(len(values) == 1 for values in borders.values()), f'{tag}/{theme}: рамки KPI-плиток різні: {borders}')
        _bank_cards(page, f'{tag}/{theme}', desk)


# v181: на Огляді ПК картки в градієнтах банків; у Налаштуваннях білі без градієнта та відблиску, з кольоровими краями.
BANKS = r"""()=>[...document.querySelectorAll('.bcard[class*=" bk-"]')].filter(e=>e.offsetParent).map(e=>{const s=getComputedStyle(e),b=getComputedStyle(e,'::before');
 const probe=(p,v)=>{const d=document.createElement('div');d.style[p]=v;e.appendChild(d);const c=getComputedStyle(d)[p];d.remove();return c};
 const layered=!!e.closest('.shell.overview-active .p-overview.desk'),bi=s.backgroundImage;return {cls:e.className.split(' ').find(c=>c.startsWith('bk-')),layered,tokenOk:bi==='none'&&s.backgroundColor==='rgb(255, 255, 255)'&&s.borderTopColor===probe('borderTopColor','var(--bank-edge)'),grad:bi.includes('gradient'),edge:s.borderTopColor,bi,head:(bi.match(/^[a-z-]+\([^,]*/)||[''])[0],n:(bi.match(/-gradient\(/g)||[]).length,
 pos:(bi.match(/\d+(\.\d+)?%/g)||[]).map(parseFloat),glare:b.content!=='none'&&b.backgroundImage!=='none'}})"""


def _bank_cards(page, w, desk):
    # Градієнти .bcard: ПК-Огляд і Налаштування → Рахунки; мобільна колода має окремі стилі.
    cards = []
    if desk:
        go_tab(page, 0)
        page.wait_for_timeout(400)
        cards = page.evaluate(BANKS)
        check(len(cards) >= 3, f'{w}: на Огляді замало карток банків: {len(cards)}')
        page.locator('.side-item', has_text='Налаштування').click()
    else:
        go_tab(page, 5)
    page.wait_for_timeout(400)
    page.get_by_text('Рахунки', exact=True).first.click()
    page.wait_for_timeout(400)
    sm = page.evaluate(BANKS)
    check(len(sm) >= 3, f'{w}: у Налаштуваннях → Рахунки замало карток банків: {len(sm)}')
    layered = [c for c in cards if c['layered']]
    if desk:
        check(len(layered) == len(cards) and all(c['grad'] and c['n'] >= 1 for c in layered), f'{w}: desktop Overview bank layers differ from authored tokens: {layered}')
        check(len({c['bi'] for c in layered}) == len({c['cls'] for c in layered}), f'{w}: desktop bank gradients do not identify bank roles: {layered}')
    check(not any(c['layered'] for c in sm), f'{w}: Overview bank layers leaked into Settings')
    cards = sm
    if desk:
        page.keyboard.press('Escape')
    go_tab(page, 0)
    check(all(c['tokenOk'] and c['n'] == 0 for c in cards), f'{w}: картки банків різного типу чи кута градієнта: {[(c["cls"], c["head"], c["n"]) for c in cards]}')
    for c in cards:
        check(not c['pos'], f'{w}: картка {c["cls"]}: жорсткий стоп (позиції {c["pos"]}): {c["bi"]}')
        check(not c['glare'], f'{w}: картка {c["cls"]} з відблиском чи смугою поверх градієнта')
    print(f'      {w}: карток банків {len(cards)}, градієнт {cards[0]["head"] if cards else None}, стопи {cards[0]["pos"] if cards else None}')


CHECKS = [
    ('v155: одна система: бірюзовий акцент, білі картки, liquid glass фон, кольори тексту зі змістом (ПК)', 'desktop', one_system),
    ('v155: одна система: бірюзовий акцент, білі картки, liquid glass фон, кольори тексту зі змістом (телефон)', 'mobile', one_system),
]
