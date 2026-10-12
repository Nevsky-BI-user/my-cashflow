-- 24: щотижневі постійні платежі, банк постійного платежу, оплата розстрочки операцією (власник 12.10.2026).
-- period: 'month' (день місяця day_of_month) або 'week' (день тижня weekday, ISO 1 = понеділок ... 7 = неділя).
-- Тижневий платіж закриває витрата з fixed_id і датою в тому самому тижні пн-нд.
-- bank: звідки платимо (oschad, privat, mono, cash, other), як accounts.bank і credits.source.
-- transactions.credit_id: витрата оплачує розстрочку місяця своєї дати; її не рахуємо змінною витратою.
alter table fixed_payments
  add column if not exists period text not null default 'month',
  add column if not exists weekday smallint null,
  add column if not exists bank text null;

alter table fixed_payments drop constraint if exists fixed_payments_period_chk;
alter table fixed_payments add constraint fixed_payments_period_chk
  check (period in ('month', 'week') and (period = 'month' or weekday between 1 and 7));

alter table transactions
  add column if not exists credit_id bigint null references credits(id) on delete set null;

create index if not exists transactions_credit_id_idx on transactions (credit_id) where credit_id is not null;
