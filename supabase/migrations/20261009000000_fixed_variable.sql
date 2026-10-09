-- 22: змінна сума постійного платежу і оплата постійного платежу операцією (власник 09.10.2026, DESIGN.md п. 13).
-- variable: сума змінна, amount = середня оцінка (у майбутніх місяцях рахуємо її).
-- transactions.fixed_id: операція-витрата з fixed_id і датою в місяці M закриває платіж місяця M,
-- тоді плановий платіж прибирається з обовʼязкових, білих і каси по датах (факт уже зменшив баланс).
-- Видалення постійного платежу не видаляє операцій: привʼязка скидається в null.
alter table fixed_payments
  add column if not exists variable boolean not null default false;

alter table transactions
  add column if not exists fixed_id bigint null references fixed_payments(id) on delete set null;

create index if not exists transactions_fixed_id_idx on transactions (fixed_id) where fixed_id is not null;

-- Комунальні: сума щомісяця різна, 3 000 у налаштуваннях: середня
update fixed_payments set variable = true where name = 'Комунальні' and variable = false;
