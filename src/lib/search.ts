/**
 * Plain-language property search — the rules layer.
 *
 * "cheap 2 bedroom house in Gaborone" → { type: 'house', bedrooms: 2,
 * town: 'Gaborone', maxPrice: 3000 }
 *
 * Handles English, common Setswana words, number words, small spelling
 * mistakes and nicknames ("gabs"). Words it cannot place are returned in
 * `unknown`; when there are any, `smart-search.ts` asks the LLM as a backup.
 */
import { formatPula, PROPERTY_TYPE_LABELS, type Property, type PropertyType } from '../data/properties';

export type SearchParams = {
  type: PropertyType | null;
  bedrooms: number | null;
  town: string | null;
  suburb: string | null;
  minPrice: number | null;
  maxPrice: number | null;
  furnished: boolean;
  /** Leftover descriptive words, used to rank results ("garden", "parking"). */
  keywords: string[];
};

export type ParseResult = SearchParams & {
  /** Words the rules did not recognise. Empty = the rules understood everything. */
  unknown: string[];
};

export const TOWNS = [
  'Gaborone', 'Francistown', 'Maun', 'Kasane', 'Serowe', 'Molepolole', 'Kanye',
  'Mochudi', 'Lobatse', 'Palapye', 'Jwaneng', 'Ghanzi', 'Tsabong', 'Letlhakane',
  'Mogoditshane', 'Selebi-Phikwe', 'Mahalapye', 'Ramotswa', 'Tonota', 'Orapa',
];

/** Suburbs and nearby villages, mapped to the town they are listed under. */
export const SUBURBS: Record<string, string> = {
  'Block 3': 'Gaborone', 'Block 5': 'Gaborone', 'Block 6': 'Gaborone', 'Block 7': 'Gaborone',
  'Block 8': 'Gaborone', 'Block 9': 'Gaborone', 'Block 10': 'Gaborone',
  Phakalane: 'Gaborone', Broadhurst: 'Gaborone', Fairgrounds: 'Gaborone', CBD: 'Gaborone',
  'Extension 10': 'Gaborone', 'Gaborone West': 'Gaborone', 'Gaborone North': 'Gaborone',
  Tlokweng: 'Gaborone', Mmopane: 'Gaborone', Mokolodi: 'Gaborone', 'Game City': 'Gaborone',
  'Area W': 'Francistown', Boseja: 'Maun',
};

/** Nicknames and common misspellings that fuzzy matching would not catch. */
const ALIASES: Record<string, string> = {
  gabs: 'gaborone',
  gabz: 'gaborone',
  gc: 'gaborone',
  ftown: 'francistown',
  'f/town': 'francistown',
  molep: 'molepolole',
  mogodi: 'mogoditshane',
  phikwe: 'selebi-phikwe',
};

/** Type words, in English and Setswana. The first one mentioned wins. */
const TYPE_SYNONYMS: Record<PropertyType, string[]> = {
  house: ['house', 'home', 'villa', 'cottage', 'bungalow', 'townhouse', 'ntlo', 'matlo'],
  apartment: ['apartment', 'flat', 'unit', 'condo', 'studio', 'bachelor'],
  room: ['room', 'backroom', 'phaposi', 'kamore'],
  office: ['office', 'offices', 'workspace', 'ofisi'],
  commercial: ['shop', 'retail', 'warehouse', 'commercial', 'kgwebo'],
  land: ['land', 'plot', 'stand', 'setsha'],
};

/** Number words, English and Setswana. */
const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
  nngwe: 1, pedi: 2, tharo: 3, nne: 4, tlhano: 5, thataro: 6,
};

