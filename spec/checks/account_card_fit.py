"""Усі реквізити картки видимі: синтетичні пʼять рахунків і довгі підписи."""
from helpers import check, shot, settle
from checks.account_card_identity import instrument


MOUNT = r"""({mobile,deck})=>{
 const previous=document.getElementById('card-fit-fixture');if(previous){window.__cardFitRoot.unmount();previous.remove()}
 const host=document.createElement('section');host.id='card-fit-fixture';
 host.className=mobile?(deck?'p-overview':''):'p-overview desk';
 Object.assign(host.style,{position:'fixed',inset:mobile?'0':'0 0 0 240px',zIndex:9000,padding:'16px',boxSizing:'border-box',overflow:'auto',background:'var(--bg)'});
 document.getElementById('root').append(host);
 const today=new Date(2026,9,25),base={active:true,balance_updated_at:'2026-10-21T10:00:00Z'};
 const accounts=[
  {...base,id:801,bank:'oschad',kind:'debit',name:'Основний рахунок',card_last4:'0678',balance:1245,is_salary:true},
  {...base,id:802,bank:'privat',kind:'credit',name:'Кредитна картка для щоденних покупок',card_last4:'1234',debt:12500,credit_limit:48000,debt_month:'2026-09-01'},
  {...base,id:803,bank:'privat',kind:'debit',name:'Окремий рахунок для сімейних витрат',card_last4:'5678',balance:3900},
  {...base,id:804,bank:'mono',kind:'debit',name:'Додаткова картка',card_last4:'9012',balance:975},
  {...base,id:805,bank:'cash',kind:'cash',name:'Готівка',balance:450},
 ];
 const minSpend=[
  {accountId:801,spent:42750,min:18000,left:0,fee:500,feeDate:'2026-11-01'},
  {accountId:803,spent:875,min:24000,left:23125,fee:600,feeDate:'2026-11-01'},
 ];
 window.__cardFitAccounts=accounts;window.__cardFitOpened=null;window.__cardFitRoot=ReactDOM.createRoot(host);
 const props={accounts,today,minSpend,advice:[],unassigned:[],onOpen:a=>window.__cardFitOpened=a.id,onAdd:()=>{},onOrder:()=>{},onRefresh:()=>{},onUnassigned:()=>{}};
 window.__cardFitRoot.render(deck?h(MobileAccountDeck,props):h('div',{className:mobile?'acc-list':'dv-cards',style:mobile?{display:'flex',flexWrap:'wrap',gap:12}:undefined},...accounts.map(a=>h(BankCard,{key:a.id,a,size:mobile?'sm':'d',today,ms:minSpend.find(r=>r.accountId===a.id),onClick:()=>window.__cardFitOpened=a.id})),h(AddAccTile,{key:'add',onClick:()=>{}})));
}"""

METRICS = r"""e=>{
 const card=e.getBoundingClientRect();const selectors='.bcard-head,.bcard-bank,.bcard-badges,.bcard-badge,.bcard-sum,.bcard-avail,.bcard-due,.ms-bar,.ms-txt,.ms-txt>span,.ms-warn,.bcard-foot,.bcard-name,.bcard-updated';
 return [...e.querySelectorAll(selectors)].filter(x=>x.getClientRects().length).map(x=>{const r=x.getBoundingClientRect(),s=getComputedStyle(x);return {cls:x.className,text:x.innerText,overflow:x.scrollWidth>x.clientWidth+1||(x.scrollHeight>x.clientHeight+1&&['hidden','clip','scroll','auto'].includes(s.overflowY)),outside:r.left<card.left-1||r.right>card.right+1||r.bottom>card.bottom+1||r.top<card.top-1,ellipsis:s.textOverflow==='ellipsis',size:parseFloat(s.fontSize)}});
}"""


def _mount(page, mobile=False, deck=False):
    page.evaluate(MOUNT, {'mobile': mobile, 'deck': deck})
    page.wait_for_selector('#card-fit-fixture .o-bank-card' if deck else '#card-fit-fixture .bcard')
    settle(page)


def _cards(page, width, theme, mobile):
    check(page.get_attribute('html', 'data-theme') == theme, f'{width}: requested theme changed')
    cards = page.locator('#card-fit-fixture .bcard')
    check(cards.count() == 5, 'synthetic five-account fixture missing cards')
    for card in cards.all():
        metrics = card.evaluate(METRICS)
        bad = [m for m in metrics if m['overflow'] or m['outside'] or m['ellipsis']]
        check(not bad, f'{width}/{theme}: clipped card content: {bad}')
        check(all(m['size'] >= 11 for m in metrics), f'{width}/{theme}: card text shrunk below existing readable size')
    # Inline CountUp glyphs can extend beyond their line box; the card must contain their actual painted bounds.
    check(cards.evaluate_all('es=>es.every(e=>{const c=e.getBoundingClientRect();return [...e.querySelectorAll(".bcard-sum .cu")].every(x=>{const r=x.getBoundingClientRect();return r.top>=c.top&&r.bottom<=c.bottom&&getComputedStyle(x.parentElement).overflow==="visible"})})'), 'amount glyphs clipped by card')
    first = cards.first
    check('зарплатна' in first.inner_text() and '0678' in first.inner_text() and 'оновлено' in first.inner_text(), 'salary/card/update identity missing')
    check('42\xa0750' in first.inner_text() and '18\xa0000' in first.inner_text() and 'жовтні' in first.inner_text() and 'без комісії' in first.inner_text(), 'full monthly spending or status missing')
    check('ліміт' not in cards.nth(1).inner_text() and 'доступно' in cards.nth(1).inner_text() and 'погашення' in cards.nth(1).inner_text(), 'credit availability or repayment date missing')
    check('23\xa0125' in cards.nth(2).inner_text() and '31.10' in cards.nth(2).inner_text() and '600' in cards.nth(2).inner_text(), 'unmet spending warning missing data')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{width}/{theme}: outer page overflow')
    if not mobile:
        paints = cards.evaluate_all('es=>es.map(e=>getComputedStyle(e).backgroundImage)')
        check(all('gradient' in paint for paint in paints), 'bank gradients lost')
    first.scroll_into_view_if_needed()
    first.click()
    check(page.evaluate('window.__cardFitOpened') == 801, 'account card action lost')


