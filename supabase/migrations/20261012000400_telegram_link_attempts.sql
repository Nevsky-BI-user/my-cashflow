-- 28: невдалі спроби привʼязки Telegram кодом, для ліміту 5 на годину з одного чату.
-- Пише й читає лише функція telegram-webhook (service_role); RLS увімкнено без політик: з клієнта таблиця недоступна.
create table if not exists telegram_link_attempts (
  id bigint generated always as identity primary key,
  chat_id bigint not null,
  at timestamptz not null default now()
);
create index if not exists telegram_link_attempts_chat_at on telegram_link_attempts (chat_id, at);
alter table telegram_link_attempts enable row level security;
