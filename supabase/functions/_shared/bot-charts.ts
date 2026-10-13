// SVG для картинок бота: баланс у часі і кільце категорій бюджету. Чисті функції без I/O (рендер у PNG: render-png.ts).
// Текст у SVG лише шрифтом Inter (кирилиця, ₴), без емодзі: емодзі йдуть тільки в текст повідомлень.
import { day, money } from './finance-message.ts';
import type { BalanceSeries, BudgetModel, BudgetRow } from './bot-reports.ts';

export const FONT = 'Inter';
const W = 1080, H = 720;
const C = {
  bg: '#f6f7fb', card: '#ffffff', grid: '#e6e8f0', axis: '#c9cdda', text: '#1f2333', muted: '#6b7083',
  fact: '#5b5bd6', forecast: '#12a594', neg: '#e5484d', negBg: '#fdeeee', pay: '#30a46c', today: '#5b5bd6', max: '#1f8a5b',
};
const esc = (s: string) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const r1 = (n: number) => Math.round(n * 10) / 10;
const DAY = 86400000;
const dn = (d: string) => Date.parse(d + 'T00:00:00Z') / DAY;
// halo: біла обвідка під підписом точки, щоб текст читався поверх ліній
const text = (x: number, y: number, s: string, o: { size?: number; fill?: string; weight?: number; anchor?: string; halo?: boolean } = {}) =>
  `<text x="${r1(x)}" y="${r1(y)}" font-family="${FONT}" font-size="${o.size || 24}" font-weight="${o.weight || 400}" fill="${o.fill || C.text}"` +
  (o.anchor ? ` text-anchor="${o.anchor}"` : '') + (o.halo ? ' stroke="#ffffff" stroke-width="8" stroke-linejoin="round" paint-order="stroke"' : '') + `>${esc(s)}</text>`;
// Підпис осі в тисячах: «-20 тис.», «0», «12,5 тис.»
export function thousands(c: number): string {
  if (c === 0) return '0';
  const v = c / 100000;
  return (v < 0 ? '-' : '') + new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 1 }).format(Math.abs(v)) + ' тис.';
}
// Крок сітки: 1, 2, 2,5, 5 × 10^n, 4-7 інтервалів
function niceStep(span: number): number {
  const raw = span / 6, p = Math.pow(10, Math.floor(Math.log10(Math.max(1, raw))));
  for (const k of [1, 2, 2.5, 5, 10]) if (k * p >= raw) return k * p;
  return 10 * p;
}

export type ChartModel = { svg: string; todayXY: [number, number]; minXY: [number, number]; maxXY: [number, number]; yZero: number | null };

