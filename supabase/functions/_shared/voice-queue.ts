// Черга мовного сервісу (таблиця voice_jobs, міграція 54). Дві сторони:
// 1) функція voice-jobs: ноутбук власника забирає завдання (claim з довгим очікуванням) і здає результат (done);
// 2) бот: кладе завдання і чекає результат обмежений час, потім видаляє запис (аудіо в базі живе секунди).
// Клієнт Supabase, годинник і пауза передаються ззовні: модуль перевіряють node-тести без мережі.
import { voiceVerify } from './voice-auth.ts';

type Sb = any;
export type VoiceKind = 'stt' | 'tts';
export type VoiceDeps = { sb: Sb; secret: string; nowMs?: () => number; sleep?: (ms: number) => Promise<void> };

const realSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

export const CLAIM_WAIT_MAX_S = 50; // довше: ризик ліміту 150 с на запит Edge
export const CLAIM_POLL_MS = 500;
export const ONLINE_WINDOW_MS = 90_000; // ноутбук приходить щонайменше раз на ~50 с між завданнями
const MAX_B64 = 4_000_000; // ~3 МБ аудіо: голосове до 2 хв і відповідь до кількох хвилин
const MAX_TEXT = 4000;

// Перевірка вихідних даних ноутбука: лише очікувані поля і розміри
function cleanOutput(kind: string, out: any): Record<string, unknown> | null {
  if (!out || typeof out !== 'object') return null;
  if (kind === 'stt') return typeof out.text === 'string' && out.text.length <= MAX_TEXT ? { text: out.text } : null;
  if (typeof out.audio_b64 !== 'string' || !out.audio_b64.length || out.audio_b64.length > MAX_B64 || !/^[A-Za-z0-9+/=]+$/.test(out.audio_b64)) return null;
  const duration = Number(out.duration);
  return { audio_b64: out.audio_b64, mime: 'audio/ogg', duration: Number.isFinite(duration) && duration > 0 ? duration : null };
}

// Обробник функції voice-jobs: спершу підпис, потім будь-яка робота з базою
export async function handleVoiceJobs(req: Request, deps: VoiceDeps): Promise<Response> {
  if (req.method !== 'POST') return json({ error: 'method' }, 405);
  const body = await req.text();
  if (body.length > MAX_B64 + 10_000) return json({ error: 'too large' }, 413);
  if (!await voiceVerify(deps.secret, req.headers.get('X-Voice-Ts'), req.headers.get('X-Voice-Sig'), body)) return json({ error: 'unauthorized' }, 401);
  let msg: any;
  try { msg = JSON.parse(body); } catch { return json({ error: 'bad json' }, 400); }
  const sb = deps.sb, now = deps.nowMs || Date.now, sleep = deps.sleep || realSleep;

  if (msg?.op === 'claim') {
    const info = msg.info && typeof msg.info === 'object' && JSON.stringify(msg.info).length <= 1000 ? msg.info : null;
    const hb = await sb.rpc('voice_heartbeat', { p_info: info });
    if (hb.error) return json({ error: 'db' }, 500);
    const wait = Math.max(0, Math.min(CLAIM_WAIT_MAX_S, Number(msg.wait) || 0)) * 1000;
    const until = now() + wait;
    for (;;) {
      const r = await sb.rpc('voice_claim', { p_max_age_s: 40 });
      if (r.error) return json({ error: 'db' }, 500);
      const row = Array.isArray(r.data) ? r.data[0] : r.data;
      if (row && row.id != null) return json({ job: { id: Number(row.id), kind: row.kind, input: row.input } });
      if (now() + CLAIM_POLL_MS > until) return json({ job: null });
      await sleep(CLAIM_POLL_MS);
    }
  }

  if (msg?.op === 'done') {
    const id = Number(msg.id);
    if (!Number.isSafeInteger(id) || id <= 0) return json({ error: 'id' }, 400);
    const kind = (await sb.from('voice_jobs').select('kind').eq('id', id).maybeSingle())?.data?.kind;
    if (!kind) return json({ accepted: false });
    const ok = msg.ok === true;
    const output = ok ? cleanOutput(kind, msg.output) : { error: String(msg.error || 'error').slice(0, 200) };
    const r = await sb.rpc('voice_done', { p_id: id, p_ok: ok && output != null, p_output: output ?? { error: 'bad output' } });
    if (r.error) return json({ error: 'db' }, 500);
    return json({ accepted: r.data === true });
  }
  return json({ error: 'op' }, 400);
}

// ---------- Бік бота ----------

// Ноутбук на звʼязку: приходив за завданнями протягом останніх 90 с
export async function voiceOnline(sb: Sb, nowMs = Date.now()): Promise<boolean> {
  const { data, error } = await sb.from('voice_worker').select('last_seen').eq('id', 1).maybeSingle();
  if (error || !data?.last_seen) return false;
  const t = Date.parse(data.last_seen);
  return Number.isFinite(t) && nowMs - t <= ONLINE_WINDOW_MS;
}

// Покласти завдання і дочекатися результату; таймаут чи помилка → null. Запис видаляється в будь-якому разі.
export async function voiceRun(sb: Sb, kind: VoiceKind, input: Record<string, unknown>, timeoutMs: number,
  opts: { nowMs?: () => number; sleep?: (ms: number) => Promise<void>; pollMs?: number } = {}): Promise<Record<string, any> | null> {
  const now = opts.nowMs || Date.now, sleep = opts.sleep || realSleep, poll = opts.pollMs ?? 300;
  const ins = await sb.from('voice_jobs').insert({ kind, input }).select('id').single();
  if (ins.error || !ins.data?.id) {
    console.error('voice job insert failed', ins.error?.message);
    return null;
  }
  const id = ins.data.id;
  const until = now() + timeoutMs;
  try {
    while (now() < until) {
      await sleep(poll);
      const r = await sb.from('voice_jobs').select('status,output').eq('id', id).maybeSingle();
      if (r.error || !r.data) return null;
      if (r.data.status === 'done') return r.data.output || null;
      if (r.data.status === 'failed') {
        console.error('voice job failed', kind, String(r.data.output?.error || '').slice(0, 100));
        return null;
      }
    }
    console.error('voice job timeout', kind);
    return null;
  } finally {
    const del = await sb.from('voice_jobs').delete().eq('id', id);
    if (del?.error) console.error('voice job delete failed', del.error.message);
  }
}
