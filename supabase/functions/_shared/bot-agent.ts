// Відповіді бота на питання своїми словами («скільки витратили на продукти в жовтні», «що з балансом»).
// Модель Claude лише обирає інструмент і параметри (період, категорію, слово пошуку) одним викликом;
// речення з числами складає код із тих самих моделей, що й звіти бота. Власний текст моделі з цифрами не показується.
// Інструменти лише читають: записати операцію голосом можна тільки через підтвердження «✅ Так, додати» (вебхук).
import { clampPeriod, type SpendQuery } from './spending.ts';
import { day, leftOrOver, money } from './finance-message.ts';
import type { BudgetModel } from './bot-reports.ts';

export const AGENT_MODEL_DEFAULT = 'claude-haiku-4-5-20251001';
const MAX_TOOLS = 4;

export type BalanceSection = 'balance' | 'cards' | 'installments' | 'payments';
export type AgentTools = {
  balance: (section: BalanceSection) => Promise<string>;
  spending: (q: SpendQuery) => Promise<string>;
  budget: (category: string | null) => Promise<string>;
};
export type AgentResult =
  | { kind: 'answer'; text: string; tools: string[] }
  | { kind: 'clarify'; text: string }
  | { kind: 'off_topic'; text: string }
  | { kind: 'not_question' }
  | { kind: 'error' };

export const OFF_TOPIC = 'Я відповідаю лише про гроші родини: баланс, картки, витрати, доходи, бюджет і платежі.';
export const CHANGE_REQUEST = 'Змінювати чи видаляти записи я не вмію: це можна зробити в застосунку.';
// Прохання записати, яке не розібралось як сума й опис («запиши каву», «додай витрату»): підказка формату, а не відмова
export const ADD_HINT = 'Щоб записати, надішліть суму й опис: «200 таксі», дохід з плюсом: «+5000 зарплата». Голосом так само: «200 гривень таксі».';
export const UNSUPPORTED = 'Цього я поки не вмію порахувати. Спробуйте кнопки меню.';
const CLARIFY_FALLBACK = 'Уточніть, будь ласка: за який період або яку категорію?';

const WEEKDAYS = ['неділя', 'понеділок', 'вівторок', 'середа', 'четвер', 'пʼятниця', 'субота'];

export function agentSystem(today: string): string {
  const wd = WEEKDAYS[new Date(today + 'T00:00:00Z').getUTCDay()];
  return [
    'Ти помічник сімейного бюджету в Telegram-боті родини. Тобі ставлять питання українською, іноді російською чи суржиком, часто розпізнані з голосу (можливі помилки розпізнавання).',
    `Сьогодні ${today}, ${wd}, часовий пояс Київ. Валюта гривня.`,
    'Відповідай ЛИШЕ викликами інструментів. Числа ти не знаєш і не називаєш: їх підставить код.',
    'Правила вибору:',
    '- гроші зараз, баланс, власні кошти, скільки можна витрачати на день, чи вистачить до зарплати: balance(section=balance);',
    '- залишки й борги на картках чи рахунках: balance(section=cards); розстрочки: balance(section=installments); найближчі обовʼязкові платежі, коли й скільки платити: balance(section=payments);',
    '- скільки лишилось чи перевитрачено в бюджеті поточного періоду, загалом чи на категорію: budget;',
    '- скільки витратили чи заробили за період, загалом, на категорію або на магазин чи річ: spending. Категорію бери лише з переліку (зіставляй за змістом: «їжа» це категорія продуктів, якщо така є). Магазин, місце чи річ, яких немає серед категорій (АТБ, Сільпо, бензин, кава), передавай у search одним словом основи без закінчення.',
    'Періоди для spending (дати YYYY-MM-DD): без періоду в питанні: з першого числа поточного місяця до сьогодні; «цей місяць» чи назва поточного місяця: так само; минулий чи названий місяць: увесь той місяць; «цього тижня»: з понеділка до сьогодні; «минулого тижня»: понеділок-неділя минулого тижня; «сьогодні», «вчора»: один день; «цього року»: з 1 січня до сьогодні. Майбутнього не буває.',
    'Кілька питань в одному: кілька викликів (до чотирьох).',
    '- питання про гроші родини, але незрозуміло, про що саме: clarify з коротким питанням без цифр;',
    '- просять додати чи записати операцію: not_supported(kind=add_request); змінити чи видалити запис: not_supported(kind=change_request);',
    '- не про гроші родини (погода, новини, загальні знання, жарти): not_supported(kind=off_topic);',
    '- не питання і не прохання (привітання, «дякую», окреме слово): not_supported(kind=not_a_question);',
    '- про гроші, але жоден інструмент не підходить: not_supported(kind=finance_unsupported).',
  ].join('\n');
}

