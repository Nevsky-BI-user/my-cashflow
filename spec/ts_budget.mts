// TS-бік паритету для spec: те саме, що /balance у боті (deriveAccounts, unassignedAdj, fixedPaid, minSpendStatus, freeToPayout)
// node spec/ts_budget.mts <знімок.json> <YYYY-MM-DD>: друкує рядок JSON з результатом freeToPayout
import fs from 'node:fs';
import { deriveAccounts, fixedPaid, freeToPayout, minSpendStatus, unassignedAdj } from '../supabase/functions/_shared/budget.ts';

const [file, today] = [process.argv[2], process.argv[3]];
const snap = JSON.parse(fs.readFileSync(file, 'utf8'));
const tx = snap.account_tx || [];
const manual = snap.accounts.filter((a: any) => !a.mono_account_id && a.balance_updated_at);
const since = Math.min(...manual.map((a: any) => Date.parse(a.balance_updated_at)));
const un = isFinite(since) ? unassignedAdj(tx, since) : 0;
snap.accounts = deriveAccounts(snap.accounts, tx);
snap.paid = fixedPaid(tx);
const ms = minSpendStatus(snap.accounts, tx.filter((t: any) => String(t.date || '') <= today), today);
const r = freeToPayout(snap, today, Number(snap.spent) || 0, un, ms);
console.log('JSON ' + JSON.stringify({ ...r, white: undefined, paid: snap.paid }));
