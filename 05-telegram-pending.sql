-- 05: відкладений запис Telegram-бота для /yes (Фаза 5.1)
-- Якщо дохід схожий на вже наявний від Monobank, бот не вставляє його, а тримає
-- тут {amount, type, description, date, source_id, expires} до підтвердження /yes
-- (TTL 10 хв). RLS на profiles не змінюється: політика "family full" покриває колонку.

alter table profiles add column if not exists telegram_pending jsonb;
