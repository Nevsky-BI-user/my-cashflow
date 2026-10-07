import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

// Whitelist — другий шар захисту окрім RLS (як ALLOWED_EMAILS на фронті)
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

// Автокатегоризація у фоні: результат не чекаємо, помилки не валять webhook
// Backfill дає до сотень транзакцій за раз: категоризуємо послідовно з паузою,
// щоб не впертись у ліміти Claude API (categorize сам кешує повтори опису)
function categorizeLater(ids: number[]) {
  const p = (async () => {
    for (const id of ids) {
      await fetch(`${SUPABASE_URL}/functions/v1/categorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${SERVICE_ROLE}` },
        body: JSON.stringify({ transaction_id: id }),
      }).catch((e) => console.error('categorize call failed:', e));
      await new Promise((r) => setTimeout(r, 150));
    }
  })();
  // Без waitUntil фонове завдання може обірватись після відповіді
  const wait = (globalThis as any).EdgeRuntime?.waitUntil;
  if (wait) wait(p);
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  // verify_jwt=true → у заголовку JWT авторизованого користувача
  const auth = req.headers.get('Authorization') || '';
  const jwt = auth.replace(/^Bearer\s+/i, '');
  if (!jwt) return json({ error: 'no auth' }, 401);

  const { data: userData, error: userErr } = await sb.auth.getUser(jwt);
  const user = userData?.user;
  if (userErr || !user) return json({ error: 'invalid token' }, 401);
  if (!ALLOWED_EMAILS.includes((user.email || '').toLowerCase())) {
    return json({ error: 'forbidden' }, 403);
  }

  // Параметри: days (≤31, ліміт вікна Mono), account (дефолт '0' — основний рахунок)
  let bodyIn: any = {};
  try {
    bodyIn = await req.json();
  } catch {
    // порожнє тіло — ок, беремо дефолти
  }
  const days = Math.min(Math.max(Number(bodyIn.days) || 31, 1), 31);
  const account = String(bodyIn.account || '0');

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('id, mono_token')
    .eq('id', user.id)
    .maybeSingle();
  if (profErr) return json({ error: 'profile lookup failed' }, 500);
  if (!prof?.mono_token) return json({ error: 'no_token' }, 400);

  // Один запит до Monobank (rate limit: 1 запит / 60с на токен)
  const to = Math.floor(Date.now() / 1000);
  const from = to - days * 24 * 3600;
  const monoRes = await fetch(
    `https://api.monobank.ua/personal/statement/${account}/${from}/${to}`,
    { headers: { 'X-Token': prof.mono_token } },
  );

  if (monoRes.status === 429) {
    return json({ error: 'rate_limited', message: 'Monobank: 1 запит на 60 секунд. Спробуйте за хвилину.' }, 429);
  }
  if (!monoRes.ok) {
    const text = await monoRes.text();
    return json({ error: 'mono_error', status: monoRes.status, detail: text.slice(0, 300) }, 502);
  }

  const items = await monoRes.json();
  if (!Array.isArray(items)) return json({ error: 'unexpected_mono_response' }, 502);

  const rows = items
    .filter((si: any) => si?.id)
    .map((si: any) => ({
      user_id: prof.id,
      amount: Math.abs(si.amount) / 100,
      type: si.amount < 0 ? 'expense' : 'income',
      description: si.description || null,
      source: 'mono',
      source_id: si.id as string,
      mcc: si.mcc || null,
      date: new Date(si.time * 1000).toISOString().split('T')[0],
    }));

  if (!rows.length) return json({ ok: true, fetched: 0, inserted: 0, skipped: 0 });

  // Дедуп: один запит по всіх source_id замість N
  const ids = rows.map((r) => r.source_id);
  const { data: existing, error: dupErr } = await sb
    .from('transactions')
    .select('source_id')
    .in('source_id', ids);
  if (dupErr) return json({ error: 'dedup lookup failed' }, 500);

  const seen = new Set((existing || []).map((e: any) => e.source_id));
  const fresh = rows.filter((r) => !seen.has(r.source_id));

  if (fresh.length) {
    const { data: ins, error: insErr } = await sb.from('transactions').insert(fresh).select('id');
    if (insErr) return json({ error: 'insert failed', detail: insErr.message }, 500);
    // Один виклик на кожну вставлену транзакцію (categorize сам кешує)
    categorizeLater((ins || []).map((t: { id: number }) => t.id));
  }

  return json({
    ok: true,
    fetched: rows.length,
    inserted: fresh.length,
    skipped: rows.length - fresh.length,
  });
});
