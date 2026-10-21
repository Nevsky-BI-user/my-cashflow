-- Щорічні платежі та дата зобовʼязання.
alter table public.fixed_payments add column if not exists month_of_year smallint;
alter table public.fixed_payments drop constraint if exists fixed_payments_period_chk;
alter table public.fixed_payments add constraint fixed_payments_period_chk check (
  period in ('month','week','year')
  and (period <> 'week' or (weekday is not null and weekday between 1 and 7))
  and (period <> 'year' or (month_of_year is not null and month_of_year between 1 and 12))
);
alter table public.transactions add column if not exists payment_due_date date;
