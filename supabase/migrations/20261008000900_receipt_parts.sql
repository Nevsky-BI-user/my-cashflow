-- Довгі чеки з кількох фото: шляхи всіх частин у bucket receipts.
-- receipt_url лишається першою частиною, receipt_parts заповнюється лише коли частин більше однієї.
alter table transactions add column if not exists receipt_parts text[];
