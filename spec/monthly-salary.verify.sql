-- Лише синтетичні записи. Усі зміни відкочуються.
begin;
create temporary table monthly_salary_verification_result(result jsonb) on commit drop;
do $test$
declare
  valid_item jsonb := '{"key":"fixed:1:2199-01-15","date":"2199-01-15","name":"Обов’язковий платіж","amount_cents":40,"kind":"fixed"}';
  candidate jsonb;
  bad record;
  accepted integer := 0;
  rejected integer := 0;
begin
  delete from public.monthly_budgets where month_start = date '2199-01-01';
  insert into public.monthly_budgets(month_start,total_cents,allocations,mandatory_items)
    values ('2199-01-01',100,'{"1":100}',null);
  accepted := accepted + 1;
  update public.monthly_budgets set total_cents=0, allocations='{}', mandatory_items='[]'
    where month_start='2199-01-01';
  accepted := accepted + 1;
  update public.monthly_budgets set total_cents=100, allocations='{"1":60}',
    mandatory_items=jsonb_build_array(valid_item) where month_start='2199-01-01';
  accepted := accepted + 1;
  update public.monthly_budgets set total_cents=20, allocations='{"1":0}'
    where month_start='2199-01-01';
  accepted := accepted + 1;
  update public.monthly_budgets set total_cents=100, allocations='{"1":60}',
    mandatory_items=jsonb_build_array(valid_item || '{"estimated":true}')
    where month_start='2199-01-01';
  accepted := accepted + 1;
  update public.monthly_budgets set mandatory_items=jsonb_build_array(valid_item ||
    '{"kind":"installment","key":"installment:1:2199-01-15"}')
    where month_start='2199-01-01';
  accepted := accepted + 1;
  for candidate in select value from jsonb_array_elements(jsonb_build_array(
    'null'::jsonb, '{}'::jsonb, '1'::jsonb, '[null]'::jsonb, '[{}]'::jsonb,
    jsonb_build_array(valid_item - 'name'),
    jsonb_build_array(valid_item || '{"unexpected":1}'),
    jsonb_build_array(valid_item || '{"estimated":null}'),
    jsonb_build_array(valid_item || '{"estimated":"true"}'),
    jsonb_build_array(valid_item || '{"name":""}'),
    jsonb_build_array(valid_item || '{"name":"   "}'),
    jsonb_build_array(valid_item || jsonb_build_object('name',repeat('x',241))),
    jsonb_build_array(valid_item || '{"name":false}'),
    jsonb_build_array(valid_item || '{"amount_cents":null}'),
    jsonb_build_array(valid_item || '{"amount_cents":"40"}'),
    jsonb_build_array(valid_item || '{"amount_cents":-1}'),
    jsonb_build_array(valid_item || '{"amount_cents":0.5}'),
    jsonb_build_array(valid_item || '{"amount_cents":9007199254740992}'),
    jsonb_build_array(valid_item || '{"kind":"other"}'),
    jsonb_build_array(valid_item || '{"key":"installment:1:2199-01-15"}'),
    jsonb_build_array(valid_item || '{"key":"fixed::2199-01-15"}'),
    jsonb_build_array(valid_item || '{"key":"fixed:1:2199-01-16"}'),
    jsonb_build_array(valid_item || '{"date":"2199-01-32","key":"fixed:1:2199-01-32"}'),
    jsonb_build_array(valid_item || '{"date":"2199-02-01","key":"fixed:1:2199-02-01"}'),
    jsonb_build_array(valid_item || '{"date":"2198-01-15","key":"fixed:1:2198-01-15"}'),
    jsonb_build_array(valid_item || '{"date":"2199-1-15","key":"fixed:1:2199-1-15"}'),
    jsonb_build_array(valid_item,valid_item),
    jsonb_build_array(valid_item || '{"amount_cents":9007199254740991}',
      valid_item || '{"key":"fixed:2:2199-01-15","amount_cents":1}')
  )) loop
    begin
      update public.monthly_budgets set total_cents=100, allocations='{}',
        mandatory_items=candidate where month_start='2199-01-01';
      raise exception 'Invalid mandatory item accepted: %', candidate;
    exception when check_violation then rejected := rejected + 1;
    end;
  end loop;
  for bad in select * from (values (100::bigint,'{"1":61}'::jsonb),
    (20,'{"1":1}'),(0,'{"1":1}')) as v(gross,allocations) loop
    begin
      update public.monthly_budgets set total_cents=bad.gross, allocations=bad.allocations,
        mandatory_items=jsonb_build_array(valid_item) where month_start='2199-01-01';
      raise exception 'Overallocated salary budget accepted';
    exception when check_violation then rejected := rejected + 1;
    end;
  end loop;
  if public.monthly_budget_salary_valid('2199-01-01',9007199254740991,'{}',
    jsonb_build_array(valid_item || '{"amount_cents":9007199254740991}')) is not true then
    raise exception 'Safe reserve boundary rejected';
  end if;
  accepted := accepted + 1;
  if not (select relrowsecurity from pg_class where oid='public.monthly_budgets'::regclass)
     or (select count(*) from pg_policies where schemaname='public' and tablename='monthly_budgets') <> 1
     or not exists(select 1 from pg_policies where schemaname='public'
       and tablename='monthly_budgets' and policyname='family full' and cmd='ALL'
       and qual='is_family_member()' and with_check='is_family_member()')
     or has_table_privilege('authenticated','public.monthly_budgets','TRUNCATE')
     or has_table_privilege('anon','public.monthly_budgets','SELECT')
     or not has_table_privilege('authenticated','public.monthly_budgets','UPDATE')
     or not exists(select 1 from pg_publication_tables where pubname='supabase_realtime'
       and schemaname='public' and tablename='monthly_budgets') then
    raise exception 'Existing family access/realtime invariants changed';
  end if;
  if has_function_privilege('anon','public.monthly_budget_salary_valid(date,bigint,jsonb,jsonb)','EXECUTE')
     or not has_function_privilege('authenticated','public.monthly_budget_salary_valid(date,bigint,jsonb,jsonb)','EXECUTE')
     or not has_function_privilege('service_role','public.monthly_budget_salary_valid(date,bigint,jsonb,jsonb)','EXECUTE')
     or exists(select 1 from pg_proc where oid='public.monthly_budget_salary_valid(date,bigint,jsonb,jsonb)'::regprocedure
       and (prosecdef or provolatile <> 'i')) then
    raise exception 'Salary helper execution invariants failed';
  end if;
  if accepted <> 7 or rejected <> 31 then
    raise exception 'Unexpected verification coverage: % accepted, % rejected', accepted, rejected;
  end if;
  insert into monthly_salary_verification_result values (jsonb_build_object(
    'accepted',accepted,'rejected',rejected,'family_rls_grants_realtime',true,'helper_permissions',true));
end;
$test$;
select result from monthly_salary_verification_result;
rollback;
