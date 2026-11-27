# Auto-render failure retry semantics QA

## Verdict

**Passed.** A controlled fixture vocal failure was truthfully surfaced, did not infinitely retry while the input fingerprint was unchanged, and did not block the queue. A subsequent input change enqueued exactly one new automatic attempt; after removing the failure trigger, that attempt completed and cleared staleness. Manual render regression also passed.

## Evidence

- Failure trigger file existed before enabling/testing auto render.
- Enabling auto render on a non-stale track created zero jobs.
- First lyric edit created exactly one automatic job, `job_63b8b0b35991`.
- That job failed truthfully:
  - status `failed`
  - error `explicit CI vocal render failure requested`
  - output path `null`
  - failure visible in the job card UI
- Waiting ~4.5s with unchanged input produced no additional retry; only the original failed job existed for that fingerprint.
- Editing another lyric while removing the failure file during the debounce window created exactly one new automatic job, `job_70283e04b7dd`.
- Retry completed with output `job_70283e04b7dd/vocal.wav`.
- After retry completion:
  - fingerprint/hash both `05c85c383bf5524e`
  - stale false
  - visible stale badge count 0
  - render revision 10
- Manual Render regression created exactly one manual job `job_f768c4a2ba8d`, which completed successfully.
- Layout remained contained; console/page/network errors: none.

## Artifacts

- `auto_render_failure_results.json`
- `00_failure_truthful.png`
- `01_no_infinite_retry.png`
- `02_retry_enqueued.png`
- `03_retry_completed_stale_cleared.png`
- `04_manual_render_completed.png`
- `05_failure_visible_final.png` — final clear visible evidence of truthful failure plus successful retry/manual jobs
