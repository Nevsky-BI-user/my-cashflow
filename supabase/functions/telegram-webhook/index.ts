// Telegram-бот (Фази 4.1, 4.2, 5.1): текстові витрати/доходи, /income з дедупом Monobank і /yes,
// фото чеків, привʼязка кодом, /balance, /last.
// Викликається Telegram без JWT (config.toml: verify_jwt = false), захист:
// заголовок X-Telegram-Bot-Api-Secret-Token + whitelist chat_id у profiles.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { debtBuckets, deriveAccounts, fixedPaid, freeToPayout, lastPayout, minSpendStatus, repayDate, unassignedAdj, type AccTx, type Snapshot } from '../_shared/budget.ts';

// Модель для чеків. Якщо дрібний друк читається погано: 'claude-sonnet-5-5' (дорожче)
const RECEIPT_MODEL = 'claude-haiku-4-5-20251001';
// Сильніша модель: одна повторна спроба для підозрілого результату Haiku (див. receiptSuspect)
const RECEIPT_MODEL_STRONG = 'claude-sonnet-5-5';
const RECEIPT_SYSTEM =
  'Розпізнай чек. Відповідай ТІЛЬКИ JSON без пояснень: ' +
  '{"has_total": true або false, "amount": число або null, "items_sum": число або null, ' +
  '"description": назва магазину або 2-3 слова, "date": "YYYY-MM-DD" або null, "readable": "good" або "poor"}. ' +
  'readable = "poor", якщо частина цифр розмита, обрізана або нечітка, інакше "good". ' +
  'has_total = true ЛИШЕ коли на фото є рядок підсумку чека (СУМА, До сплати, Разом, Всього, TOTAL), ' +
  'і тоді amount = саме це число з рядка підсумку. ' +
  'НІКОЛИ не сумуй позиції в amount: якщо рядка підсумку немає, повертай has_total: false, amount: null, ' +
  'а в items_sum клади суму видимих позицій (орієнтовно). ' +
  'Якщо фото кілька, це частини одного чека по порядку, підсумок зазвичай на останньому. ' +
  'Якщо це не чек: {"error": "коротко чому"}.';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN')!;
const WEBHOOK_SECRET = Deno.env.get('TELEGRAM_WEBHOOK_SECRET')!;
const CLAUDE_API_KEY = Deno.env.get('CLAUDE_API_KEY') || '';

const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

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
  'Фото чека: сума й магазин розпізнаються автоматично\n' +
  '/yes: підтвердити дохід, схожий на Monobank\n' +
  '/balance: баланс за місяць\n' +
  '/last: останні 5 записів\n\n' +
  'Рахунок: слово ощад, приват або готівка на початку чи в кінці опису (для фото: у підписі), ' +
  'наприклад «250 кава приват». Без слова витрата лишається без рахунку, бот спитає кнопками; ' +
  'дохід іде на рахунок зарплати. Операції Monobank приходять самі.';

// Відповідь у чат; помилки Telegram не валять обробку апдейту
// Постійна клавіатура під полем вводу: кнопки шлють звичайний текст, який роутер розуміє
const BTN = { balance: '💰 Баланс', last: '📋 Останні', income: '➕ Дохід', help: '❓ Допомога', yes: '✅ Так, додати', no: '✖ Скасувати' };
const MAIN_KB = {
  keyboard: [[{ text: BTN.balance }, { text: BTN.last }], [{ text: BTN.income }, { text: BTN.help }]],
  resize_keyboard: true,
  is_persistent: true,
};
const CONFIRM_KB = { keyboard: [[{ text: BTN.yes }, { text: BTN.no }]], resize_keyboard: true, one_time_keyboard: true };

async function reply(chatId: number, text: string, keyboard: unknown = MAIN_KB) {
  try {
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, reply_markup: keyboard }),
    });
  } catch (e) {
    console.error('sendMessage failed:', e);
  }
}

// Виклик методу Bot API без відповіді; помилки лише в лог
async function tgCall(method: string, body: Record<string, unknown>) {
  try {
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) console.error(method + ' failed:', r.status, (await r.text()).slice(0, 200));
  } catch (e) {
    console.error(method + ' failed:', e);
  }
}

// Рахунки операцій. Сімʼя спільна: активні рахунки обох без фільтра user_id.
// Рахунки Monobank (mono_account_id) для ручних операцій не пропонуються: їхні операції приходять з банку самі,
// інакше витрата задвоїться. Тому вони не потрапляють ні в слова-ключі, ні в кнопки, ні в callback
type Acc = { id: number; name: string; bank: string | null; kind: string; is_salary: boolean | null };
const BANK_WORDS: Record<string, string> = {
  'ощад': 'oschad', 'oschad': 'oschad', 'приват': 'privat', 'privat': 'privat',
  'моно': 'mono', 'mono': 'mono', 'monobank': 'mono', 'готівка': 'cash', 'кеш': 'cash', 'cash': 'cash',
};

