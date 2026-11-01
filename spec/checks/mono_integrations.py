"""Друга сімейна картка й зрозумілі результати категоризації без перезавантаження."""
import json
from helpers import check, freeze, go_tab, settle, shot
from checks.live_refresh import MOCK, updated


def mount(page):
    custom=r"""
 m.data.accounts=[{id:11,user_id:'mock-family',name:'Synthetic husband Mono',bank:'mono',kind:'debit',balance:1000,debt:0,active:true,mono_account_id:'husband',card_last4:'1111',sort_order:0,balance_updated_at:'2026-11-01T00:00:00Z'}];
 m.data.profiles=[{id:'mock-family',mono_token:'husband-secret'},{id:'mock-wife',mono_token:null}];m.invokes=[];m.registerFail=false;m.holdRegister=false;m.pendingRegisters=[];
 sb.functions.invoke=async(name,options)=>{m.invokes.push({name,body:options&&options.body});
  if(name==='mono-register'){if(m.registerFail)return{data:null,error:{context:{json:async()=>({error:'ambiguous_account',detail:'secret-private-provider'})}}};if(!m.data.accounts.some(a=>a.id===12))m.data.accounts.push({id:12,user_id:'mock-wife',name:'Synthetic wife Mono',bank:'mono',kind:'debit',balance:2000,debt:0,active:true,mono_account_id:'wife',card_last4:options.body.card_last4,sort_order:1,balance_updated_at:'2026-11-01T00:00:00Z'});const reply={data:{ok:true,account_id:options.body.profile_id==='mock-family'?11:12},error:null};if(m.holdRegister)return new Promise(resolve=>m.pendingRegisters.push(()=>resolve(reply)));return reply;}
  if(name==='mono-balance')return{data:{ok:true,accounts:m.data.accounts.map(a=>({id:a.id,balance:a.id===11?800:2500,debt:0})),account:{id:11,balance:800,debt:0}},error:null};
  if(name==='categorize-batch'){if(options.body.count_only)return{data:{uncategorized:2},error:null};return{data:{ok:true,processed:2,categorized:0,from_cache:0,errors:2,remaining:2,skipped:0,error_reasons:[{code:'provider_auth',retryable:false,count:2,detail:'secret-private-provider'}]},error:null};}
  return{data:{ok:true},error:null};};
 window.supabase={createClient:()=>sb};
 """
    script=MOCK.replace("id:'mock-family',email:ALLOWED_EMAILS[0]","id:'mock-wife',email:ALLOWED_EMAILS[1]").replace('window.supabase={createClient:()=>sb};',custom)
    page.add_init_script(script)
    freeze(page,'2026-11-01',[("if(!sb){window.__financeProjection=","{window.__financeProjection=")])
    updated(page)
    if page.viewport_size['width']>=1024:
        page.keyboard.press('s')
        page.locator('.set-page').wait_for()
    else:
        go_tab(page,5)
    scope=page.locator('.set-page' if page.viewport_size['width']>=1024 else '.set-mpage')
    (scope.locator('nav button',has_text='Інтеграції') if page.viewport_size['width']>=1024 else scope.get_by_role('button',name='Інтеграції')).first.click()
    page.get_by_placeholder('Monobank X-Token').wait_for()
    return scope


