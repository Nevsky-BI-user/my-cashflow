-- 17: рахунок Monobank для живого балансу (функція mono-balance) і привʼязка mono-операцій до нього.
-- Рахунок належить власнику X-Token (profiles.mono_token): на нього ж пишуться mono-транзакції.
alter table accounts add column if not exists mono_account_id text;   -- id рахунку з Monobank API (client-info)
alter table accounts add column if not exists currency text default 'UAH';

insert into accounts (user_id, name, bank, kind, balance, color, sort_order, is_salary)
select p.id, 'Monobank', 'mono', 'debit', 0, '#111827', 2, false
from profiles p
where p.mono_token is not null
  and not exists (select 1 from accounts a where a.user_id = p.id and a.bank = 'mono');

-- Наявні mono-операції без рахунку: привʼязати до рахунку Monobank того ж користувача
update transactions set account_id = (
  select a.id from accounts a
  where a.bank = 'mono' and a.user_id = transactions.user_id
  order by a.id limit 1
)
where source = 'mono' and account_id is null;
