# Промпти для Claude Code — Сімейний Кешфлоу

Кожен промпт — окрема задача. Виконувати строго послідовно.
Після кожного кроку — перевірити результат через валідацію з CLAUDE.md.

---

## ФАЗА 1: Дизайн UI (завершено)

Промпти 1.0–1.7+ — у git-історії.

---

## ФАЗА 2: Supabase

### 2.1 — Supabase JS client + закритий логін

(виконано)

### 2.2 — SQL-схема з RLS

(виконано — `supabase-schema.sql`)

### 2.3 — Storage bucket для чеків

(виконано)

### 2.4 — Читання категорій, кредитів, цілей

(виконано)

### 2.5 — Читання транзакцій

(виконано)

### 2.6 — Додавання транзакції (кнопка "+")

(виконано)

### 2.7 — Бюджет з реальними даними

(виконано)

### 2.8 — Перевірка безпеки

(виконано)

### 2.9 — Google OAuth + email whitelist (NEW)

```
Прочитай CLAUDE.md (секції "БЕЗПЕКА", "Авторизація — Google OAuth + Email/Password (fallback)", "Email whitelist — двошаровий захист", "Auth-логіка — інваріанти").

Контекст:
- Whitelist: gotnewmess@gmail.com, kovtunenko.yulchik@gmail.com
- Залишити email/password як fallback
- Supabase проєкт: lisedsqwdzshsxydghag.supabase.co
- supabase-js v2 у браузері — автоматично PKCE flow + detectSessionInUrl

Завдання:

1. У <script> на самому початку (після рядка з createElement:h,Fragment) додай:
   const ALLOWED_EMAILS=['gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com'];

2. Повністю переписати LoginScreen — додати кнопку "Увійти через Google" + зберегти форму email/password:
   - Google-кнопка зверху (білий фон, multi-color G SVG, текст "Увійти через Google")
   - Розділювач "або"
   - Поля email + password з кнопкою "Увійти"
   - Prop authError — показувати під формою якщо є
   - googleLogin: const redirectTo=window.location.origin+window.location.pathname;
     sb.auth.signInWithOAuth({provider:'google',options:{redirectTo}})

3. В App додати:
   - useState authError=''
   - У useEffect для session — функцію checkSession(s) яка перевіряє email проти ALLOWED_EMAILS, при невідповідності → sb.auth.signOut() + setAuthError + setSession(null)
   - Викликати checkSession і у getSession().then(), і в onAuthStateChange
   - Передати authError у LoginScreen

4. Інкрементуй CACHE у sw.js (з v105 до v106).

5. Перевірки після змін:
   grep -c "ALLOWED_EMAILS" index.html       # ≥ 2
   grep -c "signInWithOAuth" index.html      # = 1
   grep -c "signInWithPassword" index.html   # = 1
   grep -c "is_family_member" index.html     # = 0 (це SQL, не JS)
   node -e "..."  # синтаксис JS (з CLAUDE.md крок 2)

ВАЖЛИВО:
- НЕ змінювати інше, окрім LoginScreen + auth-блок у App + ALLOWED_EMAILS
- Зберегти існуючий стиль коду (compact h(), без JSX, semicolons, без пробілів між токенами)
- Не зловживати рефакторингом — лише точкові вставки
- НЕ додавати на фронтенд "Забули пароль" / "Реєстрація"
```

### 2.10 — SQL міграція: email whitelist у RLS (NEW)

