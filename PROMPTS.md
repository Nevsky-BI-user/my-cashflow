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

(без змін, див. попередню версію)

### 3.2 — Edge Function: mono-backfill

(без змін)

### 3.3 — Реєстрація webhook + UI налаштувань

(без змін)

### 3.4 — Індикатор джерела в UI

(без змін)

---

## ФАЗА 4: Telegram-бот (витрати)

(без змін, див. попередню версію)

---

## ФАЗА 5: Telegram-бот (доходи)

(без змін)

---

## ФАЗА 6: Автокатегоризація

(без змін)

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
☐ Email/password fallback працює
☐ Обидва whitelist-user бачать всі дані (сімейний доступ через RLS)
☐ DevTools: немає secret keys в Network/LocalStorage
☐ Офлайн: додаток відкривається з кешу
```
