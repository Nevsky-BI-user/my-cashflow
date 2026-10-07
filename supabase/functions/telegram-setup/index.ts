// Реєстрація webhook Telegram (Фаза 4.3). Кличеться із застосунку: JWT + whitelist,
// як у mono-register. Секрет TELEGRAM_WEBHOOK_SECRET лишається серверним:
// Telegram потім надсилає його в заголовку X-Telegram-Bot-Api-Secret-Token.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN') || '';
const WEBHOOK_SECRET = Deno.env.get('TELEGRAM_WEBHOOK_SECRET') || '';

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

  if (!BOT_TOKEN || !WEBHOOK_SECRET) {
    return json({ error: 'no_secrets', message: 'Задайте TELEGRAM_BOT_TOKEN і TELEGRAM_WEBHOOK_SECRET' }, 400);
  }

  const webhookUrl = `${SUPABASE_URL}/functions/v1/telegram-webhook`;
  let tg: any;
  try {
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/setWebhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: webhookUrl,
        secret_token: WEBHOOK_SECRET,
        allowed_updates: ['message'],
        drop_pending_updates: true,
      }),
    });
    tg = await r.json();
  } catch (e) {
    console.error('setWebhook failed:', e);
    return json({ error: 'telegram_unreachable' }, 502);
  }

  if (!tg?.ok) {
    console.error('setWebhook rejected:', tg);
    return json({ error: 'telegram_rejected', message: tg?.description || '' }, 502);
  }

  // Імʼя бота, щоб застосунок міг показати, кому писати
  let username = '';
  try {
    const me = await (await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getMe`)).json();
    username = me?.result?.username || '';
  } catch (_) { /* не критично */ }

  return json({ ok: true, username });
});
