-- Окремий план календарного місяця; наявні плани між виплатами не переносимо.
create or replace function public.monthly_budget_allocations_valid(
  allocations jsonb,
  total_cents bigint
) returns boolean
language plpgsql
immutable
security invoker
set search_path = pg_catalog
as $$
declare
  allocation record;
  amount numeric;
  allocated numeric := 0;
begin
  if allocations is null or jsonb_typeof(allocations) <> 'object'
     or total_cents is null or total_cents < 0
     or total_cents > 9007199254740991 then
    return false;
  end if;

  for allocation in select key, value from jsonb_each(allocations) loop
    -- Ідентифікатори категорій зберігаються й після приховування категорії.
    if allocation.key !~ '^[1-9][0-9]*$'
       or jsonb_typeof(allocation.value) <> 'number' then
      return false;
    end if;
    amount := allocation.value::text::numeric;
    if amount < 0 or amount > 9007199254740991 or amount <> trunc(amount) then
      return false;
    end if;
    allocated := allocated + amount;
    if allocated > total_cents then
      return false;
    end if;
  end loop;
  return true;
end;
$$;

revoke all on function public.monthly_budget_allocations_valid(jsonb, bigint) from public, anon;
grant execute on function public.monthly_budget_allocations_valid(jsonb, bigint)
  to authenticated, service_role;

create table if not exists public.monthly_budgets (
  month_start date primary key,
  total_cents bigint not null,
  allocations jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint monthly_budgets_first_day
    check (isfinite(month_start) and extract(day from month_start) = 1),
  constraint monthly_budgets_total_safe
    check (total_cents between 0 and 9007199254740991),
  constraint monthly_budgets_allocations_valid
    check (public.monthly_budget_allocations_valid(allocations, total_cents))
);

alter table public.monthly_budgets enable row level security;
drop policy if exists "family full" on public.monthly_budgets;
create policy "family full" on public.monthly_budgets for all
  using (public.is_family_member()) with check (public.is_family_member());

-- Права API не замінюють перевірку сімейного whitelist у RLS.
revoke all on public.monthly_budgets from public, anon, authenticated;
grant select, insert, update, delete on public.monthly_budgets to authenticated;
grant all on public.monthly_budgets to service_role;

do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public' and tablename = 'monthly_budgets'
  ) then
    alter publication supabase_realtime add table public.monthly_budgets;
  end if;
end;
$$;
