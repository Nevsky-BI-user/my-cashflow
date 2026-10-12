-- 25: макрокатегорії і підказки категорій для автокатегоризації (власник 12.10.2026).
-- category_groups: макрокатегорія (Їжа, Дім, Транспорт...), categories.group_id: до якої належить категорія.
-- categories.hint: приклади продавців і покупок, ідуть у запит автокатегоризації.
create table if not exists category_groups (
  id bigserial primary key,
  name text not null,
  icon text,
  color text,
  sort_order int not null default 0
);
alter table category_groups enable row level security;
drop policy if exists "family full" on category_groups;
create policy "family full" on category_groups for all
  using (is_family_member()) with check (is_family_member());

alter table categories
  add column if not exists group_id bigint null references category_groups(id) on delete set null,
  add column if not exists hint text null;

insert into category_groups (id, name, icon, color, sort_order) values
  (1, 'Їжа', '🍽', '#a8d672', 1),
  (2, 'Дім', '🏠', '#6fd3b0', 2),
  (3, 'Транспорт', '🚗', '#7fa8f2', 3),
  (4, 'Здоровʼя і краса', '💊', '#f28b82', 4),
  (5, 'Дитина', '👶', '#f6d06f', 5),
  (6, 'Одяг і взуття', '👕', '#f09ac0', 6),
  (7, 'Відпочинок', '🎉', '#f7a876', 7),
  (8, 'Звʼязок і підписки', '📱', '#a58ff0', 8),
  (9, 'Подарунки', '🎁', '#d78de6', 9),
  (10, 'Інше', '⋯', '#b8c1cc', 10)
on conflict (id) do nothing;
select setval('category_groups_id_seq', greatest((select max(id) from category_groups), 1));

-- Нові категорії: ліміт 0, сімейні (user_id як у Продуктів)
insert into categories (user_id, name, icon, color, budget_limit, sort_order, is_income, locked)
select c.user_id, v.name, v.icon, v.color, 0, v.so, false, true
from (values
  ('Доставка їжі', '🛵', '#f7a876', 14),
  ('Послуги для дому', '🧹', '#6fd3b0', 15),
  ('Комунальні', '💡', '#6ec6e8', 16),
  ('Доставка і пошта', '📦', '#7fa8f2', 17),
  ('Краса і догляд', '💄', '#f09ac0', 18),
  ('Подорожі', '✈️', '#f7a876', 19),
  ('Спорт', '🏋️', '#6fd3b0', 20),
  ('Благодійність', '🤝', '#d78de6', 21)
) as v(name, icon, color, so)
cross join (select user_id from categories where id = 1) c
where not exists (select 1 from categories x where x.name = v.name and not x.is_income);

-- Групи й підказки
update categories c set group_id = v.g, hint = v.h from (values
  ('Продукти', 1, 'супермаркети і продукти: АТБ, Сільпо, Novus, Fora, мʼясна лавка, ринок'),
  ('Кафе/Ресторани', 1, 'кафе, ресторани, кавʼярні, фастфуд у закладі'),
  ('Доставка їжі', 1, 'Glovo, Bolt Food, Uklon їжа, доставка піци чи суші'),
  ('Дім', 2, 'товари для дому і побуту, господарчі, сантехніка, інструменти, меблі, газ'),
  ('Послуги для дому', 2, 'прибирання, клінінг, майстри, ремонт у квартирі'),
  ('Комунальні', 2, 'комунальні платежі, світло, вода, опалення, ОСББ'),
  ('Транспорт', 3, 'таксі Uklon, Bolt, Uber, метро, проїзд, квитки на потяг і автобус'),
  ('Авто', 3, 'пальне ОККО, WOG, BRSM, UPG, мийка, СТО, запчастини, паркування, страховка авто'),
  ('Доставка і пошта', 3, 'Нова пошта, Укрпошта, Meest, доставка посилок'),
  ('Здоровʼя', 4, 'аптеки (Подорожник, АНЦ, Liki24, APTEKA), лікарі, клініки, аналізи'),
  ('Краса і догляд', 4, 'косметика, MAKEUP, EVA, Watsons, Prostor, барбершоп, перукарня, манікюр'),
  ('Дитина', 5, 'садочок, дитячі магазини (Немовлятко, Антошка), іграшки, дитячий одяг'),
  ('Одяг', 6, 'одяг і взуття, магазини одягу'),
  ('Розваги', 7, 'кіно, концерти, ігри, розваги'),
  ('Подорожі', 7, 'готелі, квитки в подорож, Booking, туризм'),
  ('Спорт', 7, 'спортзал, секції, спортивні товари'),
  ('Звʼязок', 8, 'мобільний звʼязок, інтернет: Київстар, Vodafone, lifecell, провайдер'),
  ('Підписки', 8, 'Claude, Anthropic, OpenAI, ChatGPT, YouTube, Netflix, OKKO (кінотеатр), Spotify, Apple, Google'),
  ('Подарунки', 9, 'подарунки, квіти'),
  ('Благодійність', 9, 'донати, благодійні фонди'),
  ('Інше', 10, 'усе, що не підходить до інших категорій')
) as v(name, g, h)
where c.name = v.name and not c.is_income;
