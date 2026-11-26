// Стан сімейних фінансів для локального клієнта власника (telegram-twin на ПК): GET, лише читання, без записів.
// Без JWT (config.toml: verify_jwt = false); захист: підпис HMAC секретом TWIN_SECRET з міткою часу не старшою за 120 с
// (_shared/voice-auth.ts). Без секрету функція відповідає 401 на все. Числа ті самі, що в боті (_shared/family-status.ts).
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { handleFamilyStatus } from '../_shared/family-status.ts';

const sb = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
  auth: { persistSession: false, autoRefreshToken: false },
});
const TWIN_SECRET = Deno.env.get('TWIN_SECRET') || '';

Deno.serve((req) => handleFamilyStatus(req, { sb, secret: TWIN_SECRET }).catch((e) => {
  console.error('family-status failed', (e as Error)?.message);
  return new Response(JSON.stringify({ error: 'internal' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
}));
