// Telegram-бот (Фази 4.1, 4.2, 5.1): текстові витрати/доходи, /income з дедупом Monobank і /yes,
// фото чеків, привʼязка кодом, /balance, /last; звіти Графік, Бюджет, Тиждень, Місяць і кнопка «Оплачено» під нагадуваннями.
// Викликається Telegram без JWT (config.toml: verify_jwt = false), захист:
// заголовок X-Telegram-Bot-Api-Secret-Token + whitelist chat_id у profiles.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { financeProjection, lastPayout, type AccTx } from '../_shared/budget.ts';
import { formatFinanceMessage } from '../_shared/finance-message.ts';
import { creditPaid, matchCredit } from '../_shared/creditmatch.ts';
import { loadFinance, type FinanceData } from '../_shared/bot-data.ts';
import {
  balanceSeries, budgetModel, chartCaption, formatBudget, formatMonth, formatWeek, monthModel, parsePaidCallback, payPlan, payRange, weekModel,
} from '../_shared/bot-reports.ts';
import { balanceChartSvg, donutSvg } from '../_shared/bot-charts.ts';
import { svgToPng } from '../_shared/render-png.ts';
import { APP_URL, KB_BTN, MAIN_KB } from '../_shared/bot-kb.ts';

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
// Telegram ID родини (секрет TELEGRAM_ALLOWED_IDS, через кому): їх пропускаємо без запиту в базу
const ALLOWED_TG_IDS = new Set((Deno.env.get('TELEGRAM_ALLOWED_IDS') || '').split(',').map((v) => Number(v.trim())).filter((v) => v > 0));
// Ліміт невдалих спроб коду з одного чату
const LINK_TRIES = 5;
const LINK_WINDOW_MS = 3600000;

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
  '/balance: баланс, картки, розстрочки\n' +
  '/chart: графік балансу, /budget: бюджет періоду, /week: тиждень, /month: місяць\n' +
  '/last: останні 5 записів\n\n' +
  'Рахунок: слово ощад, приват або готівка на початку чи в кінці опису (для фото: у підписі), ' +
  'наприклад «250 кава приват». Без слова витрата лишається без рахунку, бот спитає кнопками; ' +
  'дохід іде на рахунок зарплати. Операції Monobank приходять самі.';

// Відповідь у чат; помилки Telegram не валять обробку апдейту
// Постійна клавіатура під полем вводу: кнопки шлють звичайний текст, який роутер розуміє
// Основні кнопки: Баланс, Графік, Бюджет, Тиждень, Місяць (bot-kb.ts); /last, /help, /income лишаються командами без кнопок
const BTN = { ...KB_BTN, last: '📋 Останні', income: '➕ Дохід', help: '❓ Допомога', yes: '✅ Так, додати', no: '✖ Скасувати' };
const CONFIRM_KB = { keyboard: [[{ text: BTN.yes }, { text: BTN.no }]], resize_keyboard: true, one_time_keyboard: true };

async function reply(chatId: number, text: string, keyboard: unknown = MAIN_KB, html = false) {
  try {
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, reply_markup: keyboard, ...(html ? { parse_mode: 'HTML' } : {}) }),
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
    const pd = parsePaidCallback(String(cq?.data || ''));
    if (pd) return await onPaid(cq, chatId, msgId, prof.id, pd, answer);
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

// Невдалі спроби коду за останню годину; помилка бази не блокує родину, але й не рахується як успіх
async function linkTriesExceeded(chatId: number): Promise<boolean> {
  const since = new Date(Date.now() - LINK_WINDOW_MS).toISOString();
  const { count, error } = await sb.from('telegram_link_attempts').select('id', { count: 'exact', head: true })
    .eq('chat_id', chatId).gte('at', since);
  if (error) console.error('link attempts lookup error:', error);
  return (count || 0) >= LINK_TRIES;
}

