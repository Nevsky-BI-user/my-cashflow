// Telegram-бот (Фази 4.1, 4.2, 5.1): текстові витрати/доходи, /income з дедупом Monobank і /yes,
// фото чеків, привʼязка кодом, /balance, /last.
// Викликається Telegram без JWT (config.toml: verify_jwt = false), захист:
// заголовок X-Telegram-Bot-Api-Secret-Token + whitelist chat_id у profiles.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Модель для чеків. Якщо дрібний друк читається погано: 'claude-sonnet-5-5' (дорожче)
const RECEIPT_MODEL = 'claude-haiku-4-5-20251001';
const RECEIPT_SYSTEM =
  'Розпізнай чек. Відповідай ТІЛЬКИ JSON без пояснень: ' +
  '{"amount": число (загальна сума до сплати), "description": назва магазину або 2-3 слова, ' +
  '"date": "YYYY-MM-DD" або null}. Якщо це не чек: {"error": "коротко чому"}.';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN')!;
const WEBHOOK_SECRET = Deno.env.get('TELEGRAM_WEBHOOK_SECRET')!;
const CLAUDE_API_KEY = Deno.env.get('CLAUDE_API_KEY') || '';

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

// Автокатегоризація у фоні: результат не чекаємо, помилки не валять webhook
function categorizeLater(id: number) {
  const p = fetch(`${SUPABASE_URL}/functions/v1/categorize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${SERVICE_ROLE}` },
    body: JSON.stringify({ transaction_id: id }),
  }).catch((e) => console.error('categorize call failed:', e));
  // Без waitUntil фонове завдання може обірватись після відповіді
  const wait = (globalThis as any).EdgeRuntime?.waitUntil;
  if (wait) wait(p);
}

const HELP =
  'Формат: сума і опис, наприклад\n' +
  '250 кава\n' +
  '+51000 зарплата (плюс = дохід)\n' +
  '/income 51000 зарплата (або /дохід): теж дохід\n\n' +
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

// Telegram повторює апдейт, якщо не дочекався 200: дедуп по update_id (текст і фото)
const tgSourceId = (updateId: number) => 'tg:' + updateId;

async function isDuplicate(sourceId: string): Promise<boolean> {
  const { data } = await sb.from('transactions').select('id').eq('source_id', sourceId).maybeSingle();
  return !!data;
}

// base64 без spread у String.fromCharCode: великі фото валили б стек
function toBase64(bytes: Uint8Array): string {
  let bin = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    const part = bytes.subarray(i, i + CHUNK);
    let s = '';
    for (let j = 0; j < part.length; j++) s += String.fromCharCode(part[j]);
    bin += s;
  }
  return btoa(bin);
}

// Дата з чека: лише валідна YYYY-MM-DD і не в майбутньому, інакше сьогодні за Києвом
function receiptDate(raw: unknown): string {
  const today = todayKyiv();
  if (typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return today;
  const d = new Date(raw + 'T00:00:00Z');
  if (isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== raw) return today;
  return raw > today ? today : raw;
}

// Стійкий розбір відповіді моделі: перший {...} з тексту
function extractJson(text: string): any | null {
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try {
    return JSON.parse(text.slice(start, end + 1));
  } catch {
    return null;
  }
}

// Завантаження фото з Telegram: getFile -> file_path -> байти
async function downloadTgFile(fileId: string): Promise<Uint8Array | null> {
  try {
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getFile?file_id=${encodeURIComponent(fileId)}`);
    const j = await r.json();
    const path = j?.result?.file_path;
    if (!j?.ok || !path) {
      console.error('getFile failed:', j?.description || r.status);
      return null;
    }
    const f = await fetch(`https://api.telegram.org/file/bot${BOT_TOKEN}/${path}`);
    if (!f.ok) {
      console.error('file download failed:', f.status);
      return null;
    }
    return new Uint8Array(await f.arrayBuffer());
  } catch (e) {
    console.error('telegram file error:', e);
    return null;
  }
}

// Claude vision: повертає розібраний JSON або null при помилці API
async function recognizeReceipt(b64: string): Promise<any | null> {
  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: RECEIPT_MODEL,
        max_tokens: 300,
        system: RECEIPT_SYSTEM,
        messages: [{
          role: 'user',
          content: [
            { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: b64 } },
            { type: 'text', text: 'Розпізнай чек' },
          ],
        }],
      }),
    });
    const j = await r.json();
    if (!r.ok) {
      console.error('claude error:', r.status, j?.error?.message || j);
      return null;
    }
    const text = (j?.content || [])
      .filter((c: any) => c?.type === 'text')
      .map((c: any) => c.text)
      .join('');
    const parsed = extractJson(text);
    if (!parsed) console.error('claude non-json reply:', text);
    return parsed ?? { error: 'відповідь не у форматі JSON' };
  } catch (e) {
    console.error('claude fetch error:', e);
    return null;
  }
}

