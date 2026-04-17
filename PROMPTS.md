# Промпти для Claude Code — Сімейний Кешфлоу

Кожен промпт — окрема задача. Виконувати строго послідовно.
Після кожного кроку — перевірити результат.

---

## ФАЗА 1: Дизайн UI

### 1.0 — Портретна орієнтація + manifest

```
Прочитай CLAUDE.md (секції "ОРІЄНТАЦІЯ" та "БЕЗПЕКА").

1. У manifest.json змінити "orientation": "any" на "orientation": "portrait".

2. У index.html додати CSS для блокування landscape:
   @media (orientation: landscape) and (max-height: 500px) {
     #root { display: none !important; }
     body::after {
       content: 'Поверніть пристрій вертикально';
       display: flex; align-items: center; justify-content: center;
       height: 100vh; width: 100%; position: fixed; top: 0; left: 0;
       font-size: 18px; color: var(--muted); text-align: center;
       padding: 40px; background: var(--bg); z-index: 9999;
     }
   }

3. У JS-блоці (після register SW) додати:
   if (screen.orientation && screen.orientation.lock) {
     screen.orientation.lock('portrait').catch(() => {});
   }

4. Перевірити що на десктопі додаток працює нормально (landscape заглушка спрацьовує тільки якщо max-height < 500px — тобто тільки на мобільних і landscape).

Інкрементуй CACHE у sw.js.
```

### 1.1 — Bottom tab bar

```
Прочитай CLAUDE.md.

Заміни горизонтальні вкладки зверху на bottom tab bar і стилі Monobank:

- position: fixed, bottom: 0, left: 0, right: 0
- 5 вкладок: Огляд | Витрати | Бюджет | Кредити | Цілі
- Кожна вкладка: SVG-іконка (16×16) зверху + назва (10px) знизу
- Активна: var(--indigo), неактивна: var(--muted2)
- Фон: var(--card), border-top: 1px solid var(--border)
- Висота: 56px + padding-bottom: env(safe-area-inset-bottom)
- .content: padding-bottom = 56px + 16px (щоб контент не ховався)

SVG-іконки інлайн (path):
- Огляд: 4 квадрати (дашборд)
- Витрати: список зі стрілкою
- Бюджет: кругова діаграма
- Кредити: кредитка
- Цілі: прапорець

Header зі стрілками місяць — залишити.
Вкладку "Потік" → "Витрати".

Інкрементуй CACHE у sw.js.
```

### 1.2 — Стиль карток

```
Прочитай CLAUDE.md.

Оновити Card компонент і стилі Monobank:

- border-radius: 16px
- background: linear-gradient(160deg, var(--card) 0%, var(--card2) 100%)
- border: 1px solid var(--border)
- box-shadow: 0 2px 12px rgba(0,0,0,0.2)
- padding: 18px 20px
- При натисканні: transform: scale(0.985), transition 0.15s
- CardLabel: fontSize 11px, letter-spacing 0.06em, fontWeight 700
- Числа: fontSize +2–3px, fontWeight 800
- gap між картками: 12px

Тільки стилі, без зміни логіки.
Інкрементуй CACHE у sw.js.
```

### 1.3 — Donut chart

```
Прочитай CLAUDE.md.

На вкладці "Огляд" замінити stacked bar на SVG donut chart:

- 160×160px, по центру
- stroke-width: 28
- Сегменти: Оренда, Комунальні, Кредити, Змінні, Накопичення
- Кольори з поточних CSS-змінних
- Центр: загальна сума витрат (великий шрифт) + "витрати" (маленький)
- Gap 2px між сегментами
- Легенда під donut: кольоровий кружечок + назва + сума

SVG: <circle> з stroke-dasharray та stroke-dashoffset.

Не видаляти інші елементи Огляду.
Інкрементуй CACHE у sw.js.
```

### 1.4 — Список транзакцій з групуванням по днях

