-- Ідентифікатор рахунку Monobank не може належати двом локальним рахункам.
create unique index if not exists accounts_mono_account_id_unique
  on public.accounts (mono_account_id);