async function activeAccounts(): Promise<Acc[]> {
  const { data, error } = await sb.from('accounts')
    .select('id,name,bank,kind,is_salary')
    .eq('active', true)
    .is('mono_account_id', null)
    .order('sort_order', { ascending: true })
    .order('id', { ascending: true });
  if (error) console.error('accounts lookup error:', error);
  return (data || []) as Acc[];
}

// Лише для доходів: рахунок, куди приходить зарплата, далі перший активний дебетовий.
// Для витрат рахунок за замовчуванням не підставляється (account_id = null, бот питає кнопками)
const defaultAccount = (accs: Acc[]): Acc | null =>
  accs.find((a) => a.is_salary === true) || accs.find((a) => a.kind === 'debit') || null;

// Слово-ключ рахунку: банк за словником, інакше початок назви рахунку (від 3 літер)
function matchWord(word: string, accs: Acc[]): Acc | null {
  const w = word.toLowerCase().replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');
  if (!w) return null;
  const bank = BANK_WORDS[w];
  if (bank) {
    const a = accs.find((x) => x.bank === bank || (bank === 'cash' && x.kind === 'cash'));
    if (a) return a;
  }
  if (w.length >= 3) return accs.find((x) => x.name.toLowerCase().startsWith(w)) || null;
  return null;
}

// Рахунок з тексту: перше або останнє слово; знайдене слово вирізається з опису.
// allowWhole: текст може складатися лише зі слова-ключа (підпис фото); для опису витрати так не можна
function pickAccount(text: string, accs: Acc[], allowWhole: boolean): { acc: Acc | null; rest: string; matched: boolean } {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length > (allowWhole ? 0 : 1)) {
    for (const i of words.length > 1 ? [0, words.length - 1] : [0]) {
      const a = matchWord(words[i], accs);
      if (a) {
        words.splice(i, 1);
        return { acc: a, rest: words.join(' '), matched: true };
      }
    }
  }
  return { acc: null, rest: text.trim(), matched: false };
}

async function resolveAccount(hint: string, allowWhole: boolean) {
  const accs = await activeAccounts();
  return { ...pickAccount(hint, accs, allowWhole), accs };
}

const fmtMoney = (n: number) =>
  new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ₴';

// Текст підтвердження запису: той самий для відповіді і для редагування після вибору рахунку
type TxView = { amount: number | string; type: string; description: string | null; receipt_parts?: string[] | null };
function txText(t: TxView, accName: string | null): string {
  const parts = t.receipt_parts && t.receipt_parts.length > 1 ? ` (чек із ${t.receipt_parts.length} фото)` : '';
  return `✅ ${t.type === 'income' ? 'Дохід' : 'Витрата'}: ${fmtMoney(Number(t.amount))}, ${t.description || ''}${parts}` +
    ` · ${accName || 'рахунок не вибрано. З якого рахунку?'}`;
}

// Inline-кнопки інших активних рахунків: callback_data acc:<txId>:<accountId> (до 64 байт)
function accKeyboard(txId: number, accs: Acc[], currentId: number | null) {
  const rows = accs
    .filter((a) => a.id !== currentId)
    .map((a) => [{ text: a.name, callback_data: `acc:${txId}:${a.id}` }]);
  return rows.length ? { inline_keyboard: rows } : null;
}

// Відповідь після запису. restoreKb: перед цим була CONFIRM_KB, тож спершу повертаємо MAIN_KB,
// а кнопки рахунків ідуть окремим повідомленням (одне повідомлення несе лише одну клавіатуру)
async function replyTx(
  chatId: number, txId: number, t: TxView, accountId: number | null,
  opts: { note?: string; restoreKb?: boolean; accs?: Acc[] } = {},
) {
  const accs = opts.accs || await activeAccounts();
  const name = accs.find((a) => a.id === accountId)?.name ?? null;
  const text = txText(t, name) + (opts.note ? '\n' + opts.note : '');
  const kb = accKeyboard(txId, accs, accountId);
  if (!kb) return reply(chatId, text);
  if (opts.restoreKb) {
    await reply(chatId, text);
    return reply(chatId, 'Змінити рахунок:', kb);
  }
  return reply(chatId, text, kb);
}

