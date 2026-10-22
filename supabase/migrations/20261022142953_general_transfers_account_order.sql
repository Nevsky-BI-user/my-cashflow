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
 if src.id is null or dst.id is null then raise exception 'Invalid accounts'; end if;
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

create or replace function public.reorder_accounts(p_account_ids bigint[]) returns void
language plpgsql security invoker set search_path=pg_catalog,public as $$
declare active_ids bigint[]; supplied_ids bigint[];
begin
 if auth.uid() is null or not public.is_family_member() then raise exception 'Forbidden';end if;
 if p_account_ids is null or coalesce(array_ndims(p_account_ids),1)<>1 or array_position(p_account_ids,null) is not null then raise exception 'Invalid account order';end if;
 lock table public.accounts in share row exclusive mode;
 perform id from public.accounts where active=true order by id for update;
 select coalesce(array_agg(id order by id),'{}'::bigint[]) into active_ids from public.accounts where active=true;
 select coalesce(array_agg(id order by id),'{}'::bigint[]) into supplied_ids from unnest(p_account_ids) as x(id);
 if supplied_ids is distinct from active_ids then raise exception 'Account order must include every active account exactly once';end if;
 update public.accounts a set sort_order=(x.position-1)::integer from unnest(p_account_ids) with ordinality as x(id,position) where a.id=x.id;
end $$;
revoke all on function public.reorder_accounts(bigint[]) from public,anon,service_role;
grant execute on function public.reorder_accounts(bigint[]) to authenticated;
