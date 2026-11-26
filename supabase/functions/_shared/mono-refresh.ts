// Оновлення балансів рахунків Monobank з client-info. Спільне для двох функцій:
// mono-balance (застосунок, JWT користувача з whitelist) і mono-refresh (pg_cron без застосунку, секрет із Vault).
// Клієнт Supabase, fetch і фонове очікування передаються ззовні: модуль перевіряють node-тести без мережі.
import { migratedMonoAccount, monoBalancePatch, statementRows } from './mono-accounts.ts';

// Ліміт Monobank: 1 запит client-info на 60 секунд на токен
export const FRESH_MS = 60_000;
const UAH = 980;

export const ACC_COLS = 'id, name, balance, debt, credit_limit, balance_updated_at, mono_account_id';

export const view = (a: any) => ({
  id: a.id,
  balance: Number(a.balance),
  debt: Number(a.debt),
  credit_limit: a.credit_limit === null ? null : Number(a.credit_limit),
  balance_updated_at: a.balance_updated_at,
  name: a.name,
});

export type MonoRefreshDeps = {
  sb: any;
  fetch: (url: string, init?: RequestInit) => Promise<Response>;
  supabaseUrl: string;
  serviceRole: string;
  allowed: (email: string | undefined | null) => boolean;
  nowMs?: () => number;
  waitUntil?: (p: Promise<unknown>) => void;
  sleep?: (ms: number) => Promise<void>;
};
export type MonoRefreshResult =
  | { ok: true; cached: boolean; accounts: ReturnType<typeof view>[]; errors: { account_id: number; reason: string }[] }
  | { ok: false; error: string };

