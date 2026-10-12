-- 27: ранковий підсумок і нагадування в Telegram (функція telegram-digest).
-- pg_cron щогодини о :00 UTC кличе функцію через pg_net; функція сама відсіює все, крім 9-ї години за Києвом,
-- тож літній і зимовий час не потребують зміни розкладу.
-- Секрет НЕ пишеться в цей файл і в git: cron читає його з Supabase Vault на кожному запуску.
-- Покласти секрет один раз (SQL Editor у Dashboard, те саме значення, що в `supabase secrets set DIGEST_SECRET=...`):
--   select vault.create_secret('<секрет>', 'telegram_digest_secret', 'Заголовок x-digest-secret для telegram-digest');
-- Змінити пізніше:
--   select vault.update_secret((select id from vault.secrets where name = 'telegram_digest_secret'), '<новий секрет>');
-- Без секрету у Vault заголовок порожній і функція відповідає 403: нічого не надсилається.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

-- Повторне застосування міграції не плодить другу задачу
select cron.unschedule(jobid) from cron.job where jobname = 'telegram-digest';

select cron.schedule(
  'telegram-digest',
  '0 * * * *',
  $$
  select net.http_post(
    url := 'https://lisedsqwdzshsxydghag.supabase.co/functions/v1/telegram-digest',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-digest-secret', coalesce((select decrypted_secret from vault.decrypted_secrets where name = 'telegram_digest_secret'), '')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 30000
  );
  $$
);