async function addReceipt(chatId: number, userId: string, updateId: number, photos: any[]) {
  if (!CLAUDE_API_KEY) return reply(chatId, 'Розпізнавання чеків не налаштовано');
  const sourceId = tgSourceId(updateId);
  // Перевірка до завантаження і виклику Claude: повтор апдейту не коштує грошей
  if (await isDuplicate(sourceId)) return;

  // Останній елемент масиву photo: найбільший розмір
  const fileId: string | undefined = photos[photos.length - 1]?.file_id;
  if (!fileId) return reply(chatId, '❌ Не вдалося розпізнати: немає файлу');
  const bytes = await downloadTgFile(fileId);
  if (!bytes) return reply(chatId, 'Не вдалося отримати фото з Telegram. Спробуйте ще раз.');

  // Шлях у bucket receipts: {user_id}/{timestamp}.jpg; у receipt_url зберігаємо саме його
  const path = `${userId}/${Date.now()}.jpg`;
  const { error: upErr } = await sb.storage
    .from('receipts')
    .upload(path, bytes, { contentType: 'image/jpeg', upsert: false });
  if (upErr) {
    console.error('storage upload error:', upErr);
    return reply(chatId, 'Не вдалося зберегти фото чека. Спробуйте ще раз.');
  }

  const res = await recognizeReceipt(toBase64(bytes));
  if (!res) return reply(chatId, '❌ Не вдалося розпізнати: сервіс недоступний, спробуйте пізніше');
  if (res.error) return reply(chatId, '❌ Не вдалося розпізнати: ' + String(res.error));

  const amount = Math.round(
    Number(typeof res.amount === 'string' ? res.amount.replace(/\s/g, '').replace(',', '.') : res.amount) * 100,
  ) / 100;
  if (!isFinite(amount) || amount <= 0) return reply(chatId, '❌ Не вдалося розпізнати: немає суми');
  const description = (typeof res.description === 'string' && res.description.trim()) || 'Чек';

  const { data: ins, error } = await sb.from('transactions').insert({
    user_id: userId,
    amount,
    type: 'expense',
    description,
    source: 'telegram',
    source_id: sourceId,
    receipt_url: path,
    date: receiptDate(res.date),
  }).select('id').single();
  if (error) {
    if (error.code === '23505') return; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('receipt insert error:', error);
    return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
  }
  categorizeLater(ins.id);
  return reply(chatId, `✅ ${fmtMoney(amount)}, ${description}`);
}

// Відкладений запис для /yes: profiles.telegram_pending, TTL 10 хв
const PENDING_TTL_MS = 10 * 60 * 1000;
type Pending = { amount: number; type: string; description: string; date: string; source_id: string; expires?: string };

const ddmm = (d: string) => `${d.slice(8, 10)}.${d.slice(5, 7)}`;

// Зсув дати YYYY-MM-DD на n днів (арифметика в UTC, без часових поясів)
function shiftDate(d: string, n: number): string {
  const t = new Date(d + 'T00:00:00Z');
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}

// Схожий дохід від Monobank: сума в межах 1% і дата в межах ±1 день.
// Помилка запиту не блокує запис: логуємо і вважаємо, що дубля немає
async function findMonoIncome(amount: number, date: string): Promise<{ amount: number; date: string } | null> {
  const { data, error } = await sb
    .from('transactions')
    .select('id,amount,date')
    .eq('source', 'mono')
    .eq('type', 'income')
    .gte('amount', amount * 0.99)
    .lte('amount', amount * 1.01)
    .gte('date', shiftDate(date, -1))
    .lte('date', shiftDate(date, 1))
    .order('date', { ascending: false })
    .limit(1);
  if (error) {
    console.error('mono dedup lookup error:', error);
    return null;
  }
  return data && data.length ? { amount: Number(data[0].amount), date: data[0].date } : null;
}

