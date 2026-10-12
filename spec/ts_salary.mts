// Вхід — синтетичні випадки з salary.py; Node 24 виконує вихідний TypeScript.
import { readFileSync } from 'node:fs';
import { lastPayout, periodBudget } from '../supabase/functions/_shared/budget.ts';
import type { Snapshot } from '../supabase/functions/_shared/budget.ts';

const cases: { snap: Snapshot; today: string }[] = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(cases.map(({ snap, today }) => {
  const next = periodBudget(snap, today).payout;
  return { current: lastPayout(snap.salary, today), next, after: periodBudget(snap, next.date).payout };
})));
