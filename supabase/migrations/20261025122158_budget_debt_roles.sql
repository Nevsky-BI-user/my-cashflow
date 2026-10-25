-- Системні бюджетні резерви боргу не є категоріями звичайних витрат.
alter table public.categories add column if not exists budget_role text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.categories'::regclass
      and conname = 'categories_budget_role_check'
  ) then
    alter table public.categories add constraint categories_budget_role_check
      check (budget_role is null or
        (is_income is false and budget_role in ('debt_card', 'debt_installment')));
  end if;
end $$;

create unique index if not exists categories_budget_role_unique
  on public.categories (budget_role) where budget_role is not null;

insert into public.category_groups (name, icon, color, sort_order)
select 'Погашення боргу', '💳', '#5f86a8', coalesce(max(sort_order), 0) + 1
from public.category_groups
having not exists (
  select 1 from public.category_groups where name = 'Погашення боргу'
);

-- Наявні категорії та їхні історичні розподіли не перепризначаються.
with definitions(role, name, icon, color, position) as (
  values
    ('debt_card', 'Погашення кредиток', '💳', '#5f86a8', 1),
    ('debt_installment', 'Додаткове погашення розстрочок', '🧾', '#8c78a5', 2)
), owner as (
  select user_id from public.categories
  where user_id is not null and is_income is false
  order by id limit 1
), ordering as (
  select coalesce(max(sort_order), 0) as last_position from public.categories
)
insert into public.categories
  (user_id, name, icon, color, budget_limit, limit_abs, sort_order, is_income, locked, group_id, budget_role)
select owner.user_id, d.name, d.icon, d.color, 0, null,
  ordering.last_position + d.position, false, false,
  (select id from public.category_groups where name = 'Погашення боргу' order by id limit 1), d.role
from definitions d cross join owner cross join ordering
where not exists (select 1 from public.categories c where c.budget_role = d.role);

comment on column public.categories.budget_role is
  'Системний резерв місячного бюджету: не звичайна витрата й не фактичний платіж.';
