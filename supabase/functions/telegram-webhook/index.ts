import { repaymentAdvice, repaymentAdviceText } from '../_shared/repayment.ts';
import { salaryOptions, salaryKeyboard, recordSalary } from '../_shared/salary-bot.ts';
import { fixedCandidates, fixedOccurrence, fixedOccurrenceKey } from '../_shared/fixedmatch.ts';
// Telegram-бот (Фази 4.1, 4.2, 5.1): текстові витрати/доходи, /income з дедупом Monobank і /yes,
// фото чеків, привʼязка кодом, /balance, /last; звіти Графік, Бюджет, Тиждень, Місяць і кнопка «Оплачено» під нагадуваннями.
// Викликається Telegram без JWT (config.toml: verify_jwt = false), захист:
// заголовок X-Telegram-Bot-Api-Secret-Token + whitelist chat_id у profiles.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { financeProjection, lastPayout, type AccTx } from '../_shared/budget.ts';
import { formatFinanceMessage } from '../_shared/finance-message.ts';
import { creditPaid, matchCredit } from '../_shared/creditmatch.ts';
import { loadFinance, loadMonthlyBudgets, type FinanceData } from '../_shared/bot-data.ts';
import {
  balanceSeries, budgetModel, chartCaption, formatBudget, formatMonth, formatWeek, monthModel, parsePaidCallback, payPlan, payRange, weekModel,
} from '../_shared/bot-reports.ts';
import { balanceChartSvg, donutSvg } from '../_shared/bot-charts.ts';
import { svgToPng } from '../_shared/render-png.ts';
import { APP_URL, KB_BTN, MAIN_KB, ENTRY_KB, ENTRY_INPUT_KB } from '../_shared/bot-kb.ts';

// Модель для чеків. Якщо дрібний друк читається погано: 'claude-sonnet-5-5' (дорожче)
const RECEIPT_MODEL = 'claude-haiku-4-5-20251001';
// Сильніша модель: одна повторна спроба для підозрілого результату Haiku (див. receiptSuspect)
const RECEIPT_MODEL_STRONG = 'claude-sonnet-5-5';
const RECEIPT_SYSTEM =
  'Розпізнай чек або скриншот операцій. Відповідай ТІЛЬКИ JSON без пояснень. ' +
  'Навіть ОДИН банківський переказ або дохід поверни як kind transactions з масивом transactions. Звичайний магазинний чек залишається витратою у форматі has_total. Напрямок визначай лише за зображенням. ' +
  'Якщо на ОДНОМУ зображенні кілька незалежних чеків або список банківських операцій, поверни ' +
  '{"kind":"transactions","complete":true,"readable":"good","transactions":[' +
  '{"amount":число,"type":"expense" або "income","currency":"UAH","description":"короткий опис","date":"YYYY-MM-DD" або null}]}. ' +
  'Включи ВСІ незалежні операції, максимум 20. amount завжди додатна, type визначай за напрямком платежу. ' +
  'НЕ включай баланс, підсумки списку, перекази між власними рахунками, очікувані/скасовані платежі чи товарні позиції одного чека. ' +
  'Не вгадуй валюту, суму чи напрямок. Якщо є нерозбірлива/обрізана операція, невідома валюта/напрямок, ' +
  'переказ між власними рахунками або понад 20 операцій — поверни {"error":"коротко чому"}, не повертай частину списку. ' +
  'Для одного звичайного чека збережи формат: ' +
  '{"has_total": true або false, "amount": число або null, "items_sum": число або null, ' +
  '"description": назва магазину або 2-3 слова, "date": "YYYY-MM-DD" або null, "readable": "good" або "poor"}. ' +
  'date — дата проведення саме цієї операції, видима на зображенні, зокрема в заголовку її групи. ' +
  'Для кожної операції поверни date_text: точний видимий напис дати, включно з днем тижня, або null. Успадковуй заголовок дати лише в межах його групи. ' +
  'Видимі «сьогодні»/«вчора» та дату без року сервер визначить відносно опорної дати повідомлення за Києвом. Не підміняй відсутню дату опорною; невідома дата — null. Повну історичну дату зберігай. ' +
  'Спільний заголовок вибраної картки стосується всіх операцій, якщо окрема операція не має інших явних ознак. Поверни спільні bank/card_last4/card_network також на верхньому рівні JSON; card_last4 — рівно чотири цифри рядком зі збереженими початковими нулями. ' +
  'Скриншот застосунку Ощад 24/7 визначає bank "oschad" для всіх операцій на ньому навіть без назви банку й номера картки. ' +
  'Його ознаки (досить двох): нижнє меню «Продукти», «Платежі», «Історія», «Ще»; картка «Аналітика за <місяць>» з «Надходження» і «Витрати»; ' +
  'фільтри «За місяць», «Всі операції», «Всі рахунки»; бірюзовий акцент; копійки й ₴ дрібним надрядковим шрифтом після суми; ' +
  'праворуч під сумою назва картки чи способу оплати (наприклад «Телефон»). Суми картки «Аналітика» це підсумки місяця, не операції. ' +
  'На такому скриншоті description = назва зверху рядка (магазин чи отримувач), а не категорія під нею («Покупка», «Продукти харчування») і не напис під сумою. ' +
  'Для кожної незалежної операції (і для одного чека) додай bank: "privat", "mono", "oschad" або null, ' +
  'card_last4: лише останні 4 цифри картки рядком або null, card_network: "visa", "mastercard" або null. ' +
  'Це банк і картка власника операції, НЕ банк отримувача чи термінала. Бери лише явно видимі ознаки; ' +
  'логотип VISA сам по собі не визначає банк. Невпевнені ознаки — null. Повний номер картки не повертай. ' +
  'readable = "poor", якщо частина цифр розмита, обрізана або нечітка, інакше "good". ' +
  'has_total = true ЛИШЕ коли на фото є рядок підсумку чека (СУМА, До сплати, Разом, Всього, TOTAL), ' +
  'і тоді amount = саме це число з рядка підсумку. ' +
  'НІКОЛИ не сумуй позиції в amount: якщо рядка підсумку немає, повертай has_total: false, amount: null, ' +
  'а в items_sum клади суму видимих позицій (орієнтовно). ' +
  'Якщо фото кілька, це частини одного чека по порядку, підсумок зазвичай на останньому. ' +
  'Кілька фото ЗАВЖДИ частини одного чека, не повертай kind transactions. ' +
  'Якщо це не чек і не список операцій: {"error": "коротко чому"}.';

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
  'Просто надішліть суму й опис або фото. Сума без знака — витрата, з плюсом — дохід. На зображенні напрямок визначається за самою операцією. Кнопки звітів згортаються після вибору; відкрити їх можна стандартною іконкою клавіатури Telegram.\n\n' +
  'Формат: сума і опис, наприклад\n' +
  '250 кава\n' +
  '+51000 зарплата (плюс = дохід)\n' +
  '/income 51000 зарплата (або /дохід): теж дохід\n\n' +
  'Фото чека: сума й магазин розпізнаються автоматично\n' +
  'Скриншот із кількома операціями: до 20 доходів/витрат у гривнях, кожна окремим записом і з вибором рахунку\n' +
  'Банк на скриншоті допоможе вибрати рахунок; якщо є сумнів, бот запропонує кнопки. Підпис фото має пріоритет.\n' +
  '/yes: підтвердити дохід, схожий на Monobank\n' +
  '/balance: баланс, картки, розстрочки\n' +
  '/chart: графік балансу, /budget: бюджет періоду, /week: тиждень, /month: місяць\n' +
  '/last: останні 5 записів\n\n' +
  'Рахунок: слово ощад, приват або готівка на початку чи в кінці опису (для фото: у підписі), ' +
  'наприклад «250 кава приват». Без слова витрата лишається без рахунку, бот спитає кнопками; ' +
  'дохід іде на рахунок зарплати. Операції Monobank приходять самі.';

