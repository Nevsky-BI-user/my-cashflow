// Дані для звітів бота і ранкового підсумку: ті самі таблиці й та сама проєкція, що в статусі «Баланс» (freeBlock).
// Клієнт Supabase передається ззовні, тож модуль спільний для telegram-webhook і telegram-digest.
import { financeProjection, lastPayout, type AccTx } from './budget.ts';

export type BotTx = AccTx & { description?: string | null };
export type FinanceData = {
  today: string;
  projection: ReturnType<typeof financeProjection>;
  txs: BotTx[];
  accounts: any[];
  fixed: any[];
  credits: any[];
  cats: any[];
  salary: any;
  firstOwnDate: string | null;
};

const shift = (d: string, n: number) => new Date(Date.parse(d + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
// Перше число попереднього місяця: звіт «Місяць» і графік від мінус місяця
const prevMonthStart = (d: string) => {
  const y = Number(d.slice(0, 4)), m = Number(d.slice(5, 7));
  return m === 1 ? `${y - 1}-12-01` : `${y}-${String(m - 1).padStart(2, '0')}-01`;
};

// Усі операції від from (і створені після найранішої мітки балансу ручного рахунку): сторінки по 1000, без тихого обрізання
async function loadTxs(sb: any, from: string, today: string, since: number): Promise<BotTx[]> {
  const rows: BotTx[] = [];
  for (let page = 0; page < 100; page++) {
    let q = sb.from('transactions').select('id,account_id,category_id,fixed_id,credit_id,type,amount,created_at,date,source,description')
      .lte('date', today).order('id', { ascending: true }).range(page * 1000, page * 1000 + 999);
    q = Number.isFinite(since) ? q.or(`created_at.gt."${new Date(since).toISOString()}",date.gte.${from}`) : q.gte('date', from);
    const { data, error } = await q;
    if (error) throw new Error('bot transactions lookup failed');
    rows.push(...(data || []));
    if (!data || data.length < 1000) return rows;
  }
  throw new Error('bot transactions pagination limit');
}

export async function loadFinance(sb: any, today: string): Promise<FinanceData> {
  const [acc, fix, cred, sal, cats] = await Promise.all([
    sb.from('accounts').select('id,name,bank,kind,balance,debt,credit_limit,debt_month,active,mono_account_id,balance_updated_at,min_spend,min_spend_fee')
      .eq('active', true).order('sort_order', { ascending: true }).order('id', { ascending: true }),
    sb.from('fixed_payments').select('id,name,amount,day_of_month,period,weekday,bank,type,active,credit_ok,variable').eq('active', true),
    sb.from('credits').select('id,name,monthly_amount,payment_day,start_year,start_month,total_payments,credit_ok,source'),
    sb.from('salary_config').select('rate,advance_amount,salary_amount,split_day,advance_day,salary_day,savings_pct').order('id').limit(1).maybeSingle(),
    sb.from('categories').select('id,name,color,is_income,budget_limit,limit_abs,sort_order,group_id').order('id'),
  ]);
  if (acc.error || fix.error || cred.error || sal.error || cats.error) throw new Error('bot finance lookup failed');
  const accounts = acc.data || [];
  const manual = accounts.filter((a: any) => !a.mono_account_id && a.balance_updated_at);
  const since = Math.min(...manual.map((a: any) => Date.parse(a.balance_updated_at)).filter((t: number) => !isNaN(t)));
  const periodStart = sal.data ? lastPayout(sal.data, today).date : today.slice(0, 7) + '-01';
  const from = [shift(today, -60), periodStart, prevMonthStart(today)].sort()[0];
  const txs = await loadTxs(sb, from, today, since);
  // Перша операція на власних (не кредитних) рахунках: межа історії графіка, як у застосунку (v146)
  const ownIds = accounts.filter((a: any) => a.kind !== 'credit' && a.id != null).map((a: any) => a.id);
  let firstOwnDate: string | null = null;
  if (ownIds.length) {
    const r = await sb.from('transactions').select('date').in('account_id', ownIds).lte('date', today).order('date', { ascending: true }).limit(1);
    if (!r.error && r.data && r.data[0]?.date) firstOwnDate = String(r.data[0].date).slice(0, 10);
  }
  const categories = (cats.data || []).map((c: any) => ({ ...c, type: c.is_income ? 'income' : 'expense' }));
  const projection = financeProjection({
    accounts, fixed: fix.data || [], credits: cred.data || [], salary: sal.data, categories, transactions: txs,
  }, { asof: today, through: shift(today, 120) });
  return { today, projection, txs, accounts, fixed: fix.data || [], credits: cred.data || [], cats: categories, salary: sal.data, firstOwnDate };
}
