-- 07: лічильник невдалих спроб автокатегоризації (6.4, рішення після критики)
-- categorize збільшує його при відмові (немає категорій потрібного типу, порожній опис,
-- погана відповідь моделі); categorize-batch бере лише рядки з attempts < 3.
alter table transactions
  add column if not exists categorize_attempts int not null default 0;
