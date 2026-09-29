/**
 * The instructions sent to the LLM that backs up the rules-based search.
 * Shared by the `parse-search` Edge Function and `npm run eval:search`.
 * No imports, so it runs unchanged on Deno (Supabase) and Node.
 *
 * Keep TOWNS / SUBURBS in step with src/lib/search.ts; the eval script checks this.
 */

export const PROMPT_TOWNS = [
  'Gaborone', 'Francistown', 'Maun', 'Kasane', 'Serowe', 'Molepolole', 'Kanye',
  'Mochudi', 'Lobatse', 'Palapye', 'Jwaneng', 'Ghanzi', 'Tsabong', 'Letlhakane',
  'Mogoditshane', 'Selebi-Phikwe', 'Mahalapye', 'Ramotswa', 'Tonota', 'Orapa',
];

export const PROMPT_SUBURBS: Record<string, string> = {
  'Block 3': 'Gaborone', 'Block 5': 'Gaborone', 'Block 6': 'Gaborone', 'Block 7': 'Gaborone',
  'Block 8': 'Gaborone', 'Block 9': 'Gaborone', 'Block 10': 'Gaborone',
  Phakalane: 'Gaborone', Broadhurst: 'Gaborone', Fairgrounds: 'Gaborone', CBD: 'Gaborone',
  'Extension 10': 'Gaborone', 'Gaborone West': 'Gaborone', 'Gaborone North': 'Gaborone',
  Tlokweng: 'Gaborone', Mmopane: 'Gaborone', Mokolodi: 'Gaborone', 'Game City': 'Gaborone',
  'Area W': 'Francistown', Boseja: 'Maun',
};

const SYSTEM = `You turn a rental search typed by someone in Botswana into JSON filters.
The search may be English, Setswana, or a mix, and may have spelling mistakes or slang.

Return ONLY a JSON object with exactly these keys:
{"type": null|"house"|"apartment"|"room"|"office"|"commercial"|"land",
 "bedrooms": null|integer 1-10,
 "town": null|one of the towns below,
 "suburb": null|one of the suburbs below,
 "minPrice": null|integer (Pula per month),
 "maxPrice": null|integer (Pula per month),
 "furnished": true|false,
 "keywords": [up to 5 short English words for other wishes, e.g. "garden", "parking", "quiet"]}

Rules:
- Use null when the search does not say. Never guess a town, type or price that was not mentioned.
- Towns: ${PROMPT_TOWNS.join(', ')}.
- Suburbs (and their town): ${Object.entries(PROMPT_SUBURBS).map(([s, t]) => `${s} (${t})`).join(', ')}.
  When a suburb is given, also set its town.
- "Gabs", "GC" = Gaborone. "Ftown" = Francistown.
- flat, studio, bachelor = "apartment". backroom = "room". plot, stand = "land". shop, warehouse = "commercial".
- Prices are monthly rent in Pula. "5k" = 5000. "4 and a half" = 4500 when talking about budget.
  "under/below/max/around/about/not more than X" = maxPrice X. "from/over/at least X" = minPrice X.
- Budget words: cheap = maxPrice 3000; budget = 4000; affordable or "not too expensive" = 5000;
  expensive = 10000; premium = 12000; luxury = 15000.
- "furnished" true only if they ask for furnished; "unfurnished" is false.
- Setswana: ntlo/matlo = house; phaposi/kamore = room; "diphaposi tse pedi" = 2 bedrooms;
  nngwe=1, pedi=2, tharo=3, nne=4, tlhano=5; setsha = land; "lefelo la kgwebo" = commercial;
  ofisi = office; "e e sa tureng" = cheap; "e nnye" = small; "ke batla" = I want; "kwa" = in/at.
- Number of people or children is not bedrooms.`;

const EXAMPLES: [string, object][] = [
  [
    'cheap 2 bedroom house in gabs',
    { type: 'house', bedrooms: 2, town: 'Gaborone', suburb: null, minPrice: null, maxPrice: 3000, furnished: false, keywords: [] },
  ],
  [
    'ke batla phaposi kwa Tlokweng e e sa tureng, ke na le koloi',
    { type: 'room', bedrooms: null, town: 'Gaborone', suburb: 'Tlokweng', minPrice: null, maxPrice: 3000, furnished: false, keywords: ['parking'] },
  ],
];

export type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string };

export function buildMessages(query: string): ChatMessage[] {
  return [
    { role: 'system', content: SYSTEM },
    ...EXAMPLES.flatMap(([q, a]): ChatMessage[] => [
      { role: 'user', content: q },
      { role: 'assistant', content: JSON.stringify(a) },
    ]),
    { role: 'user', content: query.slice(0, 300) },
  ];
}

/**
 * Calls any OpenAI-compatible chat endpoint (Groq, Together, OpenRouter,
 * Ollama, vLLM, llama.cpp server …) and returns the raw parsed JSON.
 */
export async function callLLM(
  query: string,
  cfg: { baseUrl: string; model: string; apiKey?: string; timeoutMs?: number },
): Promise<unknown> {
  const res = await fetch(`${cfg.baseUrl.replace(/\/$/, '')}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(cfg.apiKey ? { Authorization: `Bearer ${cfg.apiKey}` } : {}),
    },
    body: JSON.stringify({
      model: cfg.model,
      messages: buildMessages(query),
      temperature: 0,
      max_tokens: 200,
      response_format: { type: 'json_object' },
    }),
    signal: AbortSignal.timeout(cfg.timeoutMs ?? 8000),
  });
  if (!res.ok) throw new Error(`LLM ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const text: string = data.choices?.[0]?.message?.content ?? '';
  const json = text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1);
  return JSON.parse(json);
}
