# Сімейний Кешфлоу — CLAUDE.md

## Проєкт

PWA "Сімейний Кешфлоу" — управління фінансами сімʼї.
Хостинг фронтенду: GitHub Pages (автодеплой при push у `master`).
Бекенд: Supabase (PostgreSQL + Edge Functions + Storage).
Зовнішні інтеграції: Monobank API, Telegram Bot API, Claude API (Anthropic).

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
- Supabase JS client через CDN (`https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`)
- Мова інтерфейсу: українська

**Бекенд (Supabase):**
- PostgreSQL — основна БД (транзакції, категорії, бюджети, цілі)
- Edge Functions (Deno/TypeScript) — вебхуки Monobank, Telegram, Claude API
- Storage — зберігання скріншотів чеків
- Auth — автентифікація користувачів (email або magic link)
- Row Level Security (RLS) — ізоляція даних по user_id

**Зовнішні API:**
- Monobank Personal API (`api.monobank.ua`) — автоімпорт витрат
- Telegram Bot API — ручне введення витрат/доходів, скріншоти чеків
- Anthropic Claude API — автокатегоризація транзакцій

---

## СТРАТЕГІЯ РОЗРОБКИ

Розробка поділена на 6 фаз. Кожна фаза — окремий етап з чітким Definition of Done.
Фази виконуються строго послідовно. Не починати наступну без завершення попередньої.

---

### ФАЗА 1: Дизайн UI (ітеративна)

**Ціль:** UI і стилі Monobank. Мобільний додаток, де приємно працювати з фінансами.

