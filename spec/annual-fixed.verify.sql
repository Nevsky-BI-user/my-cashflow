-- Синтетичні рядки лише в тимчасовій таблиці; фінансові дані не змінюються.
begin;
create temporary table annual_fixed_check (like public.fixed_payments including constraints including defaults) on commit drop;
insert into annual_fixed_check (id,name,amount,day_of_month,type,period,weekday,month_of_year)
values (-1,'test month',1,15,'payment','month',null,null),
       (-2,'test week',1,1,'payment','week',1,null),
       (-3,'test year',1,29,'payment','year',null,2);
do $$
begin
  begin
    insert into annual_fixed_check (id,name,amount,day_of_month,type,period,month_of_year)
    values (-4,'invalid annual month',1,1,'payment','year',null);
    raise exception 'year/null accepted';
  exception when check_violation then null;
  end;
  begin
    insert into annual_fixed_check (id,name,amount,day_of_month,type,period,month_of_year)
    values (-5,'invalid annual month',1,1,'payment','year',13);
    raise exception 'year/13 accepted';
  exception when check_violation then null;
  end;
  begin
    insert into annual_fixed_check (id,name,amount,day_of_month,type,period,weekday)
    values (-6,'invalid weekday',1,1,'payment','week',null);
    raise exception 'week/null accepted';
  exception when check_violation then null;
  end;
end $$;
select 'annual and weekly constraints PASS' as verification;
rollback;
