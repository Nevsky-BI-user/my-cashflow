-- 11: карта бажань. Фото цілі в приватному bucket `goals` (signed URL на фронтенді, як у чеків),
-- шлях у goals.image_path; achieved_at для досягнутих цілей.
alter table goals
  add column if not exists image_path text,
  add column if not exists achieved_at timestamptz;

-- Bucket приватний, до 5 МБ, лише зображення
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('goals', 'goals', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

drop policy if exists "family upload goals" on storage.objects;
drop policy if exists "family read goals" on storage.objects;
drop policy if exists "family update goals" on storage.objects;
drop policy if exists "family delete goals" on storage.objects;

create policy "family upload goals" on storage.objects for insert
  with check (bucket_id = 'goals' and public.is_family_member());

create policy "family read goals" on storage.objects for select
  using (bucket_id = 'goals' and public.is_family_member());

create policy "family update goals" on storage.objects for update
  using (bucket_id = 'goals' and public.is_family_member())
  with check (bucket_id = 'goals' and public.is_family_member());

create policy "family delete goals" on storage.objects for delete
  using (bucket_id = 'goals' and public.is_family_member());
