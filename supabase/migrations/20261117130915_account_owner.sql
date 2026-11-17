-- Власник рахунку окремим полем (власник 17.11.2026: «ім'я власника в одній комірці з назвою»): бот показує його колонкою «Хто».
-- Порожнє значення лишається порожнім, з назви не виводиться.
alter table public.accounts add column if not exists owner text;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'accounts_owner_len') then
    alter table public.accounts add constraint accounts_owner_len check (owner is null or char_length(owner) between 1 and 24);
  end if;
end $$;
