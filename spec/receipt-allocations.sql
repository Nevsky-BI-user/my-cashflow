-- Інтеграційна перевірка у транзакції. Усі синтетичні дані відкочуються.
-- Запуск після міграції зі службового SQL-з’єднання; не запускати частинами.
begin;
select set_config('request.jwt.claims', jsonb_build_object('sub',(select id from auth.users where lower(email) = any(array['gotnewmess@gmail.com','kovtunenko.yulchik@gmail.com']) order by created_at limit 1),'role','authenticated')::text,true);
set local role authenticated;
do $$
declare
  v_tx public.transactions;
  v_uid uuid := auth.uid();
  v_a integer := 2147000201;
  v_b integer := 2147000202;
  v_id bigint := 9000000201;
  v_parts jsonb;
  v_revision bigint;
begin
  if not public.is_family_member() then raise exception 'Test requires family auth context'; end if;
  insert into public.categories(id,user_id,name,is_income,sort_order) values
    (v_a,v_uid,'Synthetic receipt food',false,990001),
    (v_b,v_uid,'Synthetic receipt home',false,990002);
  insert into public.transactions(id,user_id,amount,type,category_id,description,source,date)
    values(v_id,v_uid,1000.01,'expense',v_a,'Synthetic split test','manual',current_date);
  select allocation_revision into v_revision from public.transactions where id=v_id;
  v_parts := jsonb_build_array(
    jsonb_build_object('category_id',v_a,'amount_cents',60001,'label','Synthetic food'),
    jsonb_build_object('category_id',v_b,'amount_cents',40000,'label','Synthetic home'));
  select * into v_tx from public.set_transaction_allocations(v_id,v_parts,v_revision,null);
  if v_tx.amount<>1000.01 or v_tx.expense_allocations<>v_parts or v_tx.allocation_revision<=v_revision then raise exception 'Split total/revision mismatch'; end if;
  if (select count(*) from public.transactions where id=v_id)<>1 then raise exception 'Split created extra cash transaction'; end if;
  begin
    perform public.set_transaction_allocations(v_id,v_parts,v_revision,null);
    raise exception 'Stale revision accepted';
  exception when serialization_failure then null;
  end;
  begin
    update public.categories set is_income=true where id=v_a;
    raise exception 'Allocated category converted to income';
  exception when invalid_parameter_value then null;
  end;
  begin
    delete from public.categories where id=v_b;
    raise exception 'Allocated category deleted';
  exception when invalid_parameter_value then null;
  end;
  begin
    update public.transactions set fixed_id=9000000201 where id=v_id;
    raise exception 'Split converted to recurring payment';
  exception when invalid_parameter_value then null;
  end;
  begin
    update public.transactions set credit_id=9000000201 where id=v_id;
    raise exception 'Split converted to credit repayment';
  exception when invalid_parameter_value then null;
  end;
  v_revision:=v_tx.allocation_revision;
  begin
    perform public.set_transaction_allocations(v_id,jsonb_set(v_parts,'{0,amount_cents}','60000'),v_revision,null);
    raise exception 'One-cent shortage accepted';
  exception when check_violation or invalid_parameter_value then null;
  end;
  begin
    update public.transactions set amount=999 where id=v_id;
    raise exception 'Amount mutation accepted';
  exception when check_violation or invalid_parameter_value then null;
  end;
  begin
    update public.transactions set category_id=v_b where id=v_id;
    raise exception 'Category mutation accepted';
  exception when check_violation or invalid_parameter_value then null;
  end;
  select * into v_tx from public.set_transaction_allocations(v_id,'[]'::jsonb,v_revision,v_b);
  if v_tx.expense_allocations<>'[]'::jsonb or v_tx.category_id<>v_b or v_tx.amount<>1000.01 then raise exception 'Merge failed'; end if;
  begin
    perform public.set_transaction_allocations(v_id,jsonb_build_array(jsonb_build_object('category_id',v_a,'amount_cents',100001)),v_tx.allocation_revision,null);
    raise exception 'Single-row split accepted';
  exception when check_violation or invalid_parameter_value then null;
  end;
  update public.transactions set type='income' where id=v_id;
  select allocation_revision into v_revision from public.transactions where id=v_id;
  begin
    perform public.set_transaction_allocations(v_id,v_parts,v_revision,null);
    raise exception 'Income split accepted';
  exception when check_violation or invalid_parameter_value then null;
  end;
end;
$$;
reset role;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}',true);
set local role authenticated;
do $$
begin
  begin
    perform public.set_transaction_allocations(9000000201,'[]'::jsonb,0,2147000201);
    raise exception 'Non-family RPC accepted';
  exception when insufficient_privilege then null;
  end;
  if exists(select 1 from public.transactions where id=9000000201) then raise exception 'RLS exposed receipt to non-family'; end if;
end;
$$;
reset role;
rollback;
