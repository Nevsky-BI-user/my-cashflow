// SVG у PNG прямо у функції (resvg у WebAssembly): дані не йдуть у сторонні сервіси графіків.
// Звідси завантажується лише код рендерера (wasm тієї самої закріпленої версії з jsDelivr), фінансові дані лишаються в функції.
import { initWasm, Resvg } from 'npm:@resvg/resvg-wasm@2.6.2';
import { interFonts } from './fonts-inter.ts';
import { FONT } from './bot-charts.ts';

const WASM_URL = 'https://cdn.jsdelivr.net/npm/@resvg/resvg-wasm@2.6.2/index_bg.wasm';
// initWasm можна викликати лише раз на ізолят: тримаємо одну обіцянку, при помилці дозволяємо повтор
let ready: Promise<void> | null = null;
let fonts: Uint8Array[] | null = null;

function init(): Promise<void> {
  if (!ready) {
    ready = initWasm(fetch(WASM_URL)).catch((e: unknown) => {
      ready = null;
      throw e;
    });
  }
  return ready as Promise<void>;
}

export async function svgToPng(svg: string): Promise<Uint8Array> {
  await init();
  fonts ??= interFonts();
  const r = new Resvg(svg, {
    font: { fontBuffers: fonts, loadSystemFonts: false, defaultFontFamily: FONT },
    fitTo: { mode: 'original' },
  });
  return r.render().asPng();
}