```
Прочитай CLAUDE.md.

Переробити вкладку "Витрати":

1. Групування по днях:
   - Заголовок: "6 квітня, понеділок" — жирний, 13px
   - Транзакції дня під заголовком
   - Між групами: 16px

2. Картка транзакції:
   - Зліва: круглий аватар 38×38 з emoji (напівпрозорий фон кольору категорії)
   - Центр: назва (13px, 500), підпис "mono · 5411" (11px, muted)
   - Справа: сума (14px, 700, зелена/червона), баланс під нею (10px, muted)

3. Подати 15–20 демо-транзакцій:
   АТБ, Сільпо, Bolt, WOG, Аптека Доброго Дня, Київстар, Netflix, YouTube Premium тощо.
   Рознести по різних днях. Emoji з масиву BCAT.

Інкрементуй CACHE у sw.js.
```

### 1.5 — Анімації

```
Прочитай CLAUDE.md.

1. Перехід між вкладками: opacity 0→1, translateY(8→0), 0.2s ease-out

2. Картки: staggered поява, кожна +50ms delay

3. Великі числа: count-up від 0 за 0.4s (requestAnimationFrame)

4. Donut: сегменти розкриваються від 0, stroke-dashoffset 0.8s ease-out

5. Progress bars: width від 0, 0.5s ease-out

Тільки візуал, без зміни логіки.
Інкрементуй CACHE у sw.js.
```

### 1.6 — Responsive

```
Прочитай CLAUDE.md.

1. Мобільний (< 768px): padding 14px 16px, border-radius 14px

2. Десктоп (≥ 768px): max-width контенту 480px по центру (мобільний look як Monobank web), bottom tab bar теж 480px

3. Safe areas iPhone:
   - bottom bar: padding-bottom env(safe-area-inset-bottom)
   - header: padding-top env(safe-area-inset-top)

4. Перевірити: мінімум 11px шрифт, тапабельні елементи 44×44, без обрізань на 320px

Інкрементуй CACHE у sw.js.
```

### 1.7+ — Ітерації фідбеку

```
Прочитай CLAUDE.md.
[Конкретний фідбек після перегляду]
Інкрементуй CACHE у sw.js.
```

---

## ФАЗА 2: Supabase

### 2.1 — Supabase JS client + закритий логін

```
Прочитай CLAUDE.md (секції "БЕЗПЕКА" та "Supabase Auth — закрита реєстрація").

1. Подай CDN перед основним <script>:
   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>

2. Константи на початку <script>:
   const SUPABASE_URL = 'https://XXXXX.supabase.co';  // TODO
   const SUPABASE_KEY = 'eyJ...';                       // TODO (anon key)
   const sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

3. Стан авторизації:
   - useState для session (null)
   - useEffect: sb.auth.getSession() → setSession
   - sb.auth.onAuthStateChange → оновити session
   - session === null → екран логіну
   - session !== null → додаток

4. Екран логіну — ТІЛЬКИ вхід, БЕЗ реєстрації:
   - Поля: email, password
   - Кнопка "Увійти" → sb.auth.signInWithPassword({email, password})
   - Помилка → повідомлення під кнопкою
   - Стиль: темна тема, центрований, логотип/назва зверху
   - НІЯКОЇ кнопки "Зареєструватися", "Forgot password" або подібного

5. У header додатку: кнопка logout (маленька, непримітна):
   - sb.auth.signOut()
   - Іконка: двері зі стрілкою або power icon

Інкрементуй CACHE у sw.js.
```

### 2.2 — SQL-схема з RLS

```
Прочитай CLAUDE.md (секції "Схема БД" та "Row Level Security").

Створи supabase-schema.sql:

1. Таблиці: profiles, categories, transactions, credits, goals, categorization_cache
   (повна схема з CLAUDE.md)

2. RLS — СІМЕЙНИЙ ДОСТУП (обидва користувачі бачать ВСІ дані):
   - Всі таблиці: auth.uid() is not null → повний доступ
   - Незалогінені → нічого не бачать
   - categorization_cache: select для auth users, insert/update через service_role

4. Індекси: idx_tx_user_date, idx_tx_source_id, idx_cache_hash

5. Trigger: при створенні auth.user → auto-create profiles row:
   create function handle_new_user() returns trigger as $$
   begin
     insert into profiles (id) values (new.id);
     return new;
   end;
   $$ language plpgsql security definer;
   create trigger on_auth_user_created
     after insert on auth.users
     for each row execute function handle_new_user();

6. Seed categories (13 шт з BCAT), credits (4 шт), goals (3 шт).
   user_id = placeholder (замінити на реальний UUID після створення акаунтів).

Додати supabase-schema.sql в .gitignore (містить seed з UUID).
Інкрементуй CACHE у sw.js.
```

