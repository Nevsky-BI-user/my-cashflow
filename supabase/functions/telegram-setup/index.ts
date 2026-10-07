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

  // Назва, опис і меню команд: ставляться через Bot API, аватарку ставить власник у BotFather
  const call = (method: string, body: unknown) =>
    fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => r.json()).catch((e) => ({ ok: false, description: String(e) }));
  const results = await Promise.all([
    call('setMyName', { name: 'Сімейний Кешфлоу' }),
    call('setMyShortDescription', { short_description: 'Приватний бот сімейного бюджету. Доступ лише для сімʼї.' }),
    call('setMyDescription', {
      description:
        'Записує витрати й доходи в Сімейний Кешфлоу: «250 кава», «+51000 зарплата», фото чека. ' +
        'Доступ лише для двох сімейних акаунтів: привʼязка кодом із застосунку (/start <код>).',
    }),
    call('setMyCommands', {
      commands: [
        { command: 'balance', description: 'Баланс за місяць' },
        { command: 'last', description: 'Останні 5 записів' },
        { command: 'income', description: 'Дохід: /income 51000 зарплата' },
        { command: 'help', description: 'Як користуватись' },
        { command: 'start', description: 'Привʼязати акаунт: /start <код>' },
      ],
    }),
  ]);
  results.forEach((r, i) => { if (!r?.ok) console.error('bot profile step failed', i, r); });

  // Імʼя бота, щоб застосунок міг показати, кому писати
  let username = '';
  try {
    const me = await (await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getMe`)).json();
    username = me?.result?.username || '';
  } catch (_) { /* не критично */ }

  return json({ ok: true, username });
});