// Відповідь у чат; помилки Telegram не валять обробку апдейту
// Клавіатура Telegram згортається після вибору; її кнопки шлють звичайний текст роутеру.
// Усі головні дії та кроки введення описані в спільному bot-kb.ts.
const BTN = { ...KB_BTN, no: 'Ні, не додавати' };
const CONFIRM_KB = { keyboard: [[{ text: BTN.yes }, { text: BTN.no }]], resize_keyboard: true, one_time_keyboard: true };

async function reply(chatId: number, text: string, keyboard: unknown = undefined, html = false) {
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
// інакше витрата задвоїться. Виняток — фото/скриншоти: банк може визначатися із зображення.
type Acc = { id: number; name: string; bank: string | null; kind: string; is_salary: boolean | null; card_last4?: string | null; active?: boolean };
const BANK_WORDS: Record<string, string> = {
  'ощад': 'oschad', 'oschad': 'oschad', 'приват': 'privat', 'privat': 'privat',
  'моно': 'mono', 'mono': 'mono', 'monobank': 'mono', 'готівка': 'cash', 'кеш': 'cash', 'cash': 'cash',
};

async function activeAccounts(includeMono = false): Promise<Acc[]> {
  let query = sb.from('accounts')
    .select('id,name,bank,kind,is_salary,card_last4')
    .eq('active', true);
  if (!includeMono) query = query.is('mono_account_id', null);
  const { data, error } = await query
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
    const matches = accs.filter((x) => x.bank === bank || (bank === 'cash' && x.kind === 'cash'));
    return matches.length === 1 ? matches[0] : null;
  }
  if (w.length >= 3) {
    const matches = accs.filter((x) => x.name.toLowerCase().startsWith(w));
    return matches.length === 1 ? matches[0] : null;
  }
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
  opts: { note?: string; restoreKb?: boolean; accs?: Acc[]; accountResolved?: boolean } = {},
) {
  const accs = opts.accs || await activeAccounts();
  const name = accs.find((a) => a.id === accountId)?.name ?? null;
  const text = txText(t, name) + (opts.note ? '\n' + opts.note : '');
  const accountKb = opts.accountResolved && name ? null : accKeyboard(txId, accs, accountId);
  const kb = accountKb || {inline_keyboard:[]};
  if(t.type==='expense')kb.inline_keyboard.push([{text:'Привʼязати обовʼязковий платіж',callback_data:`flpick:${txId}`}]);
  if (opts.restoreKb) {
    await reply(chatId, text, MAIN_KB);
    if (accountKb) await reply(chatId, 'Змінити рахунок:', kb);
    return;
  }
  if (!kb.inline_keyboard.length) return reply(chatId, text);
  return reply(chatId, text, kb);
}

// Натискання кнопки рахунку: whitelist за chat_id, зміна account_id лише в записах із Telegram
// Привʼязка збереженої витрати без зміни суми, рахунку та фактичної дати.
async function offerFixedLink(chatId:number,userId:string,txId?:number) {
  if(txId!=null){
    const {data:tx,error}=await sb.from('transactions').select('id,date,type,fixed_id,credit_id').eq('id',txId).eq('user_id',userId).maybeSingle();
    if(error||!tx||tx.type!=='expense'||tx.fixed_id!=null||tx.credit_id!=null)return reply(chatId,'Операцію не знайдено або її вже привʼязано.');
    const {fixed,paid}=await fixedContext();const buttons:any[]=[];
    for(const f of fixed){
      const seen=new Set<string>();let count=0;
      for(let k=0;k<=370&&count<3;k++){
        const reference=addDays(String(tx.date||todayKyiv()).slice(0,10),k),due=fixedOccurrence(f,reference);
        if(!due)continue;const key=fixedOccurrenceKey(f,due);
        if(seen.has(key)||paid.has(key))continue;seen.add(key);count++;
        buttons.push([{text:`${f.name} · ${due}`,callback_data:`fl:${txId}:${f.id}:${due}`}]);
      }
    }
    return reply(chatId,buttons.length?'Оберіть платіж і дату зобовʼязання:':'Неоплачених постійних платежів немає.',{inline_keyboard:buttons.slice(0,60)});
  }
  const {data,error}=await sb.from('transactions').select('id,date,description,amount').eq('user_id',userId).eq('type','expense').is('fixed_id',null).is('credit_id',null).order('date',{ascending:false}).limit(10);
  if(error)return reply(chatId,'Не вдалося прочитати операції.');
  return reply(chatId,'Оберіть витрату для привʼязки:',{inline_keyboard:(data||[]).map(t=>[{text:`${t.date} · ${t.description||'Витрата'} · ${fmtMoney(t.amount)}`,callback_data:`flpick:${t.id}`}])});
}
async function confirmFixedLink(chatId:number,userId:string,txId:number,fixedId:number,due:string,answer:(s:string)=>Promise<unknown>){
  const {data:tx,error}=await sb.from('transactions').select('id,type,fixed_id,credit_id').eq('id',txId).eq('user_id',userId).maybeSingle();
  if(error||!tx||tx.type!=='expense')return answer('Операцію не знайдено');
  if(tx.fixed_id!=null||tx.credit_id!=null)return answer('Операцію вже привʼязано');
  const {fixed,paid}=await fixedContext(),f=fixed.find(f=>Number(f.id)===fixedId);
  if(!f||fixedOccurrence(f,due)!==due)return answer('Некоректне зобовʼязання');
  if(paid.has(fixedOccurrenceKey(f,due)))return answer('Цей період уже оплачено');
  const {data:rows,error:err}=await sb.from('transactions').update({fixed_id:fixedId,payment_due_date:due}).eq('id',txId).eq('user_id',userId).eq('type','expense').is('fixed_id',null).is('credit_id',null).select('id');
  if(err||!rows?.length)return answer('Не вдалося привʼязати операцію');
  await answer('Привʼязано');return reply(chatId,`✅ ${f.name}: зараховано оплату за ${due}. Фактична дата витрати збережена.`);
}

