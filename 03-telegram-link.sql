-- 03: одноразовий код привʼязки Telegram (Фаза 4.1)
-- Застосунок генерує 6-значний код і термін дії, бот звіряє його в telegram-webhook
-- і записує telegram_chat_id. RLS на profiles не змінюється: політика "family full"
-- через is_family_member() уже покриває нові колонки.

alter table profiles
  add column if not exists telegram_link_code text,
  add column if not exists telegram_link_expires timestamptz;

-- Один chat_id належить одному профілю (бот перед записом відвʼязує попередній)
create unique index if not exists idx_profiles_tg_chat
  on profiles(telegram_chat_id) where telegram_chat_id is not null;
