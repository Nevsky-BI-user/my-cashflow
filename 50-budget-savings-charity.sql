-- Додаємо лише відсутні спільні видаткові категорії без зміни наявного розподілу.
-- Власник береться з наявних категорій сімʼї; персональних ідентифікаторів у міграції немає.
with definitions(name, icon, color, group_name, position) as (
  values
    ('Заощадження', '🐷', '#477b65', 'Інше', 1),
    ('Благодійність', '💗', '#a94d6d', 'Подарунки', 2)
), owner as (
  select user_id from public.categories
  where user_id is not null and is_income = false
  order by id limit 1
), ordering as (
  select coalesce(max(sort_order), 0) as last_position from public.categories
)
insert into public.categories
  (user_id, name, icon, color, budget_limit, limit_abs, sort_order, is_income, locked, group_id)
select owner.user_id, d.name, d.icon, d.color, 0, null,
  ordering.last_position + d.position, false, false,
  (select id from public.category_groups where name = d.group_name order by id limit 1)
from definitions d cross join owner cross join ordering
where not exists (
  select 1 from public.categories c
  where c.is_income = false and lower(trim(c.name)) = lower(d.name)
);
