-- 06: сімʼя може писати в categorization_cache з UI (ручне перевизначення категорії, 6.3)
create policy "family write cache" on categorization_cache
  for insert with check (is_family_member());
create policy "family update cache" on categorization_cache
  for update using (is_family_member()) with check (is_family_member());
