-- ============================================
-- Сімейний Кешфлоу — Supabase Schema + RLS
-- ============================================

-- Профілі користувачів
create table profiles (
  id uuid primary key references auth.users(id),
  display_name text,
  mono_token text,
  telegram_chat_id bigint,
  created_at timestamptz default now()
);

-- Категорії витрат
create table categories (
  id serial primary key,
  user_id uuid references profiles(id) not null,
  name text not null,
  icon text,
  color text,
  budget_limit numeric(12,2),
  sort_order int default 0,
  is_income boolean default false
);

-- Транзакції
create table transactions (
  id bigserial primary key,
  user_id uuid references profiles(id) not null,
  amount numeric(12,2) not null,
  type text not null check (type in ('income','expense')),
  category_id int references categories(id),
  description text,
  source text check (source in ('mono','telegram','manual')),
  source_id text,
  mcc int,
  receipt_url text,
  auto_categorized boolean default false,
  date date not null,
  created_at timestamptz default now()
);

-- Кредити / розстрочки
create table credits (
  id serial primary key,
  user_id uuid references profiles(id) not null,
  name text not null,
  monthly_amount numeric(12,2) not null,
  payment_day int not null,
  start_year int not null,
  start_month int not null,
  total_payments int not null,
  color text,
  source text
);

-- Цілі накопичень
create table goals (
  id serial primary key,
  user_id uuid references profiles(id) not null,
  name text not null,
  target_amount numeric(12,2) not null,
  current_amount numeric(12,2) default 0,
  color text,
  description text,
  sort_order int default 0
);

-- Кеш категоризації (спільний, без user_id)
create table categorization_cache (
  id serial primary key,
  description_hash text unique not null,
  description text not null,
  category_id int references categories(id),
  mcc int,
  created_at timestamptz default now()
);

-- ============================================
-- ІНДЕКСИ
-- ============================================
create index idx_tx_user_date on transactions(user_id, date desc);
create index idx_tx_source_id on transactions(source_id);
create index idx_cache_hash on categorization_cache(description_hash);

-- ============================================
-- RLS
-- ============================================
alter table profiles enable row level security;
alter table categories enable row level security;
alter table transactions enable row level security;
alter table credits enable row level security;
alter table goals enable row level security;
alter table categorization_cache enable row level security;

-- СІМЕЙНИЙ ДОДАТОК: обидва користувачі бачать ВСІ дані
-- RLS перевіряє тільки що користувач автентифікований (auth.uid() is not null)

-- profiles
create policy "auth full" on profiles for all using (auth.uid() is not null) with check (auth.uid() is not null);

-- categories
create policy "auth full" on categories for all using (auth.uid() is not null) with check (auth.uid() is not null);

-- transactions
create policy "auth full" on transactions for all using (auth.uid() is not null) with check (auth.uid() is not null);

-- credits
create policy "auth full" on credits for all using (auth.uid() is not null) with check (auth.uid() is not null);

-- goals
create policy "auth full" on goals for all using (auth.uid() is not null) with check (auth.uid() is not null);

-- categorization_cache
create policy "auth read" on categorization_cache for select using (auth.uid() is not null);
-- insert/update через service_role (Edge Functions)

-- ============================================
-- TRIGGER: auto-create profile при створенні auth.user
-- ============================================
create or replace function handle_new_user() returns trigger as $$
begin
  insert into public.profiles (id) values (new.id);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- ============================================
-- SEED DATA
-- Замінити 'USER_UUID' на реальний UUID після створення акаунтів
-- ============================================

-- Категорії (13 шт)
-- INSERT INTO categories (user_id, name, icon, color, budget_limit, sort_order) VALUES
-- ('USER_UUID', 'Продукти', '🛒', '#f472b6', 15000, 1),
-- ('USER_UUID', 'Кафе/Ресторани', '☕', '#fb923c', 2000, 2),
-- ('USER_UUID', 'Транспорт', '🚌', '#94a3b8', 500, 3),
-- ('USER_UUID', 'Авто', '🚗', '#60a5fa', 8900, 4),
-- ('USER_UUID', 'Зв''язок', '📱', '#a78bfa', 500, 5),
-- ('USER_UUID', 'Підписки', '📺', '#c084fc', 2000, 6),
-- ('USER_UUID', 'Дитина', '👶', '#f9a8d4', 6000, 7),
-- ('USER_UUID', 'Здоров''я', '💊', '#34d399', 2000, 8),
-- ('USER_UUID', 'Одяг', '👔', '#fbbf24', 1500, 9),
-- ('USER_UUID', 'Дім', '🏠', '#fb7185', 1500, 10),
-- ('USER_UUID', 'Розваги', '🎬', '#22d3ee', 1500, 11),
-- ('USER_UUID', 'Подарунки', '🎁', '#e879f9', 800, 12),
-- ('USER_UUID', 'Інше', '📦', '#6b7280', 1800, 13);

-- Кредити (4 шт)
-- INSERT INTO credits (user_id, name, monthly_amount, payment_day, start_year, start_month, total_payments, color, source) VALUES
-- ('USER_UUID', 'Канцтовж', 3731.88, 11, 2026, 3, 8, '#a78bfa', 'mono'),
-- ('USER_UUID', 'Навушники', 111.07, 21, 2026, 2, 11, '#fb923c', 'mono'),
-- ('USER_UUID', 'Lenovo Legion 5 Pro', 6133.27, 24, 2026, 1, 15, '#34d399', 'privat'),
-- ('USER_UUID', 'Аерогриль', 683.25, 17, 2026, 3, 12, '#fbbf24', 'privat');

-- Цілі (3 шт)
-- INSERT INTO goals (user_id, name, target_amount, current_amount, color, description, sort_order) VALUES
-- ('USER_UUID', 'Подушка безпеки', 240000, 49800, '#22d3ee', '3 міс витрат', 1),
-- ('USER_UUID', 'Фонд Авто', 415000, 0, '#60a5fa', 'б/в кросовер $10k', 2),
-- ('USER_UUID', 'Фонд Житло', 830000, 0, '#a78bfa', 'перший внесок $20k', 3);
