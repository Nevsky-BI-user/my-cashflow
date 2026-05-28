import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const MONO_SECRET = Deno.env.get('MONO_WEBHOOK_SECRET')!;

const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

Deno.serve(async (req) => {
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

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('mono_token')
    .eq('id', user.id)
    .maybeSingle();
  if (profErr) return json({ error: 'profile lookup failed' }, 500);
  if (!prof?.mono_token) return json({ error: 'no_token' }, 400);

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
    const text = await monoRes.text();
    return json({ error: 'mono_error', status: monoRes.status, detail: text.slice(0, 300) }, 502);
  }

  return json({ ok: true });
});
