import {readFileSync} from 'node:fs';
import {financeProjection} from '../supabase/functions/_shared/budget.ts';
console.log(JSON.stringify(JSON.parse(readFileSync(0,'utf8')).map(({data,options,asof,through,scenario})=>financeProjection(data,options??{asof,through,scenario}))));
