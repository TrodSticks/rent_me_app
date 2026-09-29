/**
 * Checks what the LLM returned before it is used: only known towns, suburbs
 * and types, whole-number prices in a sensible range. Anything else is dropped.
 */
import type { PropertyType } from '../data/properties';
import { SUBURBS, TOWNS, type SearchParams } from './search';

const TYPES: PropertyType[] = ['house', 'apartment', 'room', 'office', 'commercial', 'land'];

function pick<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  if (typeof value !== 'string') return null;
  return allowed.find((a) => a.toLowerCase() === value.trim().toLowerCase()) ?? null;
}

function int(value: unknown, min: number, max: number): number | null {
  const n = typeof value === 'string' ? Number(value.replace(/[^\d.]/g, '')) : value;
  return typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max ? Math.round(n) : null;
}

export function sanitizeLLM(raw: unknown): SearchParams | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;

  const suburb = pick(r.suburb, Object.keys(SUBURBS));
  const town = suburb ? SUBURBS[suburb] : pick(r.town, TOWNS);
  let minPrice = int(r.minPrice, 100, 500_000);
  let maxPrice = int(r.maxPrice, 100, 500_000);
  if (minPrice !== null && maxPrice !== null && minPrice > maxPrice) [minPrice, maxPrice] = [maxPrice, minPrice];

  return {
    type: pick(r.type, TYPES),
    bedrooms: int(r.bedrooms, 1, 10),
    town,
    suburb,
    minPrice,
    maxPrice,
    furnished: r.furnished === true,
    keywords: Array.isArray(r.keywords)
      ? r.keywords
          .filter((k): k is string => typeof k === 'string')
          .map((k) => k.toLowerCase().replace(/[^a-z ]/g, '').trim())
          .filter((k) => k.length > 2)
          .slice(0, 5)
      : [],
  };
}

/**
 * Rules win wherever they found something; the LLM fills the gaps.
 * (The rules are exact about the words they know; the LLM covers the rest.)
 */
export function mergeParams(rules: SearchParams, llm: SearchParams): SearchParams {
  const suburb = rules.suburb ?? (rules.town && llm.town !== rules.town ? null : llm.suburb);
  return {
    type: rules.type ?? llm.type,
    bedrooms: rules.bedrooms ?? llm.bedrooms,
    town: rules.town ?? llm.town,
    suburb,
    minPrice: rules.minPrice ?? llm.minPrice,
    maxPrice: rules.maxPrice ?? llm.maxPrice,
    furnished: rules.furnished || llm.furnished,
    keywords: [...new Set([...rules.keywords, ...llm.keywords])],
  };
}
