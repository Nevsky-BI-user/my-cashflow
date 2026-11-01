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
