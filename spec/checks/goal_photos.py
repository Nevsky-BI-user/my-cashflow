"""Фото цілей: природні пропорції на всю ширину й компактний текст під фото."""
import base64
import json

from helpers import check, freeze, go_tab, settle, shot


def _photos():
    urls = {}
    for i, (width, height, color) in enumerate(((1600, 900, '#537e6c'), (1500, 900, '#71899b'), (1800, 1000, '#ae8962'))):
        # Рамка по краях допомагає візуально помітити будь-яке обрізання тестового фото.
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><path fill="{color}" d="M0 0h{width}v{height}H0z"/><path fill="#23414c" d="M0 {height}L{width/3} 0 {width} {height}Z"/><rect x="8" y="8" width="{width-16}" height="{height-16}" rx="20" fill="none" stroke="#f9e4a4" stroke-width="16"/></svg>'
        urls['photo-proof-' + str(i)] = 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
    return urls


PHOTO_PATCH = [(
    'const[dbGoals,setDbGoals]=useState(null);const[goalUrls,setGoalUrls]=useState({});',
    'const[dbGoals,setDbGoals]=useState(function(){return GOALS.map(function(g,i){return Object.assign({},g,{image:"photo-proof-"+i})})});const[goalUrls,setGoalUrls]=useState(' + json.dumps(_photos()) + ');',
)]


PHOTO_GEOMETRY = r"""e=>{
 const img=e.querySelector('img'),body=e.querySelector('.gtile-info'),media=e.querySelector('.gtile-media'),s=getComputedStyle(e),r=e.getBoundingClientRect();
 const rect=x=>{const b=x.getBoundingClientRect();return{top:b.top,bottom:b.bottom,left:b.left,right:b.right,width:b.width,height:b.height}};
 return {card:rect(e),borders:parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth),
 img:img?{...rect(img),naturalWidth:img.naturalWidth,naturalHeight:img.naturalHeight,fit:getComputedStyle(img).objectFit,alt:img.alt}:null,
 media:media?rect(media):img?rect(img):null,
 body:body?{...rect(body),position:getComputedStyle(body).position,text:body.innerText}:null};
}"""