// silent: чужому чату нічого не відповідаємо, щоб бот не виказував себе
async function linkByCode(chatId: number, code: string, silent = false) {
  if (await linkTriesExceeded(chatId)) {
    console.error('link refused: too many attempts', chatId);
    return silent ? undefined : reply(chatId, 'Забагато спроб. Спробуйте через годину.', { remove_keyboard: true });
  }
  const { data: prof } = await sb
    .from('profiles')
    .select('id')
    .eq('telegram_link_code', code)
    .gt('telegram_link_expires', new Date().toISOString())
    .maybeSingle();
  if (!prof) {
    await sb.from('telegram_link_attempts').insert({ chat_id: chatId });
    if (silent) return;
    return reply(chatId, 'Код невірний або прострочений. Згенеруйте новий у застосунку (шестерня, «Код для Telegram»).', { remove_keyboard: true });
  }
  // Той самий whitelist, що в застосунку: бот належить лише сімейним акаунтам
  const { data: au } = await sb.auth.admin.getUserById(prof.id);
  if (!ALLOWED_EMAILS.includes((au?.user?.email || '').toLowerCase())) {
    console.error('link refused: email not in whitelist', prof.id);
    await sb.from('telegram_link_attempts').insert({ chat_id: chatId });
    return silent ? undefined : reply(chatId, 'Доступ закритий.', { remove_keyboard: true });
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
// від 5 літер; «комуналка», «комунальні» = платіж, що починається з «комунал»), закриває платіж місяця своєї дати
// (тижневий: тижня пн-нд своєї дати), якщо за цей місяць чи тиждень він ще не оплачений. Кілька різних збігів:
// не привʼязуємо (неоднозначно).
async function matchFixed(desc: string, date: string): Promise<{ id: number; name: string; week: boolean } | null> {
  const d = String(desc || '').toLowerCase();
  if (!d.trim()) return null;
  const { data, error } = await sb.from('fixed_payments').select('id,name,type,active,period').eq('active', true);
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
  const [from, to] = paidRange(f.period === 'week', date);
  const { data: paid, error: pe } = await sb.from('transactions').select('id').eq('fixed_id', f.id).eq('type', 'expense')
    .gte('date', from).lt('date', to).limit(1);
  if (pe) {
    console.error('fixed paid lookup error:', pe);
    return null;
  }
  return paid && paid.length ? null : { id: Number(f.id), name: String(f.name), week: f.period === 'week' };
}

const addDays = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);

// Витрата за графіком розстрочки (сума, день, банк або назва): credit_id, платіж місяця закривається фактом
async function linkCredit(p: Pending, bank: string | null): Promise<number | null> {
  const [from, to] = paidRange(false, p.date);
  const [crs, linked] = await Promise.all([
    sb.from('credits').select('id,name,monthly_amount,payment_day,start_year,start_month,total_payments,source'),
    sb.from('transactions').select('credit_id,date,type').not('credit_id', 'is', null).gte('date', from).lt('date', to),
  ]);
  if (crs.error || linked.error) {
    console.error('credit match lookup error:', crs.error || linked.error);
    return null;
  }
  return matchCredit(crs.data || [], { amount: Number(p.amount), date: p.date, bank, description: p.description }, creditPaid(linked.data || []));
}

// Межі [від, до) періоду оплати постійного платежу для дати: місяць або тиждень пн-нд
function paidRange(week: boolean, date: string): [string, string] {
  const t = Date.parse(date + 'T00:00:00Z');
  if (week) {
    const mon = t - ((new Date(t).getUTCDay() + 6) % 7) * 86400000;
    return [new Date(mon).toISOString().slice(0, 10), new Date(mon + 7 * 86400000).toISOString().slice(0, 10)];
  }
  const [y, m] = date.slice(0, 7).split('-').map(Number);
  return [date.slice(0, 7) + '-01', m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`];
}

// Вставка запису з Telegram і відповідь у чат.
// Повертає true, якщо запис у базі (вставлено або вже був по source_id)
async function insertTx(chatId: number, userId: string, p: Pending, restoreKb = false): Promise<boolean> {
  const accs = await activeAccounts();
  // pending, збережений до появи рахунків: дохід іде на рахунок зарплати, витрата без рахунку
  const accountId = p.account_id !== undefined ? p.account_id ?? null : p.type === 'income' ? defaultAccount(accs)?.id ?? null : null;
  const fx = p.type === 'expense' ? await matchFixed(p.description, p.date) : null;
  const cr = p.type === 'expense' && !fx ? await linkCredit(p, accs.find((a) => a.id === accountId)?.bank ?? null) : null;
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
    credit_id: cr,
  }).select('id').single();
  if (error) {
    if (error.code === '23505') return true; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('insert error:', error);
    await reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
    return false;
  }
  categorizeLater(ins.id);
  const wk = fx && fx.week ? paidRange(true, p.date) : null;
  const note = fx ? `зараховано як оплату: ${fx.name} за ` + (wk ? `тиждень ${wk[0].slice(8, 10)}.${wk[0].slice(5, 7)}-${addDays(wk[1], -1).slice(8, 10)}.${addDays(wk[1], -1).slice(5, 7)}` : MONTH_ACC[Number(p.date.slice(5, 7)) - 1])
    : cr ? `зараховано як платіж розстрочки за ${MONTH_ACC[Number(p.date.slice(5, 7)) - 1]}` : undefined;
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

// Посилання на застосунок під статусом; постійна клавіатура лишається
const APP_KB = { inline_keyboard: [[{ text: '📱 Відкрити застосунок', url: APP_URL }]] };

async function balance(chatId: number) {
  const today = todayKyiv();
  let free: string;
  try {
    free = await freeBlock(today);
  } catch (e) {
    console.error('balance: free block failed', (e as Error)?.message);
    return reply(chatId, 'Не вдалося завантажити фінансовий стан. Спробуйте ще раз.', APP_KB);
  }
  return reply(chatId, free, APP_KB);
}

// Місяць після «за» (знахідний відмінок збігається з називним)
const MONTH_ACC = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень'];

// Повний набір потрібних операцій: сторінки зі стабільним порядком, без тихого ліміту 1000.
async function financeTransactions(from: string, today: string, since: number): Promise<AccTx[]> {
  const rows: AccTx[] = [];
  for (let page = 0; page < 100; page++) {
    let query = sb.from('transactions').select('id,account_id,category_id,fixed_id,credit_id,type,amount,created_at,date,source')
      .lte('date', today).order('id', { ascending: true }).range(page * 1000, page * 1000 + 999);
    query = Number.isFinite(since) ? query.or(`created_at.gt."${new Date(since).toISOString()}",date.gte.${from}`) : query.gte('date', from);
    const {data, error} = await query;
    if (error) throw new Error('finance transactions lookup failed');
    rows.push(...(data || []) as AccTx[]);
    if (!data || data.length < 1000) return rows;
  }
  throw new Error('finance transactions pagination limit');
}

// Погоджений план та прогноз каси: та сама чиста модель, що у застосунку.
async function freeBlock(today: string): Promise<string> {
  const [acc, fix, cred, sal, cats] = await Promise.all([
    sb.from('accounts').select('id,name,kind,balance,debt,credit_limit,debt_month,active,mono_account_id,balance_updated_at,min_spend,min_spend_fee')
      .eq('active', true).order('sort_order', { ascending: true }).order('id', { ascending: true }),
    sb.from('fixed_payments').select('id,name,amount,day_of_month,period,weekday,bank,type,active,credit_ok,variable,end_date').eq('active', true),
    sb.from('credits').select('id,name,monthly_amount,payment_day,start_year,start_month,total_payments,credit_ok,source'),
    // v153: усі колонки, з ними budget_manual (ручний бюджет періоду, міграція 30); до застосування міграції запит не падає
    sb.from('salary_config').select('*').order('id').limit(1).maybeSingle(),
    sb.from('categories').select('id,name,is_income,budget_limit,limit_abs,sort_order,group_id').order('id'),
  ]);
  if (acc.error || fix.error || cred.error || sal.error || cats.error) throw new Error('budget data lookup failed');
  const manual = (acc.data || []).filter((a) => !a.mono_account_id && a.balance_updated_at);
  const since = Math.min(...manual.map((a) => Date.parse(a.balance_updated_at)).filter((t) => !isNaN(t)));
  const from60 = shiftDate(today, -60);
  const periodStart = sal.data ? lastPayout(sal.data, today).date : today.slice(0, 7) + '-01';
  const from = [from60, periodStart, today.slice(0, 7) + '-01'].sort()[0];
  const transactions = await financeTransactions(from, today, since);
  const projection = financeProjection({accounts: acc.data || [], fixed: fix.data || [], credits: cred.data || [], salary: sal.data,
    categories: (cats.data || []).map(c => ({...c, type: c.is_income ? 'income' : 'expense'})), transactions},
    {asof: today, through: shiftDate(today, 90)});
  const lost = transactions.filter(t => t.account_id == null && t.type === 'expense' &&
    (t.source === 'telegram' || t.source === 'manual') && String(t.date || t.created_at).slice(0, 10) >= from60);
  // Залишок розстрочок: платежі з датою після сьогодні (сплачені за планом не рахуються), крім місяців, уже
  // оплачених фактом (витрата з credit_id у місяці платежу)
  const paidCr = new Set(transactions.filter((t) => t.type === 'expense' && t.credit_id != null)
    .map((t) => String(t.credit_id) + '|' + String(t.date || t.created_at).slice(0, 7)));
  const installments = (cred.data || []).map((c) => {
    const first = Number(c.start_year) * 12 + Number(c.start_month); // start_month з 0
    let n = 0, lastDate = '';
    for (let k = first; k < first + Number(c.total_payments); k++) {
      const y = Math.floor(k / 12), m = k % 12;
      const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
      const d = `${y}-${String(m + 1).padStart(2, '0')}-${String(Math.min(Number(c.payment_day), last)).padStart(2, '0')}`;
      lastDate = d;
      if (d > today && !paidCr.has(String(c.id) + '|' + d.slice(0, 7))) n++; // платіж у свій день вважається сплаченим за планом
    }
    return { name: String(c.name), n, amountCents: Math.round(Number(c.monthly_amount) * 100), lastDate };
  }).filter((i) => i.n > 0);
  return formatFinanceMessage(projection, {count: lost.length, amountCents: lost.reduce((sum, t) => sum + Math.round(Number(t.amount) * 100), 0)},
    installments) + await recentText();
}

// Сума з копійками для відповідей бота; оголошено тут, бо блок статусу (financeTransactions..recentText) тест виконує окремо
const fmtMoney = (n: number) =>
  new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ₴';

// Останні 5 операцій рядками: для статусу і для /last
async function recentLines(): Promise<string[] | null> {
  const { data, error } = await sb
    .from('transactions')
    .select('amount,type,description,date,source,account_id')
    .order('date', { ascending: false })
    .order('created_at', { ascending: false })
    .limit(5);
  if (error || !data) return null;
  // Назви рахунків (і неактивних): помилка лише прибирає назву з дужок
  const { data: accRows, error: accErr } = await sb.from('accounts').select('id,name');
  if (accErr) console.error('last: accounts lookup error:', accErr);
  const accName = new Map((accRows || []).map((a) => [a.id, a.name]));
  return data.map((t) => {
    const d = `${t.date.slice(8, 10)}.${t.date.slice(5, 7)}`;
    const an = t.account_id != null ? accName.get(t.account_id) : null;
    return `${d} · ${t.description || ''}: ${t.type === 'income' ? '+' : '-'}${fmtMoney(Number(t.amount))}${an ? ' (' + an + ')' : ''}`;
  });
}

async function recentText(): Promise<string> {
  const lines = await recentLines();
  return lines && lines.length ? '\n\nОстанні операції:\n' + lines.join('\n') : '';
}

async function last(chatId: number) {
  const lines = await recentLines();
  if (!lines) return reply(chatId, 'Не вдалося отримати список.');
  if (!lines.length) return reply(chatId, 'Записів ще немає.');
  return reply(chatId, '📋 Останні:\n' + lines.join('\n'));
}

// ---------- Звіти кнопок: Графік, Бюджет, Тиждень, Місяць ----------
// Картинка multipart-запитом sendPhoto; підпис фото до 1024 символів
async function sendPhoto(chatId: number, png: Uint8Array, caption: string, name: string): Promise<boolean> {
  try {
    const fd = new FormData();
    fd.append('chat_id', String(chatId));
    fd.append('caption', caption.slice(0, 1024));
    fd.append('reply_markup', JSON.stringify(MAIN_KB));
    fd.append('photo', new Blob([png as BlobPart], { type: 'image/png' }), name);
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendPhoto`, { method: 'POST', body: fd });
    if (!r.ok) console.error('sendPhoto failed:', r.status, (await r.text()).slice(0, 200));
    return r.ok;
  } catch (e) {
    console.error('sendPhoto failed:', e);
    return false;
  }
}

