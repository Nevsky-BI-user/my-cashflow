"""Повні мобільні підсумки та компактні події без накладання."""
from helpers import check, freeze, go_tab, settle, shot, open_calendar_day, num


WIDTHS = (320, 375, 390, 430)
KPI_BOUNDS = r"""()=>{
 const box=e=>{const r=e.getBoundingClientRect();return{l:r.left,r:r.right,t:r.top,b:r.bottom,w:r.width,h:r.height}};
 const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const root=document.querySelector('.projection-summary');
 return {width:innerWidth,doc:document.documentElement.scrollWidth,cards:[...root.querySelectorAll(':scope>.kpi-t')].map(card=>({
  cls:card.className,...box(card),head:[...card.querySelectorAll('.dv-kpi-v')].filter(visible).map(e=>({text:e.textContent,...box(e),client:e.clientWidth,scroll:e.scrollWidth,font:parseFloat(getComputedStyle(e).fontSize),paint:box((()=>{const r=document.createRange();r.selectNodeContents(e);return r})())})),
  rows:[...card.querySelectorAll('.kpi-row')].map(e=>({label:e.querySelector('.kpi-rl').textContent,value:e.querySelector('.kpi-rv').textContent,labelBox:box(e.querySelector('.kpi-rl')),valueBox:box(e.querySelector('.kpi-rv')),font:parseFloat(getComputedStyle(e).fontSize)}))
 }))};
}"""
CAL_BOUNDS = r"""()=>{
 const box=e=>{const r=e.getBoundingClientRect();return{l:r.left,r:r.right,t:r.top,b:r.bottom}};
 const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 return {width:innerWidth,doc:document.documentElement.scrollWidth,cells:[...document.querySelectorAll('.calendar-only .cal-cell')].map(cell=>({
  date:cell.dataset.date,...box(cell),aria:cell.getAttribute('aria-label'),
  content:[...cell.querySelectorAll('.cal-dh,.cal-event-icon,.cal-preview-amount,.cal-bal')].filter(visible).map(e=>({cls:e.className,text:e.textContent,...box(e),scroll:e.scrollWidth,client:e.clientWidth}))
 }))};
}"""


def overview(page):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        page.set_viewport_size(dict(width=375, height=844))
        freeze(page, '2026-10-26')
        go_tab(page, 0)
        for width in WIDTHS:
            page.set_viewport_size(dict(width=width, height=844))
            page.wait_for_timeout(250)
            settle(page)
            tag = f'{theme}/{width}'
            g = page.evaluate(KPI_BOUNDS)
            check(g['doc'] <= width, f'{tag}: горизонтальна прокрутка')
            check(len(g['cards']) == 4, f'{tag}: втрачено підсумки')
            for card in g['cards']:
                check(card['w'] >= width - 50 and card['r'] <= width, f'{tag}: вузька або обрізана картка {card}')
                for amount in card['head']:
                    check('₴' in amount['text'] and amount['font'] >= 24, f'{tag}: сума без валюти або замала {amount}')
                    check(amount['scroll'] <= amount['client'] + 1 and amount['paint']['r'] <= card['r'] - 8 and amount['paint']['l'] >= card['l'], f'{tag}: сума виходить за картку {amount}')
                for row in card['rows']:
                    check(row['font'] >= 12 and row['labelBox']['r'] <= row['valueBox']['l'] - 4, f'{tag}: накладені підпис і сума {row}')
                    check(row['valueBox']['r'] <= card['r'] - 8 and row['valueBox']['l'] >= card['l'], f'{tag}: обрізана сума {row}')
            if width in (375, 390):
                shot(page, f'mobile-kpi-{theme}-{width}.jpg', full=False)


def calendar(page):
    for theme in ('light', 'dark'):
        page.evaluate('(t)=>localStorage.setItem("theme",t)', theme)
        page.set_viewport_size(dict(width=375, height=844))
        freeze(page, '2026-10-08')
        go_tab(page, 3)
        for width in WIDTHS:
            page.set_viewport_size(dict(width=width, height=844))
            page.wait_for_timeout(250)
            settle(page)
            tag = f'{theme}/{width}'
            check(page.locator('.cal-legend').count() == 0, f'{tag}: легенду не прибрано')
            g = page.evaluate(CAL_BOUNDS)
            check(g['doc'] <= width and len(g['cells']) == 31, f'{tag}: календар обрізано')
            for cell in g['cells']:
                for item in cell['content']:
                    check(item['l'] >= cell['l'] - 1 and item['r'] <= cell['r'] + 1 and item['t'] >= cell['t'] and item['b'] <= cell['b'] + 1, f'{tag}: подія вийшла за свій день {cell["date"]}: {item}')
                    check(item['scroll'] <= item['client'] + 1, f'{tag}: текст події не вміщається {item}')
            check(page.locator('.cal-preview-amount').count() > 0 and page.locator('.cal-event-icon[aria-label]').count() > 0, f'{tag}: втрачено суми або типи подій')
            details = open_calendar_day(page, '2026-10-10')
            row = details.locator('.cal-day-row', has_text='Садочок')
            check(row.count() == 1 and num(row.locator('.cal-day-amount').inner_text()) == -3500, f'{tag}: повна назва або точна сума недоступні')
            check(row.locator('.pay-done').count() == 1, f'{tag}: втрачено оплату')
            page.keyboard.press('Escape')
            check(page.locator('.cal-cell[data-date="2026-10-10"]').evaluate('e=>e===document.activeElement'), f'{tag}: фокус не повернувся на день')
            if width in (375, 390):
                page.locator('.ck-cal').scroll_into_view_if_needed()
                shot(page, f'mobile-calendar-{theme}-{width}.jpg', full=False)
        page.set_viewport_size(dict(width=1280, height=720))
        page.wait_for_timeout(250)
        settle(page)
        check(page.locator('.cal-legend').count() == 0 and page.locator('.cal-cell').count() == 31, 'Легенду не прибрано на ПК')


CHECKS = [
    ('mobile overlap: complete financial summaries', 'mobile', overview),
    ('mobile overlap: compact calendar and no legend', 'mobile', calendar),
]
