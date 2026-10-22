"""Generate rollback-only checks against temporary tables and real migration bodies."""
from pathlib import Path
import runpy
R=Path(__file__).resolve().parents[1]
base=runpy.run_path(str(R/'spec/transfer-sql-isolated.py'))
s=(R/'49-general-transfers-account-order.sql').read_text(encoding='utf8')
mapping={**base['mapping'],'public.reorder_accounts':'pg_temp.reorder_accounts','public.is_family_member':'pg_temp.is_family_member'}
funcs=[f for f in base['functions'] if 'function pg_temp.record_account_transfer(' not in f]
for name in ('record_account_transfer','reorder_accounts'):
 a=s.index('create or replace function public.'+name+'(');b=s.index('end $$;',a)+len('end $$;');f=s[a:b]
 for old,new in mapping.items():f=f.replace(old,new)
 funcs.append(f)
tests='''
create function pg_temp.is_family_member() returns boolean language sql as $$select exists(select 1 from pg_temp.test_users where id=auth.uid())$$;
create trigger guard_transfer_leg before insert or update or delete on test_transactions for each row execute function pg_temp.guard_transfer_leg();
insert into test_accounts(id,user_id,name,kind,balance,debt,balance_updated_at,active) values
 (-6,'00000000-0000-0000-0000-000000000001','Debit target','debit',100,0,now()-interval '1 day',true),
 (-7,'00000000-0000-0000-0000-000000000001','Cash target','cash',100,0,now()-interval '1 day',true),
 (-8,'00000000-0000-0000-0000-000000000001','Inactive','debit',100,0,now()-interval '1 day',false);
select set_config('request.jwt.claims','{"role":"authenticated","sub":"00000000-0000-0000-0000-000000000001"}',true);
do $$
declare day date:=(now() at time zone 'Europe/Kyiv')::date; bank_id bigint; count_before integer; got bigint[]; bad bigint[];
begin
 perform pg_temp.record_account_transfer('20000000-0000-0000-0000-000000000001',-1,-6,500,day);
 perform pg_temp.record_account_transfer('20000000-0000-0000-0000-000000000002',-3,-6,500,day);
 perform pg_temp.record_account_transfer('20000000-0000-0000-0000-000000000003',-1,-7,100,day);
 if (select count(*) from test_transactions)<>6 then raise exception 'general paired legs failed';end if;
 if (select sum(case when type='income' then amount else -amount end) from test_transactions)<>0 then raise exception 'net conservation failed';end if;
 perform pg_temp.record_account_transfer('20000000-0000-0000-0000-000000000001',-1,-6,500,day);
 if (select count(*) from test_transactions)<>6 then raise exception 'retry duplicated';end if;
 insert into test_transactions(user_id,account_id,type,amount,date,source,source_id) values('00000000-0000-0000-0000-000000000001',-5,'income',200,day,'mono','test-general-import') returning id into bank_id;
 perform pg_temp.record_account_transfer('20000000-0000-0000-0000-000000000004',-1,-5,200,day,null,bank_id);
 if (select count(*) from test_transactions)<>8 then raise exception 'bank import duplicated';end if;
 perform pg_temp.reorder_accounts(array[-7,-1,-3,-2,-4,-5,-6]::bigint[]);
 select array_agg(id order by sort_order) into got from test_accounts where active;
 if got is distinct from array[-7,-1,-3,-2,-4,-5,-6]::bigint[] then raise exception 'order not saved';end if;
 foreach bad slice 1 in array array[[-7,-1,-3,-2,-4,-5,-5],[-7,-1,-3,-2,-4,-5,-8],[-7,-1,-3,-2,-4,-5,null]]::bigint[][] loop
  begin
   perform pg_temp.reorder_accounts(bad);raise exception 'invalid order accepted';
  exception when raise_exception then if SQLERRM='invalid order accepted' then raise;end if;end;
 end loop;
 begin perform pg_temp.reorder_accounts(array[-1]::bigint[]);raise exception 'missing accepted';exception when raise_exception then if SQLERRM='missing accepted' then raise;end if;end;
 begin perform pg_temp.reorder_accounts(null);raise exception 'null accepted';exception when raise_exception then if SQLERRM='null accepted' then raise;end if;end;
 if (select array_agg(id::bigint order by sort_order) from test_accounts where active) is distinct from got then raise exception 'failed reorder changed rows';end if;
 perform set_config('request.jwt.claims','{"role":"anon"}',true);
 begin perform pg_temp.reorder_accounts(got);raise exception 'anon accepted';exception when raise_exception then if SQLERRM='anon accepted' then raise;end if;end;
 perform set_config('request.jwt.claims','{"role":"authenticated","sub":"00000000-0000-0000-0000-000000000099"}',true);
 begin perform pg_temp.reorder_accounts(got);raise exception 'outsider accepted';exception when raise_exception then if SQLERRM='outsider accepted' then raise;end if;end;
end $$;
grant select,update on test_accounts to authenticated;
grant select on test_users to authenticated;
do $$begin execute format('grant usage on schema %I to authenticated',pg_my_temp_schema()::regnamespace);end $$;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"00000000-0000-0000-0000-000000000001"}',true);
set local role authenticated;
select pg_temp.reorder_accounts(array[-6,-5,-4,-3,-2,-1,-7]::bigint[]);
reset role;
do $$begin
 if (select array_agg(id order by sort_order) from test_accounts where active) is distinct from array[-6,-5,-4,-3,-2,-1,-7] then raise exception 'authenticated invoker failed';end if;
end $$;
select 'general transfers and account order PASS' as verification;
rollback;
'''
out=R/'spec/.out/general-transfers-order-isolated.sql'
out.write_text('begin;\n'+base['setup']+'\n'+'\n'.join(funcs)+'\n'+tests,encoding='utf8')
print(out)
