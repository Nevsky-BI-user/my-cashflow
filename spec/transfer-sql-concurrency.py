"""Exercise RPC locking in a private disposable schema, never in the family ledger."""
import concurrent.futures
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
CLI = Path.home() / 'AppData/Local/npm-cache/_npx/0e23c24576954b26/node_modules/@supabase/cli-windows-x64/bin/supabase.exe'
SCHEMA = 'cashflow_verify_' + uuid.uuid4().hex[:12]
assert re.fullmatch(r'cashflow_verify_[a-f0-9]{12}', SCHEMA)
OUT = ROOT / 'spec/.out' / SCHEMA
OUT.mkdir(parents=True, exist_ok=True)
raw = (ROOT / '48-account-transfers-salary.sql').read_text(encoding='utf-8-sig')
mapping = {
    'public.account_transfers': f'{SCHEMA}.test_transfers',
    'public.salary_payouts': f'{SCHEMA}.test_payouts',
    'public.transactions': f'{SCHEMA}.test_transactions',
    'public.accounts': f'{SCHEMA}.test_accounts',
    'public.profiles': f'{SCHEMA}.test_users',
    'auth.users': f'{SCHEMA}.test_users',
    'public.guard_transfer_leg': f'{SCHEMA}.guard_transfer_leg',
    'public.record_account_transfer': f'{SCHEMA}.record_account_transfer',
    'public.record_salary_payout': f'{SCHEMA}.record_salary_payout',
}


def rewrite(sql):
    for a, b in mapping.items():
        sql = sql.replace(a, b)
    return sql


def run(name, sql):
    path = OUT / (name + '.sql')
    path.write_text(sql, encoding='utf8')
    return subprocess.run([str(CLI), 'db', 'query', '--linked', '--project-ref', 'lisedsqwdzshsxydghag',
                           '--file', str(path), '--output', 'json'], cwd=ROOT, text=True,
                          encoding='utf8', capture_output=True, timeout=90)


def must(name, sql):
    p = run(name, sql)
    if p.returncode:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout).get('rows', [])


setup = f"""begin;
create schema {SCHEMA};
revoke all on schema {SCHEMA} from public;
create table {SCHEMA}.test_users(id uuid primary key,email text);
create table {SCHEMA}.test_accounts(like public.accounts including all);
create table {SCHEMA}.test_transactions(like public.transactions including all);
create sequence {SCHEMA}.test_tx_seq;
alter table {SCHEMA}.test_transactions alter column id set default nextval('{SCHEMA}.test_tx_seq');
alter table {SCHEMA}.test_transactions add column if not exists payment_due_date date;
"""
for table in ('account_transfers', 'salary_payouts'):
    a = raw.index('create table if not exists public.' + table + ' (')
    b = raw.index('\n);', a) + 3
    setup += rewrite(raw[a:b]) + '\n'
setup += f"""
alter table {SCHEMA}.test_transactions add column if not exists transfer_id uuid references {SCHEMA}.test_transfers(id);
create unique index test_transfer_legs on {SCHEMA}.test_transactions(transfer_id,type) where transfer_id is not null;
"""
for name in ('guard_transfer_leg', 'record_account_transfer', 'record_salary_payout'):
    a = raw.index('create or replace function public.' + name + '(')
    b = raw.index('end $$;', a) + len('end $$;')
    setup += rewrite(raw[a:b]) + '\n'
setup += f"""
create trigger guard_transfer_leg before insert or update or delete on {SCHEMA}.test_transactions
 for each row execute function {SCHEMA}.guard_transfer_leg();
insert into {SCHEMA}.test_users values
 ('00000000-0000-0000-0000-000000000001','gotnewmess@gmail.com'),
 ('00000000-0000-0000-0000-000000000002','kovtunenko.yulchik@gmail.com');
insert into {SCHEMA}.test_accounts(id,user_id,name,kind,balance,debt,balance_updated_at,active,is_salary) values
 (-1,'00000000-0000-0000-0000-000000000001','Source','debit',10000,0,now()-interval '1 day',true,true),
 (-2,'00000000-0000-0000-0000-000000000001','Target','credit',0,5000,now()-interval '1 day',true,false);
commit;
"""
claims = "select set_config('request.jwt.claims','{\"role\":\"service_role\"}',true);"
day = "(now() at time zone 'Europe/Kyiv')::date"
actor = '00000000-0000-0000-0000-000000000001'


def transfer(request, amount):
    return f"begin;{claims}select {SCHEMA}.record_account_transfer('{request}',-1,-2,{amount},{day},null,null,'{actor}');select pg_sleep(1);commit;"


def counts():
    return must('counts', f"select (select count(*) from {SCHEMA}.test_transfers) as transfers,(select count(*) from {SCHEMA}.test_transactions) as legs,(select count(*) from {SCHEMA}.test_payouts) as payouts;")[0]


def reset():
    must('reset', f'truncate {SCHEMA}.test_payouts,{SCHEMA}.test_transfers,{SCHEMA}.test_transactions;')


try:
    must('setup', setup)
    request = str(uuid.uuid4())
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda i: run('same_' + str(i), transfer(request, 3000)), range(2)))
    assert all(p.returncode == 0 for p in results), [p.stderr for p in results]
    assert counts() == {'transfers': 1, 'legs': 2, 'payouts': 0}
    reset()
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda i: run('funds_' + str(i), transfer(str(uuid.uuid4()), 7000)), range(2)))
    assert sum(p.returncode == 0 for p in results) == 1, [p.stderr for p in results]
    assert any('Insufficient own funds' in p.stderr for p in results)
    assert counts() == {'transfers': 1, 'legs': 2, 'payouts': 0}
    reset()
    def salary(i):
        a = f'00000000-0000-0000-0000-00000000000{i+1}'
        return run('salary_' + str(i), f"begin;{claims}select {SCHEMA}.record_salary_payout(-1,{day},'salary',5000,'{a}');select pg_sleep(1);commit;")
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(salary, range(2)))
    assert all(p.returncode == 0 for p in results), [p.stderr for p in results]
    assert counts() == {'transfers': 0, 'legs': 1, 'payouts': 1}
    print('SQL concurrency PASS: same request, competing own funds, shared salary occurrence')
finally:
    p = run('cleanup', f'drop schema if exists {SCHEMA} cascade;')
    if p.returncode:
        raise RuntimeError('Disposable schema cleanup failed: ' + p.stderr)
    print('Disposable SQL schema removed')
