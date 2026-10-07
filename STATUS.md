# Статус розробки

Оновлюється на кожному кроці. Легенда: [x] зроблено, [ ] у черзі, [~] у роботі, (ти) крок, який робить власник у терміналі або в Dashboard.

## Посилання

- Застосунок: https://nevsky-bi-user.github.io/my-cashflow/
- Репозиторій: https://github.com/Nevsky-BI-user/my-cashflow
- Supabase Dashboard: https://supabase.com/dashboard/project/lisedsqwdzshsxydghag
- SQL Editor: https://supabase.com/dashboard/project/lisedsqwdzshsxydghag/sql/new
- Edge Functions і логи: https://supabase.com/dashboard/project/lisedsqwdzshsxydghag/functions

## Бекенд (стан на 07.10.2026)

- [x] Проєкт Supabase відновлено з паузи, `ACTIVE_HEALTHY`
- [x] CLI залогінений і привʼязаний до проєкту
- [x] Функції задеплоєно: mono-webhook, mono-register, mono-backfill, telegram-webhook
- [x] Секрет MONO_WEBHOOK_SECRET
- [ ] (ти) Міграції 03, 04, 05 (`db push`): код привʼязки Telegram, унікальний source_id, telegram_pending
- [ ] (ти) Секрети TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET (README-telegram.md)
- [ ] (ти) Деплой: `functions deploy telegram-webhook telegram-setup categorize`
- [ ] (ти) Секрет CLAUDE_API_KEY (console.anthropic.com)
- [ ] (ти) Перевірити в Dashboard, що bucket `receipts` існує і приватний
- [ ] (ти) Фаза 3 вручну: шестерня -> X-Token -> «Автооновлення» -> «Історія 31 день»

## План

### Фаза 3: Monobank
- [x] 3.1-3.4 код
- [ ] (ти) ручна перевірка на телефоні: транзакції Mono в «Потоці»

### Фаза 4: Telegram-бот (витрати)
- [x] 4.1 telegram-webhook: текст, /start <код>, /balance, /last (коміт 5b0bfb8)
- [x] 4.3 telegram-setup + кнопка «Підключити бота» + README-telegram.md
- [ ] (ти) BotFather, секрети, деплой, «Підключити бота», /start <код>, тест «250 кава»
- [x] 4.2 фото чеків: Storage + Claude API vision (бекенд: secrets set CLAUDE_API_KEY, deploy telegram-webhook, bucket receipts приватний)

### Фаза 5: Telegram-бот (доходи)
- [x] 5.1 /income, дедуплікація з Monobank, /yes (міграція 05, deploy telegram-webhook)

### Фаза 6: Автокатегоризація
- [x] 6.1 categorize (Haiku 4.5, кеш по hash), deploy categorize
- [ ] 6.2 виклик із webhook-ів
- [ ] 6.3 модалка деталей транзакції, зміна категорії
- [ ] 6.4 categorize-batch + кнопка в налаштуваннях

## Рішення, що чекають на власника

1. Запасна модель для чеків у 4.2: `claude-sonnet-5-5` дорожча за бюджет ~$0.10/міс; старт на Haiku 4.5.
2. `/balance` у боті рахує до сьогодні; записи з датою наперед не входять.
3. `supabase-schema.sql` лишається «початковою» схемою, нові колонки живуть у міграціях `NN-*.sql`.
