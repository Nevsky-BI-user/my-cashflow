// Оновлення балансів Monobank без відкриття застосунку: pg_cron кличе раз на 30 хв (міграція 56-mono-refresh-cron.sql).
// Без JWT (config.toml: verify_jwt = false); захист заголовком x-mono-refresh-secret == секрет MONO_REFRESH_SECRET,
// cron читає його з Supabase Vault (mono_refresh_secret), як telegram-digest. Без секрету 403 на все.
// Логіка та сама, що в mono-balance (_shared/mono-refresh.ts): свіжий за 60 с знімок не запитується, 429 нічого не пише.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { allowedMonoOwner } from '../_shared/mono-accounts.ts';
import { handleMonoRefresh } from '../_shared/mono-refresh.ts';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const SECRET = Deno.env.get('MONO_REFRESH_SECRET') || '';

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

Deno.serve((req) => {
  const wait = (globalThis as any).EdgeRuntime?.waitUntil;
  return handleMonoRefresh(req, SECRET, {
    sb, fetch: (url, init) => fetch(url, init), supabaseUrl: SUPABASE_URL, serviceRole: SERVICE_ROLE, allowed: allowedMonoOwner,
    waitUntil: wait ? (p) => wait.call((globalThis as any).EdgeRuntime, p) : undefined,
  }).catch((e) => {
    console.error('mono-refresh failed', (e as Error)?.message);
    return new Response(JSON.stringify({ error: 'internal' }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  });
});
