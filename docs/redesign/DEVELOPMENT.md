# Локальна розробка й перегляд ескізів

Продакшен лишається статичним застосунком без npm і кроку збірки.
Інструменти Python ізольовані в `.venv/` і зафіксовані в `requirements-dev.txt`.
Перевірене середовище цього етапу: Windows, Python 3.13, Node 24.

## Початкове налаштування

```powershell
powershell -NoProfile -File scripts/setup-dev.ps1
```

Скрипт створює `.venv`, встановлює зафіксовані залежності й готує Chromium.
Глобальні Python-пакети не змінює. Node потрібний наявним тестам TS-ядра.

## Перегляд

Основний перегляд — справжній застосунок із демоданими (`app`, також за замовчуванням).
`minimal-concepts.html` і `concepts.html` — відхилені архівні напрями.
Для HTTP-превʼю:

```powershell
.\.venv\Scripts\python.exe scripts/dev-preview.py --target app
```

Адреса друкується в терміналі. Сервер доступний лише на `127.0.0.1`;
автоматично завершується через 20 хвилин або Ctrl+C. Час можна змінити
параметром `--seconds` (до години). Сервер не відкриває корінь репозиторію.
App-preview використовує наявний `spec/preview.py`: демо, Supabase і SW вимкнені.
Ескізи мають вигадані дані й не виконують мережевих запитів.

## Перевірки

```powershell
.\.venv\Scripts\python.exe spec/run.py
.\.venv\Scripts\python.exe spec/run.py --only cash
.\.venv\Scripts\python.exe spec/run.py --only fixedpaid
.\.venv\Scripts\python.exe spec/review_concepts.py
.\.venv\Scripts\python.exe spec/review_minimal.py
node --test spec/forecast-model.test.cjs
node --test spec/next-period.test.cjs
node --test spec/finance-projection.test.cjs spec/finance-message.test.cjs spec/telegram-finance.test.cjs spec/canonical-copy.test.cjs spec/frontend-data.test.cjs
.\.venv\Scripts\python.exe spec/release_smoke.py --version v159
.\.venv\Scripts\python.exe scripts/build-design-preview.py
git diff --check
```

Логи й скриншоти — тільки в ігнорованій `spec/.out/`. При звичайному
запуску runner закриває браузер і HTTP-сервер у `finally`; не застосовувати
`--keep` для автоматичних перевірок. Демо-тести не підтверджують роботу
Google OAuth, реальної БД, RLS або розгорнутих Edge Functions.

Активне фінансове ядро — `financeProjection` у `_shared/budget.ts` та його
точна автономна копія між маркерами `CANONICAL FINANCE PROJECTION` у
`index.html`. Python `scripts/budget_pool.py --finance` приймає масив
`[{data, options: {asof, through, scenario?}}]` через stdin і повертає JSON.
Нові екрани та Telegram використовують цю модель. `nextPeriodPlan`,
`periodBudget` і старі CLI залишені для сумісності та історичних перевірок.
Після зміни ядра потрібно синхронізувати вбудовану функцію та перевірити
повну відповідність результатів браузера, TS і Python на демоданих.

`review_concepts.py` відкриває ескіз як локальний файл і перевіряє пʼять
вкладок у двох темах на шести ширинах, діалоги та повернення фокуса.
Знімки й звіт зберігає в `spec/.out/redesign/`; Chromium закриває сам.

`review_minimal.py` перевіряє архівний мінімалістичний прототип.
`forecast-model.test.cjs` перевіряє незалежні приклади доступних коштів,
щоденного розподілу, кредитних сценаріїв та збереження копійок у прототипі.

Для перевірки inline-перегляду зібрати `minimal-preview.html`, обгорнути його
через `render.py` скіла visualize у `spec/.out/redesign/minimal-inline-rendered.html`
(для повторної генерації `--force`), потім виконати `spec/review_minimal_inline.py`.
Фінальний фрагмент містить модель і розмітку всередині; локальний сервер не потрібний.

## Скіли

Для поточного етапу вже встановлені й доступні: `model-orchestration`,
`frontend-design`, `emil-design-eng`, `react-ux-mechanics`, `webapp-testing`,
`ukrainian-ui-copy`, `supabase`; також `skill-installer` для майбутньої
потреби. Дублі не встановлювали. UX-аудит виконує `ux-baseline-auditor`.
Корпоративні сервіси й інші репозиторії для цієї роботи не потрібні.
