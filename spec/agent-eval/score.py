# Оцінка сліпого заміру (набір 14.11.2026). Правила зафіксовано ДО першого прогону:
# - правильно: спостережене збігається з однією з альтернатив розмітки (кожен обовʼязковий виклик знайдено;
#   зайві виклики допускаються лише поруч із правильними);
# - частково: відповідь із числами, де є частина обовʼязкових викликів і немає хибних;
# - впевнено хибно: відповідь із числами не на те питання (інший розділ, період, категорія чи пошук);
# - безпечний промах: уточнення, відмова, «не питання», відхилення кодом (вигадана категорія, період),
#   а також голосова пропозиція запису там, де його не просили (без «✅ Так, додати» нічого не пишеться);
# - текстовий запис там, де його не просили, впевнено хибний: текстом бот пише операцію одразу;
# - збій API (ключ, кредит, перевантаження після повторів) не оцінюється: прогін із ним відкидається.
# Розріз за мовою, каналом і маршрутом; інтервал Вілсона 95 %.
# Не сліпе: після перегляду набору правились маршрут запису (voice-entry: CHANGE, російські слова, дата на
# початку) і промпт моделі (вид відмови add_request для «додай каву»). Тож маршрут і пункти #13, #80 завищені;
# решта вибору моделі сліпа (інших правок промпту після перегляду набору не було).
# Після першого прогону 14.11 (09:48, 72/80) правились: період рахує код (period, month), апостроф у назвах категорій,
# розстрочки, «аванс» як виплата і загальне питання про гроші в промпті. Тож #8, #11, #22, #42, #50, #63 і всі періоди
# завищені: повторний прогін цього набору лише регресійний, чесний замір потребує нового набору.
# Запуск: python spec/agent-eval/score.py [шлях до run-*.jsonl]  (без шляху: найновіший у .local/agent-eval)
import json
import math
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LABELS = json.loads((HERE / 'labels-2026-11-14.json').read_text(encoding='utf-8'))
SHA = 'bf444f03cfc93f4fc84b64af55e09420ecfcbaeeb2af0059a51c798e8a56909f'
assert LABELS['sha256'] == SHA

def norm(s):
    return unicodedata.normalize('NFKC', str(s or '')).lower().replace("'", 'ʼ').replace('’', 'ʼ').strip()


def observed(r):
    """Що побачив би користувач, як перелік викликів."""
    if r['route'] == 'entry':
        return 'entry', [{'t': 'entry'}]
    if r['route'] in ('menu', 'help'):
        return 'refusal', [{'t': 'not_question'}]
    res = r.get('result') or {}
    kind = res.get('kind')
    if kind == 'answer':
        return ('answer', r['executed']) if r['executed'] else ('rejected', [{'t': 'rejected'}])
    if kind == 'clarify':
        return 'refusal', [{'t': 'clarify'}]
    if kind == 'not_question':
        return 'refusal', [{'t': 'not_question'}]
    if kind == 'off_topic':
        # вид відмови з сирого виклику моделі
        ns = [c for c in r['raw'] if c['name'] == 'not_supported']
        k = (ns[0]['input'] or {}).get('kind') if ns else 'off_topic'
        return 'refusal', [{'t': {'not_a_question': 'not_question'}.get(k, k)}]
    return 'refusal', [{'t': 'error'}]


def call_ok(want, got):
    if want['t'] != got['t']:
        return False
    t = want['t']
    if t in ('entry', 'clarify', 'not_question', 'off_topic', 'add_request', 'change_request', 'finance_unsupported'):
        return True
    if t == 'balance':
        return want['section'] == got['section']
    if t == 'budget':
        return norm(want.get('category')) == norm(got.get('category'))
    # spending
    if want.get('type', 'expense') != got.get('type'):
        return False
    if want.get('nocat'):
        return not got.get('category') and not got.get('search')
    if got.get('from') not in want['from'] or got.get('to') != want['to']:
        return False
    wc, ws = want.get('category'), want.get('search')
    gc, gs = got.get('category'), norm(got.get('search')) if got.get('search') else None
    if wc:
        if norm(gc) not in {norm(c) for c in wc} or (gs and not ws):
            return False
    elif gc:
        return False
    if ws:
        if not gs or len(gs) < 3 or not any(norm(s) in gs or gs in norm(s) for s in ws):
            return False
    elif gs:
        return False
    return True