export function balanceChartSvg(s: BalanceSeries): ChartModel {
  const L = 130, R = 40, T = 140, B = 92, pw = W - L - R, ph = H - T - B;
  const all = [...s.past, ...s.future];
  const x0 = dn(s.from), x1 = Math.max(dn(s.to), x0 + 1);
  const vals = all.map((p) => p.cents);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) hi = lo + 100000;
  const pad = (hi - lo) * 0.16;
  lo -= pad * 1.4;
  hi += pad;
  const step = niceStep(hi - lo);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const X = (d: string) => L + (dn(d) - x0) / (x1 - x0) * pw;
  const Y = (c: number) => T + (hi - c) / (hi - lo) * ph;
  const out: string[] = [];
  out.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  out.push(`<rect width="${W}" height="${H}" fill="${C.bg}"/>`);
  out.push(`<rect x="20" y="20" width="${W - 40}" height="${H - 40}" rx="28" fill="${C.card}"/>`);
  out.push(text(48, 74, 'Баланс: власні мінус борг кредиток', { size: 32, weight: 600 }));
  // легенда
  let lx = 48;
  const ly = 112;
  out.push(`<line x1="${lx}" y1="${ly - 8}" x2="${lx + 40}" y2="${ly - 8}" stroke="${C.fact}" stroke-width="5" stroke-linecap="round"/>`, text(lx + 52, ly, 'факт', { size: 22, fill: C.muted }));
  lx += 130;
  out.push(`<line x1="${lx}" y1="${ly - 8}" x2="${lx + 40}" y2="${ly - 8}" stroke="${C.forecast}" stroke-width="5" stroke-dasharray="10 8"/>`, text(lx + 52, ly, 'прогноз', { size: 22, fill: C.muted }));
  lx += 170;
  out.push(`<circle cx="${lx + 8}" cy="${ly - 8}" r="8" fill="${C.pay}"/>`, text(lx + 26, ly, 'виплата', { size: 22, fill: C.muted }));
  lx += 150;
  out.push(`<circle cx="${lx + 8}" cy="${ly - 8}" r="8" fill="${C.neg}"/>`, text(lx + 26, ly, 'мінімум', { size: 22, fill: C.muted }));
  // зона мінусу
  const yZero = lo < 0 && hi > 0 ? Y(0) : null;
  if (yZero != null) out.push(`<rect x="${L}" y="${r1(yZero)}" width="${pw}" height="${r1(T + ph - yZero)}" fill="${C.negBg}"/>`);
  else if (hi <= 0) out.push(`<rect x="${L}" y="${T}" width="${pw}" height="${ph}" fill="${C.negBg}"/>`);
  // сітка і вісь Y у тисячах
  for (let v = lo; v <= hi + 1; v += step) {
    const y = Y(v);
    out.push(`<line x1="${L}" y1="${r1(y)}" x2="${L + pw}" y2="${r1(y)}" stroke="${v === 0 ? C.axis : C.grid}" stroke-width="${v === 0 ? 3 : 1.5}"/>`);
    out.push(text(L - 14, y + 8, thousands(v), { size: 22, fill: v < 0 ? C.neg : C.muted, anchor: 'end' }));
  }
  // вісь X: дати з кроком, щоб вмістилось до 8 підписів; сьогодні окремо
  const total = Math.round(x1 - x0), every = Math.max(1, Math.ceil(total / 7));
  for (let i = 0; i <= total; i += every) {
    const d = new Date((x0 + i) * DAY).toISOString().slice(0, 10), x = X(d);
    if (Math.abs(x - X(s.today.date)) < 50) continue;
    out.push(`<line x1="${r1(x)}" y1="${T + ph}" x2="${r1(x)}" y2="${T + ph + 8}" stroke="${C.axis}" stroke-width="2"/>`, text(x, T + ph + 40, day(d), { size: 22, fill: C.muted, anchor: 'middle' }));
  }
  const tx = X(s.today.date);
  out.push(`<line x1="${r1(tx)}" y1="${T}" x2="${r1(tx)}" y2="${T + ph}" stroke="${C.axis}" stroke-width="2" stroke-dasharray="4 6"/>`);
  out.push(text(tx, T + ph + 40, day(s.today.date), { size: 22, fill: C.today, anchor: 'middle', weight: 600 }));
  // лінії: факт суцільна індиго, прогноз пунктир бірюзою; мінус показують червона зона і червоні підписи
  const path = (pts: { date: string; cents: number }[]) => pts.map((p, i) => `${i ? 'L' : 'M'}${r1(X(p.date))} ${r1(Y(p.cents))}`).join(' ');
  if (s.past.length > 1) out.push(`<path d="${path(s.past)}" fill="none" stroke="${C.fact}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>`);
  if (s.future.length) out.push(`<path d="${path([s.today, ...s.future])}" fill="none" stroke="${C.forecast}" stroke-width="5" stroke-dasharray="14 10" stroke-linejoin="round"/>`);
  // виплати
  for (const p of s.payouts) out.push(`<circle cx="${r1(X(p.date))}" cy="${r1(Y(p.cents))}" r="9" fill="${C.pay}" stroke="#fff" stroke-width="3"/>`);
  // мінімум, максимум і сьогодні; мін і макс лише числом, сьогодні виділене підписом
  const todayXY: [number, number] = [tx, Y(s.today.cents)];
  const minXY: [number, number] = [X(s.min.date), Y(s.min.cents)];
  const clampX = (x: number, w: number) => Math.min(L + pw - w / 2, Math.max(L + w / 2, x));
  const sameAsToday = s.min.date === s.today.date;
  if (!sameAsToday) {
    out.push(`<circle cx="${r1(minXY[0])}" cy="${r1(minXY[1])}" r="10" fill="${C.neg}" stroke="#fff" stroke-width="3"/>`);
    const mx = clampX(minXY[0], 230), below = minXY[1] + 78 < T + ph + 4;
    const my = below ? minXY[1] + 42 : minXY[1] - 52;
    out.push(text(mx, my, money(s.min.cents), { size: 28, weight: 600, fill: C.neg, anchor: 'middle', halo: true }));
  }
  const maxXY: [number, number] = [X(s.max.date), Y(s.max.cents)];
  if (s.max.date !== s.today.date && s.max.date !== s.min.date) {
    out.push(`<circle cx="${r1(maxXY[0])}" cy="${r1(maxXY[1])}" r="10" fill="${C.max}" stroke="#fff" stroke-width="3"/>`);
    const ax = clampX(maxXY[0], 230), up = maxXY[1] - 40 > T - 10;
    out.push(text(ax, up ? maxXY[1] - 24 : maxXY[1] + 42, money(s.max.cents), { size: 28, weight: 600, fill: C.max, anchor: 'middle', halo: true }));
  }
  out.push(`<circle cx="${r1(todayXY[0])}" cy="${r1(todayXY[1])}" r="12" fill="${sameAsToday ? C.neg : C.today}" stroke="#fff" stroke-width="4"/>`);
  const tX = clampX(todayXY[0], 240), above = todayXY[1] - 76 > T - 10;
  const tY = above ? todayXY[1] - 52 : todayXY[1] + 46;
  out.push(text(tX, tY, sameAsToday ? 'Сьогодні, мінімум' : 'Сьогодні', { size: 22, fill: C.muted, anchor: 'middle', halo: true }));
  out.push(text(tX, tY + 30, money(s.today.cents), { size: 30, weight: 600, fill: s.today.cents < 0 ? C.neg : C.text, anchor: 'middle', halo: true }));
  // Кожна виплата це локальний пік: число над точкою (або під нею), якщо не налазить на вже підписані сьогодні, мін і макс
  const busy: [number, number][] = [[tX, tY + 15]];
  if (!sameAsToday) busy.push([clampX(minXY[0], 230), minXY[1] + 78 < T + ph + 4 ? minXY[1] + 42 : minXY[1] - 52]);
  if (s.max.date !== s.today.date && s.max.date !== s.min.date) busy.push([clampX(maxXY[0], 230), maxXY[1] - 40 > T - 10 ? maxXY[1] - 24 : maxXY[1] + 42]);
  for (const p of s.payouts) {
    if (p.date === s.today.date || p.date === s.min.date || p.date === s.max.date) continue;
    const px = clampX(X(p.date), 230), py = Y(p.cents);
    const spot = [py - 24, py + 42].filter((y) => y > T - 10 && y < T + ph + 4)
      .find((y) => busy.every(([bx, by]) => Math.abs(bx - px) > 210 || Math.abs(by - y) > 40));
    if (spot == null) continue;
    busy.push([px, spot]);
    out.push(text(px, spot, money(p.cents), { size: 28, weight: 600, fill: C.max, anchor: 'middle', halo: true }));
  }
  out.push('</svg>');
  return { svg: out.join(''), todayXY, minXY, maxXY, yZero };
}

