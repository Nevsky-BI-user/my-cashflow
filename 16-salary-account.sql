-- 16: на який рахунок заходить зарплата (власник: завжди на картку Ощадбанку)
alter table accounts add column if not exists is_salary boolean default false;
update accounts set is_salary = (bank = 'oschad');