// Вставка запису з Telegram і відповідь у чат.
// Повертає true, якщо запис у базі (вставлено або вже був по source_id)
async function insertTx(chatId: number, userId: string, p: Pending): Promise<boolean> {
  const { data: ins, error } = await sb.from('transactions').insert({
    user_id: userId,
    amount: p.amount,
    type: p.type,
    description: p.description,
    source: 'telegram',
    source_id: p.source_id,
    date: p.date,
  }).select('id').single();
  if (error) {
    if (error.code === '23505') return true; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('insert error:', error);
    await reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
    return false;
  }
  categorizeLater(ins.id);
  await reply(chatId, `✅ ${p.type === 'income' ? 'Дохід' : 'Витрата'}: ${fmtMoney(p.amount)}, ${p.description}`);
  return true;
}

async function addTx(chatId: number, userId: string, updateId: number, type: 'income' | 'expense', rawAmount: string, desc: string) {
  const amount = parseFloat(rawAmount.replace(',', '.'));
  if (!amount || amount <= 0) return reply(chatId, 'Сума має бути більша за нуль.');
  const sourceId = tgSourceId(updateId);
  if (await isDuplicate(sourceId)) return;
  const p: Pending = { amount, type, description: desc.trim(), date: todayKyiv(), source_id: sourceId };

  // Дохід міг уже прийти з Monobank: не вставляємо, просимо підтвердження /yes
  if (type === 'income') {
    const mono = await findMonoIncome(amount, p.date);
    if (mono) {
      const { error } = await sb
        .from('profiles')
        .update({ telegram_pending: { ...p, expires: new Date(Date.now() + PENDING_TTL_MS).toISOString() } })
        .eq('id', userId);
      if (error) {
        console.error('pending save error:', error);
        return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
      }
      return reply(chatId,
        `⚠️ Схожий дохід уже є від Monobank (${fmtMoney(mono.amount)}, ${ddmm(mono.date)}). Додати все одно? /yes`);
    }
  }
  await insertTx(chatId, userId, p);
}

// /yes: вставити відкладений запис, якщо він є і не прострочений
async function confirmPending(chatId: number, userId: string) {
  const { data, error } = await sb.from('profiles').select('telegram_pending').eq('id', userId).maybeSingle();
  if (error) {
    console.error('pending lookup error:', error);
    return reply(chatId, 'Не вдалося прочитати. Спробуйте ще раз.');
  }
  const p = data?.telegram_pending as Pending | null;
  if (!p || !p.expires || Date.parse(p.expires) < Date.now()) {
    if (p) await sb.from('profiles').update({ telegram_pending: null }).eq('id', userId);
    return reply(chatId, 'Немає що підтверджувати.');
  }
  // source_id з відкладеного запису: дедуп по update_id лишається в силі
  const ok = await insertTx(chatId, userId, p);
  if (ok) {
    const { error: clrErr } = await sb.from('profiles').update({ telegram_pending: null }).eq('id', userId);
    if (clrErr) console.error('pending clear error:', clrErr);
  }
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
  const photos: any[] | null = Array.isArray(msg?.photo) && msg.photo.length ? msg.photo : null;
  if (!chatId || (!text && !photos)) return new Response('ignored');

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

  // Фото чека: лише для привʼязаних профілів (whitelist вище)
  if (photos) {
    await addReceipt(chatId, prof.id, Number(update.update_id) || 0, photos);
    return new Response('ok');
  }

  const updateId = Number(update.update_id) || 0;
  let m: RegExpMatchArray | null;
  if (/^\/balance$/i.test(text)) await balance(chatId);
  else if (/^\/last$/i.test(text)) await last(chatId);
  else if (/^\/help$/i.test(text)) await reply(chatId, HELP);
  else if (/^\/yes$/i.test(text)) await confirmPending(chatId, prof.id);
  else if ((m = text.match(/^\/(income|дохід)\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) {
    await addTx(chatId, prof.id, updateId, 'income', m[2], m[3]);
  } else {
    m = text.match(/^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/s);
    if (m) await addTx(chatId, prof.id, updateId, m[1] === '+' ? 'income' : 'expense', m[2], m[3]);
    else await reply(chatId, 'Не зрозумів. ' + HELP);
  }

  return new Response('ok');
});
