// Таблиці бота моноширинним блоком <pre> (parse_mode HTML). Перша колонка ліворуч, решта праворуч.
// Одиниця пишеться один раз у підписі над таблицею, у клітинках лише числа.
// Підсумки рахуються з показаних клітинок (hrn/sumShown), щоб калькулятор сходився з рядками.

export const esc = (t: string) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const groups = (s: string) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

// Копійки, округлені до гривні так само, як їх показує клітинка
export const hrn = (c: number) => (c < 0 ? -1 : 1) * Math.round(Math.abs(c) / 100) * 100;
// Гривні без копійок; пробіл тисяч звичайний, щоб колонки рівнялись
export const uah = (c: number) => (c < 0 ? '-' : '') + groups(String(Math.round(Math.abs(c) / 100)));
// Гривні з копійками: завжди два знаки
export const kop = (c: number) => {
  const a = Math.abs(Math.round(c));
  return (c < 0 ? '-' : '') + groups(String(Math.floor(a / 100))) + ',' + String(a % 100).padStart(2, '0');
};
// Одна точність на колонку: копійки, лише якщо хоч одне значення їх має
export const cellFormat = (values: number[]) => values.some((c) => Math.round(c) % 100 !== 0) ? kop : uah;

const MAX_WIDTH = 40;
const len = (s: string) => Array.from(s).length;
const padEnd = (s: string, w: number) => s + ' '.repeat(Math.max(0, w - len(s)));
const padStart = (s: string, w: number) => ' '.repeat(Math.max(0, w - len(s))) + s;

// Таблиця для картинки (bot-table-svg.ts). preTable запамʼятовує її за готовим HTML, тож відправник (rich-send.ts)
// знаходить таблицю в тексті звіту й надсилає картинкою з сіткою; формат текстових звітів не змінюється.
// kind: total жирний рядок із заливкою, group підзаголовок групи на всю ширину, mark жирний рядок без заливки (сьогодні).
export type RowKind = 'row' | 'total' | 'group' | 'mark';
export type TableSpec = { head: string[]; rows: string[][]; kinds: RowKind[]; aligns: ('l' | 'r')[] };
const SPECS = new Map<string, TableSpec>();
export const tableSpecOf = (html: string): TableSpec | undefined => SPECS.get(html);
export type TableImage = { head?: string[]; rows?: string[][]; kinds?: RowKind[]; aligns?: ('l' | 'r')[] };
const autoKind = (r: string[]): RowKind => r[0] === 'Разом' || r[0] === 'Баланс' ? 'total' : r.length > 1 && r.slice(1).every((c) => !c) ? 'group' : 'row';
export function registerTable(html: string, spec: TableSpec): string {
  if (SPECS.size > 500) SPECS.clear();
  SPECS.set(html, spec);
  return html;
}

// rows: перша клітинка назва, решта числа текстом. Назва довша за nameMax стоїть окремим рядком, числа рядком нижче.
// head: шапка (порожня перша клітинка допустима); без шапки таблиця йде одразу з рядків.
export function preTable(head: string[] | null, rows: string[][], nameMax = 14, image: TableImage = {}): string {
  if (!rows.length) return '';
  const all = head ? [head, ...rows] : rows;
  const cols = Math.max(...all.map((r) => r.length));
  const w = Array.from({ length: cols }, (_, i) => i === 0 ? 0 : Math.max(...all.map((r) => len(r[i] || ''))));
  // Рядок не ширший за екран телефона (40 знаків): назва звужується, довші назви стають окремим рядком
  const rest = w.slice(1).reduce((n, x) => n + x + 2, 0);
  const w0 = Math.max(1, Math.min(nameMax, MAX_WIDTH - rest, Math.max(...all.map((r) => len(r[0] || '')))));
  w[0] = w0;
  const line = (r: string[]) => (padEnd(r[0] || '', w0) + '  ' +
    w.slice(1).map((x, i) => padStart(r[i + 1] || '', x)).join('  ')).replace(/\s+$/, '');
  const out: string[] = [];
  // Пробіли в кінці шапки: кнопка копіювання Telegram лягає на них, а не на останній підпис
  if (head) out.push(line(head) + '    ');
  for (const r of rows) {
    if (len(r[0] || '') > w0) out.push(r[0], line(['', ...r.slice(1)]));
    else out.push(line(r));
  }
  const html = '<pre>' + esc(out.join('\n')) + '</pre>';
  // Картинка: відступи назв прибрано, вкладеність показують сітка й рядок групи
  const iRows = (image.rows || rows).map((r) => [String(r[0] || '').trim(), ...r.slice(1)]);
  const iHead = image.head || head || [];
  const n = Math.max(iHead.length, ...iRows.map((r) => r.length));
  return registerTable(html, {
    head: iHead, rows: iRows,
    kinds: image.kinds || iRows.map(autoKind),
    aligns: image.aligns || Array.from({ length: n }, (_, i) => i === 0 ? 'l' : 'r'),
  });
}
