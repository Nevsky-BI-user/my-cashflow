# Математика зарплати: JS-функції з index.html проти еталону scripts/salary_check.py
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from helpers import ROOT, check

RATE, YEAR, MONTH, COUNT = 102000, 2026, 9, 4
NAMES = ['getDow', 'adjSal', 'wdRange', 'wdMonth', 'salaryParts']
LINE = re.compile(r'^(advance|salary)\s+(\d{4})-(\d{2})-(\d{2}) period \S+ (\d+)\.\.(\d+) wd (\d+)/(\d+) amount ([\d.]+)$')


def reference():
    out = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'salary_check.py'), str(RATE), str(YEAR), str(MONTH), str(COUNT)],
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for ln in out.splitlines():
        m = LINE.match(ln.strip())
        if m:
            k, y, mo, d, d1, d2, wd, tot, amt = m.groups()
            rows.append((k, int(y), int(mo), int(d), int(d1), int(d2), int(wd), int(tot), float(amt)))
    check(len(rows) == COUNT * 2, f'еталон дав {len(rows)} рядків замість {COUNT * 2}')
    return rows


def js_source():
    """Вирізає визначення функцій з index.html (const X=...; до наступного const або function)."""
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    parts = []
    for n in NAMES:
        m = re.search(r'const ' + n + r'=.*?;(?=const |function )', html)
        check(m, f'у index.html не знайдено const {n}=')
        parts.append(m.group(0))
    return '\n'.join(parts)


def math(page):
    ref = reference()
    cfg = {'rate': RATE, 'split_day': 15, 'advance_day': 21, 'salary_day': 6}
    months = [(YEAR + (MONTH - 1 + i) // 12, (MONTH - 1 + i) % 12) for i in range(COUNT)]
    if page.evaluate("typeof salaryParts==='function'&&typeof wdRange==='function'"):
        got = page.evaluate("([cfg,ms])=>ms.map(([y,m])=>salaryParts(cfg,y,m))", [cfg, months])
    else:
        got = page.evaluate("([src,cfg,ms])=>{const f=new Function(src+';return salaryParts');const sp=f();return ms.map(([y,m])=>sp(cfg,y,m))}",
                            [js_source(), cfg, months])
    js = []
    for (y, m0), r in zip(months, got):
        for k in ('advance', 'salary'):
            p = r[k]
            js.append((k, y, m0 + 1, p['day'], p['d1'], p['d2'], p['wd'], p['total'], p['amount']))
    check(len(js) == len(ref), f'JS дав {len(js)} рядків, еталон {len(ref)}')
    for a, b in zip(ref, js):
        check(a[:8] == b[:8], f'розбіжність дат/днів: еталон {a[:8]}, JS {b[:8]}')
        check(abs(a[8] - b[8]) <= 0.01, f'{a[0]} {a[1]}-{a[2]:02d}: еталон {a[8]}, JS {b[8]}')


def fixed_parity(page):
    # Синтетичні суми й відомі дати: без snapshot з приватними даними.
    base = {'split_day': 15, 'advance_day': 21, 'salary_day': 6,
            'advance_amount': 30000, 'salary_amount': 40000}
    cases = [
        ('zero', {**base, 'rate': 0}, '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [40000, 30000, 40000]),
        ('missing rate', base, '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [40000, 30000, 40000]),
        ('negative rate', {**base, 'rate': -1}, '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [40000, 30000, 40000]),
        ('missing amounts', {'rate': 0, 'split_day': 15, 'advance_day': 21, 'salary_day': 6},
         '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [0, 0, 0]),
        ('positive rate', {**base, 'rate': 102000}, '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [51000, 51000, 51000]),
        ('weekend and month', {**base, 'rate': 0}, '2026-11-21', ['2026-11-20', '2026-12-07', '2026-12-21'], [30000, 40000, 30000]),
        ('year boundary', {**base, 'rate': 0}, '2026-12-31', ['2026-12-21', '2027-01-06', '2027-01-21'], [30000, 40000, 30000]),
        ('positive year boundary', {**base, 'rate': 102000}, '2026-12-31',
         ['2026-12-21', '2027-01-06', '2027-01-21'], [48782.61, 53217.39, 53428.57]),
        ('string amounts', {**base, 'rate': None, 'advance_amount': '30000.125', 'salary_amount': '40000.125'},
         '2026-10-10', ['2026-10-06', '2026-10-21', '2026-11-06'], [40000.125, 30000.125, 40000.125]),
    ]
    inputs = [{'today': today, 'snap': {'accounts': [{'kind': 'debit', 'balance': 100000, 'debt': 0}],
               'fixed': [], 'credits': [], 'salary': cfg}} for _, cfg, today, _, _ in cases]
    out = subprocess.run(['node', str(ROOT / 'spec' / 'ts_salary.mts')], input=json.dumps(inputs),
                         capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
    ts_rows = json.loads(out.stdout)
    src = js_source()
    with tempfile.TemporaryDirectory(prefix='cashflow-salary-') as tmp:
        fixture = Path(tmp) / 'synthetic.json'
        for (name, cfg, today, dates, amounts), inp, ts in zip(cases, inputs, ts_rows):
            kinds = ['advance' if date.fromisoformat(d).day >= 15 else 'salary' for d in dates]
            expected = [dict(date=d, kind=k, amount=a) for d, k, a in zip(dates, kinds, amounts)]
            browser = page.evaluate('''([src,cfg,expected])=>{
                const sp=new Function(src+';return salaryParts')();
                return expected.map(p=>{const [y,m]=p.date.split('-').map(Number),part=sp(cfg,y,m-1)[p.kind];
                    return {date:y+'-'+String(m).padStart(2,'0')+'-'+String(part.day).padStart(2,'0'),kind:p.kind,amount:part.amount}});
            }''', [src, cfg, expected])
            check(browser == expected, f'{name}: browser {browser} != {expected}')
            check([ts['current'], ts['next'], ts['after']] == expected, f'{name}: TypeScript {ts} != {expected}')
            fixture.write_text(json.dumps(inp['snap']), encoding='utf-8')
            # Python обчислює поточний період від дня перед останньою виплатою.
            before = str(date.fromisoformat(dates[0]) - timedelta(days=1))
            out = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'budget_pool.py'), str(fixture), before, today],
                                 capture_output=True, text=True, encoding='utf-8', check=True, timeout=30,
                                 env={**os.environ, 'PYTHONUTF8': '1'})
            py = json.loads(next(line[5:] for line in out.stdout.splitlines() if line.startswith('JSON ')))
            check(py['payout'] == expected[0], f'{name}: Python current {py["payout"]} != {expected[0]}')
            check(py['nextPayout'] == expected[1], f'{name}: Python next {py["nextPayout"]} != {expected[1]}')
            after = next(e for e in py['timeline'] if e['kind'] == 'payout' and e['date'] == dates[2])
            check(after['amount'] == amounts[2] and after['payout'] == kinds[2], f'{name}: Python after {after}')


CHECKS = [
    ('Зарплата 2026-09..12 як в еталоні', 'desktop', math),
    ('Фіксовані виплати: browser / TypeScript / Python', 'desktop', fixed_parity),
]