// Дані з тієї самої проєкції, що статус і застосунок; помилка завантаження або звіту дає коротку відповідь
async function withFinance(chatId: number, fn: (chatId: number, d: FinanceData) => Promise<unknown>) {
  let d: FinanceData;
  try {
    d = await loadFinance(sb, todayKyiv());
  } catch (e) {
    console.error('report: finance load failed', (e as Error)?.message);
    return reply(chatId, 'Не вдалося завантажити фінансовий стан. Спробуйте ще раз.');
  }
  try {
    await fn(chatId, d);
  } catch (e) {
    console.error('report failed', (e as Error)?.message);
    await reply(chatId, 'Не вдалося побудувати звіт. Спробуйте ще раз.');
  }
}

// 📈 Графік балансу від мінус місяця до плюс місяця; якщо картинка не вийшла, підпис надсилається текстом
async function chartReport(chatId: number, d: FinanceData) {
  const s = balanceSeries(d.projection, d.txs, d.accounts, d.today, { firstOwnDate: d.firstOwnDate, salary: d.salary });
  const caption = chartCaption(s);
  let png: Uint8Array | null = null;
  try {
    png = await svgToPng(balanceChartSvg(s).svg);
  } catch (e) {
    console.error('chart render failed', (e as Error)?.message);
  }
  if (!png || !(await sendPhoto(chatId, png, caption, 'balance.png'))) await reply(chatId, '📈 ' + caption);
}

