/**
 * Test sentences for the plain-language search, with the filters a person
 * would expect. Used by `npm run eval:search` to measure the rules and the LLM.
 *
 * Any field left out of `expect` must come back empty (null / false).
 * The Setswana sentences were written without a native speaker. Please have
 * one check them, and add real searches from users once the app is live.
 */
import type { PropertyType } from '../src/data/properties';

export type Expected = {
  type?: PropertyType;
  bedrooms?: number;
  town?: string;
  suburb?: string;
  minPrice?: number;
  maxPrice?: number;
  furnished?: boolean;
};

export type SearchCase = {
  query: string;
  lang: 'en' | 'tn' | 'mixed';
  /** easy = the old rules should manage; hard = needs flexible understanding. */
  level: 'easy' | 'hard';
  expect: Expected;
  /** Held out: written after the rules were tuned, so they measure unseen input. */
  holdout?: boolean;
};

export const CASES: SearchCase[] = [
  // --- English, straightforward ---
  { query: 'cheap 2 bedroom house in Gaborone', lang: 'en', level: 'easy', expect: { type: 'house', bedrooms: 2, town: 'Gaborone', maxPrice: 3000 } },
  { query: '2 bedroom house in Gaborone under P5,000', lang: 'en', level: 'easy', expect: { type: 'house', bedrooms: 2, town: 'Gaborone', maxPrice: 5000 } },
  { query: '1 bedroom apartment in Gaborone', lang: 'en', level: 'easy', expect: { type: 'apartment', bedrooms: 1, town: 'Gaborone' } },
  { query: '3 bedroom house under P7,000', lang: 'en', level: 'easy', expect: { type: 'house', bedrooms: 3, maxPrice: 7000 } },
  { query: 'furnished apartment', lang: 'en', level: 'easy', expect: { type: 'apartment', furnished: true } },
  { query: 'office space', lang: 'en', level: 'easy', expect: { type: 'office' } },
  { query: 'house in Phakalane', lang: 'en', level: 'easy', expect: { type: 'house', town: 'Gaborone', suburb: 'Phakalane' } },
  { query: 'flat in Francistown under 4000', lang: 'en', level: 'easy', expect: { type: 'apartment', town: 'Francistown', maxPrice: 4000 } },
  { query: '2br flat Block 10 P3000 to P6000', lang: 'en', level: 'easy', expect: { type: 'apartment', bedrooms: 2, town: 'Gaborone', suburb: 'Block 10', minPrice: 3000, maxPrice: 6000 } },
  { query: 'room in Maun', lang: 'en', level: 'easy', expect: { type: 'room', town: 'Maun' } },
  { query: 'plot for rent in Mogoditshane', lang: 'en', level: 'easy', expect: { type: 'land', town: 'Mogoditshane' } },
  { query: 'shop space in Francistown', lang: 'en', level: 'easy', expect: { type: 'commercial', town: 'Francistown' } },
  { query: '3 bed house in Tlokweng max 6k', lang: 'en', level: 'easy', expect: { type: 'house', bedrooms: 3, town: 'Gaborone', suburb: 'Tlokweng', maxPrice: 6000 } },

  // --- English, messy / flexible ---
  { query: '2 bedrom hous in gabs', lang: 'en', level: 'hard', expect: { type: 'house', bedrooms: 2, town: 'Gaborone' } },
  { query: 'two bedroom apartment in gaborone', lang: 'en', level: 'hard', expect: { type: 'apartment', bedrooms: 2, town: 'Gaborone' } },
  { query: 'three bedroom house francistown', lang: 'en', level: 'hard', expect: { type: 'house', bedrooms: 3, town: 'Francistown' } },
  { query: 'house in gabs budget around 4 and a half', lang: 'en', level: 'hard', expect: { type: 'house', town: 'Gaborone', maxPrice: 4500 } },
  { query: 'apartment in Gaborone for about P4500', lang: 'en', level: 'hard', expect: { type: 'apartment', town: 'Gaborone', maxPrice: 4500 } },
  { query: 'place to stay in Maun not more than 3500 a month', lang: 'en', level: 'hard', expect: { town: 'Maun', maxPrice: 3500 } },
  { query: 'studio in francistwon', lang: 'en', level: 'hard', expect: { type: 'apartment', town: 'Francistown' } },
  { query: 'somewhere for me and my 2 kids in Gaborone, nothing crazy expensive', lang: 'en', level: 'hard', expect: { town: 'Gaborone', maxPrice: 5000 } },
  { query: 'backroom in Mogodishane below 1500', lang: 'en', level: 'hard', expect: { type: 'room', town: 'Mogoditshane', maxPrice: 1500 } },
  { query: 'i need a fully furnished 1 bed in phakalane', lang: 'en', level: 'hard', expect: { bedrooms: 1, town: 'Gaborone', suburb: 'Phakalane', furnished: true } },
  { query: 'unfurnished house in Lobatse', lang: 'en', level: 'hard', expect: { type: 'house', town: 'Lobatse' } },
  { query: 'house in Palapye between 3 and 5 thousand', lang: 'en', level: 'hard', expect: { type: 'house', town: 'Palapye', minPrice: 3000, maxPrice: 5000 } },

  // --- Setswana ---
  { query: 'ntlo kwa Gaborone', lang: 'tn', level: 'hard', expect: { type: 'house', town: 'Gaborone' } },
  { query: 'ke batla ntlo e nnye kwa Tlokweng', lang: 'tn', level: 'hard', expect: { type: 'house', town: 'Gaborone', suburb: 'Tlokweng' } },
  { query: 'ke batla phaposi kwa Maun', lang: 'tn', level: 'hard', expect: { type: 'room', town: 'Maun' } },
  { query: 'ntlo ya diphaposi tse pedi kwa Francistown', lang: 'tn', level: 'hard', expect: { type: 'house', bedrooms: 2, town: 'Francistown' } },
  { query: 'ntlo ya diphaposi tse tharo kwa Gaborone', lang: 'tn', level: 'hard', expect: { type: 'house', bedrooms: 3, town: 'Gaborone' } },
  { query: 'ntlo e e sa tureng kwa Molepolole', lang: 'tn', level: 'hard', expect: { type: 'house', town: 'Molepolole', maxPrice: 3000 } },
  { query: 'kamore kwa Kanye ka P1500', lang: 'tn', level: 'hard', expect: { type: 'room', town: 'Kanye', maxPrice: 1500 } },
  { query: 'lefelo la kgwebo kwa Gaborone', lang: 'tn', level: 'hard', expect: { type: 'commercial', town: 'Gaborone' } },
  { query: 'setsha kwa Mochudi', lang: 'tn', level: 'hard', expect: { type: 'land', town: 'Mochudi' } },

  // --- Mixed Setswana / English ---
  { query: 'ke batla 2 bedroom house kwa Gabs', lang: 'mixed', level: 'hard', expect: { type: 'house', bedrooms: 2, town: 'Gaborone' } },
  { query: 'flat e e sa tureng in Francistown', lang: 'mixed', level: 'hard', expect: { type: 'apartment', town: 'Francistown', maxPrice: 3000 } },
  { query: 'ntlo in Block 8 under 5k', lang: 'mixed', level: 'hard', expect: { type: 'house', town: 'Gaborone', suburb: 'Block 8', maxPrice: 5000 } },

  // --- Held out: NOT used when tuning the rules (honest measure of new input) ---
  { holdout: true, query: 'looking for a 4 bedroom house in Serowe', lang: 'en', level: 'easy', expect: { type: 'house', bedrooms: 4, town: 'Serowe' } },
  { holdout: true, query: 'apartmnt in broadhurst max P5500', lang: 'en', level: 'hard', expect: { type: 'apartment', town: 'Gaborone', suburb: 'Broadhurst', maxPrice: 5500 } },
  { holdout: true, query: 'affordable room near Jwaneng mine', lang: 'en', level: 'hard', expect: { type: 'room', town: 'Jwaneng', maxPrice: 5000 } },
  { holdout: true, query: 'luxury villa phakalane golf estate', lang: 'en', level: 'hard', expect: { type: 'house', town: 'Gaborone', suburb: 'Phakalane', maxPrice: 15000 } },
  { holdout: true, query: 'Need a bachelor pad in Kasane for 2500', lang: 'en', level: 'hard', expect: { type: 'apartment', town: 'Kasane', maxPrice: 2500 } },
  { holdout: true, query: 'warehouse to rent in Gaborone West', lang: 'en', level: 'easy', expect: { type: 'commercial', town: 'Gaborone', suburb: 'Gaborone West' } },
  { holdout: true, query: 'my budget is 3k, one bedroom flat mogoditshane', lang: 'en', level: 'hard', expect: { type: 'apartment', bedrooms: 1, town: 'Mogoditshane', maxPrice: 3000 } },
  { holdout: true, query: 'house with at least 3 bedrooms in lobatse', lang: 'en', level: 'hard', expect: { type: 'house', bedrooms: 3, town: 'Lobatse' } },
  { holdout: true, query: 'offices in the CBD from P10000', lang: 'en', level: 'easy', expect: { type: 'office', town: 'Gaborone', suburb: 'CBD', minPrice: 10000 } },
  { holdout: true, query: 'student accommodation close to UB', lang: 'en', level: 'hard', expect: { type: 'room', town: 'Gaborone' } },
  { holdout: true, query: 'ke batla ntlo ya diphaposi tse nne kwa Palapye', lang: 'tn', level: 'hard', expect: { type: 'house', bedrooms: 4, town: 'Palapye' } },
  { holdout: true, query: 'matlo a a hirisiwang kwa Kanye', lang: 'tn', level: 'hard', expect: { type: 'house', town: 'Kanye' } },
  { holdout: true, query: 'kamore e e sa tureng kwa Mmopane', lang: 'tn', level: 'hard', expect: { type: 'room', town: 'Gaborone', suburb: 'Mmopane', maxPrice: 3000 } },
  { holdout: true, query: 'ntlo e kgolo kwa Maun ka P8000', lang: 'tn', level: 'hard', expect: { type: 'house', town: 'Maun', maxPrice: 8000 } },
  { holdout: true, query: 'ke batla flat kwa Francistown, 2 bedroom', lang: 'mixed', level: 'hard', expect: { type: 'apartment', bedrooms: 2, town: 'Francistown' } },
  { holdout: true, query: 'room kwa Block 6 e e sa tureng', lang: 'mixed', level: 'hard', expect: { type: 'room', town: 'Gaborone', suburb: 'Block 6', maxPrice: 3000 } },
];
