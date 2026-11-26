"""Перевірка відповіді family-status: підсумки дорівнюють сумі показаних рядків і числа збігаються з розділами бота.

Два режими:
  python scripts/verify_family_status.py
      Локальний прогін на синтетичній фікстурі бота (node spec/family-status-fixture.mjs): та сама вхідна
      база дає і відповідь функції, і текст розділів бота «Баланс» та «Картки». Таблиці бота розбираються
      з тексту (як їх бачить людина), а не беруться з тих самих чисел.
  python scripts/verify_family_status.py --json captured.json
      Збережена відповідь справжньої функції: лише внутрішні тотожності (без бота). Файл не комітити.

Код виходу 0, якщо розбіжностей немає.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACES = '    '
fails = []
checks = 0


def check(label, got, want, tol=0.0):
    global checks
    checks += 1
    ok = (got is None and want is None) or (got is not None and want is not None and abs(got - want) <= tol + 1e-9)
    print(f"{'OK  ' if ok else 'FAIL'} {label}: {got} vs {want}" + (f' (допуск {tol})' if tol else ''))
    if not ok:
        fails.append(label)


def num(text):
    t = text.strip()
    for ch in SPACES:
        t = t.replace(ch, '')
    if not t:
        return None
    return float(t.replace(',', '.'))


def internal(s):
    """Тотожності всередині відповіді: калькулятор над показаними числами."""
    acc = s['accounts']
    unassigned = s['unassigned_own'] or 0
    check('Разом власні = сума рядків + без рахунку', s['accounts_total']['own'], sum(a['own'] for a in acc) + unassigned)
    check('Разом борг = сума рядків', s['accounts_total']['debt'], sum(a['debt'] for a in acc))
    avail = [a['available'] for a in acc if a['available'] is not None]
    check('Разом доступно = сума рядків', s['accounts_total']['available'], sum(avail) if avail else None)
    own_pos = max(0, sum(max(0, a['own']) for a in acc) + unassigned)
    check('Власні (як у «Баланс») = сума додатних рядків + без рахунку, не менше 0', s['own_total'], own_pos)
    check('Кредитні = сума боргу рядків', s['credit_debt_total'], sum(a['debt'] for a in acc))
    check('Баланс = Власні - Кредитні', s['balance'], s['own_total'] - s['credit_debt_total'])
    pays = s['payments_until_payday']
    check('Платежі до виплати: разом = сума рядків', s['payments_until_payday_total'], sum(p['amount'] for p in pays))
    if s['next_payday']:
        bad = [p for p in pays if not (s['today'] <= p['date'] < s['next_payday'])]
        check('Платежі до виплати: дати в [сьогодні; день виплати)', len(bad), 0)
        # Рушій рахує «вільні до виплати» з копійок, рядки показані в гривнях: допуск лише на округлення показаних рядків
        tol = 0.5 * (len(acc) + len(pays) + 1) + 1e-9
        check('Вільні до виплати = Власні - платежі до виплати', s['free_until_payday'], s['own_total'] - s['payments_until_payday_total'], tol)
    b = s['budget']
    if b and b['daily'] is not None:
        check('Бюджет: на день є лише за додатного залишку', 1 if b['left'] > 0 and b['left_days'] > 0 else 0, 1)
    secret_like = [k for k in json.dumps(s, ensure_ascii=False).split('"') if re.search(r'token|description|mono_account_id|user_id', k)]
    check('У відповіді немає токенів, описів операцій і службових id', len(secret_like), 0)


def pre_lines(block):
    m = re.search(r'<pre>(.*?)</pre>', block, re.S)
    return m.group(1).split('\n') if m else []


def top_table(sections):
    out = {}
    for line in pre_lines('\n'.join(sections['top'])):
        m = re.match(r'^(.*?\S)\s{2,}(-?[\d' + SPACES + r',]+)$', line)
        if m:
            out[m.group(1).strip()] = num(m.group(2))
    return out


def cards_table(sections):
    lines = pre_lines('\n'.join(sections['cards']))
    head = lines[0]
    cols = ['Власні', 'Борг', 'Доступно']
    edges = [head.index(c) + len(c) for c in cols]
    rows, pending = [], None
    for line in lines[1:]:
        name_part = line[:head.index('Власні')].rstrip()
        cells = []
        start = len(name_part)
        for e in edges:
            cells.append(num(line[start:e]) if len(line) > start else None)
            start = e
        if all(c is None for c in cells):
            pending = line.strip()  # довга назва окремим рядком, числа рядком нижче
            continue
        rows.append((pending or name_part.strip(), cells))
        pending = None
    return rows


def bot_parity(s, sections):
    top = top_table(sections)
    check('«Баланс»: Власні', s['own_total'], top.get('Власні'))
    check('«Баланс»: Кредитні', s['credit_debt_total'], top.get('Кредитні'))
    check('«Баланс»: Баланс', s['balance'], top.get('Баланс'))
    b = s['budget']
    left = next(((k, v) for k, v in top.items() if k.startswith('Лишилось до') or 'перевитрати до' in k.lower()), None)
    check('«Баланс»: рядок залишку бюджету є (порівняння не порожнє)', 1 if left and b else 0, 1)
    if left and b:
        sign = 1 if left[0].startswith('Лишилось') else -1
        check(f'«Баланс»: {left[0]}', b['left'], sign * left[1])
        check('«Баланс»: дата кінця періоду бюджету', 1 if left[0].endswith(b['end'][8:10] + '.' + b['end'][5:7]) else 0, 1)
        daily = next((v for k, v in top.items() if k.startswith('На день,')), None)
        check('«Баланс»: На день до кінця періоду', b['daily'], daily)
    short = next((v for k, v in top.items() if k.startswith('Не вистачає до')), None)
    free = s['free_until_payday']
    check('«Баланс»: Не вистачає до виплати', -free if free is not None and free < 0 else None, short)
    rows = cards_table(sections)
    acc = s['accounts']
    body = [r for r in rows if r[0] not in ('Разом', 'Без рахунку')]
    check('«Картки»: кількість рахунків', len(body), len(acc))
    for (name, (own, debt, avail)), a in zip(body, acc):
        check(f'«Картки» {name}: назва', 1 if name == a['name'] else 0, 1)
        check(f'«Картки» {name}: власні', a['own'], own)
        check(f'«Картки» {name}: борг', a['debt'], debt or 0)
        check(f'«Картки» {name}: доступно', a['available'], avail)
    un = next((r for r in rows if r[0] == 'Без рахунку'), None)
    check('«Картки»: Без рахунку', s['unassigned_own'], un[1][0] if un else None)
    tot = next(r for r in rows if r[0] == 'Разом')
    check('«Картки»: Разом власні', s['accounts_total']['own'], tot[1][0])
    check('«Картки»: Разом борг', s['accounts_total']['debt'], tot[1][1])
    check('«Картки»: Разом доступно', s['accounts_total']['available'], tot[1][2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', help='збережена відповідь family-status (лише внутрішні тотожності)')
    ap.add_argument('--date', help='дата фікстури YYYY-MM-DD (локальний прогін)')
    a = ap.parse_args()
    if a.json:
        data = json.loads(Path(a.json).read_text(encoding='utf-8'))
        internal(data)
    else:
        cmd = ['node', str(ROOT / 'spec' / 'family-status-fixture.mjs')] + ([a.date] if a.date else [])
        out = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=True, cwd=ROOT).stdout
        data = json.loads(out)
        check('HTTP 200 на підписаний GET', data['httpStatus'], 200)
        internal(data['status'])
        bot_parity(data['status'], data['sections'])
    print(f'\nПеревірок {checks}, розбіжностей {len(fails)}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
