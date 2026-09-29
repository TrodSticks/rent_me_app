/**
 * Plain-language property search, ported from the original Flask
 * `search_engine.py` and extended for the new property types and suburbs.
 *
 * "2 bedroom house in Gaborone under P5,000" → { bedrooms: 2, type: 'house',
 * town: 'Gaborone', maxPrice: 5000 }
 */
import { formatPula, PROPERTY_TYPE_LABELS, type Property, type PropertyType } from '@/data/properties';

export type SearchParams = {
  type: PropertyType | null;
  bedrooms: number | null;
  town: string | null;
  suburb: string | null;
  minPrice: number | null;
  maxPrice: number | null;
  furnished: boolean;
  keywords: string[];
};

export const TOWNS = [
  'Gaborone', 'Francistown', 'Maun', 'Kasane', 'Serowe', 'Molepolole', 'Kanye',
  'Mochudi', 'Lobatse', 'Palapye', 'Jwaneng', 'Ghanzi', 'Tsabong', 'Letlhakane',
  'Mogoditshane', 'Selebi-Phikwe', 'Mahalapye', 'Tlokweng',
];

/** Suburbs mapped to the town they belong to. */
export const SUBURBS: Record<string, string> = {
  'Block 10': 'Gaborone', 'Block 8': 'Gaborone', 'Block 9': 'Gaborone', 'Block 6': 'Gaborone',
  Phakalane: 'Gaborone', Broadhurst: 'Gaborone', Fairgrounds: 'Gaborone', CBD: 'Gaborone',
  'Extension 10': 'Gaborone', Gaborone: 'Gaborone', 'Gaborone West': 'Gaborone',
  Tlokweng: 'Gaborone', 'Area W': 'Francistown', Boseja: 'Maun',
};

const TYPE_SYNONYMS: Record<PropertyType, string[]> = {
  house: ['house', 'home', 'villa', 'cottage', 'bungalow', 'townhouse'],
  apartment: ['apartment', 'flat', 'unit', 'condo', 'studio'],
  room: ['room', 'backroom', 'student room', 'bachelor'],
  office: ['office', 'workspace'],
  commercial: ['shop', 'retail', 'warehouse', 'commercial'],
  land: ['land', 'plot', 'stand'],
};

const PRICE_WORDS: Record<string, number> = {
  cheap: 3000,
  budget: 4000,
  affordable: 5000,
  premium: 12000,
  expensive: 10000,
  luxury: 15000,
};

const STOP_WORDS = new Set([
  'a', 'an', 'the', 'in', 'at', 'on', 'near', 'for', 'with', 'and', 'or', 'to', 'of', 'i',
  'want', 'need', 'looking', 'find', 'me', 'show', 'rent', 'rental', 'place', 'month', 'per',
  'under', 'below', 'less', 'than', 'max', 'maximum', 'up', 'between', 'bedroom', 'bedrooms',
  'bed', 'beds', 'br', 'pula', 'p', 'furnished', 'is', 'my', 'budget',
]);

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hasWord(query: string, word: string) {
  return new RegExp(`\\b${escapeRegExp(word.toLowerCase())}s?\\b`).test(query);
}

/** "5,000" / "5000" / "5k" → 5000 */
function toAmount(raw: string, k?: string) {
  const n = Number(raw.replace(/,/g, ''));
  return k ? n * 1000 : n;
}

const AMOUNT = String.raw`p?\s?(\d[\d,]*)(k)?`;

export function parseQuery(input: string): SearchParams {
  const query = input.toLowerCase().trim();
  const params: SearchParams = {
    type: null,
    bedrooms: null,
    town: null,
    suburb: null,
    minPrice: null,
    maxPrice: null,
    furnished: /\bfurnished\b/.test(query) && !/\bunfurnished\b/.test(query),
    keywords: [],
  };

  // Property type — check multi-word synonyms first so "student room" wins.
  const synonyms = Object.entries(TYPE_SYNONYMS)
    .flatMap(([type, words]) => words.map((w) => [type as PropertyType, w] as const))
    .sort((a, b) => b[1].length - a[1].length);
  params.type = synonyms.find(([, w]) => hasWord(query, w))?.[0] ?? null;

  const bed = query.match(/(\d+)\s*-?\s*(?:bedroom|bed|br)s?\b/);
  if (bed) {
    const n = Number(bed[1]);
    if (n >= 1 && n <= 10) params.bedrooms = n;
  }

  // Suburb (more specific) before town.
  const suburb = Object.keys(SUBURBS)
    .sort((a, b) => b.length - a.length)
    .find((s) => hasWord(query, s));
  if (suburb && suburb !== SUBURBS[suburb]) {
    params.suburb = suburb;
    params.town = SUBURBS[suburb];
  }
  params.town ??= TOWNS.find((t) => hasWord(query, t)) ?? null;

  // Price: explicit range, then "under X", then price words.
  const range = query.match(new RegExp(`(?:between\\s+)?${AMOUNT}\\s*(?:-|to|and)\\s*${AMOUNT}`));
  const max = query.match(new RegExp(`(?:under|below|less than|max(?:imum)?|up to|budget of)\\s*${AMOUNT}`));
  const min = query.match(new RegExp(`(?:over|above|more than|from|at least)\\s*${AMOUNT}`));
  if (range && toAmount(range[1], range[2]) >= 100) {
    params.minPrice = toAmount(range[1], range[2]);
    params.maxPrice = toAmount(range[3], range[4]);
  } else {
    if (max) params.maxPrice = toAmount(max[1], max[2]);
    if (min) params.minPrice = toAmount(min[1], min[2]);
    if (params.maxPrice === null) {
      const word = Object.keys(PRICE_WORDS).find((w) => hasWord(query, w));
      if (word) params.maxPrice = PRICE_WORDS[word];
    }
  }

  // Whatever is left over is matched against the title and description.
  const known = new Set(
    [
      ...Object.values(TYPE_SYNONYMS).flat(),
      ...Object.keys(PRICE_WORDS),
      ...TOWNS,
      ...Object.keys(SUBURBS),
    ].flatMap((w) => w.toLowerCase().split(/\s+/)),
  );
  params.keywords = query
    .split(/[^a-z]+/)
    .filter((w) => w.length > 2 && !STOP_WORDS.has(w) && !known.has(w) && !known.has(w.replace(/s$/, '')));

  return params;
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

export function search(properties: Property[], query: string) {
  const params = parseQuery(query);
  const results = properties
    .filter((prop) => matches(prop, params))
    .sort((a, b) => score(b, params) - score(a, params) || a.price - b.price);
  return { params, results };
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
  'House in Phakalane',
];
