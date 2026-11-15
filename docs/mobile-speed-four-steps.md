# Mobile speed: four-step follow-up, 15 November 2026

## Changes

1. Chat submits a small JSON request and updates in place. An immediately visible
   pending bubble is confirmed only after saving. Repeated taps are blocked;
   interrupted sends retain the draft and submission ID, including across reloads
   in the same tab. A database uniqueness constraint prevents concurrent retries
   from producing duplicates. New-message forms retain their non-JavaScript path.
   Chat history is fetched 50 messages at a time; older messages remain accessible.
   New messages are checked every 15 seconds only while the chat is visible and
   online, without overlapping requests or polling during an unresolved send.
2. Public CSS, JavaScript and app icons use content-hashed URLs with one-year
   immutable caching. Changed files get different URLs. Dynamic pages and message
   responses have private/no-store headers; no service worker caches private data.
3. Listing cards use 320/640-pixel WebP previews. Full photos remain on detail
   pages. Previews use Pillow and existing hosting, with one-day browser/CDN
   caching; unavailable previews fall back to originals. No paid image service.
4. Signed-in Dashboard, Inbox, Account and Chat were measured using isolated test
   accounts. Inbox/Account now load only each thread's latest message and counts,
   instead of loading every message body. Chat rendering completes before the
   read-receipt commit expires objects, avoiding unnecessary reloads.

## Verification

- Full Python suite: 431 passed initially, with 5 failures caused by restricted
  loopback access to the fake storage server. Re-running all 14 storage tests with
  local network access passed. Two further tests were added and passed; the final
  focused mobile/messaging/performance run passed all 19 tests.
- Database upgrade/downgrade tests passed. Migration 0006 adds a nullable message
  submission token and unique sender/token constraint; existing messages remain.
- Headless Chrome mobile browser: 390×844, 4× CPU slowdown, 150 ms simulated
  latency, 200,000 bytes/s download, 93,750 bytes/s upload. Local database testing
  adds 30 ms per statement. Generated data: 12 listings, 1,000 messages, 10 threads.
- Browser verified older-history loading, repeated submissions, response loss
  after the server saved a message, and a successful retry producing exactly one
  saved and displayed message without navigation.
- Later page visits transferred zero bytes for the versioned stylesheet, script
  and app icon, confirming browser reuse.
- Local noisy-image test checks WebP dimensions and at least 75% byte reduction.

## Signed-in measurements

These are local synthetic observations, not live-account or phone guarantees.
Single samples include template compilation and should not be treated as averages.

| Page | Baseline server time | Final server time | Final database statements |
| --- | --- | --- | --- |
| Dashboard | 190 ms | 193 ms | 4 |
| Inbox | 262 ms | 152 ms | 4 |
| Account | 223 ms | 156 ms | 4 |
| Chat | 321 ms | 210 ms | 6 (previously 9) |

The generated chat's HTML decreased from 63,599 to 37,826 bytes; subsequent sends
return under 1 KB of JSON in the regression test, without downloading HTML again.
The one-thread/1,000-message test confirms Inbox and Account load one Message
object each, rather than 1,000. Dashboard had no excessive-query fault in this
fixture; its changes target browser file reuse and photo download size.

Private live conversations were not read and no messages were sent to real users.
Production verification follows deployment; real-phone results may vary.
