-- Ідентифікатор картки зберігається текстом, щоб не втрачати початкові нулі.
alter table public.accounts add column if not exists card_last4 text;
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.accounts'::regclass
      and conname = 'accounts_card_last4_check'
  ) then
    alter table public.accounts add constraint accounts_card_last4_check
      check (card_last4 is null or card_last4 ~ '^[0-9]{4}$');
  end if;
end $$;
