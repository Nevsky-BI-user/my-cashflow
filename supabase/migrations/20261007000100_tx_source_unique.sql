-- 04: унікальний source_id у transactions (Фаза 4.2)
-- Webhook-и Monobank і Telegram дедуплять по source_id перед insert, але між
-- перевіркою й вставкою є вікно (фото чека обробляється секунди). Унікальний
-- індекс закриває його: повторна вставка дає 23505, функції її ігнорують.
create unique index if not exists idx_tx_source_id_unique
  on transactions(source_id) where source_id is not null;
