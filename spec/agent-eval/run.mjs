// Сліпий замір відповідей бота (набір 14.11.2026): маршрут як у вебхуку, далі справжній виклик Claude.
// Питання писав окремий агент, що не бачив ні промпту, ні інструментів; файл заморожено контрольною сумою.
// Ключ: змінна CLAUDE_API_KEY або файл .local/anthropic-key.txt (шукається в цій теці й вище, у git не потрапляє).
// Ключ не друкується і не пишеться у вивід. Інструменти лише записують, що їх покликали: бази скрипт не чіпає.
// Запуск: node spec/agent-eval/run.mjs [--limit N]  → .local/agent-eval/run-<час>.jsonl; оцінка: score.py
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../..');
const SET = join(HERE, 'blind-2026-11-14.jsonl');
const SHA = 'bf444f03cfc93f4fc84b64af55e09420ecfcbaeeb2af0059a51c798e8a56909f';
const TODAY = '2026-11-14';
const shared = (f) => import(pathToFileURL(join(ROOT, 'supabase/functions/_shared', f)).href);

// Сума по тексту з LF (так файл лежить у git); на Windows git кладе його з CRLF, сирий файл тоді дає 739ff226…
const raw = readFileSync(SET, 'utf8').replace(/\r\n/g, '\n');
if (createHash('sha256').update(raw, 'utf8').digest('hex') !== SHA) {
  console.error('Набір змінено: контрольна сума не збігається. Новий замір = новий набір.');
  process.exit(2);
}
const questions = raw.split('\n').filter(Boolean).map((l) => JSON.parse(l));
const categories = JSON.parse(readFileSync(join(HERE, 'categories-2026-11-14.json'), 'utf8'));

function findKey() {
  if (process.env.CLAUDE_API_KEY) return process.env.CLAUDE_API_KEY.trim();
  for (let d = HERE; ; d = dirname(d)) {
    const f = join(d, '.local', 'anthropic-key.txt');
    if (existsSync(f)) return readFileSync(f, 'utf8').trim();
    if (dirname(d) === d) return '';
  }
}
const apiKey = findKey();
if (!apiKey) {
  console.error('Немає ключа: поставте його у .local/anthropic-key.txt або змінну CLAUDE_API_KEY.');
  process.exit(2);
}

const { askAgent, AGENT_MODEL_DEFAULT } = await shared('bot-agent.ts');
const { notEntry, parseVoiceEntry } = await shared('voice-entry.ts');
const model = process.env.AGENT_MODEL || AGENT_MODEL_DEFAULT;
const li = process.argv.indexOf('--limit');
const limit = li > 0 ? Number(process.argv[li + 1]) : questions.length;

// Маршрут тексту як у telegram-webhook: кнопки й команди, «меню», запис сумою, інакше питання
function textRoute(t) {
  if (/^\/[a-z]+$/i.test(t) || /^меню$/i.test(t)) return { route: 'menu' };
  let m;
  if ((m = t.match(/^\/(income|дохід)\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) return { route: 'entry', entry: { type: 'income', amount: m[2], description: m[3] } };
  if ((m = t.match(/^\/expense\s+(\d+(?:[.,]\d{1,2})?)\s+(.+)$/is))) return { route: 'entry', entry: { type: 'expense', amount: m[1], description: m[2] } };
  if ((m = t.match(/^([+-]?)\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$/s)) && !notEntry(t)) return { route: 'entry', entry: { type: m[1] === '+' ? 'income' : 'expense', amount: m[2], description: m[3] } };
  if (t.startsWith('/') || t.length > 500) return { route: 'help' };
  return { route: 'agent' };
}

// Повтор лише на перевантаження чи збій мережі: це інфраструктура, а не вибір моделі
function recordingFetch(rec) {
  return async (url, init) => {
    for (let attempt = 0; ; attempt++) {
      let r;
      try {
        r = await fetch(url, init);
      } catch (e) {
        if (attempt >= 3) throw e;
        rec.retries++;
        await new Promise((ok) => setTimeout(ok, 2000 * (attempt + 1)));
        continue;
      }
      if ([429, 500, 502, 503, 529].includes(r.status) && attempt < 3) {
        rec.retries++;
        await new Promise((ok) => setTimeout(ok, 3000 * (attempt + 1)));
        continue;
      }
      const j = await r.json();
      rec.status = r.status;
      rec.usage = j?.usage || null;
      rec.raw = (Array.isArray(j?.content) ? j.content : []).filter((c) => c?.type === 'tool_use').map((c) => ({ name: c.name, input: c.input }));
      return { ok: r.ok, status: r.status, json: async () => j };
    }
  };
}

async function one(q) {
  const rec = { n: q.n, q: q.q, lang: q.lang, channel: q.channel, retries: 0, raw: [], executed: [] };
  const v = q.channel === 'voice' ? parseVoiceEntry(q.q) : null;
  const tr = q.channel === 'voice' ? (v ? { route: 'entry', entry: v } : { route: 'agent' }) : textRoute(q.q);
  rec.route = tr.route;
  if (tr.entry) rec.entry = tr.entry;
  if (tr.route !== 'agent') return rec;
  const tools = {
    balance: async (section) => { rec.executed.push({ t: 'balance', section }); return `[balance:${section}]`; },
    spending: async (s) => { rec.executed.push({ t: 'spending', ...s }); return `[spending]`; },
    budget: async (category) => { rec.executed.push({ t: 'budget', category }); return `[budget]`; },
  };
  const t0 = Date.now();
  const r = await askAgent(q.q, { apiKey, model, today: TODAY, categories, fetchImpl: recordingFetch(rec), timeoutMs: 60000 }, tools);
  rec.ms = Date.now() - t0;
  rec.result = r;
  return rec;
}

const out = [];
const todo = questions.slice(0, limit);
const POOL = 4;
for (let i = 0; i < todo.length; i += POOL) {
  out.push(...await Promise.all(todo.slice(i, i + POOL).map(one)));
  process.stdout.write(`\r${Math.min(i + POOL, todo.length)}/${todo.length}`);
}
const dir = join(ROOT, '.local', 'agent-eval');
mkdirSync(dir, { recursive: true });
const file = join(dir, `run-${new Date().toISOString().replace(/[:.]/g, '-')}.jsonl`);
writeFileSync(file, out.sort((a, b) => a.n - b.n).map((r) => JSON.stringify({ model, ...r })).join('\n') + '\n');
const tokIn = out.reduce((s, r) => s + (r.usage?.input_tokens || 0), 0), tokOut = out.reduce((s, r) => s + (r.usage?.output_tokens || 0), 0);
console.log(`\nготово: ${file}\nмодель ${model}, викликів ${out.filter((r) => r.route === 'agent').length}, токенів вхід ${tokIn}, вихід ${tokOut}`);
// Збій API не є вибором моделі: такий прогін не оцінюється
const broken = out.filter((r) => r.route === 'agent' && r.status !== 200);
if (broken.length) {
  console.error(`збоїв API: ${broken.length} (статуси ${[...new Set(broken.map((r) => r.status ?? 'мережа'))].join(', ')}); прогін не оцінюється`);
  process.exit(3);
}