// ---------- Кільце категорій ----------
// v153 (власник: «кольори категорій бота = кольори застосунку»): палітра BUD_PAL, сірі BUD_OTH і BUD_NONE, сталий тон budStable і порядок budRing
// рівно як в index.html (паритет перевіряє spec/budget-ring.test.cjs); колір категорії з БД пастельний, тому тут не береться
export const BUD_PAL: [string, string][] = [['#9c6ef7', '#804ce6'], ['#fbc123', '#e6ab0a'], ['#17cfcf', '#09aeae'], ['#f8596e', '#e82c45'], ['#458cf7', '#2371e7'],
  ['#fa7238', '#f2520d'], ['#26d98b', '#0eaf69'], ['#e568f3', '#ce40dd'], ['#86df20', '#6bb814'], ['#f55cb2', '#e63398']];
const BUD_OTH: [string, string] = ['#94a3b8', '#64748b'], BUD_NONE: [string, string] = ['#9ca3af', '#6b7280'];
const hueOf = (c: string) => {
  const r = parseInt(c.slice(1, 3), 16) / 255, g = parseInt(c.slice(3, 5), 16) / 255, b = parseInt(c.slice(5, 7), 16) / 255;
  const mx = Math.max(r, g, b), d = mx - Math.min(r, g, b);
  if (!d) return 0;
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
};
const budDh = (a: number, b: number) => { const x = Math.abs(hueOf(BUD_PAL[a][0]) - hueOf(BUD_PAL[b][0])) % 360; return Math.min(x, 360 - x); };
// Сталий індекс палітри: числовий id дає (id мінус 1) mod 10, нечислові за місцем серед нечислових
export function budStable(ids: string[]): Record<string, number> {
  const idx: Record<string, number> = {}, N = BUD_PAL.length;
  let k = 0;
  for (const raw of ids) { const id = String(raw); idx[id] = /^\d+$/.test(id) ? ((Number(id) - 1) % N + N) % N : (k++) % N; }
  return idx;
}
// Порядок кільця: першим найбільший, далі найбільший із тих, що відрізняються від попереднього ≥ 40° (з поверненням), сірі в кінці;
// без сірих кільце замкнене (останній із першим теж ≥ 40°); порядку немає: лишається спадний
export function budRing<T extends { id: string }>(segs: T[], idx: Record<string, number>): T[] {
  const col = segs.filter((s) => s.id.slice(0, 2) !== '__'), grey = segs.filter((s) => s.id.slice(0, 2) === '__'), n = col.length;
  if (n < 2) return segs;
  const closed = !grey.length;
  const ok = (a: number, b: number) => { const x = idx[col[a].id], y = idx[col[b].id]; return x == null || y == null || budDh(x, y) >= 40; };
  const used = col.map(() => false), path: number[] = [];
  let steps = 0;
  const dfs = (): boolean => {
    if (path.length === n) return !closed || ok(path[n - 1], path[0]);
    if (++steps > 20000) return false;
    for (let i = 0; i < n; i++) {
      if (used[i] || (path.length && !ok(path[path.length - 1], i))) continue;
      used[i] = true; path.push(i);
      if (dfs()) return true;
      path.pop(); used[i] = false;
    }
    return false;
  };
  return dfs() ? path.map((i) => col[i]).concat(grey) : segs;
}
export type DonutSeg = BudgetRow & { share: number; pct: number; color: string; grad: [string, string] };

