"""Build a rollback-only SQL check using temporary ledger copies and real RPC bodies."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
annual = (ROOT / '47-annual-fixed-due-dates.sql').read_text(encoding='utf-8-sig')
migration = (ROOT / '48-account-transfers-salary.sql').read_text(encoding='utf-8-sig')
mapping = {
    'public.account_transfers': 'pg_temp.test_transfers',
    'public.salary_payouts': 'pg_temp.test_payouts',
    'public.transactions': 'pg_temp.test_transactions',
    'public.accounts': 'pg_temp.test_accounts',
    'auth.users': 'pg_temp.test_users',
    'public.guard_salary_identity': 'pg_temp.guard_salary_identity',
    'public.guard_transfer_leg': 'pg_temp.guard_transfer_leg',
    'public.record_account_transfer': 'pg_temp.record_account_transfer',
    'public.record_salary_payout': 'pg_temp.record_salary_payout',
}
functions = []
for name in ('guard_transfer_leg', 'guard_salary_identity', 'record_account_transfer', 'record_salary_payout'):
    a = migration.index('create or replace function public.' + name + '(')
    b = migration.index('end $$;', a) + len('end $$;')
    sql = migration[a:b]
    for original, replacement in mapping.items():
        sql = sql.replace(original, replacement)
    functions.append(sql)

setup = """
create temporary table test_accounts (like public.accounts including all) on commit drop;
create temporary table test_transactions (like public.transactions including all) on commit drop;
create temporary table test_transfers (like public.account_transfers including all) on commit drop;
create temporary table test_payouts (like public.salary_payouts including all) on commit drop;
create temporary table test_users(id uuid primary key,email text) on commit drop;
create temporary sequence test_tx_seq;
alter table test_transactions alter column id set default nextval('pg_temp.test_tx_seq');
insert into test_users values
 ('00000000-0000-0000-0000-000000000001','gotnewmess@gmail.com'),
 ('00000000-0000-0000-0000-000000000002','kovtunenko.yulchik@gmail.com');
insert into test_accounts(id,user_id,name,kind,balance,debt,balance_updated_at,active,is_salary,mono_account_id) values
 (-1,'00000000-0000-0000-0000-000000000001','Source','debit',10000,0,now()-interval '1 day',true,true,null),
 (-2,'00000000-0000-0000-0000-000000000001','Target','credit',0,5000,now()-interval '1 day',true,false,null),
 (-3,'00000000-0000-0000-0000-000000000001','Credit source','credit',2000,500,now()-interval '1 day',true,false,null),
 (-4,'00000000-0000-0000-0000-000000000001','Mono target','credit',0,2000,now()-interval '1 day',true,false,'mono-test'),
 (-5,'00000000-0000-0000-0000-000000000001','Mono salary','debit',0,0,now()-interval '1 day',true,true,'mono-salary-test');
"""
tests = """
create trigger guard_salary_identity before update on test_transactions for each row execute function pg_temp.guard_salary_identity();
create trigger guard_transfer_leg before insert or update or delete on test_transactions for each row execute function pg_temp.guard_transfer_leg();
create or replace function pg_temp.reject_second_leg() returns trigger language plpgsql as $$
begin
 if new.transfer_id='10000000-0000-0000-0000-000000000099' and new.type='income' then raise exception 'second leg test failure';end if;
 return new;
end $$;
create trigger reject_second_leg before insert on test_transactions for each row execute function pg_temp.reject_second_leg();
select set_config('request.jwt.claims','{"role":"service_role"}',true);
do $$
declare actor uuid:='00000000-0000-0000-0000-000000000001'; other_actor uuid:='00000000-0000-0000-0000-000000000002';
 day date:=(now() at time zone 'Europe/Kyiv')::date; rid uuid:='10000000-0000-0000-0000-000000000001'; tid bigint; second_tid bigint; bank_tid bigint; col text; n bigint;
