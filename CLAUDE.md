# Сімейний Кешфлоу — CLAUDE.md

## Проєкт

PWA "Сімейний Кешфлоу" — управління фінансами сімʼї.
Хостинг фронтенду: GitHub Pages (автодеплой при push у `master`).
Бекенд: Supabase (PostgreSQL + Edge Functions + Storage).
Зовнішні інтеграції: Monobank API, Telegram Bot API, Claude API (Anthropic).

**Користувачі:** тільки двоє — Vitaliy та дружина. Whitelist:
- `gotnewmess@gmail.com`
- `kovtunenko.yulchik@gmail.com`

---

## БЕЗПЕКА

### Принцип

**Код публічний — дані приватні.**

Вихідний код, дизайн, структура проєкту — відкриті (public repo). Це нормально і безпечно.
Фінансові дані (транзакції, доходи, витрати, баланси, чеки) — закриті. Доступ тільки для двох користувачів через email-whitelist.
Захист даних забезпечується Supabase RLS (Row Level Security) + функцією `is_family_member()`, а не приховуванням коду.

### GitHub-репозиторій

- Репозиторій **PUBLIC** (безкоштовний GitHub Pages).
- В `index.html` є `SUPABASE_URL` та `SUPABASE_ANON_KEY` — це **безпечно**: ANON KEY є публічним ключем за дизайном Supabase, він не дає доступу до даних без автентифікації + RLS з whitelist.
- `.gitignore`: ніколи не комітити файли з SERVICE_ROLE_KEY, API-ключами, токенами.

### Авторизація — тільки Google OAuth

Єдиний спосіб входу:

1. **Google OAuth** — `sb.auth.signInWithOAuth({provider:'google', options:{redirectTo}})`

> Email/password-форму прибрано (коміт `f86c106`). `signInWithPassword` на фронтенді не використовується; акаунти створюються вручну в Supabase (Invite User), вхід — лише через Google.

**Email/password sign up вимкнено** у Supabase Dashboard: Authentication → Settings → "Enable sign up" = OFF. Облікові записи створюються вручну (Invite User).

**КРИТИЧНО про Google OAuth і sign up:** параметр "Disable Sign Ups" блокує лише email/password реєстрацію. Google OAuth обходить цей параметр — будь-який Google-акаунт при першому вході створить запис у `auth.users`. Тому захист реалізується НЕ через відключення sign up, а через **email whitelist у RLS**.

### Email whitelist — двошаровий захист

**Шар 1 — фронтенд (UX):**
```js
const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];
// після session: якщо email не в списку → sb.auth.signOut() + повідомлення
```

**Шар 2 — RLS (справжній захист):**
```sql
create or replace function is_family_member() returns boolean
  language sql security definer stable as $$
  select exists (
    select 1 from auth.users
    where id = auth.uid()
      and lower(email) = any (array['gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com'])
  );
$$;

-- Всі політики:
create policy "family full" on transactions for all
  using (is_family_member()) with check (is_family_member());
```

Шар 1 — для UX (швидке повідомлення замість порожнього інтерфейсу).
Шар 2 — справжня безпека: навіть якщо хтось обійде фронтенд (вимкне JS у DevTools), без правильного email RLS поверне порожній результат.

### Налаштування Google OAuth

**Google Cloud Console:**
1. Створити проєкт (або використати існуючий).
2. APIs & Services → OAuth consent screen → External → заповнити (назва "Family Cashflow", тестові користувачі: обидва email).
3. APIs & Services → Credentials → Create Credentials → OAuth Client ID → Web application:
   - **Authorized JavaScript origins:** `https://<user>.github.io` (без шляху до репо)
   - **Authorized redirect URIs:** `https://lisedsqwdzshsxydghag.supabase.co/auth/v1/callback`
4. Скопіювати Client ID та Client Secret.

**Supabase Dashboard:**
1. Authentication → Providers → Google → Enable → вставити Client ID + Secret.
2. Authentication → URL Configuration:
   - **Site URL:** `https://<user>.github.io/<repo>/`
   - **Redirect URLs:** `https://<user>.github.io/<repo>/**`
3. Зберегти.

### OAuth flow

`supabase-js v2` у браузері використовує **PKCE flow** автоматично:
- При натисканні кнопки → редірект на Google
- Google → редірект на `https://lisedsqwdzshsxydghag.supabase.co/auth/v1/callback?code=...`
- Supabase → редірект на `redirectTo` з параметром `?code=...`
- `supabase-js` (з `detectSessionInUrl: true` за замовчуванням) автоматично перехоплює `code` і обмінює на сесію
- `onAuthStateChange` спрацьовує → перевірка email → доступ

Жодного callback route не потрібно — все обробляється клієнтом.

### Row Level Security (RLS) — підсумок

Всі таблиці з даними мають RLS з політикою через `is_family_member()`:
- `profiles`, `categories`, `transactions`, `credits`, `goals` — `for all using (is_family_member()) with check (is_family_member())`
- `categorization_cache` — `for select using (is_family_member())`, write через service_role
- Storage `receipts` — `is_family_member() AND bucket_id='receipts'`

