# Кольори категорій і платежів: палітра CAT_PALETTE, унікальність у списку, контраст маркера від 3:1 в обох темах
from helpers import check, dialog, freeze, go_tab, shot

DAY = '2026-10-08'

# контраст WCAG кольору маркера до --card і --bg поточної теми; кольори з getComputedStyle (rgb або hex)
CONTRAST_JS = r"""(cols)=>{
  const rgb=s=>{s=String(s).trim();if(s[0]==='#'){const v=s.length===4?s.slice(1).split('').map(c=>c+c):[s.slice(1,3),s.slice(3,5),s.slice(5,7)];return v.map(x=>parseInt(x,16))}
    const m=s.match(/[\d.]+/g);return m.slice(0,3).map(Number)};
  const lum=c=>{const v=c.map(x=>{x/=255;return x<=0.04045?x/12.92:Math.pow((x+0.055)/1.055,2.4)});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]};
  const cr=(a,b)=>{const x=lum(rgb(a)),y=lum(rgb(b));return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)};
  const out={};const root=document.documentElement,prev=root.getAttribute('data-theme');
  for(const t of ['light','dark']){root.setAttribute('data-theme',t);const cs=getComputedStyle(root);
    const bgs=[cs.getPropertyValue('--card'),cs.getPropertyValue('--bg')];
    out[t]={bgs:bgs.map(s=>s.trim()),min:Math.min(...cols.flatMap(c=>bgs.map(b=>cr(c,b))))};}
  if(prev)root.setAttribute('data-theme',prev);return out}"""


def _contrast(page, cols, where):
    r = page.evaluate(CONTRAST_JS, cols)
    print(f'      {where}: контраст {", ".join(f"{t} {v["min"]:.2f} (тло {v["bgs"]})" for t, v in r.items())}')
    for t, v in r.items():
        check(v['min'] >= 3, f'{where}: контраст маркера в темі {t} {v["min"]:.2f} < 3')


