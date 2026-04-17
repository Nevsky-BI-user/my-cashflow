# Сімейний Кешфлоу — CLAUDE.md

## Проєкт

PWA "Сімейний Кешфлоу" — управління фінансами сімʼї.
Хостинг фронтенду: GitHub Pages (автодеплой при push у `master`).
Бекенд: Supabase (PostgreSQL + Edge Functions + Storage).
Зовнішні інтеграції: Monobank API, Telegram Bot API, Claude API (Anthropic).

**Користувачі:** тільки двоє — Vitaliy та дружина. Ніяких інших.

---

## БЕЗПЕКА

### Принцип

**Код публічний — дані приватні.**

Вихідний код, дизайн, структура проєкту — відкриті (public repo). Це нормально і безпечно.
Фінансові дані (транзакції, доходи, витрати, баланси, чеки) — закриті. Доступ тільки для двох користувачів.
Захист даних забезпечується Supabase RLS (Row Level Security), а не приховуванням коду.

### GitHub-репозиторій

- Репозиторій **PUBLIC** (безкоштовний GitHub Pages).
- В `index.html` є `SUPABASE_URL` та `SUPABASE_ANON_KEY` — це **безпечно**: ANON KEY є публічним ключем за дизайном Supabase, він не дає доступу до даних без автентифікації + RLS.
- `.gitignore`: ніколи не комітити файли з SERVICE_ROLE_KEY, API-ключами, токенами.

### Supabase Auth — закрита реєстрація

- Публічна реєстрація (sign up) **ВИМКНЕНА**.
- У Supabase Dashboard: Authentication → Settings → Auth → вимкнути "Enable sign up".
- Два акаунти створюються ВРУЧНУ через Supabase Dashboard: Authentication → Users → Invite User.
- Метод авторизації: email + password.
- Екран логіну на фронтенді: тільки "Увійти" (email + password), без кнопки "Зареєструватися".
- Якщо session відсутня — показувати ТІЛЬКИ екран логіну. Жодні дані не рендеряться.

### Row Level Security (RLS)

Кожна таблиця з даними має RLS з політикою `auth.uid()`:

```sql
-- Роздільні політики для SELECT, INSERT, UPDATE, DELETE
-- SELECT: бачу тільки своє
create policy "select own" on transactions for select using (user_id = auth.uid());
-- INSERT: можу створити тільки зі своїм user_id
create policy "insert own" on transactions for insert with check (user_id = auth.uid());
-- UPDATE: можу оновити тільки своє
create policy "update own" on transactions for update using (user_id = auth.uid());
-- DELETE: можу видалити тільки своє
create policy "delete own" on transactions for delete using (user_id = auth.uid());

-- Аналогічно для: profiles, categories, credits, goals
```

Таблиця `categorization_cache` — спільна (без user_id). RLS:
```sql
-- Читати може будь-який автентифікований
create policy "read auth" on categorization_cache for select using (auth.uid() is not null);
-- Писати — тільки через service_role (Edge Functions)
create policy "write service" on categorization_cache for insert using (false);
```

### Supabase ANON KEY vs SERVICE_ROLE KEY

- **ANON KEY** — публічний за дизайном Supabase. Будь-хто може його бачити. Він не дає доступу до даних — RLS блокує всі запити без валідного JWT (тобто без логіну). Безпечно в публічному репозиторії.
- **SERVICE_ROLE KEY** — повний доступ, обходить RLS. ТІЛЬКИ і Edge Functions (env var). НІКОЛИ не в коді, НІКОЛИ не в Git.

### Supabase Storage (чеки)

- Bucket `receipts` — **PRIVATE** (не public).
- RLS на storage.objects:
  ```sql
  create policy "user uploads" on storage.objects for insert
    with check (bucket_id = 'receipts' and auth.uid()::text = (storage.foldername(name))[1]);
  create policy "user reads" on storage.objects for select
    using (bucket_id = 'receipts' and auth.uid()::text = (storage.foldername(name))[1]);
  ```
- Структура: `receipts/{user_id}/{timestamp}.jpg`
- Edge Functions використовують service_role для запису (з Telegram webhook).
- На фронтенді — signed URL для перегляду (supabase.storage.from('receipts').createSignedUrl(path, 3600)).

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
- Повідомлення від невідомого chat_id — відхилити з відповіддю "Доступ закритий".
- Команда `/start` потребує верифікацію (email + пароль або одноразовий код).
- Бот приватний — НЕ публікувати в каталозі ботів.

