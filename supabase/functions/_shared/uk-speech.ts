// Текст відповіді бота → текст для синтезу мови (HolosTTS не читає цифр і символів).
// Суми, дати, відсотки, дні й кількості словами з узгодженням роду й числа. Чиста функція, без мережі.
// Принцип: числа лишаються в називному відмінку (після двокрапки, як підмет), дати в родовому («двадцять пʼятого листопада»),
// бо обидва звучать природно без відмінювання числівників. Копійки вимовляються, коли вони є (сума частин = загальна сума).

type Gender = 'm' | 'f' | 'n';

const UNITS: Record<Gender, string[]> = {
  m: ['', 'один', 'два', 'три', 'чотири', 'пʼять', 'шість', 'сім', 'вісім', 'девʼять'],
  f: ['', 'одна', 'дві', 'три', 'чотири', 'пʼять', 'шість', 'сім', 'вісім', 'девʼять'],
  n: ['', 'одне', 'два', 'три', 'чотири', 'пʼять', 'шість', 'сім', 'вісім', 'девʼять'],
};
const TEENS = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 'пʼятнадцять', 'шістнадцять', 'сімнадцять', 'вісімнадцять', 'девʼятнадцять'];
const TENS = ['', '', 'двадцять', 'тридцять', 'сорок', 'пʼятдесят', 'шістдесят', 'сімдесят', 'вісімдесят', 'девʼяносто'];
const HUNDREDS = ['', 'сто', 'двісті', 'триста', 'чотириста', 'пʼятсот', 'шістсот', 'сімсот', 'вісімсот', 'девʼятсот'];

// Форма іменника після числа: 1, 21 → one; 2-4, 22-24 → few; решта (і 11-14) → many
export function plural(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a >= 11 && a <= 14) return many;
  if (b === 1) return one;
  if (b >= 2 && b <= 4) return few;
  return many;
}

function triad(n: number, g: Gender): string[] {
  const out: string[] = [];
  const h = Math.floor(n / 100), r = n % 100;
  if (h) out.push(HUNDREDS[h]);
  if (r >= 10 && r < 20) out.push(TEENS[r - 10]);
  else {
    if (r >= 20) out.push(TENS[Math.floor(r / 10)]);
    if (r % 10) out.push(UNITS[g][r % 10]);
  }
  return out;
}

const SCALES: { value: number; g: Gender; forms: [string, string, string] }[] = [
  { value: 1e9, g: 'm', forms: ['мільярд', 'мільярди', 'мільярдів'] },
  { value: 1e6, g: 'm', forms: ['мільйон', 'мільйони', 'мільйонів'] },
  { value: 1e3, g: 'f', forms: ['тисяча', 'тисячі', 'тисяч'] },
];

// Ціле число словами в називному відмінку; «тисяча», «мільйон» без «одна/один» на початку
export function numberWords(value: number, g: Gender = 'm'): string {
  if (!Number.isFinite(value)) return '';
  let n = Math.trunc(Math.abs(value));
  if (n === 0) return 'нуль';
  const words: string[] = value < 0 ? ['мінус'] : [];
  for (const s of SCALES) {
    const k = Math.floor(n / s.value);
    if (k) {
      const w = triad(k, s.g);
      if (!(k === 1 && words.length === (value < 0 ? 1 : 0))) words.push(...w);
      words.push(plural(k, ...s.forms));
      n %= s.value;
    }
  }
  if (n) words.push(...triad(n, g));
  return words.join(' ');
}

// Сума в копійках словами: «дві тисячі триста гривень пʼятдесят копійок»; копійки лише ненульові
export function moneyWords(cents: number): string {
  const neg = cents < 0, abs = Math.round(Math.abs(cents));
  const uah = Math.floor(abs / 100), kop = abs % 100;
  const parts: string[] = [];
  if (uah || !kop) parts.push(`${numberWords(uah, 'f')} ${plural(uah, 'гривня', 'гривні', 'гривень')}`);
  if (kop) parts.push(`${numberWords(kop, 'f')} ${plural(kop, 'копійка', 'копійки', 'копійок')}`);
  return (neg ? 'мінус ' : '') + parts.join(' ');
}

const ORD_UNITS = ['', 'першого', 'другого', 'третього', 'четвертого', 'пʼятого', 'шостого', 'сьомого', 'восьмого', 'девʼятого'];
const ORD_TEENS = ['десятого', 'одинадцятого', 'дванадцятого', 'тринадцятого', 'чотирнадцятого', 'пʼятнадцятого', 'шістнадцятого', 'сімнадцятого', 'вісімнадцятого', 'девʼятнадцятого'];
const MONTHS_GEN = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];

// День місяця порядковим числівником у родовому відмінку: 25 → «двадцять пʼятого»
export function dayOrdinalGen(d: number): string {
  if (d < 10) return ORD_UNITS[d];
  if (d < 20) return ORD_TEENS[d - 10];
  const t = Math.floor(d / 10), u = d % 10;
  if (!u) return t === 2 ? 'двадцятого' : 'тридцятого';
  return `${TENS[t]} ${ORD_UNITS[u]}`;
}

// Дата «25.11» → «двадцять пʼятого листопада»; рік у мові не називаємо (він видно в тексті)
export function dateWords(day: number, month: number): string | null {
  if (!(day >= 1 && day <= 31 && month >= 1 && month <= 12)) return null;
  return `${dayOrdinalGen(day)} ${MONTHS_GEN[month - 1]}`;
}

