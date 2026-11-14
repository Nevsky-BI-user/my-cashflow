// Підпис запитів мовного сервісу на ноутбуці власника (voice-service/) до функції voice-jobs.
// Ноутбук лише сам звертається до Supabase (вихідні HTTPS-запити), до нього ніхто не підключається.
// Підпис: X-Voice-Sig = hex(HMAC-SHA256(VOICE_SECRET, "<ts>\n" + тіло)), X-Voice-Ts = unix-секунди.
// Тіло JSON містить дію (op), тож підпис покриває і дію, і дані. Запит старший чи новіший за 120 с відхиляється.
const enc = new TextEncoder();

export const nowTs = () => Math.floor(Date.now() / 1000);
export const tsFresh = (ts: number, now = nowTs(), skew = 120) => Number.isSafeInteger(ts) && Math.abs(now - ts) <= skew;

const hex = (buf: ArrayBuffer) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
}

export async function voiceSign(secret: string, ts: number | string, body: string): Promise<string> {
  return hex(await crypto.subtle.sign('HMAC', await hmacKey(secret), enc.encode(`${ts}\n${body}`)));
}

// Порівняння без раннього виходу: час не підказує, скільки символів збіглося
function sameHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Перевірка підпису: секрет порожній, мітка часу стара чи підпис чужий → false
export async function voiceVerify(secret: string, tsHeader: string | null, sigHeader: string | null, body: string, now = nowTs()): Promise<boolean> {
  if (!secret || secret.length < 32 || !tsHeader || !sigHeader || !/^\d{1,12}$/.test(tsHeader) || !/^[0-9a-f]{64}$/.test(sigHeader)) return false;
  if (!tsFresh(Number(tsHeader), now)) return false;
  return sameHex(await voiceSign(secret, tsHeader, body), sigHeader);
}