def desktop(page):
    for width in (1280, 1440, 1920):
        page.set_viewport_size({'width': width, 'height': 900})
        for theme in ('light', 'dark'):
            page.evaluate('(t)=>document.documentElement.setAttribute("data-theme",t)', theme)
            _mount(page)
            _cards(page, width, theme, False)
            if width in (1280, 1920):
                shot(page, f'account-card-fit-{width}-{theme}.jpg', full=False)


def mobile(page):
    for width in (375, 390, 430):
        page.set_viewport_size({'width': width, 'height': 900})
        for theme in ('light', 'dark'):
            page.evaluate('(t)=>document.documentElement.setAttribute("data-theme",t)', theme)
            _mount(page, mobile=True)
            _cards(page, width, theme, True)
            if width == 390:
                shot(page, f'account-card-fit-settings-{width}-{theme}.jpg', full=False)
    # Зміна підпису MsBar не змінює мобільну колоду й не обрізає її прогрес.
    for width in (375, 430):
        page.set_viewport_size({'width': width, 'height': 900})
        _mount(page, mobile=True, deck=True)
        current = page.locator('#card-fit-fixture .o-bank-card[aria-current=true]')
        check(current.count() == 1 and 'жовтні' in current.inner_text(), 'mobile deck lost visible month')
        check(current.locator('.ms-txt>span').evaluate_all('es=>es.every(e=>e.scrollWidth<=e.clientWidth+1&&e.scrollHeight<=e.clientHeight+1)'), 'mobile deck spending text clipped')
        current.focus()
        page.keyboard.press('ArrowRight')
        page.wait_for_timeout(500)
        check(page.locator('#card-fit-fixture .o-stack-item').nth(1).get_attribute('aria-hidden') == 'false', 'mobile deck keyboard navigation lost')
        check(page.evaluate('window.__cardFitOpened') is None, 'changing card opened account details')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile deck creates page overflow')


def dashboard(page):
    page.emulate_media(reduced_motion='reduce')
    # Reuse synthetic metadata, then reload into the real App and its normal dashboard composition.
    _mount(page)
    page.evaluate("""()=>localStorage.setItem('test_cards',JSON.stringify(window.__cardFitAccounts.map(a=>({...a,min_spend:a.id===801?18000:a.id===803?24000:null,min_spend_fee:a.id===801?500:a.id===803?600:null}))))""")
    instrument(page)
    for width in (1280, 1920):
        page.set_viewport_size({'width': width, 'height': 900})
        page.reload()
        page.locator('.dv-cards .bcard').first.wait_for()
        settle(page)
        check(page.locator('#card-fit-fixture').count() == 0, 'standalone fixture leaked into App integration')
        cards = page.locator('.dv-cards .bcard')
        check(cards.count() == 5, f'{width}: real App lost synthetic accounts')
        check(page.locator('.dv-cards .bcard-add').count() == 1, 'real account add control missing')
        check(cards.first.locator('.ms-txt').count() == 1 and cards.nth(2).locator('.ms-txt').count() == 1, 'real monthly spending labels missing')
        for card in cards.all():
            bad = [m for m in card.evaluate(METRICS) if m['overflow'] or m['outside'] or m['ellipsis']]
            check(not bad, f'{width}: real App clipped card content: {bad}')
            card.scroll_into_view_if_needed()
            check(card.evaluate("e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}"), f'{width}: account cannot be reached')
            card.click()
            history = page.locator('.account-history-sheet')
            history.wait_for(state='visible')
            check(history.locator('h2').inner_text().strip(), 'account history opened without identity')
            page.keyboard.press('Escape')
            history.wait_for(state='hidden')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{width}: real App outer width overflow')
        panels = page.locator('.dv-fc,.dv-near,.dv-bud,.ov-grid>.kpi-t.kpi-inst,.dv-recent')
        check(panels.count() == 5, f'{width}: mandatory dashboard panel missing')
        for panel in panels.all():
            panel.scroll_into_view_if_needed()
            check(panel.evaluate("e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=-1&&r.bottom<=innerHeight+1&&r.left>=0&&r.right<=innerWidth+1}"), f'{width}: dashboard panel cut or unreachable')
        page.evaluate('window.scrollTo(0,0)')
        page.wait_for_timeout(500)
        settle(page)
        shot(page, f'account-card-fit-dashboard-{width}.jpg', full=True)


CHECKS = [
    ('Account card fit: real App five-account dashboard, panels and history 1280/1920', 'desktop', dashboard),
    ('Account card fit: five accounts, full labels, amounts and dates 1280/1440/1920 light/dark', 'desktop', desktop),
    ('Account card fit: settings and mobile deck 375/390/430 light/dark', 'mobile', mobile),
]
