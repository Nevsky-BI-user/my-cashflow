-- 18: ознака «можна оплатити кредитною карткою» (DESIGN.md, правило «білої» і кредитної картки).
-- Без ознаки платіж «білий»: лише з власних коштів дебетової картки.
alter table fixed_payments add column if not exists credit_ok boolean default false;
alter table credits add column if not exists credit_ok boolean default false;
-- Розстрочки ПриватБанку списуються з кредитної картки
update credits set credit_ok = true where lower(coalesce(source,'')) like '%privat%';
