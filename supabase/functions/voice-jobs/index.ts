// Мовний сервіс на ноутбуці власника забирає тут завдання бота (розпізнати голосове, озвучити відповідь) і здає результат.
// Викликає лише ноутбук, без JWT (config.toml: verify_jwt = false); захист: підпис HMAC секретом VOICE_SECRET
// з міткою часу (_shared/voice-auth.ts). Без секрету функція відповідає 401 на все.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { handleVoiceJobs } from '../_shared/voice-queue.ts';

const sb = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
  auth: { persistSession: false, autoRefreshToken: false },
});
const VOICE_SECRET = Deno.env.get('VOICE_SECRET') || '';

Deno.serve((req) => handleVoiceJobs(req, { sb, secret: VOICE_SECRET }).catch((e) => {
  console.error('voice-jobs failed', (e as Error)?.message);
  return new Response(JSON.stringify({ error: 'internal' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
}));
