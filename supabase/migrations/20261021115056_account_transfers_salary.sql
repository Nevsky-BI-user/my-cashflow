-- Атомарні внутрішні перекази та підтверджені виплати.
create table if not exists public.account_transfers (
 id uuid primary key, user_id uuid not null references public.profiles(id),
 from_account_id bigint not null references public.accounts(id), to_account_id bigint not null references public.accounts(id),
 amount numeric(12,2) not null check(amount>0), date date not null, created_at timestamptz not null default now(),
 from_import_id bigint references public.transactions(id), to_import_id bigint references public.transactions(id),
 check(from_account_id<>to_account_id)
);
alter table public.account_transfers enable row level security;
drop policy if exists "family read" on public.account_transfers;
create policy "family read" on public.account_transfers for select to authenticated using(public.is_family_member());
grant select on public.account_transfers to authenticated;
revoke insert,update,delete on public.account_transfers from authenticated,anon;
alter table public.transactions add column if not exists transfer_id uuid references public.account_transfers(id);
create unique index if not exists transactions_transfer_leg_unique on public.transactions(transfer_id,type) where transfer_id is not null;

create or replace function public.guard_transfer_leg() returns trigger language plpgsql set search_path=pg_catalog,public as $$
begin
 if (case when TG_OP='DELETE' then old.transfer_id is not null when TG_OP='INSERT' then new.transfer_id is not null else old.transfer_id is not null or new.transfer_id is not null end)
 and not (current_setting('cashflow.transfer_write',true)='yes' and current_user=pg_get_userbyid((select relowner from pg_class where oid='public.account_transfers'::regclass))) then
  raise exception 'Linked transfer legs must be changed atomically';
 end if;
 if TG_OP='DELETE' then return old; end if; return new;
end $$;
drop trigger if exists guard_transfer_leg on public.transactions;
create trigger guard_transfer_leg before insert or update or delete on public.transactions for each row execute function public.guard_transfer_leg();