def connect(page):
    page.emulate_media(reduced_motion='reduce')
    scope=mount(page)
    reloads=[];page.on('framenavigated',lambda frame:reloads.append(frame.url) if frame==page.main_frame else None)
    page.get_by_label('Останні 4 цифри картки Monobank').fill('2222')
    page.get_by_placeholder('Monobank X-Token').fill('wife-synthetic-secret')
    page.get_by_role('button',name='Зберегти токен',exact=True).click()
    page.get_by_text('Картку підключено. Автооновлення увімкнено.',exact=True).wait_for()
    check(page.get_by_placeholder('Monobank X-Token').input_value()=='','Токен лишився в полі')
    check('Токен збережено' in scope.inner_text(),'Статус токена некоректний')
    check(not reloads,'Підключення перезавантажило сторінку')
    go_tab(page,0)
    page.get_by_role('button',name='Оновити рахунки',exact=True).first.click()
    page.wait_for_function("()=>__financeProjection.snapshot.accounts.some(a=>a.id===12&&a.balance===2500)")
    if page.viewport_size['width']>=1024:
        page.keyboard.press('s')
        page.locator('.set-page').wait_for()
    else:
        go_tab(page,5)
    scope=page.locator('.set-page' if page.viewport_size['width']>=1024 else '.set-mpage')
    if page.get_by_placeholder('Monobank X-Token').count()==0:
        (scope.locator('nav button',has_text='Інтеграції') if page.viewport_size['width']>=1024 else scope.get_by_role('button',name='Інтеграції')).first.click()
    result=page.evaluate("()=>({writes:__liveMock.writes,invokes:__liveMock.invokes,profiles:__liveMock.data.profiles,accounts:__financeProjection.snapshot.accounts.map(a=>({id:a.id,balance:a.balance}))})")
    writes=[r for r in result['writes'] if r['table']=='profiles']
    check(len(writes)==1 and ['eq','id','mock-wife'] in writes[0]['ops'],'Записано чужий профіль')
    check(result['profiles'][0]['mono_token']=='husband-secret','Токен чоловіка змінено')
    check(any(r['name']=='mono-register' and r['body']=={'profile_id':'mock-wife','card_last4':'2222'} for r in result['invokes']),'Цифри картки не передано')
    check(result['accounts']==[{'id':11,'balance':800},{'id':12,'balance':2500}],f'Обидва баланси не оновлено: {result["accounts"]}')
    page.get_by_role('button',name='Категоризувати (до 50)',exact=True).click()
    page.get_by_text('Категоризовано 0, з кешу 0, помилок 2',exact=False).wait_for()
    text=scope.inner_text();check('не прийняв ключ доступу' in text and 'secret-private-provider' not in text,'Причина помилки відсутня або розкриває відповідь')
    check('Внутрішні перекази не потребують категоризації.' in text,'Немає пояснення переказів')
    page.evaluate('__liveMock.registerFail=true')
    page.get_by_role('button',name='Підключити картку',exact=True).click()
    page.get_by_text('Токен збережено, але картку не підключено.',exact=False).wait_for()
    check('Є кілька карток.' in scope.inner_text(),'Не пояснено неоднозначний вибір')
    shot(page,'mono-integrations-'+str(page.viewport_size['width'])+'.jpg',full=False)
    page.get_by_placeholder('Monobank X-Token').fill('pending-wife-synthetic-secret')
    page.get_by_label('Останні 4 цифри картки Monobank').fill('2222')
    page.evaluate("__liveMock.auth('SIGNED_IN',{user:{id:'mock-family',email:ALLOWED_EMAILS[0]}})")
    page.wait_for_function("()=>document.querySelector('input[placeholder=\"Monobank X-Token\"]').value===''&&document.querySelector('input[aria-label=\"Останні 4 цифри картки Monobank\"]').value===''")
    check('pending-wife-synthetic-secret' not in scope.inner_text(),'Токен перейшов до іншого профілю')


def pending_profile_save(page):
    scope=mount(page)
    page.get_by_placeholder('Monobank X-Token').fill('pending-wife-token')
    page.get_by_label('Останні 4 цифри картки Monobank').fill('2222')
    page.evaluate('__liveMock.holdWrites=true')
    page.get_by_role('button',name='Зберегти токен',exact=True).click()
    page.wait_for_function('()=>__liveMock.pendingWrites.length===1')
    page.evaluate("__liveMock.auth('SIGNED_IN',{user:{id:'mock-family',email:ALLOWED_EMAILS[0]}})")
    page.wait_for_function("()=>document.querySelector('input[placeholder=\"Monobank X-Token\"]').value===''")
    page.evaluate('__liveMock.releaseWrites()')
    page.wait_for_timeout(150)
    check(page.evaluate("__liveMock.invokes.filter(x=>x.name==='mono-register').length") == 0,'Застаріле збереження запустило реєстрацію іншого профілю')
    check('Картку підключено.' not in scope.inner_text(),'Застаріла відповідь відновила повідомлення')
    check(page.get_by_role('button',name='Зберегти токен',exact=True).is_enabled(),'Зміна профілю не скинула зайнятість')


def pending_registration(page):
    scope=mount(page)
    page.get_by_label('Останні 4 цифри картки Monobank').fill('2222')
    page.evaluate('__liveMock.holdRegister=true')
    page.get_by_role('button',name='Підключити картку',exact=True).click()
    page.wait_for_function('()=>__liveMock.pendingRegisters.length===1')
    page.evaluate("__liveMock.auth('SIGNED_IN',{user:{id:'mock-family',email:ALLOWED_EMAILS[0]}})")
    page.get_by_role('button',name='Підключити картку',exact=True).wait_for()
    updated(page)
    page.get_by_label('Останні 4 цифри картки Monobank').fill('1111')
    page.get_by_role('button',name='Підключити картку',exact=True).click()
    page.wait_for_function('()=>__liveMock.pendingRegisters.length===2')
    reads=page.evaluate('__liveMock.reads.length')
    page.evaluate('__liveMock.pendingRegisters.shift()()')
    page.wait_for_timeout(150)
    check(page.get_by_role('button',name='Історія 31 день',exact=True).is_disabled(),'Стара відповідь скинула зайнятість нового запиту')
    check(page.evaluate('__liveMock.reads.length')==reads,'Стара відповідь оновила новий профіль')
    check('Картку підключено.' not in scope.inner_text(),'Стара реєстрація показала успіх новому профілю')
    page.evaluate('__liveMock.pendingRegisters.shift()()')
    page.get_by_text('Картку підключено. Автооновлення увімкнено.',exact=True).wait_for()


CHECKS=[('Зміна профілю під час збереження токена','desktop',pending_profile_save),('Зміна профілю під час реєстрації картки','desktop',pending_registration),('Друга картка та результати категоризації на ПК','desktop',connect),('Друга картка та результати категоризації на телефоні','mobile',connect)]
