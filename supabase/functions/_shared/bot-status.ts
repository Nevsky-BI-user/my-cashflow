// Дані статусу бота («Баланс», «Картки», «Розстрочки», «Платежі»): та сама проєкція, що в застосунку.
// До v235 жило у telegram-webhook (freeBlock); винесено без змін логіки, щоб функція family-status
// (для локального клієнта власника) брала ті самі числа, що бот, а не рахувала їх удруге.
// Клієнт Supabase передається ззовні; project підміняють лише тести, щоб побачити вхід рушія.
import { financeProjection, lastPayout, type AccTx } from './budget.ts';
import { loadFinance, loadMonthlyBudgets } from './bot-data.ts';
import { budgetModel, type BudgetModel } from './bot-reports.ts';
import type { Installment } from './finance-message.ts';

const shiftDate = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);

export type StatusData = {
  projection: ReturnType<typeof financeProjection>;
  unassigned: {count: number; amountCents: number};
  installments: Installment[];
  budget: BudgetModel | null;
};

// Повний набір потрібних операцій: сторінки зі стабільним порядком, без тихого ліміту 1000.
async function financeTransactions(sb: any, from: string, today: string, since: number): Promise<AccTx[]> {
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
export async function statusData(sb: any, today: string, project: typeof financeProjection = financeProjection): Promise<StatusData> {
  const [acc, fix, cred, sal, cats] = await Promise.all([
    // v234: '*' несе й owner (колонка «Хто» картинки); до застосування міграції запит не падає
    sb.from('accounts').select('*')
      .eq('active', true).order('sort_order', { ascending: true }).order('id', { ascending: true }),
    sb.from('fixed_payments').select('id,name,amount,day_of_month,month_of_year,period,weekday,bank,type,active,credit_ok,variable,end_date').eq('active', true),
    sb.from('credits').select('id,name,monthly_amount,payment_day,start_year,start_month,total_payments,credit_ok,source'),
    // v153: усі колонки, з ними budget_manual (ручний бюджет періоду, міграція 30); до застосування міграції запит не падає
    sb.from('salary_config').select('*').order('id').limit(1).maybeSingle(),
    sb.from('categories').select('id,name,is_income,budget_limit,limit_abs,sort_order,group_id,budget_role').order('id'),
  ]);
  if (acc.error || fix.error || cred.error || sal.error || cats.error) throw new Error('budget data lookup failed');
  const manual = (acc.data || []).filter((a: any) => !a.mono_account_id && a.balance_updated_at);
  const since = Math.min(...manual.map((a: any) => Date.parse(a.balance_updated_at)).filter((t: number) => !isNaN(t)));
  const from60 = shiftDate(today, -60);
  const periodStart = sal.data ? lastPayout(sal.data, today).date : today.slice(0, 7) + '-01';
  const from = [from60, periodStart, today.slice(0, 7) + '-01'].sort()[0];
  const transactions = await financeTransactions(sb, from, today, since);
  const monthly_budgets = await loadMonthlyBudgets(sb);
  const projection = project({monthly_budgets, accounts: acc.data || [], fixed: fix.data || [], credits: cred.data || [], salary: sal.data,
    categories: (cats.data || []).map((c: any) => ({...c, type: c.is_income ? 'income' : 'expense'})), transactions} as any,
    {asof: today, through: shiftDate(today, 90)});
  const lost = transactions.filter(t => t.account_id == null && t.type === 'expense' &&
    (t.source === 'telegram' || t.source === 'manual') && String(t.date || t.created_at).slice(0, 10) >= from60);
  // Залишок розстрочок: платежі з датою після сьогодні (сплачені за планом не рахуються), крім місяців, уже
  // оплачених фактом (витрата з credit_id у місяці платежу)
  const paidCr = new Set(transactions.filter((t) => t.type === 'expense' && t.credit_id != null)
    .map((t) => String(t.credit_id) + '|' + String(t.payment_due_date ?? t.date ?? t.created_at).slice(0, 7)));
  const installments = (cred.data || []).map((c: any) => {
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
  }).filter((i: Installment) => i.n > 0);
  // v186: залишок бюджету періоду на день тим самим шляхом, що звіт «Бюджет» і ранковий підсумок; збій не ламає статус
  let budget: BudgetModel | null = null;
  try {
    const fd = await loadFinance(sb, today);
    budget = budgetModel(fd.projection, fd.txs, fd.cats, today, fd.input, fd.accounts);
  } catch (e) {
    console.error('status budget failed', (e as Error)?.message);
  }
  return {projection, unassigned: {count: lost.length, amountCents: lost.reduce((sum, t) => sum + Math.round(Number(t.amount) * 100), 0)}, installments, budget};
}
