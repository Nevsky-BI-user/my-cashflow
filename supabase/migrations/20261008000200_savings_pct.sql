-- 12: відсоток накопичень з доходу зберігається в salary_config (раніше жив лише в стані сторінки і скидався на 20 після перезавантаження)
alter table salary_config
  add column if not exists savings_pct int default 20;
