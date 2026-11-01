-- Основа зарплати дозволяє актуалізувати активний план, зберігаючи ручний розподіл.
alter table public.monthly_budgets
  add column if not exists income_basis_cents bigint;
do $$ begin
  if not exists (select 1 from pg_constraint where conrelid='public.monthly_budgets'::regclass and conname='monthly_budgets_income_basis_valid') then
    alter table public.monthly_budgets add constraint monthly_budgets_income_basis_valid
      check (income_basis_cents is null or income_basis_cents between 0 and 9007199254740991);
  end if;
end $$;
