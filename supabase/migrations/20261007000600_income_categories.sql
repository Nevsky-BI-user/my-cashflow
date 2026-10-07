-- 09: дохідні категорії (is_income = true), без яких доходи не категоризуються.
-- Без них categorize віддає no_categories на всі доходи (Mono «Від: ...», /income у боті).
-- Категорії сімейні (RLS віддає обом усе), тому додаємо їх тому профілю,
-- який уже володіє витратними, а не кожному. Ідемпотентно: лише відсутні назви.
insert into categories (user_id, name, icon, color, sort_order, is_income)
select p.id, c.name, c.icon, c.color, c.sort_order, true
from (select distinct user_id as id from categories) p
cross join (values
  ('Зарплата',     '💼', '#58d68d', 101),
  ('Аванс',        '💼', '#7dcea0', 102),
  ('Фріланс',      '💻', '#5dade2', 103),
  ('Повернення',   '↩️', '#a0a4ff', 104),
  ('Подарунок',    '🎁', '#f5b041', 105),
  ('Інший дохід',  '📈', '#95a5a6', 106)
) as c(name, icon, color, sort_order)
where not exists (
  select 1 from categories x
  where x.user_id = p.id and x.name = c.name and x.is_income = true
);

-- Доходи, що вичерпали спроби через відсутність категорій, знову підбирає categorize-batch
update transactions
set categorize_attempts = 0
where type = 'income' and category_id is null and categorize_attempts > 0;