def payments(page):
    """Вікно «Платежі»: маркер-коло 10px, кольори маркерів без повторів, контраст від 3:1 в обох темах."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY)
    go_tab(page, 3)
    page.click('.dact')
    page.wait_for_timeout(400)
    d = dialog(page, 'Платежі')
    check(d.count() == 1, 'вікно «Платежі» не відкрилось')
    dots = d.locator('.pay-dot').evaluate_all(
        "els=>els.map(e=>{const s=getComputedStyle(e);return{c:s.backgroundColor,w:e.offsetWidth,h:e.offsetHeight,r:s.borderRadius,o:getComputedStyle(e.closest('button')).opacity}})")
    cols = [x['c'] for x in dots]
    print(f'      маркери: {cols}')
    check(len(dots) >= 5, f'у списку платежів мало маркерів: {len(dots)}')
    check(len(set(cols)) == len(cols), f'кольори маркерів повторюються: {cols}')
    check(all(8 <= x['w'] <= 10 and x['w'] == x['h'] and x['r'] == '50%' for x in dots), f'маркер не коло 8-10px: {dots[:2]}')
    check(all(x['o'] == '1' for x in dots), 'рядок платежу приглушений')
    _contrast(page, cols, 'платежі')
    page.mouse.move(2, 2)
    shot(page, 'pay-dialog-1920.jpg', full=False)
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    # Налаштування → Платежі: той самий список, без повторів і без приглушення розстрочок, що ще не почались
    page.locator('.side-item', has_text='Налаштування').click()
    page.wait_for_timeout(400)
    page.get_by_text('Платежі', exact=True).first.click()
    page.wait_for_timeout(400)
    rows = page.locator('.pay-dot').evaluate_all(
        "els=>els.map(e=>({c:getComputedStyle(e).backgroundColor,o:getComputedStyle(e.parentElement).opacity,r:getComputedStyle(e).borderRadius}))")
    print(f'      налаштування: {[(r["c"], r["o"]) for r in rows]}')
    check(len(rows) == len(dots), f'у налаштуваннях {len(rows)} маркерів, у вікні {len(dots)}')
    check([r['c'] for r in rows] == cols, 'кольори в налаштуваннях і у вікні платежів різні')
    check(all(r['o'] == '1' and r['r'] == '50%' for r in rows), f'рядок приглушений або маркер не коло: {rows}')
    page.mouse.move(2, 2)
    shot(page, 'settings-pay-1920.jpg', full=False)


def categories(page):
    """Категорії демо: кольори з палітри без повторів (витрати), Бюджет і Потік у тих самих кольорах, контраст палітри від 3:1."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    # кінець періоду: більшість категорій уже мають витрати
    freeze(page, '2026-10-19')
    pal = page.evaluate('CAT_PALETTE')
    cats = page.evaluate("(()=>{const ex=BCAT.filter(c=>!c.isIncome);const cs=paintColors(ex);return ex.map((c,i)=>({id:c.id,name:c.name,color:cs[i]}))})()")
    cols = [c['color'] for c in cats]
    print(f'      категорії ({len(cats)}): {[c["name"] + " " + c["color"] for c in cats]}')
    check(len(set(cols)) == len(cols), f'кольори категорій повторюються: {cols}')
    check(all(c in pal for c in cols), 'колір категорії поза палітрою')
    _contrast(page, pal, 'палітра')
    # Бюджет: тло значка категорії (колір категорії з прозорістю) і смуга (крім перевитрати й неактивних) у кольорі категорії
    go_tab(page, 1)
    rows = page.locator('.bud-cat').evaluate_all(
        "els=>els.map(e=>{const b=e.querySelector('.bud-bar span');return{n:e.querySelector('.bud-name').textContent.trim(),hot:e.classList.contains('hot'),idle:e.classList.contains('idle'),"
        "ico:getComputedStyle(e.querySelector('.bud-ico')).backgroundColor,bar:b?getComputedStyle(b).backgroundColor:null}})")
    rgb = lambda c: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    num3 = lambda s: tuple(int(float(x)) for x in s.replace('rgba(', '').replace('rgb(', '').replace(')', '').split(',')[:3])
    want = {c['name']: rgb(c['color']) for c in cats}
    seen = 0
    for r in rows:
        if r['idle'] or r['n'] not in want:
            continue
        seen += 1
        check(num3(r['ico']) == want[r['n']], f'значок «{r["n"]}» {r["ico"]}, очікували {want[r["n"]]}')
        if not r['hot']:
            check(num3(r['bar']) == want[r['n']], f'смуга «{r["n"]}» {r["bar"]}, очікували {want[r["n"]]}')
    print(f'      бюджет: перевірено категорій {seen} з {len(rows)}')
    check(seen >= 3, 'на сторінці Бюджету замало активних категорій для перевірки')
    page.mouse.move(2, 2)
    shot(page, 'budget-1920.jpg', full=False)
    # Потік: кружок категорії в рядку операції того ж кольору, що категорія
    go_tab(page, 2)
    fl = page.locator('.flow-cat:not(.none)').evaluate_all(
        "els=>els.map(e=>({n:e.textContent.trim(),c:getComputedStyle(e.querySelector('.flow-dot')).backgroundColor,w:e.querySelector('.flow-dot').offsetWidth}))")
    ok = [f for f in fl if f['n'] in want]
    print(f'      потік: кружків {len(fl)}, з категорією демо {len(ok)}')
    check(len(ok) >= 3, 'у Потоці замало рядків з категорією')
    for f in ok:
        check(num3(f['c']) == want[f['n']] and 8 <= f['w'] <= 10, f'кружок «{f["n"]}» {f["c"]} {f["w"]}px, очікували {want[f["n"]]}')


# Аерогриль починається з листопада, Ланцюжок завершився у вересні
LATE = [("{name:'Аерогриль',amount:683.25,day:17,sy:2026,sm:3,", "{name:'Аерогриль',amount:683.25,day:17,sy:2026,sm:10,"),
        ("{name:'Ланцюжок',amount:3731.88,day:11,sy:2026,sm:3,total:8,", "{name:'Ланцюжок',amount:3731.88,day:11,sy:2026,sm:3,total:6,")]


def settings_dim(page):
    """Налаштування → Платежі: розстрочка, що ще не почалась, не приглушена; завершена приглушена."""
    page.set_viewport_size({'width': 1920, 'height': 900})
    freeze(page, DAY, LATE)
    page.locator('.side-item', has_text='Налаштування').click()
    page.wait_for_timeout(400)
    page.get_by_text('Платежі', exact=True).first.click()
    page.wait_for_timeout(400)
    op = lambda nm: page.locator('.pay-dot').evaluate_all(
        "(els,nm)=>els.filter(e=>e.parentElement.textContent.includes(nm)).map(e=>getComputedStyle(e.parentElement).opacity)", nm)
    a, l = op('Аерогриль'), op('Ланцюжок')
    print(f'      Аерогриль (з листопада) {a}, Ланцюжок (завершено) {l}')
    check(a == ['1'], f'розстрочка, що почнеться пізніше, приглушена: {a}')
    check(l == ['0.5'], f'завершена розстрочка не приглушена: {l}')


CHECKS = [
    ('Кольори: маркери платежів без повторів, коло, контраст', 'desktop', payments),
    ('Кольори: приглушення розстрочок у налаштуваннях лише завершених', 'desktop', settings_dim),
    ('Кольори: категорії демо унікальні, Бюджет і Потік у кольорах категорій', 'desktop', categories),
]
