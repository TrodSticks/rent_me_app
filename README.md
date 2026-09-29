# Rent Me

**Find a place. Call it home.** A mobile app for renting houses, apartments,
rooms and offices across Botswana. Renters search in plain language
("2 bedroom house in Gaborone under P5,000"); landlords and agents list properties.

Built with **Expo (React Native) + Expo Router + TypeScript**. The backend will be
**Supabase** (auth, database, photo storage, chat), which isn't connected yet;
screens currently use sample listings in `src/data/properties.ts`.

## Run it

```bash
npm install
npx expo start        # then press a (Android), i (iOS) or w (web), or scan the QR code with Expo Go
```

Checks: `npx expo lint` and `npx tsc --noEmit`.

## Project layout

| Path | What's there |
| --- | --- |
| `src/app/` | Screens (every file is a route) |
| `src/app/index.tsx` | 01 Welcome |
| `src/app/(auth)/` | 02 Sign up (Google / Apple / Email), sign up with email, sign in |
| `src/app/(tabs)/` | Bottom tabs: Home, Saved, Bookings, Profile |
| `src/app/search.tsx` | 04 Search results |
| `src/components/` | Logo, buttons, property card, search box, form fields |
| `src/constants/theme.ts` | Brand colours, Manrope font weights, spacing |
| `src/lib/search.ts` | Plain-language search parser (ported from the Flask app) |
| `src/lib/session.tsx` | Temporary in-memory login + saved properties |
| `scripts/generate-icons.mjs` | Renders the app icon / splash PNGs from the logo |
| `legacy-flask/` | The original Flask prototype, kept for reference |

## Smart search (rules first, LLM as backup)

1. **Rules** (`src/lib/search.ts`) understand English, common Setswana, number words
   ("two", "pedi"), nicknames ("gabs"), small typos ("bedrom hous") and price styles
   ("5k", "4 and a half", "not more than 3500"). Instant, offline, free.
2. If some words are not understood, the app asks the **`parse-search` Edge Function**
   (`supabase/functions/parse-search`), which calls an open-source LLM through any
   OpenAI-compatible API. The answer is validated (`src/lib/search-llm.ts`) and merged;
   if it fails or takes over 4 s, the rules' result is used.

**Measure it:** `npm run eval:search` scores the test sentences in `eval/search-cases.ts`
(English, Setswana, mixed, plus a held-out set). Set `LLM_BASE_URL` / `LLM_MODEL`
(see `.env.example`) to also score the LLM on its own and the combined search.

**Deploy the LLM backup** (once Supabase is set up):

```bash
npx supabase secrets set LLM_BASE_URL=... LLM_MODEL=... LLM_API_KEY=...
npx supabase functions deploy parse-search
```

## Accounts

Sign-up offers three roles: **Renter**, **Landlord** and **Agent** (agents also give
their agency name). Landlords and agents get the same listing tools.

## Status

- [x] Brand theme, logo, app icon, splash
- [x] Welcome, sign up, sign up with email, sign in
- [x] Home with plain-language search, suggestions and featured listings
- [x] Search results with filters
- [x] Smart search: better rules + LLM backup + test set (LLM goes live with Supabase)
- [ ] Supabase backend (real accounts, listings, photos)
- [ ] Property details, map view, saved, messages, book a viewing, profile
- [ ] Landlord dashboard and add property
