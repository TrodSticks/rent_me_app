# Published mobile performance fixes

Published with Rod's approval on 15 November 2026.

- Commit: `6ab12100dcaafb663b3ac597b110858d5f8a74a0`
- Production deployment: `dpl_57Gb3DR6wAWeYP7Nc3U6KLnvaNnq`
- URL: https://rent-me-app-rho.vercel.app
- Verified status: READY; production alias assigned; region `cdg1` (Paris).
- Build duration: approximately 13 seconds.
- No paid plan changes or database migrations introduced.

## Repeat measurements

Same testing computer and mobile emulation settings as the investigation report.
Single browser run before/after; these are observations, not statistical proof.

| Mobile page | First content before | First content after | Load event before | Load event after |
| --- | --- | --- | --- | --- |
| Home | 3.648 s | 3.440 s | 6.246 s | 6.077 s |
| Login | 1.164 s | 0.732 s | 1.283 s | 0.821 s |
| Map | 2.116 s | 0.980 s | 3.245 s | 2.428 s |

Three separate home HTTP requests after release returned HTTP 200 and first-byte
times of 0.981 / 0.444 / 0.398 seconds (baseline 1.298 / 1.687 / 1.542).
Login first-byte times were 0.510 / 0.478 / 0.452 seconds, all HTTP 200.

The chat database-query fix is included in the deployed commit; its reduction was
verified locally using generated conversations. Private live chats were not opened
or sent to. Actual signed-in mobile chat improvement still needs Rod's test.

Home rendering still needs attention: the improvement in the simulated mobile
run was small, with photo requests still taking approximately 2.4–2.6 seconds.
Do not mark the overall mobile speed issue resolved from these tests alone.
Repeated-send protection remains a separate outstanding issue.
