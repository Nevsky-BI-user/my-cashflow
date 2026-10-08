# Доступність: діалоги (role, aria-modal, Tab-трап, повернення фокуса), видимий фокус, контраст підписів і сум (WCAG ≥ 4.5)
from helpers import check, go_tab

OPEN_DLG = "[...document.querySelectorAll('[role=dialog]')].map(d=>({l:d.getAttribute('aria-label'),m:d.getAttribute('aria-modal')}))"
OVERLAYS_OK = "[...document.querySelectorAll('.overlay')].every(o=>o.querySelector('[role=dialog][aria-modal=true][aria-label]'))"
FAB = "()=>{const b=[...document.querySelectorAll('button.fab')];b[b.length-1].click()}"

# контраст із computed styles: колір тексту проти фону, складеного з напівпрозорих шарів предків над --bg
CONTRAST = r"""(sel)=>{const el=typeof sel==='string'?document.querySelector(sel):sel;if(!el)return null;
const P=c=>{const m=c.match(/rgba?\(([^)]+)\)/);if(!m)return null;const p=m[1].split(',').map(Number);return[p[0],p[1],p[2],p.length>3?p[3]:1]};
const root=getComputedStyle(document.documentElement);const hex=v=>{v=v.trim();return[parseInt(v.slice(1,3),16),parseInt(v.slice(3,5),16),parseInt(v.slice(5,7),16),1]};
let layers=[];for(let e=el;e&&e!==document.documentElement;e=e.parentElement){const c=P(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)layers.push(c)}
let bg=hex(root.getPropertyValue('--bg'));for(let i=layers.length-1;i>=0;i--){const c=layers[i],a=c[3];bg=[c[0]*a+bg[0]*(1-a),c[1]*a+bg[1]*(1-a),c[2]*a+bg[2]*(1-a),1]}
let fg=P(getComputedStyle(el).color);const op=parseFloat(getComputedStyle(el).opacity);const a=fg[3]*(isNaN(op)?1:op);fg=[fg[0]*a+bg[0]*(1-a),fg[1]*a+bg[1]*(1-a),fg[2]*a+bg[2]*(1-a)];
const L=c=>{const f=x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
const l1=L(fg),l2=L(bg);return{r:Math.round(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05))*100)/100,fg:getComputedStyle(el).color,t:el.innerText.slice(0,30)}}"""


def dialogs_desktop(page):
    # нова операція (N), налаштування (S), період, тур (?)
    for key, lbl in (('KeyN', 'Нова операція'), ('KeyS', 'Налаштування')):
        page.keyboard.press(key)
        page.wait_for_timeout(300)
        d = page.evaluate(OPEN_DLG)
        check(any(x['l'] == lbl and x['m'] == 'true' for x in d), f'{key}: діалог {lbl} без role/aria-modal: {d}')
        check(page.evaluate(OVERLAYS_OK), f'{key}: оверлей без діалогу з aria-modal і aria-label')
        page.keyboard.press('Escape')
        page.wait_for_timeout(250)
    page.click('.side-pname')
    page.wait_for_timeout(300)
    check(page.evaluate(OVERLAYS_OK), 'вибір періоду: оверлей без діалогу з aria-modal і aria-label')
    page.keyboard.press('Escape')
    page.wait_for_timeout(250)
    # дровер операції в Потоці
    go_tab(page, 2)
    page.locator('.flow-row.tx').first.click()
    page.wait_for_timeout(300)
    d = page.evaluate(OPEN_DLG)
    check(any(x['l'] == 'Операція' and x['m'] == 'true' for x in d), f'дровер без aria-modal: {d}')


def focus_return(page):
    btn = page.locator('.side-add')
    btn.click()
    page.wait_for_timeout(300)
    inside = page.evaluate("!!document.activeElement.closest('[role=dialog]')")
    check(inside, 'після відкриття фокус не в діалозі')
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    check(page.locator('[role=dialog]').count() == 0, 'Esc не закрив форму')
    check(page.evaluate("document.activeElement.classList.contains('side-add')"), 'фокус не повернувся на «+ Операція» після Esc')