export function agentTools(categoryNames: string[]): any[] {
  const cats = [...new Set(categoryNames.map((n) => String(n || '').trim()).filter(Boolean))].slice(0, 200);
  const category = cats.length ? { type: 'string', enum: cats, description: 'Категорія з переліку, якщо питають про категорію' } : { type: 'string' };
  return [
    {
      name: 'balance', description: 'Поточний фінансовий стан родини: розділ статусу.',
      input_schema: { type: 'object', properties: { section: { type: 'string', enum: ['balance', 'cards', 'installments', 'payments'] } }, required: ['section'] },
    },
    {
      name: 'spending', description: 'Сума витрат або доходів за період: загалом, на одну категорію або за словом в описі операції (магазин, річ).',
      input_schema: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['expense', 'income'] },
          from: { type: 'string', description: 'Перший день періоду, YYYY-MM-DD' },
          to: { type: 'string', description: 'Останній день періоду, YYYY-MM-DD' },
          category,
          search: { type: 'string', description: 'Слово з опису операції: магазин, місце, річ', maxLength: 40 },
        },
        required: ['type', 'from', 'to'],
      },
    },
    {
      name: 'budget', description: 'Бюджет поточного періоду між виплатами: план, витрачено, залишок; загалом або на одну категорію.',
      input_schema: { type: 'object', properties: { category } },
    },
    {
      name: 'clarify', description: 'Коротке уточнювальне питання без цифр, коли питання про гроші родини незрозуміле.',
      input_schema: { type: 'object', properties: { question: { type: 'string', maxLength: 200 } }, required: ['question'] },
    },
    {
      name: 'not_supported', description: 'Питання поза можливостями.',
      input_schema: { type: 'object', properties: { kind: { type: 'string', enum: ['off_topic', 'not_a_question', 'add_request', 'change_request', 'finance_unsupported'] } }, required: ['kind'] },
    },
  ];
}

// Відповідь про бюджет періоду з тієї самої моделі, що звіт «📊 Бюджет»
const normName = (s: unknown) => String(s ?? '').normalize('NFKC').toLocaleLowerCase('uk-UA').trim();
export function budgetAnswer(m: BudgetModel | null, category: string | null): string {
  if (!m) return 'Бюджет недоступний: налаштуйте суми та дати виплат у застосунку.';
  const period = `${day(m.start)}-${day(m.end)}`;
  if (!category) {
    const head = `Бюджет періоду ${period}: ${money(m.poolCents)}, витрачено ${money(m.spentCents)}, ${leftOrOver(m.leftCents)}.`;
    return m.leftDays > 0 && m.leftCents >= 0 ? `${head} До ${day(m.end)}: ${money(m.dailyCents)}/день (${m.leftDays} дн.).` : head;
  }
  const row = m.rows.find((r) => normName(r.name) === normName(category));
  if (!row) return `${category} у періоді ${period}: ні плану, ні витрат немає.`;
  if (row.noPlan || row.plan <= 0) return `${row.name} у періоді ${period}: витрачено ${money(row.fact)}, плану немає.`;
  // Без «з <сума>»: числівник після прийменника вимовлявся б у неправильному відмінку
  return `${row.name} у періоді ${period}: план ${money(row.plan)}, витрачено ${money(row.fact)}, ${leftOrOver(row.plan - row.fact)}.`;
}

