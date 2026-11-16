# Four-step release: production checks

Published with explicit approval on 15 November 2026.

- Commit: `e57dd0064208b44da0d81795c0f20d0660be87ec`
- Deployment: `dpl_6sNy1ZqcrhC5TiawSmfcLDKVwx49`
- Production: https://rent-me-app-rho.vercel.app
- Status READY, alias assigned, region cdg1 (Paris).
- Database: revision 0006_message_submission; unique submission constraint
  confirmed present; message row-level security remains enabled. Only schema
  metadata was queried, not live message bodies.
- Public home/login/map returned 200. No browser JavaScript errors in the final
  run, and no error/fatal logs returned for the deployment's inspected 15 minutes.
- App CSS, scripts and icons return one-year immutable public caching; home
  returns private/no-store. Later page visits showed zero asset transfer bytes.
- Two real listing previews returned image/webp, 33,284 and 19,804 bytes.
  Repeated preview requests returned X-Vercel-Cache: HIT. Visible listing images
  loaded correctly; below-fold lazy images were not required to load.
- The mobile screenshot was visually inspected at 390×844.

Same simulated mobile connection/CPU settings as the implementation report:

| Page | First content | Load event |
| --- | --- | --- |
| Home, fresh browser cache | 5.044 s | 6.479 s |
| Login | 0.668 s | 0.755 s |
| Map | 1.748 s | 3.221 s |
| Home, return visit | 0.992 s | 1.205 s |

Single samples, not averages. An earlier browser attempt timed out waiting for
the load event; the successful repeat completed without JS errors. First-visit
performance is still variable and was not demonstrated to improve in this run.
The strongest verified improvements are cached return navigation, smaller photo
payloads, bounded chat history, in-place sends, and safe retries. Signed-in browser
checks used generated local accounts, not real live users' private conversations.

No paid plans or paid image-transformation services were enabled.
