-- 13: мʼяка райдужна палітра (10 кольорів по колу) для категорій і розстрочок.
-- Кольори йдуть за порядком сортування, тому сусідні категорії перетікають одна в одну.
with pal as (
  select array['#f28b82','#f7a876','#f6d06f','#a8d672','#6fd3b0','#6ec6e8','#7fa8f2','#a58ff0','#d78de6','#f09ac0'] as c
),
ordered as (
  select id, row_number() over (order by is_income, sort_order, id) as rn from categories
)
update categories k
set color = (select c from pal)[((o.rn - 1) % 10) + 1]
from ordered o
where o.id = k.id;

with pal as (
  select array['#f28b82','#f7a876','#f6d06f','#a8d672','#6fd3b0','#6ec6e8','#7fa8f2','#a58ff0','#d78de6','#f09ac0'] as c
),
ordered as (
  select id, row_number() over (order by start_year, start_month, id) as rn from credits
)
update credits k
set color = (select c from pal)[((o.rn - 1) * 3 % 10) + 1]
from ordered o
where o.id = k.id;

-- Постійні платежі: витрати теплим, доходи мʼятним
update fixed_payments set color = case when type = 'income' then '#6fd3b0' else '#f7a876' end;
