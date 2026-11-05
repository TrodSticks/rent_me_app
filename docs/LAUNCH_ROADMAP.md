# Rent Me: Gaborone-first launch roadmap

5 November 2026. This is the working delivery plan, not a claim that the listed work is complete.

## Destination

Launch a reliable rental service for Gaborone and its surroundings first. Expand only after the local service works well. Retain the existing Flask app; focus on launch gaps rather than a rewrite.

Proposed first service area: Gaborone, Phakalane, Tlokweng, Mogoditshane, Gabane, Mmopane and Metsimotlhabe. Confirm the final boundary before implementing it. Existing nationwide listings must be retained; restrict phase-one publishing and discovery consistently without deleting old data. The current code still contains nationwide locations: this document changes the delivery focus, not the running application.

## Where we are

- Core listings, photos, accounts, messaging, favourites, search, maps and moderation exist.
- Vercel access is restored. Latest deployment checked before the documentation push was READY at `2f8cfbd`.
- Actual simultaneous-user capacity is UNKNOWN. No controlled load-test report exists.
- The October audit recorded 395 passing tests and four local-network-related storage failures, plus two deselected optional tests. A separate local backup/restore test passed again on 5 November. This is not a full green test suite or hosted recovery proof.
- Real email delivery, hosted data durability, backup recovery, production safeguards, upload compatibility and operational alerts still need completion or live evidence.

## Delivery order and exit gates

Effort estimates below are planning ranges for focused development work, not promised calendar dates. Access, service configuration and failed tests can extend them. Do not purchase services automatically.

| Step | Work | Finished when | Rough effort |
|---|---|---|---|
| 1. Establish a safe baseline | Inventory current hosting/database/storage/mail settings and plan limits without exposing secrets. Create isolated staging with separate database, photo storage and credentials; capture outbound test mail. Add basic health checks and measurements. Reproduce release dependencies and rerun tests, including Postgres. | Test traffic cannot reach production data or send real bulk email; exact build and resources are recorded; normal user flows pass. | 2–4 working days |
| 2. Measure today's app | Build a repeatable fake-data generator and load-test scripts. Run the unchanged application build in production-like staging at recorded resource limits. | Baseline report shows latency, failures, request rate and simultaneous active users; limitations versus production are explicit. | 2–3 days after step 1 |
| 3. Close launch infrastructure gaps | Reject temporary database/photo storage and missing stable secrets in production; disable automatic demo accounts; move migrations into controlled releases; fix upload limits; verify account email; implement backup/restore, alerts and release checks. Review permissions, session security and abuse controls. | Hosted restart/redeploy, email, photo upload, restore and alert drills pass; full required checks pass; rollback is rehearsed. | 5–10 days, overlapping search work where possible |
| 4. Make Gaborone search useful | Implement the agreed service area across forms, search, map and recommendations. Add neighbourhoods and local naming variants; improve filters and ranking against labelled search examples. Paginate remaining large account views. | Out-of-area publishing is blocked with a clear explanation; existing data is retained; search quality targets pass. | 3–5 days |
| 5. Re-test and invite a small pilot | Repeat the baseline workload after fixes, then spike and sustained tests. Invite roughly 20–50 real renters/landlords and gather feedback on real listings. | Measured capacity has headroom; no critical flow failures or unexplained data loss; pilot issues are resolved; someone owns support and alerts. | 2–3 test days plus 1–2 weeks of pilot observation |
| 6. Public launch | Publish only real approved listings; verify domain, sender, reporting/help and account/privacy information; record release and recovery sign-off. | All launch gates below have evidence. Start within measured limits and monitor actual demand. | Gate-based, not a fixed date |

Planning expectation: several weeks of focused work plus a small pilot, not an immediate public launch. Re-estimate after the first baseline and infrastructure inspection.

## When can we stress test?

Local data-volume experiments can begin as the next development task. The first meaningful hosted load test follows isolated staging and monitoring: approximately 4–7 focused working days for steps 1–2 if access and resources are available. This does not require every launch feature to be finished.

The baseline must use the current application build, with test isolation supplied through configuration. Label any differences from production. A local laptop result cannot establish Vercel capacity. Testing staging on smaller resources cannot establish larger production capacity either.

Before running hosted load, record the exact target, resource quotas, allowed test volume, maximum duration, spending cap and stop conditions. Check the providers' current test policies. Keep production and unrelated third-party services outside the load target. Use a controlled mail sink and stub external map tiles; test real photo and email integrations separately with small bounded checks.

## Fake accounts and useful search data

Fake accounts alone do not improve property search: search needs varied listings and known-good answers.

Create repeatable datasets in stages: 1,000, then 10,000, then 100,000 synthetic accounts only if smaller runs and storage budgets permit. Suggested associated listing sizes: 2,000, 20,000 and 100,000. These are test dataset sizes, NOT supported-user claims. Make account/listing counts independently configurable. Mix renters, landlords with multiple properties, favourites, conversations, reports and realistic photo counts. Use small licensed/generated fixture photos initially; measure realistic image sizes in a separate upload test.

