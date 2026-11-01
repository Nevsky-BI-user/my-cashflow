-- Розподіл чека не створює додаткового руху коштів.
alter table public.transactions add column if not exists expense_allocations jsonb not null default '[]'::jsonb;
alter table public.transactions add column if not exists allocation_revision bigint not null default 0;

create or replace function public.validate_expense_allocations() returns trigger
language plpgsql security invoker set search_path = public, pg_temp as $$
declare item jsonb; total numeric := 0; c public.categories; changed boolean;
begin
  if new.expense_allocations is null or jsonb_typeof(new.expense_allocations) <> 'array' then
    raise exception using errcode='22023', message='allocation_invalid';
  end if;
  if tg_op = 'UPDATE' then
    changed := (new.amount,new.type,new.transfer_id,new.fixed_id,new.credit_id,new.category_id,new.expense_allocations)
      is distinct from (old.amount,old.type,old.transfer_id,old.fixed_id,old.credit_id,old.category_id,old.expense_allocations);
    if jsonb_array_length(old.expense_allocations)>0 and jsonb_array_length(new.expense_allocations)>0
      and (new.amount,new.type,new.transfer_id,new.fixed_id,new.credit_id,new.category_id)
      is distinct from (old.amount,old.type,old.transfer_id,old.fixed_id,old.credit_id,old.category_id) then
      raise exception using errcode='22023', message='allocation_clear_first';
    end if;
    new.allocation_revision := old.allocation_revision + case when changed then 1 else 0 end;
  else
    new.allocation_revision := 0;
  end if;
  if jsonb_array_length(new.expense_allocations)=0 then
    if tg_op='UPDATE' and jsonb_array_length(old.expense_allocations)>0 then
      select * into c from public.categories where id=new.category_id for share;
      if not found or c.is_income is distinct from false or c.budget_role is not null or lower(trim(normalize(c.name,NFKC)))='заощадження' then
        raise exception using errcode='22023',message='allocation_category_invalid';
      end if;
      new.auto_categorized := false;
    end if;
    return new;
  end if;
  if jsonb_array_length(new.expense_allocations) not between 2 and 100 or new.type<>'expense'
    or new.transfer_id is not null or new.fixed_id is not null or new.credit_id is not null then
    raise exception using errcode='22023', message='allocation_ineligible';
  end if;
  -- Блокуємо зміну ролі категорії під час перевірки розподілу.
  if new.category_id is not null then
    select * into c from public.categories where id=new.category_id for share;
    if not found or c.is_income is distinct from false or c.budget_role is not null or lower(trim(normalize(c.name,NFKC)))='заощадження' then
      raise exception using errcode='22023', message='allocation_category_invalid';
    end if;
  end if;
  for item in select value from jsonb_array_elements(new.expense_allocations) loop
    if jsonb_typeof(item)<>'object' or jsonb_typeof(item->'category_id') is distinct from 'number'
      or jsonb_typeof(item->'amount_cents') is distinct from 'number' then
      raise exception using errcode='22023', message='allocation_invalid';
    end if;
    if (item->>'category_id')::numeric<>trunc((item->>'category_id')::numeric)
      or (item->>'category_id')::numeric not between 1 and 9007199254740991
      or (item->>'amount_cents')::numeric<>trunc((item->>'amount_cents')::numeric)
      or (item->>'amount_cents')::numeric not between 1 and 9007199254740991
      or (item ? 'label' and (jsonb_typeof(item->'label')<>'string' or char_length(item->>'label')>160)) then
      raise exception using errcode='22023', message='allocation_invalid';
    end if;
    select * into c from public.categories where id=(item->>'category_id')::bigint for share;
    if not found or c.is_income is distinct from false or c.budget_role is not null or lower(trim(normalize(c.name,NFKC)))='заощадження' then
      raise exception using errcode='22023', message='allocation_category_invalid';
    end if;
    total := total+(item->>'amount_cents')::numeric;
  end loop;
  if total>9007199254740991 or total<>new.amount*100 then
    raise exception using errcode='22023', message='allocation_total_mismatch';
  end if;
  new.auto_categorized := false;
  return new;
end $$;
drop trigger if exists validate_expense_allocations on public.transactions;
create trigger validate_expense_allocations before insert or update on public.transactions
for each row execute function public.validate_expense_allocations();

create or replace function public.protect_allocated_category() returns trigger
language plpgsql security invoker set search_path = public, pg_temp as $$
begin
  if tg_op='UPDATE' then
    if new.id=old.id and new.is_income is false and new.budget_role is null and lower(trim(normalize(new.name,NFKC)))<>'заощадження' then return new; end if;
  end if;
  if exists(select 1 from public.transactions t where jsonb_array_length(t.expense_allocations)>0 and
    (t.category_id=old.id or exists(select 1 from jsonb_array_elements(t.expense_allocations) a where (a->>'category_id')::bigint=old.id))) then
    raise exception using errcode='22023', message='allocation_category_in_use';
  end if;
  if tg_op='DELETE' then return old; end if;
  return new;
end $$;
drop trigger if exists protect_allocated_category on public.categories;
create trigger protect_allocated_category before update or delete on public.categories
for each row execute function public.protect_allocated_category();

create or replace function public.set_transaction_allocations(p_transaction_id bigint,p_allocations jsonb,p_expected_revision bigint,p_category_id bigint default null)
returns public.transactions language plpgsql security invoker set search_path = public, pg_temp as $$
declare tx public.transactions; c public.categories;
begin
  if not public.is_family_member() then raise exception using errcode='42501',message='allocation_forbidden'; end if;
  select * into tx from public.transactions where id=p_transaction_id for update;
  if not found then raise exception using errcode='P0002',message='allocation_not_found'; end if;
  if p_expected_revision is null or tx.allocation_revision<>p_expected_revision then
    raise exception using errcode='40001',message='allocation_revision_conflict';
  end if;
  if p_allocations='[]'::jsonb then
    select * into c from public.categories where id=p_category_id for share;
    if not found or c.is_income is distinct from false or c.budget_role is not null or lower(trim(normalize(c.name,NFKC)))='заощадження' then
      raise exception using errcode='22023',message='allocation_category_invalid';
    end if;
  end if;
  update public.transactions set expense_allocations=p_allocations, category_id=coalesce(p_category_id,category_id),auto_categorized=false
    where id=p_transaction_id returning * into tx;
  return tx;
end $$;
revoke all on function public.set_transaction_allocations(bigint,jsonb,bigint,bigint) from public, anon;
grant execute on function public.set_transaction_allocations(bigint,jsonb,bigint,bigint) to authenticated;