```
Прочитай CLAUDE.md (секція "Email whitelist — двошаровий захист", "Row Level Security (RLS) — підсумок").

Контекст:
- Файл міграції готовий: supabase-migrations/02-family-whitelist.sql
- Whitelist: gotnewmess@gmail.com, kovtunenko.yulchik@gmail.com

Завдання:

1. Створити папку supabase-migrations/ (якщо нема).
2. Покласти туди файл 02-family-whitelist.sql.
3. Зробити commit: chore: add RLS family whitelist migration
4. Інструкція користувачу (в README або terminal echo):
   "Запусти SQL з supabase-migrations/02-family-whitelist.sql у Supabase Dashboard → SQL Editor → Run."

Після виконання SQL — тест у браузері:
- Залогінитися як gotnewmess@gmail.com → дані видно
- Залогінитися як stranger@gmail.com → дані порожні (RLS блокує), на фронті показано "Доступ закритий"
```

### 2.11 — Google Cloud Console + Supabase Dashboard налаштування (ручні кроки)

```
Це НЕ для Claude Code. Це ручні кроки. Виконуються один раз.

ЧАСТИНА A — Google Cloud Console:

1. https://console.cloud.google.com → створити новий проєкт "Family Cashflow".
2. APIs & Services → OAuth consent screen:
   - User Type: External
   - App name: Family Cashflow
   - User support email: gotnewmess@gmail.com
   - Developer contact: gotnewmess@gmail.com
   - Scopes: email, profile, openid (за замовчуванням)
   - Test users: gotnewmess@gmail.com, kovtunenko.yulchik@gmail.com
3. APIs & Services → Credentials → Create Credentials → OAuth Client ID:
   - Application type: Web application
   - Name: Family Cashflow Web
   - Authorized JavaScript origins:
     - https://<github-username>.github.io
   - Authorized redirect URIs:
     - https://lisedsqwdzshsxydghag.supabase.co/auth/v1/callback
4. Зберегти. Скопіювати Client ID та Client Secret.

ЧАСТИНА B — Supabase Dashboard:

1. https://supabase.com/dashboard → проєкт lisedsqwdzshsxydghag.
2. Authentication → Providers → Google:
   - Enable
   - Client ID: <вставити>
   - Client Secret: <вставити>
   - Save
3. Authentication → URL Configuration:
   - Site URL: https://<github-username>.github.io/<repo-name>/
   - Redirect URLs (один на рядок):
     https://<github-username>.github.io/<repo-name>/
     https://<github-username>.github.io/<repo-name>/**
   - Save
4. Authentication → Settings (Auth Configuration):
   - "Enable Email Signups" — OFF (sign up через email/password вимкнено)
   - "Confirm email" — за бажанням (для Google не використовується)

ЧАСТИНА C — SQL міграція:

5. SQL Editor → New Query → вставити вміст supabase-migrations/02-family-whitelist.sql → Run.

ЧАСТИНА D — Перевірка:

6. Відкрити PWA → Login Screen → "Увійти через Google".
7. Google consent screen → вибрати gotnewmess@gmail.com → дозволити.
8. Має повернутися на додаток, авторизований, з даними.
9. Спробувати залогінитися сторонньою адресою → має показати "Доступ закритий" і кнопку Logout.
10. У БД: select count(*) from auth.users; — має бути 2 (обидва whitelist-користувачі після першого входу).
```

### 2.12 — Фінальна перевірка безпеки після Google OAuth (NEW)

```
Прочитай CLAUDE.md (секція "БЕЗПЕКА").

Тести:

1. Сторонній акаунт:
   - Залогінитися Google-акаунтом, якого нема в whitelist.
   - Перевірити: фронт показує "Доступ закритий" + signOut автоматично.
   - У БД (SQL Editor): select email from auth.users; — сторонній email у списку (це нормально, його блокує RLS).
   - Видалити запис: delete from auth.users where email = '<sторонній>'; (опціонально).

2. RLS-bypass спроба:
   - Залогінитися як стороннім.
   - У DevTools Console:
     fetch('https://lisedsqwdzshsxydghag.supabase.co/rest/v1/transactions?select=*', {
       headers: {
         'apikey': 'ANON_KEY',
         'Authorization': 'Bearer ' + localStorage.getItem('sb-...-auth-token').access_token
       }
     }).then(r => r.json()).then(console.log)
   - Очікувано: [] (порожній масив), RLS блокує.

3. Email/password fallback:
   - Створити вручну в Dashboard користувача з email gotnewmess@gmail.com та password.
   - Залогінитися через форму email/password.
   - Має працювати ідентично Google-логіну.

4. Whitelist enforcement:
   - Тимчасово прибрати email з is_family_member().
   - Залогінитися — на фронті дані порожні (RLS).
   - Повернути email назад → рефреш → дані повертаються.

5. PWA offline:
   - Перший раз залогінитися онлайн.
   - Вимкнути інтернет → відкрити додаток.
   - Сесія у localStorage — додаток відкривається (з кешу SW), але запити до Supabase падають (нормально).
```

