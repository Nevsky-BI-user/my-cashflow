import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Модель категоризації: дешева і швидка, відповідь лише id категорії
const CATEGORIZE_MODEL = 'claude-haiku-4-5-20251001';
const MAX_ATTEMPTS = 3; // після стількох відмов рядок випадає з масової категоризації

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const CLAUDE_API_KEY = Deno.env.get('CLAUDE_API_KEY') || '';

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

// sha256 у hex через Web Crypto
async function sha256Hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// Позначити транзакцію категорією; лише якщо її досі не категоризовано вручну
async function applyCategory(txId: number, categoryId: number) {
  const { error } = await sb
    .from('transactions')
    .update({ category_id: categoryId, auto_categorized: true })
    .eq('id', txId)
    .is('category_id', null);
  if (error) {
    console.error('categorize: update transactions failed', { txId, categoryId, error });
    return false;
  }
  return true;
}

// Відмова без категорії: інкремент transactions.categorize_attempts, щоб
// categorize-batch не брав той самий рядок (і не платив Claude) нескінченно
async function giveUp(txId: number, reason: string) {
  const { data } = await sb.from('transactions').select('categorize_attempts').eq('id', txId).maybeSingle();
  const attempts = (data?.categorize_attempts ?? 0) + 1;
  await sb.from('transactions').update({ categorize_attempts: attempts }).eq('id', txId);
  return json({ category_id: null, reason, attempts, gave_up: attempts >= MAX_ATTEMPTS });
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  // Внутрішня функція: кличуть інші Edge Functions з Bearer <SERVICE_ROLE>
  const auth = req.headers.get('Authorization') || '';
  const token = auth.replace(/^Bearer\s+/i, '');
  if (!token || !SERVICE_ROLE || token !== SERVICE_ROLE) {
    return json({ error: 'unauthorized' }, 401);
  }

  if (!CLAUDE_API_KEY) return json({ error: 'no_claude_key' }, 400);

  let body: { transaction_id?: unknown };
  try {
    body = await req.json();
  } catch {
    return json({ error: 'bad_json' }, 400);
  }
  const txId = Number(body?.transaction_id);
  if (!Number.isInteger(txId) || txId <= 0) return json({ error: 'bad_transaction_id' }, 400);

  // Транзакція
  const { data: tx, error: txErr } = await sb
    .from('transactions')
    .select('id, description, mcc, amount, type, category_id, user_id')
    .eq('id', txId)
    .maybeSingle();
  if (txErr) {
    console.error('categorize: transaction lookup failed', { txId, txErr });
    return json({ error: 'transaction_lookup_failed' }, 500);
  }
  if (!tx) return json({ error: 'not_found' }, 404);
  if (tx.category_id != null) return json({ category_id: tx.category_id, skipped: true });

  // Категорії сімейні (RLS віддає обом усе), тому беремо всі, фільтруємо за типом
  const { data: cats, error: catErr } = await sb
    .from('categories')
    .select('id, name, is_income');
  if (catErr) {
    console.error('categorize: categories lookup failed', { txId, catErr });
    return json({ error: 'categories_lookup_failed' }, 500);
  }
  const wantIncome = tx.type === 'income';
  // is_income null вважаємо витратою
  const pool = (cats || []).filter((c) => (c.is_income === true) === wantIncome);
  if (pool.length === 0) return giveUp(txId, 'no_categories');
  const poolIds = new Set(pool.map((c) => c.id));

  // Ключ кешу: опис, а без опису MCC
  const desc = (tx.description || '').trim();
  const mcc = tx.mcc ?? null;
  let key: string;
  if (desc) key = desc.toLowerCase();
  else if (mcc != null) key = 'mcc:' + mcc;
  else return giveUp(txId, 'no_description');
  const hash = await sha256Hex(key);

  // Кеш
  const { data: cached, error: cacheErr } = await sb
    .from('categorization_cache')
    .select('category_id')
    .eq('description_hash', hash)
    .maybeSingle();
  if (cacheErr) console.error('categorize: cache lookup failed', { txId, cacheErr });
  if (cached?.category_id != null && poolIds.has(cached.category_id)) {
    const ok = await applyCategory(txId, cached.category_id);
    if (!ok) return json({ error: 'update_failed' }, 500);
    return json({ category_id: cached.category_id, from_cache: true });
  }

  // Claude API
  const catList = pool.map((c) => `${c.id}:${c.name}`).join(', ');
  const amount = Math.abs(Number(tx.amount) || 0);
  const system = `Категоризуй транзакцію. Категорії: {${catList}}. Відповідай ТІЛЬКИ числом: id категорії.`;
  const userMsg = `'${desc}', MCC: ${mcc ?? 'немає'}, ${amount} грн`;

  let answer = '';
  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: CATEGORIZE_MODEL,
        max_tokens: 20,
        system,
        messages: [{ role: 'user', content: userMsg }],
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      console.error('categorize: Claude API error', { txId, status: res.status, detail: text.slice(0, 300) });
      return json({ error: 'claude_error', status: res.status }, 502);
    }
    const data = await res.json();
    answer = (data?.content || [])
      .filter((p: { type?: string }) => p?.type === 'text')
      .map((p: { text?: string }) => p.text || '')
      .join(' ');
  } catch (e) {
    console.error('categorize: Claude API fetch failed', { txId, e: String(e) });
    return json({ error: 'claude_error' }, 502);
  }

  const m = answer.match(/\d+/);
  const categoryId = m ? parseInt(m[0], 10) : NaN;
  if (!poolIds.has(categoryId)) {
    console.error('categorize: bad model answer', { txId, answer: answer.slice(0, 100) });
    return giveUp(txId, 'bad_model_answer');
  }

  // Кеш: конфлікт по description_hash не перезаписує наявний запис
  const { error: insErr } = await sb
    .from('categorization_cache')
    .upsert(
      { description_hash: hash, description: desc || key, category_id: categoryId, mcc },
      { onConflict: 'description_hash', ignoreDuplicates: true },
    );
  if (insErr) console.error('categorize: cache insert failed', { txId, insErr });

  const ok = await applyCategory(txId, categoryId);
  if (!ok) return json({ error: 'update_failed' }, 500);
  return json({ category_id: categoryId });
});
