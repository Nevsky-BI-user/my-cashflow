-- 14: рахунки (картки, готівка) з балансами і борг кредитної картки.
-- Правило власника: борг, що утворився в місяці M, закривається до 25-го числа місяця M+1.
create table if not exists accounts (
  id serial primary key,
  user_id uuid references profiles(id) not null,
  name text not null,
  bank text,                      -- 'privat' | 'mono' | 'oschad' | 'cash' | 'other'
  kind text not null default 'debit' check (kind in ('debit','credit','cash')),
  balance numeric(12,2) not null default 0,   -- власні кошти на рахунку
  debt numeric(12,2) not null default 0,      -- борг кредитної картки (додатне число)
  debt_month date,                            -- перше число місяця, у якому борг утворився
  credit_limit numeric(12,2),
  color text,
  sort_order int default 0,
  active boolean default true,
  balance_updated_at timestamptz default now()
);

alter table accounts enable row level security;
drop policy if exists "family full" on accounts;
create policy "family full" on accounts for all
  using (public.is_family_member()) with check (public.is_family_member());

-- Привʼязка операцій до рахунку на майбутнє (необовʼязкова)
alter table transactions add column if not exists account_id int references accounts(id);

-- Стартові рахунки власника (08.10.2026): Ощадбанк 5 000 ₴; ПриватБанк кредитна, борг 10 000 ₴ за вересень
insert into accounts (user_id, name, bank, kind, balance, debt, debt_month, color, sort_order)
select p.id, v.name, v.bank, v.kind, v.balance, v.debt, v.debt_month, v.color, v.sort_order
from (select distinct user_id as id from categories) p
cross join (values
  ('Ощадбанк',            'oschad', 'debit',  5000.00,     0.00, null::date,          '#6fd3b0', 0),
  ('ПриватБанк кредитна', 'privat', 'credit',    0.00, 10000.00, date '2026-09-01',   '#f28b82', 1)
) as v(name, bank, kind, balance, debt, debt_month, color, sort_order)
where not exists (select 1 from accounts a where a.user_id = p.id and a.name = v.name);