// Як budDonutData застосунку: категорії з фактом, дрібні (менше 3%) зливаються в «Інші», якщо їх дві й більше
export function donutSegments(rows: BudgetRow[], ids?: string[]): { total: number; segs: DonutSeg[] } {
  const r = rows.filter((x) => x.fact > 0).sort((a, b) => b.fact - a.fact);
  const total = r.reduce((n, x) => n + x.fact, 0);
  if (!(total > 0)) return { total: 0, segs: [] };
  const small = r.filter((x) => x.fact / total < 0.03), merge = small.length >= 2;
  const base: BudgetRow[] = merge ? r.filter((x) => x.fact / total >= 0.03) : r;
  if (merge) {
    base.push({ id: '__other', name: 'Інші', fact: small.reduce((n, x) => n + x.fact, 0), plan: small.reduce((n, x) => n + x.plan, 0),
      over: small.some((x) => x.over), near: false });
  }
  const raw = base.map((x) => x.fact / total * 100), fl = raw.map(Math.floor);
  let left = 100 - fl.reduce((n, v) => n + v, 0);
  raw.map((v, i) => [v - fl[i], i]).sort((a, b) => b[0] - a[0]).forEach((q) => { if (left > 0) { fl[q[1]]++; left--; } });
  // v153: сталий тон за id категорії (усі витратні категорії рядків), порядок кільця як budRing застосунку
  const idx = budStable((ids || rows.map((x) => x.id)).filter((id) => id.slice(0, 2) !== '__' && id !== 'unallocated'));
  const segs = budRing(base.map((x, i) => {
    const k = idx[x.id];
    const grad = x.id === '__none' ? BUD_NONE : k == null ? BUD_OTH : BUD_PAL[k];
    return { ...x, share: x.fact / total, pct: fl[i], color: grad[0], grad };
  }), idx);
  return { total, segs };
}