**Референс-принципи Monobank UI:**
- Темний фон (#0c0c12 або близький), картки з м'якими тінями
- Великі числа — головний контент, мінімум тексту
- Bottom tab bar (фіксований знизу, 4–5 іконок)
- Свайпи між місяцями (або стрілки як зараз)
- Кругові діаграми / donut charts для розподілу витрат
- Картки транзакцій: іконка категорії зліва, назва + час посередині, сума справа
- Кольори категорій — насичені на темному фоні
- Анімації: плавні переходи між вкладками, появи елементів
- Тактильний фідбек: натиснута картка м'яко масштабується (transform: scale(0.98))

**Екрани для MVP:**

1. **Головний (Огляд)** — баланс за місяць, міні-графік, останні 5 транзакцій, розподіл витрат (donut)
2. **Транзакції** — повний список за місяць, фільтр по категоріях, групування по днях
3. **Бюджет** — категорії з прогресбарами (витрачено / ліміт), відсоток
4. **Кредити** — активні розстрочки з прогресом сплати
5. **Цілі / Накопичення** — прогрес по фондах

**Навігація:**
- Bottom tab bar (фіксований): Огляд | Витрати | Бюджет | Кредити | Цілі
- Вгорі: місяць/рік + стрілки навігації
- Кожна вкладка — окремий "екран" без перезавантаження

**Ітерації:**
- Ітерація 1: базова розкладка, bottom tab bar, оновлений стиль карток
- Ітерація 2: donut chart, транзакційний список із групуванням по днях
- Ітерація 3: анімації, мікроінтеракції, responsive-полірування
- Ітерацій може бути більше — продовжувати поки дизайн не задовольнить

**Дані:** залишити ЗАХАРДКОДЖЕНИМИ. Мета цієї фази — тільки UI.
Подати демо-транзакції (15–20 записів різних категорій) для наповнення списку.

**Definition of Done Фази 1:**
- [ ] Bottom tab bar з іконками, фіксований знизу
- [ ] Кожен екран виглядає як мобільний додаток, не як веб-сторінка
- [ ] Donut chart на головному екрані
- [ ] Список транзакцій з іконками категорій та групуванням по днях
- [ ] Плавні переходи між вкладками
- [ ] Тест на мобільному (реальний пристрій): все зручно тапати, немає горизонтального скролу, шрифти читабельні

---

### ФАЗА 2: Supabase

**Ціль:** перенести дані з хардкоду в Supabase PostgreSQL. Фронтенд читає/пише через Supabase JS client.

**Supabase JS підключення (CDN):**
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script>
  const supabase = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
</script>
```

**Конфігурація** — URL та ANON KEY зберігати як константи в `index.html`.
ANON KEY — публічний, безпечно класти в клієнтський код (RLS захищає дані).

**Схема БД:**

```sql
-- Користувачі (Supabase Auth)
-- Додатково: profiles таблиця

create table profiles (
  id uuid primary key references auth.users(id),
  display_name text,
  mono_token text,             -- зашифрований X-Token monobank
  telegram_chat_id bigint,     -- chat_id для Telegram бота
  created_at timestamptz default now()
);

-- Категорії витрат
create table categories (
  id serial primary key,
  user_id uuid references profiles(id),
  name text not null,
  icon text,                    -- emoji
  color text,                   -- HEX
  budget_limit numeric(12,2),   -- місячний ліміт
  sort_order int default 0,
  is_income boolean default false
);

-- Транзакції
create table transactions (
  id bigserial primary key,
  user_id uuid references profiles(id),
  amount numeric(12,2) not null,       -- завжди додатне
  type text not null check (type in ('income','expense')),
  category_id int references categories(id),
  description text,
  source text check (source in ('mono','telegram','manual')),
  source_id text,                       -- ідентифікатор з джерела (mono transaction id)
  mcc int,                              -- MCC-код від Monobank
  receipt_url text,                     -- URL скріншота в Supabase Storage
  auto_categorized boolean default false,
  date date not null,
  created_at timestamptz default now()
);

-- Кредити / розстрочки
create table credits (
  id serial primary key,
  user_id uuid references profiles(id),
  name text not null,
  monthly_amount numeric(12,2) not null,
  payment_day int not null,             -- день місяця
  start_year int not null,
  start_month int not null,             -- 0-indexed
  total_payments int not null,
  color text,
  source text                           -- mono / privat
);

-- Цілі накопичень
create table goals (
  id serial primary key,
  user_id uuid references profiles(id),
  name text not null,
  target_amount numeric(12,2) not null,
  current_amount numeric(12,2) default 0,
  color text,
  description text,
  sort_order int default 0
);

-- Кеш категоризації (description → category)
create table categorization_cache (
  id serial primary key,
  description_hash text unique not null,  -- md5(lower(trim(description)))
  description text not null,
  category_id int references categories(id),
  mcc int,
  created_at timestamptz default now()
);

-- RLS
alter table profiles enable row level security;
alter table categories enable row level security;
alter table transactions enable row level security;
alter table credits enable row level security;
alter table goals enable row level security;
alter table categorization_cache enable row level security;

-- Політики: кожен бачить тільки свої дані
create policy "own data" on profiles for all using (id = auth.uid());
create policy "own data" on categories for all using (user_id = auth.uid());
create policy "own data" on transactions for all using (user_id = auth.uid());
create policy "own data" on credits for all using (user_id = auth.uid());
create policy "own data" on goals for all using (user_id = auth.uid());
create policy "own data" on categorization_cache for all using (true);
```

**Індекси:**
```sql
create index idx_tx_user_date on transactions(user_id, date desc);
create index idx_tx_source_id on transactions(source_id);
create index idx_cache_hash on categorization_cache(description_hash);
```

**Авторизація:**
- Supabase Auth, email + password
- На фронтенді: екран логіну (простий, з одним полем email + password)
- Після логіну — токен зберігається в Supabase JS client автоматично (localStorage)
- Для сімʼї: 1–2 акаунти (Vitaliy + партнер)

**Міграція хардкоду:**
- Перенести BCAT → таблиця `categories` (insert seed data)
- Перенести CREDITS → таблиця `credits`
- Перенести GOALS → таблиця `goals`
- buildMonth() → замінити на запити до `transactions` з GROUP BY

**Definition of Done Фази 2:**
- [ ] Supabase проєкт створено, схема накатана
- [ ] Seed-дані (категорії, кредити, цілі) в БД
- [ ] Фронтенд читає дані з Supabase замість хардкоду
- [ ] Логін/логаут працює
- [ ] Можна додати транзакцію вручну через UI (кнопка "+")
- [ ] RLS працює — інші користувачі не бачать чужих даних

---

### ФАЗА 3: Monobank API

**Ціль:** автоматичний імпорт транзакцій з Monobank.

**Monobank Personal API:**
- Документація: `https://api.monobank.ua/docs/`
- Авторизація: заголовок `X-Token` (отримати на `https://api.monobank.ua/`)
- Токен безстроковий, зберігається в `profiles.mono_token`

**Два механізми отримання транзакцій:**

1. **Webhook (основний)** — Monobank надсилає POST-запит при кожній транзакції:
   ```
   POST https://api.monobank.ua/personal/webhook
   Header: X-Token
   Body: {"webHookUrl": "https://<project>.supabase.co/functions/v1/mono-webhook"}
   ```
   Тіло вебхука містить: `id`, `time`, `description`, `mcc`, `amount` (копійки, від'ємне для витрат), `balance`, `currencyCode`.

2. **Polling (бекфіл)** — для історичних даних:
   ```
   GET /personal/statement/{account}/{from}/{to}
   ```
   Обмеження: 1 запит на 60 секунд, максимум 31 день за запит.

**Supabase Edge Function `mono-webhook`:**
```
Отримує POST від Monobank →
  Перевіряє чо user з таким mono_token існує →
    Конвертує amount з копійок і грн (÷100, Math.abs) →
      Перевіряє дублікат по source_id →
        Зберігає в transactions (source='mono') →
          Запускає категоризацію (Фаза 6)
```

**Безпека:**
- Monobank не підписує вебхуки — потрібен секретний параметр в URL:
  `https://<project>.supabase.co/functions/v1/mono-webhook?secret=<random>`
- Або верифікація через GET /personal/client-info з отриманим X-Token

**Edge Function для бекфілу `mono-backfill`:**
- Одноразовий запуск для імпорту транзакцій за останні 31 день
- Запускається вручну або через invoke

**Definition of Done Фази 3:**
- [ ] Edge Function `mono-webhook` задеплоєна і приймає транзакції
- [ ] Webhook зареєстрований на api.monobank.ua
- [ ] Нові транзакції Monobank зʼявляються в додатку автоматично
- [ ] Бекфіл за 31 день виконаний
- [ ] Дублікати не створюються (перевірка по source_id)

---

### ФАЗА 4: Telegram-бот (витрати)

**Ціль:** ручне введення витрат через Telegram — текстом або скріншотом чека.

**Telegram Bot API:**
- Створити бота через @BotFather
- Токен зберігати в Supabase Secrets (Edge Function env vars)
- Webhook: `https://<project>.supabase.co/functions/v1/telegram-webhook`

**Формат текстового введення:**
```
250 кава
1200 продукти АТБ
80 маршрутка
```
Парсинг: перше число — сума, решта — опис.

**Обробка скріншотів:**
```
Фото чека в Telegram →
  Edge Function отримує file_id →
    Завантажує фото через Telegram API →
      Зберігає в Supabase Storage (bucket: receipts) →
        Передає base64 і Claude API для розпізнавання →
          Claude повертає: [{amount, description, date}] →
            Зберігає в transactions (source='telegram', receipt_url=...)
```

**Команди бота:**
- Просто число + текст — витрата (type='expense')
- `/start` — привʼязка telegram_chat_id до profiles
- `/balance` — поточний баланс за місяць
- `/last` — останні 5 транзакцій

**Безпека:**
- Whitelist по telegram_chat_id (тільки зареєстровані в profiles)
- Telegram надсилає `X-Telegram-Bot-Api-Secret-Token` і заголовку — верифікувати

**Definition of Done Фази 4:**
- [ ] Бот створений, webhook задеплоєний
- [ ] Текстове повідомлення "250 кава" створює транзакцію
- [ ] Скріншот чека розпізнається через Claude і створює транзакцію
- [ ] Скріншот зберігається в Supabase Storage, URL — в transactions.receipt_url
- [ ] Невідомий chat_id — відхиляється з повідомленням

---

### ФАЗА 5: Telegram-бот (доходи)

**Ціль:** введення доходів через той самий Telegram-бот.

**Формат:**
```
+51000 зарплата аванс
+2500 фріланс
```
Знак `+` на початку — маркер доходу (type='income').

**Альтернатива — команда:**
```
/income 51000 зарплата аванс
/дохід 51000 зарплата аванс
```

**Автоматичні доходи:**
- Monobank webhook вже обробляє зарахування (amount > 0 і сирих даних)
- Фільтрувати міжкартні перекази (description містить "Від:" + власне імʼя)

**Definition of Done Фази 5:**
- [ ] `+5000 фріланс` створює транзакцію type='income'
- [ ] `/income` команда працює
- [ ] Monobank зарахування автоматично мають type='income'
- [ ] Міжкартні перекази фільтруються (не дублюють дохід)

---

### ФАЗА 6: Автокатегоризація (Claude API)

**Ціль:** кожна нова транзакція автоматично отримує категорію.

**Архітектура:**
```
Нова транзакція →
  Перевірити categorization_cache по md5(lower(trim(description))) →
    Є в кеші → використати збережену категорію →
    Нема в кеші → запит до Claude API →
      Claude повертає category_id →
        Зберегти в cache + оновити transaction.category_id
```

**Claude API запит (Edge Function `categorize`):**

```typescript
const response = await fetch('https://api.anthropic.com/v1/messages', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': CLAUDE_API_KEY,
    'anthropic-version': '2023-06-01'
  },
  body: JSON.stringify({
    model: 'claude-haiku-4-5-20251001',  // дешева модель для класифікації
    max_tokens: 100,
    system: `Ти категоризатор витрат. Відповідай ТІЛЬКИ JSON.
Категорії: ${JSON.stringify(categories.map(c => ({id: c.id, name: c.name})))}
Відповідай: {"category_id": <число>}`,
    messages: [{
      role: 'user',
      content: `Транзакція: "${description}", MCC: ${mcc || 'невідомий'}, сума: ${amount} грн`
    }]
  })
});
```

**Вибір моделі:**
- `claude-haiku-4-5` — для масової категоризації (дешево: $0.80/1M input, $4/1M output)
- Один запит категоризації — 200 input + 20 output токенів — $0.0002
- 500 транзакцій/місяць — $0.10/місяць

**Кеш:**
- Ключ: `md5(lower(trim(description)))` — одна й та сама назва торгової точки завжди потрапляє в ту саму категорію
- MCC-код як додатковий сигнал, але не частина ключа кешу (один магазин може мати різний опис, але той самий MCC)
- Кеш глобальний (не per-user) — "АТБ" — це "Продукти" для всіх

**Ручне перевизначення:**
- Якщо користувач змінює категорію транзакції і UI — оновити кеш для цього description
- Наступна транзакція з таким description — нова категорія з кешу

**Definition of Done Фази 6:**
- [ ] Нові транзакції з Monobank автоматично категоризуються
- [ ] Нові транзакції з Telegram автоматично категоризуються
- [ ] Кеш працює — повторні description не викликають Claude API
- [ ] Ручне перевизначення категорії оновлює кеш
- [ ] Некатегоризовані транзакції відображаються з міткою "без категорії"

---

## ПРАВИЛА ДЛЯ CLAUDE CODE

### Service Worker — автооновлення PWA

При КОЖНОМУ коміті обовʼязково:
1. Інкрементувати версію кеш у `sw.js`:
   ```js
   const CACHE = 'cashflow-v1';  // → cashflow-v2, v3, ...
   ```
2. Якщо додано новий локальний файл — додати в масив `ASSETS`.
3. CDN-залежності НЕ додавати в ASSETS — вони кешуються через fetch-обробник.

### Код

- Single-file: весь фронтенд в `index.html`. Не виносити CSS/JS в окремі файли.
- React через CDN. Не переходити на npm/Vite/Next.js.
- `createElement` через аліас `h()`. Не використовувати JSX (немає транспілятора).
- Коментарі українською.
- Supabase credentials (URL, ANON KEY) — як константи в `index.html` (ANON KEY публічний).
- Claude API KEY, Telegram BOT TOKEN, Monobank X-Token — ТІЛЬКИ в Supabase Edge Function env vars (Secrets). Ніколи в клієнтському коді.

### Коміти

```
feat: опис нової функціональності
fix: опис виправлення
style: візуальні зміни без зміни логіки
refactor: реструктуризація без зміни поведінки
chore: інфраструктурні зміни
```

### Заборони

- Не комітити без інкременту `CACHE` у `sw.js`
- Не видаляти `skipWaiting()` і `self.clients.claim()` з SW
- Не зберігати секрети (API-ключі, токени) і клієнтському коді або в Git
- Не змінювати стратегію кешування SW без узгодження
- Не видаляти/перейменовувати `sw.js`, `manifest.json`, іконки
- Не додавати npm / build step — проєкт працює без збірки

### Git

Гілка: `master`. GitHub Pages: `master` branch, root `/`.
```bash
git add -A
git commit -m "feat: опис"
git push origin master
```

### Перевірка оновлення після push

DevTools → Application:
1. Service Workers — новий SW активний
2. Cache Storage — тільки новий CACHE
3. На мобільному PWA: закрити → відкрити

Примусово: `Ctrl+Shift+R` (десктоп) або перевстановити PWA (мобільний).
