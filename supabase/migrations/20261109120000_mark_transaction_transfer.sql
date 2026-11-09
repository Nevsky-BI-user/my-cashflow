-- Позначити вже записану операцію як переказ між власними рахунками.
-- Друга половина: наявна зустрічна операція (та сама сума, дата ±3 дні) або нова ручна.
-- Нова половина отримує час першої (не пізніше кінця дня переказу), тож баланс, оновлений після переказу, не віднімається вдруге.
create or replace function public.mark_transaction_transfer(
 p_request_id uuid,p_transaction_id bigint,p_other_account_id bigint,p_actor_id uuid default null
) returns uuid language plpgsql security definer set search_path=pg_catalog,public as $$
declare actor uuid; tx public.transactions%rowtype; mate public.transactions%rowtype; own_acc public.accounts%rowtype; other public.accounts%rowtype; prior public.account_transfers%rowtype; src_id bigint; dst_id bigint;
begin
 actor:=auth.uid();
 if auth.role()='service_role' then actor:=p_actor_id; elsif p_actor_id is not null and p_actor_id is distinct from actor then raise exception 'Invalid actor'; end if;
 if actor is null or not exists(select 1 from auth.users where id=actor and lower(email) in ('gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com')) then raise exception 'Forbidden'; end if;
 if p_request_id is null or p_transaction_id is null or p_other_account_id is null then raise exception 'Invalid transfer'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_request_id::text,0));
 select * into prior from public.account_transfers where id=p_request_id;
 if found then
  if prior.user_id<>actor or p_transaction_id not in(coalesce(prior.from_import_id,0),coalesce(prior.to_import_id,0)) or p_other_account_id not in(prior.from_account_id,prior.to_account_id) then raise exception 'Request conflict'; end if;
  return prior.id;
 end if;
 select * into tx from public.transactions where id=p_transaction_id for update;
 if tx.id is null or tx.account_id is null or tx.type not in('income','expense') or tx.amount is null or tx.amount<=0 then raise exception 'Invalid operation'; end if;
 if tx.transfer_id is not null then raise exception 'Already a transfer'; end if;
 if tx.fixed_id is not null or tx.credit_id is not null or jsonb_array_length(tx.expense_allocations)>0 or exists(select 1 from public.salary_payouts where transaction_id=tx.id) then raise exception 'Operation is linked'; end if;
 if tx.account_id=p_other_account_id then raise exception 'Same account'; end if;
 perform id from public.accounts where id in(tx.account_id,p_other_account_id) order by id for update;
 select * into own_acc from public.accounts where id=tx.account_id;
 select * into other from public.accounts where id=p_other_account_id and active=true;
 if own_acc.id is null or other.id is null then raise exception 'Invalid accounts'; end if;
 -- Зустрічна операція: протилежний тип, та сама сума, дата ±3 дні, ще не привʼязана; найближча за датою
 select t.* into mate from public.transactions t
  where t.account_id=other.id and t.type=(case when tx.type='income' then 'expense' else 'income' end) and t.amount=tx.amount
   and t.date between tx.date-3 and tx.date+3 and t.transfer_id is null and t.fixed_id is null and t.credit_id is null
   and jsonb_array_length(t.expense_allocations)=0 and not exists(select 1 from public.salary_payouts s where s.transaction_id=t.id)
  order by abs(t.date-tx.date),t.id limit 1 for update;
 if mate.id is null and other.mono_account_id is not null then raise exception 'Mono counterpart not found'; end if;
 if tx.type='income' then src_id:=other.id;dst_id:=own_acc.id; else src_id:=own_acc.id;dst_id:=other.id; end if;
 insert into public.account_transfers(id,user_id,from_account_id,to_account_id,amount,date,from_import_id,to_import_id)
  values(p_request_id,actor,src_id,dst_id,tx.amount,tx.date,
   case when tx.type='expense' then tx.id else mate.id end,case when tx.type='income' then tx.id else mate.id end);
 perform set_config('cashflow.transfer_write','yes',true);
 update public.transactions set transfer_id=p_request_id,category_id=null,auto_categorized=false where id=tx.id;
 if mate.id is not null then update public.transactions set transfer_id=p_request_id,category_id=null,auto_categorized=false where id=mate.id;
 else insert into public.transactions(user_id,account_id,type,amount,date,created_at,description,source,source_id,transfer_id)
  values(actor,other.id,case when tx.type='income' then 'expense' else 'income' end,tx.amount,tx.date,least(tx.created_at,((tx.date+1)::timestamp at time zone 'Europe/Kyiv')-interval '1 second'),
   case when tx.type='income' then 'Переказ на '||own_acc.name else 'Переказ з '||own_acc.name end,'manual','transfer:'||p_request_id||':'||case when tx.type='income' then 'expense' else 'income' end,p_request_id); end if;
 perform set_config('cashflow.transfer_write','no',true);
 return p_request_id;
end $$;
revoke all on function public.mark_transaction_transfer(uuid,bigint,bigint,uuid) from public,anon;
grant execute on function public.mark_transaction_transfer(uuid,bigint,bigint,uuid) to authenticated,service_role;
