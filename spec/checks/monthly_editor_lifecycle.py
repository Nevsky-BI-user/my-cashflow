"""Редактор не втрачає чернетку під час жестів та оновлення даних."""
from helpers import check, go_tab
from checks.monthly_budget import mount


def draft_survives(page):
    mount(page)
    go_tab(page, 1)
    page.locator('.bud-alloc').get_by_role('button', name='Розподіл бюджету').click()
    sheet = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    field = sheet.get_by_role('textbox', name='Продукти, ₴', exact=True)
    field.fill('432.10')
    field.press('Tab')
    page.evaluate("__liveMock.event('categories')")
    page.wait_for_timeout(800)
    check(field.input_value() == '432.10', 'realtime lost allocation draft')
    box = field.bounding_box()
    # Миша/палець починає жест у полі, завершує на тлі:
    # браузер адресує click спільному предку — overlay.
    page.mouse.move(box['x'] + 20, box['y'] + box['height'] / 2)
    page.mouse.down()
    page.mouse.move(8, 8, steps=12)
    page.mouse.up()
    check(sheet.count() == 1, 'drag from editor onto backdrop dismissed allocation draft')
    check(field.input_value() == '432.10', 'drag lost allocation draft')
    vp = page.viewport_size
    page.set_viewport_size({'width': vp['width'], 'height': vp['height'] - 220})
    page.wait_for_timeout(150)
    page.set_viewport_size(vp)
    check(field.input_value() == '432.10', 'keyboard resize lost allocation draft')
    sheet.evaluate('(el)=>el.scrollTop=el.scrollHeight')
    check(sheet.count() == 1, 'scroll dismissed allocation draft')
    sheet.get_by_role('button', name='Закрити', exact=True).click()
    check(sheet.count() == 0, 'explicit close stopped working')


CHECKS = [
    ('monthly_editor_lifecycle: draft survives realtime drag and resize desktop', 'desktop', draft_survives),
    ('monthly_editor_lifecycle: draft survives realtime drag and resize mobile', 'mobile', draft_survives),
]
