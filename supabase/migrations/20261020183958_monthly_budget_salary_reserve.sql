-- NULL зберігає попередній ручний план; масив фіксує резерв із зарплати.
alter table public.monthly_budgets
  add column if not exists mandatory_items jsonb;

create or replace function public.monthly_budget_salary_valid(
  month_start date,
  total_cents bigint,
  allocations jsonb,
  mandatory_items jsonb
) returns boolean
language plpgsql
immutable
security invoker
set search_path = pg_catalog
as $$
declare
  item jsonb;
  item_date date;
  amount numeric;
  reserved numeric := 0;
  seen_keys text[] := array[]::text[];
begin
  if month_start is null or not isfinite(month_start)
     or extract(day from month_start) <> 1
     or total_cents is null or total_cents < 0
     or total_cents > 9007199254740991 then
    return false;
  end if;
  if mandatory_items is null then
    return public.monthly_budget_allocations_valid(allocations, total_cents);
  end if;
  if jsonb_typeof(mandatory_items) <> 'array' then
    return false;
  end if;
  for item in select value from jsonb_array_elements(mandatory_items) loop
    if jsonb_typeof(item) <> 'object' then return false; end if;
    if not (item ?& array['key','date','name','amount_cents','kind'])
       or item - array['key','date','name','amount_cents','kind','estimated'] <> '{}'::jsonb
       or jsonb_typeof(item->'key') <> 'string'
       or jsonb_typeof(item->'date') <> 'string'
       or jsonb_typeof(item->'name') <> 'string'
       or jsonb_typeof(item->'kind') <> 'string'
       or jsonb_typeof(item->'amount_cents') <> 'number'
       or (item ? 'estimated' and jsonb_typeof(item->'estimated') <> 'boolean') then
      return false;
    end if;
    if item->>'kind' not in ('fixed','installment')
       or length(btrim(item->>'name')) = 0 or length(item->>'name') > 240
       or item->>'date' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
       or item->>'key' !~ ('^' || (item->>'kind') || ':[A-Za-z0-9_-]{1,80}:' || (item->>'date') || '$')
       or item->>'key' = any(seen_keys) then
      return false;
    end if;
    begin
      item_date := (item->>'date')::date;
    exception when invalid_datetime_format or datetime_field_overflow then
      return false;
    end;
    if not isfinite(item_date)
       or extract(year from item_date) <> extract(year from month_start)
       or extract(month from item_date) <> extract(month from month_start) then
      return false;
    end if;
    amount := (item->>'amount_cents')::numeric;
    if amount < 0 or amount > 9007199254740991 or amount <> trunc(amount) then
      return false;
    end if;
    reserved := reserved + amount;
    if reserved > 9007199254740991 then return false; end if;
    seen_keys := array_append(seen_keys, item->>'key');
  end loop;
  -- Дефіцит обов'язкових платежів дозволений, але розподіл тоді нульовий.
  return public.monthly_budget_allocations_valid(
    allocations, greatest(0::numeric, total_cents::numeric - reserved)::bigint
  );
end;
$$;

revoke all on function public.monthly_budget_salary_valid(date, bigint, jsonb, jsonb)
  from public, anon;
grant execute on function public.monthly_budget_salary_valid(date, bigint, jsonb, jsonb)
  to authenticated, service_role;

-- Решту обмежень, політики доступу та підписку Realtime не змінюємо.
alter table public.monthly_budgets
  drop constraint if exists monthly_budgets_salary_valid;
alter table public.monthly_budgets
  add constraint monthly_budgets_salary_valid check (
    public.monthly_budget_salary_valid(month_start, total_cents, allocations, mandatory_items)
  );