### 2.3 — Storage bucket для чеків

```
Прочитай CLAUDE.md (секції "Supabase Storage").

Створи інструкцію (і коментарі supabase-schema.sql або окремим файлом) для налаштування Storage:

1. Створити bucket 'receipts' через Dashboard: Storage → New Bucket
   - Public: OFF (приватний)
   - File size limit: 5MB
   - Allowed MIME types: image/jpeg, image/png, image/webp

2. SQL для RLS на storage.objects — СІМЕЙНИЙ ДОСТУП (обидва бачать все):

   create policy "auth upload receipts" on storage.objects for insert
     with check (bucket_id = 'receipts' and auth.uid() is not null);

   create policy "auth read receipts" on storage.objects for select
     using (bucket_id = 'receipts' and auth.uid() is not null);

   create policy "auth delete receipts" on storage.objects for delete
     using (bucket_id = 'receipts' and auth.uid() is not null);

3. Edge Functions (service_role) мають повний доступ — вони завантажують чеки з Telegram.
```

### 2.4 — Читання категорій, кредитів, цілей

```
Прочитай CLAUDE.md.

Замінити хардкод BCAT, CREDITS, GOALS на Supabase:

1. loadCategories(): sb.from('categories').select('*').order('sort_order')
2. loadCredits(): sb.from('credits').select('*')
3. loadGoals(): sb.from('goals').select('*').order('sort_order')

4. App:
   - useState: categories=[], credits=[], goals=[], loading=true
   - useEffect(session): якщо session → завантажити дані
   - loading=true → спінер
   - Передати дані в компоненти
   - TOTAL_VAR = categories.reduce(...)

5. Видалити BCAT, CREDITS, GOALS хардкод.

Інкрементуй CACHE у sw.js.
```

### 2.5 — Читання транзакцій

```
Прочитай CLAUDE.md.

Замінити buildMonth() на реальні транзакції:

1. loadTransactions(year, month):
   - start = `${year}-${String(month+1).padStart(2,'0')}-01`
   - end = last day of month
   - sb.from('transactions').select('*, categories(name, icon, color)').gte('date', start).lte('date', end).order('date')

2. Перерахунок:
   - inc = sum where type='income'
   - expenses group by category_id
   - Кумулятивний баланс

3. Оновити App: при зміні year/month → loadTransactions()

4. Видалити buildMonth() або закоментувати.

5. Вкладка "Витрати" та "Огляд" — рендерити реальні дані.

Інкрементуй CACHE у sw.js.
```

### 2.6 — Додавання транзакції (кнопка "+")

```
Прочитай CLAUDE.md.

1. FAB кнопка "+":
   - position fixed, bottom 72px, right 20px
   - 52×52, круглий, var(--indigo), тінь
   - SVG "+"

2. Модалка "Нова транзакція":
   - Overlay з blur
   - Toggle "Витрата" / "Дохід"
   - Сума (number, 24px, автофокус)
   - Категорія (picker з emoji)
   - Опис (text, optional)
   - Дата (date, default сьогодні)
   - "Зберегти" / "Скасувати"

3. Insert:
   sb.from('transactions').insert({
     user_id: session.user.id,
     amount, type, category_id, description,
     source: 'manual', date
   })

4. Після збереження: закрити модалку, перезавантажити транзакції.

5. Валідація: amount > 0, category обрана.

Інкрементуй CACHE у sw.js.
```

### 2.7 — Бюджет з реальними даними

```
Прочитай CLAUDE.md.

Вкладка "Бюджет" — факт vs план:

1. Для кожної категорії: spent = transactions.filter(category_id).sum(amount) where type='expense'

2. BudgetRow:
   - emoji + назва | "spent / limit"
   - Progress bar: width = (spent/limit)*100%
   - Колір: <80% — категорії, 80–100% — var(--yellow), >100% — var(--red)
   - % під прогресбаром

3. Загальна картка зверху: "Витрачено X з Y", загальний progress bar.

4. Сортування: найбільший % зверху.

Інкрементуй CACHE у sw.js.
```