// Натискання кнопки рахунку: whitelist за chat_id, зміна account_id лише в записах із Telegram
async function onCallback(cq: any) {
  const cbId = String(cq?.id || '');
  if (!cbId) return;
  const answer = (text: string) => tgCall('answerCallbackQuery', { callback_query_id: cbId, text });
  try {
    const chatId: number | undefined = cq?.message?.chat?.id;
    const msgId: number | undefined = cq?.message?.message_id;
    if (!chatId || !msgId) return answer('Повідомлення недоступне');
    const { data: prof, error: profErr } = await sb.from('profiles').select('id').eq('telegram_chat_id', chatId).maybeSingle();
    if (profErr) {
      console.error('callback profile lookup error:', profErr);
      return answer('Помилка, спробуйте ще раз');
    }
    if (!prof) return answer('Доступ закритий');
    const m = String(cq?.data || '').match(/^acc:(\d+):(\d+)$/);
    if (!m) return answer('Невідома дія');
    const txId = Number(m[1]), accId = Number(m[2]);
    const accs = await activeAccounts();
    const acc = accs.find((a) => a.id === accId);
    if (!acc) return answer('Рахунок недоступний');
    const { data: rows, error: upErr } = await sb.from('transactions')
      .update({ account_id: accId })
      .eq('id', txId)
      .eq('source', 'telegram')
      .select('id,amount,type,description,receipt_parts');
    if (upErr) {
      console.error('callback update error:', upErr);
      return answer('Не вдалося змінити рахунок');
    }
    if (!rows || !rows.length) return answer('Операцію не знайдено');
    await answer(`Рахунок: ${acc.name}`);
    const kb = accKeyboard(txId, accs, accId);
    await tgCall('editMessageText', {
      chat_id: chatId, message_id: msgId, text: txText(rows[0] as TxView, acc.name),
      ...(kb ? { reply_markup: kb } : {}),
    });
  } catch (e) {
    console.error('callback error:', (e as Error)?.message);
    await answer('Помилка, спробуйте ще раз');
  }
}

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
    return reply(chatId, 'Код невірний або прострочений. Згенеруйте новий у застосунку (шестерня, «Код для Telegram»).', { remove_keyboard: true });
  }
  // Той самий whitelist, що в застосунку: бот належить лише сімейним акаунтам
  const { data: au } = await sb.auth.admin.getUserById(prof.id);
  if (!ALLOWED_EMAILS.includes((au?.user?.email || '').toLowerCase())) {
    console.error('link refused: email not in whitelist', prof.id);
    return reply(chatId, 'Доступ закритий.', { remove_keyboard: true });
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

// Дата з чека: лише валідна YYYY-MM-DD, не в майбутньому і не старша за 45 днів, інакше сьогодні за Києвом
function receiptDate(raw: unknown): string {
  const today = todayKyiv();
  if (typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return today;
  const d = new Date(raw + 'T00:00:00Z');
  if (isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== raw) return today;
  if (raw > today) return today;
  // Чек старший за 45 днів: найімовірніше модель помилилась у році, беремо сьогодні
  const ageDays = (Date.parse(today + 'T00:00:00Z') - d.getTime()) / 86400000;
  return ageDays > 45 ? today : raw;
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

// Claude vision однією моделлю: повертає розібраний JSON або null при помилці API
async function askReceipt(b64s: string[], model: string): Promise<any | null> {
  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model,
        max_tokens: 400,
        system: RECEIPT_SYSTEM,
        messages: [{
          role: 'user',
          content: [
            ...b64s.map((data) => ({ type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data } })),
            {
              type: 'text',
              text: b64s.length > 1
                ? `Розпізнай чек; це ${b64s.length} фото одного чека, підсумок на останньому`
                : 'Розпізнай чек',
            },
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

// Причина перечитати чек сильнішою моделлю або null: помилка чи немає жодної суми, нечітке фото,
// підсумок розходиться із сумою позицій більше ніж на max(1 ₴, 2 %), дата з чека не пройшла б receiptDate як є
function receiptSuspect(r: any): string | null {
  if (!r || r.error) return 'error';
  const amount = posNum(r.amount);
  const items = posNum(r.items_sum);
  if (amount === null && items === null) return 'no_amount';
  if (r.readable === 'poor') return 'poor';
  if (r.has_total === true && amount !== null && items !== null && Math.abs(items - amount) > Math.max(1, amount * 0.02)) {
    return 'sum_mismatch';
  }
  if (r.date != null && receiptDate(r.date) !== r.date) return 'date';
  return null;
}

// Відповідь придатна: є підсумок або (немає підсумку і є сума позицій)
function receiptValid(r: any): boolean {
  return !!r && !r.error && (posNum(r.amount) !== null || (r.has_total === false && posNum(r.items_sum) !== null));
}

// Каскад: Haiku; підозрілий результат одна спроба Sonnet на тих самих фото; беремо Sonnet, якщо валідний.
// Діє на кожен виклик, зокрема для частин довгого чека
async function recognizeReceipt(b64s: string[]): Promise<any | null> {
  const first = await askReceipt(b64s, RECEIPT_MODEL);
  const reason = receiptSuspect(first);
  if (!reason) return first;
  console.log('receipt escalate', reason);
  const strong = await askReceipt(b64s, RECEIPT_MODEL_STRONG);
  return receiptValid(strong) ? strong : first;
}

// Стан збирання частин довгого чека (profiles.telegram_pending з kind: 'receipt')
type ReceiptPart = { path: string; update_id: number };
type ReceiptPending = {
  kind: 'receipt';
  parts: ReceiptPart[];
  media_group_id?: string;
  description: string;
  date: string | null;
  items_sum: number | null;
  expires: string;
  account_id?: number | null; // рахунок з підпису першої частини або за замовчуванням
  account_name?: string | null;
};

const isLiveReceipt = (p: any): p is ReceiptPending =>
  !!p && p.kind === 'receipt' && Array.isArray(p.parts) && !!p.expires && Date.parse(p.expires) >= Date.now();

async function readPending(userId: string): Promise<any | null> {
  const { data, error } = await sb.from('profiles').select('telegram_pending').eq('id', userId).maybeSingle();
  if (error) console.error('pending lookup error:', error);
  return data?.telegram_pending ?? null;
}

const posNum = (v: unknown): number | null => {
  const n = Math.round(Number(typeof v === 'string' ? v.replace(/\s/g, '').replace(',', '.') : v) * 100) / 100;
  return isFinite(n) && n > 0 ? n : null;
};

async function addReceipt(
  chatId: number, userId: string, updateId: number, photos: any[], mediaGroupId?: string, caption?: string,
) {
  if (!CLAUDE_API_KEY) return reply(chatId, 'Розпізнавання чеків не налаштовано');
  const sourceId = tgSourceId(updateId);
  // Перевірка до завантаження і виклику Claude: повтор апдейту не коштує грошей
  if (await isDuplicate(sourceId)) return;
  // Частина без підсумку транзакції не створює: повтор апдейту ловимо по parts
  const pending0 = await readPending(userId);
  if (isLiveReceipt(pending0) && pending0.parts.some((x) => x.update_id === updateId)) return;

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

  // Продовження, якщо є живий receipt-pending, інакше нова перша частина
  const wasReceipt = isLiveReceipt(pending0);
  const parts: ReceiptPart[] = [...(wasReceipt ? pending0.parts : []), { path, update_id: updateId }];

  const b64s: string[] = [];
  for (const part of parts) {
    if (part.path === path) { b64s.push(toBase64(bytes)); continue; }
    const { data: blob, error: dlErr } = await sb.storage.from('receipts').download(part.path);
    if (dlErr || !blob) {
      console.error('storage download error:', dlErr);
      return reply(chatId, 'Не вдалося прочитати попередню частину чека. Спробуйте /no і надішліть усі фото знову.');
    }
    b64s.push(toBase64(new Uint8Array(await blob.arrayBuffer())));
  }

  const res = await recognizeReceipt(b64s);
  if (!res) return reply(chatId, '❌ Не вдалося розпізнати: сервіс недоступний, спробуйте пізніше');
  if (res.error) return reply(chatId, '❌ Не вдалося розпізнати: ' + String(res.error));

  const description = (typeof res.description === 'string' && res.description.trim()) || 'Чек';
  const total = res.has_total === true ? posNum(res.amount) : null;

  // Рахунок: слово-ключ у підписі фото переозначає; інакше рахунок першої частини чи за замовчуванням
  const accs = await activeAccounts();
  const cap = caption && caption.trim() ? pickAccount(caption, accs, true) : null;
  let accountId: number | null;
  if (cap?.matched) accountId = cap.acc?.id ?? null;
  else if (wasReceipt && pending0.account_id !== undefined) accountId = pending0.account_id ?? null;
  else accountId = null; // чек це витрата: рахунок за замовчуванням не підставляємо
  const accountName = accs.find((a) => a.id === accountId)?.name ?? (wasReceipt ? pending0.account_name ?? null : null);

  if (total === null) {
    // Підсумку на фото немає: чекаємо наступну частину, транзакцію не створюємо
    const itemsSum = posNum(res.items_sum);
    const state: ReceiptPending = {
      kind: 'receipt',
      parts,
      ...(mediaGroupId ? { media_group_id: mediaGroupId } : {}),
      description,
      date: typeof res.date === 'string' ? res.date : null,
      items_sum: itemsSum,
      expires: new Date(Date.now() + PENDING_TTL_MS).toISOString(),
      account_id: accountId,
      account_name: accountName,
    };
    let saved = false;
    if (!wasReceipt) {
      // Умовний запис: закриває гонку двох майже одночасних апдейтів альбому
      const { data: upd, error: e1 } = await sb.from('profiles')
        .update({ telegram_pending: state }).eq('id', userId).is('telegram_pending', null).select('id');
      if (e1) console.error('receipt pending save error:', e1);
      saved = !!(upd && upd.length);
      if (!saved) {
        // Хтось уже записав pending: якщо це живий receipt, дописуємо свою частину до нього
        const cur = await readPending(userId);
        if (isLiveReceipt(cur) && !cur.parts.some((x) => x.update_id === updateId)) {
          state.parts = [...cur.parts, { path, update_id: updateId }];
        }
      }
    }
    if (!saved) {
      const { error: e2 } = await sb.from('profiles').update({ telegram_pending: state }).eq('id', userId);
      if (e2) {
        console.error('receipt pending save error:', e2);
        return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
      }
    }
    const sumPart = itemsSum ? ` (позицій на ≈ ${fmtMoney(itemsSum)})` : '';
    return reply(chatId,
      `📄 Частина чека без підсумку${sumPart}. Нічого не записано. ` +
      'Надішліть наступне фото з рядком «СУМА», або /yes щоб записати як є, або /no щоб скасувати. Чекаю 10 хв.');
  }

  const { data: ins, error } = await sb.from('transactions').insert({
    user_id: userId,
    amount: total,
    type: 'expense',
    description,
    source: 'telegram',
    source_id: sourceId,
    receipt_url: parts[0].path,
    receipt_parts: parts.length > 1 ? parts.map((x) => x.path) : null,
    date: receiptDate(res.date),
    account_id: accountId,
  }).select('id').single();
  if (error) {
    if (error.code === '23505') return; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('receipt insert error:', error);
    return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
  }
  if (wasReceipt) {
    const { error: clrErr } = await sb.from('profiles').update({ telegram_pending: null }).eq('id', userId);
    if (clrErr) console.error('pending clear error:', clrErr);
  }
  categorizeLater(ins.id);
  return replyTx(chatId, ins.id, {
    amount: total, type: 'expense', description, receipt_parts: parts.length > 1 ? parts.map((x) => x.path) : null,
  }, accountId, { accs });
}

// Відкладений запис для /yes: profiles.telegram_pending, TTL 10 хв
const PENDING_TTL_MS = 10 * 60 * 1000;
type Pending = {
  amount: number; type: string; description: string; date: string; source_id: string; expires?: string;
  account_id?: number | null; account_name?: string | null; // рахунок операції (старі записи pending без нього)
};

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

// DESIGN.md п. 13: витрата, в описі якої є назва активного постійного платежу (уся назва або її перше слово
// від 5 літер; «комуналка», «комунальні» = платіж, що починається з «комунал»), закриває платіж місяця своєї дати,
// якщо цього місяця він ще не оплачений. Кілька різних збігів: не привʼязуємо (неоднозначно).
async function matchFixed(desc: string, date: string): Promise<{ id: number; name: string } | null> {
  const d = String(desc || '').toLowerCase();
  if (!d.trim()) return null;
  const { data, error } = await sb.from('fixed_payments').select('id,name,type,active').eq('active', true);
  if (error) {
    console.error('fixed lookup error:', error);
    return null;
  }
  const hits = (data || []).filter((f) => {
    if (f.type === 'income') return false;
    const n = String(f.name || '').toLowerCase().trim();
    if (!n) return false;
    if (d.includes(n)) return true;
    const w = n.split(/\s+/)[0];
    if ([...w].length >= 5 && d.includes(w)) return true;
    return /комунал/.test(d) && n.startsWith('комунал');
  });
  if (hits.length !== 1) return null;
  const f = hits[0];
  const mo = date.slice(0, 7);
  const [y, m] = mo.split('-').map(Number);
  const next = m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`;
  const { data: paid, error: pe } = await sb.from('transactions').select('id').eq('fixed_id', f.id).eq('type', 'expense')
    .gte('date', mo + '-01').lt('date', next).limit(1);
  if (pe) {
    console.error('fixed paid lookup error:', pe);
    return null;
  }
  return paid && paid.length ? null : { id: Number(f.id), name: String(f.name) };
}

// Вставка запису з Telegram і відповідь у чат.
// Повертає true, якщо запис у базі (вставлено або вже був по source_id)
async function insertTx(chatId: number, userId: string, p: Pending, restoreKb = false): Promise<boolean> {
  const accs = await activeAccounts();
  // pending, збережений до появи рахунків: дохід іде на рахунок зарплати, витрата без рахунку
  const accountId = p.account_id !== undefined ? p.account_id ?? null : p.type === 'income' ? defaultAccount(accs)?.id ?? null : null;
  const fx = p.type === 'expense' ? await matchFixed(p.description, p.date) : null;
  const { data: ins, error } = await sb.from('transactions').insert({
    user_id: userId,
    amount: p.amount,
    type: p.type,
    description: p.description,
    source: 'telegram',
    source_id: p.source_id,
    date: p.date,
    account_id: accountId,
    fixed_id: fx ? fx.id : null,
  }).select('id').single();
  if (error) {
    if (error.code === '23505') return true; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('insert error:', error);
    await reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
    return false;
  }
  categorizeLater(ins.id);
  const note = fx ? `зараховано як оплату: ${fx.name} за ${MONTH_ACC[Number(p.date.slice(5, 7)) - 1]}` : undefined;
  await replyTx(chatId, ins.id, { amount: p.amount, type: p.type, description: p.description }, accountId, { accs, restoreKb, note });
  return true;
}

async function addTx(chatId: number, userId: string, updateId: number, type: 'income' | 'expense', rawAmount: string, desc: string) {
  const amount = parseFloat(rawAmount.replace(',', '.'));
  if (!amount || amount <= 0) return reply(chatId, 'Сума має бути більша за нуль.');
  const sourceId = tgSourceId(updateId);
  if (await isDuplicate(sourceId)) return;
  // Слово-ключ рахунку на початку чи в кінці опису вирізається з нього
  const r = await resolveAccount(desc, false);
  // Дохід без слова-ключа іде на рахунок зарплати; витрата без нього лишається без рахунку (кнопки під відповіддю)
  const acc = r.acc ?? (type === 'income' ? defaultAccount(r.accs) : null);
  const p: Pending = {
    amount, type, description: r.rest, date: todayKyiv(), source_id: sourceId,
    account_id: acc?.id ?? null, account_name: acc?.name ?? null,
  };

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
        `⚠️ Схожий дохід уже є від Monobank (${fmtMoney(mono.amount)}, ${ddmm(mono.date)}). Додати все одно?`, CONFIRM_KB);
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
  const p = data?.telegram_pending as Pending | ReceiptPending | null;
  if (!p || !p.expires || Date.parse(p.expires) < Date.now()) {
    if (p) await sb.from('profiles').update({ telegram_pending: null }).eq('id', userId);
    return reply(chatId, 'Немає що підтверджувати.');
  }
  if ((p as any).kind === 'receipt') {
    const rp = p as ReceiptPending;
    if (!rp.items_sum || rp.items_sum <= 0 || !rp.parts?.length) {
      return reply(chatId, 'У цієї частини чека немає суми. Надішліть фото з підсумком або /no.');
    }
    const accs = await activeAccounts();
    const rpAccount = rp.account_id !== undefined ? rp.account_id ?? null : null;
    const { data: ins, error: rErr } = await sb.from('transactions').insert({
      user_id: userId,
      amount: rp.items_sum,
      type: 'expense',
      description: rp.description || 'Чек',
      source: 'telegram',
      source_id: tgSourceId(rp.parts[rp.parts.length - 1].update_id),
      receipt_url: rp.parts[0].path,
      receipt_parts: rp.parts.length > 1 ? rp.parts.map((x) => x.path) : null,
      date: receiptDate(rp.date),
      account_id: rpAccount,
    }).select('id').single();
    if (rErr && rErr.code !== '23505') {
      console.error('receipt confirm insert error:', rErr);
      return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
    }
    await sb.from('profiles').update({ telegram_pending: null }).eq('id', userId);
    if (ins) {
      categorizeLater(ins.id);
      return replyTx(chatId, ins.id, {
        amount: rp.items_sum, type: 'expense', description: rp.description || 'Чек',
        receipt_parts: rp.parts.length > 1 ? rp.parts.map((x) => x.path) : null,
      }, rpAccount, { accs, note: 'Записано за сумою позицій: підсумку на фото не було.' });
    }
    return;
  }
  // source_id з відкладеного запису: дедуп по update_id лишається в силі
  // Перед /yes була CONFIRM_KB: відповідь повертає MAIN_KB, кнопки рахунків окремим повідомленням
  const ok = await insertTx(chatId, userId, p as Pending, true);
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
  const month =
    `Місяць з ${start.slice(8, 10)}.${start.slice(5, 7)}\n` +
    `Доходи: ${fmtMoney(inc)}\nВитрати: ${fmtMoney(exp)}\nБаланс: ${fmtMoney(inc - exp)}`;
  // Блок «Вільно до виплати»: помилка в ньому не ховає підсумок місяця
  let free = '';
  try {
    free = await freeBlock(today);
  } catch (e) {
    console.error('balance: free block failed', (e as Error)?.message);
  }
  return reply(chatId, free ? month + '\n\n' + free : month);
}

const fmtNum = (n: number) => new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 0 }).format(Math.round(n));
const fmtInt = (n: number) => fmtNum(n) + ' ₴';
// Місяць після «за» (знахідний відмінок збігається з називним)
const MONTH_ACC = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень'];

// «Вільно до виплати» за правилом білої і кредитної картки (DESIGN.md), спільна логіка в _shared/budget.ts
async function freeBlock(today: string): Promise<string> {
  const [acc, fix, cred, sal] = await Promise.all([
    sb.from('accounts').select('id,name,kind,balance,debt,debt_month,active,mono_account_id,balance_updated_at,min_spend,min_spend_fee')
      .eq('active', true).order('sort_order', { ascending: true }).order('id', { ascending: true }),
    sb.from('fixed_payments').select('id,name,amount,day_of_month,type,active,credit_ok,variable').eq('active', true),
    sb.from('credits').select('name,monthly_amount,payment_day,start_year,start_month,total_payments,credit_ok,source'),
    sb.from('salary_config').select('rate,split_day,advance_day,salary_day,savings_pct').order('id').limit(1).maybeSingle(),
  ]);
  if (acc.error || fix.error || cred.error || sal.error || !sal.data) throw new Error('budget data lookup failed');
  // Похідний баланс ручних рахунків: операції з account_id після balance_updated_at (deriveAccounts)
  const manual = (acc.data || []).filter((a) => !a.mono_account_id && a.balance_updated_at);
  const since = Math.min(...manual.map((a) => Date.parse(a.balance_updated_at)).filter((t) => !isNaN(t)));
  // Той самий запит дає й витрати поточного місяця для порогу мінімальних витрат (п. 11): операції місяця,
  // записані до звірки балансу, теж мають рахуватись. Зайві рядки deriveAccounts відсіює міткою created_at.
  const monthStart = today.slice(0, 7) + '-01';
  let atQ = sb.from('transactions').select('account_id,type,amount,created_at,date').not('account_id', 'is', null);
  atQ = isFinite(since) ? atQ.or(`created_at.gte."${new Date(since).toISOString()}",date.gte.${monthStart}`) : atQ.gte('date', monthStart);
  const { data: at, error: atErr } = await atQ;
  if (atErr) throw new Error('account tx lookup failed');
  const accTx = (at || []) as AccTx[];
  const accounts = deriveAccounts(acc.data || [], accTx);
  const minSpend = minSpendStatus(accounts, accTx.filter((t) => String(t.date || '') <= today), today);
  // Операції без рахунку (п. 9): віднімаються від власних, доки не розподілені; ті, що створені до мітки балансу, не рахуємо.
  // Нагадування: витрати з бота й застосунку без рахунку за 60 днів
  const lowerMs = Math.min(isFinite(since) ? since : Infinity, Date.now() - 60 * 86_400_000);
  const { data: ua, error: uaErr } = await sb.from('transactions')
    .select('account_id,type,amount,created_at,source,date')
    .is('account_id', null)
    .gte('created_at', new Date(lowerMs).toISOString());
  if (uaErr) throw new Error('unassigned lookup failed');
  const unTx = (ua || []) as (AccTx & { date: string })[];
  const unassigned = isFinite(since) ? unassignedAdj(unTx, since) : 0;
  const from60 = shiftDate(today, -60);
  const lost = unTx.filter((t) => t.type !== 'income' && (t.source === 'telegram' || t.source === 'manual') && t.date >= from60);
  const lostSum = lost.reduce((s, t) => s + (Number(t.amount) || 0), 0);
  const snap: Snapshot = { accounts, fixed: fix.data || [], credits: cred.data || [], salary: sal.data };

  // Витрати поточного періоду: від останньої виплати до сьогодні (як у застосунку)
  const from = lastPayout(snap.salary, today).date;
  const { data: tx, error: txErr } = await sb
    .from('transactions')
    .select('amount')
    .neq('type', 'income')
    .gte('date', from)
    .lte('date', today);
  if (txErr) throw new Error('spent lookup failed');
  const spent = (tx || []).reduce((s, t) => s + (Number(t.amount) || 0), 0);
  // п. 13: постійний платіж, оплачений операцією з fixed_id у своєму місяці, з обовʼязкових цього місяця зникає
  const { data: fp, error: fpErr } = await sb.from('transactions').select('fixed_id,type,amount,created_at,date')
    .not('fixed_id', 'is', null).gte('date', from.slice(0, 7) + '-01');
  if (fpErr) throw new Error('fixed paid lookup failed');
  snap.paid = fixedPaid((fp || []) as AccTx[]);

  const r = freeToPayout(snap, today, spent, unassigned, minSpend);
  const kind = r.nextPayout.kind === 'advance' ? 'аванс' : 'зарплата';
  const due = ddmm(r.nextPayout.date);
  // Кредитка: борг і найближча дата погашення (24-те наступного місяця після місяця боргу, DESIGN.md п. 12)
  const repayOf = (a: (typeof accounts)[number]) => {
    const ds = debtBuckets(a, today).map((b) => repayDate(b[0], today)).sort();
    return ds.length ? `, закрити до ${ddmm(ds[0])}` : '';
  };
  const accLine = 'Рахунки: ' + accounts
    .map((a) => `${a.name} ${a.kind === 'credit' ? 'борг ' + fmtInt(Number(a.debt) || 0) + repayOf(a) : fmtInt(Number(a.balance) || 0)}`)
    .join(' · ');
  let out = accLine + '\n' + `Вільно до виплати: ${fmtInt(r.freeNow)} (${kind} ${due}) · на день ${fmtInt(r.perDay)}`;
  // Каса напередодні виплати (DESIGN.md п. 12): усі білі платежі, комісії й погашення кредиток до дати виплати вже враховані
  out += `\nДо виплати ${due} (${r.daysToPayout} дн.): каса ${fmtInt(r.cashBeforePayout)}`;
  if (r.shortage > 0) out += `\nБракує ${fmtInt(r.shortage)} на білі платежі до ${due}`;
  // Поріг мінімальних витрат за місяць (п. 11): «Ощадбанк: витрачено 1 763 з 15 000 за жовтень, ще 13 237 до 31.10, інакше комісія 400 ₴»
  for (const m of r.minSpend) {
    const a = accounts.find((x) => Number(x.id) === m.accountId);
    const [y, mo] = m.month.split('-').map(Number);
    const end = `${String(new Date(Date.UTC(y, mo, 0)).getUTCDate()).padStart(2, '0')}.${String(mo).padStart(2, '0')}`;
    out += `\n${a?.name || 'Рахунок'}: витрачено ${fmtNum(m.spent)} з ${fmtNum(m.min)} за ${MONTH_ACC[mo - 1]}, ` +
      (m.left > 0 ? `ще ${fmtNum(m.left)} до ${end}, інакше комісія ${fmtInt(m.fee)}` : `поріг ${fmtNum(m.min)} досягнуто`);
  }
  if (lost.length) {
    out += `\n⚠️ Без рахунку: ${lost.length} ${lost.length === 1 ? 'операція' : lost.length < 5 ? 'операції' : 'операцій'} ` +
      `на ${fmtInt(lostSum)}, виберіть рахунок під повідомленнями або в застосунку`;
  }
  return out;
}

async function last(chatId: number) {
  const { data, error } = await sb
    .from('transactions')
    .select('amount,type,description,date,source,account_id')
    .order('date', { ascending: false })
    .order('created_at', { ascending: false })
    .limit(5);
  if (error || !data) return reply(chatId, 'Не вдалося отримати список.');
  if (!data.length) return reply(chatId, 'Записів ще немає.');
  // Назви рахунків (і неактивних): помилка лише прибирає назву з дужок
  const { data: accRows, error: accErr } = await sb.from('accounts').select('id,name');
  if (accErr) console.error('last: accounts lookup error:', accErr);
  const accName = new Map((accRows || []).map((a) => [a.id, a.name]));
  const lines = data.map((t) => {
    const d = `${t.date.slice(8, 10)}.${t.date.slice(5, 7)}`;
    const s = t.source === 'mono' ? 'mono' : t.source === 'telegram' ? 'tg' : 'вручну';
    const an = t.account_id != null ? accName.get(t.account_id) : null;
    return `${d} ${t.type === 'income' ? '+' : '-'}${fmtMoney(Number(t.amount))} ${t.description || ''} (${s}${an ? ', ' + an : ''})`;
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
  // Кнопки рахунку під відповіддю: окремий тип апдейту без message
  if (update?.callback_query) {
    await onCallback(update.callback_query);
    return new Response('ok');
  }

  const msg = update?.message;
  const chatId: number | undefined = msg?.chat?.id;
  const text: string = (msg?.text || '').trim();
  const photos: any[] | null = Array.isArray(msg?.photo) && msg.photo.length ? msg.photo : null;
  if (!chatId || (!text && !photos)) return new Response('ignored');

  const startMatch = text.match(/^\/start(?:\s+(\d{6}))?$/);
  if (startMatch) {
    if (startMatch[1]) await linkByCode(chatId, startMatch[1]);
    else await reply(chatId, 'Щоб привʼязати акаунт, згенеруйте код у застосунку і надішліть: /start <код>', { remove_keyboard: true });
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
    await reply(chatId, 'Доступ закритий. Згенеруйте код у застосунку і надішліть /start <код>.', { remove_keyboard: true });
    return new Response('ok');
  }

  // Фото чека: лише для привʼязаних профілів (whitelist вище)
  if (photos) {
    await addReceipt(chatId, prof.id, Number(update.update_id) || 0, photos,
      msg?.media_group_id ? String(msg.media_group_id) : undefined,
      typeof msg?.caption === 'string' ? msg.caption : undefined);
    return new Response('ok');
  }

  const updateId = Number(update.update_id) || 0;
  let m: RegExpMatchArray | null;
  if (/^\/balance$/i.test(text) || text === BTN.balance) await balance(chatId);
  else if (/^\/last$/i.test(text) || text === BTN.last) await last(chatId);
  else if (/^\/help$/i.test(text) || text === BTN.help) await reply(chatId, HELP);
  else if (/^\/yes$/i.test(text) || text === BTN.yes) await confirmPending(chatId, prof.id);
  else if (/^\/no$/i.test(text) || text === BTN.no) {
    await sb.from('profiles').update({ telegram_pending: null }).eq('id', prof.id);
    await reply(chatId, 'Скасовано.');
  } else if (text === BTN.income) await reply(chatId, 'Напишіть суму й опис, наприклад:\n+51000 зарплата');
  else if ((m = text.match(/^\/(income|дохід)\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) {
    await addTx(chatId, prof.id, updateId, 'income', m[2], m[3]);
  } else {
    m = text.match(/^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/s);
    if (m) await addTx(chatId, prof.id, updateId, m[1] === '+' ? 'income' : 'expense', m[2], m[3]);
    else await reply(chatId, 'Не зрозумів. ' + HELP);
  }

  return new Response('ok');
});
