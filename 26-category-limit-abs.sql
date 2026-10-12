-- 26: ліміт категорії в гривнях на період (власник 12.10.2026: «ліміти бюджету абсолютним або відсотковим значенням»).
-- limit_abs не null: категорія отримує рівно цю суму (у межах бюджету періоду, у порядку sort_order);
-- limit_abs null: категорія ділить залишок бюджету за вагою budget_limit, як і раніше.
alter table categories add column if not exists limit_abs numeric(12,2) null;
alter table categories drop constraint if exists categories_limit_abs_chk;
alter table categories add constraint categories_limit_abs_chk check (limit_abs is null or limit_abs >= 0);
