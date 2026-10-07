# Математика зарплати: JS-функції з index.html проти еталону scripts/salary_check.py
import re
import subprocess
import sys

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


CHECKS = [
    ('Зарплата 2026-09..12 як в еталоні', 'desktop', math),
]
