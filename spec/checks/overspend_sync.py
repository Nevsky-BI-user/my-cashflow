"""Перевитрата категорії зменшує спільний залишок; зовнішні зміни видно без reload."""
import json

from helpers import check, expand_groups, freeze, go_tab, num, shot
from checks.live_refresh import MOCK, updated

DAY = '2026-10-10'
MONTH = '2026-10-01'
CATEGORIES = [
    {'id': 'food', 'name': 'Продукти', 'icon': '🛒', 'color': '#7066e0', 'budget_limit': 1, 'group_id': 1, 'sort_order': 0},
    {'id': 'other', 'name': 'Інше', 'icon': '•', 'color': '#a94d6d', 'budget_limit': 1, 'group_id': 1, 'sort_order': 1},
    {'id': 'savings', 'name': 'Заощадження', 'icon': '₴', 'color': '#477b65', 'budget_limit': 0, 'group_id': 2, 'sort_order': 2},
]


def plan(savings):
    return {'month_start': MONTH, 'total_cents': 10000 + savings,
            'allocations': {'food': 5000, 'other': 5000, 'savings': savings}, 'mandatory_items': []}


def expense(identifier, category, amount, day='2026-10-02'):
    cat = next(c for c in CATEGORIES if c['id'] == category)
    return {'id': identifier, 'type': 'expense', 'date': day, 'created_at': day + 'T10:00:00Z',
            'amount': amount, 'account_id': 1, 'category_id': category, 'source': 'manual',
            'description': 'Synthetic ' + category, 'categories': {key: cat[key] for key in ('name', 'icon', 'color')}}


def wait_money(page, selector, cents):
    page.wait_for_function("""({selector,cents})=>{
      const el=document.querySelector(selector);
      return el && Math.round(Number(el.innerText.replace(/[^0-9,−-]/g,'').replace('−','-').replace(',','.'))*100)===cents;
    }""", arg={'selector': selector, 'cents': round(cents)})


def wait_transactions(page, rows):
    expected = [{'id': row['id'], 'amount': row['amount'], 'category': row['category_id']} for row in rows]
    page.wait_for_function("""expected=>{
      if(!window.__financeInput)return false;
      const all=__financeInput.transactions,ids=new Set(all.map(t=>t.id));
      return ids.size===expected.length && expected.every(x=>
        all.some(t=>t.id===x.id) && all.filter(t=>t.id===x.id).every(t=>t.amount===x.amount&&t.category_id===x.category));
    }""", arg=expected, timeout=15000)
    updated(page)


def replace_transactions(page, rows):
    reads = page.evaluate('__liveMock.reads.length')
    page.evaluate("rows=>{__liveMock.data.transactions=rows;__liveMock.event('transactions')}", rows)
    wait_transactions(page, rows)
    check(page.evaluate('__liveMock.reads.length') > reads, 'external event bypassed the actual snapshot read')


