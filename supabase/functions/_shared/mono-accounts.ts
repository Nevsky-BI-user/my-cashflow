export const FAMILY_EMAILS = ['gotnewmess@gmail.com', 'kovtunenko.yulchik@gmail.com'];
export const allowedMonoOwner = (email: unknown) => typeof email === 'string' && FAMILY_EMAILS.includes(email.toLowerCase());
export function selectMonoAccount(cards: any[], linked: any[], last4?: string) {
  const uah = cards.filter(a => a?.id && a.currencyCode === 980);
  if (last4 != null && (typeof last4 !== 'string' || !/^\d{4}$/.test(last4))) throw new Error('invalid_card_last4');
  const matches = last4 ? uah.filter(a => (a.maskedPan || []).some((pan: string) => pan.endsWith(last4))) : uah.filter(a => linked.some(b => b.mono_account_id === a.id));
  if (!last4 && linked.some(a => a.mono_account_id) && !matches.length) throw new Error('unknown_account');
  const candidates = matches.length || last4 ? matches : uah;
  if (candidates.length !== 1) throw new Error(candidates.length ? 'ambiguous_account' : 'no_uah_account');
  return candidates[0];
}
export function monoBalancePatch(card: any) {
  if (!Number.isFinite(card.balance) || !Number.isFinite(card.creditLimit) || card.creditLimit < 0) throw new Error('invalid_mono_balance');
  return { mono_account_id: card.id, balance_updated_at: new Date().toISOString(), credit_limit: card.creditLimit / 100,
    balance: card.creditLimit > 0 ? Math.max(0, card.balance - card.creditLimit) / 100 : card.balance / 100,
    debt: card.creditLimit > 0 ? Math.max(0, card.creditLimit - card.balance) / 100 : 0 };
}
export function exactMonoAccount(accounts: any[], monoId: unknown) {
  if (typeof monoId !== 'string' || !monoId) return null;
  const matches = accounts.filter(a => a.bank === 'mono' && a.mono_account_id === monoId);
  return matches.length === 1 ? matches[0] : null;
}
export function registrationTarget(accounts: any[], owner: string, card: any, last4?: string) {
  const exact = accounts.filter(a => a.mono_account_id === card.id);
  if (exact.length) {
    if (exact.length !== 1 || exact[0].user_id !== owner || exact[0].bank !== 'mono') throw new Error('account_owner_conflict');
    return exact[0];
  }
  const manual = accounts.filter(a => a.user_id === owner && a.bank === 'mono' && !a.mono_account_id && last4 && a.card_last4 === last4);
  if (manual.length > 1) throw new Error('ambiguous_account');
  return manual[0] || null;
}
// Monobank мігрує рахунок на новий id: старий зникає з client-info, на ньому «Зарахування коштів в рамках міграції рахунку».
// Перепривʼязка лише однозначна: старого id у списку немає, а серед гривневих карток не ФОП рівно одна вільна
// (не привʼязана до жодного рахунку) з тим самим видом ліміту, що й у збереженого. Інакше null: не вгадуємо.
export function migratedMonoAccount(cards: any[], acc: any, linkedIds: string[]) {
  const uah = (cards || []).filter(a => a?.id && a.currencyCode === 980);
  if (!acc?.mono_account_id || uah.some(a => a.id === acc.mono_account_id)) return null;
  const credit = Number(acc.credit_limit) > 0;
  const same = uah.filter(a => !linkedIds.includes(a.id) && a.type !== 'fop' && (Number(a.creditLimit) > 0) === credit);
  return same.length === 1 ? same[0] : null;
}
// Рядки transactions із виписки Monobank (той самий вигляд, що в mono-webhook і mono-backfill)
export function statementRows(items: any[], userId: string, accountId: number) {
  return (Array.isArray(items) ? items : []).filter((si: any) => si?.id).map((si: any) => ({
    user_id: userId, amount: Math.abs(si.amount) / 100, type: si.amount < 0 ? 'expense' : 'income',
    description: si.description || null, source: 'mono', source_id: String(si.id), mcc: si.mcc || null,
    date: new Date(si.time * 1000).toISOString().split('T')[0], account_id: accountId,
  }));
}