create or replace function public.record_account_transfer(
 p_request_id uuid,p_from_account_id bigint,p_to_account_id bigint,p_amount numeric,p_date date,
 p_from_transaction_id bigint default null,p_to_transaction_id bigint default null,p_actor_id uuid default null
) returns uuid language plpgsql security definer set search_path=pg_catalog,public as $$
declare actor uuid; src public.accounts%rowtype; dst public.accounts%rowtype; prior public.account_transfers%rowtype; tr public.transactions%rowtype; own numeric; debt numeric; r record;
begin
 actor:=auth.uid();
 if auth.role()='service_role' then actor:=p_actor_id; elsif p_actor_id is not null and p_actor_id is distinct from actor then raise exception 'Invalid actor'; end if;
 if actor is null or not exists(select 1 from auth.users where id=actor and lower(email) in ('gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com')) then raise exception 'Forbidden'; end if;
 if p_request_id is null or p_from_account_id=p_to_account_id or p_amount is null or p_amount::text in ('NaN','Infinity','-Infinity') or p_amount<=0 or p_amount<>round(p_amount,2) or p_date is null or p_date>(now() at time zone 'Europe/Kyiv')::date then raise exception 'Invalid transfer'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_request_id::text,0));
 select * into prior from public.account_transfers where id=p_request_id;
 if found then
  if prior.from_account_id<>p_from_account_id or prior.to_account_id<>p_to_account_id or prior.amount<>p_amount or prior.date<>p_date or prior.user_id<>actor or prior.from_import_id is distinct from p_from_transaction_id or prior.to_import_id is distinct from p_to_transaction_id then raise exception 'Request conflict'; end if;
  return prior.id;
 end if;
 perform id from public.accounts where id in(p_from_account_id,p_to_account_id) order by id for update;
 select * into src from public.accounts where id=p_from_account_id and active=true;
 select * into dst from public.accounts where id=p_to_account_id and active=true;
 if src.id is null or dst.id is null or dst.kind<>'credit' then raise exception 'Invalid accounts'; end if;
 if dst.mono_account_id is null and dst.balance_updated_at is null then raise exception 'Target balance has no timestamp';end if;
 if (src.mono_account_id is not null)<>(p_from_transaction_id is not null) or (dst.mono_account_id is not null)<>(p_to_transaction_id is not null) then raise exception 'Select imported Mono operations'; end if;
 if p_from_transaction_id is not null then
  select * into tr from public.transactions where id=p_from_transaction_id for update;
  if tr.id is null or tr.account_id is distinct from src.id or tr.type is distinct from 'expense' or tr.source is distinct from 'mono' or tr.amount is distinct from p_amount or tr.date is distinct from p_date or tr.transfer_id is not null or tr.fixed_id is not null or tr.credit_id is not null or exists(select 1 from public.salary_payouts where transaction_id=tr.id) then raise exception 'Invalid source operation'; end if;
 else
  own:=coalesce(src.balance,0);debt:=greatest(0,coalesce(src.debt,0));
  if src.balance_updated_at is null then raise exception 'Source balance has no timestamp'; end if;
  for r in select type,amount from public.transactions where account_id=src.id and created_at>src.balance_updated_at and date<=(now() at time zone 'Europe/Kyiv')::date order by created_at,id loop
   if src.kind='credit' then
    if r.type='income' then own:=own+greatest(0,r.amount-debt);debt:=greatest(0,debt-r.amount);
    else debt:=debt+greatest(0,r.amount-greatest(0,own));own:=greatest(0,own-r.amount);end if;
   else own:=own+case when r.type='income' then r.amount else -r.amount end;end if;
  end loop;
  if own<p_amount then raise exception 'Insufficient own funds';end if;
 end if;
 if p_to_transaction_id is not null then
  select * into tr from public.transactions where id=p_to_transaction_id for update;
  if tr.id is null or tr.account_id is distinct from dst.id or tr.type is distinct from 'income' or tr.source is distinct from 'mono' or tr.amount is distinct from p_amount or tr.date is distinct from p_date or tr.transfer_id is not null or tr.fixed_id is not null or tr.credit_id is not null or exists(select 1 from public.salary_payouts where transaction_id=tr.id) then raise exception 'Invalid target operation'; end if;
 end if;
 insert into public.account_transfers(id,user_id,from_account_id,to_account_id,amount,date,from_import_id,to_import_id) values(p_request_id,actor,src.id,dst.id,p_amount,p_date,p_from_transaction_id,p_to_transaction_id);
 perform set_config('cashflow.transfer_write','yes',true);
 if p_from_transaction_id is not null then update public.transactions set transfer_id=p_request_id where id=p_from_transaction_id;
 else insert into public.transactions(user_id,account_id,type,amount,date,description,source,source_id,transfer_id) values(actor,src.id,'expense',p_amount,p_date,'Переказ на '||dst.name,'manual','transfer:'||p_request_id||':expense',p_request_id); end if;
 if p_to_transaction_id is not null then update public.transactions set transfer_id=p_request_id where id=p_to_transaction_id;
 else insert into public.transactions(user_id,account_id,type,amount,date,description,source,source_id,transfer_id) values(actor,dst.id,'income',p_amount,p_date,'Переказ з '||src.name,'manual','transfer:'||p_request_id||':income',p_request_id); end if;
 perform set_config('cashflow.transfer_write','no',true);
 return p_request_id;
end $$;
revoke all on function public.record_account_transfer(uuid,bigint,bigint,numeric,date,bigint,bigint,uuid) from public,anon;
grant execute on function public.record_account_transfer(uuid,bigint,bigint,numeric,date,bigint,bigint,uuid) to authenticated,service_role;