type Deps = { apiKey: string; model?: string; fetchImpl?: typeof fetch; today: string; categories: string[]; timeoutMs?: number };

// Один виклик Claude: модель обирає інструменти, код їх виконує і складає відповідь
export async function askAgent(question: string, deps: Deps, tools: AgentTools): Promise<AgentResult> {
  const q = String(question || '').trim().slice(0, 500);
  if (!q || !deps.apiKey) return { kind: 'error' };
  const f = deps.fetchImpl || fetch;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), deps.timeoutMs ?? 20000);
  let content: any[];
  try {
    const r = await f('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      signal: ctrl.signal,
      headers: { 'x-api-key': deps.apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: deps.model || AGENT_MODEL_DEFAULT, max_tokens: 600, temperature: 0,
        system: agentSystem(deps.today), tools: agentTools(deps.categories), tool_choice: { type: 'any' },
        messages: [{ role: 'user', content: `Питання: «${q}»` }],
      }),
    });
    const j = await r.json();
    if (!r.ok) {
      console.error('agent claude error', r.status, j?.error?.type || '');
      return { kind: 'error' };
    }
    content = Array.isArray(j?.content) ? j.content : [];
  } catch (e) {
    console.error('agent claude fetch failed', (e as Error)?.name || '');
    return { kind: 'error' };
  } finally {
    clearTimeout(timer);
  }
  const calls = content.filter((c) => c?.type === 'tool_use' && c.input && typeof c.input === 'object').slice(0, MAX_TOOLS);
  if (!calls.length) return { kind: 'error' };
  return runCalls(calls, deps, tools);
}

// Виконання вибору моделі: перевірка параметрів, тексти лише від коду
export async function runCalls(calls: { name: string; input: any }[], deps: Pick<Deps, 'today' | 'categories'>, tools: AgentTools): Promise<AgentResult> {
  const lines: string[] = [], used: string[] = [];
  const catOk = (v: unknown) => typeof v === 'string' && deps.categories.some((c) => normName(c) === normName(v)) ? deps.categories.find((c) => normName(c) === normName(v))! : null;
  let clarify: string | null = null, refusal: AgentResult | null = null;
  for (const c of calls) {
    const a = c.input || {};
    if (c.name === 'balance') {
      const section = ['balance', 'cards', 'installments', 'payments'].includes(a.section) ? a.section : 'balance';
      lines.push(await tools.balance(section));
      used.push('balance:' + section);
    } else if (c.name === 'spending') {
      const p = clampPeriod(a.from, a.to, deps.today);
      if (!p) { lines.push('Не зрозумів період. Назвіть місяць, тиждень або дати.'); continue; }
      const search = typeof a.search === 'string' ? a.search.replace(/[«»"<>]/g, '').trim().slice(0, 40) : '';
      const category = a.category != null ? catOk(a.category) : null;
      if (a.category != null && !category && !search) { lines.push(`Категорії «${String(a.category).slice(0, 40)}» немає.`); continue; }
      lines.push(await tools.spending({ type: a.type === 'income' ? 'income' : 'expense', ...p, category, search: search || null }));
      used.push('spending');
    } else if (c.name === 'budget') {
      lines.push(await tools.budget(a.category != null ? catOk(a.category) ?? String(a.category).slice(0, 40) : null));
      used.push('budget');
    } else if (c.name === 'clarify') {
      const t = typeof a.question === 'string' ? a.question.trim().slice(0, 200) : '';
      clarify = t && !/\d/.test(t) ? t : CLARIFY_FALLBACK;
    } else if (c.name === 'not_supported') {
      refusal = a.kind === 'not_a_question' ? { kind: 'not_question' }
        : { kind: 'off_topic', text: a.kind === 'add_request' ? ADD_HINT : a.kind === 'change_request' ? CHANGE_REQUEST : a.kind === 'finance_unsupported' ? UNSUPPORTED : OFF_TOPIC };
    }
  }
  if (lines.length) return { kind: 'answer', text: lines.filter(Boolean).join('\n'), tools: used };
  if (clarify) return { kind: 'clarify', text: clarify };
  return refusal || { kind: 'error' };
}
