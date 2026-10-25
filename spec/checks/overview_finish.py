"""Overview fits the browser viewport and respects motion preferences."""
from helpers import check, freeze, go_tab, settle
from checks.a11y import CONTRAST


def viewport_fit(page):
    freeze(page, '2026-10-20')
    go_tab(page, 0)
    for theme in ('dark', 'light'):
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        for width, height in ((1280, 720), (1366, 768), (1536, 760), (1280, 800), (1440, 900), (1920, 940), (1920, 1080)):
            page.set_viewport_size(dict(width=width, height=height))
            page.wait_for_timeout(650)
            settle(page)
            geometry = page.evaluate("""()=>({height:document.documentElement.scrollHeight,
              width:document.documentElement.scrollWidth,
              bottom:Math.max(...[...document.querySelectorAll('.p-overview.desk .surface')]
                .filter(e=>e.getClientRects().length).map(e=>e.getBoundingClientRect().bottom)),
              hidden:[...document.querySelectorAll('.p-overview.desk .surface')]
                .filter(e=>e.getClientRects().length&&/hidden|clip/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+2)
                .map(e=>e.className)})""")
            check(geometry['height'] <= height + 1 and geometry['bottom'] <= height + 1,
                  f'{theme}/{width}x{height}: Overview exceeds viewport {geometry}')
            check(geometry['width'] <= width and not geometry['hidden'],
                  f'{theme}/{width}x{height}: content clipped {geometry}')
    brand = page.locator('.side-brand img')
    check(brand.evaluate("e=>e.complete&&e.naturalWidth>0&&e.getAttribute('src')==='brand-mark.svg'"),
          'New brand mark missing or failed to load')


def reduced_motion(page):
    page.emulate_media(reduced_motion='reduce')
    go_tab(page, 1)
    go_tab(page, 0)
    page.wait_for_timeout(350)
    settle(page)
    active = page.evaluate("""()=>document.getAnimations().filter(a=>{
      const e=a.effect&&a.effect.target;
      return e&&e.closest&&e.closest('.p-overview,.side-brand')&&a.playState==='running'
        &&a.effect.getTiming().duration>1;
    }).map(a=>a.animationName||'transition')""")
    check(not active, f'Reduced motion: running animations {active}')
    check(page.locator('.p-overview').evaluate('e=>getComputedStyle(e).opacity') == '1',
          'Reduced motion leaves Overview invisible')


def surface_layers(page):
    page.emulate_media(reduced_motion='no-preference')
    go_tab(page, 0)
    for theme in ('dark', 'light'):
        page.evaluate('t=>document.documentElement.dataset.theme=t', theme)
        page.wait_for_timeout(1000)
        roles = page.locator('.p-overview.desk').evaluate("""e=>{
          const s=getComputedStyle(e),names=['--bg','--card','--card2','--border'];
          return names.map(n=>s.getPropertyValue(n).trim());
        }""")
        check(all(roles) and len(set(roles)) == 4, f'{theme}: material layers are not distinct {roles}')
        panel = page.locator('.dv-fc')
        material = panel.evaluate("""e=>{const s=getComputedStyle(e);return {
          shadow:s.boxShadow,background:s.backgroundColor,animation:s.animationName,opacity:s.opacity,
          canvas:getComputedStyle(document.body).backgroundImage,
          glass:getComputedStyle(document.querySelector('.side')).backdropFilter
        }}""")
        expected_background = 'rgb(255, 255, 255)' if theme == 'light' else 'rgb(22, 34, 44)'
        check(material['shadow'] != 'none' and material['background'] == expected_background
              and 'radial-gradient' in material['canvas'] and 'blur' in material['glass'],
              f'{theme}: missing layered panel material {material}')
        heading = panel.locator('.fc-title').first
        check(heading.count() == 1, f'{theme}: forecast heading missing')
        contrast = heading.evaluate('(e,fn)=>eval(fn)(e)', CONTRAST)
        check(contrast['r'] >= 4.5, f'{theme}: forecast text contrast below 4.5: {contrast}')
        check('overview-arrive' in material['animation'] and material['opacity'] == '1',
              f'{theme}: entrance animation missing or does not finish {material}')


CHECKS = [
    ('overview_finish: whole viewport and loaded brand', 'desktop', viewport_fit),
    ('overview_finish: material layers and entrance', 'desktop', surface_layers),
    ('overview_finish: reduced motion', 'desktop', reduced_motion),
]