Зміна whitelist — у файлі `supabase-migrations/02-family-whitelist.sql`, переcтворити функцію.

### Supabase ANON KEY vs SERVICE_ROLE KEY

- **ANON KEY** — публічний за дизайном Supabase. Безпечний у публічному репо. RLS блокує всі запити без email у whitelist.
- **SERVICE_ROLE KEY** — повний доступ, обходить RLS. ТІЛЬКИ в Edge Functions (env var). НІКОЛИ не в коді, НІКОЛИ не в Git.

### Supabase Storage (чеки)

- Bucket `receipts` — **PRIVATE** (не public).
- RLS на storage.objects — через `is_family_member()`.
- Структура: `receipts/{user_id}/{timestamp}.jpg`
- Edge Functions використовують service_role для запису (з Telegram webhook).
- На фронтенді — signed URL для перегляду.

### Секрети (Edge Function env vars)

Зберігаються через `supabase secrets set`:
```
SUPABASE_SERVICE_ROLE_KEY=eyJ...
MONO_WEBHOOK_SECRET=<random-uuid>
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_WEBHOOK_SECRET=<random-uuid>
CLAUDE_API_KEY=sk-ant-...
```
Жоден з цих ключів не потрапляє в Git або клієнтський код.

### Telegram-бот

- Whitelist: тільки chat_id, збережені в `profiles.telegram_chat_id`.
- `/start` потребує email + password або одноразовий код для привʼязки.
- Бот приватний — НЕ публікувати в каталозі.

### Monobank X-Token

- Зберігається в `profiles.mono_token`.
- Доступний тільки для Edge Functions (через service_role).

### Клієнтський код (index.html) — публічний

Допустимо (видно всім, але безпечно):
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ALLOWED_EMAILS` — масив дозволених email (шар 1 захисту)

НІКОЛИ НІЯКИХ:
- SERVICE_ROLE KEY
- CLAUDE_API_KEY
- TELEGRAM_BOT_TOKEN
- MONO_WEBHOOK_SECRET
- Паролі, токени

---

## ОРІЄНТАЦІЯ: ТІЛЬКИ ПОРТРЕТНА

### manifest.json
```json
{ "orientation": "portrait" }
```

### CSS
```css
@media (orientation: landscape) and (max-height: 500px) {
  #root { display: none; }
  body::after {
    content: 'Поверніть пристрій вертикально';
    display: flex; align-items: center; justify-content: center;
    height: 100vh; font-size: 18px; color: var(--muted);
    text-align: center; padding: 20px;
  }
}
```

### Screen Orientation API
```js
if (screen.orientation && screen.orientation.lock) {
  screen.orientation.lock('portrait').catch(() => {});
}
```

---

## Поточний стан

- Весь код — в `index.html` (React 18 CDN, ~780 рядків)
- Дані: Supabase + захардкоджені defaults
- 5 вкладок: Огляд, Бюджет, Потік, Кредити (Календар), Цілі
- Темна тема, glassmorphism, mobile-first
- Auth: тільки Google OAuth, email whitelist

## Структура файлів

```
/
├── index.html                              — фронтенд
├── manifest.json                            — PWA-маніфест
├── sw.js                                    — Service Worker
├── icon-192.svg / icon-512.svg
├── .gitignore
├── CLAUDE.md                                — цей файл
├── PROMPTS.md                               — інструкції для Claude Code
├── supabase-schema.sql                      — початкова схема + RLS
└── supabase-migrations/
    └── 02-family-whitelist.sql              — email whitelist через is_family_member()
