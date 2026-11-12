-- v215: виправлення суми підтвердженої виплати з Telegram-бота (кнопка «✏️ Змінити суму»).
-- Тригер guard_salary_identity (міграція 20261021115056) забороняє будь-яку зміну amount доходу з salary_payouts.
-- Тепер зміна лише суми проходить, коли її робить функція update_salary_payout_amount у межах тієї самої транзакції БД
-- (локальний параметр cashflow.salary_amount_edit = id операції). Рахунок, тип, дата, джерело й source_id незмінні, як і раніше.
-- Повторне застосування безпечне: create or replace.

create or replace function public.guard_salary_identity() returns trigger language plpgsql security definer set search_path=pg_catalog,public as $$
begin
 if row(new.account_id,new.type,new.amount,new.date,new.transfer_id,new.source,new.source_id) is distinct from row(old.account_id,old.type,old.amount,old.date,old.transfer_id,old.source,old.source_id)
    and exists(select 1 from public.salary_payouts where transaction_id=old.id) then
  if row(new.account_id,new.type,new.date,new.transfer_id,new.source,new.source_id) is not distinct from row(old.account_id,old.type,old.date,old.transfer_id,old.source,old.source_id)
     and coalesce(current_setting('cashflow.salary_amount_edit',true),'')=old.id::text then
   return new;
  end if;
  raise exception 'Claimed salary income identity cannot be changed';
 end if;
 return new;
end $$;

-- Лише сервер бота (service_role) від імені сімейного акаунта; сума з Monobank не змінюється (її задає банк).
create or replace function public.update_salary_payout_amount(p_tx_id bigint,p_amount numeric,p_actor_id uuid)
returns numeric language plpgsql security definer set search_path=pg_catalog,public as $$
declare tx public.transactions%rowtype;
begin
 if auth.role() is distinct from 'service_role' or p_actor_id is null or not exists(select 1 from auth.users where id=p_actor_id and lower(email) in('gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com')) then raise exception 'Forbidden';end if;
 if p_amount is null or p_amount::text in ('NaN','Infinity','-Infinity') or p_amount<=0 or p_amount>10000000 or p_amount<>round(p_amount,2) then raise exception 'Invalid amount';end if;
 select * into tx from public.transactions where id=p_tx_id for update;
 if tx.id is null or not exists(select 1 from public.salary_payouts where transaction_id=tx.id) then raise exception 'Salary payout not found';end if;
 if tx.type is distinct from 'income' or tx.transfer_id is not null or tx.source='mono' then raise exception 'Amount cannot be changed';end if;
 if tx.amount=p_amount then return p_amount;end if;
 perform set_config('cashflow.salary_amount_edit',tx.id::text,true);
 update public.transactions set amount=p_amount where id=tx.id;
 perform set_config('cashflow.salary_amount_edit','',true);
 return p_amount;
end $$;
revoke all on function public.update_salary_payout_amount(bigint,numeric,uuid) from public,anon,authenticated;
grant execute on function public.update_salary_payout_amount(bigint,numeric,uuid) to service_role;
