// Таблиці бота картинкою (власник 17.11.2026: «сітки немає», «тотал не виділено ніяк»): SVG з сіткою, жирний рядок «Разом»
// із заливкою, підзаголовки груп на всю ширину. Кілька таблиць одного звіту стоять одна під одною зі спільною шириною.
// Чиста функція без I/O; у PNG перетворює render-png.ts (шрифт Inter).
import { FONT } from './bot-charts.ts';
import type { TableSpec } from './bot-table.ts';

const C = { bg: '#F2F2F7', card: '#FFFFFF', grid: '#E5E5EA', frame: '#C7C7CC', text: '#1C1C1E', muted: '#6C6C70', total: '#ECECF1', group: '#F6F6F9', neg: '#FF3B30' };
const SIZE = 30, ROW = 58, PADX = 22, GAP = 28, MARGIN = 24, RADIUS = 18;
const esc = (s: string) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Ширина тексту Inter у частках кегля (оцінка з запасом: колонка трохи ширша, ніж треба, але текст не налазить)
function em(ch: string): number {
  if (/[0-9₴]/.test(ch)) return 0.64;
  if (ch === ' ' || ch === ' ') return 0.29;
  if (/[.,:;'ʼ·|!]/.test(ch)) return 0.3;
  if (/[()\[\]\-]/.test(ch)) return 0.4;
  if (/[%ЖШЩЮМWmшщжюмФф]/.test(ch)) return 0.9;
  if (/[A-ZА-ЯІЇЄҐ]/.test(ch)) return 0.72;
  return 0.6;
}
export const textWidth = (s: string, size = SIZE, bold = false) => Array.from(s).reduce((n, ch) => n + em(ch), 0) * size * (bold ? 1.07 : 1);

const t = (x: number, y: number, s: string, o: { bold?: boolean; fill?: string; anchor?: string; size?: number } = {}) =>
  `<text x="${Math.round(x)}" y="${Math.round(y)}" font-family="${FONT}" font-size="${o.size || SIZE}" font-weight="${o.bold ? 700 : 400}"` +
  ` fill="${o.fill || C.text}"${o.anchor ? ` text-anchor="${o.anchor}"` : ''}>${esc(s)}</text>`;

// Ширини колонок однієї таблиці; перша колонка розтягується до спільної ширини картинки
function widths(sp: TableSpec): number[] {
  const n = Math.max(sp.head.length, ...sp.rows.map((r) => r.length));
  return Array.from({ length: n }, (_, i) => {
    const cells = [{ s: sp.head[i] || '', b: true }, ...sp.rows.map((r, k) => ({ s: sp.kinds[k] === 'group' && i === 0 ? '' : r[i] || '', b: sp.kinds[k] !== 'row' }))];
    return Math.ceil(Math.max(...cells.map((c) => textWidth(c.s, SIZE, c.b)))) + PADX * 2;
  });
}

export function tablesSvg(specs: TableSpec[]): string {
  const ws = specs.map(widths);
  // Таблиці з однаковою кількістю колонок стоять одна під одною зі спільними межами: числові колонки беруть найширшу
  for (const w of ws) for (const v of ws) if (v !== w && v.length === w.length) for (let c = 1; c < w.length; c++) w[c] = Math.max(w[c], v[c]);
  // Підзаголовки груп ідуть на всю ширину: таблиця не вужча за найдовший із них
  const groupW = specs.map((sp) => Math.max(0, ...sp.rows.filter((_, k) => sp.kinds[k] === 'group').map((r) => Math.ceil(textWidth(r[0] || '', SIZE, true)) + PADX * 2)));
  const inner = Math.max(560, ...ws.map((w, i) => Math.max(groupW[i], w.reduce((a, b) => a + b, 0))));
  const W = inner + MARGIN * 2;
  const parts: string[] = [];
  let y = MARGIN;
  specs.forEach((sp, i) => {
    const w = ws[i].slice();
    w[0] += inner - w.reduce((a, b) => a + b, 0);
    const xs = w.reduce((acc, x) => [...acc, acc[acc.length - 1] + x], [MARGIN]);
    const hasHead = sp.head.some((h) => h);
    const rows = sp.rows.length + (hasHead ? 1 : 0), H = rows * ROW, top = y;
    parts.push(`<rect x="${MARGIN}" y="${top}" width="${inner}" height="${H}" rx="${RADIUS}" fill="${C.card}" stroke="${C.frame}" stroke-width="2"/>`);
    parts.push(`<clipPath id="c${i}"><rect x="${MARGIN}" y="${top}" width="${inner}" height="${H}" rx="${RADIUS}"/></clipPath><g clip-path="url(#c${i})">`);
    let ry = top;
    const base = (yy: number) => yy + ROW / 2 + SIZE * 0.36;
    const cellX = (c: number) => sp.aligns[c] === 'l' ? xs[c] + PADX : xs[c + 1] - PADX;
    if (hasHead) {
      sp.head.forEach((h, c) => h && parts.push(t(cellX(c), base(ry), h, { bold: true, fill: C.muted, anchor: sp.aligns[c] === 'l' ? undefined : 'end', size: SIZE - 3 })));
      ry += ROW;
      parts.push(`<line x1="${MARGIN}" y1="${ry}" x2="${MARGIN + inner}" y2="${ry}" stroke="${C.frame}" stroke-width="2"/>`);
    }
    sp.rows.forEach((r, k) => {
      const kind = sp.kinds[k];
      if (kind === 'total') parts.push(`<rect x="${MARGIN}" y="${ry}" width="${inner}" height="${ROW}" fill="${C.total}"/>`);
      if (kind === 'group') parts.push(`<rect x="${MARGIN}" y="${ry}" width="${inner}" height="${ROW}" fill="${C.group}"/>`);
      if (k > 0 || hasHead) {
        const strong = kind === 'total';
        parts.push(`<line x1="${MARGIN}" y1="${ry}" x2="${MARGIN + inner}" y2="${ry}" stroke="${strong ? C.frame : C.grid}" stroke-width="${strong ? 2 : 1.5}"/>`);
      }
      if (kind === 'group') parts.push(t(xs[0] + PADX, base(ry), r[0] || '', { bold: true }));
      else r.forEach((s, c) => s && parts.push(t(cellX(c), base(ry), s, {
        bold: kind === 'total' || kind === 'mark', anchor: sp.aligns[c] === 'l' ? undefined : 'end', fill: c > 0 && /^-\d/.test(s) ? C.neg : C.text,
      })));
      ry += ROW;
    });
    // Вертикальні лінії сітки між колонками; у рядку групи їх немає
    for (let c = 1; c < w.length; c++) {
      let yy = top;
      const segs: [number, number][] = [];
      const kinds = [...(hasHead ? ['head'] : []), ...sp.kinds];
      for (const kd of kinds) {
        if (kd !== 'group') segs.push([yy, yy + ROW]);
        yy += ROW;
      }
      for (const [a, b] of segs) parts.push(`<line x1="${xs[c]}" y1="${a}" x2="${xs[c]}" y2="${b}" stroke="${C.grid}" stroke-width="1.5"/>`);
    }
    parts.push('</g>');
    y += H + GAP;
  });
  const H = y - GAP + MARGIN;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="${C.bg}"/>${parts.join('')}</svg>`;
}