// Розбір суми з тексту бота: «12 345,67», «1 470,5» (Intl дає 1-2 знаки після коми), «-3 000»
const NBSP = /[   ]/g;
export function parseMoneyCents(raw: string): number | null {
  const s = raw.replace(NBSP, ' ').replace(/\s+/g, '').replace('−', '-');
  const m = s.match(/^(-?)(\d+)(?:[.,](\d{1,2}))?$/);
  if (!m) return null;
  const kop = m[3] ? Number(m[3].padEnd(2, '0')) : 0;
  const cents = Number(m[2]) * 100 + kop;
  return m[1] ? -cents : cents;
}

// Жіночий рід іменника після числа (для «одна», «дві»): лише слова, що трапляються у відповідях бота
const FEMININE = /^(операці|гривн|копійк|копійок|тисяч|категорі|позиці|покупк|витрат|розстрочк|розстрочок|картк|карток|ціл)/i;
const NEUTER = /^(місяц)/i; // «місяць» чоловічого роду; запас для середнього, якщо зʼявиться

function bareNumber(raw: string, next: string): string {
  const s = raw.replace(NBSP, '').replace(/\s+/g, '');
  const m = s.match(/^(-?)(\d+)(?:[.,](\d+))?$/);
  if (!m) return raw;
  const g: Gender = FEMININE.test(next) ? 'f' : NEUTER.test(next) ? 'n' : 'm';
  const int = numberWords(Number(m[2]), m[3] ? 'f' : g);
  const head = (m[1] ? 'мінус ' : '') + int;
  if (!m[3]) return head;
  // Дробове число: «дванадцять кома пʼять»
  return `${head} кома ${m[3].split('').map((c) => numberWords(Number(c), 'f')).join(' ')}`;
}

// Головна функція: рядки відповіді → один текст для синтезу
export function toSpeech(text: string): string {
  let s = String(text || '').replace(NBSP, ' ');
  // HTML і службові символи
  s = s.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, ' і ').replace(/&lt;|&gt;/g, ' ');
  s = s.replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, ' ');
  // Діапазон дат «06.11-20.11» → «з шостого листопада до двадцятого листопада»
  s = s.replace(/(?<![\d.])(\d{1,2})\.(\d{1,2})(?:\.\d{4})?\s*-\s*(\d{1,2})\.(\d{1,2})(?:\.\d{4})?(?![\d.])/g, (all, d1, m1, d2, m2) => {
    const a = dateWords(+d1, +m1), b = dateWords(+d2, +m2);
    if (!a || !b) return all;
    return m1 === m2 ? `з ${dayOrdinalGen(+d1)} до ${b}` : `з ${a} до ${b}`;
  });
  // Дата «25.11» або «25.11.2026»
  s = s.replace(/(?<![\d.,])(\d{1,2})\.(\d{1,2})(?:\.\d{4})?(?![\d,]|\.\d)/g, (all, d, m) => dateWords(+d, +m) ?? all);
  // Сума з гривнею: «12 345,67 ₴», «300 ₴/день», «500 грн»
  s = s.replace(/(?:(-|−)\s?)?(\d{1,3}(?:[ ]\d{3})+|\d+)(?:,(\d{1,2}))?\s?(?:₴|грн\.?)(\/день)?/g, (all, sign, int, frac, perDay) => {
    const cents = parseMoneyCents(`${sign ? '-' : ''}${int}${frac ? ',' + frac : ''}`);
    if (cents == null) return all;
    return moneyWords(cents) + (perDay ? ' на день' : '');
  });
  // Відсоток: «15%», «+12,5%»
  s = s.replace(/([+-])?(\d+(?:,\d+)?)\s?%/g, (all, sign, num) => {
    const whole = !num.includes(',');
    const words = bareNumber(num, whole ? 'відсоток' : '');
    const unit = whole ? plural(Number(num), 'відсоток', 'відсотки', 'відсотків') : 'відсотка';
    return `${sign === '+' ? 'плюс ' : sign === '-' ? 'мінус ' : ''}${words} ${unit}`;
  });
  // Скорочення днів: «13 дн.» → «тринадцять днів»
  s = s.replace(/(\d+)\s?дн\.?(?![а-яіїєґ])/gi, (all, n) => `${numberWords(Number(n))} ${plural(Number(n), 'день', 'дні', 'днів')}`);
  // «3 × тисяча гривень = …»: кількість платежів, кожен по сумі, разом
  s = s.replace(/(\d+)\s?×\s?/g, (all, n) => `${numberWords(Number(n))} ${plural(Number(n), 'платіж', 'платежі', 'платежів')}, кожен `);
  s = s.replace(/\s=\s/g, ', разом ');
  // Решта чисел: рід за наступним словом
  s = s.replace(/(-)?(\d{1,3}(?:[ ]\d{3})+|\d+)(?:,(\d+))?(\s+)([^\s\d]*)/g, (all, sign, int, frac, sp, next) =>
    bareNumber(`${sign || ''}${int}${frac ? ',' + frac : ''}`, next) + sp + next);
  s = s.replace(/(-)?(\d+)(?:,(\d+))?/g, (all) => bareNumber(all, ''));
  // Розділювачі: «·» і перенос рядка як пауза, стрілки і решта символів геть
  s = s.replace(/\s*·\s*/g, ', ').replace(/\n+/g, '. ').replace(/[↑↓→←⚠️✅❌•*_#|«»"]/g, ' ');
  s = s.replace(/\(\s*/g, ', ').replace(/\s*\)/g, ',');
  s = s.replace(/\s+([,.:;!?])/g, '$1').replace(/([,.:;])\1+/g, '$1').replace(/[,]\s*\./g, '.').replace(/:\s*\./g, '.');
  s = s.replace(/\.\s*,/g, '.').replace(/\s{2,}/g, ' ').trim();
  return s.replace(/^[,.\s]+/, '').replace(/,\s*$/, '.');
}
