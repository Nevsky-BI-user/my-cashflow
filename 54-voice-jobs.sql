-- 54: черга мовного сервісу на ноутбуці власника (голосові в Telegram-боті).
-- Бот кладе завдання (розпізнати голосове або озвучити відповідь), ноутбук сам забирає їх через функцію voice-jobs
-- і здає результат. До ноутбука ніхто не підключається. Записи живуть секунди: бот видаляє завдання, щойно забрав
-- результат; прострочені (старші за 10 хв) видаляє кожен прихід ноутбука.
-- Доступ лише service_role (бот і функція voice-jobs): RLS увімкнено без політик, anon і authenticated без прав.
-- Таблиці не в публікації realtime. Повторне застосування безпечне.
create table if not exists public.voice_jobs (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('stt', 'tts')),
  status text not null default 'queued' check (status in ('queued', 'claimed', 'done', 'failed')),
  input jsonb not null,
  output jsonb,
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  done_at timestamptz
);
create index if not exists voice_jobs_queued on public.voice_jobs (id) where status = 'queued';
alter table public.voice_jobs enable row level security;
revoke all on public.voice_jobs from anon, authenticated;

-- Мітка «ноутбук на звʼязку»: один рядок, оновлюється на кожному приході ноутбука
create table if not exists public.voice_worker (
  id smallint primary key default 1 check (id = 1),
  last_seen timestamptz not null default now(),
  info jsonb
);
alter table public.voice_worker enable row level security;
revoke all on public.voice_worker from anon, authenticated;

-- Прихід ноутбука: мітка звʼязку і прибирання прострочених завдань (раз на довге очікування, не на кожен опит)
create or replace function public.voice_heartbeat(p_info jsonb default null) returns void
language plpgsql security definer set search_path = public as $$
begin
  insert into voice_worker (id, last_seen, info) values (1, now(), p_info)
    on conflict (id) do update set last_seen = now(), info = coalesce(excluded.info, voice_worker.info);
  delete from voice_jobs where created_at < now() - interval '10 minutes';
end $$;

-- Взяти одне завдання атомарно: лише свіже (бот чекає недовго), лише одному виконавцю
create or replace function public.voice_claim(p_max_age_s int default 40)
returns table (id bigint, kind text, input jsonb)
language sql security definer set search_path = public as $$
  update voice_jobs j set status = 'claimed', claimed_at = now()
  where j.id = (
    select q.id from voice_jobs q
    where q.status = 'queued' and q.created_at > now() - make_interval(secs => p_max_age_s)
    order by q.id limit 1 for update skip locked
  )
  returning j.id, j.kind, j.input;
$$;

-- Здати результат: лише завдання, яке ще чекає (бот міг уже видалити його за таймаутом)
create or replace function public.voice_done(p_id bigint, p_ok boolean, p_output jsonb) returns boolean
language sql security definer set search_path = public as $$
  with u as (
    update voice_jobs set status = case when p_ok then 'done' else 'failed' end, output = p_output, done_at = now()
    where id = p_id and status = 'claimed'
    returning 1
  )
  select exists (select 1 from u);
$$;

revoke execute on function public.voice_heartbeat(jsonb) from public, anon, authenticated;
revoke execute on function public.voice_claim(int) from public, anon, authenticated;
revoke execute on function public.voice_done(bigint, boolean, jsonb) from public, anon, authenticated;
grant execute on function public.voice_heartbeat(jsonb) to service_role;
grant execute on function public.voice_claim(int) to service_role;
grant execute on function public.voice_done(bigint, boolean, jsonb) to service_role;
comment on table public.voice_jobs is 'Черга мовного сервісу: розпізнати голосове (stt) чи озвучити відповідь (tts). Записи живуть секунди.';
comment on table public.voice_worker is 'Мітка звʼязку мовного сервісу на ноутбуці власника.';
