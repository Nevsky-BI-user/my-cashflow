import { repaymentAdvice, repaymentAdviceText } from '../_shared/repayment.ts';
import { salaryOptions, salaryKeyboard } from '../_shared/salary-bot.ts';
// Ранковий підсумок і нагадування на завтра в Telegram.
// Викликає pg_cron щогодини о :00 UTC (міграція 27-telegram-digest.sql); функція сама перевіряє, що в Києві зараз 9-та година,
// тож перехід на літній і зимовий час не потребує зміни розкладу.
// Захист: заголовок x-digest-secret == секрет DIGEST_SECRET (без секрету або з чужим значенням 403).
// Тіло {"force": true} пропускає перевірку години (ручна перевірка після деплою).
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { loadFinance } from '../_shared/bot-data.ts';
import { budgetModel, dueTomorrow, formatDigest, formatReminder, kyivNow } from '../_shared/bot-reports.ts';
import { paidKb } from '../_shared/bot-kb.ts';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN')!;
const DIGEST_SECRET = Deno.env.get('DIGEST_SECRET') || '';
const DIGEST_HOUR = 9;

// Той самий список, що в застосунку і is_family_member(): підсумок іде лише привʼязаним членам сімʼї
const ALLOWED_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

// Порівняння секрету за сталий час: тривалість не підказує, скільки символів збіглося
function sameSecret(a: string, b: string): boolean {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

async function send(chatId: number, text: string, markup?: unknown): Promise<boolean> {
  try {
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, reply_markup: markup }),
    });
    if (!r.ok) console.error('digest: sendMessage failed:', r.status, (await r.text()).slice(0, 200));
    return r.ok;
  } catch (e) {
    console.error('digest: sendMessage failed:', e);
    return false;
  }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method not allowed', { status: 405 });
  if (!DIGEST_SECRET || !sameSecret(req.headers.get('x-digest-secret') || '', DIGEST_SECRET)) {
    return new Response('forbidden', { status: 403 });
  }
  let force = false;
  try {
    force = (await req.json())?.force === true;
  } catch {
    // порожнє тіло від cron: звичайний запуск
  }
  const now = kyivNow(new Date());
  if (!force && now.hour !== DIGEST_HOUR) return json({ ok: true, skipped: `kyiv hour ${now.hour}` });

  const { data: profs, error } = await sb.from('profiles').select('id,telegram_chat_id').not('telegram_chat_id', 'is', null);
  if (error) {
    console.error('digest: profiles lookup failed:', error.message);
    return json({ ok: false }, 500);
  }
  // Лише члени сімʼї з whitelist (привʼязка це вже перевіряє, тут другий шар перед відправкою фінансових даних)
  const chats: number[] = [];
  for (const p of profs || []) {
    const { data: au } = await sb.auth.admin.getUserById(p.id);
    if (ALLOWED_EMAILS.includes((au?.user?.email || '').toLowerCase())) chats.push(Number(p.telegram_chat_id));
  }
  if (!chats.length) return json({ ok: true, sent: 0 });

  let d;
  try {
    d = await loadFinance(sb, now.date);
  } catch (e) {
    console.error('digest: finance load failed', (e as Error)?.message);
    return json({ ok: false }, 500);
  }
  const salaries=await salaryOptions(sb,now.date);
  const salaryToday=salaries.choices.filter(p=>p.date===now.date);
  const source=salaryToday[0];
  const advice=source?repaymentAdviceText(repaymentAdvice(d.input,d.projection,source.accountId,d.today)):'';
  // v186: залишок бюджету періоду на день, як звіт «Бюджет»
  let budget = null;
  try { budget = budgetModel(d.projection, d.txs, d.cats, d.today, d.input, d.accounts); } catch (e) { console.error('digest: budget failed', (e as Error)?.message); }
  const digest = formatDigest(d.projection, d.credits, d.txs, d.today, budget)+(advice?'\n\n'+advice:'');
  const due = dueTomorrow(d.projection, d.fixed, d.credits, d.today);
  let sent = 0;
  for (const chatId of chats) {
    // Підсумок не розкриває згорнуту користувачем панель кнопок.
    if (await send(chatId, digest)) sent++;
    if(salaryToday.length&&await send(chatId,'Сьогодні день виплати. Підтвердіть надходження:',salaryKeyboard(salaryToday)))sent++;
    // Кожне нагадування окремим повідомленням: кнопка «Оплачено» редагує саме його
    for (const it of due) if (await send(chatId, formatReminder(it), paidKb(it.callback))) sent++;
  }
  return json({ ok: true, chats: chats.length, reminders: due.length, sent });
});