def check_views(page, signed, ordinary_fact, savings_fact=0):
    """Жовтневий ліміт спільний, а період 06–21.10 окремо обмежений його часткою."""
    # Частка ще не витраченої категорії B: 50 × (20−5)/31 = 24,19;
    # місячний спільний залишок 20 менший, тому саме він обмежує цей період.
    check(5000 * 20 // 31 - 5000 * 5 // 31 == 2419, 'fixture prefix changed')
    state = page.evaluate('({period:__periodBudget,month:__calendarBudget,cp:__financeProjection.currentPeriod})')
    period, month, cp = state['period'], state['month'], state['cp']
    check((period['start'], period['end']) == ('2026-10-06', '2026-10-21'), 'fixture compares a different salary period')
    check((month['start'], month['end']) == ('2026-10-01', '2026-11-01'), 'calendar range changed')
    check(month['remaining'] == signed, f'calendar shared remainder {month["remaining"]}, expected {signed}')
    check(period['rawRemaining'] == signed and cp['signedSpendableRemainingCents'] == signed,
          f'overview/engine signed balance differs: {period["rawRemaining"]}, {cp.get("signedSpendableRemainingCents")} vs {signed}')
    check(period['avail'] == max(0, signed), f'overview hid overspending in another category: {period["avail"]} vs {signed}')
    check(period['overrun'] == max(0, -signed), 'overview overrun is not the shared deficit')
    check(period['daily'] == round(max(0, signed) / 11), 'daily budget uses a category sum instead of shared remaining / 11 days')
    check(month['savingsRemainingCents'] == 0 and month['savingsTargetCents'] == 10000, 'provisional savings target became an upfront cash reserve')
    check(month['fact'] == ordinary_fact + savings_fact, 'snapshot facts differ between calendar and projection')
    check(page.evaluate('__liveMock.data.monthly_budgets[0].allocations.savings') == 10000, 'overspending edited the saved allocation')

    go_tab(page, 0)
    wait_money(page, '.kpi-budget [data-r=avail] .kpi-rv', abs(signed))
    wait_money(page, '.kpi-budget [data-r=daily] .kpi-rv', max(0, signed) / 11)
    over = page.locator('.kpi-budget [data-r=avail]')
    check(over.get_attribute('data-over') == ('1' if signed < 0 else None), 'overview hides negative shared balance')
    if signed < 0:
        check('Перевитрата' in over.inner_text(), 'overview describes a deficit as available money')

    go_tab(page, 1)
    wait_money(page, '.bud-avail .bud-kpi-v', abs(signed))
    check(page.locator('.bud-avail .bud-kpi-v').get_attribute('data-over') == ('1' if signed < 0 else None),
          'calendar hides negative shared balance')
    expand_groups(page)
    raw = next(row for row in month['rows'] if row['id'] == 'food')
    check(raw['remainingCents'] == 5000 - ordinary_fact, 'raw category overspend was erased')
    category = page.locator('.bud-cat[data-cat=food]')
    check(category.is_visible(), 'overspent category disappeared from the budget')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'signed balance widened the page')


