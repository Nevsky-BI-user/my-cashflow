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
async function findToken(userId: string): Promise<{ owner: string; token: string } | null | 'error'> {
  const { data: own, error: ownErr } = await sb
    .from('profiles')
    .select('id, mono_token')
    .eq('id', userId)
    .maybeSingle();
  if (ownErr) {
    console.error('mono-balance: profile lookup failed', ownErr.message);
    return 'error';
  }
  if (own?.mono_token) return { owner: own.id, token: own.mono_token };

  const { data: others, error: othErr } = await sb
    .from('profiles')
    .select('id, mono_token')
    .not('mono_token', 'is', null)
    .neq('id', userId);
  if (othErr) {
    console.error('mono-balance: family token lookup failed', othErr.message);
    return 'error';
  }
  for (const p of others || []) {
    const { data: u } = await sb.auth.admin.getUserById(p.id);
    if (isAllowed(u?.user?.email)) return { owner: p.id, token: p.mono_token };
  }
  return null;
}

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

  let body: { force?: unknown } = {};
  try {
    body = (await req.json()) || {};
  } catch {
    // порожнє тіло допустиме
  }
  const force = body.force === true;

  const tok = await findToken(user.id);
  if (tok === 'error') return json({ error: 'profile lookup failed' }, 500);
  if (!tok) return json({ ok: false, reason: 'no_token' });

  const { data: acc, error: accErr } = await sb
    .from('accounts')
    .select(ACC_COLS)
    .eq('user_id', tok.owner)
    .eq('bank', 'mono')
    .order('id')
    .limit(1)
    .maybeSingle();
  if (accErr) {
    console.error('mono-balance: account lookup failed', accErr.message);
    return json({ error: 'account lookup failed' }, 500);
  }
  if (!acc) return json({ ok: false, reason: 'no_account' });

  // Свіже значення: не чіпаємо Monobank, щоб не впертися в ліміт
  const age = acc.balance_updated_at ? Date.now() - new Date(acc.balance_updated_at).getTime() : Infinity;
  if (!force && age < FRESH_MS) return json({ ok: true, cached: true, account: view(acc) });

  const monoRes = await fetch('https://api.monobank.ua/personal/client-info', {
    headers: { 'X-Token': tok.token },
  });
  if (monoRes.status === 429) return json({ ok: false, reason: 'rate_limited', retry_in: 60 });
  if (!monoRes.ok) {
    console.error('mono-balance: client-info status', monoRes.status);
    return json({ ok: false, reason: 'mono_error', status: monoRes.status });
  }

  const info = await monoRes.json().catch(() => null);
  const list: any[] = Array.isArray(info?.accounts) ? info.accounts : [];
  const picked =
    (acc.mono_account_id && list.find((a) => a?.id === acc.mono_account_id)) ||
    list.find((a) => a?.type === 'black' && a?.currencyCode === UAH) ||
    list.find((a) => a?.currencyCode === UAH);
  if (!picked) {
    console.error('mono-balance: no UAH account among', list.length);
    return json({ ok: false, reason: 'no_uah_account' });
  }

  // Monobank віддає копійки; balance включає кредитний ліміт
  const bal = Number(picked.balance) || 0;
  const lim = Number(picked.creditLimit) || 0;
  const patch: Record<string, unknown> = {
    mono_account_id: picked.id,
    balance_updated_at: new Date().toISOString(),
  };
  if (lim > 0) {
    patch.credit_limit = lim / 100;
    patch.balance = Math.max(0, bal - lim) / 100;
    patch.debt = Math.max(0, lim - bal) / 100;
  } else {
    patch.balance = bal / 100;
  }

  const { data: upd, error: updErr } = await sb
    .from('accounts')
    .update(patch)
    .eq('id', acc.id)
    .select(ACC_COLS)
    .single();
  if (updErr) {
    console.error('mono-balance: update failed', updErr.message);
    return json({ error: 'update failed' }, 500);
  }

  return json({ ok: true, account: view(upd) });
});