Use invented identities and reserved test email addresses. Capture all outbound mail. Tag every generated record and object with a run identifier; support repeatable seeds, count validation and scoped cleanup of that run only. Do not use the existing destructive sample-data reset against shared data. Seed in bounded batches and report partial failures. Keep all synthetic listings private to staging; do not present fake landlords, messages or demand to the public.

Include varied prices, property types, bedroom counts, amenities, unavailable/draft/hidden listings and clustered map locations. Use realistic Gaborone-area distributions, not identical random rows. Preserve a smaller fixed dataset for fast regression tests.

Create at least 100 labelled searches with expected filters and relevant results, including misspellings, neighbourhood aliases, price limits, contradictory requests and zero-result cases. Example intents: “2 bedroom in Tlokweng under P4000”, “room in Mogoditshane”, and “Phakalane house with parking”. Keep a held-out set that is not used to tune ranking. Proposed launch target: at least 90% of answerable test searches show a labelled relevant listing in the first five results; hard price/location/visibility restrictions must always be respected. Report parser accuracy separately from ranking. Confirm the thresholds against real pilot feedback.

## Measuring how many users we can handle

Report separately: stored accounts, stored listings, simultaneously active people, requests per second, and expected daily usage under explicit activity assumptions. Never translate “100,000 stored accounts” into “100,000 people online”.

1. Start with 1–5 simulated users and verify correctness, session isolation and CSRF handling.
2. Try 10, 25, 50, 100 and 200 simultaneously active users, advancing only while the previous level passes. Higher levels need remaining budget and evidence. Include realistic pauses so users behave like people.
3. Use an initial workload of 40% search/list browsing, 25% property pages, 15% map requests, 10% login/favourites and 10% messages/listing actions. State the assumptions, account for authenticated roles, and replace the mix with real pilot usage later. Exercise upload size/concurrency separately.
4. Hold each level for 10–15 minutes after warm-up. Record cold-start behaviour separately. Repeat the candidate passing level; then run a 60–120 minute sustained test and a bounded spike/recovery test.
5. Initial proposed pass criteria: p95 core page/API response below 2 seconds (95 of 100 responses finish within 2 seconds), unexpected request failures below 1%, no lost/cross-account data, and no exhausted database connections or service quotas. Report expected rate-limit responses separately. Image transfer and browser page rendering have separate measurements, including Botswana/mobile latency.
6. Stop increasing load on threshold failure. Stop the run immediately for data-integrity issues, production-target detection, connection exhaustion, spending-cap breach, or more than 5% unexpected failures for a minute. Investigate and verify recovery before rerunning.

Record CPU/memory where available, database connections and slow queries, runtime duration, storage/egress, rate limits, errors, mail/photo failures and estimated cost. Include tested commit, dependency versions, dataset seed/counts, region, plans/limits, duration, workload, latency percentiles and recovery time. Keep tokens and personal data out of reports.

The capacity statement should read: “Build X sustained Y active users at Z requests/second with this dataset, workload and resource setup.” Set the initial operating target below the highest repeatedly passing level, initially around 50–70%, then validate that headroom during the pilot. If the load generator or budget reaches its limit first, report “at least Y tested”, not the app's maximum.

## Infrastructure still to finish or verify

- Separate test and production services; inventory limits, regions, database connection pooling, TLS and stable configuration.
- Production startup safeguards; no temporary storage or automatic demo users.
- Controlled database migrations, dependency locking/scanning and automated release tests.
- Host-compatible photo upload limits with matching UI; object validation, privacy rules and failed-delete reconciliation.
- Real verification/reset email delivery, correct public links and safe retry/failure behaviour.
- Database AND photo backups, independent copies, tested restoration and a named recovery owner.
- Health checks, error/latency monitoring, quota/budget alerts and tested notification delivery.
- Measured database/query performance, pagination of growing views and rate-limit retention.
- Reviewed access permissions, session/host/proxy settings, spam/reporting controls and moderation workflow.
- Domain/HTTPS checks, rollback procedure and documented support ownership.

## Public-launch gate

Do not mark launch-ready until: required tests pass; synthetic data is excluded from production; the agreed Gaborone area is enforced; real sign-up/reset/listing/message flows pass; photo/data persistence survives redeployment; paired restore succeeds within agreed recovery targets; alerts reach a named operator; load-test capacity and operating headroom are documented; and the real-user pilot passes. Record any accepted lower-priority issues explicitly. No capacity number or launch date is guaranteed before these checks.

Next implementation task: inspect current infrastructure settings and build isolated staging plus the repeatable fake-data/load-test harness. No mass account creation or load test has been executed by writing this plan.

## Reference checks

Checked on 5 November 2026: [Vercel function limits](https://vercel.com/docs/functions/limitations) document a 4.5 MB request/response payload ceiling, which must be reconciled with the app's larger photo-upload allowance. [Grafana k6 thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/) support explicit latency/error pass-fail criteria; the targets in this roadmap are proposed product targets, not provider guarantees.
