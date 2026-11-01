import { monoBalancePatch } from '../_shared/mono-accounts.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Живий баланс рахунку Monobank: застосунок кличе sb.functions.invoke('mono-balance') з JWT користувача.
// Токен і рахунок належать власнику X-Token; інший член сімʼї отримує той самий рахунок.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

// Whitelist: другий шар захисту окрім RLS (як ALLOWED_EMAILS на фронті)
const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

// Ліміт Monobank: 1 запит client-info на 60 секунд
const FRESH_MS = 60_000;
const UAH = 980;

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

// CORS: функцію кличе браузер із GitHub Pages, тому preflight OPTIONS і заголовки обовʼязкові
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS },
  });

const ACC_COLS = 'id, name, balance, debt, credit_limit, balance_updated_at, mono_account_id';

const view = (a: any) => ({
  id: a.id,
  balance: Number(a.balance),
  debt: Number(a.debt),
  credit_limit: a.credit_limit === null ? null : Number(a.credit_limit),
  balance_updated_at: a.balance_updated_at,
  name: a.name,
});

const isAllowed = (email: string | undefined | null) =>
  ALLOWED_EMAILS.includes((email || '').toLowerCase());

// Токен того, хто кличе; якщо його немає, токен іншого профілю сімʼї (теж з whitelist)
Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  const auth = req.headers.get('Authorization') || '';
  const jwt = auth.replace(/^Bearer\s+/i, '');
  if (!jwt) return json({ error: 'no auth' }, 401);

  const { data: userData, error: userErr } = await sb.auth.getUser(jwt);
  const user = userData?.user;
  if (userErr || !user) return json({ error: 'invalid token' }, 401);
  if (!isAllowed(user.email)) return json({ error: 'forbidden' }, 403);

  const { data: profiles, error: profilesErr } = await sb.from('profiles').select('id,mono_token').not('mono_token', 'is', null);
  if (profilesErr) return json({ error: 'profile lookup failed' }, 500);
  const accounts: any[] = [];
  const errors: any[] = [];
  let cached = true;
  for (const profile of profiles || []) {
    const { data: owner, error: ownerErr } = await sb.auth.admin.getUserById(profile.id);
    if (ownerErr || !isAllowed(owner?.user?.email)) continue;
    const { data: linked, error: accErr } = await sb.from('accounts').select(ACC_COLS).eq('user_id', profile.id).eq('bank', 'mono').not('mono_account_id', 'is', null).order('id');
    if (accErr) return json({ error: 'account lookup failed' }, 500);
    if (!linked?.length) continue;
    const newest = Math.max(...linked.map(a => Date.parse(a.balance_updated_at) || 0));
    if (Date.now() - newest < FRESH_MS) { accounts.push(...linked.map(view)); continue; }
    cached = false;
    let info: any;
    try {
      const res = await fetch('https://api.monobank.ua/personal/client-info', { headers: { 'X-Token': profile.mono_token } });
      if (!res.ok) {
        errors.push(...linked.map(a => ({ account_id: a.id, reason: res.status === 429 ? 'rate_limited' : 'mono_error' })));
        accounts.push(...linked.map(view)); continue;
      }
      info = await res.json();
    } catch {
      errors.push(...linked.map(a => ({ account_id: a.id, reason: 'mono_error' })));
      accounts.push(...linked.map(view)); continue;
    }
    for (const acc of linked) {
      const matches = (Array.isArray(info?.accounts) ? info.accounts : []).filter((a: any) => a.id === acc.mono_account_id && a.currencyCode === UAH);
      if (matches.length !== 1) { errors.push({ account_id: acc.id, reason: 'unknown_account' }); accounts.push(view(acc)); continue; }
      let patch: any;
      try { patch = monoBalancePatch(matches[0]); }
      catch { errors.push({ account_id: acc.id, reason: 'invalid_mono_balance' }); accounts.push(view(acc)); continue; }
      const { data: updated, error: updateErr } = await sb.from('accounts').update(patch).eq('id', acc.id).eq('user_id', profile.id).select(ACC_COLS).single();
      if (updateErr) { errors.push({ account_id: acc.id, reason: 'update_failed' }); accounts.push(view(acc)); }
      else accounts.push(view(updated));
    }
  }
  if (!accounts.length) return json({ ok: false, reason: 'no_account', accounts: [] });
  return json({ ok: true, cached, account: accounts[0], accounts, errors });
});