### Monobank X-Token

- Зберігається в `profiles.mono_token`.
- Доступний тільки для Edge Functions (через service_role).
- RLS: фронтенд НЕ може прочитати mono_token з profiles (окрема policy, що виключає це поле, або окрема таблиця `secrets`).

### Клієнтський код (index.html) — публічний

Допустимо (видно всім, але безпечно):
- `SUPABASE_URL` — публічна адреса
- `SUPABASE_ANON_KEY` — публічний ключ, без логіну не дає доступу до даних

НІКОЛИ НІЯКИХ (дає прямий доступ до даних або зовнішніх сервісів):
- SERVICE_ROLE KEY
- CLAUDE_API_KEY
- TELEGRAM_BOT_TOKEN
- MONO_WEBHOOK_SECRET
- Будь-які паролі або токени

---

## ОРІЄНТАЦІЯ: ТІЛЬКИ ПОРТРЕТНА

### manifest.json

```json
{
  "orientation": "portrait"
}
```
Поле `orientation` змінити з `"any"` на `"portrait"`.

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

### Meta viewport

```html
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
```
Вже є. Залишити без змін.

### Screen Orientation API (опціонально)

```js
if (screen.orientation && screen.orientation.lock) {
  screen.orientation.lock('portrait').catch(() => {});
}
```
Працює тільки в standalone PWA mode (не і звичайному браузері).

---

## Поточний стан

- Весь код — в `index.html` (React 18 CDN, ~750 рядків)
- Дані захардкоджені і JS-константах: CREDITS, BCAT, GOALS, buildMonth()
- 5 вкладок: Огляд, Бюджет, Потік, Кредити, Цілі
- Бекенду немає. Реальних даних немає.
- Темна тема, CSS-змінні, mobile-first

## Структура файлів

```
/
├── index.html        — фронтенд (HTML + CSS + React inline)
├── manifest.json     — PWA-маніфест
├── sw.js             — Service Worker
├── icon-192.svg
├── icon-512.svg
├── .gitignore
├── CLAUDE.md         — цей файл
```

## Технічний стек

**Фронтенд (GitHub Pages):**
- React 18 через CDN (cdnjs.cloudflare.com)
- Single-file: весь HTML/CSS/JS в `index.html`
- Без npm, без збірки, без бандлера
- Supabase JS client через CDN
- Мова інтерфейсу: українська
- Орієнтація: тільки портретна

**Бекенд (Supabase):**
- PostgreSQL — основна БД
- Edge Functions (Deno/TypeScript) — вебхуки, категоризація
- Storage — скріншоти чеків (private bucket)
- Auth — закрита реєстрація, тільки 2 користувачі
- RLS — ізоляція даних по user_id

**Зовнішні API:**
- Monobank Personal API
- Telegram Bot API
- Anthropic Claude API

---

## СТРАТЕГІЯ РОЗРОБКИ

6 фаз, строго послідовно.

---

### ФАЗА 1: Дизайн UI (ітеративна)

**Ціль:** UI і стилі Monobank. Портретний мобільний додаток.

