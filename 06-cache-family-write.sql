-- 06: сімʼя може писати в categorization_cache з UI (ручне перевизначення категорії, 6.3)
drop policy if exists "family write cache" on categorization_cache;
create policy "family write cache" on categorization_cache
  for insert with check (is_family_member());
drop policy if exists "family update cache" on categorization_cache;
create policy "family update cache" on categorization_cache
  for update using (is_family_member()) with check (is_family_member());
