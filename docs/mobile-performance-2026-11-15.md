# Mobile loading investigation — 15 November 2026

Live baseline: commit `2abe4a53a471cbb11a38542d044438e2c7690907`,
deployment `dpl_8m5Zzhs8UXrZN68dqWzdxHfooTi9`.

## Measurements

Public HTTPS requests from the testing computer (not Rod's phone):

| Page | Initial response, seconds |
| --- | --- |
| Home, first observation | 9.249 |
| Home, three subsequent requests | 1.298 / 1.687 / 1.542 |
| Login, three subsequent requests | 0.451 / 0.479 / 0.582 |

The first slow request alone does not prove a cold start. No error/warning logs
were returned for the inspected 30-minute window.

Headless Chrome, fresh mobile browser context, 390×844 viewport, 4× CPU slowdown,
150 ms simulated network latency, 200,000 bytes/s download, 93,750 bytes/s upload.
Pages visited in this order, retaining browser cache between pages:

| Page | First content displayed | Load event |
| --- | --- | --- |
| Home | 3.648 s | 6.246 s |
| Login | 1.164 s | 1.283 s |
| Map | 2.116 s | 3.245 s |

Single-run diagnostics, not averages or phone guarantees. Public pages only;
no live account credentials or private conversations were accessed. Photo requests
on home took up to 2.64 seconds. Timing does not establish that image size alone
caused their delay. The load event is not the same as readiness to interact.

## Confirmed fault and local correction

The conversation route loaded messages, then committed read receipts. SQLAlchemy
expired all loaded objects at commit. Template rendering then fetched every
message again, causing database round trips proportional to history length.

An isolated generated-data regression test measured 12 SQL statements for 5
messages and 57 for 50 before the fix. Fetching the history after committing read
receipts keeps the no-property conversation at no more than 7 statements for
both sizes. Property-specific conversations are also tested with a fixed bound.
This removes database work; it is not an animation or loading indicator change.

The shared page template now reuses an existing unread count on the inbox page,
instead of issuing the same count query twice.

## Hosting correction prepared

The live deployment reports `iad1` (US), while the established service baseline
places the database in Paris. `vercel.json` selects `cdg1` (Paris) to remove the
cross-Atlantic database path on future deployments. Vercel supports one selected
region on Hobby: https://vercel.com/docs/project-configuration/vercel-json#regions

This configuration does not move the database or change plans. Its improvement
must be measured after deployment; the local query-count tests cannot quantify it.

## Remaining verification

Deploy the reviewed changes, confirm the new deployment region, repeat public
mobile timings, then check signed-in dashboard, inbox and conversation navigation
on Rod's phone. Do not claim that the general mobile issue is fully resolved until
these checks pass. Duplicate-submission protection is a separate outstanding fix.
