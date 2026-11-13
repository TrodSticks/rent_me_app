# Direct photo upload checks

Implementation date: 13 November 2026. Phone acceptance tests remain pending until Rod runs them.

## What changed

The browser sends each original photo straight to a private Supabase holding bucket. Rent Me issues a temporary permission for one randomly named object after checking the landlord's login and listing ownership. The server reads and checks the uploaded image, creates the normal resized JPEG, and returns a single-use receipt. Saving the listing sends receipts and text, not photo bytes, through Vercel.

Limits remain **10 photos per listing, 5 MiB per original photo**, JPG/PNG/GIF/WebP. Originals are not recompressed in the browser: this preserves the existing duplicate detection behavior. The saved JPEG is resized to 1200 pixels on its longest side, with metadata removed. Images over 40 million pixels are rejected to bound server memory use. HEIC conversion is not included.

## Rod's phone tests

Use a clearly labelled **UPLOAD TEST — do not publish** draft. Keep the existing Phakalane test house unchanged. Refresh the app before starting so it loads the updated upload script.

| Test | Steps | Pass condition |
| --- | --- | --- |
| Main large-batch test | Select 3–5 different photos. Each must be below 5 MB, but together they must exceed 4.5 MB. Tap Save as draft. | Progress appears; save succeeds; reopening shows every selected photo once. |
| Maximum gallery | Upload 10 different photos to an empty draft. | All 10 remain after reopening. |
| Too many | Try adding an 11th photo to the same draft. | A clear message stops saving more than 10. |
| Oversized single photo | Choose a photo larger than 5 MB. | A clear size message appears before upload. |
| Duplicate in one batch | Choose the same photo twice, including a renamed copy. | A duplicate message appears; the listing is unchanged. |
| Duplicate of saved photo | Add a copy of a photo already in the draft. | Duplicate is rejected. Removing the old copy and replacing it is allowed. |
| Connection interruption | During photo 2 or later, turn off mobile data/Wi-Fi. Restore it, then tap the same Save button. | An understandable error appears; completed uploads are reused; final gallery has no missing or extra photos. |
| Save choice | Save as draft, reopen, then publish the dedicated test listing only if desired. | Draft stays private; publishing requires confirmed email and the selected action is respected. |
| Editing | Remove one saved photo, reorder another to cover, and add a different photo. Save and reopen. | Count, cover and order are correct; removed image leaves Supabase. |
| Display | Open the saved gallery on a phone and computer. | Photos load, rotation is correct and picture quality is acceptable. |

For a failed test, record the device/browser, number of photos, individual sizes, action used and exact visible message. Never include a signed upload link or secret key in screenshots shared with others.

## Automated and operator checks

- Flask tests: login/role/ownership, listing scope, CSRF, quota, actual bytes and image decoding, expiry, repeated finish requests, one-use receipts, duplicates against legacy images, max count, invalid form retries, replacement/removal, cleanup failure retries and preservation of claimed photos.
- JavaScript tests: a 6 MB batch goes to Storage; final form has no file bodies; draft action survives; a failed second upload retries without repeating the first; form errors reuse completed uploads.
- Existing photo, hosted storage, migration and account regression tests run alongside the new tests.
- Verify production migration `0005_photo_uploads`, RLS on `photo_upload`, and private bucket settings after release.
- Confirm real browser upload CORS, saved object contents, gallery rows and draft visibility. Automated transport mocks alone cannot prove these.

## Cleanup and recovery

The private `property-photo-uploads` bucket is created through the Storage API on the first upload, limited to 5 MiB and the four accepted MIME types. Unexpected existing bucket settings stop uploads instead of silently weakening access.

Permissions and receipts last two hours. Private source objects are deliberately retained beyond permission expiry so a consumed upload address cannot recreate a deleted object during its validity period. Each new upload request attempts cleanup of one receipt older than 24 hours. Failed deletions retain receipts for retry. Claimed gallery photos are never deleted by this cleanup.

On a quiet site, cleanup waits for new upload activity. An operator can run `flask --app app cleanup-photo-uploads` against the intended environment to clean up to 100 old receipts per run. A scheduled cleanup job is not part of this release.

`DIRECT_PHOTO_UPLOADS=0` disables the new browser path if rollback is necessary. The old multipart path remains for local development and compatibility; its Vercel combined-request limit still applies. The migration is additive and does not alter existing listing/photo rows.

Reference: [Supabase signed upload URLs](https://supabase.com/docs/reference/javascript/storage-from-createsigneduploadurl).
