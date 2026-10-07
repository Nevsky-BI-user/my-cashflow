# Правило бюджету періоду: periodBudget з index.html проти еталону scripts/budget_pool.py на знімку spec/fixtures
import json
import subprocess
import sys

from helpers import ROOT, SPEC, check

FIX = SPEC / 'fixtures' / 'snapshot.json'
# (дата сьогодні, зміна боргу кредитки або None): звичайний день, день самої виплати, дефіцит, бюджет у мінусі
CASES = [('2026-10-08', None), ('2026-10-21', None), ('2026-11-05', None), ('2026-10-08', 40000), ('2026-10-08', 100000)]
NUMS = ['oblSum', 'own', 'debt', 'deficit', 'pool0', 'savings', 'varPool']


def reference(snap, today):
    tmp = SPEC / '.out' / 'budget_snapshot.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(snap, ensure_ascii=False), encoding='utf-8')
    out = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), str(tmp), today],
                         capture_output=True, text=True, encoding='utf-8', check=True, env={'PYTHONUTF8': '1', **__import__('os').environ}).stdout
    line = [x for x in out.splitlines() if x.startswith('JSON ')]
    check(line, f'еталон не надрукував JSON для {today}')
    return json.loads(line[-1][5:])


def math(page):
    base = json.loads(FIX.read_text(encoding='utf-8'))
    check(page.evaluate("typeof window.periodBudget==='function'"), 'window.periodBudget не функція')
    for today, debt in CASES:
        snap = json.loads(json.dumps(base))
        if debt is not None:
            snap['accounts'][1]['debt'] = debt
        ref = reference(snap, today)
        js = page.evaluate("([t,s])=>periodBudget(t,s.salary,s.accounts,s.fixed,s.credits,s.salary.savings_pct)", [today, snap])
        tag = f'{today}' + (f', борг {debt}' if debt is not None else '')
        check(js['payout']['date'] == ref['payout']['date'] and js['payout']['kind'] == ref['payout']['kind'],
              f'{tag}: виплата JS {js["payout"]}, еталон {ref["payout"]}')
        check(abs(js['payout']['amount'] - ref['payout']['amount']) <= 0.01, f'{tag}: сума виплати JS {js["payout"]["amount"]}, еталон {ref["payout"]["amount"]}')
        check(js['end'] == ref['end'], f'{tag}: кінець періоду JS {js["end"]}, еталон {ref["end"]}')
        jo = [(o['date'], o['name'], round(o['amount'], 2)) for o in js['obligations']]
        ro = [(o['date'], o['name'], round(o['amount'], 2)) for o in ref['obligations']]
        check(jo == ro, f'{tag}: обовʼязкові JS {jo}, еталон {ro}')
        for k in NUMS:
            check(abs(js[k] - ref[k]) <= 0.01, f'{tag}: {k} JS {js[k]}, еталон {ref[k]}')


CHECKS = [
    ('Бюджет періоду як в еталоні (5 випадків)', 'desktop', math),
]