// 📊 Бюджет: текст окремим повідомленням (підпис фото обмежений 1024 символами), потім кільце категорій
async function budgetReport(chatId: number, d: FinanceData) {
  const m = budgetModel(d.projection, d.txs, d.cats, d.today, d.input, d.accounts);
  await reply(chatId, formatBudget(m));
  if (!m || !m.rows.some((r) => r.fact > 0)) return;
  try {
    await sendPhoto(chatId, await svgToPng(donutSvg(m)), 'Витрати періоду за категоріями', 'budget.png');
  } catch (e) {
    console.error('donut render failed', (e as Error)?.message);
  }
}

// «✅ Оплачено» під нагадуванням: витрата з привʼязкою fixed_id або credit_id, як «Внести оплату» в застосунку.
// Повтор (друге натискання, інший член сімʼї, оплата вже внесена в застосунку) нового запису не дає:
// перевірка оплаченого періоду плюс унікальний source_id tgpaid:<тип>:<id>:<місяць або W понеділок>.
async function onPaid(cq: any, chatId: number, msgId: number, userId: string, p: { kind: 'f' | 'c'; id: string; date: string },
  answer: (text: string) => Promise<unknown>) {
  const fixed = p.kind === 'f';
  const q: any = fixed ? sb.from('fixed_payments').select('id,name,amount,period,bank,active,type') : sb.from('credits').select('id,name,monthly_amount,source');
  const { data: item, error } = await q.eq('id', Number(p.id)).maybeSingle();
  if (error) {
    console.error('paid: item lookup error:', error);
    return answer('Помилка, спробуйте ще раз');
  }
  if (!item || (fixed && (item.active === false || item.type === 'income'))) return answer('Платіж не знайдено');
  const col = fixed ? 'fixed_id' : 'credit_id';
  const [from, to] = payRange(fixed && item.period === 'week', p.date);
  const [recent, range, cats] = await Promise.all([
    sb.from('transactions').select('id,date,type,category_id,fixed_id,credit_id').eq(col, Number(p.id)).order('date', { ascending: false }).limit(50),
    sb.from('transactions').select('id,date,type,category_id,fixed_id,credit_id').eq(col, Number(p.id)).gte('date', from).lt('date', to),
    sb.from('categories').select('id,name,is_income'),
  ]);
  if (recent.error || range.error || cats.error) {
    console.error('paid: lookup error:', recent.error || range.error || cats.error);
    return answer('Помилка, спробуйте ще раз');
  }
  const head = String(cq?.message?.text || '').split('\n')[0];
  const plan = payPlan({ kind: p.kind, item, eventDate: p.date, today: todayKyiv(), history: [...(range.data || []), ...(recent.data || [])], cats: cats.data || [] });
  if (plan.status === 'already') {
    await answer(`Уже оплачено ${ddmm(plan.date)}`);
    return tgCall('editMessageText', { chat_id: chatId, message_id: msgId, text: `${head}\n✅ Уже оплачено ${ddmm(plan.date)}` });
  }
  // Рахунок за банком платежу (лише ручні рахунки, як у кнопках бота); без збігу бот питає рахунок кнопками
  const accs = await activeAccounts();
  const bank = fixed ? item.bank : item.source;
  const acc = bank ? accs.find((a) => a.bank === bank || (bank === 'cash' && a.kind === 'cash')) || null : null;
  const row = { ...plan.row, user_id: userId, account_id: acc?.id ?? null };
  const { data: ins, error: insErr } = await sb.from('transactions').insert(row).select('id').single();
  if (insErr) {
    if (insErr.code === '23505') {
      await answer('Уже оплачено');
      return tgCall('editMessageText', { chat_id: chatId, message_id: msgId, text: `${head}\n✅ Уже оплачено` });
    }
    console.error('paid: insert error:', insErr);
    return answer('Не вдалося записати оплату');
  }
  if (row.category_id == null) categorizeLater(ins.id);
  await answer('Оплату записано');
  await tgCall('editMessageText', {
    chat_id: chatId, message_id: msgId, text: `${head}\n✅ Оплачено, записано ${ddmm(row.date)}` + (acc ? ` · ${acc.name}` : ''),
  });
  if (!acc) await replyTx(chatId, ins.id, { amount: row.amount, type: 'expense', description: row.description }, null, { accs });
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
  // Сторожа: лише особисті чати; чужим Telegram ID нічого не відповідаємо
  const gateChat = update?.message?.chat || update?.callback_query?.message?.chat;
  const fromId = Number(update?.message?.from?.id || update?.callback_query?.from?.id || 0);
  if (!gateChat || gateChat.type !== 'private' || !fromId || Number(gateChat.id) !== fromId) return new Response('ignored');
  if (!ALLOWED_TG_IDS.has(fromId)) {
    // Не в списку: або вже привʼязаний профіль (новий член родини після коду), або лише /start <код>
    const { data: linked } = await sb.from('profiles').select('id').eq('telegram_chat_id', fromId).maybeSingle();
    if (!linked) {
      const code = String(update?.message?.text || '').trim().match(/^\/start\s+(\d{6})$/);
      if (code) await linkByCode(fromId, code[1], true);
      return new Response('ignored');
    }
  }

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
  else if (/^\/chart$/i.test(text) || text === BTN.chart) await withFinance(chatId, chartReport);
  else if (/^\/budget$/i.test(text) || text === BTN.budget) await withFinance(chatId, budgetReport);
  else if (/^\/week$/i.test(text) || text === BTN.week) await withFinance(chatId, (c, d) => reply(c, formatWeek(weekModel(d.projection, d.today)), MAIN_KB, true));
  else if (/^\/month$/i.test(text) || text === BTN.month) await withFinance(chatId, (c, d) => reply(c, formatMonth(monthModel(d.txs, d.cats, d.accounts, d.today))));
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
