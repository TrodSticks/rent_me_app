/**
 * Rules first, LLM as backup.
 *
 * 1. The rules parse the search instantly and offline.
 * 2. Only if some words were not understood, ask the `parse-search`
 *    Supabase Edge Function (an open-source LLM) — with a short timeout.
 * 3. Validate its answer and merge; on any failure keep the rules' result.
 */
import type { Property } from '../data/properties';
import { filterAndRank, parseQuery, type SearchParams } from './search';
import { mergeParams, sanitizeLLM } from './search-llm';

export type SmartSearchResult = {
  params: SearchParams;
  results: Property[];
  /** Which layer produced the filters (useful for analytics and debugging). */
  source: 'rules' | 'rules+llm';
};

const FUNCTION_URL = process.env.EXPO_PUBLIC_SUPABASE_URL
  ? `${process.env.EXPO_PUBLIC_SUPABASE_URL}/functions/v1/parse-search`
  : null;
const ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

async function askLLM(query: string, timeoutMs: number): Promise<SearchParams | null> {
  if (!FUNCTION_URL || !ANON_KEY) return null; // backend not connected yet
  try {
    const res = await fetch(FUNCTION_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${ANON_KEY}` },
      body: JSON.stringify({ query }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    return sanitizeLLM((await res.json()).filters);
  } catch {
    return null;
  }
}

export async function smartSearch(
  properties: Property[],
  query: string,
  { timeoutMs = 4000 } = {},
): Promise<SmartSearchResult> {
  const { unknown, ...rules } = parseQuery(query);
  if (unknown.length > 0) {
    const llm = await askLLM(query, timeoutMs);
    if (llm) {
      const params = mergeParams(rules, llm);
      return { params, results: filterAndRank(properties, params), source: 'rules+llm' };
    }
  }
  return { params: rules, results: filterAndRank(properties, rules), source: 'rules' };
}