begin
 perform pg_temp.record_account_transfer(rid,-1,-2,3000,day,null,null,actor);
 if (select count(*) from test_transactions where transfer_id=rid)<>2 then raise exception 'paired legs missing';end if;
 if (select sum(case when type='income' then amount else -amount end) from test_transactions where transfer_id=rid)<>0 then raise exception 'transfer not conserved';end if;
 perform pg_temp.record_account_transfer(rid,-1,-2,3000,day,null,null,actor);
 if (select count(*) from test_transfers)<>1 then raise exception 'retry duplicated transfer';end if;
 begin
  perform pg_temp.record_account_transfer(rid,-1,-2,3001,day,null,null,actor);
  raise exception 'conflicting retry accepted';
 exception when raise_exception then if SQLERRM='conflicting retry accepted' then raise;end if;end;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000002',-1,-2,9000,day,null,null,actor);
  raise exception 'overspend accepted';
 exception when raise_exception then if SQLERRM='overspend accepted' then raise;end if;end;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000003',-3,-2,3000,day,null,null,actor);
  raise exception 'credit limit treated as own funds';
 exception when raise_exception then if SQLERRM='credit limit treated as own funds' then raise;end if;end;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000098',-1,-2,'NaN'::numeric,day,null,null,actor);
  raise exception 'NaN transfer accepted';
 exception when raise_exception then if SQLERRM='NaN transfer accepted' then raise;end if;end;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000099',-1,-2,100,day,null,null,actor);
  raise exception 'failing second leg accepted';
 exception when raise_exception then if SQLERRM<>'second leg test failure' then raise;end if;end;
 if exists(select 1 from test_transfers where id='10000000-0000-0000-0000-000000000099') or exists(select 1 from test_transactions where transfer_id='10000000-0000-0000-0000-000000000099') then raise exception 'second leg failure leaked partial write';end if;
 update test_accounts set balance_updated_at=null where id=-2;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000097',-1,-2,100,day,null,null,actor);
  raise exception 'untimestamped manual target accepted';
 exception when raise_exception then if SQLERRM='untimestamped manual target accepted' then raise;end if;end;
 update test_accounts set balance_updated_at=now()-interval '1 day' where id=-2;
 begin
  update test_transactions set amount=1 where transfer_id=rid;
  raise exception 'direct linked edit accepted';
 exception when raise_exception then if SQLERRM='direct linked edit accepted' then raise;end if;end;
 begin
  delete from test_transactions where transfer_id=rid;
  raise exception 'direct linked delete accepted';
 exception when raise_exception then if SQLERRM='direct linked delete accepted' then raise;end if;end;
 insert into test_transactions(user_id,account_id,type,amount,date,source) values(actor,-4,'income',1000,day,'mono') returning id into bank_tid;
 perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000004',-1,-4,1000,day,null,bank_tid,actor);
 if (select count(*) from test_transactions where account_id=-4)<>1 then raise exception 'Mono leg duplicated';end if;
 insert into test_transactions(user_id,account_id,type,amount,date,source) values(actor,null,'income',1000,day,'mono') returning id into bank_tid;
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000096',-1,-4,1000,day,null,bank_tid,actor);
  raise exception 'unassigned imported leg accepted';
 exception when raise_exception then if SQLERRM='unassigned imported leg accepted' then raise;end if;end;
 update test_accounts set is_salary=true where id=-4;
 insert into test_transactions(user_id,account_id,type,amount,date,source) values(actor,-4,'income',500,day,'mono') returning id into bank_tid;
 perform pg_temp.record_salary_payout(-4,day,'salary',500,actor,bank_tid);
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000095',-1,-4,500,day,null,bank_tid,actor);
  raise exception 'salary reused as transfer';
 exception when raise_exception then if SQLERRM='salary reused as transfer' then raise;end if;end;
 perform set_config('request.jwt.claims','{"role":"anon"}',true);
 begin
  perform pg_temp.record_account_transfer('10000000-0000-0000-0000-000000000005',-1,-2,1,day,null,null,actor);
  raise exception 'anonymous transfer accepted';
 exception when raise_exception then if SQLERRM='anonymous transfer accepted' then raise;end if;end;
 perform set_config('request.jwt.claims','{"role":"service_role"}',true);
 tid:=pg_temp.record_salary_payout(-1,day,'salary',5000,actor);
 second_tid:=pg_temp.record_salary_payout(-1,day,'salary',5000,other_actor);
 if tid<>second_tid or (select count(*) from test_payouts where account_id=-1)<>1 then raise exception 'shared salary duplicated';end if;
 foreach col in array array['account_id','type','amount','date','transfer_id','source','source_id'] loop
  begin
   execute format('update test_transactions set %I=%s where id=$1',col,
    case col when 'account_id' then '-2' when 'type' then quote_literal('expense') when 'amount' then '1' when 'date' then 'current_date-1' when 'transfer_id' then quote_literal('10000000-0000-0000-0000-000000000009')||'::uuid' when 'source' then quote_literal('mono') else quote_literal('different') end) using tid;
   raise exception 'salary identity edit accepted';
  exception when raise_exception then if SQLERRM='salary identity edit accepted' then raise;end if;end;
 end loop;
 update test_transactions set description='Editable salary description' where id=tid;
 begin
  perform pg_temp.record_salary_payout(-1,day,'advance',5000,actor,tid);
  raise exception 'claimed salary income accepted';
 exception when raise_exception then if SQLERRM='claimed salary income accepted' then raise;end if;end;
 second_tid:=pg_temp.record_salary_payout(-1,day,'advance',5000,actor);
 if tid=second_tid then raise exception 'same day advance reused salary';end if;

 begin
  perform pg_temp.record_salary_payout(-5,day,'salary',5000,actor);
  raise exception 'synthetic Mono salary accepted';
 exception when raise_exception then if SQLERRM='synthetic Mono salary accepted' then raise;end if;end;
 begin
  perform pg_temp.record_salary_payout(-1,day+1,'advance',5000,actor);
  raise exception 'future salary accepted';
 exception when raise_exception then if SQLERRM='future salary accepted' then raise;end if;end;
 if (select count(*) from test_transfers)<>2 then raise exception 'failed request left a transfer';end if;
end $$;
select 'isolated transfer and salary RPC checks PASS' as verification;
rollback;
"""
out = ROOT / 'spec/.out/transfer-isolated.sql'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('begin;\n' + annual + '\n' + migration + '\n' + setup + '\n'.join(functions) + '\n' + tests, encoding='utf8')
print(out)
