-- 52: курси НБУ і ПриватБанку в exchange_rates, курс внеску в savings_log, щоденне оновлення курсів.
-- Повторне застосування безпечне: if not exists, перевірка обмежень і перестворення політик та задачі cron.

-- 1. exchange_rates: джерело курсу. Наявні рядки (USD/EUR, оновлені вручну 17.04.2026) були курсом ПриватБанку.
alter table public.exchange_rates add column if not exists source text;
update public.exchange_rates set source = 'privat' where source is null;
alter table public.exchange_rates alter column source set default 'privat';
alter table public.exchange_rates alter column source set not null;

do $$
begin
  if not exists (select 1 from pg_constraint where conrelid = 'public.exchange_rates'::regclass and conname = 'exchange_rates_source_check') then
    alter table public.exchange_rates add constraint exchange_rates_source_check check (source in ('nbu', 'privat'));
  end if;
  if not exists (select 1 from pg_constraint where conrelid = 'public.exchange_rates'::regclass and conname = 'exchange_rates_positive_check') then
    alter table public.exchange_rates add constraint exchange_rates_positive_check check (buy > 0 and sale > 0);
  end if;
  -- upsert функції rates-refresh іде за (ccy, source)
  if not exists (select 1 from pg_constraint where conrelid = 'public.exchange_rates'::regclass and conname = 'exchange_rates_ccy_source_key') then
    alter table public.exchange_rates add constraint exchange_rates_ccy_source_key unique (ccy, source);
  end if;
end $$;

comment on column public.exchange_rates.source is
  'nbu: офіційний курс НБУ (buy = sale = rate); privat: готівковий курс ПриватБанку (buy купує банк, sale продає банк).';

-- RLS: читає лише сімʼя, пише лише service role (функція rates-refresh). Політики без insert/update/delete.
alter table public.exchange_rates enable row level security;
drop policy if exists "auth read" on public.exchange_rates;
drop policy if exists "family full" on public.exchange_rates;
drop policy if exists "family read" on public.exchange_rates;
create policy "family read" on public.exchange_rates for select using (public.is_family_member());
revoke insert, update, delete, truncate on public.exchange_rates from anon, authenticated;

-- 2. savings_log: курс на момент внеску (гривень за 1 одиницю валюти) і його джерело.
-- Старі внески лишаються без курсу: їх не заповнюємо жодним іншим курсом.
alter table public.savings_log add column if not exists rate numeric;
alter table public.savings_log add column if not exists rate_source text;

do $$
begin
  if not exists (select 1 from pg_constraint where conrelid = 'public.savings_log'::regclass and conname = 'savings_log_rate_check') then
    alter table public.savings_log add constraint savings_log_rate_check check (rate is null or rate > 0);
  end if;
  if not exists (select 1 from pg_constraint where conrelid = 'public.savings_log'::regclass and conname = 'savings_log_rate_source_check') then
    alter table public.savings_log add constraint savings_log_rate_source_check
      check (rate_source is null or rate_source in ('privat', 'nbu', 'manual'));
  end if;
end $$;

comment on column public.savings_log.rate is 'Курс внеску: гривень за 1 одиницю валюти на дату внеску; для UAH порожньо.';
comment on column public.savings_log.rate_source is 'Звідки курс внеску: privat, nbu або manual (введено вручну).';

-- 3. Щоденне оновлення курсів: pg_cron о 04:10 UTC (06:10 або 07:10 за Києвом) кличе rates-refresh через pg_net.
-- Ключ НЕ пишеться в цей файл і в git: cron читає його з Supabase Vault на кожному запуску.
-- Покласти ключ один раз (SQL Editor у Dashboard; значення: service_role key з Project Settings, API):
--   select vault.create_secret('<service role key>', 'rates_refresh_service_key', 'Bearer для rates-refresh з pg_cron');
-- Без ключа у Vault заголовок порожній, функція відповідає 401 і нічого не пише; застосунок тоді оновлює курси сам.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

select cron.unschedule(jobid) from cron.job where jobname = 'rates-refresh';

select cron.schedule(
  'rates-refresh',
  '10 4 * * *',
  $$
  select net.http_post(
    url := 'https://lisedsqwdzshsxydghag.supabase.co/functions/v1/rates-refresh',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || coalesce((select decrypted_secret from vault.decrypted_secrets where name = 'rates_refresh_service_key'), '')
    ),
    body := '{"force":true}'::jsonb,
    timeout_milliseconds := 30000
  );
  $$
);