def tab_trap_mobile(page):
    go_tab(page, 2)
    page.evaluate(FAB)
    page.wait_for_timeout(400)
    check(page.locator('[role=dialog][aria-label="Нова операція"]').count() == 1, 'шит нової операції не відкрився')
    out = []
    for i in range(30):
        page.keyboard.press('Shift+Tab' if i % 7 == 6 else 'Tab')
        if not page.evaluate("!!document.activeElement.closest('[role=dialog][aria-label=\"Нова операція\"]')"):
            out.append(page.evaluate("document.activeElement.tagName+'.'+document.activeElement.className"))
    check(not out, f'Tab вийшов із шита: {out[:3]}')


def focus_visible(page):
    page.locator('.side-item').first.focus()
    page.keyboard.press('Tab')
    st = page.evaluate("(()=>{const e=document.activeElement,s=getComputedStyle(e);return{c:e.className,o:s.outlineStyle,w:s.outlineWidth}})()")
    check('side-item' in st['c'], f'Tab не перейшов на наступний пункт панелі: {st}')
    check(st['o'] == 'solid' and st['w'] == '2px', f'немає видимого контуру фокуса: {st}')


def _pairs(page, items):
    bad, rows = [], []
    for name, sel in items:
        r = page.evaluate(CONTRAST, sel)
        check(r, f'{name}: елемент не знайдено ({sel})')
        rows.append(f'{name} {r["r"]}')
        if r['r'] < 4.5:
            bad.append(f'{name}: {r}')
    print('      контраст: ' + '; '.join(rows))
    check(not bad, 'контраст нижче 4.5: ' + ' | '.join(bad))


def contrast_desktop(page):
    # світла тема (за замовчуванням), ПК: підпис KPI, «через N дн.», баланс після операції
    page.evaluate("document.documentElement.setAttribute('data-theme','light')")
    page.wait_for_timeout(150)
    lbl = page.evaluate_handle("[...document.querySelectorAll('.dv-kpi div')].find(e=>/вільно до виплати/i.test(e.innerText)&&!e.children.length)")
    fut = page.evaluate_handle("[...document.querySelectorAll('.dv-near .dv-ev span span')].find(e=>/^через /.test(e.innerText))")
    _pairs(page, [('підпис KPI', lbl), ('«через N дн.»', fut)])
    go_tab(page, 2)
    _pairs(page, [('баланс після операції', '.flow-bal')])
    go_tab(page, 4)
    sav = page.evaluate_handle("[...document.querySelectorAll('.p-goals.desk *')].find(e=>/₴\\/міс$/.test(e.innerText.trim())&&!e.children.length&&e.style.color==='var(--green-t)')")
    _pairs(page, [('сума зелена в KPI «Відкладаємо»', sav)])


def contrast_mobile(page):
    page.evaluate("document.documentElement.setAttribute('data-theme','light')")
    page.wait_for_timeout(150)
    inc = page.evaluate_handle("[...document.querySelectorAll('.o-strip div')].find(e=>/^\\+/.test(e.innerText)&&!e.children.length)")
    exp = page.evaluate_handle("[...document.querySelectorAll('.o-strip div')].find(e=>/^\\u2212/.test(e.innerText)&&!e.children.length)")
    _pairs(page, [('підпис табки', '.tab-bar .tab-btn:not([aria-current]) span'), ('сума зелена', inc), ('сума червона', exp)])


CHECKS = [
    ('Діалоги ПК: role=dialog, aria-modal, aria-label', 'desktop', dialogs_desktop),
    ('Фокус повертається на ініціатор після Esc', 'desktop', focus_return),
    ('Tab не виходить із відкритого шита', 'mobile', tab_trap_mobile),
    ('Видимий контур фокуса на кнопці панелі', 'desktop', focus_visible),
    ('Контраст підписів на ПК (світла тема) ≥ 4.5', 'desktop', contrast_desktop),
    ('Контраст табки і сум на телефоні (світла тема) ≥ 4.5', 'mobile', contrast_mobile),
]