create table if not exists public.salary_payouts (
 account_id bigint not null references public.accounts(id),kind text not null check(kind in('salary','advance')),due_date date not null,
 transaction_id bigint not null unique references public.transactions(id),user_id uuid not null references public.profiles(id),created_at timestamptz not null default now(),
 primary key(account_id,kind,due_date)
);
alter table public.salary_payouts enable row level security;
drop policy if exists "family read" on public.salary_payouts;
create policy "family read" on public.salary_payouts for select to authenticated using(public.is_family_member());
grant select on public.salary_payouts to authenticated;
revoke insert,update,delete on public.salary_payouts from authenticated,anon;
-- Суму й конфігурацію обчислює сервер бота; клієнт не має EXECUTE.
create or replace function public.guard_salary_identity() returns trigger language plpgsql security definer set search_path=pg_catalog,public as $$
begin
 if row(new.account_id,new.type,new.amount,new.date,new.transfer_id,new.source,new.source_id) is distinct from row(old.account_id,old.type,old.amount,old.date,old.transfer_id,old.source,old.source_id)
    and exists(select 1 from public.salary_payouts where transaction_id=old.id) then
  raise exception 'Claimed salary income identity cannot be changed';
 end if;
 return new;
end $$;
drop trigger if exists guard_salary_identity on public.transactions;
create trigger guard_salary_identity before update on public.transactions for each row execute function public.guard_salary_identity();
create or replace function public.record_salary_payout(p_account_id bigint,p_due_date date,p_kind text,p_amount numeric,p_actor_id uuid,p_existing_tx_id bigint default null)
returns bigint language plpgsql security definer set search_path=pg_catalog,public as $$
declare a public.accounts%rowtype; tx public.transactions%rowtype; result bigint; ids bigint[]; today date:=(now() at time zone 'Europe/Kyiv')::date;
begin
 if auth.role() is distinct from 'service_role' or p_actor_id is null or not exists(select 1 from auth.users where id=p_actor_id and lower(email) in('gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com')) then raise exception 'Forbidden';end if;
 if p_due_date is null or p_due_date>today or p_kind is null or p_kind not in('salary','advance') or p_amount is null or p_amount::text in ('NaN','Infinity','-Infinity') or p_amount<=0 or p_amount<>round(p_amount,2) then raise exception 'Invalid payout';end if;
 select * into a from public.accounts where id=p_account_id and active=true and is_salary=true for update;
 if a.id is null then raise exception 'Salary account unavailable';end if;
 select transaction_id into result from public.salary_payouts where account_id=a.id and kind=p_kind and due_date=p_due_date;
 if result is not null then return result;end if;
 if p_existing_tx_id is null then
  select array_agg(t.id order by t.id) into ids from public.transactions t where t.account_id=a.id and t.type='income' and t.amount=p_amount and t.date between p_due_date-3 and least(p_due_date+3,today) and t.transfer_id is null and not exists(select 1 from public.salary_payouts s where s.transaction_id=t.id);
  if cardinality(ids)>1 then raise exception 'Ambiguous existing income';end if;
  p_existing_tx_id:=ids[1];
 end if;
 if p_existing_tx_id is not null then
  select * into tx from public.transactions where id=p_existing_tx_id for update;
  if tx.id is null or tx.account_id is distinct from a.id or tx.type is distinct from 'income' or tx.amount is distinct from p_amount or tx.date<p_due_date-3 or tx.date>today or tx.transfer_id is not null or (a.mono_account_id is not null and tx.source is distinct from 'mono') then raise exception 'Invalid existing income';end if;
  if exists(select 1 from public.salary_payouts where transaction_id=tx.id) then raise exception 'Income already claimed by another payout';end if;
  result:=tx.id;
 else
  if a.mono_account_id is not null then raise exception 'Awaiting Mono income';end if;
  insert into public.transactions(user_id,account_id,type,amount,date,description,source,source_id) values(p_actor_id,a.id,'income',p_amount,today,case when p_kind='salary' then 'Зарплата' else 'Аванс' end,'telegram','salary:'||a.id||':'||p_kind||':'||p_due_date) returning id into result;
 end if;
 insert into public.salary_payouts(account_id,kind,due_date,transaction_id,user_id) values(a.id,p_kind,p_due_date,result,p_actor_id);
 return result;
end $$;
revoke all on function public.record_salary_payout(bigint,date,text,numeric,uuid,bigint) from public,anon,authenticated;
grant execute on function public.record_salary_payout(bigint,date,text,numeric,uuid,bigint) to service_role;
