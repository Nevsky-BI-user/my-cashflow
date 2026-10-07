import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

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

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Кількість некатегоризованих транзакцій (усі сімейні, без фільтра user_id)
async function countUncategorized(): Promise<number | null> {
  const { count, error } = await sb
    .from('transactions')
    .select('id', { count: 'exact', head: true })
    .is('category_id', null);
  if (error) {
    console.error('categorize-batch: count failed', error);
    return null;
  }
  return count ?? 0;
}

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
    .is('category_id', null)
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
      });
      if (!res.ok) {
        const text = await res.text();
        console.error('categorize-batch: categorize http error', {
          id: tx.id,
          status: res.status,
          detail: text.slice(0, 200),
        });
        errors++;
      } else {
        const r = await res.json();
        if (r?.category_id == null) {
          console.error('categorize-batch: no category', { id: tx.id, reason: r?.reason });
          errors++;
        } else if (r.skipped) {
          // категорію вже поставили (UI або паралельний виклик): не наш результат
        } else if (r.from_cache) {
          fromCache++;
        } else {
          categorized++;
        }
      }
    } catch (e) {
      console.error('categorize-batch: categorize failed', { id: tx.id, e: String(e) });
      errors++;
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
    remaining,
  });
});