async function offerSalary(chatId:number,explicit=false){
 const data=await salaryOptions(sb,todayKyiv());
 if(!data.choices.length){if(explicit)await reply(chatId,'Налаштуйте зарплатний рахунок, суми й дати виплат у застосунку.');return;}
 await reply(chatId,'Підтвердіть отриману виплату:',salaryKeyboard(data.choices));
}
async function onSalary(chatId:number,userId:string,parts:RegExpMatchArray,answer:(s:string)=>Promise<unknown>){
 const result=await recordSalary(sb,userId,todayKyiv(),parts[1]==='s'?'salary':'advance',parts[2],parts[3],parts[4]?Number(parts[4]):undefined);
 if(result.status==='invalid')return answer('Виплата недоступна або дата ще не настала');
 if(result.status==='already')return answer('Цю виплату вже враховано');
 if(result.status==='awaiting')return answer('Чекаємо надходження з Monobank');
 if(result.status==='choose'){
  await answer('Оберіть наявний дохід');
  return reply(chatId,'Є кілька однакових доходів. Оберіть виплату:',{inline_keyboard:result.rows.map((t:any)=>[{text:t.date+' · '+fmtMoney(t.amount),callback_data:'sal:'+parts[1]+':'+parts[2]+':'+parts[3]+':'+t.id}])});
 }
 await answer('Виплату враховано');
 await reply(chatId,'✅ '+(result.payout.kind==='salary'?'Зарплата':'Аванс')+': '+fmtMoney(result.payout.amount)+' · '+result.payout.accountName);
 const finance=await loadFinance(sb,todayKyiv()),advice=repaymentAdviceText(repaymentAdvice(finance.input,finance.projection,result.payout.accountId,todayKyiv()));
 if(advice)await reply(chatId,advice);
}

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
    const salary=String(cq?.data||'').match(/^sal:([sa]):(\d{4}-\d{2}-\d{2}):(\d+)(?::(\d+))?$/);
    if(salary)return onSalary(chatId,prof.id,salary,answer);
    const pick=String(cq?.data||'').match(/^flpick:(\d+)$/);
    if(pick){await answer('Оберіть зобовʼязання');return offerFixedLink(chatId,prof.id,Number(pick[1]));}
    const link=String(cq?.data||'').match(/^fl:(\d+):(\d+):(\d{4}-\d{2}-\d{2})$/);
    if(link)return confirmFixedLink(chatId,prof.id,Number(link[1]),Number(link[2]),link[3],answer);
    const pd = parsePaidCallback(String(cq?.data || ''));
    if (pd) return await onPaid(cq, chatId, msgId, prof.id, pd, answer);
    const m = String(cq?.data || '').match(/^acc:(\d+):(\d+)$/);
    if (!m) return answer('Невідома дія');
    const txId = Number(m[1]), accId = Number(m[2]);
    const { data: tx, error: txErr } = await sb.from('transactions').select('receipt_url').eq('id', txId).eq('source', 'telegram').maybeSingle();
    if (txErr) return answer('Помилка, спробуйте ще раз');
    if (!tx) return answer('Операцію не знайдено');
    const accs = await activeAccounts(!!tx.receipt_url);
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
    await tgCall('editMessageText', {
      chat_id: chatId, message_id: msgId, text: txText(rows[0] as TxView, acc.name),
      reply_markup: { inline_keyboard: [] },
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
  return reply(chatId, 'Привʼязано до акаунту. ' + HELP, MAIN_KB);
}

// Telegram повторює апдейт, якщо не дочекався 200: дедуп по update_id (текст і фото)
const tgSourceId = (updateId: number) => 'tg:' + updateId;

type EntryPending = { kind: 'entry'; type: 'income' | 'expense'; input: 'choose' | 'text' | 'image'; expires: string };
const liveEntry = (p: any): p is EntryPending => p?.kind === 'entry' && ['income','expense'].includes(p.type) &&
  ['choose','text','image'].includes(p.input) && typeof p.expires === 'string' && Number.isFinite(Date.parse(p.expires)) && Date.parse(p.expires) > Date.now();
// Порівнюємо весь попередній стан: застарілий апдейт не стирає нове підтвердження.
async function replacePending(userId: string, expected: any, next: any): Promise<boolean> {
  let q = sb.from('profiles').update({ telegram_pending: next }).eq('id', userId);
  q = expected == null ? q.is('telegram_pending', null) : q.eq('telegram_pending', JSON.stringify(expected));
  const { data, error } = await q.select('id');
  return !error && Array.isArray(data) && data.length === 1;
}
function entryKeyboard(p: EntryPending): unknown { return p.input === 'choose' ? ENTRY_KB : ENTRY_INPUT_KB; }
async function entryHint(chatId: number, p: EntryPending, prefix = '') {
  const kind = p.type === 'income' ? 'дохід' : 'витрату';
  const text = p.input === 'choose' ? `Як додати ${kind}? Оберіть спосіб.` : p.input === 'text'
    ? `Введіть суму й опис ${p.type === 'income' ? 'доходу, наприклад: 1500 повернення коштів' : 'витрати, наприклад: 250 кава'}.`
    : `Надішліть фото або скриншот, де видно ${kind}, суму й дату. ${p.type === 'income' ? 'На зображенні мають бути лише доходи.' : 'На зображенні мають бути лише витрати.'}`;
  await reply(chatId, prefix + text, entryKeyboard(p));
}

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

// Дата операції лише зі зображення: невідому дату не підміняємо сьогоднішньою.
function receiptDate(raw: unknown): string | null {
  if (typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const d = new Date(raw + 'T00:00:00Z');
  if (isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== raw || raw > todayKyiv()) return null;
  return raw;
}
const RECEIPT_DATE_REQUIRED = '❌ Не вдалося визначити дату операції. Нічого не записано. Надішліть скриншот або фото, де видно дату проведення кожної операції.';

// Опора стабільна при повторній доставці Telegram, з урахуванням київської півночі.
function receiptReference(timestamp?: number): string | null {
  if (!Number.isFinite(timestamp) || timestamp! <= 0) return null;
  const d = new Date(timestamp! * 1000);
  if (isNaN(d.getTime())) return null;
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

function receiptVisibleDate(raw: unknown, reference: string | null): string | null {
  if (typeof raw !== 'string') return null;
  let text = raw.trim().toLowerCase().replace(/[,]/g, ' ').replace(/\s+/g, ' ');
  const cap = reference && reference < todayKyiv() ? reference : todayKyiv();
  const checked = (date: string) => date <= cap ? receiptDate(date) : null;
  const weekdays = ['нд|неділя|неділю','пн|понеділок','вт|вівторок','ср|середа|середу','чт|четвер',"пт|п[’ʼ']ятниця|п[’ʼ']ятницю",'сб|субота|суботу'];
  let weekday = -1;
  for (let i = 0; i < weekdays.length; i++) {
    const prefix = new RegExp('^(?:' + weekdays[i] + ')\\.?\\s+');
    if (prefix.test(text)) { weekday = i; text = text.replace(prefix, ''); break; }
  }
  const finish = (date: string | null) => date && (weekday < 0 || new Date(date + 'T00:00:00Z').getUTCDay() === weekday) ? date : null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return finish(checked(text));
  if (text === 'сьогодні' || text === 'вчора') {
    if (!reference) return null;
    return finish(checked(new Date(Date.parse(reference + 'T00:00:00Z') - (text === 'вчора' ? 86400000 : 0)).toISOString().slice(0, 10)));
  }
  const months = ['січень|січня|січ','лютий|лютого|лют','березень|березня|бер','квітень|квітня|квіт','травень|травня|трав','червень|червня|черв','липень|липня|лип','серпень|серпня|серп','вересень|вересня|вер','жовтень|жовтня|жовт','листопад|листопада|лист','грудень|грудня|груд'];
  const words = text.match(/^(\d{1,2})\s+([а-яіїєґ]+)\.?(?:\s+(\d{4}|\d{2}))?$/);
  const numeric = text.match(/^(\d{1,2})([./])(\d{1,2})(?:\2(\d{4}|\d{2}))?$/);
  if (!words && !numeric) return null;
  const day = Number(words ? words[1] : numeric![1]);
  const month = words ? months.findIndex((names) => names.split('|').includes(words[2])) + 1 : Number(numeric![3]);
  const rawYear = words ? words[3] : numeric![4];
  if (!month || month > 12 || day < 1 || day > 31 || (!rawYear && !reference)) return null;
  if (rawYear?.length === 2 && !reference) return null;
  // Двозначний рік належить століттю опори; майбутнє не переносимо на 100 років назад.
  const year = rawYear ? Number(rawYear) + (rawYear.length === 2 ? Math.floor(Number(reference!.slice(0, 4)) / 100) * 100 : 0) : Number(reference!.slice(0, 4));
  for (let offset = 0; offset < (rawYear ? 1 : 9); offset++) {
    const date = `${String(year - offset).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const valid = checked(date);
    // Шукаємо календарний рік, а не підганяємо день тижня.
    if (valid) return finish(valid);
  }
  return null;
}

function normalizeReceipt(r: any, reference: string | null): any {
  if (!r || typeof r !== 'object') return r;
  const normalize = (t: any) => {
    if (!t || typeof t !== 'object') return t;
    // Видимий напис має пріоритет над припущенням моделі в date.
    const raw = Object.prototype.hasOwnProperty.call(t, 'date_text') ? t.date_text : t.date;
    // Відрізняємо відсутню дату від помилкового напису: останній не можна
    // замінювати датою попередньої частини довгого чека.
    return { ...t, date: receiptVisibleDate(raw, reference) ?? (raw == null ? null : '') };
  };
  if (!Array.isArray(r.transactions)) return normalize(r);
  return { ...r, transactions: r.transactions.map((t: any) => {
    if (!t || typeof t !== 'object') return t;
    const conflict = ['bank','card_last4','card_network'].some((k) => t[k] != null && r[k] != null && t[k] !== r[k]);
    const inherited = conflict ? t : { ...t, bank: t.bank ?? r.bank, card_last4: t.card_last4 ?? r.card_last4, card_network: t.card_network ?? r.card_network };
    return normalize(inherited);
  }) };
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
async function askReceipt(b64s: string[], model: string, reference: string | null): Promise<any | null> {
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
        max_tokens: 4096,
        system: RECEIPT_SYSTEM + (reference ? ` Опорна дата повідомлення (Europe/Kyiv): ${reference}.` : ' Опорна дата невідома; відносні дати та дати без року не визначай.'),
        messages: [{
          role: 'user',
          content: [
            ...b64s.map((data) => ({ type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data } })),
            {
              type: 'text',
              text: b64s.length > 1
                ? `Розпізнай чек; це ${b64s.length} фото одного чека, підсумок на останньому`
                : 'Розпізнай усі незалежні операції на зображенні або один чек',
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
    if (j?.stop_reason !== 'end_turn') return { error: 'Розпізнавання не завершено. Надішліть менший або чіткіший фрагмент.' };
    const text = (j?.content || [])
      .filter((c: any) => c?.type === 'text')
      .map((c: any) => c.text)
      .join('');
    const parsed = extractJson(text);
    if (!parsed) console.error('claude non-json reply');
    return normalizeReceipt(parsed, reference) ?? { error: 'відповідь не у форматі JSON' };
  } catch (e) {
    console.error('claude fetch error:', e);
    return null;
  }
}

// Причина перечитати чек сильнішою моделлю або null: помилка чи немає жодної суми, нечітке фото,
// підсумок розходиться із сумою позицій більше ніж на max(1 ₴, 2 %), дата з чека не пройшла б receiptDate як є
function receiptSuspect(r: any): string | null {
  if (!r || r.error) return 'error';
  if (r.kind === 'transactions' || 'transactions' in r) {
    if (!receiptBatch(r)) return 'invalid_batch';
    return null;
  }
  const amount = posNum(r.amount);
  const items = posNum(r.items_sum);
  if (amount === null && items === null) return 'no_amount';
  if (r.readable === 'poor') return 'poor';
  if (r.has_total === true && amount !== null && items !== null && Math.abs(items - amount) > Math.max(1, amount * 0.02)) {
    return 'sum_mismatch';
  }
  if (!receiptDate(r.date)) return 'date';
  return null;
}

// Відповідь придатна: є підсумок або (немає підсумку і є сума позицій)
function receiptValid(r: any): boolean {
  if (r && (r.kind === 'transactions' || 'transactions' in r)) return receiptBatch(r) !== null;
  return !!r && !r.error && (posNum(r.amount) !== null || (r.has_total === false && posNum(r.items_sum) !== null));
}

type ReceiptBankHint = { bank: 'privat' | 'mono' | 'oschad' | null; card_last4: string | null; card_network: 'visa' | 'mastercard' | null };
function receiptBankHint(r: any): ReceiptBankHint {
  return {
    bank: ['privat', 'mono', 'oschad'].includes(r?.bank) ? r.bank : null,
    card_last4: typeof r?.card_last4 === 'string' && /^\d{4}$/.test(r.card_last4) ? r.card_last4 : null,
    card_network: ['visa', 'mastercard'].includes(r?.card_network) ? r.card_network : null,
  };
}

// Лише однозначний збіг із налаштованим рахунком; невідому картку не підміняємо іншою.
function receiptAccount(r: any, accs: Acc[]): Acc | null {
  const hint = receiptBankHint(r);
  if (r?.card_last4 != null && hint.card_last4 === null) return null;
  let candidates = accs.filter((a) => a.active !== false && a.kind !== 'cash' && a.bank !== 'cash');
  if (hint.bank) candidates = candidates.filter((a) => a.bank === hint.bank);
  if (hint.card_last4) {
    candidates = candidates.filter((a) => a.card_last4 === hint.card_last4);
  } else if (!hint.bank) return null;
  return candidates.length === 1 ? candidates[0] : null;
}

type ReceiptTransaction = { amount: number; type: 'expense' | 'income'; description: string; date: string; hint: ReceiptBankHint };

type ReceiptRow = { amount: number | string; type: string; date: string; account_id: number | null; description: string | null };
const receiptDescription = (v: unknown) => String(v || '').normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
function sameReceiptOperation(a: ReceiptRow, b: ReceiptRow): boolean {
  return a.type === b.type && Math.round(Number(a.amount) * 100) === Math.round(Number(b.amount) * 100) &&
    Math.abs(Date.parse(a.date) - Date.parse(b.date)) <= 3 * 86400000 &&
    ((a.account_id != null && b.account_id != null && String(a.account_id) === String(b.account_id)) ||
      (!!receiptDescription(a.description) && receiptDescription(a.description) === receiptDescription(b.description)));
}

// Перевірка всіх джерел до INSERT. Неповний результат або помилка не означають відсутність дубля.
async function receiptDuplicate(rows: ReceiptRow[]): Promise<string | null> {
  const duplicate = (r: ReceiptRow, inside = false) =>
    `${inside ? 'На зображенні є схожі операції' : 'Схожа операція вже записана'}: ${r.date.split('-').reverse().join('.')}, ${fmtMoney(Number(r.amount))}. ` +
    'Збігаються сума, тип і рахунок або опис; дати відрізняються не більше ніж на 3 дні. Нічого не додано. Перевірте записи й надішліть лише нові операції.';
  for (let i = 0; i < rows.length; i++) {
    if (rows.slice(0, i).some((r) => sameReceiptOperation(rows[i], r))) return duplicate(rows[i], true);
  }
  const dates = rows.map((r) => r.date).sort();
  const shift = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
  const failure = 'Не вдалося перевірити, чи ці операції вже записані. Нічого не додано. Спробуйте пізніше.';
  try {
    for (let page = 0; page < 10; page++) {
      const { data, error } = await sb.from('transactions')
        .select('id,amount,type,date,account_id,description')
        .gte('date', shift(dates[0], -3)).lte('date', shift(dates[dates.length - 1], 3))
        .order('id', { ascending: true }).range(page * 1000, page * 1000 + 999);
      if (error || !Array.isArray(data)) return failure;
      for (const existing of data) {
        if (rows.some((r) => sameReceiptOperation(r, existing))) return duplicate(existing);
      }
      if (data.length < 1000) return null;
    }
  } catch {
    return failure;
  }
  return failure;
}

// Перевіряємо весь список до запису: жодної часткової імпортованої суми.
function receiptBatch(r: any): ReceiptTransaction[] | null {
  if (!r || r.error || r.kind !== 'transactions' || r.complete !== true || r.readable !== 'good' ||
    !Array.isArray(r.transactions) || r.transactions.length < 1 || r.transactions.length > 20) return null;
  const result: ReceiptTransaction[] = [];
  for (const t of r.transactions) {
    if (!t || typeof t.amount !== 'number' || !Number.isFinite(t.amount) || posNum(t.amount) === null ||
      !['expense', 'income'].includes(t.type) || t.currency !== 'UAH' ||
      typeof t.description !== 'string' || !t.description.trim() || t.description.length > 300 ||
      !receiptDate(t.date)) return null;
    // Некоректний номер не використовується для автоматичного вибору банку.
    const hint = receiptBankHint(t);
    if (t.card_last4 != null && hint.card_last4 === null) hint.bank = null;
    result.push({ amount: posNum(t.amount)!, type: t.type, description: t.description.trim(), date: t.date, hint });
  }
  return result;
}

// Каскад: Haiku; підозрілий результат одна спроба Sonnet на тих самих фото; беремо Sonnet, якщо валідний.
// Діє на кожен виклик, зокрема для частин довгого чека
async function recognizeReceipt(b64s: string[], reference: string | null = null): Promise<any | null> {
  const first = await askReceipt(b64s, RECEIPT_MODEL, reference);
  const reason = receiptSuspect(first);
  if (!reason) return first;
  console.log('receipt escalate', reason);
  const strong = await askReceipt(b64s, RECEIPT_MODEL_STRONG, reference);
  // Вже побачений список не можна тихо замінити одним чеком при повторній спробі.
  if (first && (first.kind === 'transactions' || 'transactions' in first)) {
    return receiptBatch(strong) ? strong : first;
  }
  return receiptValid(strong) ? strong : first;
}

// Стан збирання частин довгого чека (profiles.telegram_pending з kind: 'receipt')
type ReceiptPart = { path: string; update_id: number };
type ReceiptPending = {
  kind: 'receipt';
  parts: ReceiptPart[];
  reference?: string | null;
  media_group_id?: string;
  description: string;
  date: string | null;
  items_sum: number | null;
  expires: string;
  account_id?: number | null; // рахунок з підпису першої частини або за замовчуванням
  account_name?: string | null;
  account_resolved?: boolean;
};

const isLiveReceipt = (p: any): p is ReceiptPending =>
  !!p && p.kind === 'receipt' && Array.isArray(p.parts) && !!p.expires && Date.parse(p.expires) >= Date.now();

async function readPending(userId: string): Promise<any | null> {
  const { data, error } = await sb.from('profiles').select('telegram_pending').eq('id', userId).maybeSingle();
  if (error) throw new Error('pending lookup failed');
  return data?.telegram_pending ?? null;
}

const posNum = (v: unknown): number | null => {
  const n = Math.round(Number(typeof v === 'string' ? v.replace(/\s/g, '').replace(',', '.') : v) * 100) / 100;
  return isFinite(n) && n > 0 ? n : null;
};

async function addReceipt(
  chatId: number, userId: string, updateId: number, photos: any[], mediaGroupId?: string, caption?: string, messageDate?: number, entry?: EntryPending,
) {
  if (!CLAUDE_API_KEY) return reply(chatId, 'Розпізнавання чеків не налаштовано');
  const sourceId = tgSourceId(updateId);
  // Перевірка до завантаження і виклику Claude: повтор апдейту не коштує грошей
  if (await isDuplicate(sourceId)) return 'duplicate';
  // Частина без підсумку транзакції не створює: повтор апдейту ловимо по parts
  let pending0: any;
  try { pending0 = await readPending(userId); } catch { return reply(chatId, 'Не вдалося прочитати стан. Спробуйте ще раз.'); }
  if (entry && (!liveEntry(pending0) || JSON.stringify(pending0) !== JSON.stringify(entry))) return reply(chatId, 'Стан змінився. Оберіть дію знову.');
  if (!entry && pending0 && !isLiveReceipt(pending0)) return reply(chatId, 'Спочатку підтвердьте або скасуйте попередню дію.');
  if (isLiveReceipt(pending0) && pending0.parts.some((x) => x.update_id === updateId)) return 'duplicate';

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

  const reference = wasReceipt && pending0.reference !== undefined ? pending0.reference : receiptReference(messageDate);
  const res = await recognizeReceipt(b64s, reference);
  if (!res) return reply(chatId, '❌ Не вдалося розпізнати: сервіс недоступний, спробуйте пізніше');
  if (res.error) return reply(chatId, '❌ Не вдалося розпізнати: ' + String(res.error));
  if (entry) {
    const selected = receiptBatch(res);
    if (entry.type === 'income' && (!selected || selected.some((t) => t.type !== 'income'))) {
      return reply(chatId, 'На зображенні не вдалося підтвердити лише доходи з коректними датами. Нічого не записано.');
    }
    if (entry.type === 'expense' && (res.kind === 'transactions' || 'transactions' in res) && (!selected || selected.some((t) => t.type !== 'expense'))) {
      return reply(chatId, 'На зображенні не вдалося підтвердити лише витрати з коректними датами. Нічого не записано.');
    }
    if (entry.type === 'expense' && !(res.kind === 'transactions' || 'transactions' in res) && (res.has_total !== true || !posNum(res.amount))) {
      return reply(chatId, 'Потрібне фото цілого чека з підсумком і датою. Нічого не записано.');
    }
  }

  if (res.kind === 'transactions' || 'transactions' in res) {
    const batch = receiptBatch(res);
    if (wasReceipt) return reply(chatId, 'Зараз збирається один довгий чек. Завершіть його або надішліть /no, а потім скриншот операцій.');
    if (Array.isArray(res.transactions) && res.transactions.some((t: any) => !receiptDate(t?.date))) return reply(chatId, RECEIPT_DATE_REQUIRED);
    if (!batch) return reply(chatId, '❌ Не вдалося надійно прочитати всі операції. Нічого не записано. Надішліть чіткіший скриншот із максимум 20 операціями у гривнях.');
    const accs = await activeAccounts(true);
    const cap = caption?.trim() ? pickAccount(caption, accs, true) : null;
    const rows = batch.map((t, i) => ({
      amount: t.amount, type: t.type, description: t.description, date: t.date, user_id: userId, source: 'telegram',
      source_id: i === 0 ? sourceId : `${sourceId}:${i}`,
      receipt_url: path, receipt_parts: null,
      account_id: cap?.matched ? cap.acc?.id ?? null : receiptAccount(t.hint, accs)?.id ?? null,
    }));
    await linkReceiptRows(rows);
    const duplicate = await receiptDuplicate(rows);
    if (duplicate) return reply(chatId, duplicate);
    // Один INSERT — усі рядки разом або жодного; source_id захищає також конкурентний повтор.
    const { data: inserted, error } = await sb.from('transactions').insert(rows).select('id,source_id');
    if (error) {
      if (error.code === '23505') return 'duplicate';
      console.error('receipt batch insert error:', error);
      return reply(chatId, 'Не вдалося зберегти операції. Нічого не записано. Спробуйте ще раз.');
    }
    await reply(chatId, `✅ Записано операцій: ${rows.length}.`);
    for (const row of rows) {
      const tx = inserted?.find((t: any) => t.source_id === row.source_id);
      if (!tx) continue;
      categorizeLater(tx.id);
      await replyTx(chatId, tx.id, row, row.account_id, { accs, accountResolved: row.account_id != null });
    }
    return 'saved';
  }

  const description = (typeof res.description === 'string' && res.description.trim()) || 'Чек';
  const total = res.has_total === true ? posNum(res.amount) : null;
  // Попередня частина належить тому самому чеку; зберігаємо її дату, якщо нова частина дати не містить.
  const operationDate = receiptDate(res.date) ?? (wasReceipt && res.date == null ? receiptDate(pending0.date) : null);
  if (total !== null && !operationDate) return reply(chatId, RECEIPT_DATE_REQUIRED);

  // Рахунок: слово-ключ у підписі фото переозначає; інакше рахунок першої частини чи за замовчуванням
  const accs = await activeAccounts(true);
  const cap = caption && caption.trim() ? pickAccount(caption, accs, true) : null;
  let accountId: number | null;
  if (cap?.matched) accountId = cap.acc?.id ?? null;
  else if (wasReceipt && pending0.account_id !== undefined) accountId = pending0.account_id ?? null;
  else accountId = receiptAccount(res, accs)?.id ?? null;
  const accountResolved = accountId != null && (cap?.matched ? true : wasReceipt && pending0.account_id !== undefined ? pending0.account_resolved === true : true);
  const accountName = accs.find((a) => a.id === accountId)?.name ?? (wasReceipt ? pending0.account_name ?? null : null);

  if (total === null) {
    // Підсумку на фото немає: чекаємо наступну частину, транзакцію не створюємо
    const itemsSum = posNum(res.items_sum);
    const state: ReceiptPending = {
      kind: 'receipt',
      parts,
      reference,
      ...(mediaGroupId ? { media_group_id: mediaGroupId } : {}),
      description,
      date: operationDate,
      items_sum: itemsSum,
      expires: new Date(Date.now() + PENDING_TTL_MS).toISOString(),
      account_id: accountId,
      account_name: accountName,
      account_resolved: accountResolved,
    };
    const saved = await replacePending(userId, pending0, state);
    if (!saved) return reply(chatId, 'Не вдалося зберегти стан або інша дія вже змінила його. Спробуйте ще раз.');
    const sumPart = itemsSum ? ` (позицій на ≈ ${fmtMoney(itemsSum)})` : '';
    await reply(chatId,
      `📄 Частина чека без підсумку${sumPart}. Нічого не записано. ` +
      (itemsSum ? 'Надішліть наступне фото з рядком «СУМА» або натисніть «✅ Так, додати», щоб записати суму позицій. ' : 'Надішліть наступне фото з рядком «СУМА». ') +
      'Щоб завершити без запису, надішліть /no. Чекаю 10 хв.', itemsSum ? CONFIRM_KB : wasReceipt ? MAIN_KB : undefined);
    return 'pending';
  }

  const row = {
    user_id: userId,
    amount: total,
    type: 'expense',
    description,
    source: 'telegram',
    source_id: sourceId,
    receipt_url: parts[0].path,
    receipt_parts: parts.length > 1 ? parts.map((x) => x.path) : null,
    date: operationDate!,
    account_id: accountId,
  };
  await linkReceiptRows([row]);
  const duplicate = await receiptDuplicate([row]);
  if (duplicate) return reply(chatId, duplicate);
  const { data: ins, error } = await sb.from('transactions').insert(row).select('id').single();
  if (error) {
    if (error.code === '23505') return 'duplicate'; // повтор апдейту встиг пройти isDuplicate: мовчимо
    console.error('receipt insert error:', error);
    return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
  }
  if (wasReceipt) {
    if (!await replacePending(userId, pending0, null)) await reply(chatId, 'Запис збережено, але стан чека не вдалося очистити. Повторно його не додавайте.');
  }
  categorizeLater(ins.id);
  await replyTx(chatId, ins.id, {
    amount: total, type: 'expense', description, receipt_parts: parts.length > 1 ? parts.map((x) => x.path) : null,
  }, accountId, { accs, accountResolved, restoreKb: wasReceipt });
  return 'saved';
}

// Відкладений запис для /yes: profiles.telegram_pending, TTL 10 хв
const PENDING_TTL_MS = 10 * 60 * 1000;
type Pending = {
  amount: number; type: string; description: string; date: string; source_id: string; expires?: string;
  account_id?: number | null; account_name?: string | null; // рахунок операції (старі записи pending без нього)
  account_resolved?: boolean;
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
async function fixedContext() {
  const items=await sb.from('fixed_payments').select('id,name,type,active,period,weekday,day_of_month,month_of_year,end_date').eq('active',true);
  if(items.error)throw new Error('Не вдалося перевірити постійні платежі');
  const fixed=items.data||[],paid=new Set<string>();
  for(let page=0;page<100;page++){
    const history=await sb.from('transactions').select('id,fixed_id,type,date,created_at,payment_due_date').not('fixed_id','is',null).eq('type','expense').order('id').range(page*1000,page*1000+999);
    if(history.error)throw new Error('Не вдалося перевірити оплати');
    for(const t of history.data||[]){const f=fixed.find(f=>String(f.id)===String(t.fixed_id));if(f)paid.add(fixedOccurrenceKey(f,String(t.payment_due_date??t.date??t.created_at??'').slice(0,10)));}
    if(!history.data||history.data.length<1000)return {fixed,paid};
  }
  throw new Error('Перевищено ліміт історії оплат');
}
async function matchFixed(desc:string,date:string) {
  const {fixed,paid}=await fixedContext();
  const hits=fixedCandidates(fixed,desc,date,paid);
  if(hits.length!==1)return null;
  const f=hits[0];return {id:Number(f.id),name:f.name,week:f.period==='week',due:f.due};
}
async function linkReceiptRows(rows:any[]) {
  const {fixed,paid}=await fixedContext();
  for(const row of rows){
    if(row.type!=='expense')continue;
    const hits=fixedCandidates(fixed,row.description,row.date,paid);
    if(hits.length!==1)continue;
    const f=hits[0];row.fixed_id=Number(f.id);row.payment_due_date=f.due;paid.add(fixedOccurrenceKey(f,f.due));
  }
}

const addDays = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);

// Витрата за графіком розстрочки (сума, день, банк або назва): credit_id, платіж місяця закривається фактом
async function linkCredit(p: Pending, bank: string | null): Promise<number | null> {
  const [from, to] = paidRange(false, p.date);
  const [crs, linked] = await Promise.all([
    sb.from('credits').select('id,name,monthly_amount,payment_day,start_year,start_month,total_payments,source'),
    sb.from('transactions').select('credit_id,date,payment_due_date,type').not('credit_id', 'is', null).or(`and(payment_due_date.gte.${from},payment_due_date.lt.${to}),and(payment_due_date.is.null,date.gte.${from},date.lt.${to})`),
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
    payment_due_date: fx ? fx.due : null,
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
  await replyTx(chatId, ins.id, { amount: p.amount, type: p.type, description: p.description }, accountId, { accs, restoreKb, note, accountResolved: p.account_resolved === true });
  return true;
}

async function addTx(chatId: number, userId: string, updateId: number, type: 'income' | 'expense', rawAmount: string, desc: string, expected: any = null) {
  const amount = Number(rawAmount.replace(/\s/g, '').replace(',', '.'));
  if (!Number.isFinite(amount) || amount <= 0) return reply(chatId, 'Сума має бути більшою за нуль.');
  const sourceId = tgSourceId(updateId);
  if (await isDuplicate(sourceId)) return 'duplicate';
  // Слово-ключ рахунку на початку чи в кінці опису вирізається з нього
  const r = await resolveAccount(desc, false);
  // Дохід без слова-ключа іде на рахунок зарплати; витрата без нього лишається без рахунку (кнопки під відповіддю)
  const acc = r.acc ?? (type === 'income' ? defaultAccount(r.accs) : null);
  const p: Pending = {
    amount, type, description: r.rest, date: todayKyiv(), source_id: sourceId,
    account_id: acc?.id ?? null, account_name: acc?.name ?? null,
    account_resolved: r.matched && r.acc != null,
  };

  // Дохід міг уже прийти з Monobank: не вставляємо, просимо підтвердження /yes
  if (type === 'income') {
    const mono = await findMonoIncome(amount, p.date);
    if (mono) {
      if (!await replacePending(userId, expected, { ...p, expires: new Date(Date.now() + PENDING_TTL_MS).toISOString() })) {
        return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
      }
      await reply(chatId,
        `⚠️ Схожий дохід уже є від Monobank (${fmtMoney(mono.amount)}, ${ddmm(mono.date)}). Додати все одно?`, CONFIRM_KB);
      return 'pending';
    }
  }
  return await insertTx(chatId, userId, p) ? 'saved' : 'rejected';
}

// /yes: вставити відкладений запис, якщо він є і не прострочений
async function confirmPending(chatId: number, userId: string) {
  const { data, error } = await sb.from('profiles').select('telegram_pending').eq('id', userId).maybeSingle();
  if (error) {
    console.error('pending lookup error:', error);
    return reply(chatId, 'Не вдалося прочитати. Спробуйте ще раз.');
  }
  const p = data?.telegram_pending as Pending | ReceiptPending | null;
  if ((p as any)?.kind === 'entry') {
    if (liveEntry(p)) await entryHint(chatId, p, 'Тут немає операції для підтвердження. ');
    else await reply(chatId, 'Час введення минув. Надішліть суму й опис або фото знову.', MAIN_KB);
    return;
  }
  if (!p || !p.expires || Date.parse(p.expires) < Date.now()) {
    if (p && !await replacePending(userId, p, null)) return reply(chatId, 'Не вдалося очистити стан. Спробуйте ще раз.');
    return reply(chatId, 'Немає що підтверджувати.', p ? MAIN_KB : undefined);
  }
  if ((p as any).kind === 'receipt') {
    const rp = p as ReceiptPending;
    if (!rp.items_sum || rp.items_sum <= 0 || !rp.parts?.length) {
      return reply(chatId, 'У цієї частини чека немає суми. Надішліть фото з підсумком або /no.');
    }
    const operationDate = receiptDate(rp.date);
    if (!operationDate) return reply(chatId, RECEIPT_DATE_REQUIRED);
    const accs = await activeAccounts(true);
    const rpAccount = rp.account_id !== undefined ? rp.account_id ?? null : null;
    const duplicate = await receiptDuplicate([{
      amount: rp.items_sum!, type: 'expense', description: rp.description || 'Чек',
      date: operationDate, account_id: rpAccount,
    }]);
    if (duplicate) return reply(chatId, duplicate);
    const receiptLink:any={type:'expense',description:rp.description,date:operationDate};
    await linkReceiptRows([receiptLink]);
    const { data: ins, error: rErr } = await sb.from('transactions').insert({
      fixed_id:receiptLink.fixed_id??null,payment_due_date:receiptLink.payment_due_date??null,
      user_id: userId,
      amount: rp.items_sum,
      type: 'expense',
      description: rp.description || 'Чек',
      source: 'telegram',
      source_id: tgSourceId(rp.parts[rp.parts.length - 1].update_id),
      receipt_url: rp.parts[0].path,
      receipt_parts: rp.parts.length > 1 ? rp.parts.map((x) => x.path) : null,
      date: operationDate,
      account_id: rpAccount,
    }).select('id').single();
    if (rErr && rErr.code !== '23505') {
      console.error('receipt confirm insert error:', rErr);
      return reply(chatId, 'Не вдалося зберегти. Спробуйте ще раз.');
    }
    if (!await replacePending(userId, p, null)) await reply(chatId, 'Операція збережена, але стан не вдалося очистити. Не додавайте її повторно.');
    if (ins) {
      categorizeLater(ins.id);
      return replyTx(chatId, ins.id, {
        amount: rp.items_sum, type: 'expense', description: rp.description || 'Чек',
        receipt_parts: rp.parts.length > 1 ? rp.parts.map((x) => x.path) : null,
      }, rpAccount, { accs, restoreKb: true, accountResolved: rp.account_resolved === true, note: 'Записано за сумою позицій: підсумку на фото не було.' });
    }
    return;
  }
  // source_id з відкладеного запису: дедуп по update_id лишається в силі
  // Перед /yes була CONFIRM_KB: відповідь повертає MAIN_KB, кнопки рахунків окремим повідомленням
  const ok = await insertTx(chatId, userId, p as Pending, true);
  if (ok) {
    if (!await replacePending(userId, p, null)) await reply(chatId, 'Операція збережена, але стан не вдалося очистити. Не додавайте її повторно.');
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
    let query = sb.from('transactions').select('id,account_id,category_id,fixed_id,credit_id,payment_due_date,transfer_id,type,amount,created_at,date,source')
      .lte('date', today).order('id', { ascending: true }).range(page * 1000, page * 1000 + 999);
    query = Number.isFinite(since) ? query.or(`created_at.gt."${new Date(since).toISOString()}",date.gte.${from},payment_due_date.gte.${from}`) : query.or(`date.gte.${from},payment_due_date.gte.${from}`);
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
    sb.from('fixed_payments').select('id,name,amount,day_of_month,month_of_year,period,weekday,bank,type,active,credit_ok,variable,end_date').eq('active', true),
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
  const monthly_budgets=await loadMonthlyBudgets(sb);
  const projection = financeProjection({monthly_budgets,accounts: acc.data || [], fixed: fix.data || [], credits: cred.data || [], salary: sal.data,
    categories: (cats.data || []).map(c => ({...c, type: c.is_income ? 'income' : 'expense'})), transactions},
    {asof: today, through: shiftDate(today, 90)});
  const lost = transactions.filter(t => t.account_id == null && t.type === 'expense' &&
    (t.source === 'telegram' || t.source === 'manual') && String(t.date || t.created_at).slice(0, 10) >= from60);
  // Залишок розстрочок: платежі з датою після сьогодні (сплачені за планом не рахуються), крім місяців, уже
  // оплачених фактом (витрата з credit_id у місяці платежу)
  const paidCr = new Set(transactions.filter((t) => t.type === 'expense' && t.credit_id != null)
    .map((t) => String(t.credit_id) + '|' + String(t.payment_due_date ?? t.date ?? t.created_at).slice(0, 7)));
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
  const q: any = fixed ? sb.from('fixed_payments').select('id,name,amount,period,bank,active,type,day_of_month,weekday,month_of_year,end_date') : sb.from('credits').select('id,name,monthly_amount,source,payment_day,start_year,start_month,total_payments');
  const { data: item, error } = await q.eq('id', Number(p.id)).maybeSingle();
  if (error) {
    console.error('paid: item lookup error:', error);
    return answer('Помилка, спробуйте ще раз');
  }
  if (!item || (fixed && (item.active === false || item.type === 'income'))) return answer('Платіж не знайдено');
  if (fixed && fixedOccurrence(item,p.date)!==p.date) return answer('Некоректна дата зобовʼязання');
  if(!fixed){
    const [year,month,day]=p.date.split('-').map(Number),k=year*12+month-1,first=Number(item.start_year)*12+Number(item.start_month);
    const due=Math.min(Number(item.payment_day),new Date(Date.UTC(year,month,0)).getUTCDate());
    if(day!==due||k<first||k>=first+Number(item.total_payments))return answer('Некоректна дата зобовʼязання');
  }
  const col = fixed ? 'fixed_id' : 'credit_id';
  const [from, to] = payRange(fixed && item.period === 'week', p.date);
  const [recent, range, cats] = await Promise.all([
    sb.from('transactions').select('id,date,payment_due_date,type,category_id,fixed_id,credit_id').eq(col, Number(p.id)).order('date', { ascending: false }).limit(50),
    sb.from('transactions').select('id,date,payment_due_date,type,category_id,fixed_id,credit_id').eq(col, Number(p.id)).or(`and(payment_due_date.gte.${from},payment_due_date.lt.${to}),and(payment_due_date.is.null,date.gte.${from},date.lt.${to})`),
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
  if (!chatId) return new Response('ignored');

  const startMatch = text.match(/^\/start(?:\s+(\d{6}))?$/);
  if (startMatch?.[1]) {
    await linkByCode(chatId, startMatch[1]);
    return new Response('ok');
  }

  const { data: prof, error: profErr } = await sb
    .from('profiles')
    .select('id,telegram_pending')
    .eq('telegram_chat_id', chatId)
    .maybeSingle();
  if (profErr) {
    console.error('profile lookup error:', profErr);
    await reply(chatId, 'Не вдалося прочитати стан. Нічого не записано. Спробуйте ще раз.');
    return new Response('ok');
  }
  if (!prof) {
    await reply(chatId, 'Доступ закритий. Згенеруйте код у застосунку і надішліть /start <код>.', { remove_keyboard: true });
    return new Response('ok');
  }

  const updateId = Number(update.update_id) || 0;
  const pending = prof.telegram_pending ?? null;
  const done = () => new Response('ok');
  if(/^\/salary$/i.test(text)){await offerSalary(chatId,true);return done();}
  const linkCommand=text.match(/^\/link(?:\s+(\d+))?$/i);
  if(linkCommand){await offerFixedLink(chatId,prof.id,linkCommand[1]?Number(linkCommand[1]):undefined);return done();}
  if (/^\/(?:no|cancel)$/i.test(text) || text === BTN.cancel || text === BTN.no) {
    if (pending && !await replacePending(prof.id, pending, null)) await reply(chatId, 'Не вдалося скасувати. Спробуйте ще раз.');
    else await reply(chatId, 'Скасовано. Оберіть наступну дію.', pending ? MAIN_KB : undefined);
    return done();
  }
  const navigation = /^\/(?:menu|start|help|app|balance|chart|budget|week|month|last)$/i.test(text) || /^меню$/i.test(text) ||
    [BTN.menu,BTN.help,BTN.app,BTN.balance,BTN.chart,BTN.budget,BTN.week,BTN.month,BTN.last].includes(text);
  if (navigation && pending?.kind === 'entry' && !await replacePending(prof.id, pending, null)) {
    await reply(chatId, 'Не вдалося завершити введення. Спробуйте ще раз.', liveEntry(pending) ? entryKeyboard(pending) : MAIN_KB);
    return done();
  }
  if (navigation && pending?.kind === 'entry') await reply(chatId, 'Введення завершено.', MAIN_KB);
  if (!navigation && pending?.kind === 'entry' && !liveEntry(pending)) {
    const cleared = await replacePending(prof.id, pending, null);
    await reply(chatId, cleared ? 'Час введення минув або стан некоректний. Нічого не записано. Надішліть суму й опис або фото знову.' : 'Не вдалося прочитати або очистити стан. Спробуйте ще раз.', cleared ? MAIN_KB : undefined);
    return done();
  }
  if (/^\/yes$/i.test(text) || text === BTN.yes) { await confirmPending(chatId, prof.id); return done(); }
  const entryType = text === BTN.income || /^\/(?:income|дохід)$/i.test(text) ? 'income'
    : text === BTN.expense || /^\/expense$/i.test(text) ? 'expense' : null;
  if (entryType) {
    if (pending && pending.kind !== 'entry') await reply(chatId, 'Спочатку завершіть або скасуйте попередню дію.', CONFIRM_KB);
    else {
      const state: EntryPending = {kind:'entry',type:entryType,input:'choose',expires:new Date(Date.now()+PENDING_TTL_MS).toISOString()};
      if (await replacePending(prof.id, pending, state)) {await entryHint(chatId, state);if(entryType==='income')await offerSalary(chatId);}
      else await reply(chatId, 'Не вдалося почати введення. Спробуйте ще раз.');
    }
    return done();
  }
  if (!navigation && liveEntry(pending)) {
    if (text === BTN.text || text === BTN.image) {
      const next: EntryPending = {...pending,input:text === BTN.text ? 'text' : 'image'};
      if (await replacePending(prof.id, pending, next)) await entryHint(chatId, next);
      else await entryHint(chatId, pending, 'Не вдалося змінити спосіб. ');
      return done();
    }
    let outcome: unknown;
    if (pending.input === 'image' && photos) {
      outcome = await addReceipt(chatId, prof.id, updateId, photos, msg.media_group_id, msg.caption, msg.date, pending);
    } else if (pending.input === 'text' && text) {
      // Групи тисяч мають рівно три цифри; неоднозначний числовий початок опису відхиляємо.
      const input = text.match(/^([+-]?)\s*((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d{1,2})?)\s+([^\d\s].*)$/s);
      if (!input || (input[1] && (input[1] === '+' ? 'income' : 'expense') !== pending.type)) {
        await entryHint(chatId, pending, 'Перевірте суму, опис і знак: він має відповідати обраному типу. '); return done();
      }
      outcome = await addTx(chatId, prof.id, updateId, pending.type, input[2], input[3], pending);
    } else { await entryHint(chatId, pending, 'Цей формат не підходить для обраного кроку. '); return done(); }
    if (outcome === 'saved' || outcome === 'duplicate') {
      if (await replacePending(prof.id, pending, null)) await reply(chatId, outcome === 'duplicate' ? 'Цю операцію вже оброблено. Оберіть наступну дію.' : 'Готово. Оберіть наступну дію.', MAIN_KB);
      else await reply(chatId, 'Операцію оброблено. Не додавайте її повторно; стан введення змінився або не очистився.');
    } else if (outcome !== 'pending') await entryHint(chatId, pending, 'Нічого не записано. Спробуйте ще раз. ');
    return done();
  }
  if (!navigation && pending && !(photos && isLiveReceipt(pending))) {
    await reply(chatId, 'Спочатку підтвердьте або скасуйте попередню дію.', CONFIRM_KB); return done();
  }
  if (photos) {
    await addReceipt(chatId, prof.id, updateId, photos, msg.media_group_id, msg.caption, msg.date); return done();
  }
  let m: RegExpMatchArray | null;
  if (/^\/balance$/i.test(text) || text === BTN.balance) await balance(chatId);
  else if (/^\/chart$/i.test(text) || text === BTN.chart) await withFinance(chatId, chartReport);
  else if (/^\/budget$/i.test(text) || text === BTN.budget) await withFinance(chatId, budgetReport);
  else if (/^\/week$/i.test(text) || text === BTN.week) await withFinance(chatId, (c, d) => reply(c, formatWeek(weekModel(d.projection, d.today)), undefined, true));
  else if (/^\/month$/i.test(text) || text === BTN.month) await withFinance(chatId, (c, d) => reply(c, formatMonth(monthModel(d.txs, d.cats, d.accounts, d.today)), undefined, true));
  else if (/^\/last$/i.test(text) || text === BTN.last) await last(chatId);
  else if (/^\/help$/i.test(text) || text === BTN.help) await reply(chatId, HELP, MAIN_KB);
  else if (/^\/app$/i.test(text) || text === BTN.app) await reply(chatId, 'Відкрити застосунок:', APP_KB);
  else if (/^\/(?:menu|start)$/i.test(text) || /^меню$/i.test(text) || text === BTN.menu) await reply(chatId, 'Вітаю! Оберіть дію кнопками нижче.', MAIN_KB);
  else if ((m = text.match(/^\/(income|дохід)\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) {
    await addTx(chatId, prof.id, updateId, 'income', m[2], m[3]);
  } else if ((m = text.match(/^\/expense\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) {
    await addTx(chatId, prof.id, updateId, 'expense', m[1], m[2]);
  } else {
    m = text.match(/^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/s);
    if (m) await addTx(chatId, prof.id, updateId, m[1] === '+' ? 'income' : 'expense', m[2], m[3]);
    else await reply(chatId, 'Не зрозумів. ' + HELP);
  }

  return new Response('ok');
});
