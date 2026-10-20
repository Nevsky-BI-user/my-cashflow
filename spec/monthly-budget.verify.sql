-- Запускати після міграції. Усі тестові записи відкочуються.
begin;
create temporary table monthly_budget_test_result (result jsonb) on commit drop;
do $test$
declare
  item record;
  rejected integer := 0;
  accepted integer := 0;
  hidden_count integer;
  caller_role text := current_user;
  anon_denied boolean := false;
  member_write_denied boolean := false;
  anon_write_denied boolean := false;
  member_uid uuid;
  member_verified boolean := false;
begin
  -- Лише синтетичний місяць; наявний запис тимчасово прибираємо в транзакції.
  delete from public.monthly_budgets where month_start = date '2199-01-01';
  insert into public.monthly_budgets(month_start,total_cents,allocations)
    values ('2199-01-01',0,'{}');
  accepted := accepted + 1;
  update public.monthly_budgets set total_cents=100, allocations='{"1":25,"2":50}'
    where month_start='2199-01-01';
  accepted := accepted + 1;
  for item in select * from (values
    ('null'::jsonb,100::bigint), ('[]',100), ('1',100),
    ('{"1":null}',100), ('{"1":"1"}',100), ('{"1":true}',100),
    ('{"1":{}}',100), ('{"1":[]}',100),
    ('{"1":-1}',100), ('{"1":0.5}',100),
    ('{"1":9007199254740992}',9007199254740991),
    ('{"1":60,"2":41}',100), ('{"bad":1}',100), ('{"0":1}',100),
    ('{}',-1), ('{}',9007199254740992)
  ) as bad(allocations,total_cents) loop
    begin
      update public.monthly_budgets b set allocations=item.allocations,
        total_cents=item.total_cents where b.month_start='2199-01-01';
      raise exception 'Invalid allocation accepted: %', item.allocations;
    exception when check_violation then rejected := rejected + 1;
    end;
  end loop;
  for item in select unnest(array[date '2199-01-02', 'infinity'::date, '-infinity'::date]) as bad_date loop
    begin
      update public.monthly_budgets set month_start=item.bad_date where month_start='2199-01-01';
      raise exception 'Invalid date accepted';
    exception when check_violation then rejected := rejected + 1;
    end;
  end loop;
  if public.monthly_budget_allocations_valid('{"1":9007199254740991}',9007199254740991) is not true then
    raise exception 'Safe integer boundary rejected';
  end if;
  accepted := accepted + 1;
  -- Знаходимо дозволеного користувача без виведення його даних.
  for item in select id from auth.users loop
    perform set_config('request.jwt.claim.sub',item.id::text,true);
    perform set_config('request.jwt.claims',jsonb_build_object('sub',item.id,'role','authenticated')::text,true);
    if public.is_family_member() then
      member_uid := item.id;
      exit;
    end if;
  end loop;
  if member_uid is null then raise exception 'No family member available for RLS verification'; end if;
  execute 'set local role authenticated';
  update public.monthly_budgets set total_cents=100,allocations='{"1":75}'
    where month_start='2199-01-01';
  if not found then raise exception 'Family member cannot update monthly budget'; end if;
  select exists(select 1 from public.monthly_budgets
    where month_start='2199-01-01' and allocations='{"1":75}'::jsonb)
    into member_verified;
  if not member_verified then raise exception 'Family member cannot read saved monthly budget'; end if;
  execute format('set local role %I',caller_role);
  -- Порожній JWT не належить до сімейного whitelist.
  perform set_config('request.jwt.claims','{}',true);
  perform set_config('request.jwt.claim.sub','',true);
  execute 'set local role authenticated';
  select count(*) into hidden_count from public.monthly_budgets;
  if hidden_count <> 0 then raise exception 'Nonmember can read monthly budgets'; end if;
  begin
    insert into public.monthly_budgets(month_start,total_cents) values ('2199-02-01',0);
  exception when insufficient_privilege then member_write_denied := true;
  end;
  execute format('set local role %I',caller_role);
  if not member_write_denied then raise exception 'Nonmember write accepted'; end if;
  execute 'set local role anon';
  begin
    select count(*) into hidden_count from public.monthly_budgets;
    if hidden_count <> 0 then raise exception 'Anon can read monthly budgets'; end if;
  exception when insufficient_privilege then anon_denied := true;
  end;
  begin
    insert into public.monthly_budgets(month_start,total_cents) values ('2199-03-01',0);
  exception when insufficient_privilege then anon_write_denied := true;
  end;
  execute format('set local role %I',caller_role);
  if not anon_write_denied then raise exception 'Anon write accepted'; end if;
  insert into monthly_budget_test_result values(jsonb_build_object(
    'valid_cases',accepted,'rejected_invalid_cases',rejected,'member_read_write_verified',member_verified,
    'nonmember_select_rows',0,'nonmember_write_denied',member_write_denied,
    'anon_select_permission_denied',anon_denied,'anon_write_denied',anon_write_denied
  ));
end;
$test$;
-- NOTICE залишається видимим навіть коли CLI повертає лише останній результат.
do $report$
declare
  report jsonb;
begin
  select r.result || jsonb_build_object(
    'rls_enabled',(select relrowsecurity from pg_class where oid='public.monthly_budgets'::regclass),
    'family_policy',(select jsonb_build_object('using',qual,'check',with_check,'command',cmd)
      from pg_policies where schemaname='public' and tablename='monthly_budgets' and policyname='family full'),
    'authenticated_truncate',has_table_privilege('authenticated','public.monthly_budgets','TRUNCATE'),
    'realtime',(select exists(select 1 from pg_publication_tables where pubname='supabase_realtime'
      and schemaname='public' and tablename='monthly_budgets'))
  ) into report from monthly_budget_test_result r;
  raise notice 'MONTHLY_BUDGET_VERIFICATION %', report;
end;
$report$;
select * from monthly_budget_test_result;
rollback;