**Референс Monobank UI:**
- Темний фон (#0c0c12), картки з м'якими тінями
- Великі числа — головний контент, мінімум тексту
- Bottom tab bar (фіксований знизу, 4–5 іконок)
- Кругові діаграми / donut charts
- Картки транзакцій: іконка зліва, назва посередині, сума справа
- Анімації: плавні переходи, появи елементів
- Тактильний фідбек: transform: scale(0.98)

**Орієнтація:**
- Тільки портретна. Landscape: приховати контент, показати повідомлення "Поверніть пристрій".
- manifest.json: orientation: "portrait"
- Screen Orientation API lock і standalone mode

**Екрани для MVP:**
1. Огляд — баланс, donut, останні 5 транзакцій
2. Транзакції — список за місяць, групування по днях
3. Бюджет — категорії з прогресбарами
4. Кредити — розстрочки з прогресом
5. Цілі — фонди накопичень

**Навігація:**
- Bottom tab bar (фіксований): Огляд | Витрати | Бюджет | Кредити | Цілі
- Вгорі: місяць/рік + стрілки

**Ітерації:** продовжувати поки дизайн не задовольнить.
**Дані:** залишити захардкоджені. Мета — тільки UI.

**Definition of Done Фази 1:**
- [ ] Портретна орієнтація зафіксована (manifest + CSS + JS)
- [ ] Bottom tab bar з іконками
- [ ] Donut chart на головному екрані
- [ ] Список транзакцій з групуванням по днях
- [ ] Плавні переходи між вкладками
- [ ] Тест на мобільному: все працює, landscape — заглушка

---

### ФАЗА 2: Supabase

**Ціль:** бекенд з закритим доступом для двох користувачів.

**Авторизація — ВАЖЛИВО:**
- Sign up вимкнено в Supabase Dashboard
- 2 акаунти створені вручну (Invite User)
- Фронтенд: тільки форма логіну, без реєстрації
- Session timeout: за замовчуванням Supabase (1 тиждень)

**Схема БД:** profiles, categories, transactions, credits, goals, categorization_cache.
**RLS:** окремі політики на SELECT/INSERT/UPDATE/DELETE з `auth.uid()`.
**Міграція:** хардкод → Supabase.

**Definition of Done Фази 2:**
- [ ] Sign up вимкнено
- [ ] 2 акаунти створені
- [ ] RLS працює (перевірити: один user не бачить даних іншого)
- [ ] Фронтенд читає/пише через Supabase
- [ ] Логін/логаут працює
- [ ] Без session — тільки екран логіну, жодних даних

---

### ФАЗА 3: Monobank API

**Ціль:** автоімпорт транзакцій.

**Webhook URL:** з секретним query-параметром.
**Mono token:** зберігається в profiles, недоступний для фронтенду через RLS.
**Edge Functions:** mono-webhook, mono-backfill, mono-register-webhook.

**Definition of Done Фази 3:**
- [ ] Webhook приймає транзакції
- [ ] Mono token зберігається безпечно (не читається фронтендом)
- [ ] Бекфіл працює
- [ ] Дублікати не створюються

---

### ФАЗА 4: Telegram-бот (витрати)

**Ціль:** введення витрат текстом + скріншотами.

**Безпека:**
- Whitelist по telegram_chat_id
- `/start` потребує верифікацію (email + пароль або одноразовий код)
- Webhook secret header перевіряється
- Бот не в публічному каталозі

**Скріншоти:** private Storage bucket, signed URLs.

**Definition of Done Фази 4:**
- [ ] Текст → транзакція
- [ ] Фото чека → Claude OCR → транзакція
- [ ] Невідомий chat_id відхиляється
- [ ] Чеки і private bucket, доступні тільки власнику

---

### ФАЗА 5: Telegram-бот (доходи)

**Ціль:** `+сума опис` або `/income`.

**Definition of Done Фази 5:**
- [ ] Доходи через бот працюють
- [ ] Дублікати з Monobank фільтруються

---

### ФАЗА 6: Автокатегоризація (Claude API)

**Ціль:** автоматична категорія для кожної транзакції.

**Модель:** claude-haiku-4-5 (дешева).
**Кеш:** categorization_cache, md5(description).
**API KEY:** тільки в Edge Function env var.

**Definition of Done Фази 6:**
- [ ] Автокатегоризація працює
- [ ] Кеш зменшує кількість API-викликів
- [ ] Ручне перевизначення оновлює кеш
- [ ] Claude API KEY не в клієнтському коді

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
- Всі інші ключі — ТІЛЬКИ в Edge Function Secrets.

### Коміти

```
feat: / fix: / style: / refactor: / chore: / security:
```

### Заборони

- Не комітити без інкременту `CACHE`
- Не зберігати секрети в Git або клієнтському коді
- Не додавати функцію реєстрації (sign up) на фронтенд
- Не створювати public Storage buckets
- Не вимикати RLS
- Не додавати npm / build step
- Не видаляти `skipWaiting()` / `clients.claim()` з SW
- Не змінювати orientation на "any" або "landscape"

### Git

Гілка: `master`. Репозиторій: **PUBLIC** (безкоштовний GitHub Pages).
```bash
git add -A
git commit -m "feat: опис"
git push origin master
```

### Вартість

Все безкоштовне, крім Claude API:
- GitHub Pages — безкоштовно (public repo)
- Supabase Free Tier — 500 МБ БД, 1 ГБ Storage, 500K Edge Function invocations
- Monobank API — безкоштовно
- Telegram Bot API — безкоштовно
- Claude API (Haiku категоризація) — ~$0.10/місяць на 500 транзакцій
