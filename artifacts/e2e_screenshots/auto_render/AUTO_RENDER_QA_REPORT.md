# Debounced automatic vocal rendering QA

## Verdict

**Core auto-render behavior passed, but a critical active-render project data-loss defect was found.** The defect prevents the required follow-up-render behavior from being meaningful: edits made during a running render can be overwritten when the render job completion saves its stale project snapshot.

## Critical defect: mid-render edit overwritten

Focused reproduction:

1. Track began non-stale after manual render (`render_fingerprint 5d16fdd7d2e5b13f`).
2. Lyric edit `呜 → 啦` triggered auto job `job_ff1e1150f39d` after debounce.
3. While that job was `running`, second lyric was edited `卡 → 喵`.
4. Immediately after that edit backend state was `['啦','喵','萨']`; hash changed `b4d3d5bbbc0f8994 → 11443f55aede7393`.
5. No parallel job was created while the first was active — this part passed.
6. When the running job completed, backend state reverted to `['啦','卡','萨']`; the `喵` edit was lost. `render_fingerprint` and current hash both became `b4d3d5bbbc0f8994`.
7. Therefore the project was not stale and no follow-up job was queued.

This strongly suggests render completion persists a stale project object loaded at job start, clobbering concurrent user edits. Screenshot `10_followup_after_completion.png` visibly shows the second note reverted to `k a` and no follow-up queued.

## Passed checks

- Checkbox visible and initially unchecked after clearing localStorage.
- Enabling `Auto render edits` persisted in localStorage across reload.
- With a non-stale rendered track, enabling/reloading did **not** create spurious jobs.
- Lyric edit plus two rapid note transposes created exactly one automatic `svs_score` CI-fixture job after debounce; no duplicate flood.
- While an automatic job was active, an attempted edit did not create a parallel job.
- In the ordinary no-concurrent-edit path, completion updated the render fingerprint and cleared stale badge/warning.
- Canceling an auto-created job produced `canceled`, `output_path=null`, and no retry for the same fingerprint after ~4.5s.
- Changing input after cancellation allowed exactly one new auto attempt.
- Manual `Render vocal` regression passed: manual job `job_ee26e86b776b` completed with real fixture output; no extra auto duplicate appeared afterward.
- Layout contained: checkbox within right panel; right panel `clientWidth == scrollWidth == 311px`.
- Console/page/network errors: none observed.

## Untested / not practical

- Failure (rather than cancellation) retry semantics were not tested; no controlled production failure fixture was available without modifying code.
- Audio quality was not evaluated; this was FIFO/orchestration QA using CI fixture audio.

## Key artifacts

- `auto_render_results.json` — complete machine-readable evidence.
- `00_loaded_auto_unchecked.png`
- `01_enabled_no_job.png`
- `02_reload_checkbox_persisted.png`
- `03_first_auto_job.png`
- `04_active_edit_no_parallel.png`
- `06_followup_stale_cleared.png`
- `07_cancel_no_retry.png`
- `08_manual_render.png`
- `09_active_lyric_edit_no_parallel.png`
- `10_followup_after_completion.png` — critical defect evidence
- `11_manual_completed_jobs.png`
