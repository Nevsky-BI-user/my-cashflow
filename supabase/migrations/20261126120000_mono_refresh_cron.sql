-- 56: баланс Monobank без відкриття застосунку (функція mono-refresh).
-- pg_cron кожні 30 хв кличе функцію через pg_net. Функція сама дотримується ліміту Monobank (client-info раз на 60 с
-- на токен): свіжий знімок не запитує вдруге, відповідь 429 нічого не пише. Відповідь лише з лічильниками, без балансів.
-- Секрет НЕ пишеться в цей файл і в git: cron читає його з Supabase Vault на кожному запуску (як telegram-digest, міграція 27).
-- Покласти секрет один раз (SQL Editor у Dashboard, те саме значення, що в `supabase secrets set MONO_REFRESH_SECRET=...`):
--   select vault.create_secret('<секрет>', 'mono_refresh_secret', 'Заголовок x-mono-refresh-secret для mono-refresh');
-- Змінити пізніше:
--   select vault.update_secret((select id from vault.secrets where name = 'mono_refresh_secret'), '<новий секрет>');
-- Без секрету у Vault заголовок порожній і функція відповідає 403: нічого не оновлюється.
-- Курси (rates-refresh) у cron не додаються: їх читає лише застосунок і сам оновлює, коли курсам понад 12 год.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

-- Повторне застосування міграції не плодить другу задачу
select cron.unschedule(jobid) from cron.job where jobname = 'mono-refresh';

select cron.schedule(
  'mono-refresh',
  '*/30 * * * *',
  $$
  select net.http_post(
    url := 'https://lisedsqwdzshsxydghag.supabase.co/functions/v1/mono-refresh',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-mono-refresh-secret', coalesce((select decrypted_secret from vault.decrypted_secrets where name = 'mono_refresh_secret'), '')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 30000
  );
  $$
);
