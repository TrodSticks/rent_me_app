/**
 * POST { "query": "ke batla ntlo kwa Gabs" } → the LLM's JSON filters.
 *
 * Keeps the LLM key on the server. The app validates the answer
 * (src/lib/search-llm.ts) and falls back to the rules if this fails.
 *
 * Secrets (supabase secrets set …):
 *   LLM_BASE_URL  e.g. https://api.groq.com/openai/v1  or  http://<your-server>:11434/v1 (Ollama)
 *   LLM_MODEL     e.g. an open-source model such as qwen2.5:3b or llama-3.2-3b
 *   LLM_API_KEY   (not needed for your own Ollama server)
 */
import { callLLM } from '../_shared/search-prompt.ts';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: CORS });

  let query = '';
  try {
    query = String((await req.json()).query ?? '').trim();
  } catch {
    // fall through to the empty-query error
  }
  if (!query || query.length > 300) {
    return Response.json({ error: 'query must be 1–300 characters' }, { status: 400, headers: CORS });
  }

  try {
    const filters = await callLLM(query, {
      baseUrl: Deno.env.get('LLM_BASE_URL')!,
      model: Deno.env.get('LLM_MODEL')!,
      apiKey: Deno.env.get('LLM_API_KEY'),
      timeoutMs: 6000,
    });
    return Response.json({ filters }, { headers: CORS });
  } catch (err) {
    console.error('parse-search failed', err);
    return Response.json({ error: 'llm_unavailable' }, { status: 502, headers: CORS });
  }
});
