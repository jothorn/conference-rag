import { createClient } from 'npm:@supabase/supabase-js@2';

export async function authenticatedUserId(request: Request): Promise<string | null> {
  const authorization = request.headers.get('Authorization') ?? '';
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match) return null;

  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  let apiKey = Deno.env.get('SUPABASE_ANON_KEY');
  const publishableKeys = Deno.env.get('SUPABASE_PUBLISHABLE_KEYS');
  if (publishableKeys) {
    try {
      apiKey = JSON.parse(publishableKeys).default || apiKey;
    } catch {
      return null;
    }
  }
  if (!supabaseUrl || !apiKey) return null;

  const supabase = createClient(supabaseUrl, apiKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data, error } = await supabase.auth.getUser(match[1]);
  return error ? null : data.user?.id ?? null;
}
