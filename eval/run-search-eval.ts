/**
 * Measures how well search understands the test sentences in search-cases.ts.
 *
 *   npm run eval:search                       # rules only
 *   LLM_BASE_URL=… LLM_MODEL=… [LLM_API_KEY=…] npm run eval:search
 *                                             # + LLM alone, and rules → LLM backup
 *   … npm run eval:search -- --verbose        # show every failure
 *
 * A sentence passes only if every filter is right (and nothing extra is set).
 */
import { PROMPT_SUBURBS, PROMPT_TOWNS, callLLM } from '../supabase/functions/_shared/search-prompt';
import { SUBURBS, TOWNS, parseQuery, type SearchParams } from '../src/lib/search';
import { mergeParams, sanitizeLLM } from '../src/lib/search-llm';
import { CASES, type Expected, type SearchCase } from './search-cases';

const FIELDS = ['type', 'bedrooms', 'town', 'suburb', 'minPrice', 'maxPrice', 'furnished'] as const;
const verbose = process.argv.includes('--verbose');

if (JSON.stringify(PROMPT_TOWNS) !== JSON.stringify(TOWNS) || JSON.stringify(PROMPT_SUBURBS) !== JSON.stringify(SUBURBS)) {
  console.error('✗ Town/suburb lists in supabase/functions/_shared/search-prompt.ts differ from src/lib/search.ts');
  process.exit(1);
}

function diff(got: SearchParams, want: Expected) {
  return FIELDS.filter((f) => (got[f] ?? (f === 'furnished' ? false : null)) !== (want[f] ?? (f === 'furnished' ? false : null))).map(
    (f) => `${f}: got ${JSON.stringify(got[f])}, want ${JSON.stringify(want[f] ?? null)}`,
  );
}

type Row = { c: SearchCase; errors: string[]; ms: number };

function report(name: string, rows: Row[]) {
  const pass = (rs: Row[]) => rs.filter((r) => r.errors.length === 0).length;
  const pct = (rs: Row[]) => (rs.length ? `${Math.round((100 * pass(rs)) / rs.length)}%`.padStart(4) : '   –');
  const group = (pred: (c: SearchCase) => boolean) => rows.filter((r) => pred(r.c));
  const fieldsRight = rows.length * FIELDS.length - rows.reduce((n, r) => n + r.errors.length, 0);
  const avgMs = rows.reduce((n, r) => n + r.ms, 0) / rows.length;

  console.log(`\n${name}`);
  console.log(`  All sentences     ${pct(rows)}  (${pass(rows)}/${rows.length})   fields right: ${Math.round((100 * fieldsRight) / (rows.length * FIELDS.length))}%   avg ${avgMs.toFixed(avgMs < 10 ? 2 : 0)} ms`);
  console.log(`  English — easy    ${pct(group((c) => c.lang === 'en' && c.level === 'easy'))}`);
  console.log(`  English — messy   ${pct(group((c) => c.lang === 'en' && c.level === 'hard'))}`);
  console.log(`  Setswana          ${pct(group((c) => c.lang === 'tn'))}`);
  console.log(`  Mixed             ${pct(group((c) => c.lang === 'mixed'))}`);
  console.log(`  Held-out (unseen) ${pct(group((c) => !!c.holdout))}   ← the honest number`);
  const failed = rows.filter((r) => r.errors.length);
  if (failed.length) {
    console.log(`  Failures:`);
    for (const r of verbose ? failed : failed.slice(0, 8)) console.log(`   ✗ "${r.c.query}"  →  ${r.errors.join('; ')}`);
    if (!verbose && failed.length > 8) console.log(`   … ${failed.length - 8} more (use --verbose)`);
  }
}

async function main() {
  const rules: Row[] = CASES.map((c) => {
    const t = performance.now();
    const { unknown: _unknown, ...p } = parseQuery(c.query);
    return { c, errors: diff(p, c.expect), ms: performance.now() - t };
  });
  report('RULES ONLY', rules);

  const baseUrl = process.env.LLM_BASE_URL;
  const model = process.env.LLM_MODEL;
  if (!baseUrl || !model) {
    console.log('\n(Set LLM_BASE_URL and LLM_MODEL to also measure the LLM.)');
    return;
  }

  const llmOnly: Row[] = [];
  const hybrid: Row[] = [];
  let llmCalls = 0;
  for (const c of CASES) {
    const t = performance.now();
    let llm: SearchParams | null = null;
    try {
      llm = sanitizeLLM(await callLLM(c.query, { baseUrl, model, apiKey: process.env.LLM_API_KEY }));
    } catch (e) {
      console.error(`  LLM error on "${c.query}": ${(e as Error).message}`);
    }
    const ms = performance.now() - t;
    const empty: SearchParams = { type: null, bedrooms: null, town: null, suburb: null, minPrice: null, maxPrice: null, furnished: false, keywords: [] };
    llmOnly.push({ c, errors: diff(llm ?? empty, c.expect), ms });

    const { unknown, ...r } = parseQuery(c.query);
    const useLLM = unknown.length > 0 && llm;
    if (unknown.length > 0) llmCalls++;
    hybrid.push({ c, errors: diff(useLLM ? mergeParams(r, llm!) : r, c.expect), ms: unknown.length > 0 ? ms : 0 });
  }
  report(`LLM ONLY (${model})`, llmOnly);
  report(`RULES → LLM BACKUP (LLM called for ${llmCalls}/${CASES.length})`, hybrid);
}

main();