### 2.8 — Перевірка безпеки

```
Прочитай CLAUDE.md (секції "БЕЗПЕКА").

Фінальна перевірка безпеки Фази 2.
Репо ПУБЛІЧНЕ — код бачать усі. Перевіряємо що ДАНІ закриті.

1. Відкрити додаток і incognito — має бути ТІЛЬКИ екран логіну, жодних даних.

2. Залогінитися як user 1. Перевірити що видно тільки свої дані.

3. Відкрити DevTools → Network:
   - Запити до Supabase мають header Authorization: Bearer <jwt>
   - Жодних запитів що повертають дані без авторизації
   - В запитах немає service_role key

4. Відкрити DevTools → Application → Local Storage:
   - Supabase зберігає session token — нормально
   - Немає mono_token, api keys, bot tokens

5. Переглянути index.html (код публічний, тому перевіряємо що в ньому):
   - Є SUPABASE_URL — ОК (публічний)
   - Є SUPABASE_ANON_KEY — ОК (публічний за дизайном, RLS захищає)
   - Немає SERVICE_ROLE_KEY — КРИТИЧНО
   - Немає CLAUDE_API_KEY — КРИТИЧНО
   - Немає TELEGRAM_BOT_TOKEN — КРИТИЧНО
   - Немає паролів, mono-токенів — КРИТИЧНО

6. Тест атаки з ANON KEY (перевірка RLS):
   У консолі DevTools без логіну:
   fetch('SUPABASE_URL/rest/v1/transactions?select=*', {
     headers: { 'apikey': 'ANON_KEY', 'Authorization': 'Bearer ANON_KEY' }
   }).then(r => r.json()).then(console.log)
   -- Має повернути порожній масив [] або 401, НЕ дані

7. Перевірити що обидва користувачі бачать ВСІ дані (сімейний доступ):
   -- Залогінитися як user1 → бачить всі транзакції
   -- Залогінитися як user2 → бачить ті самі транзакції

8. Перевірити що sign up вимкнено:
   sb.auth.signUp({email:'test@test.com', password:'test1234'})
   -- Помилка "Signups not allowed"

9. Перевірити що profiles.mono_token не читається з фронтенду:
   sb.from('profiles').select('mono_token')
   -- Повинно повернути null/порожнє для цього поля
```

---

## ФАЗА 3: Monobank API

### 3.1 — Edge Function: mono-webhook

```
Прочитай CLAUDE.md (Фаза 3 + БЕЗПЕКА).

Створи supabase/functions/mono-webhook/index.ts:

1. Перевірити query ?secret= проти env MONO_WEBHOOK_SECRET
   Якщо не збігається → return 403

2. Парсинг body:
   { type: "StatementItem", data: { account, statementItem: { id, time, description, mcc, amount, currencyCode } } }

3. Конвертація:
   amount_uah = Math.abs(statementItem.amount) / 100
   type = amount < 0 ? 'expense' : 'income'
   date = new Date(time * 1000).toISOString().split('T')[0]

4. Знайти user: profiles where mono_token IS NOT NULL
   Використовувати service_role для обходу RLS.

5. Дедуплікація: select id from transactions where source_id = statementItem.id
   Є → return 200

6. Insert в transactions: { user_id, amount, type, description, source:'mono', source_id, mcc, date }

7. Return 200 OK

Env: MONO_WEBHOOK_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 3.2 — Edge Function: mono-backfill

```
Прочитай CLAUDE.md.

Створи supabase/functions/mono-backfill/index.ts:

1. POST body: { user_id, mono_token, days: 31 }
   Або: читати mono_token з profiles по user_id (service_role).

2. GET /personal/client-info (X-Token) → accounts

3. GET /personal/statement/0/{from}/{to} (account 0, останні N днів)

4. Для кожної транзакції: конвертація + дедуплікація + insert

5. Return { imported, duplicates, errors }

Rate limit: 1 запит на 60с (Monobank обмеження).

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 3.3 — Реєстрація webhook + UI налаштувань

