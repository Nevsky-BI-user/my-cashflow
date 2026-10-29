-- Майбутні ставки зберігаються окремо від базової: минулі виплати не перераховуються.
create or replace function public.salary_rate_schedule_valid(schedule jsonb)
returns boolean language plpgsql immutable security invoker
set search_path = pg_catalog
as $$
declare
  item jsonb;
  effective text;
  previous_date text := '';
  amount numeric;
begin
  if schedule is null or jsonb_typeof(schedule) <> 'array' then return false; end if;
  for item in select value from jsonb_array_elements(schedule) loop
    if jsonb_typeof(item) <> 'object'
      or jsonb_typeof(item->'effective_from') is distinct from 'string'
      or jsonb_typeof(item->'rate') is distinct from 'number'
      or (select count(*) from jsonb_object_keys(item)) <> 2 then return false; end if;
    effective := item->>'effective_from';
    if effective !~ '^\d{4}-\d{2}-\d{2}$' or effective < '2000-01-01'
      or effective > '9999-12-31' or effective <= previous_date then return false; end if;
    -- Перетворення на date відхиляє неіснуючі дати, наприклад 31 лютого.
    perform effective::date;
    amount := (item->>'rate')::numeric;
    if amount <= 0 or amount > 9999999999.99 then return false; end if;
    previous_date := effective;
  end loop;
  return true;
exception when others then
  return false;
end;
$$;
revoke all on function public.salary_rate_schedule_valid(jsonb) from public, anon;
grant execute on function public.salary_rate_schedule_valid(jsonb) to authenticated, service_role;

alter table public.salary_config add column if not exists rate_schedule jsonb not null default '[]'::jsonb;
alter table public.salary_config drop constraint if exists salary_config_rate_schedule_check;
alter table public.salary_config add constraint salary_config_rate_schedule_check
  check (public.salary_rate_schedule_valid(rate_schedule));
-- Чинні RLS та сімейний whitelist залишаються на таблиці salary_config.
