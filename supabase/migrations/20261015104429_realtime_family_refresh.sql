-- Автооновлення сімейного застосунку: payload використовується лише як сигнал
-- перечитування даних. RLS, SELECT-політики й права ця міграція не змінює.
-- Дев'ять таблиць відповідають ресурсам екранів; старі локальні міграції
-- не потрібно застосовувати разом із цією. Повторне виконання безпечне.
do $$
declare
  table_name text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;

  foreach table_name in array array[
    'transactions', 'accounts', 'fixed_payments', 'credits', 'categories',
    'category_groups', 'salary_config', 'savings_log', 'goals'
  ] loop
    if not exists (
      select 1 from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relname = table_name
        and c.relkind = 'r' and c.relrowsecurity
    ) then
      raise exception 'Realtime requires an existing RLS-enabled public table: %', table_name;
    end if;

    if not exists (
      select 1 from pg_publication_tables p
      where p.pubname = 'supabase_realtime' and p.schemaname = 'public'
        and p.tablename = table_name
    ) then
      execute format('alter publication supabase_realtime add table public.%I', table_name);
    end if;
  end loop;
end $$;