```
Прочитай CLAUDE.md.

1. Edge Function supabase/functions/mono-register-webhook/index.ts:
   - POST body: { mono_token } + auth header (JWT)
   - Отримати user_id з JWT
   - Зберегти mono_token в profiles (service_role, UPDATE ... SET mono_token = ...)
   - POST https://api.monobank.ua/personal/webhook { webHookUrl: ...?secret=... }
   - Return result

2. На фронтенді — екран "Налаштування" (нова вкладка або кнопка в header ⚙️):
   - Поле: "Monobank X-Token"
   - Кнопка "Підключити"
   - Статус: підключено / ні
   - Інструкція: "Отримай токен → api.monobank.ua"
   - Кнопка "Завантажити історію" → викликає mono-backfill

3. Mono token НЕ зберігати в localStorage. Тільки надсилати на сервер при натисканні "Підключити".

Інкрементуй CACHE у sw.js.
```

### 3.4 — Індикатор джерела в UI

```
Прочитай CLAUDE.md.

В списку транзакцій — підпис джерела:
- source='mono' → "monobank" (сірий, 10px)
- source='telegram' → "telegram"
- source='manual' → "вручну"
- mcc → показати поруч: "mono · 5411"
- category_id is null → іконка "?" + "без категорії"

Інкрементуй CACHE у sw.js.
```

---

## ФАЗА 4: Telegram-бот (витрати)

### 4.1 — Edge Function: telegram-webhook (текст)

```
Прочитай CLAUDE.md (Фаза 4 + БЕЗПЕКА → Telegram-бот).

Створи supabase/functions/telegram-webhook/index.ts:

БЕЗПЕКА:
1. Перевірити header X-Telegram-Bot-Api-Secret-Token проти env TELEGRAM_WEBHOOK_SECRET
   Не збігається → return 403
2. chat_id з message.chat.id
3. Whitelist: select id from profiles where telegram_chat_id = chat_id (service_role)
   Не знайдено → sendMessage "Доступ закритий. Використай /start для привʼязки."
   Return 200

ПАРСИНГ:
4. /start <email> <password>:
   - signInWithPassword → отримати user
   - UPDATE profiles SET telegram_chat_id = chat_id WHERE id = user.id
   - Відповідь: "Привʼязано до акаунту <email>"
   - Після привʼязки → видалити повідомлення з паролем (deleteChatMessage)

5. Текст: /^(\+?)(\d+[\.,]?\d*)\s+(.+)$/
   - "+" → income, інакше expense
   - amount, description → insert transactions (source='telegram')
   - Відповідь: "✅ Витрата: 250.00 ₴ — кава"

6. /balance → income - expense за місяць → відповідь
7. /last → останні 5 транзакцій → відповідь

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 4.2 — Telegram-webhook: скріншоти чеків

```
Прочитай CLAUDE.md.

Додати в telegram-webhook обробку фото:

1. message.photo → file_id (останній = найбільший)
2. GET /getFile → file_path → download binary
3. Upload в Supabase Storage: receipts/{user_id}/{timestamp}.jpg (service_role)
4. Конвертувати фото в base64

5. Claude API OCR:
   model: 'claude-haiku-4-5-20251001'
   system: "Розпізнай чек. Відповідай ТІЛЬКИ JSON: [{amount, description, date}]. Не чек → {error: '...'}"
   messages: [{ role:'user', content: [{ type:'image', source:{type:'base64', ...} }, { type:'text', text:'Розпізнай чек' }] }]

6. Парсити → insert transactions (source='telegram', receipt_url = signed URL)
7. Відповідь: "✅ 1 250.00 ₴ — АТБ" або "❌ Не вдалося розпізнати"

Env: CLAUDE_API_KEY (додати)
```

### 4.3 — Реєстрація Telegram webhook

```
Прочитай CLAUDE.md.

Створи supabase/functions/telegram-setup/index.ts:

1. Генерувати secret_token
2. POST /setWebhook { url: .../telegram-webhook, secret_token, allowed_updates: ["message"] }
3. Return result

Створи README-telegram.md з інструкцією:
1. @BotFather → /newbot → TOKEN
2. supabase secrets set TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=...
3. supabase functions deploy telegram-webhook telegram-setup
4. curl POST .../telegram-setup (auth: service_role)
5. В боті: /start email password