/** Budget words → the maximum monthly rent they imply (Pula). */
const PRICE_WORDS: [RegExp, number][] = [
  [/\b(?:e\s+e\s+)?sa\s+tureng\b|\btlhwatlhwa\s+e\s+e\s+kwa\s+tlase\b/, 3000],
  [/\b(?:not|nothing|isn't|nt)\s+(?:too\s+|so\s+|very\s+|crazy\s+|that\s+)?expensive\b/, 5000],
  [/\bcheap(?:est)?\b|\blow\s+budget\b/, 3000],
  [/\bbudget\b/, 4000],
  [/\baffordable\b|\breasonabl[ey]\b/, 5000],
  [/\bpremium\b/, 12000],
  [/\bexpensive\b/, 10000],
  [/\bluxury\b|\bluxurious\b/, 15000],
];

/** Words that carry no search meaning, in English and Setswana. */
const FILLER = new Set([
  // English
  'a', 'an', 'the', 'in', 'at', 'on', 'near', 'for', 'with', 'and', 'or', 'to', 'of', 'i',
  'im', 'we', 'want', 'need', 'needs', 'looking', 'find', 'me', 'my', 'show', 'rent', 'rental',
  'place', 'places', 'month', 'per', 'pm', 'under', 'below', 'less', 'than', 'max', 'maximum',
  'up', 'between', 'bedroom', 'bedrooms', 'bed', 'beds', 'br', 'pula', 'p', 'furnished',
  'unfurnished', 'fully', 'is', 'am', 'for', 'about', 'around', 'roughly', 'approximately',
  'not', 'no', 'more', 'most', 'least', 'over', 'above', 'from', 'space', 'something',
  'somewhere', 'stay', 'live', 'please', 'any', 'available', 'some', 'can', 'get', 'good',
  'nice', 'new', 'k', 'thousand', 'monthly', 'nothing', 'too', 'very', 'crazy', 'so',
  'that', 'this', 'there', 'town', 'area', 'side', 'price', 'cost', 'costs', 'budget',
  'cheap', 'affordable', 'expensive', 'luxury', 'premium', 'reasonable', 'small', 'big',
  'large',
  // Setswana
  'ke', 'batla', 'kwa', 'mo', 'go', 'e', 'ya', 'la', 'le', 'tse', 'tsa', 'sa', 'ka', 'nnye',
  'kgolo', 'diphaposi', 'dikamore', 'robala', 'hira', 'nang', 'lefelo', 'tureng', 'tlase',
  'tlhwatlhwa', 'rona', 'nna', 'ba', 'ga',
]);

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hasWord(query: string, word: string) {
  return new RegExp(`(?:^|[^a-z0-9])${escapeRegExp(word.toLowerCase())}s?(?![a-z0-9])`).test(query);
}

function wordIndex(query: string, word: string) {
  const m = new RegExp(`(?:^|[^a-z0-9])${escapeRegExp(word)}s?(?![a-z0-9])`).exec(query);
  return m ? m.index : -1;
}

/** Levenshtein distance, stopping early once it passes `max`. */
function distance(a: string, b: string, max: number) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      best = Math.min(best, cur[j]);
    }
    if (best > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

/** Words worth correcting a typo towards. Short town names are left out ("main" ≠ Maun). */
const VOCABULARY = [
  ...Object.values(TYPE_SYNONYMS).flat(),
  ...TOWNS.map((t) => t.toLowerCase()),
  ...Object.keys(SUBURBS).flatMap((s) => s.toLowerCase().split(' ')),
  'bedroom', 'bedrooms', 'furnished', 'unfurnished', 'under', 'below', 'between', 'thousand',
].filter((w) => w.length >= 5 && !/\d/.test(w));

function correctSpelling(token: string) {
  if (token.length < 4 || FILLER.has(token) || /\d/.test(token)) return token;
  if (VOCABULARY.includes(token)) return token;
  const allowed = token.length >= 7 ? 2 : 1;
  let best = token;
  let bestDist = allowed + 1;
  for (const word of VOCABULARY) {
    if (word[0] !== token[0]) continue;
    const d = distance(token, word, allowed);
    if (d < bestDist) {
      best = word;
      bestDist = d;
    }
  }
  return best;
}

/** Lower-case, fix typos, expand nicknames, number words and "5k"/"4 and a half". */
export function normalize(input: string) {
  let q = ` ${input.toLowerCase().replace(/[’']/g, '').replace(/(\d),(\d{3})/g, '$1$2')} `;

  q = q
    .split(/(\s+|[.,;!?()])/)
    .map((tok) => {
      const word = tok.trim();
      if (!word) return tok;
      if (ALIASES[word]) return ALIASES[word];
      if (NUMBER_WORDS[word] !== undefined) return String(NUMBER_WORDS[word]);
      return correctSpelling(word);
    })
    .join('');

  q = q
    // "4 and a half (thousand)" → 4500
    .replace(/\b(\d{1,2})\s+and\s+a\s+half(?:\s*(?:thousand|k))?\b/g, (_, n) => String(Number(n) * 1000 + 500))
    // "between 3 and 5 thousand" → "between 3000 and 5000"
    .replace(
      /\b(\d{1,2})\s*(and|to|-)\s*(\d{1,2})\s*(?:thousand|k)\b/g,
      (_, a, sep, b) => `${Number(a) * 1000} ${sep} ${Number(b) * 1000}`,
    )
    // "5k", "5 thousand", "4.5k" → 5000 / 4500
    .replace(/\b(\d+(?:\.\d+)?)\s*(?:k|thousand)\b/g, (_, n) => String(Math.round(Number(n) * 1000)));

  return q.replace(/\s+/g, ' ').trim();
}

const AMOUNT = String.raw`p?\s?(\d{3,6})\b`;

function parsePrice(q: string) {
  const range = q.match(new RegExp(`${AMOUNT}\\s*(?:-|to|and)\\s*${AMOUNT}`));
  if (range) return { minPrice: Number(range[1]), maxPrice: Number(range[2]) };

  const out = { minPrice: null as number | null, maxPrice: null as number | null };
  const max = q.match(
    new RegExp(
      `(?:under|below|less than|max(?:imum)?|up to|budget(?: of| is)?|not more than|no more than|at most|around|about|roughly|approximately|for|ka)\\s*(?:about\\s*|around\\s*)?${AMOUNT}`,
    ),
  );
  const min = q.match(new RegExp(`(?:over|above|more than|from|at least|minimum|min)\\s*${AMOUNT}`));
  if (max) out.maxPrice = Number(max[1]);
  const negated = min && /\b(?:not|no)\s+$/.test(q.slice(0, min.index));
  if (min && !negated) out.minPrice = Number(min[1]);

  // A lone amount written as a price ("P1500", "4500 a month") is a maximum.
  if (out.maxPrice === null && out.minPrice === null) {
    const lone = q.match(/\bp\s?(\d{3,6})\b|\b(\d{3,6})\s*(?:pula|a month|per month|pm)\b/);
    if (lone) out.maxPrice = Number(lone[1] ?? lone[2]);
  }
  if (out.maxPrice === null) {
    const word = PRICE_WORDS.find(([re]) => re.test(q));
    if (word) out.maxPrice = word[1];
  }
  return out;
}

function parseBedrooms(q: string) {
  const en = q.match(/\b(\d{1,2})\s*-?\s*(?:bedroom|bed|br|bdr|bhk)s?\b/);
  const tn = q.match(/\b(?:diphaposi|dikamore)(?:\s+tsa\s+go\s+robala)?\s+(?:tse\s+)?(\d{1,2})\b/);
  const n = Number((en ?? tn)?.[1]);
  return n >= 1 && n <= 10 ? n : null;
}

function parseType(q: string): PropertyType | null {
  let best: { type: PropertyType; at: number } | null = null;
  for (const [type, words] of Object.entries(TYPE_SYNONYMS) as [PropertyType, string[]][]) {
    for (const w of words) {
      const at = wordIndex(q, w);
      if (at >= 0 && (!best || at < best.at)) best = { type, at };
    }
  }
  return best?.type ?? null;
}

export function parseQuery(input: string): ParseResult {
  const q = normalize(input);

  const suburb =
    Object.keys(SUBURBS)
      .sort((a, b) => b.length - a.length)
      .find((s) => hasWord(q, s)) ?? null;
  const town = suburb ? SUBURBS[suburb] : (TOWNS.find((t) => hasWord(q, t)) ?? null);

  const params: SearchParams = {
    type: parseType(q),
    bedrooms: parseBedrooms(q),
    town,
    suburb,
    ...parsePrice(q),
    furnished: /\bfurnished\b/.test(q) && !/\bunfurnished\b/.test(q),
    keywords: [],
  };

  // Everything not recognised above is left over.
  const known = new Set(
    [
      ...Object.values(TYPE_SYNONYMS).flat(),
      ...TOWNS,
      ...Object.keys(SUBURBS),
      ...Object.keys(ALIASES),
    ].flatMap((w) => w.toLowerCase().split(/[\s-]+/)),
  );
  const leftover = q
    .split(/[^a-z]+/)
    .filter((w) => w.length > 1 && !FILLER.has(w) && !known.has(w) && !known.has(w.replace(/s$/, '')));

  params.keywords = leftover.filter((w) => w.length > 2);
  return { ...params, unknown: leftover };
}

export function matches(property: Property, p: SearchParams) {
  if (p.type && property.type !== p.type) return false;
  if (p.bedrooms !== null && property.bedrooms !== p.bedrooms) return false;
  if (p.town && property.town !== p.town) return false;
  if (p.suburb && property.suburb !== p.suburb) return false;
  if (p.maxPrice !== null && property.price > p.maxPrice) return false;
  if (p.minPrice !== null && property.price < p.minPrice) return false;
  if (p.furnished && !/furnished/i.test(property.description)) return false;
  return true;
}

/** Keyword hits only rank results; they never hide a listing. */
function score(property: Property, p: SearchParams) {
  const text = `${property.title} ${property.description}`.toLowerCase();
  return p.keywords.filter((k) => text.includes(k)).length + (property.featured ? 0.5 : 0);
}

export function filterAndRank(properties: Property[], params: SearchParams) {
  return properties
    .filter((prop) => matches(prop, params))
    .sort((a, b) => score(b, params) - score(a, params) || a.price - b.price);
}

/** Rules-only search (instant, offline). */
export function search(properties: Property[], query: string) {
  const params = parseQuery(query);
  return { params, results: filterAndRank(properties, params) };
}

/** The "Searching for you…" checklist shown on the results screen. */
export function describeSteps(p: SearchParams): string[] {
  const steps = ['Understanding your request'];
  const where = p.suburb ? `${p.suburb}, ${p.town}` : p.town;
  steps.push(where ? `Searching listings in ${where}` : 'Searching listings across Botswana');
  if (p.bedrooms || p.type) {
    const type = p.type ? PROPERTY_TYPE_LABELS[p.type].toLowerCase() + 's' : 'properties';
    steps.push(`Filtering ${p.bedrooms ? `${p.bedrooms} bedroom ` : ''}${type}`);
  }
  if (p.furnished) steps.push('Keeping furnished places only');
  if (p.maxPrice !== null || p.minPrice !== null) {
    const budget =
      p.minPrice !== null && p.maxPrice !== null
        ? `${formatPula(p.minPrice)}–${formatPula(p.maxPrice)}`
        : p.maxPrice !== null
          ? `up to ${formatPula(p.maxPrice)}`
          : `from ${formatPula(p.minPrice!)}`;
    steps.push(`Matching your budget (${budget})`);
  }
  steps.push('Ranking by best match');
  return steps;
}

/** Example searches shown as chips under the search box. */
export const SUGGESTIONS = [
  '1 bedroom apartment in Gaborone',
  '3 bedroom house under P7,000',
  'Rooms near university',
  'Furnished apartment',
  'Office space',
  'Ntlo kwa Tlokweng',
];
