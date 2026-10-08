-- 21: мінімальні витрати з рахунку за календарний місяць (правило власника 08.10.2026).
-- Якщо за місяць M витрати (type = 'expense') з рахунку менші за min_spend, банк 1-го числа M+1
-- списує min_spend_fee. Застосунок, бот і scripts/budget_pool.py показують подію комісії,
-- доки поріг поточного місяця не досягнуто. null: правила немає.
alter table accounts
  add column if not exists min_spend numeric(12,2),
  add column if not exists min_spend_fee numeric(12,2);

-- Ощадбанк: не менше 15 000 на місяць, інакше комісія 400
update accounts set min_spend = 15000, min_spend_fee = 400
  where bank = 'oschad' and min_spend is null;
