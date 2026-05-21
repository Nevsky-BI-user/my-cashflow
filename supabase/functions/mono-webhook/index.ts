import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const MONO_SECRET = Deno.env.get('MONO_WEBHOOK_SECRET')!;

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

Deno.serve(async (req) => {
  // Monobank робить GET для перевірки доступності webhook
  if (req.method === 'GET') return new Response('ok');
  if (req.method !== 'POST') return new Response('method not allowed', { status: 405 });

  const url = new URL(req.url);
  if (url.searchParams.get('secret') !== MONO_SECRET) {
    return new Response('forbidden', { status: 403 });
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return new Response('bad json', { status: 400 });
  }

  if (body?.type !== 'StatementItem') return new Response('ignored');

  const si = body.data?.statementItem;
  if (!si?.id) return new Response('no statement', { status: 400 });

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('id')
    .not('mono_token', 'is', null)
    .limit(1)
    .maybeSingle();

  if (profErr) {
    console.error('profile lookup error:', profErr);
    return new Response('profile error', { status: 500 });
  }
  if (!prof) return new Response('no user with mono_token');

  const { data: dup } = await sb
    .from('transactions')
    .select('id')
    .eq('source_id', si.id)
    .maybeSingle();
  if (dup) return new Response('duplicate');

  const amount = Math.abs(si.amount) / 100;
  const type = si.amount < 0 ? 'expense' : 'income';
  const date = new Date(si.time * 1000).toISOString().split('T')[0];

  const { error: insErr } = await sb.from('transactions').insert({
    user_id: prof.id,
    amount,
    type,
    description: si.description || null,
    source: 'mono',
    source_id: si.id,
    mcc: si.mcc || null,
    date,
  });

  if (insErr) {
    console.error('insert error:', insErr);
    return new Response('insert failed', { status: 500 });
  }

  return new Response('ok');
});