def matches(alt, got):
    used = set()
    for w in alt:
        hit = next((i for i, g in enumerate(got) if i not in used and call_ok(w, g)), None)
        if hit is None:
            return False
        used.add(hit)
    return True


def grade(n, r):
    alts = LABELS['labels'][str(n)]
    kind, got = observed(r)
    if any(matches(a, got) for a in alts):
        return 'correct'
    if kind == 'entry' and r['channel'] == 'text':
        return 'wrong'
    if kind == 'answer':
        wants = [w for a in alts for w in a]
        good = [g for g in got if any(call_ok(w, g) for w in wants)]
        return 'partial' if good and len(good) == len(got) else 'wrong'
    return 'safe_miss'


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def line(name, rows):
    n = len(rows)
    c = Counter(g for _, g in rows)
    lo, hi = wilson(c['correct'], n)
    wlo, whi = wilson(c['wrong'], n)
    return (f'{name:<16} n={n:>3}  правильно {c["correct"]:>3} ({100 * c["correct"] / n:5.1f} %, {100 * lo:.0f}-{100 * hi:.0f})'
            f'  частково {c["partial"]:>2}  впевнено хибно {c["wrong"]:>2} ({100 * c["wrong"] / n:4.1f} %, до {100 * whi:.0f})'
            f'  безпечний промах {c["safe_miss"]:>2}')


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        runs = sorted((ROOT / '.local' / 'agent-eval').glob('run-*.jsonl'))
        if not runs:
            sys.exit('Немає прогонів: спершу node spec/agent-eval/run.mjs')
        path = runs[-1]
    recs = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert sorted(r['n'] for r in recs) == list(range(1, 81)), 'прогін неповний'
    broken = [r['n'] for r in recs if r['route'] == 'agent' and r.get('status') != 200]
    if broken:
        sys.exit(f'прогін зіпсований збоями API ({len(broken)}: {broken[:10]}); виправте ключ чи кредит і повторіть')
    rows = [(r, grade(r['n'], r)) for r in recs]
    print(f'прогін: {path.name}, модель {recs[0].get("model")}')
    print(line('усі', rows))
    for key in ('lang', 'channel', 'route'):
        groups = defaultdict(list)
        for r, g in rows:
            groups[r[key]].append((r, g))
        for k in sorted(groups):
            print(line(f'{key}={k}', groups[k]))
    tin = sum((r.get('usage') or {}).get('input_tokens', 0) for r in recs)
    tout = sum((r.get('usage') or {}).get('output_tokens', 0) for r in recs)
    calls = sum(1 for r in recs if r['route'] == 'agent')
    # Ціни Haiku 4.5: $1 за мільйон вхідних, $5 за мільйон вихідних токенів
    cost = tin / 1e6 * 1 + tout / 1e6 * 5
    if calls:
        print(f'токени: вхід {tin}, вихід {tout}; ${cost:.4f} за {calls} викликів, ${cost / calls:.5f} за питання')
    print(f'повтори через перевантаження: {sum(r.get("retries", 0) for r in recs)}')
    print('\nне правильно:')
    for r, g in rows:
        if g != 'correct':
            kind, got = observed(r)
            print(f'  #{r["n"]:<3} {g:<9} [{r["lang"]}/{r["channel"]}/{r["route"]}] {r["q"]}  →  {json.dumps(got, ensure_ascii=False)}')


if __name__ == '__main__':
    main()
