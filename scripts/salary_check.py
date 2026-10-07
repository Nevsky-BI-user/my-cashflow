# Еталон розрахунку зарплати за робочими днями (перевірка JS-логіки в index.html).
# Правила: робочі дні = Пн-Пт; аванс 21-го за 1..split поточного місяця,
# зарплата 6-го за split+1..кінець ПОПЕРЕДНЬОГО місяця; сума = ставка / РД(місяця періоду) * РД(періоду);
# день виплати з суботи переноситься на пʼятницю, з неділі на понеділок.
# Запуск: python scripts/salary_check.py [ставка] [рік] [місяць] [кількість місяців]
import calendar, sys
from datetime import date, timedelta

rate = float(sys.argv[1]) if len(sys.argv) > 1 else 102000
year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
month = int(sys.argv[3]) if len(sys.argv) > 3 else 9
count = int(sys.argv[4]) if len(sys.argv) > 4 else 4
SPLIT, ADV_DAY, SAL_DAY = 15, 21, 6


def wd(y, m, d1, d2):
    return sum(1 for d in range(d1, d2 + 1) if date(y, m, d).weekday() < 5)


def adj(y, m, d):
    w = date(y, m, d).weekday()
    return d - 1 if w == 5 else d + 1 if w == 6 else d


def part(y, m, d1, d2):
    total = wd(y, m, 1, calendar.monthrange(y, m)[1])
    worked = wd(y, m, d1, d2)
    return total, worked, round(rate / total * worked, 2)


for i in range(count):
    y, m = divmod((year * 12 + month - 1) + i, 12)
    m += 1
    py, pm = divmod((y * 12 + m - 2), 12)
    pm += 1
    t, w, a = part(y, m, 1, SPLIT)
    print(f"advance {y}-{m:02d}-{adj(y, m, ADV_DAY):02d} period {y}-{m:02d} 1..{SPLIT} wd {w}/{t} amount {a:.2f}")
    t, w, a = part(py, pm, SPLIT + 1, calendar.monthrange(py, pm)[1])
    print(f"salary  {y}-{m:02d}-{adj(y, m, SAL_DAY):02d} period {py}-{pm:02d} {SPLIT + 1}..{calendar.monthrange(py, pm)[1]} wd {w}/{t} amount {a:.2f}")