---

## ФАЗА 3: Monobank API

### 3.1 — Edge Function: mono-webhook

(виконано — `supabase/functions/mono-webhook/index.ts`, коміт `04f19f0`)

### 3.2 — Edge Function: mono-backfill

(виконано — `supabase/functions/mono-backfill/index.ts`, коміт `d4de973`)
Підвантаження історії: `GET /personal/statement/{account}/{from}/{to}`, один запит (rate limit 1/60с), вікно ≤31 день, дедуп по `source_id`, JWT + email whitelist. Ідемпотентно.

### 3.3 — Реєстрація webhook + UI налаштувань

(виконано — `supabase/functions/mono-register/index.ts` + UI-модалка, коміт `f9d00f6`)
Шестерня в хедері → модалка «Monobank»: поле X-Token (write-only → `profiles.mono_token`), кнопки «Автооновлення» (mono-register) і «Історія 31 день» (mono-backfill). `mono-register` реєструє webhook у Mono, `MONO_WEBHOOK_SECRET` лишається серверним.

### 3.4 — Індикатор джерела в UI

(виконано — коміти `31562ea`, `dfdeb27`)
`buildMonth(y,m,txs)` вливає реальні транзакції з Supabase у таймлайн (`Потік`, `Останні`, `Найближчі`, тижні) + бюджет-агрегацію. `Row` показує бейдж джерела (mono/вручну/telegram) + MCC. Виправлено double-count кредитів у `pExp`.

**Ручні кроки після деплою фронтенду:**

- `supabase functions deploy mono-backfill mono-register`
- Секрети: `MONO_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`
- У застосунку: шестерня → ввести X-Token → «Автооновлення» → (пауза ~хв) → «Історія 31 день»

---

## ФАЗА 4: Telegram-бот (витрати)

Бот приватний: не публікувати в каталозі, не вмикати inline-режим. Привʼязка акаунта
тільки одноразовим кодом із застосунку, бо email/password-входу в проєкті немає
(`signInWithPassword` на фронтенді = 0, акаунти лише Google).

### 4.1 - Edge Function: telegram-webhook (текст) + привʼязка кодом

