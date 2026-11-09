"""Внутрішні відступи блоків: текст і елементи керування не підходять до краю картки, панелі чи шита ближче за MIN px.

Блок: видимий елемент із фоном, градієнтом або рамкою і заокругленням від 8px, ширина від 120px, висота від 40px
(не кнопка, не поле, не чип). Зміст: прямокутники текстових вузлів і елементів керування всередині блоку.
Відстань рахується від внутрішнього краю рамки до найближчого змісту з кожного боку: зліва і справа від MIN_X,
згори і знизу від MIN_Y (рядок тексту міряється з міжрядковим полем); допуск 1px.
Каруселі й стрічки з горизонтальною прокруткою пропускаються за межами видимої області.
"""
from helpers import check, freeze, go_tab, shot, settle, TABS

DAY = '2026-10-13'
MIN_X = 10
MIN_Y = 8

SCAN = r"""([minX,minY])=>{
 const vis=e=>{const s=getComputedStyle(e);if(s.visibility==='hidden'||s.display==='none'||+s.opacity===0)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
 const hidden=e=>{for(let x=e;x;x=x.parentElement){if(x.inert||x.getAttribute('aria-hidden')==='true')return true;const s=getComputedStyle(x);if(+s.opacity===0||s.visibility==='hidden')return true}return false};
 const painted=s=>{const bg=s.backgroundColor,clear=!bg||bg==='transparent'||/rgba\([^)]*,\s*0\)$/.test(bg);const border=['Top','Right','Bottom','Left'].filter(k=>parseFloat(s['border'+k+'Width'])>0&&!/rgba\([^)]*,\s*0\)$/.test(s['border'+k+'Color'])).length>=3;return !clear||s.backgroundImage!=='none'||border};
 const CTRL='button,input,select,textarea,a,[role=button],[role=switch],[role=radio],[role=tab]';
 const blocks=[...document.querySelectorAll('body *')].filter(e=>{if(e.matches(CTRL+',svg,svg *,img,.tab-bar,.tab-bar *,.side,.side *'))return false;if(!vis(e)||hidden(e))return false;const r=e.getBoundingClientRect(),s=getComputedStyle(e);if(r.width<120||r.height<40)return false;const rad=parseFloat(s.borderTopLeftRadius);if(rad<8||rad>=r.height/2-1)return false;if(r.right<0||r.left>innerWidth)return false;return painted(s)});
 const out=[];
 for(const b of blocks){
  const r=b.getBoundingClientRect(),s=getComputedStyle(b);
  const inner={l:r.left+parseFloat(s.borderLeftWidth),r:r.right-parseFloat(s.borderRightWidth),t:r.top+parseFloat(s.borderTopWidth),b:r.bottom-parseFloat(s.borderBottomWidth)};
  const clip=(q,el)=>{let x={l:q.left,r:q.right,t:q.top,b:q.bottom};for(let a=el;a&&a!==b;a=a.parentElement){const st=getComputedStyle(a);if(st.overflowX!=='visible'||st.overflowY!=='visible'){const c=a.getBoundingClientRect();if(st.overflowX!=='visible'){x.l=Math.max(x.l,c.left);x.r=Math.min(x.r,c.right)}if(st.overflowY!=='visible'){x.t=Math.max(x.t,c.top);x.b=Math.min(x.b,c.bottom)}}}return x.r-x.l>0.5&&x.b-x.t>0.5?{left:x.l,right:x.r,top:x.t,bottom:x.b}:null};
  const rects=[];
  const walker=document.createTreeWalker(b,NodeFilter.SHOW_TEXT);let n;
  while((n=walker.nextNode())){if(!n.textContent.trim())continue;const p=n.parentElement;if(!p||!vis(p)||hidden(p))continue;
   // текст усередині власного елемента керування міряє сам елемент
   const own=p.closest(CTRL);if(own&&own!==b&&b.contains(own)&&own.getBoundingClientRect().width<(inner.r-inner.l)*0.9)continue;
   const g=document.createRange();g.selectNodeContents(n);for(const q0 of g.getClientRects()){const q=q0.width>0&&q0.height>0&&clip(q0,p);if(q)rects.push([q,p])}}
  for(const c of b.querySelectorAll(CTRL)){if(!vis(c)||hidden(c))continue;const q0=c.getBoundingClientRect();if(q0.width>=(inner.r-inner.l)*0.9)continue;const q=clip(q0,c.parentElement);if(q)rects.push([q,c])}
  const scrollX=['auto','scroll'].includes(s.overflowX)&&b.scrollWidth>b.clientWidth+1,scrollY=['auto','scroll'].includes(s.overflowY)&&b.scrollHeight>b.clientHeight+1;
  const side={l:Infinity,r:Infinity,t:Infinity,b:Infinity},who={};
  for(const [q,el] of rects){
   if(scrollX&&(q.left<inner.l||q.right>inner.r))continue;if(scrollY&&(q.top<inner.t||q.bottom>inner.b))continue;
   if(q.bottom<=inner.t||q.top>=inner.b||q.right<=inner.l||q.left>=inner.r)continue;
   const d={l:q.left-inner.l,r:inner.r-q.right,t:q.top-inner.t,b:inner.b-q.bottom};
   for(const k in d)if(d[k]<side[k]){side[k]=d[k];who[k]=(el.className&&el.className.baseVal===undefined?String(el.className):el.tagName)+' «'+(el.innerText||el.value||el.getAttribute('aria-label')||'').trim().slice(0,30)+'»'}
  }
  const bad=Object.keys(side).filter(k=>isFinite(side[k])&&side[k]<(k==='l'||k==='r'?minX:minY)-1);
  if(bad.length)out.push({block:(b.className&&String(b.className))||b.tagName,text:(b.innerText||'').trim().slice(0,40).replace(/\n/g,' / '),w:Math.round(r.width),sides:bad.map(k=>k+' '+Math.round(side[k])+'px '+who[k])});
 }
 return out}"""


