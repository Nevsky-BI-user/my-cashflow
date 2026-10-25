do $$
begin
  if (select count(*) from public.categories where budget_role is not null) <> 2 then
    raise exception 'Expected two unique system debt categories';
  end if;
  if exists (select 1 from public.categories where budget_role is not null
      and (is_income is not false or budget_role not in ('debt_card','debt_installment'))) then
    raise exception 'Invalid system category role';
  end if;
  if not exists (select 1 from pg_indexes where schemaname='public'
      and indexname='categories_budget_role_unique' and indexdef like 'CREATE UNIQUE INDEX%') then
    raise exception 'Missing debt role uniqueness';
  end if;
  if exists (select 1 from pg_class where oid in
      ('public.categories'::regclass,'public.category_groups'::regclass) and not relrowsecurity) then
    raise exception 'Family category RLS must remain enabled';
  end if;
end $$;
