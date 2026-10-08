-- 20: рахунок операції з Telegram і похідний баланс ручних рахунків.
-- Похідний баланс рахунку без mono_account_id = збережений баланс + операції з цим account_id,
-- створені після balance_updated_at. Тому будь-яка ручна зміна балансу чи боргу мусить зсувати мітку.
-- mono-balance пише balance_updated_at сам: якщо мітку в запиті змінено, тригер її не чіпає.
create or replace function public.accounts_touch_balance() returns trigger
  language plpgsql as $$
begin
  if (new.balance is distinct from old.balance or new.debt is distinct from old.debt)
     and new.balance_updated_at is not distinct from old.balance_updated_at then
    new.balance_updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists accounts_touch_balance on accounts;
create trigger accounts_touch_balance
  before update on accounts
  for each row execute function public.accounts_touch_balance();

-- Сьогоднішні витрати з бота (08.10.2026) були з Ощадбанку
update transactions set account_id = 1 where id in (31, 32) and account_id is null;