def _check(page, widths):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        freeze(page, '2026-10-26', PHOTO_PATCH)
        page.unroute(page.url)
        go_tab(page, 4)
        for width, height in widths:
            page.set_viewport_size({'width': width, 'height': height})
            settle(page)
            cards = page.locator('.gtile[data-gid]')
            check(cards.count() == 3, f'{theme}/{width}: фікстура не має трьох цілей')
            check(cards.locator('img').count() == 3, f'{theme}/{width}: фото не є повними зображеннями img')
            for img in cards.locator('img').all():
                img.evaluate('e=>e.decode()')
            if width >= 1024:
                # ResizeObserver має завершити саме розрахунок пропорцій; не чекаємо
                # довільного зникнення переповнення, яке перевіряється нижче.
                page.wait_for_function(r"""()=>{
                  const b=document.querySelector('.board-featured');if(!b)return false;
                  const cards=[...b.querySelectorAll(':scope>.gtile')],imgs=cards.map(e=>e.querySelector('img'));
                  if(cards.length!==3||imgs.some(i=>!i?.naturalWidth))return false;
                  const ratio=Math.min(...imgs.slice(1).map(i=>i.naturalWidth/i.naturalHeight));
                  const expected=imgs[1].getBoundingClientRect().width/ratio;
                  return Math.abs(parseFloat(getComputedStyle(b).getPropertyValue('--goal-media'))-expected)<.2;
                }""")
                settle(page)
            geometry = []
            for i, card in enumerate(cards.all()):
                tag = f'{theme}/{width}/ціль {i+1}'
                if width < 1024:
                    card.scroll_into_view_if_needed()
                d = card.evaluate(PHOTO_GEOMETRY)
                image, body, outer, media = d['img'], d['body'], d['card'], d['media']
                check(image and image['naturalWidth'] > 0 and image['naturalHeight'] > 0, f'{tag}: фото не завантажене: {d}')
                natural_ratio = image['naturalWidth'] / image['naturalHeight']
                check(abs(image['width'] / image['height'] - natural_ratio) <= .01, f'{tag}: змінено природні пропорції фото: {d}')
                check(image['fit'] != 'cover', f'{tag}: фото знову обрізається через cover: {d}')
                check(abs(image['width'] - (outer['width'] - d['borders'])) <= 2, f'{tag}: фото не на всю ширину картки: {d}')
                check(image['left'] >= outer['left'] and image['right'] <= outer['right'] + 1 and image['top'] >= outer['top'] and image['bottom'] <= outer['bottom'], f'{tag}: фото обрізане карткою: {d}')
                check(image['alt'].strip(), f'{tag}: фото без текстового опису')
                check(body and body['position'] not in ('absolute', 'fixed'), f'{tag}: підпис поза звичайним потоком: {d}')
                check(media and media['top'] <= image['top'] + 1 and media['bottom'] >= image['bottom'] - 1, f'{tag}: фото обрізане фотоблоком: {d}')
                check(-1 <= body['top'] - media['bottom'] <= 4, f'{tag}: порожній простір або перекриття між фотоблоком і підписом: {d}')
                check(media['height'] - image['height'] <= 40, f'{tag}: навколо повного фото надмірний порожній простір: {d}')
                check(body['height'] <= 150 and body['bottom'] <= outer['bottom'] + 1, f'{tag}: надмірний чи обрізаний підпис: {d}')
                check(body['text'].strip() and '%' in body['text'], f'{tag}: загублено назву або прогрес цілі: {d}')
                geometry.append(d)
                if width >= 1024:
                    check(outer['top'] >= 0 and outer['bottom'] <= height + 1, f'{tag}: картка з фото не вмістилася у стандартний екран: {d}')
            if width >= 1024:
                left, upper, lower = [d['card'] for d in geometry]
                check(left['width'] > upper['width'] and abs(upper['width'] - lower['width']) <= 1, f'{theme}/{width}: головна картка не ліворуч або праві колонки різні: {geometry}')
                check(abs(left['top'] - upper['top']) <= 1 and abs(upper['left'] - lower['left']) <= 1 and upper['left'] > left['right'], f'{theme}/{width}: картки не утворюють велику ліву та дві праві: {geometry}')
                check(abs(upper['height'] - lower['height']) <= 1 and abs(left['bottom'] - lower['bottom']) <= 1, f'{theme}/{width}: зовнішні краї карток не вирівняні: {geometry}')
                check(lower['top'] >= upper['bottom'] + 1, f'{theme}/{width}: праві картки перекриваються: {geometry}')
                check(page.evaluate("document.documentElement.scrollHeight<=innerHeight+1&&[...document.querySelectorAll('.p-goals,.goals-main,.board-d,.gtile')].filter(e=>e.offsetParent).every(e=>e.scrollHeight<=e.clientHeight+1&&e.scrollWidth<=e.clientWidth+1)"), f'{theme}/{width}: заощадження потребують прокрутки')
            check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{theme}/{width}: горизонтальне переповнення')
            page.evaluate('window.scrollTo(0,0)')
            shot(page, f'goal-photos-{theme}-{width}.jpg', full=width < 1024)


def desktop(page):
    _check(page, ((2048, 1000), (1280, 800)))


def mobile(page):
    _check(page, ((390, 844),))


def edited_caption(page):
 page.set_viewport_size({'width':1280,'height':720})
 freeze(page,'2026-10-26',PHOTO_PATCH);go_tab(page,4)
 for img in page.locator('.gtile img').all(): img.evaluate('e=>e.decode()')
 page.wait_for_timeout(500)
 page.locator('.gtile[data-gid]').nth(1).click()
 form=page.locator('[role=dialog]').last
 form.get_by_role('textbox',name='Назва',exact=True).fill('Сімейний автомобіль для подорожей Україною')
 form.get_by_role('textbox',name='Опис',exact=True).fill('Надійний автомобіль для спільних поїздок та щоденних сімейних потреб')
 form.get_by_role('button',name='Зберегти',exact=True).click()
 form.wait_for(state='hidden');page.wait_for_timeout(500);settle(page)
 data=page.locator('.gtile-info').evaluate_all('es=>es.map(e=>({h:e.clientHeight,sh:e.scrollHeight,txt:e.innerText,bottom:e.getBoundingClientRect().bottom,parentBottom:e.parentElement.getBoundingClientRect().bottom}))')
 check(all(e['sh']<=e['h']+1 and e['bottom']<=e['parentBottom']+1 for e in data),'Edited goal caption overflows')

CHECKS = [
    ('Goal photos: edited caption stays fully visible', 'desktop', edited_caption),
    ('Goal photos: full natural image and compact caption desktop', 'desktop', desktop),
    ('Goal photos: full natural image and compact caption mobile', 'mobile', mobile),
]
