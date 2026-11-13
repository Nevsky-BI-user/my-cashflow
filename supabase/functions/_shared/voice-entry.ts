// Розпізнаний голос → запис операції або питання. Розпізнавач пише суми цифрами («500 гривень продукти»,
// «плюс 65 459 гривень зарплата»), тож тут лише прибираються слова-обгортки і знаходиться сума з описом.
// Запис голосом іде в бот тільки через підтвердження «✅ Так, додати»: помилка розпізнавання не потрапляє в облік мовчки.
export type VoiceEntry = { type: 'income' | 'expense'; amount: string; description: string };

// Ознаки питання: тоді це не запис, навіть якщо є число («скільки витратили на продукти за 2 тижні»)
const QUESTION = /\?|(?:^|[\s,])(скільки|скіки|скока|сколько|який|яка|яке|які|якої|якого|коли|чи|що|шо|де|куди|навіщо|чому|як|покажи|розкажи|порахуй|підкажи|назви|баланс|залишок|лишилось|лишилося|осталось)(?=[\s,.!?]|$)/i;
const NUM = String.raw`(?:\d{1,3}(?:[   .,]\d{3})+|\d+)(?:[.,]\d{1,2})?`;
const CURRENCY = String.raw`(?:гривень|гривні|гривня|гривен|гривни|грн\.?|₴|uah)`;
const KOP = String.raw`(?:\s+(\d{1,2})\s+(?:копійок|копійки|копійка|копеек|копейки|коп\.?))?`;
const LEAD = /^(?:(?:будь\s+ласка|запиши|записати|додай|додати|внеси|внести|витрата|витрату|витратив|витратила|витратили|потратив|потратила|купив|купила|заплатив|заплатила)\s+)+/i;
const INCOME_LEAD = /^(?:(?:дохід|доход|прихід|надходження|отримав|отримала|отримали|прийшло|прийшла|прийшли|плюс)\s+)+/i;
const PREP = /^(?:на|за|в|у)\s+/i;

// Сума з тексту розпізнавача: групи тисяч через пробіл, крапку чи кому лише по три цифри; дробова частина 1-2 цифри
export function voiceAmount(raw: string, kop?: string): string | null {
  let s = raw.replace(/[   ]/g, ' ').trim();
  const thousands = s.match(/^(\d{1,3})((?:[ .,]\d{3})+)(?:[.,](\d{1,2}))?$/);
  if (thousands) s = thousands[1] + thousands[2].replace(/[ .,]/g, '') + (thousands[3] ? '.' + thousands[3] : '');
  else s = s.replace(',', '.');
  if (!/^\d+(?:\.\d{1,2})?$/.test(s)) return null;
  if (kop && !s.includes('.')) s += '.' + kop.padStart(2, '0');
  return Number(s) > 0 ? s : null;
}

export function parseVoiceEntry(text: string): VoiceEntry | null {
  let s = String(text || '').normalize('NFKC').replace(/[   ]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[.!…]+$/, '').trim();
  if (!s || s.length > 200 || QUESTION.test(s)) return null;
  let type: 'income' | 'expense' = 'expense';
  s = s.replace(LEAD, '');
  if (/^\+\s*/.test(s)) { type = 'income'; s = s.replace(/^\+\s*/, ''); }
  if (INCOME_LEAD.test(s)) { type = 'income'; s = s.replace(INCOME_LEAD, ''); }
  if (/^(?:мінус|-)\s*/i.test(s)) s = s.replace(/^(?:мінус|-)\s*/i, '');
  // Сума спершу: «500 гривень на продукти», «65 459 гривень зарплата»
  let m = s.match(new RegExp(`^(${NUM})\\s*${CURRENCY}?${KOP}\\s*,?\\s+(.+)$`, 'i'));
  let amount: string | null = null, desc = '';
  if (m) { amount = voiceAmount(m[1], m[2]); desc = m[3]; }
  else {
    // Опис спершу: «продукти 500 гривень»
    m = s.match(new RegExp(`^(.+?)\\s*,?\\s+(${NUM})\\s*${CURRENCY}?${KOP}$`, 'i'));
    if (m) { amount = voiceAmount(m[2], m[3]); desc = m[1]; }
  }
  if (!amount) return null;
  desc = desc.replace(PREP, '').replace(/^[,.:;\s]+|[,.:;\s]+$/g, '').trim();
  // Опис має містити літери і не починатися з цифри (як у текстовому записі бота)
  if (!desc || /^\d/.test(desc) || !/\p{L}/u.test(desc) || new RegExp(`^${CURRENCY}$`, 'i').test(desc)) return null;
  if (/зарплат|аванс|премі/i.test(desc) && /^(?:плюс|\+)/i.test(String(text).trim())) type = 'income';
  return { type, amount, description: desc.slice(0, 120) };
}
