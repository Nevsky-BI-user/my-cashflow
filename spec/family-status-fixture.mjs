// Відповідь family-status і розділи бота «Баланс» і «Картки» з одного входу: синтетична фікстура бота (spec/bot-fixture.cjs)
// через фальшивий Supabase. Ті самі функції, що в Edge: statusData (дані freeBlock бота), financeSections (текст бота),
// handleFamilyStatus (відповідь функції з перевіркою підпису). Без мережі.
// Запуск: node spec/family-status-fixture.mjs [дата] [base|rich]  → JSON {status, sections} у stdout для scripts/verify_family_status.py
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const require = createRequire(import.meta.url);
const mod = (p) => import(pathToFileURL(path.join(root, 'supabase/functions/_shared', p)).href);

// Фальшивий Supabase: фільтри eq/lte/in/not, порядок, range/limit; or(...) пропускає все (фікстура мала), запити записують у calls
export function fakeSb(tables) {
  const calls = [];
  return {calls, from(table) {
    const call = {table, ops: []};
    calls.push(call);
    const f = [], order = [];
    let lo = 0, hi = Infinity, single = false;
    const q = {};
    const op = (name, fn) => { q[name] = (...a) => { call.ops.push([name, ...a]); fn?.(...a); return q; }; };
    op('select'); op('or');
    op('eq', (k, v) => f.push((r) => r[k] === v));
    op('lte', (k, v) => f.push((r) => r[k] == null || String(r[k]) <= String(v)));
    op('in', (k, v) => f.push((r) => v.map(String).includes(String(r[k]))));
    op('not', (k, o, v) => f.push((r) => r[k] != v));
    op('order', (k, o = {}) => order.push([k, o.ascending !== false]));
    op('range', (a, b) => { lo = a; hi = b + 1; });
    op('limit', (n) => { hi = Math.min(hi, lo + n); });
    op('maybeSingle', () => { single = true; });
    for (const w of ['insert', 'update', 'upsert', 'delete', 'rpc']) q[w] = () => { throw new Error('write attempted: ' + w); };
    q.then = (res, rej) => Promise.resolve().then(() => {
      let rows = (tables[table] || []).filter((r) => f.every((x) => x(r)));
      if (order.length) rows = rows.slice().sort((a, b) => { for (const [k, asc] of order) { const x = a[k], y = b[k]; if (x === y) continue; return (x > y ? 1 : -1) * (asc ? 1 : -1); } return 0; });
      rows = rows.slice(lo, hi);
      return {data: single ? rows[0] ?? null : rows, error: null};
    }).then(res, rej);
    return q;
  }};
}

// variant 'rich': місячні бюджети з перевитратою, відʼємний і шестизначний залишки, довга назва рахунку,
// без рядка «Без рахунку», розстрочка, сплачена наперед (рушій переписує суму такого платежу)
export function fixtureTables(variant = 'base') {
  const {botFixture} = require('./bot-fixture.cjs');
  const fx = botFixture();
  const t = {
    accounts: fx.accounts.map((a, i) => ({...a, sort_order: i, owner: i % 2 ? 'Дружина' : null, mono_token: 'не має потрапити у відповідь'})),
    fixed_payments: fx.fixed, credits: fx.credits, salary_config: [{id: 1, ...fx.salary}],
    categories: fx.categories.map(({type, ...c}) => c), transactions: fx.transactions, monthly_budgets: [],
  };
  if (variant === 'rich') {
    const by = (id) => t.accounts.find((a) => a.id === id);
    by(1).balance = 152519.37;
    by(5).balance = -300;
    by(4).name = 'ПриватБанк Універсальна кредитна';
    t.transactions = t.transactions.filter((x) => x.account_id != null);
    t.transactions.push({id: 9001, account_id: 1, type: 'expense', amount: 1500, date: '2026-10-10', created_at: '2026-10-10T11:00:00Z',
      source: 'manual', description: 'Телефон наперед', category_id: 8, credit_id: 22, payment_due_date: '2026-11-13'});
    const row = (m, total, allocations) => ({month_start: m + '-01', total_cents: total, allocations, mandatory_items: [], income_basis_cents: null});
    t.monthly_budgets = [row('2026-09', 1000000, {1: 600000}), row('2026-10', 1000000, {1: 600000, 2: 200000}), row('2026-11', 1200000, {1: 700000})];
  }
  return {today: fx.today, tables: t};
}

// Обидві сторони з одного входу. Бот: financeSections від statusData (так freeBlock у telegram-webhook);
// функція: справжній обробник з підписаним GET і годинником на полудень дня фікстури за Києвом
export async function both(today, variant = 'base') {
  const fx = fixtureTables(variant);
  const day = today || fx.today;
  const sb = fakeSb(fx.tables);
  const {statusData} = await mod('bot-status.ts');
  const {financeSections} = await mod('finance-message.ts');
  const {handleFamilyStatus, TWIN_SIGNED} = await mod('family-status.ts');
  const {voiceSign} = await mod('voice-auth.ts');
  const s = await statusData(sb, day);
  const sections = financeSections(s.projection, s.unassigned, s.installments, s.budget);
  const secret = 'fixture-secret-0123456789abcdef-0123456789';
  const ts = Math.floor(Date.now() / 1000);
  const req = new Request('https://example.test/functions/v1/family-status', {method: 'GET',
    headers: {'X-Twin-Ts': String(ts), 'X-Twin-Sig': await voiceSign(secret, ts, TWIN_SIGNED)}});
  const handlerSb = fakeSb(fx.tables);
  const res = await handleFamilyStatus(req, {sb: handlerSb, secret, now: () => new Date(day + 'T09:00:00Z')});
  return {httpStatus: res.status, status: await res.json(), sections, statusData: s, sbCalls: sb.calls, handlerCalls: handlerSb.calls};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const r = await both(process.argv[2] || undefined, process.argv[3] || 'base');
  process.stdout.write(JSON.stringify({httpStatus: r.httpStatus, status: r.status, sections: {top: r.sections.top, cards: r.sections.cards}}, null, 1));
}
