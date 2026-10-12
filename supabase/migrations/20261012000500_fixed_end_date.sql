-- 29: постійний дохід або витрата з останньою датою (власник 12.10.2026).
-- type: 'payment' (витрата, як було) або 'income' (постійний дохід поза зарплатою й авансом).
-- end_date: остання дата, коли платіж ще буде; null = безстроково. Після неї подій немає.
alter table fixed_payments
  add column if not exists end_date date null;

alter table fixed_payments drop constraint if exists fixed_payments_type_chk;
alter table fixed_payments add constraint fixed_payments_type_chk
  check (type in ('payment', 'income'));
