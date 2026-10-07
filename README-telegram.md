# Telegram-бот: підключення

Бот приватний: не публікувати в каталозі, не вмикати inline-режим. Привʼязка до акаунта
лише одноразовим кодом із застосунку (email/password у боті не буває).

## 1. Створити бота

1. У Telegram відкрити @BotFather, надіслати `/newbot`, задати назву й username.
2. Скопіювати токен виду `123456789:AAH...` (він показується один раз).
3. `/setprivacy` -> Enable (бот читає лише повідомлення, адресовані йому).

## 2. Секрети (PowerShell, у теці репозиторію, по одній команді)

Токен вставити замість `<TOKEN>`; секрет webhook генерується на місці:

```
npx -y supabase@latest secrets set TELEGRAM_BOT_TOKEN=<TOKEN>
```

```
npx -y supabase@latest secrets set TELEGRAM_WEBHOOK_SECRET=$([guid]::NewGuid().ToString())
```

Для чеків і автокатегоризації ще ключ Claude API (console.anthropic.com):

```
npx -y supabase@latest secrets set CLAUDE_API_KEY=<KEY>
```

## 3. Міграція й деплой

```
npx -y supabase@latest db push
```

```
npx -y supabase@latest functions deploy telegram-webhook telegram-setup categorize categorize-batch
```

У Dashboard -> Storage має бути приватний bucket `receipts` (для фото чеків).

## 4. Реєстрація webhook і привʼязка

1. У застосунку: шестерня -> блок Telegram -> «Підключити бота». Відповідь «Бот підключено: @ім'я».
2. «Код для Telegram» -> у боті надіслати `/start 123456` (код діє 10 хв).
3. Перевірка: `250 кава` -> «✅ Витрата: 250,00 ₴, кава»; `/last`, `/balance`.

## Команди бота

| Текст | Дія |
|---|---|
| `250 кава` | витрата 250 ₴ з описом «кава» |
| `+51000 зарплата` | дохід |
| `/income 51000 зарплата` або `/дохід ...` | дохід |
| `/yes` | підтвердити дохід, схожий на запис Monobank (бот сам запитає) |
| фото чека | сума й магазин розпізнаються, запис із чеком |
| `/balance` | доходи, витрати, баланс за поточний місяць |
| `/last` | останні 5 записів |
| `/help` | підказка |

Суми без пробілів-роздільників: «1 250 кава» прочитається як 1 ₴ з описом «250 кава».

## Якщо не працює

- 403 у логах `telegram-webhook`: секрет у Telegram не збігається з `TELEGRAM_WEBHOOK_SECRET`; натиснути «Підключити бота» ще раз.
- «Доступ закритий»: chat_id не привʼязаний; згенерувати код і надіслати `/start <код>`.
- Логи: Dashboard -> Edge Functions -> telegram-webhook -> Logs.
