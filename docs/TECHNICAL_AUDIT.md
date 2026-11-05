# Rent Me technical audit — 14 October 2026

## Follow-up — 5 November 2026

Vercel team access now works. A live deployment-list read confirmed the latest three production deployments are READY; the newest is `dpl_HLKoe2YuDWZEce1WWkWWVSCLbf1V`, built from main commit `2f8cfbd7a412a0bbc37fccf8900b8e735626f1b3`. This resolves the historical deployment-read access blocker, but does not verify live user flows, configuration, capacity or recovery. Historical findings below retain their original audit date. The local persistence test was rerun on 5 November: **1 passed**; the full suite was not rerun.

## Decision

The audit and architecture plan are complete; the application is **not yet cleared for production**. Existing features are substantial, but real email delivery, deployed configuration, hosted restart/redeployment durability, a hosted restore drill, and operational alerts remain unverified or absent. October remains development-only, using local/free tools. No paid services, live data changes, migrations, deployments or purchases were performed during this audit.

Related: [architecture and operating plan](ARCHITECTURE_PLAN.md), [Asana completion text](ASANA_SUMMARY.md), [Asana task](https://app.asana.com/0/1219195318077115/1219195354562319).

## Evidence boundary

- Repository: `TrodSticks/rent_me_app`, main at `2f8cfbd7a412a0bbc37fccf8900b8e735626f1b3`. The clean local checkout initially contained `bc9d4a5`; it was fetched and fast-forwarded before reviewing current implementation. Audit changes are local, uncommitted additions on top of that revision.
- Live checks used read-only Supabase catalog/aggregate queries and advisor tools. No passwords, messages, email addresses, database connection strings or secret values were retrieved for the audit.
- Supabase project `Rent Me` (`pupcwewlhfqsbdxrfwep`) reported `ACTIVE_HEALTHY`, Postgres 17.11, region `eu-west-3`. This is a point-in-time service status, not uptime history.
- Vercel discovery returned `rent-me-app`, project `prj_c6glYUcxFfD16meHFIA3hinXtkKc`, team `team_L1cS4wXi98VUCNhETxpcblWh`. Detailed project and deployment reads returned **403, insufficient scope access**. The Vercel CLI was not installed. Deployed commit, domains, environment values, logs, plan, region, protection, backup subscriptions and alerts were not verified. Project discovery alone does not prove the app is healthy.
- No deployment URL or approved test inbox was supplied. Real email testing was explained to the owner and remains pending. No email was sent.

Status meanings: **Verified complete** applies only to the named check and evidence; **Partially complete** means implementation or some operational evidence exists; **Missing** means absent in inspected repository (external setup may still exist); **Blocked** means the check could not be completed. A blocked check is not a pass.

## Findings

| ID / launch priority | Status | Finding and evidence | Remaining acceptance criterion |
|---|---|---|---|
| DB1 / P0 | Partially complete | `config.py::_database_url/_engine_options` supports psycopg/Postgres, pool pre-ping, disabled prepared statements and Vercel NullPool. Live database has nine public tables and revision `0004_lock_down_data_api`. | Verify the deployed app actually uses this database, TLS settings, connection budget and staging isolation. Run Postgres integration tests. |
| DB2 / P0 | Verified complete (catalog check) | All nine live public tables have RLS enabled; no public policies exist. Security advisor reports nine informational `rls_enabled_no_policy` findings. This matches the server-only design in `app.py::enable_row_level_security` and migration 0004. | Keep denial of browser Data API row access; do not add permissive policies to silence the advisor. See DB3 for remaining privilege risk. |
| DB3 / P1 | Partially complete | Live `anon` and `authenticated` grants still include SELECT/INSERT/UPDATE/DELETE and TRUNCATE/REFERENCES/TRIGGER. RLS protects ordinary row operations, not all table privileges. Application expects an owner connection that bypasses RLS. | Revoke unnecessary grants/default privileges in a reviewed migration; disable unused Data API exposure or move app tables to a private schema. Separate migration and runtime roles, with explicit server-only access design. Do not claim these grants alone create a public HTTP TRUNCATE endpoint. |
| DB4 / P0 | Partially complete | `prepare_database` uses create-all plus stamp for new databases, migration upgrade for existing ones, and a Postgres advisory lock. `vercel_app.py` performs startup migration/seeding. SQLite migration tests pass. | Run full migration chain on clean and prior-version Postgres. Serialize deployment migration outside request startup (`AUTO_MIGRATE=0` at runtime); test lock/connection exhaustion and restore before production. |
| ST1 / P0 | Partially complete | `photos.py` encodes JPEGs and uses Supabase Storage when URL and server key are set. Live `property-photos` bucket is public; 2 photo rows match 2 objects, with 0 missing and 0 unreferenced objects in this snapshot. | Verify actual object bytes/load from deployed site and newly uploaded photo persistence after fresh instance and redeployment. Metadata match is not a byte-integrity or durability test. |
| ST2 / P0 | Blocked | Hosted restart/redeployment test was not performed: deployment access is denied and no staging target/test account was established. `vercel_app.py` otherwise falls back to `/tmp` SQLite/photos, which are temporary. | Run the staged durability procedure in the architecture plan; fail production startup when persistent settings are incomplete. |
| ST3 / P1 | Partially complete | Image validation, orientation, resize to 1200px, random names and rollback cleanup exist (`photos.py`, `listings.py::plan_photos/save_listing`). Bucket has no MIME or file-size restriction. Delete errors are logged but not retried durably. Public URLs do not enforce listing visibility. | Decide private-draft/hidden-photo policy; add bucket limits, reconcile failed deletes/orphans, and validate decompression/pixel budgets. Verify moderation removes access as intended, including cached URLs. |
| AU1 / P1 | Verified complete (local tests) | Flask-Login authentication, verification gates, expiring signed links, reset replay prevention and password-change session invalidation are covered by passing `test_accounts.py`, `test_security.py` and moderation tests. Auth is custom Flask auth, **not Supabase Auth**. | Retest on deployed HTTPS origin/Postgres; address remaining security risks below. |
| EM1 / P0 | Blocked | `mailer.py` implements SMTP/STARTTLS/SSL, file and memory backends; SMTP handoff/failure tests pass with a fake SMTP object. README explicitly says real delivery is untested. | Receive verification and reset messages in an owner-approved real inbox, follow links and log in; verify expired/reused links fail. Check sender authentication, spam delivery and configured origin. |
| DP1 / P0 | Partially complete | `pyproject.toml` defines `vercel_app:app`; dependencies are separated from optional AI packages. Vercel project exists, but detailed access is blocked. | Verify release SHA, production/preview separation, secrets presence without disclosure, stable key, HTTPS, canonical host, proxy trust, runtime region and resource limits. |
| DP2 / P0 | Missing (production guard) | `vercel_app.py` seeds known demo accounts whenever the user table is empty, even with a persistent database. `config.py` permits local/temporary storage and an ephemeral secret-key fallback. | Make demo seeding explicit development/demo-only; require stable secrets, Postgres and photo storage for production. Review existing demo accounts without deleting live data as part of this audit. |
| PF1 / P0 | Partially complete | App permits 10 photos at 5 MiB each and 52 MiB total (`config.py`). Vercel documentation specifies a 4.5 MB function request limit; resize happens only after the upload reaches Flask. | Test hosted upload boundaries and choose a supported upload design. Until then, the advertised maximum gallery upload cannot be assumed to work. |
| PF2 / P1 | Verified complete (bounded-query tests) | Homepage uses count + LIMIT 12/OFFSET, stable ID tie-break; map uses bbox filtering and LIMIT 300 (`routes.py`). `test_performance.py` uses 4,000 generated listings and checks query/loading bounds. Expected indexes exist in live Postgres. | Measure production-like latency/query plans, not just returned row counts. |
| PF3 / P1 | Partially complete | Dashboard, favorites, inbox and conversation use unbounded `.all()` (`listings.py`, `routes.py`). Sequential photo requests each allow 15 seconds; SMTP is synchronous. | Paginate these views, set input/time budgets, measure query counts and concurrency, and decide retry/queue strategy. |
| BK1 / P0 | Missing (operating process) | No scheduled paired database/object backup, manifest verification or restore runbook existed in repository. Local `.bak` files are not proof of a usable production backup. This audit adds the plan. | Execute hosted paired restore and verify retention/off-site copies; assign an owner and alert on backup age/failure. |
| BK2 / P1 | Verified complete (local fixture only) | New `test_persistence.py` passes: writes SQLite rows and a JPEG, recreates the app, backs up SQLite using its backup API, copies photos, restores into separate paths and checks rows/password hash/photo SHA-256. | Does not test Supabase, separate OS process, deployed sessions or Vercel redeployment. Hosted drill remains ST2/BK1. |
| OB1 / P0 | Partially complete | App logs disabled mail, SMTP failures and storage upload/delete failures. Supabase health/advisors can be inspected. No repository health/readiness route, error-tracking integration, external uptime configuration or alert runbook was found. | Implement and exercise the monitoring/alert plan. Vercel logs, drains and externally configured monitors remain blocked, not proven absent. |
| QA1 / P0 | Partially complete | 395 tests passed; four storage tests failed due to sandbox loopback denial. New persistence test separately passed. Installed packages differ from declared deployment versions. No tracked GitHub Actions workflow found. | Run exact pinned deployment dependencies, local fake-storage tests with loopback access, Postgres suite and release smoke tests in CI. Scan dependencies and require passing checks. |

P0 means block public launch; P1 means complete before launch or record explicit owner acceptance of a limited exposure; P2 means optimize based on measured usage.

## Security review details

- CSRF is initialized globally; security tests explicitly enable CSRF although ordinary fixtures disable it. Authorization checks are server-side for listing ownership, conversations and administrator actions. ORM predicates and escaped templates reduce injection risk; this is not a penetration-test certification.
- The minimum password length is six (`security.py`); strengthen the policy and add abuse controls for registration, messaging and uploads. Login/reset/report limits exist, but count-then-insert is not atomic under concurrent requests. Rate-limit buckets use unsalted SHA-256 of predictable identifiers; do not describe this as irreversible anonymization. Test a concurrency-safe design and retention cleanup.
- `PUBLIC_BASE_URL` defaults to the request host. Require the canonical HTTPS origin and validate allowed hosts/proxy trust to prevent hostile recovery-link origins. `TRUSTED_PROXY_COUNT` trusts forwarded host as well as IP/scheme; the actual ingress chain must be verified.
- `GET /logout` changes session state. Convert to CSRF-protected POST. Review CSP, frame restrictions, HSTS, referrer policy and no-store headers for account/token pages; no app-level security-header hook was found. Prevent access-log/error-service collection of token-bearing paths and request bodies. Provider error strings also need redaction review.
- SMTP TLS calls do not supply an explicit `ssl.create_default_context()` in `mailer.py`; verify certificate/hostname validation for the deployed Python runtime and harden both STARTTLS and SMTP_SSL paths with tests. Reject plaintext SMTP in production.
- `User.password_hash` is `String(128)`. Before upgrading Werkzeug, verify hash length and algorithm on Postgres; SQLite does not enforce this length and newer hashes can exceed it. Dependency upgrades require schema compatibility testing, not blind version changes.
- RLS does not isolate one Flask user from another when Flask connects as table owner. Route authorization remains essential. Never expose the storage server key to browser code; the current request construction is server-side.
- Public bucket access means a known image URL can outlive draft/hidden listing visibility. No private documents should go in this bucket. Establish whether published listing photos are intentionally public and how hiding/deletion affects copies and caches.
- No vulnerability scan was completed. `requirements.txt` and `pyproject.toml` have old exact pins alongside unpinned Flask-WTF/Pillow/psycopg. Build a tested lock and scan it; do not infer a specific CVE from package age alone.

## Performance review details

Live advisor found three unindexed foreign keys: `property.hidden_by_id`, `report.resolved_by_id`, `user.landlord_verified_by_id`. Add indexes only after checking expected moderation/admin workloads, or document why unnecessary. It also flagged five currently unused indexes; the live dataset is only 9 properties, so this is not evidence to remove them. See [foreign-key advisor](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys) and [unused-index advisor](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).

Bounding a result does not bound all database work. Counts, wildcard text search, high OFFSET pages and computed similar-property ordering can still scan/sort large sets. Run EXPLAIN on representative staging data; consider keyset pagination, search indexes and spatial indexes only where measurements justify them. Check lazy relationship loads on cards and detail pages. Test traffic from Botswana to the selected function/database region. Keep optional local LLM disabled for the initial hosted release. Review map tile capacity/terms and image caching before public launch.

## Test record

| Command / check | Result and limitation |
|---|---|
| `python -m pytest -q` | Initial sandbox temporary-directory creation failed; run interrupted. Not an app failure. Outside-sandbox retry was rejected; no unrestricted run occurred. |
| `python -m pytest -q --tb=short --basetemp=.pytest_cache/audit-temp-20261014` | **395 passed, 4 failed, 2 deselected**, 164.86 seconds. All four failures had WinError 10013 on HTTP calls to the loopback fake-storage server. No hosted storage calls were made. |
| `python -m pytest tests/test_persistence.py -q --tb=short --basetemp=.pytest_cache/audit-persistence-20261014` | **1 passed**, 1.22 seconds; local restart and paired restore fixture only. Added after the full-suite run. |
| Live catalog/object-reference/advisor checks | Latest revision, RLS flags, grants, bucket settings, counts and indexes inspected read-only. Not an end-to-end application test. |

Failed storage test names: `test_uploads_go_to_the_bucket_not_the_disk`, `test_pages_load_photos_from_the_bucket`, `test_removed_and_deleted_photos_leave_the_bucket`, `test_storage_errors_say_what_supabase_answered`. Keep these tests intact and rerun where loopback is allowed; do not convert failures to skips or call the suite green. Two optional real-model tests were deselected by the repository's default marker configuration.

Local Python was 3.13; package metadata: Flask 3.1.3, SQLAlchemy 2.1.1, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-Migrate 4.1.0, Werkzeug 3.1.9, Flask-WTF 1.3.0, Pillow 12.3.0, pytest 9.1.1. These differ from the declared Flask 2.3.3, SQLAlchemy 2.0.21, Flask-SQLAlchemy 3.0.5, Flask-Migrate 4.0.5 and Werkzeug 2.3.7. No claim is made that this validates the deployment dependency set.

## Changes made within this audit

1. Isolated test settings in `tests/conftest.py`: empty service settings now prevent `.env` from supplying live Supabase/SMTP configuration. A test-only signing key and explicit migration mode make the suite predictable. Existing storage tests still inject their own fake server.
2. Added `tests/test_persistence.py` to verify local rows and photo bytes survive app recreation and a paired local restore.
3. Added this audit, architecture/backup/monitoring runbook and paste-ready Asana summary. No production feature, configuration or data was changed.

## Prioritized work by month

Suggested accountable owner for all work: Rodney; delegate development and operations actions explicitly before launch. These are proposed follow-ups, not new Asana tasks or purchased infrastructure.

| When | Priority | Action / finding IDs | Evidence required to close |
|---|---|---|---|
| October, free/local | P0 | Reproduce release dependencies and complete tests (QA1) | Locked clean environment, full suite including fake-storage HTTP, Postgres migration/auth tests, dependency scan and required CI checks. |
| October, free/local | P0 | Add production configuration guards and explicit demo mode (DP2, ST2) | Tests reject missing persistent DB/storage/stable key; production empty database never seeds demo accounts. |
| October, free/local | P0 | Resolve deployment access; inventory settings without values (DP1) | Correct team access, release SHA, environment scope and domain/region checklist recorded. Preview never shares production credentials. |
| October, free tier or local prototype | P0 | Resolve upload envelope (PF1) | Hosted boundary test; supported smaller total payload or secure direct-upload workflow with server-side validation and authorization. |
| October, free/local | P0 | Prepare backup scripts/manifest and staged durability/restore drills (ST2, BK1) | Local drills now; hosted drills only in an isolated free staging target with access. Record hashes, row counts, timing and missing-object count. |
| October, existing/free SMTP only | P0 | Real verification/reset delivery (EM1) | Owner-approved inbox receives messages; complete flows and failure/replay checks pass. If no provider exists, remain blocked until provisioned. |
| October, free/local | P0 | Add health/readiness, sanitized error tracking and alert rehearsal (OB1) | Simulated failure produces one actionable notification and recovery event; no secrets/tokens logged. |
| October, free/local | P1 | Harden auth/TLS/host/proxy/rate limits and storage privacy (AU1, ST3, DB3) | Focused tests; reviewed grants and runtime-role design; explicit public-photo decision. |
| October, free/local | P1 | Paginate remaining views and profile representative data (PF3) | Query plans and latency/load results; no unbounded account views. |
| November, infrastructure decision | P0 | Choose production hosting/database/storage/SMTP capacity | Owner approves spend then provisions appropriate plans; document limits, region, access, support and budget alerts. No automatic upgrade is authorized by this document. |
| November, before launch | P0 | Enable durable backup destination and managed DB backup/PITR if justified | Chosen recovery targets met; independent photo backup retained; full hosted restore drill passes. |
| November, before launch | P0 | Production domain, mail sender, monitoring and launch rehearsal | HTTPS and sender authentication, real email, redeploy durability, on-call alerts, rollback and restore sign-off. |
| November / measured growth | P2 | Paid capacity, tile service, queues or additional indexes | Measurements justify expense; revisit targets and budget before changing plans. |

Audit completion does not depend on all follow-ups being implemented. Public launch does depend on closing P0 items and accepting any remaining P1 risks explicitly.

## External references checked

- [Supabase backups](https://supabase.com/docs/guides/platform/backups): database backups exclude object bytes; free-tier projects should maintain exports/off-site copies. Actual project backup entitlement was not inspected.
- [Vercel function limits](https://vercel.com/docs/functions/limitations): 4.5 MB request limit, relevant to PF1.
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control) and [RLS without policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- [Supabase changelog](https://supabase.com/changelog): reviewed relevant Data API exposure changes; rely on observed grants/RLS, not assumed defaults. The markdown endpoint could not be fetched; HTML was used. Policies and limits can change; recheck before November provisioning.