// Пропущені операції нової картки після міграції: виписка Monobank дозволена раз на 60 с після client-info,
// тому чекаємо 61 с у фоні; дублікати за source_id пропускаються, категоризація як у mono-backfill
function importLater(d: MonoRefreshDeps, token: string, monoId: string, accountId: number, userId: string, fromSec: number) {
  const { sb } = d, sleep = d.sleep || ((ms: number) => new Promise((r) => setTimeout(r, ms)));
  const p = (async () => {
    await sleep(61_000);
    const res = await d.fetch(`https://api.monobank.ua/personal/statement/${monoId}/${fromSec}/${Math.floor(Date.now() / 1000)}`, { headers: { 'X-Token': token } });
    if (!res.ok) { console.error('mono-refresh: statement status', res.status); return; }
    const rows = statementRows(await res.json(), userId, accountId);
    if (!rows.length) return;
    const { data: seen, error: seenErr } = await sb.from('transactions').select('source_id').in('source_id', rows.map(r => r.source_id));
    if (seenErr) { console.error('mono-refresh: dedup failed', seenErr.message); return; }
    const known = new Set((seen || []).map((x: any) => x.source_id)), fresh = rows.filter(r => !known.has(r.source_id));
    if (!fresh.length) return;
    const { data: ins, error: insErr } = await sb.from('transactions').insert(fresh).select('id');
    if (insErr) { console.error('mono-refresh: insert failed', insErr.message); return; }
    console.log('mono-refresh: imported after migration', fresh.length);
    for (const t of ins || []) {
      await d.fetch(`${d.supabaseUrl}/functions/v1/categorize`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${d.serviceRole}` }, body: JSON.stringify({ transaction_id: t.id }) }).catch(e => console.error('categorize call failed:', e));
    }
  })().catch(e => console.error('mono-refresh: import failed', e));
  if (d.waitUntil) d.waitUntil(p);
}

// Усі профілі з токеном Monobank (лише власники з whitelist). Свіжий за 60 с знімок не запитується вдруге;
// відповідь 429 чи збій Monobank нічого не пише, рахунок лишається з попереднім знімком і причиною в errors
export async function refreshMonoAccounts(d: MonoRefreshDeps): Promise<MonoRefreshResult> {
  const { sb } = d, now = d.nowMs || Date.now;
  const { data: profiles, error: profilesErr } = await sb.from('profiles').select('id,mono_token').not('mono_token', 'is', null);
  if (profilesErr) return { ok: false, error: 'profile lookup failed' };
  const accounts: ReturnType<typeof view>[] = [];
  const errors: { account_id: number; reason: string }[] = [];
  let cached = true;
  for (const profile of profiles || []) {
    const { data: owner, error: ownerErr } = await sb.auth.admin.getUserById(profile.id);
    if (ownerErr || !d.allowed(owner?.user?.email)) continue;
    const { data: linked, error: accErr } = await sb.from('accounts').select(ACC_COLS).eq('user_id', profile.id).eq('bank', 'mono').not('mono_account_id', 'is', null).order('id');
    if (accErr) return { ok: false, error: 'account lookup failed' };
    if (!linked?.length) continue;
    const newest = Math.max(...linked.map((a: any) => Date.parse(a.balance_updated_at) || 0));
    if (now() - newest < FRESH_MS) { accounts.push(...linked.map(view)); continue; }
    cached = false;
    let info: any;
    try {
      const res = await d.fetch('https://api.monobank.ua/personal/client-info', { headers: { 'X-Token': profile.mono_token } });
      if (!res.ok) {
        errors.push(...linked.map((a: any) => ({ account_id: a.id, reason: res.status === 429 ? 'rate_limited' : 'mono_error' })));
        accounts.push(...linked.map(view)); continue;
      }
      info = await res.json();
    } catch {
      errors.push(...linked.map((a: any) => ({ account_id: a.id, reason: 'mono_error' })));
      accounts.push(...linked.map(view)); continue;
    }
    for (const acc of linked) {
      const cards = Array.isArray(info?.accounts) ? info.accounts : [];
      let matches = cards.filter((a: any) => a.id === acc.mono_account_id && a.currencyCode === UAH);
      // Міграція рахунку Monobank: однозначна нова картка замість зниклого id, операції з моменту знімка дотягуються у фоні
      if (!matches.length) {
        const { data: all, error: allErr } = await sb.from('accounts').select('mono_account_id').not('mono_account_id', 'is', null);
        const moved = allErr ? null : migratedMonoAccount(cards, acc, (all || []).map((a: any) => a.mono_account_id));
        if (moved) {
          matches = [moved];
          const since = Math.max(Date.parse(acc.balance_updated_at) || 0, Date.now() - 30 * 86400_000);
          importLater(d, profile.mono_token, moved.id, acc.id, profile.id, Math.floor(since / 1000) - 86400);
          console.log('mono-refresh: account migrated', acc.id);
        }
      }
      if (matches.length !== 1) { errors.push({ account_id: acc.id, reason: 'unknown_account' }); accounts.push(view(acc)); continue; }
      let patch: any;
      try { patch = monoBalancePatch(matches[0]); }
      catch { errors.push({ account_id: acc.id, reason: 'invalid_mono_balance' }); accounts.push(view(acc)); continue; }
      const { data: updated, error: updateErr } = await sb.from('accounts').update(patch).eq('id', acc.id).eq('user_id', profile.id).select(ACC_COLS).single();
      if (updateErr) { errors.push({ account_id: acc.id, reason: 'update_failed' }); accounts.push(view(acc)); }
      else accounts.push(view(updated));
    }
  }
  return { ok: true, cached, accounts, errors };
}

// Порівняння секрету за сталий час: тривалість не підказує, скільки символів збіглося (як у telegram-digest)
export function sameSecret(a: string, b: string): boolean {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

// Обробник функції mono-refresh (pg_cron): POST із заголовком x-mono-refresh-secret == MONO_REFRESH_SECRET.
// Без секрету чи з чужим значенням 403 і жодного звернення до бази. Відповідь без балансів і назв:
// pg_net зберігає тіло відповіді в net._http_response, тож туди потрапляють лише лічильники
export async function handleMonoRefresh(req: Request, secret: string, deps: MonoRefreshDeps): Promise<Response> {
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);
  if (!secret || !sameSecret(req.headers.get('x-mono-refresh-secret') || '', secret)) return json({ error: 'forbidden' }, 403);
  const r = await refreshMonoAccounts(deps);
  if (!r.ok) return json({ ok: false, error: r.error }, 500);
  return json({ ok: true, cached: r.cached, accounts: r.accounts.length, errors: r.errors.map(e => e.reason) });
}