```

## Технічний стек

**Фронтенд (GitHub Pages):**
- React 18 через CDN
- Single-file `index.html`
- Без npm, без збірки
- Supabase JS client через CDN
- Мова: українська
- Орієнтація: тільки портретна

**Бекенд (Supabase):**
- PostgreSQL
- Edge Functions (Deno/TS)
- Storage (private bucket)
- Auth: тільки Google OAuth
- RLS через `is_family_member()`

**Зовнішні API:**
- Monobank Personal API
- Telegram Bot API
- Anthropic Claude API

---

## СТРАТЕГІЯ РОЗРОБКИ

6 фаз, строго послідовно.

### ФАЗА 1: Дизайн UI (завершено)
### ФАЗА 2: Supabase (завершено, додано Google OAuth)
### ФАЗА 3: Monobank API
### ФАЗА 4: Telegram-бот (витрати)
### ФАЗА 5: Telegram-бот (доходи)
### ФАЗА 6: Автокатегоризація (Claude API)

Детальні DoD кожної фази — у PROMPTS.md.

---

## ПРАВИЛА ДЛЯ CLAUDE CODE

### Service Worker

При КОЖНОМУ коміті: інкрементувати `CACHE` у `sw.js`.
Нові файли — додати в `ASSETS`. CDN — не додавати.

### Код

- Single-file: `index.html`. Без npm, без збірки.
- React CDN, `createElement` через `h()`. Без JSX.
- Коментарі українською.
- ANON KEY — допустимо в `index.html`.
- ALLOWED_EMAILS — допустимо в `index.html`.
- Всі інші ключі — ТІЛЬКИ в Edge Function Secrets.

### Auth-логіка — інваріанти

- `LoginScreen` має одну кнопку: "Увійти через Google". Форми email/password немає.
- Після `setSession` обов'язково перевірити `session.user.email` проти `ALLOWED_EMAILS`. Якщо ні → `auth.signOut()` + `authError`.
- `signInWithOAuth` має параметр `redirectTo: window.location.origin + window.location.pathname` (без query/hash).
- Не використовувати `signUp()` ніде на фронтенді.
- Не показувати "Забули пароль" / "Реєстрація" / інші auth-функції — лише вхід.

### Коміти

```
feat: / fix: / style: / refactor: / chore: / security:
```

### Заборони

- Не комітити без інкременту `CACHE`
- Не зберігати секрети в Git або клієнтському коді
- Не додавати функцію реєстрації (sign up) на фронтенд
- Не видаляти whitelist-перевірку у LoginScreen / App
- Не додавати email-и в `ALLOWED_EMAILS` без оновлення `is_family_member()` у БД
- Не створювати public Storage buckets
- Не вимикати RLS
- Не додавати npm / build step
- Не видаляти `skipWaiting()` / `clients.claim()` з SW
- Не змінювати orientation на "any" або "landscape"
- Не комітити без проходження всіх перевірок (див. нижче)
- Не рефакторити код, який працює, якщо промпт цього не просить

### Принцип мінімальних змін

- Змінювати ТІЛЬКИ те, що просить промпт
- Перед str_replace — спочатку `grep` щоб знайти точний рядок
- Після str_replace — `grep` щоб переконатися що заміна відбулася
- Один промпт = одна логічна задача

### Валідація перед комітом (ОБОВ'ЯЗКОВО)

**Крок 1 — Бекап:**
```bash
cp index.html index.backup.html
```

**Крок 2 — Синтаксис JS:**
```bash
node -e "
const fs=require('fs');
const html=fs.readFileSync('index.html','utf8');
const m=html.match(/<script[^>]*>([\s\S]*?)<\/script>/g);
if(!m){console.log('FAIL: no script tags');process.exit(1)}
const last=m[m.length-1].replace(/<\/?script[^>]*>/g,'');
try{new Function(last);console.log('JS OK')}
catch(e){console.log('JS FAIL:',e.message);process.exit(1)}
"
```

**Крок 3 — Структурна цілісність:**
```bash
grep -c "^function App()" index.html              # = 1
grep -c "ReactDOM.createRoot" index.html          # = 1
grep -c "^function LoginScreen" index.html         # = 1
grep -c "ALLOWED_EMAILS" index.html               # ≥ 2 (декларація + використання)
grep -c "signInWithOAuth" index.html              # = 1
grep -c "serviceWorker" index.html                # ≥ 1
grep "const CACHE" sw.js                           # перевірити інкремент
```

**Крок 4 — HTML валідність:**
```bash
node -e "
const h=require('fs').readFileSync('index.html','utf8');
const o=(h.match(/<script/g)||[]).length;
const c=(h.match(/<\/script>/g)||[]).length;
console.log(o===c?'HTML OK ('+o+' scripts)':'HTML FAIL');
if(o!==c)process.exit(1);
"
```

**Крок 5 — Критичні рядки:**
```bash
node -e "
const h=require('fs').readFileSync('index.html','utf8');
const checks=[
  ['SUPABASE_URL','Supabase URL'],
  ['supabase.createClient','Supabase client'],
  ['ALLOWED_EMAILS','Email whitelist'],
  ['signInWithOAuth','Google OAuth'],
  ['function App','App component'],
  ['function LoginScreen','LoginScreen component'],
  ['tab-bar','Tab bar'],
  ['sw.js','SW registration'],
];
let ok=true;
checks.forEach(([pat,name])=>{
  if(!h.includes(pat)){console.log('MISSING:',name);ok=false}
});
console.log(ok?'ALL CHECKS PASSED':'SOME CHECKS FAILED');
if(!ok)process.exit(1);
"
```

**Крок 6 — Візуальна перевірка:**
```bash
npx live-server --port=8080 --no-browser &
# Відкрий http://localhost:8080
# Має зʼявитись LoginScreen з двома способами входу
# DevTools Console — 0 помилок
```

**Якщо всі перевірки пройшли:**
```bash
rm -f index.backup.html
git add -A
git commit -m "feat: опис"
git push origin master
```

**Якщо перевірка НЕ пройшла:**
```bash
cp index.backup.html index.html
echo "Відкочено. Переформулюй промпт."
```

### Git

Гілка: `master`. Репозиторій PUBLIC.
```bash
git add -A
git commit -m "feat: опис"
git push origin master
```

### Вартість

Все безкоштовне, крім Claude API (~$0.10/міс на 500 транзакцій).
