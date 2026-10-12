# Локальні календарні дати й захист операції від повторного запису.
from helpers import check, dialog, go_tab


def add_saving(page):
    """Кнопка «+ Внесок» у «Фактичних накопиченнях» (v142: текстова кнопка без класу .goals-log-add)."""
    return page.locator('.goals-log').get_by_role('button', name='+ Внесок', exact=True)


def local_dates(page):
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send('Emulation.setTimezoneOverride', {'timezoneId': 'Europe/Kyiv'})
        # Зима, літо й межа місяця: UTC ще попереднього дня.
        for instant, day in [('2026-01-15T22:15:00Z', '2026-01-16'),
                             ('2026-07-15T21:15:00Z', '2026-07-16'),
                             ('2026-03-31T21:15:00Z', '2026-04-01')]:
            page.clock.set_fixed_time(instant)
            page.reload()
            page.wait_for_selector('.side')
            page.keyboard.press('n')
            tx = dialog(page, 'Нова операція')
            check(tx.locator('input[type=date]').input_value() == day,
                  f'операція {instant}: очікували {day}')
            page.keyboard.press('Escape')
            go_tab(page, 4)
            add_saving(page).click()
            sav = dialog(page, 'Поповнення')
            check(sav.locator('input[type=date]').input_value() == day,
                  f'накопичення {instant}: очікували {day}')
            page.keyboard.press('Escape')
            # Повторне відкриття після переходу через північ без reload.
            next_day = day[:-2] + str(int(day[-2:]) + 1).zfill(2)
            page.clock.set_fixed_time(next_day + 'T00:15:00+03:00' if '-07-' in day or '-04-' in day
                                      else next_day + 'T00:15:00+02:00')
            page.keyboard.press('n')
            check(tx.locator('input[type=date]').input_value() == next_day,
                  'повторне відкриття операції зберегло стару дату')
            page.keyboard.press('Escape')
            add_saving(page).click()
            check(sav.locator('input[type=date]').input_value() == next_day,
                  'повторне відкриття накопичення зберегло стару дату')
            page.keyboard.press('Escape')
    finally:
        cdp.detach()


def mock_save(page):
    # Лише saveTx отримує тестову БД: auth і решта завантажень лишаються демо.
    url = page.url
    def patch(route):
        response = route.fetch()
        body = response.text()
        marker = 'const saveTx=async()=>{'
        check(body.count(marker) == 1, 'не знайдено saveTx для фікстури')
        body = body.replace(marker, marker + "const sb=window.__integrityDb;"
                            "const session={user:{id:'synthetic-user'}};const reloadTx=()=>{};")
        route.fulfill(response=response, body=body)
    page.route(url, patch)
    page.reload()
    page.wait_for_selector('.side')
    page.evaluate("""()=>{
      window.__writes=[];window.__pending=[];
      window.__integrityDb={from(table){if(table!=='transactions')throw Error('unexpected table');
        return{insert(row){window.__writes.push(row);return new Promise((resolve,reject)=>window.__pending.push({resolve,reject}))}}}};
    }""")
    page.keyboard.press('n')
    tx = dialog(page, 'Нова операція')
    tx.locator('.amt-in').fill('321')
    tx.get_by_role('button', name='Продукти', exact=False).click()
    tx.locator('.acc-seg button').first.click()
    return tx


def repeat_enter(page):
    tx = mock_save(page)
    tx.locator('.amt-in').focus()
    # Справжній шлях Enter, включно з повтором клавіші й setTimeout hotkey.
    page.evaluate("""()=>{for(let i=0;i<4;i++)document.activeElement.dispatchEvent(
      new KeyboardEvent('keydown',{key:'Enter',code:'Enter',repeat:i>0,bubbles:true}));}""")
    page.wait_for_function('window.__writes.length > 0')
    page.wait_for_timeout(150)
    count = page.evaluate('window.__writes.length')
    check(count == 1, f'повтор Enter записав {count} операцій замість однієї')
    page.evaluate("window.__pending.splice(0).forEach(p=>p.resolve({error:null}))")
    tx.wait_for(state='hidden')


def clicks_and_retry(page):
    tx = mock_save(page)
    # Валідація не має заблокувати майбутнє коректне збереження.
    tx.locator('.amt-in').fill('0')
    tx.locator('.amt-in').press('Enter')
    page.wait_for_timeout(100)
    check(page.evaluate('window.__writes.length') == 0, 'записано нульову суму')
    check('Введіть суму' in tx.inner_text(), 'немає помилки валідації')
    tx.locator('.amt-in').fill('321')
    page.evaluate("""()=>{const b=document.querySelector('.tx-save');b.click();b.click();}""")
    page.wait_for_function('window.__writes.length === 1')
    check(tx.locator('.tx-save').is_disabled(), 'кнопка активна під час запису')
    # Supabase може повернути error або відхилити Promise; обидва шляхи дають retry.
    page.evaluate("window.__pending.shift().resolve({error:{message:'synthetic response error'}})")
    page.wait_for_function("document.querySelector('.tx-save').disabled === false")
    check('synthetic response error' in tx.inner_text(), 'не показано помилку відповіді')
    tx.locator('.tx-save').click()
    page.wait_for_function('window.__writes.length === 2')
    page.evaluate("window.__pending.shift().reject(new Error('synthetic network error'))")
    page.wait_for_function("document.querySelector('.tx-save').disabled === false")
    check('synthetic network error' in tx.inner_text(), 'не показано помилку мережі')
    tx.locator('.amt-in').press('Enter')
    page.wait_for_function('window.__writes.length === 3')
    page.evaluate("window.__pending.shift().resolve({error:null})")
    tx.wait_for(state='hidden')
    check(page.evaluate('window.__writes.map(r=>r.amount)') == [321, 321, 321],
          'retry змінив суму операції')


def demo_save(page):
    page.keyboard.press('n')
    tx = dialog(page, 'Нова операція')
    tx.locator('.amt-in').fill('321')
    tx.get_by_role('button', name='Продукти', exact=False).click()
    tx.locator('.acc-seg button').first.click()
    tx.locator('input[type=text]').fill('integrity demo operation')
    tx.locator('.amt-in').press('Enter')
    tx.wait_for(state='hidden')
    go_tab(page, 2)
    check(page.locator('.flow-row.tx:has-text("integrity demo operation")').count() == 1,
          'демо не показало рівно одну збережену операцію')


CHECKS = [
    ('Локальні дати форм: Київ, зима, літо, межа місяця', 'desktop', local_dates),
    ('Повтор Enter записує одну операцію', 'desktop', repeat_enter),
    ('Подвійний клік, валідація, помилка відповіді/мережі, retry', 'desktop', clicks_and_retry),
    ('Демо: Enter зберігає операцію і закриває форму', 'desktop', demo_save),
]
