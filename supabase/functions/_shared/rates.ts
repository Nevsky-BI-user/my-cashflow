// Курси валют для накопичень: розбір відповідей НБУ і ПриватБанку в рядки таблиці exchange_rates.
// Чисті функції без мережі: їх ганяють node-тести (spec/rates.test.cjs), а rates-refresh лише кличе.

export const RATE_CCYS = ['USD', 'EUR'] as const;
export type RateCcy = typeof RATE_CCYS[number];
export type RateSource = 'nbu' | 'privat';
export type RateRow = { ccy: RateCcy; source: RateSource; buy: number; sale: number; updated_at: string };

// Офіційний курс НБУ: https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json
// [{cc:'USD', rate:45.3222, exchangedate:'12.11.2026'}, ...]
export const NBU_URL = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json';
// Готівковий курс ПриватБанку у відділеннях (coursid=5): [{ccy:'USD', base_ccy:'UAH', buy:'45.35000', sale:'45.95000'}]
export const PRIVAT_URL = 'https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5';

// Додатне скінченне число або null: рядок '45.35000' теж приймається
export const posNum = (v: unknown): number | null => {
  if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
  const n = typeof v === 'number' ? v : Number(String(v).trim().replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : null;
};

const isCcy = (c: unknown): c is RateCcy => RATE_CCYS.includes(String(c).toUpperCase() as RateCcy);

// НБУ: один курс, buy = sale = rate. Невалідні або відсутні валюти просто не потрапляють у результат.
export const parseNbu = (json: unknown, at: string): RateRow[] => {
  if (!Array.isArray(json)) return [];
  const out: RateRow[] = [];
  for (const ccy of RATE_CCYS) {
    const it = json.find((x: any) => x && String(x.cc).toUpperCase() === ccy);
    const rate = posNum(it && (it as any).rate);
    if (rate !== null) out.push({ ccy, source: 'nbu', buy: rate, sale: rate, updated_at: at });
  }
  return out;
};

// ПриватБанк: купівля банком (buy) і продаж банком (sale); пара з sale < buy відкидається як зіпсована
export const parsePrivat = (json: unknown, at: string): RateRow[] => {
  if (!Array.isArray(json)) return [];
  const out: RateRow[] = [];
  for (const ccy of RATE_CCYS) {
    const it = json.find((x: any) => x && isCcy(x.ccy) && String(x.ccy).toUpperCase() === ccy && String(x.base_ccy || 'UAH').toUpperCase() === 'UAH');
    const buy = posNum(it && (it as any).buy), sale = posNum(it && (it as any).sale);
    if (buy !== null && sale !== null && sale >= buy) out.push({ ccy, source: 'privat', buy, sale, updated_at: at });
  }
  return out;
};