```
Прочитай CLAUDE.md (БЕЗПЕКА -> Telegram-бот).

1. Міграція 03-telegram-link.sql:
   alter table profiles add column telegram_link_code text,
                        add column telegram_link_expires timestamptz;
   RLS не чіпати: політика "family full" через is_family_member() уже покриває profiles.

2. UI (index.html, модалка «Інтеграції», блок Telegram):
   - статус: «Telegram привʼязано» / «не привʼязано» (profiles.telegram_chat_id is not null)
   - кнопка «Код для Telegram»: 6 цифр, update profiles set telegram_link_code, telegram_link_expires = now + 10 хв
   - показати «Надішліть боту: /start 123456 (діє 10 хв)»
   Інкрементувати CACHE у sw.js.

3. supabase/functions/telegram-webhook/index.ts (config.toml: verify_jwt = false):
   БЕЗПЕКА:
   a) header X-Telegram-Bot-Api-Secret-Token != env TELEGRAM_WEBHOOK_SECRET -> 403
   b) chat_id = message.chat.id; текст = message.text
   c) /start <code>: profiles where telegram_link_code = code and telegram_link_expires > now()
      знайдено -> update telegram_chat_id = chat_id, code/expires = null -> «Привʼязано до акаунту»
      ні -> «Код невірний або прострочений. Згенеруйте новий у застосунку.»
   d) решта: profiles where telegram_chat_id = chat_id (service_role)
      не знайдено -> «Доступ закритий. Згенеруйте код у застосунку і надішліть /start <код>.» -> 200

   ПАРСИНГ:
   e) текст /^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/
      «+» -> income, інакше expense; insert transactions (source='telegram', date = сьогодні за Europe/Kyiv)
      відповідь: «✅ Витрата: 250,00 ₴, кава»
   f) /balance -> доходи - витрати за поточний місяць (усі сімейні транзакції)
   g) /last -> останні 5 транзакцій
   h) /help і невідомий текст -> підказка формату
   Завжди відповідати 200, щоб Telegram не повторював апдейт; insert дедупити по source_id = 'tg:' + update_id.
   Сума без пробілів-роздільників: «1 250 кава» прочитається як 1 ₴ з описом «250 кава».

Приймання 4.1 наживо можливе лише після 4.3 (BotFather, секрети, setWebhook): до того код і
міграція перевіряються читанням і `deno check`.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 4.2 - Telegram-webhook: фото чеків

```
Прочитай CLAUDE.md.

Додати в telegram-webhook обробку message.photo:

1. file_id останнього елемента (найбільший розмір)
2. GET /getFile -> file_path -> завантажити байти
3. Upload у Storage receipts/{user_id}/{timestamp}.jpg (service_role, bucket приватний)
4. base64 -> Claude API (vision):
   модель у константі RECEIPT_MODEL. Старт: 'claude-haiku-4-5-20251001' (дешево).
   Якщо чеки читаються погано: 'claude-sonnet-5-5' (краще бачить дрібний друк, дорожче).
   system: «Розпізнай чек. Відповідай ТІЛЬКИ JSON: {amount, description, date}. Не чек -> {error}».
5. Парсити -> insert transactions (source='telegram', receipt_url = шлях у Storage, не signed URL:
   signed URL генерує фронтенд при перегляді)
6. Відповідь: «✅ 1 250,00 ₴, АТБ» або «❌ Не вдалося розпізнати»

Env: CLAUDE_API_KEY (додати)
```

### 4.3 - Реєстрація Telegram webhook

```
Прочитай CLAUDE.md.

supabase/functions/telegram-setup/index.ts (JWT + whitelist як у mono-register):
1. POST /setWebhook { url: <SUPABASE_URL>/functions/v1/telegram-webhook,
   secret_token: env TELEGRAM_WEBHOOK_SECRET, allowed_updates: ["message"] }
2. Повернути відповідь Telegram як є.

README-telegram.md:
1. @BotFather -> /newbot -> TOKEN. Не публікувати бота, не вмикати inline.
2. supabase secrets set TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=<uuid>
3. supabase functions deploy telegram-webhook telegram-setup
4. У застосунку: шестерня -> кнопка «Підключити бота» (invoke telegram-setup)
5. Шестерня -> «Код для Telegram» -> у боті /start <код>
```

---

## ФАЗА 5: Telegram-бот (доходи)

### 5.1 - Доходи + дедуплікація

```
Прочитай CLAUDE.md (Фаза 5).

Оновити telegram-webhook:

1. «+» на початку -> type='income' (є з 4.1, перевірити)
2. /income і /дохід: /^\/(income|дохід)\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/ -> type='income'
   відповідь: «✅ Дохід: 51 000,00 ₴, зарплата»
