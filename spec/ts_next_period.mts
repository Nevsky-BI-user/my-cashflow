import {readFileSync} from 'node:fs';
import {nextPeriodPlan} from '../supabase/functions/_shared/budget.ts';
console.log(JSON.stringify(JSON.parse(readFileSync(0,'utf8')).map(({data,asof})=>nextPeriodPlan(data,asof))));
