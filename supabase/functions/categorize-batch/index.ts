import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Те саме значення, що в categorize: рядки з більшою кількістю відмов у вибірку не йдуть
const MAX_ATTEMPTS = 3;

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;
const PAUSE_MS = 100;
// Запас до ліміту часу Edge Function: після цього зупиняємось, решту добере наступний запуск
const TIME_BUDGET_MS = 110_000;

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

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Кількість некатегоризованих транзакцій (усі сімейні, без фільтра user_id)
async function countUncategorized(): Promise<number | null> {
  const { count, error } = await sb
    .from('transactions')
    .select('id', { count: 'exact', head: true })
    .is('category_id', null).eq('expense_allocations', '[]')
    .is('transfer_id', null)
    .lt('categorize_attempts', MAX_ATTEMPTS);
  if (error) {
    console.error('categorize-batch: count failed', error);
    return null;
  }
  return count ?? 0;
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
  if (!ALLOWED_EMAILS.includes((user.email || '').toLowerCase())) {
    return json({ error: 'forbidden' }, 403);
  }

  let body: { limit?: unknown; count_only?: unknown } = {};
  try {
    body = (await req.json()) || {};
  } catch {
    // порожнє тіло допустиме: діють значення за замовчуванням
  }

  // Лише підрахунок для напису в налаштуваннях
  if (body.count_only === true) {
    const n = await countUncategorized();
    if (n === null) return json({ error: 'count_failed' }, 500);
    return json({ uncategorized: n });
  }

  let limit = Number(body.limit);
  if (!Number.isFinite(limit) || limit <= 0) limit = DEFAULT_LIMIT;
  limit = Math.min(Math.floor(limit), MAX_LIMIT);

  const { data: txs, error: txErr } = await sb
    .from('transactions')
    .select('id')
    .is('category_id', null).eq('expense_allocations', '[]')
    .is('transfer_id', null)
    .lt('categorize_attempts', MAX_ATTEMPTS)
    .order('date', { ascending: false })
    .limit(limit);
  if (txErr) {
    console.error('categorize-batch: select failed', txErr);
    return json({ error: 'select_failed' }, 500);
  }

  const started = Date.now();
  let processed = 0;
  let categorized = 0;
  let fromCache = 0;
  let errors = 0;
  const reasons = new Map<string, { code: string; status?: number; retryable: boolean; count: number }>();
  // Дозволені причини без описів операцій, сирих відповідей чи секретів.
  const allowed = new Set(['configuration','credit_balance','provider_auth','rate_limit','provider_unavailable','provider_request','network','database','invalid_request','not_found','internal_auth','bad_model_answer','unknown']);
  const recordError = (body: any, httpStatus?: number) => {
    const status = Number.isInteger(body?.status) && body.status >= 100 && body.status <= 599 ? body.status : httpStatus;
    const code = allowed.has(body?.error_code) ? body.error_code : body?.reason === 'bad_model_answer' ? 'bad_model_answer' : body?.error === 'no_claude_key' ? 'configuration' : body?.error === 'claude_error' ? status === 401 || status === 403 ? 'provider_auth' : status === 429 ? 'rate_limit' : status && status >= 500 ? 'provider_unavailable' : 'provider_request' : ['transaction_lookup_failed','categories_lookup_failed','update_failed'].includes(body?.error) ? 'database' : httpStatus === 401 || httpStatus === 403 ? 'internal_auth' : httpStatus === 404 ? 'not_found' : httpStatus === 400 ? 'invalid_request' : 'unknown';
    const retryable = ['rate_limit','provider_unavailable','network','database','unknown'].includes(code);
    const key = code + ':' + String(status || '');
    const previous = reasons.get(key);
    if (previous) previous.count++; else reasons.set(key, { code, ...(status ? { status } : {}), retryable, count: 1 });
    errors++;
  };
  // Внутрішні перекази та відсутні опис/категорії пропускаємо без помилки.
  let skipped = 0;

  for (const tx of txs || []) {
    if (Date.now() - started > TIME_BUDGET_MS) {
      console.error('categorize-batch: time budget reached, stopping early', { processed });
      break;
    }
    processed++;
    try {
      const res = await fetch(`${SUPABASE_URL}/functions/v1/categorize`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${SERVICE_ROLE}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ transaction_id: tx.id }),
        signal: AbortSignal.timeout(25_000),
      });
      if (!res.ok) {
        const failure = await res.json().catch(() => null);
        recordError(failure, res.status);
        console.error('categorize-batch: categorize http error', { status: res.status });
      } else {
        const r = await res.json();
        if (r?.skipped) {
          skipped++;
        } else if (r?.category_id == null) {
          if (r?.reason === 'no_description' || r?.reason === 'no_categories' || r?.reason === 'internal_transfer') {
            console.warn('categorize-batch: skipped', { id: tx.id, reason: r.reason });
            skipped++;
          } else {
            console.error('categorize-batch: no category', { id: tx.id, reason: r?.reason });
            recordError(r);
          }
        } else if (r.skipped) {
          // категорію вже поставили (UI або паралельний виклик): не наш результат
        } else if (r.from_cache) {
          fromCache++;
        } else {
          categorized++;
        }
      }
    } catch (e) {
      console.error('categorize-batch: categorize failed');
      recordError({ error_code: 'network' });
    }
    await sleep(PAUSE_MS);
  }

  const remaining = await countUncategorized();
  return json({
    ok: true,
    processed,
    categorized,
    from_cache: fromCache,
    errors,
    error_reasons: [...reasons.values()],
    skipped,
    remaining,
  });
});
