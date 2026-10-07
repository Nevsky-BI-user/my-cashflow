-- 15: кольори категорій і постійних платежів за змістом, а не за порядком (власник кольори не обирає).
-- Палітра: корал #f28b82, персик #f7a876, жовтий #f6d06f, лайм #a8d672, мʼята #6fd3b0,
-- небо #6ec6e8, барвінок #7fa8f2, лаванда #a58ff0, бузок #d78de6, рожевий #f09ac0, нейтральний #b8c1cc.
update categories set color = case
  when name ilike 'продукт%'                     then '#a8d672'
  when name ilike 'кафе%' or name ilike 'ресторан%' then '#f7a876'
  when name ilike 'транспорт%'                   then '#6ec6e8'
  when name ilike 'авто%'                        then '#7fa8f2'
  when name ilike 'зв%язок%' or name ilike 'інтернет%' then '#a58ff0'
  when name ilike 'підписк%'                     then '#d78de6'
  when name ilike 'дитин%' or name ilike 'діти%' then '#f6d06f'
  when name ilike 'здоров%' or name ilike 'аптек%' then '#f28b82'
  when name ilike 'одяг%'                        then '#f09ac0'
  when name ilike 'дім%' or name ilike 'житло%' or name ilike 'комунал%' then '#6fd3b0'
  when name ilike 'подарун%'                     then '#f09ac0'
  when name ilike 'розваг%'                      then '#d78de6'
  when name ilike 'інше%'                        then '#b8c1cc'
  when name ilike 'зарплат%'                     then '#6fd3b0'
  when name ilike 'аванс%'                       then '#a8d672'
  when name ilike 'фріланс%'                     then '#6ec6e8'
  when name ilike 'поверненн%'                   then '#7fa8f2'
  when name ilike 'подарунок%'                   then '#f09ac0'
  when name ilike 'інший дохід%'                 then '#a58ff0'
  else color end;

update fixed_payments set color = case
  when type = 'income'                                           then '#6fd3b0'
  when name ilike '%інтернет%' or name ilike '%звʼязок%' or name ilike '%зв''язок%' or name ilike '%мобіл%' then '#6ec6e8'
  when name ilike '%оренд%' or name ilike '%житл%' or name ilike '%комунал%' or name ilike '%гараж%' then '#7fa8f2'
  when name ilike '%страх%'                                      then '#a58ff0'
  when name ilike '%підписк%' or name ilike '%netflix%' or name ilike '%spotify%' or name ilike '%youtube%' then '#d78de6'
  when name ilike '%спорт%' or name ilike '%зал%'                then '#a8d672'
  else '#f7a876' end;
