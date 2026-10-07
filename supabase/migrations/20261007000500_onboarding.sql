-- 08: позначка, що користувач пройшов вступну підказку (навчання лише при першому вході)
alter table profiles
  add column if not exists onboarded_at timestamptz;