Бот НЕ публікувати в каталозі.
```

---

## ФАЗА 5: Telegram-бот (доходи)

### 5.1 — Доходи + дедуплікація

```
Прочитай CLAUDE.md (Фаза 5).

Оновити telegram-webhook:

1. "+" на початку → type='income' (вже є з 4.1, перевірити)

2. Додати /income та /дохід:
   /^[/](income|дохід)\s+(\d+[\.,]?\d*)\s+(.+)$/
   → type='income'
   Відповідь: "✅ Дохід: 51 000 ₴ — зарплата"

3. Дедуплікація з Monobank:
   При type='income' → перевірити:
   select id from transactions
   where source='mono' and type='income'
     and abs(amount - $1) < amount * 0.01
     and date between $2 - 1 and $2 + 1
   Якщо є → відповісти: "⚠️ Схожий дохід є від Monobank (51 000 ₴, 06.04). Додати? /yes"
   /yes → force insert

4. /last → показати income + expense:
   "📋 Останні:
    06.04 +51 000 ₴ зарплата (mono)
    06.04 -250 ₴ АТБ (mono)
    05.04 -80 ₴ маршрутка (tg)"
```

---

## ФАЗА 6: Автокатегоризація

### 6.1 — Edge Function: categorize

```
Прочитай CLAUDE.md (Фаза 6).

Створи supabase/functions/categorize/index.ts:

1. POST { transaction_id }
2. Завантажити транзакцію + категорії user (service_role)
3. hash = md5(description.toLowerCase().trim())
4. Перевірити categorization_cache по hash
   Є → update transactions set category_id, auto_categorized=true → return

5. Claude API:
   model: 'claude-haiku-4-5-20251001', max_tokens: 50
   system: "Категоризуй. Категорії: {id:name,...}. Відповідай ТІЛЬКИ числом — id."
   user: "'{description}', MCC: {mcc}, {amount} грн"

6. Парсити → parseInt
7. Insert в categorization_cache
8. Update transaction
9. Return { category_id }

Env: CLAUDE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

### 6.2 — Виклик з webhook-ів

```
Прочитай CLAUDE.md.

В mono-webhook та telegram-webhook — після insert транзакції:

if (category_id === null) {
  fetch(`${SUPABASE_URL}/functions/v1/categorize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`
    },
    body: JSON.stringify({ transaction_id })
  }).catch(() => {});  // fire-and-forget
}

Транзакції з UI (де категорія вибрана вручну) — НЕ категоризувати.
```

### 6.3 — Ручне перевизначення в UI

```
Прочитай CLAUDE.md.

1. Tap на транзакцію → модалка деталей:
   - Дата, сума, опис, джерело
   - Категорія: dropdown для зміни
   - auto_categorized=true → мітка "🤖 авто"
   - "Зберегти" / "Закрити"

2. При зміні категорії:
   a) update transactions set category_id, auto_categorized=false
   b) upsert categorization_cache (по hash description)
   c) Перезавантажити список

Інкрементуй CACHE у sw.js.
```

### 6.4 — Масова категоризація

```
Прочитай CLAUDE.md.

Створи supabase/functions/categorize-batch/index.ts:

1. POST { user_id, limit: 50 }
2. select transactions where category_id IS NULL and user_id = $1 limit $2
3. Для кожної: перевірка кеш → Claude API → update
4. Затримка 100ms між запитами
5. Return { categorized, from_cache, errors }

На фронтенді (Налаштування):
- "Некатегоризованих: X" + кнопка "Категоризувати"
- Прогрес-індикатор під час роботи

Інкрементуй CACHE у sw.js.
```

---

## ФІНАЛ-ЧЕКЛІСТ

```
Після кожної фази:

☐ git push origin master
☐ GitHub Pages оновився
☐ PWA на мобільному оновилася
☐ Supabase Edge Functions: supabase functions deploy
☐ Secrets: supabase secrets set
☐ Landscape → заглушка "Поверніть пристрій"
☐ Без session → тільки логін, жодних даних
☐ Обидва user бачать всі дані (сімейний доступ)
☐ DevTools: немає secret keys в Network/LocalStorage
☐ Офлайн: додаток відкривається з кешу
```