3. Дедуплікація з Monobank при type='income':
   select id, amount, date from transactions
   where source='mono' and type='income'
     and abs(amount - $1) < $1 * 0.01
     and date between $2 - 1 and $2 + 1
   є -> «⚠️ Схожий дохід уже є від Monobank (51 000 ₴, 06.04). Додати все одно? /yes»
   /yes -> вставити відкладений запис (тримати в profiles.telegram_pending jsonb, TTL 10 хв)
4. /last показує income і expense:
   «📋 Останні:
    06.04 +51 000 ₴ зарплата (mono)
    06.04 -250 ₴ АТБ (mono)
    05.04 -80 ₴ маршрутка (tg)»
```

---

## ФАЗА 6: Автокатегоризація

### 6.1 - Edge Function: categorize

```
Прочитай CLAUDE.md (Фаза 6).

supabase/functions/categorize/index.ts (виклик лише з service_role: перевіряти Bearer == SERVICE_ROLE):

1. POST { transaction_id }
2. Завантажити транзакцію + категорії (service_role)
3. hash = sha256(description.toLowerCase().trim()) через Web Crypto
4. categorization_cache по hash
   є -> update transactions set category_id, auto_categorized=true -> return { category_id, from_cache: true }
5. Claude API: модель у константі CATEGORIZE_MODEL = 'claude-haiku-4-5-20251001', max_tokens 20
   system: «Категоризуй. Категорії: {id:name,...}. Відповідай ТІЛЬКИ числом: id.»
   user: «'{description}', MCC: {mcc}, {amount} грн»
6. parseInt; id не з переліку -> не категоризувати, залогувати
7. insert categorization_cache
8. update transactions
9. return { category_id }

Env: CLAUDE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 6.2 - Виклик з webhook-ів

```
Прочитай CLAUDE.md.

У mono-webhook, mono-backfill і telegram-webhook після insert транзакції без category_id:

fetch(`${SUPABASE_URL}/functions/v1/categorize`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` },
  body: JSON.stringify({ transaction_id })
}).catch(() => {});   // fire-and-forget

Транзакції з UI (категорія вибрана вручну) не категоризувати.
```

### 6.3 - Ручне перевизначення в UI

```
Прочитай CLAUDE.md.

1. Тап на транзакцію -> модалка деталей: дата, сума, опис, джерело, категорія (select),
   auto_categorized=true -> мітка «🤖 авто», чек -> signed URL із Storage.
2. Зміна категорії:
   a) update transactions set category_id, auto_categorized=false
   b) upsert categorization_cache по hash опису (через Edge Function або RLS-політику insert для сімʼї)
   c) reloadTx()
Інкрементувати CACHE у sw.js.
```

### 6.4 - Масова категоризація

```
Прочитай CLAUDE.md.

supabase/functions/categorize-batch/index.ts (JWT + whitelist як у mono-register):
1. POST { limit: 50 }
2. select transactions where category_id is null limit $1
3. кожну: кеш -> Claude API -> update; пауза 100 мс між запитами
4. return { categorized, from_cache, errors }

Фронтенд (шестерня): «Некатегоризованих: X» + кнопка «Категоризувати» + індикатор.
Інкрементувати CACHE у sw.js.
```

---

## ФІНАЛ-ЧЕКЛІСТ

```
Після кожної фази:

☐ git push origin master
☐ GitHub Pages оновився
☐ PWA на мобільному оновилася (SW підхопив новий CACHE)
☐ Supabase Edge Functions: supabase functions deploy
☐ Secrets: supabase secrets set
☐ Landscape → заглушка "Поверніть пристрій"
☐ Без session → тільки логін, жодних даних
☐ Google OAuth працює (whitelist user)
☐ Сторонній Google акаунт → "Доступ закритий"
☐ Telegram: чужий chat_id отримує «Доступ закритий», свій пише витрату
☐ Обидва whitelist-user бачать всі дані (сімейний доступ через RLS)
☐ DevTools: немає secret keys в Network/LocalStorage
☐ Офлайн: додаток відкривається з кешу
```
