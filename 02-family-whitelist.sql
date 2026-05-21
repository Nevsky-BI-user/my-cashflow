-- ============================================
-- 02-family-whitelist.sql
-- Whitelist по email замість "auth.uid() is not null"
-- Виконати у Supabase Dashboard → SQL Editor → New Query
-- ============================================

-- ============================================
-- 1. Функція whitelist
-- ============================================
create or replace function public.is_family_member() returns boolean
  language sql
  security definer
  stable
  set search_path = public, auth
as $$
  select exists (
    select 1
    from auth.users
    where id = auth.uid()
      and lower(email) = any (array[
        'gotnewmess@gmail.com',
        'kovtunenko.yulchik@gmail.com'
      ])
  );
$$;

grant execute on function public.is_family_member() to authenticated, anon;

-- ============================================
-- 2. Видалення старих політик
-- ============================================
drop policy if exists "auth full" on public.profiles;
drop policy if exists "auth full" on public.categories;
drop policy if exists "auth full" on public.transactions;
drop policy if exists "auth full" on public.credits;
drop policy if exists "auth full" on public.goals;
drop policy if exists "auth read" on public.categorization_cache;

-- ============================================
-- 3. Нові політики на основі whitelist
-- ============================================
create policy "family full" on public.profiles for all
  using (public.is_family_member()) with check (public.is_family_member());

create policy "family full" on public.categories for all
  using (public.is_family_member()) with check (public.is_family_member());

create policy "family full" on public.transactions for all
  using (public.is_family_member()) with check (public.is_family_member());

create policy "family full" on public.credits for all
  using (public.is_family_member()) with check (public.is_family_member());

create policy "family full" on public.goals for all
  using (public.is_family_member()) with check (public.is_family_member());

create policy "family read" on public.categorization_cache for select
  using (public.is_family_member());
-- INSERT/UPDATE через service_role (Edge Functions)

-- ============================================
-- 4. Додаткові таблиці (якщо існують)
-- savings_log, fixed_payments, exchange_rates, salary_config
-- ============================================
do $$
declare
  t text;
  tables text[] := array['savings_log','fixed_payments','exchange_rates','salary_config'];
begin
  foreach t in array tables loop
    if exists (select 1 from information_schema.tables
               where table_schema='public' and table_name=t) then
      execute format('alter table public.%I enable row level security', t);
      execute format('drop policy if exists "auth full" on public.%I', t);
      execute format('drop policy if exists "family full" on public.%I', t);
      execute format(
        'create policy "family full" on public.%I for all using (public.is_family_member()) with check (public.is_family_member())',
        t
      );
    end if;
  end loop;
end $$;

-- ============================================
-- 5. Storage — bucket "receipts"
-- ============================================
drop policy if exists "auth upload receipts" on storage.objects;
drop policy if exists "auth read receipts" on storage.objects;
drop policy if exists "auth delete receipts" on storage.objects;

create policy "family upload receipts" on storage.objects for insert
  with check (bucket_id = 'receipts' and public.is_family_member());

create policy "family read receipts" on storage.objects for select
  using (bucket_id = 'receipts' and public.is_family_member());

create policy "family delete receipts" on storage.objects for delete
  using (bucket_id = 'receipts' and public.is_family_member());

-- ============================================
-- 6. Тест (виконати залогінившись через Google як один з whitelist-користувачів)
-- ============================================
-- select public.is_family_member();   -- має повернути true
-- select count(*) from public.transactions;   -- має повернути число (не помилку)
