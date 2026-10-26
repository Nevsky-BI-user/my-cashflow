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
 const img=e.querySelector('img'),body=e.querySelector(':scope > div:last-child'),s=getComputedStyle(e),r=e.getBoundingClientRect();
 const rect=x=>{const b=x.getBoundingClientRect();return{top:b.top,bottom:b.bottom,left:b.left,right:b.right,width:b.width,height:b.height}};
 return {card:rect(e),borders:parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth),
 img:img?{...rect(img),naturalWidth:img.naturalWidth,naturalHeight:img.naturalHeight,fit:getComputedStyle(img).objectFit,alt:img.alt}:null,
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
            widths_seen = []
            for i, card in enumerate(cards.all()):
                tag = f'{theme}/{width}/ціль {i+1}'
                if width < 1024:
                    card.scroll_into_view_if_needed()
                d = card.evaluate(PHOTO_GEOMETRY)
                image, body, outer = d['img'], d['body'], d['card']
                check(image and image['naturalWidth'] > 0 and image['naturalHeight'] > 0, f'{tag}: фото не завантажене: {d}')
                natural_ratio = image['naturalWidth'] / image['naturalHeight']
                check(abs(image['width'] / image['height'] - natural_ratio) <= .01, f'{tag}: змінено природні пропорції фото: {d}')
                check(image['fit'] != 'cover', f'{tag}: фото знову обрізається через cover: {d}')
                check(abs(image['width'] - (outer['width'] - d['borders'])) <= 2, f'{tag}: фото не на всю ширину картки: {d}')
                check(image['left'] >= outer['left'] and image['right'] <= outer['right'] + 1 and image['top'] >= outer['top'] and image['bottom'] <= outer['bottom'], f'{tag}: фото обрізане карткою: {d}')
                check(image['alt'].strip(), f'{tag}: фото без текстового опису')
                check(body and body['position'] not in ('absolute', 'fixed'), f'{tag}: підпис поза звичайним потоком: {d}')
                check(-1 <= body['top'] - image['bottom'] <= 4, f'{tag}: порожній простір або перекриття між фото й підписом: {d}')
                check(body['height'] <= 150 and body['bottom'] <= outer['bottom'] + 1, f'{tag}: надмірний чи обрізаний підпис: {d}')
                check(body['text'].strip() and '%' in body['text'], f'{tag}: загублено назву або прогрес цілі: {d}')
                widths_seen.append(outer['width'])
                if width >= 1024:
                    check(outer['top'] >= 0 and outer['bottom'] <= height + 1, f'{tag}: картка з фото не вмістилася у стандартний екран: {d}')
            if width >= 1024:
                check(max(widths_seen) - min(widths_seen) <= 2, f'{theme}/{width}: фото-картки не мають рівних колонок: {widths_seen}')
            check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{theme}/{width}: горизонтальне переповнення')
            page.evaluate('window.scrollTo(0,0)')
            shot(page, f'goal-photos-{theme}-{width}.jpg', full=width < 1024)


def desktop(page):
    _check(page, ((2048, 1000), (1280, 800)))


def mobile(page):
    _check(page, ((390, 844),))


CHECKS = [
    ('Goal photos: full natural image and compact caption desktop', 'desktop', desktop),
    ('Goal photos: full natural image and compact caption mobile', 'mobile', mobile),
]
