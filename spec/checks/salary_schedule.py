"""Графік підвищення: робочі дні, збереження чернетки та керування майбутніми ставками."""
import json

from helpers import check, freeze, shot, settle, SHOTS
from checks.numfield import _salary_root


def reopen(page):
    if page.viewport_size['width'] >= 1024:
        page.locator('.set-page nav button', has_text='Тема').first.click()
        page.locator('.set-page nav button', has_text='Зарплата').first.click()
        return page.locator('.set-page:has(input.nf-range)')
    page.locator('.set-mpage button', has_text='Назад').click()
    page.locator('.set-mpage button', has_text='Зарплата').first.click()
    return page.locator('.set-mpage .set-msec[data-sec=salary]').last


def save(root):
    root.get_by_role('button', name='Зберегти', exact=True).click()


def lifecycle(page):
    freeze(page, '2026-10-29')
    root = _salary_root(page)
    before = root.locator('input.nf-range').first.input_value()
    root.get_by_role('button', name='+ Запланувати підвищення', exact=True).click()
    rate = root.get_by_role('spinbutton', name='Нова ставка 1', exact=True)
    when = root.get_by_label('Дата зміни 1', exact=True)
    check(when.input_value() == '2026-11-01', 'нова зміна має починатися з наступного місяця')
    rate.fill('126000')
    root.get_by_role('button', name='Наступний місяць', exact=True).click()
    text = ' '.join(root.inner_text().split())
    check('60 000 ₴' in text, 'аванс листопада не врахував нову ставку 126000')
    check('51 000 ₴' in text, 'зарплата за жовтень втратила попередню ставку')
    check(root.locator('input.nf-range').first.input_value() == before, 'планування змінило базову ставку')
    check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'горизонтальне переповнення')
    rate.scroll_into_view_if_needed()
    settle(page)
    shot(page, 'salary-schedule-' + str(page.viewport_size['width']) + '.jpg', full=False)
    root.locator('.sal-plan').screenshot(path=str(SHOTS / ('salary-schedule-form-' + str(page.viewport_size['width']) + '.png')))
    save(root)
    root = reopen(page)
    check(root.get_by_role('spinbutton', name='Нова ставка 1', exact=True).input_value() == '126000', 'збережена ставка не відновилась')
    check(root.get_by_label('Дата зміни 1', exact=True).input_value() == '2026-11-01', 'збережена дата не відновилась')
    root.get_by_role('spinbutton', name='Нова ставка 1', exact=True).fill('147000')
    root.get_by_label('Дата зміни 1', exact=True).fill('2026-11-16')
    save(root)
    root = reopen(page)
    check(root.get_by_role('spinbutton', name='Нова ставка 1', exact=True).input_value() == '147000', 'редагування ставки не збережено')
    check(root.get_by_label('Дата зміни 1', exact=True).input_value() == '2026-11-16', 'редагування дати не збережено')
    root.get_by_role('button', name='Скасувати зміну 1', exact=True).click()
    save(root)
    root = reopen(page)
    check(root.locator('[data-salary-change]').count() == 0, 'скасована зміна знову зʼявилась')
    check(root.locator('input.nf-range').first.input_value() == before, 'редагування графіка змінило базову ставку')


def invalid(page):
    freeze(page, '2026-10-29')
    root = _salary_root(page)
    root.get_by_role('button', name='+ Запланувати підвищення', exact=True).click()
    rate = root.get_by_role('spinbutton', name='Нова ставка 1', exact=True)
    when = root.get_by_label('Дата зміни 1', exact=True)
    rate.fill('0')
    save(root)
    check('Нова ставка має бути більшою за 0' in root.inner_text(), 'нульову ставку прийнято')
    check(rate.input_value() == '0', 'помилка стерла чернетку ставки')
    rate.fill('126000')
    when.fill('')
    save(root)
    check('Вкажіть коректну дату початку' in root.inner_text(), 'порожню дату прийнято')
    when.fill('2026-10-29')
    save(root)
    check('Виберіть майбутню дату' in root.inner_text(), 'дату сьогодні прийнято для нової зміни')
    when.fill('2026-11-01')
    root.get_by_role('button', name='+ Запланувати підвищення', exact=True).click()
    root.get_by_label('Дата зміни 2', exact=True).fill('2026-11-01')
    save(root)
    check('На одну дату можна запланувати лише одну ставку' in root.inner_text(), 'дублікат дати прийнято')
    check(root.locator('[data-salary-change]').count() == 2, 'помилка стерла рядки чернетки')
    root = reopen(page)
    check(root.locator('[data-salary-change]').count() == 0, 'некоректний графік зберігся')


def fixed_cancel(page):
    cfg = {'rate': 0, 'advance_day': 21, 'salary_day': 6, 'split_day': 15,
           'advance_amount': 30000, 'salary_amount': 40000,
           'rate_schedule': [{'effective_from': '2026-11-01', 'rate': 126000}]}
    freeze(page, '2026-10-29', [('const[salCfg,setSalCfg]=useState(null)',
                               'const[salCfg,setSalCfg]=useState(' + json.dumps(cfg) + ')')])
    root = _salary_root(page)
    root.get_by_role('button', name='Скасувати зміну 1', exact=True).click()
    save(root)
    check('Ставка має бути більшою' not in root.inner_text(), 'скасування графіка вимагає переписати історичну нульову ставку')
    root = reopen(page)
    check(root.locator('[data-salary-change]').count() == 0, 'остання запланована зміна не скасувалась')
    check(root.locator('input.nf-range').first.input_value() == '0', 'фіксований режим змінився')
    text = ' '.join(root.inner_text().split())
    check('30 000 ₴' in text and '40 000 ₴' in text, 'фіксовані суми втрачено')


def applied_readonly(page):
    cfg = {'rate': 102000, 'advance_day': 21, 'salary_day': 6, 'split_day': 15,
           'rate_schedule': [{'effective_from': '2026-10-01', 'rate': 126000},
                             {'effective_from': '2026-11-01', 'rate': 147000}]}
    freeze(page, '2026-10-29', [('const[salCfg,setSalCfg]=useState(null)',
                               'const[salCfg,setSalCfg]=useState(' + json.dumps(cfg) + ')')])
    root = _salary_root(page)
    check(root.locator('.sal-plan-applied').count() == 1, 'чинну ставку не показано як історичну')
    check('126 000' in ' '.join(root.locator('.sal-plan-applied').inner_text().split()), 'чинна ставка неправильна')
    check(root.get_by_label('Дата зміни 1', exact=True).count() == 0, 'чинну дату можна змінити')
    check(root.get_by_role('button', name='Скасувати зміну 1', exact=True).count() == 0, 'чинну зміну можна видалити')
    root.get_by_role('button', name='Скасувати зміну 2', exact=True).click()
    save(root)
    root = reopen(page)
    check(root.locator('[data-salary-change]').count() == 1 and root.locator('.sal-plan-applied').count() == 1,
          'скасування майбутньої ставки змінило історію')


CHECKS = [
    ('Підвищення: додати, перерахувати, зберегти, редагувати й скасувати', 'desktop', lifecycle),
    ('Підвищення телефон: повний цикл і геометрія', 'mobile', lifecycle),
    ('Підвищення: некоректні ставки й дати не зберігаються', 'desktop', invalid),
    ('Підвищення телефон: помилка зберігає чернетку', 'mobile', invalid),
    ('Підвищення: скасування в режимі фіксованих сум', 'desktop', fixed_cancel),
    ('Підвищення: чинні ставки лише для перегляду', 'mobile', applied_readonly),
]
