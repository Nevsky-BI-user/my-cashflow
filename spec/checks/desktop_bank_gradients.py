from io import BytesIO
import re
from PIL import Image
from helpers import check, shot


def luminance(rgb):
    linear = [v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def desktop_gradients(page):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>document.documentElement.setAttribute("data-theme",t)', theme)
        for width in (1280, 1440, 1920):
            page.set_viewport_size({'width': width, 'height': 900})
            page.mouse.move(2, 2)
            page.wait_for_timeout(500)
            cards = page.locator('.dv-cards .bcard')
            check(cards.count() == 3, f'{theme}/{width}: missing bank cards')
            paints = cards.evaluate_all('es=>es.map(e=>getComputedStyle(e).backgroundImage)')
            check(all('gradient' in p for p in paints) and len(set(paints)) == 3,
                  f'{theme}/{width}: banks need distinct gradients: {paints}')
            check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{theme}/{width}: page overflows')
            for card in cards.all():
                check(card.evaluate('e=>e.scrollWidth<=e.clientWidth+1'), f'{theme}/{width}: card contents overflow')
                for text in card.locator('.bcard-bank,.bcard-sum,.bcard-avail,.ms-txt,.ms-warn,.bank-advice').all():
                    if not text.is_visible():
                        continue
                    fg = [float(v) for v in re.findall(r'[\d.]+', text.evaluate('e=>getComputedStyle(e).color'))]
                    alpha = fg[3] if len(fg) > 3 else 1
                    old = text.evaluate('e=>[e,...e.querySelectorAll("*")].map(n=>n.getAttribute("style"))')
                    clip = text.bounding_box()
                    painted = Image.open(BytesIO(page.screenshot(clip=clip))).convert('RGB')
                    # Transparent glyphs leave the real gradient and chip paint intact.
                    text.evaluate('e=>{for(const n of [e,...e.querySelectorAll("*")]){const s=getComputedStyle(n);for(const side of ["top","right","bottom","left"]){n.style.setProperty("border-"+side+"-color",s.getPropertyValue("border-"+side+"-color"),"important")}n.style.setProperty("color","transparent","important");n.style.setProperty("text-shadow","none","important")}}')
                    try:
                        pixels = Image.open(BytesIO(page.screenshot(clip=clip))).convert('RGB')
                    finally:
                        text.evaluate('(e,ss)=>[e,...e.querySelectorAll("*")].forEach((n,i)=>ss[i]===null?n.removeAttribute("style"):n.setAttribute("style",ss[i]))', old)
                    ratios = []
                    # Measure backgrounds beneath glyphs, excluding empty rounded corners.
                    backgrounds = {bg for ink, bg in zip(painted.getdata(), pixels.getdata())
                                   if max(abs(a-b) for a, b in zip(ink, bg)) > 16}
                    check(bool(backgrounds), f'{theme}/{width}: no text pixels measured')
                    for bg in backgrounds:
                        blend = [f * alpha + b * (1-alpha) for f, b in zip(fg[:3], bg)]
                        low, high = sorted((luminance(blend), luminance(bg)))
                        ratios.append((high+.05)/(low+.05))
                    minimum = min(ratios)
                    check(minimum >= 4.5, f'{theme}/{width}/{text.inner_text()}: contrast {minimum:.2f}<4.5')
                    print(f'      {theme}/{width}: {text.inner_text()[:35]} contrast >= {minimum:.2f}')
            shot(page, f'desktop-bank-gradients-{theme}-{width}.jpg', full=False)


CHECKS = [('Desktop bank gradients: readable real pixels, both themes, 1280/1440/1920', 'desktop', desktop_gradients)]