def synchronization(page):
    page.emulate_media(reduced_motion='reduce')
    desktop = page.viewport_size['width'] >= 1024
    if desktop:
        page.set_viewport_size({'width': 1280, 'height': 800})
    initial = [expense(1, 'food', 80)]
    setup = {
        'accounts': [{'id': 1, 'name': 'Synthetic wallet', 'bank': 'cash', 'kind': 'cash', 'balance': 1000,
                      'debt': 0, 'active': True, 'sort_order': 0, 'balance_updated_at': '2026-10-01T00:00:00Z'}],
        'categories': CATEGORIES,
        'category_groups': [{'id': 1, 'name': 'Побут', 'sort_order': 0}, {'id': 2, 'name': 'Резерв', 'sort_order': 1}],
        'salary_config': [{'id': 1, 'rate': 0, 'salary_day': 6, 'advance_day': 21, 'split_day': 15,
                           'salary_amount': 100, 'advance_amount': 100, 'savings_pct': 0, 'budget_manual': None}],
        'monthly_budgets': [plan(0)], 'transactions': initial,
    }
    assignments = ''.join('m.data.' + key + '=' + json.dumps(value, ensure_ascii=False) + ';' for key, value in setup.items())
    mock = MOCK.replace('window.supabase={createClient:()=>sb};', assignments + 'window.supabase={createClient:()=>sb};')
    page.add_init_script(mock)
    freeze(page, DAY, patch=[
        ('if(!sb){window.__financeProjection=', '{window.__financeProjection='),
        ('if(!sb)window.__periodBudget=', 'window.__periodBudget='),
        ('if(!sb)window.__calendarBudget=', 'window.__calendarBudget='),
    ])
    wait_transactions(page, initial)
    page.evaluate('window.overspendSameDocument=true')
    go_tab(page, 1)
    page.wait_for_function('__calendarBudget.fact===8000')
    wait_money(page, '.bud-avail .bud-kpi-v', 2000)
    go_tab(page, 0)
    wait_money(page, '.kpi-budget [data-r=avail] .kpi-rv', 2000)
    check(page.evaluate('__periodBudget.daily') == round(2000 / 11), 'no-savings regression baseline changed')

    # Та сама перевитрата з окремим резервом не повинна звільняти резерв для витрат.
    page.evaluate("row=>{__liveMock.data.monthly_budgets=[row];__liveMock.event('monthly_budgets')}", plan(10000))
    page.wait_for_function('__financeInput.monthly_budgets[0].allocations.savings===10000')
    page.wait_for_function('__calendarBudget.savingsTargetCents===10000&&__calendarBudget.savingsRemainingCents===0')
    check_views(page, 2000, 8000)

    # Зміни з іншого пристрою, коли відкрита сторінка Бюджету: add/edit/reclassify/delete.
    replace_transactions(page, initial + [expense(2, 'food', 20, '2026-10-03')])
    check_views(page, 0, 10000)
    replace_transactions(page, initial + [expense(2, 'food', 50, '2026-10-03')])
    check_views(page, -3000, 13000)
    shot(page, 'overspend-sync-desktop-budget.jpg' if desktop else 'overspend-sync-mobile-budget.jpg', full=True)
    go_tab(page, 0)
    shot(page, 'overspend-sync-desktop-overview.jpg' if desktop else 'overspend-sync-mobile-overview.jpg', full=True)

    # Перекласифікація не повертає глобально вже витрачені гроші, але міняє обидва рядки.
    replace_transactions(page, initial + [expense(2, 'other', 50, '2026-10-03')])
    page.wait_for_function("__calendarBudget.rows.find(r=>r.id==='other').factCents===5000")
    # Сума факту та глобальний дефіцит ті самі; тут A має лише початкові 80.
    check(page.evaluate('__periodBudget.rawRemaining') == -3000, 'reclassification inflated the global pool')
    check(page.evaluate("__calendarBudget.rows.find(r=>r.id==='food').remainingCents") == -3000, 'reclassification left the wrong category overspend')
    go_tab(page, 1)
    wait_money(page, '.bud-avail .bud-kpi-v', 3000)
    replace_transactions(page, initial)
    check_views(page, 2000, 8000)

    funds = page.evaluate('kpiFunds(__financeProjection).total')
    replace_transactions(page, initial + [expense(3, 'savings', 40, '2026-10-04')])
    check_views(page, 2000, 8000, 4000)
    check(page.evaluate('kpiFunds(__financeProjection).total') == funds - 4000, 'actual savings were not deducted exactly once')
    page.get_by_role('button', name='Розподіл бюджету', exact=True).click()
    editor = page.get_by_role('dialog', name='Розподіл бюджету місяця')
    check(editor.get_by_role('textbox', name='Продукти, ₴', exact=True).input_value() == '50', 'overspending changed editor allocation A')
    check(editor.get_by_role('textbox', name='Інше, ₴', exact=True).input_value() == '50', 'overspending changed editor allocation B')
    check(editor.get_by_role('textbox', name='Заощадження, ₴', exact=True).count() == 0, 'savings can still be distributed manually')
    check(editor.locator('[data-auto-savings] output').get_attribute('data-cents') == '10000', 'debt-free surplus differs from one automatic savings amount')
    page.keyboard.press('Escape')
    check(page.evaluate('overspendSameDocument===true && __liveMock.channels===1'), 'updates required a reload or duplicate subscription')
    check(page.evaluate('__liveMock.writes.length') == 0, 'external read-only updates generated writes')


CHECKS = [
    ('Overspend shared remaining and daily sync across realtime mutations on desktop', 'desktop', synchronization),
    ('Overspend shared remaining and daily sync across realtime mutations on mobile', 'mobile', synchronization),
]
