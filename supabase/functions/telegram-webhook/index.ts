// Telegram-бот (Фаза 4.1): текстові витрати/доходи, привʼязка кодом, /balance, /last.
// Викликається Telegram без JWT (config.toml: verify_jwt = false), захист:
// заголовок X-Telegram-Bot-Api-Secret-Token + whitelist chat_id у profiles.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN')!;
const WEBHOOK_SECRET = Deno.env.get('TELEGRAM_WEBHOOK_SECRET')!;

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

const HELP =
  'Формат: сума і опис, наприклад\n' +
  '250 кава\n' +
  '+51000 зарплата (плюс = дохід)\n\n' +
  '/balance: баланс за місяць\n' +
  '/last: останні 5 записів';

// Відповідь у чат; помилки Telegram не валять обробку апдейту
async function reply(chatId: number, text: string) {
  try {
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
  } catch (e) {
    console.error('sendMessage failed:', e);
  }
}

const fmtMoney = (n: number) =>
  new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ₴';

// Сьогодні за Києвом у форматі YYYY-MM-DD (Edge Functions працюють в UTC)
function todayKyiv(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const get = (t: string) => parts.find((p) => p.type === t)!.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

async function linkByCode(chatId: number, code: string) {
  const { data: prof } = await sb
    .from('profiles')
    .select('id')
    .eq('telegram_link_code', code)
    .gt('telegram_link_expires', new Date().toISOString())
    .maybeSingle();
  if (!prof) {
    return reply(chatId, 'Код невірний або прострочений. Згенеруйте новий у застосунку (шестерня, «Код для Telegram»).');
  }
  // Один Telegram-чат належить одному профілю: відвʼязуємо від попереднього
  await sb.from('profiles').update({ telegram_chat_id: null }).eq('telegram_chat_id', chatId).neq('id', prof.id);
  const { error } = await sb
    .from('profiles')
    .update({ telegram_chat_id: chatId, telegram_link_code: null, telegram_link_expires: null })
    .eq('id', prof.id);
  if (error) {
    console.error('link update error:', error);
    return reply(chatId, 'Не вдалося привʼязати. Спробуйте ще раз.');
  }
  return reply(chatId, 'Привʼязано до акаунту. ' + HELP);
}

async function addTx(chatId: number, userId: string, updateId: number, sign: string, rawAmount: string, desc: string) {
  const amount = parseFloat(rawAmount.replace(',', '.'));
  if (!amount || amount <= 0) return reply(chatId, 'Сума має бути більша за нуль.');
  const type = sign === '+' ? 'income' : 'expense';
  // Telegram повторює апдейт, якщо не дочекався 200: дедуп по update_id
  const sourceId = 'tg:' + updateId;
  const { data: dup } = await sb.from('transactions').select('id').eq('source_id', sourceId).maybeSingle();
  if (dup) return;
  const { error } = await sb.from('transactions').insert({
    user_id: userId,
    amount,
    type,
    description: desc.trim(),
    source: 'telegram',
    source_id: sourceId,
    date: todayKyiv(),
  });
  if (error) {
    console.error('insert error:', error);
    return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
  }
  return reply(chatId, `✅ ${type === 'income' ? 'Дохід' : 'Витрата'}: ${fmtMoney(amount)}, ${desc.trim()}`);
}

async function balance(chatId: number) {
  const today = todayKyiv();
  const start = today.slice(0, 7) + '-01';
  const { data, error } = await sb
    .from('transactions')
    .select('amount,type')
    .gte('date', start)
    .lte('date', today);
  if (error || !data) return reply(chatId, 'Не вдалося порахувати.');
  let inc = 0, exp = 0;
  for (const t of data) (t.type === 'income' ? (inc += Number(t.amount)) : (exp += Number(t.amount)));
  return reply(chatId,
    `Місяць з ${start.slice(8, 10)}.${start.slice(5, 7)}\n` +
    `Доходи: ${fmtMoney(inc)}\nВитрати: ${fmtMoney(exp)}\nБаланс: ${fmtMoney(inc - exp)}`);
}

async function last(chatId: number) {
  const { data, error } = await sb
    .from('transactions')
    .select('amount,type,description,date,source')
    .order('date', { ascending: false })
    .order('created_at', { ascending: false })
    .limit(5);
  if (error || !data) return reply(chatId, 'Не вдалося отримати список.');
  if (!data.length) return reply(chatId, 'Записів ще немає.');
  const lines = data.map((t) => {
    const d = `${t.date.slice(8, 10)}.${t.date.slice(5, 7)}`;
    const s = t.source === 'mono' ? 'mono' : t.source === 'telegram' ? 'tg' : 'вручну';
    return `${d} ${t.type === 'income' ? '+' : '-'}${fmtMoney(Number(t.amount))} ${t.description || ''} (${s})`;
  });
  return reply(chatId, '📋 Останні:\n' + lines.join('\n'));
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method not allowed', { status: 405 });

  if (req.headers.get('X-Telegram-Bot-Api-Secret-Token') !== WEBHOOK_SECRET) {
    return new Response('forbidden', { status: 403 });
  }

  let update: any;
  try {
    update = await req.json();
  } catch {
    return new Response('bad json', { status: 400 });
  }

  // Далі завжди 200: інакше Telegram повторює той самий апдейт
  const msg = update?.message;
  const chatId: number | undefined = msg?.chat?.id;
  const text: string = (msg?.text || '').trim();
  if (!chatId || !text) return new Response('ignored');

  const startMatch = text.match(/^\/start(?:\s+(\d{6}))?$/);
  if (startMatch) {
    if (startMatch[1]) await linkByCode(chatId, startMatch[1]);
    else await reply(chatId, 'Щоб привʼязати акаунт, згенеруйте код у застосунку і надішліть: /start <код>');
    return new Response('ok');
  }

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('id')
    .eq('telegram_chat_id', chatId)
    .maybeSingle();
  if (profErr) {
    console.error('profile lookup error:', profErr);
    return new Response('ok');
  }
  if (!prof) {
    await reply(chatId, 'Доступ закритий. Згенеруйте код у застосунку і надішліть /start <код>.');
    return new Response('ok');
  }

  if (/^\/balance$/i.test(text)) await balance(chatId);
  else if (/^\/last$/i.test(text)) await last(chatId);
  else if (/^\/help$/i.test(text)) await reply(chatId, HELP);
  else {
    const m = text.match(/^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/s);
    if (m) await addTx(chatId, prof.id, Number(update.update_id) || 0, m[1], m[2], m[3]);
    else await reply(chatId, 'Не зрозумів. ' + HELP);
  }

  return new Response('ok');
});
