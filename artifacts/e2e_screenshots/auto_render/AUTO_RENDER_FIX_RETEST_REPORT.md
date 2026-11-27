# Auto render backend fix retest

## Verdict

**Passed.** The critical stale-project completion defect is fixed in the focused reproduction. A lyric edit made during an active render survived completion, the completed render fingerprint correctly remained stale, exactly one automatic follow-up job was queued, and that follow-up completed and cleared stale state.

## Critical reproduction evidence

- Initial non-stale fingerprint/current hash: `b4d3d5bbbc0f8994`.
- Two fast lyric edits (`啦→呜`, `卡→喵`) inside the debounce window produced exactly one job: `job_88d9059c79fd`.
- While that job was running, third lyric edit `萨→呢` survived in backend state:
  - before mid-render edit lyrics/hash: `['呜','喵','萨']` / `74ed4876216f7ed0`
  - after mid-render edit lyrics/hash: `['呜','喵','呢']` / `8b3ff71f9430eba5`
  - no parallel job was created.
- After first job `job_88d9059c79fd` completed:
  - lyrics remained `['呜','喵','呢']`
  - completed render fingerprint `74ed4876216f7ed0`
  - current input hash `8b3ff71f9430eba5`
  - stale: true
  - visible stale badge count: 1
  - exactly one follow-up job queued/running: `job_ed35460f4173`
- Follow-up completed:
  - output `data/renders/project_4ca9232b530b/job_ed35460f4173/vocal.wav`
  - fingerprint/current hash both `8b3ff71f9430eba5`
  - stale false, stale badge count 0, render revision 6.

## Regression checks

- Rapid edits inside debounce window: exactly one auto job, no duplicate flood.
- Cancellation regression: triggered job canceled; after waiting, still only that one canceled attempt and no infinite retry.
- Manual render regression: manual job `job_02377065aafb` completed with output.
- Layout contained: toggle inside right panel, panel `clientWidth == scrollWidth == 311px`.
- Console/page/network errors: none.

## New artifacts

- `auto_render_fix_retest_results.json`
- `12_fix_first_auto_job.png`
- `13_fix_midedit_active.png`
- `14_fix_followup_queued.png` — stale badge + exactly one running follow-up
- `15_fix_followup_completed.png` — stale badge cleared
- `16_fix_cancel_no_retry.png`
- `17_fix_manual_running.png`
- `18_fix_manual_completed.png`
