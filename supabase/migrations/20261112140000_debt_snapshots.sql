-- 53: щоденний знімок боргу кредиток для графіка боргу за весь строк.
-- Історії боргу кредиток у базі раніше не було: знімки пишуться з 12.11.2026, минуле не відновлюється.
-- Пише застосунок (рядок за день, останнє значення дня перезаписує попереднє). Повторне застосування безпечне.
create table if not exists public.debt_snapshots (
  day date primary key,
  card_debt numeric not null check (card_debt >= 0),
  updated_at timestamptz not null default now()
);
alter table public.debt_snapshots enable row level security;
drop policy if exists "family full" on public.debt_snapshots;
create policy "family full" on public.debt_snapshots for all using (public.is_family_member()) with check (public.is_family_member());
revoke all on public.debt_snapshots from anon;
comment on table public.debt_snapshots is 'Борг кредиток на кінець дня (гривні), як у панелі «Борг станом на сьогодні».';
