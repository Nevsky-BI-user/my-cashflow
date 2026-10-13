-- 30: ручний бюджет періоду (власник 13.10.2026: «має бути можливість встановлювати суму, яка розподіляється»).
-- budget_manual null: авто (15 000 ₴, якщо з виплати лишається більше, до 20 000 ₴); не null: бюджет кожного періоду рівно ця сума
-- (гривні), доки в налаштуваннях не повернуть «Авто». Рушій бере її в резерв виплати до погашення кредиток.
alter table salary_config add column if not exists budget_manual numeric(12,2) null;
alter table salary_config drop constraint if exists salary_config_budget_manual_chk;
alter table salary_config add constraint salary_config_budget_manual_chk check (budget_manual is null or budget_manual >= 0);
