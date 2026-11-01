import { selectMonoAccount, monoBalancePatch, registrationTarget } from '../_shared/mono-accounts.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const MONO_SECRET = Deno.env.get('MONO_WEBHOOK_SECRET')!;

const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

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

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  const auth = req.headers.get('Authorization') || '';
  const jwt = auth.replace(/^Bearer\s+/i, '');
  if (!jwt) return json({ error: 'no auth' }, 401);

  const { data: userData, error: userErr } = await sb.auth.getUser(jwt);
  const user = userData?.user;
  if (userErr || !user) return json({ error: 'invalid token' }, 401);
  if (!ALLOWED_EMAILS.includes((user.email || '').toLowerCase())) {
    return json({ error: 'forbidden' }, 403);
  }

  let input: any = {};
  try { input = await req.json(); } catch { }
  if (!input || typeof input !== 'object' || Array.isArray(input)) return json({ error: 'bad_json' }, 400);
  if (input.profile_id != null && input.profile_id !== user.id) return json({ error: 'profile_changed' }, 403);

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('mono_token')
    .eq('id', user.id)
    .maybeSingle();
  if (profErr) return json({ error: 'profile lookup failed' }, 500);
  if (!prof?.mono_token) return json({ error: 'no_token' }, 400);

  const infoRes = await fetch('https://api.monobank.ua/personal/client-info', { headers: { 'X-Token': prof.mono_token } });
  if (!infoRes.ok) return json({ error: infoRes.status === 429 ? 'rate_limited' : 'mono_error' }, infoRes.status === 429 ? 429 : 502);
  const info = await infoRes.json().catch(() => null);
  const { data: accounts, error: accountsErr } = await sb.from('accounts').select('id,user_id,bank,mono_account_id,card_last4').eq('user_id', user.id);
  if (accountsErr) return json({ error: 'account lookup failed' }, 500);
  let selected: any, target: any, patch: any;
  try {
    selected = selectMonoAccount(info?.accounts || [], (accounts || []).filter(a => a.user_id === user.id && a.bank === 'mono'), input.card_last4);
    const suffixes = [...new Set((selected.maskedPan || []).map((pan: string) => pan.slice(-4)).filter((v: string) => /^\d{4}$/.test(v)))];
    const last4 = input.card_last4 || (suffixes.length === 1 ? suffixes[0] : null);
    const { data: exact, error: exactErr } = await sb.from('accounts').select('id,user_id,bank,mono_account_id,card_last4').eq('mono_account_id', selected.id);
    if (exactErr) return json({ error: 'account lookup failed' }, 500);
    target = registrationTarget([...(accounts || []).filter(a => a.mono_account_id !== selected.id), ...(exact || [])], user.id, selected, last4);
    patch = { ...monoBalancePatch(selected), ...(last4 ? { card_last4: last4 } : {}) };
  } catch (e) { return json({ error: (e as Error).message }, 400); }
  let result = target
    ? await sb.from('accounts').update(patch).eq('id', target.id).eq('user_id', user.id).select('id').single()
    : await sb.from('accounts').insert({ ...patch, user_id: user.id, name: 'Monobank', bank: 'mono', kind: selected.creditLimit > 0 ? 'credit' : 'debit', currency: 'UAH', color: '#111827' }).select('id').single();
  if (result.error?.code === '23505') result = await sb.from('accounts').select('id').eq('mono_account_id', selected.id).eq('user_id', user.id).eq('bank', 'mono').single();
  if (result.error) return json({ error: 'account save failed' }, 500);

  // URL вебхука — наша функція mono-webhook із секретом (MONO_SECRET лишається серверним)
  const webHookUrl = `${SUPABASE_URL}/functions/v1/mono-webhook?secret=${MONO_SECRET}`;

  const monoRes = await fetch('https://api.monobank.ua/personal/webhook', {
    method: 'POST',
    headers: { 'X-Token': prof.mono_token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ webHookUrl }),
  });

  if (monoRes.status === 429) {
    return json({ error: 'rate_limited', message: 'Monobank: 1 запит на 60 секунд. Спробуйте за хвилину.' }, 429);
  }
  if (!monoRes.ok) {
    return json({ error: 'mono_error', status: monoRes.status }, 502);
  }

  return json({ ok: true, account_id: result.data.id });
});