export function donutSvg(m: BudgetModel): string {
  const { total, segs } = donutSegments(m.rows);
  const cx = 300, cy = 392, Ro = 236, Ri = 146;
  const out: string[] = [`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`,
    `<rect width="${W}" height="${H}" fill="${C.bg}"/>`, `<rect x="20" y="20" width="${W - 40}" height="${H - 40}" rx="28" fill="${C.card}"/>`,
    text(48, 80, `Витрати за категоріями, ${day(m.start)}-${day(m.end)}`, { size: 32, weight: 600 })];
  out.push('<defs>' + segs.map((s, i) => `<linearGradient id="g${i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${s.grad[0]}"/><stop offset="1" stop-color="${s.grad[1]}"/></linearGradient>`).join('') + '</defs>');
  if (!segs.length) {
    out.push(`<circle cx="${cx}" cy="${cy}" r="${(Ro + Ri) / 2}" fill="none" stroke="${C.grid}" stroke-width="${Ro - Ri}"/>`);
    out.push(text(cx, cy + 10, 'Витрат ще немає', { size: 28, fill: C.muted, anchor: 'middle' }));
  } else if (segs.length === 1) {
    out.push(`<circle cx="${cx}" cy="${cy}" r="${(Ro + Ri) / 2}" fill="none" stroke="url(#g0)" stroke-width="${Ro - Ri}"/>`);
  } else {
    const gap = 0.018;
    let a = -Math.PI / 2;
    const pt = (r: number, t: number) => `${r1(cx + r * Math.cos(t))} ${r1(cy + r * Math.sin(t))}`;
    for (const [i, s] of segs.entries()) {
      const a0 = a + gap / 2, a1 = a + Math.max(s.share * Math.PI * 2 - gap / 2, gap);
      a += s.share * Math.PI * 2;
      const lg = a1 - a0 > Math.PI ? 1 : 0;
      out.push(`<path d="M${pt(Ro, a0)} A${Ro} ${Ro} 0 ${lg} 1 ${pt(Ro, a1)} L${pt(Ri, a1)} A${Ri} ${Ri} 0 ${lg} 0 ${pt(Ri, a0)} Z" fill="url(#g${i})"/>`);
    }
  }
  out.push(text(cx, cy - 34, 'витрачено', { size: 24, fill: C.muted, anchor: 'middle' }));
  out.push(text(cx, cy + 12, money(m.spentCents), { size: 38, weight: 600, anchor: 'middle' }));
  out.push(text(cx, cy + 52, `з ${money(m.poolCents)}`, { size: 24, fill: C.muted, anchor: 'middle' }));
  // легенда праворуч: до 9 рядків
  const lx = 600;
  let ly = 160;
  for (const [i, s] of segs.slice(0, 9).entries()) {
    const name = s.name.length > 20 ? s.name.slice(0, 19) + '…' : s.name;
    out.push(`<rect x="${lx}" y="${ly - 22}" width="24" height="24" rx="7" fill="url(#g${i})"/>`);
    out.push(text(lx + 38, ly, name, { size: 25, weight: 600 }));
    out.push(text(W - 56, ly, `${s.pct}%`, { size: 25, weight: 600, fill: C.muted, anchor: 'end' }));
    const note = s.noPlan ? 'без плану' : s.over ? `план ${money(s.plan)} · понад ${money(Math.round(s.fact - s.plan))}` : `план ${money(s.plan)}`;
    out.push(text(lx + 38, ly + 28, `${money(s.fact)} · ${note}`, { size: 21, fill: s.over ? C.neg : C.muted }));
    ly += 60;
  }
  out.push(text(lx, H - 50, `Разом ${money(total)} · бюджет ${money(m.poolCents)}`, { size: 22, fill: C.muted }));
  out.push('</svg>');
  return out.join('');
}