def scan(page, where):
    settle(page)
    return [dict(x, where=where) for x in page.evaluate(SCAN, [MIN_X, MIN_Y])]


def _tabs(page, widths, label):
    found = []
    for w in widths:
        page.set_viewport_size({'width': w, 'height': 900 if w >= 1024 else 844})
        page.wait_for_timeout(200)
        for i, (key, _) in enumerate(TABS):
            go_tab(page, i)
            found += scan(page, f'{label} {w} {key}')
    return found


def _report(found):
    lines = [f"{x['where']}: {x['block']} «{x['text']}» ({x['w']}px): " + '; '.join(x['sides']) for x in found]
    for l in lines:
        print('  PADDING', l)
    check(not found, f'{len(found)} блок(ів) з відступом менше {MIN_X}/{MIN_Y}px:\n' + '\n'.join(lines[:40]))


def mobile(page):
    freeze(page, DAY)
    found = _tabs(page, (360, 390), 'mobile')
    # шит переказу і вікно картки
    page.set_viewport_size({'width': 360, 'height': 844})
    go_tab(page, 0)
    page.locator('.account-transfer-open').click()
    page.wait_for_timeout(450)
    found += scan(page, 'mobile 360 transfer')
    shot(page, 'padding-transfer-360.jpg', full=False)
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Закрити', exact=True).last.click()
    page.wait_for_timeout(300)
    page.locator('.o-stack-item[aria-hidden=false] .o-bank-card').click()
    page.wait_for_timeout(450)
    found += scan(page, 'mobile 360 account')
    _report(found)


def desktop(page):
    freeze(page, DAY)
    _report(_tabs(page, (1440, 1920), 'desktop'))


CHECKS = [
    ('Padding: blocks keep inner padding on phone 360/390, tabs, transfer and account sheets', 'mobile', mobile),
    ('Padding: blocks keep inner padding on desktop 1440/1920, all tabs', 'desktop', desktop),
]
