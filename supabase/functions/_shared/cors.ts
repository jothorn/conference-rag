const DEFAULT_ALLOWED_ORIGINS = [
  'https://jothorn.github.io',
  'http://localhost:5500',
  'http://127.0.0.1:5500',
];

export function corsHeaders(request: Request): Record<string, string> {
  const configured = Deno.env.get('ALLOWED_ORIGINS');
  const allowedOrigins = configured
    ? configured.split(',').map((origin) => origin.trim()).filter(Boolean)
    : DEFAULT_ALLOWED_ORIGINS;
  const origin = request.headers.get('Origin') ?? '';
  const allowOrigin = allowedOrigins.includes('*')
    ? '*'
    : (allowedOrigins.includes(origin) ? origin : allowedOrigins[0]);

  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Headers': 'authorization, apikey, x-client-info, content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Max-Age': '86400',
    'Cache-Control': 'no-store',
    'Vary': 'Origin',
    'Content-Type': 'application/json',
  };
}

export function jsonResponse(
  request: Request,
  body: Record<string, unknown>,
  status = 200,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: corsHeaders(request),
  });
}
