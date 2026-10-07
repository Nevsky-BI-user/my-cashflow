-- 10: зарплата за робочими днями. Ставка на місяць і межа періодів;
-- старі advance_amount / salary_amount лишаються як запасний варіант без ставки.
alter table salary_config
  add column if not exists rate numeric(12,2),
  add column if not exists split_day int default 15;

-- Ставка = сума двох виплат, як було; аванс за правилом власника 21-го (було 20-го)
update salary_config
set rate = coalesce(rate, advance_amount + salary_amount),
    advance_day = case when advance_day = 20 then 21 else advance_day end;
