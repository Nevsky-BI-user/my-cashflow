import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { NBU_URL, PRIVAT_URL, parseNbu, parsePrivat, type RateRow } from '../_shared/rates.ts';

// Оновлення курсів USD/EUR у exchange_rates: офіційний НБУ (source 'nbu') і готівковий ПриватБанку (source 'privat').
// Кличуть: застосунок (JWT користувача з whitelist), коли збережені курси старші за 12 год,
// або сервер із service role (задачі cron немає: ключ лише в env функцій).
// Пише лише те джерело, що відповіло валідно; збій одного не чіпає рядків іншого, нулів не пише ніколи.

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

// Whitelist: другий шар захисту окрім RLS (як ALLOWED_EMAILS на фронті)
const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

// Два пристрої відкрили застосунок одночасно: свіжі за 10 хв курси не тягнемо вдруге
const FRESH_MS = 10 * 60_000;
const FETCH_MS = 8_000;

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...CORS } });

const getJson = async (url: string) => {
  const r = await fetch(url, { signal: AbortSignal.timeout(FETCH_MS), headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return await r.json();
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  const jwt = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!jwt) return json({ error: 'no auth' }, 401);
  // service role (виклик з іншої функції); інакше користувач із whitelist
  const service = jwt === SERVICE_ROLE;
  if (!service) {
    const { data, error } = await sb.auth.getUser(jwt);
    const email = (data?.user?.email || '').toLowerCase();
    if (error || !data?.user) return json({ error: 'invalid token' }, 401);
    if (!ALLOWED_EMAILS.includes(email)) return json({ error: 'forbidden' }, 403);
  }

  let force = false;
  try { force = !!(await req.json())?.force; } catch (_) { /* тіло необовʼязкове */ }

  const cur = await sb.from('exchange_rates').select('ccy, source, updated_at');
  if (cur.error) return json({ error: 'read failed' }, 500);
  const rows = cur.data || [];
  const oldest = rows.length >= 4 ? Math.min(...rows.map((r: any) => Date.parse(r.updated_at) || 0)) : 0;
  if (!force && Date.now() - oldest < FRESH_MS) return json({ ok: true, fresh: true, saved: [] });

  const at = new Date().toISOString();
  const errors: string[] = [];
  const got: RateRow[] = [];
  const [nbu, privat] = await Promise.allSettled([getJson(NBU_URL), getJson(PRIVAT_URL)]);
  if (nbu.status === 'fulfilled') {
    const r = parseNbu(nbu.value, at);
    if (r.length) got.push(...r); else errors.push('nbu: no valid rates');
  } else errors.push('nbu: ' + String(nbu.reason?.message || nbu.reason));
  if (privat.status === 'fulfilled') {
    const r = parsePrivat(privat.value, at);
    if (r.length) got.push(...r); else errors.push('privat: no valid rates');
  } else errors.push('privat: ' + String(privat.reason?.message || privat.reason));

  if (!got.length) return json({ ok: false, errors }, 502);
  // updated_at задаємо явно: default спрацьовує лише на insert, а без нього 12-годинна перевірка не скинулась би
  const up = await sb.from('exchange_rates').upsert(got, { onConflict: 'ccy,source' });
  if (up.error) return json({ ok: false, errors: [...errors, 'write failed'] }, 500);
  return json({ ok: errors.length === 0, saved: got.map((r) => r.source + ':' + r.ccy), errors });
});
