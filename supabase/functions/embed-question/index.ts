import { authenticatedUserId } from '../_shared/auth.ts';
import { jsonResponse } from '../_shared/cors.ts';

const MAX_QUESTION_LENGTH = 2_000;

Deno.serve(async (request: Request) => {
  if (request.method === 'OPTIONS') return jsonResponse(request, {});
  if (request.method !== 'POST') {
    return jsonResponse(request, { error: 'Use POST for this endpoint.' }, 405);
  }

  const userId = await authenticatedUserId(request);
  if (!userId) return jsonResponse(request, { error: 'Sign in to use semantic search.' }, 401);

  const apiKey = Deno.env.get('OPENAI_API_KEY');
  if (!apiKey) return jsonResponse(request, { error: 'OPENAI_API_KEY is not configured.' }, 503);

  let body: { question?: unknown; health_check?: unknown };
  try {
    const contentLength = Number(request.headers.get('Content-Length') ?? 0);
    if (contentLength > 16_384) return jsonResponse(request, { error: 'Request is too large.' }, 413);
    body = await request.json();
  } catch {
    return jsonResponse(request, { error: 'Request body must be valid JSON.' }, 400);
  }

  if (body.health_check === true) return jsonResponse(request, { healthy: true });
  const question = typeof body.question === 'string' ? body.question.trim() : '';
  if (!question || question.length > MAX_QUESTION_LENGTH) {
    return jsonResponse(request, { error: `Question must be between 1 and ${MAX_QUESTION_LENGTH} characters.` }, 400);
  }

  try {
    const response = await fetch('https://api.openai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model: 'text-embedding-3-small', input: question }),
      signal: AbortSignal.timeout(30_000),
    });
    const result = await response.json();
    if (!response.ok) {
      console.error('OpenAI embeddings request failed', response.status, result?.error?.type);
      return jsonResponse(request, { error: 'Embedding service request failed.' }, 502);
    }

    const embedding = result?.data?.[0]?.embedding;
    if (!Array.isArray(embedding) || embedding.length !== 1_536) {
      return jsonResponse(request, { error: 'Embedding service returned an unexpected vector.' }, 502);
    }
    return jsonResponse(request, { embedding });
  } catch (error) {
    console.error('Embedding request failed', error);
    return jsonResponse(request, { error: 'Embedding service is unavailable.' }, 502);
  }
});
