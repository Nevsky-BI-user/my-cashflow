import { refreshMonoAccounts } from '../_shared/mono-refresh.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Живий баланс рахунку Monobank: застосунок кличе sb.functions.invoke('mono-balance') з JWT користувача.
// Токен і рахунок належать власнику X-Token; інший член сімʼї отримує той самий рахунок.
// Саме оновлення (ліміт 60 с на токен, міграція картки) у _shared/mono-refresh.ts, його ж кличе mono-refresh з pg_cron.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

// Whitelist: другий шар захисту окрім RLS (як ALLOWED_EMAILS на фронті)
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

  const wait = (globalThis as any).EdgeRuntime?.waitUntil;
  const r = await refreshMonoAccounts({
    sb, fetch: (url, init) => fetch(url, init), supabaseUrl: SUPABASE_URL, serviceRole: SERVICE_ROLE, allowed: isAllowed,
    waitUntil: wait ? (p) => wait.call((globalThis as any).EdgeRuntime, p) : undefined,
  });
  if (!r.ok) return json({ error: r.error }, 500);
  if (!r.accounts.length) return json({ ok: false, reason: 'no_account', accounts: [] });
  return json({ ok: true, cached: r.cached, account: r.accounts[0], accounts: r.accounts, errors: r.errors });
});
