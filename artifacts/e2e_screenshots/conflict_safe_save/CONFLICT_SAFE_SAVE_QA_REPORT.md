# Conflict-safe whole-project persistence QA

## Verdict

**Passed.** The realistic stale whole-project autosave race now preserves both the user's mid-render edit and the newly completed render output. The auto-render critical regression still passes: exactly one follow-up is queued automatically and completion clears stale state.

## Evidence

- Two quick lyric edits produced exactly one debounced auto render (`job_8ad5f5bdc1e0`), no duplicate flood.
- While that job was running, lyric three was edited; captured stale whole-project payload had lyrics `['呜','啦','呀']` and timestamp before job completion.
- First render completed with output `job_8ad5f5bdc1e0/vocal.wav`.
- Replaying the stale payload through `PUT /api/projects/{id}` returned `200` and merged correctly:
  - user lyrics remained `['呜','啦','呀']`
  - render output path survived
  - render revision `8` survived
  - completed fingerprint `8c49a34b22b8b6a2`
  - current input hash `5a72cf5d1779ce36`
  - stale remained true and visible stale badge count was 1
- Exactly one follow-up job `job_942ac2b58857` was created automatically.
- Follow-up completed; fingerprint/hash both became `5a72cf5d1779ce36`, stale false, badge count 0.
- Manual regression passed:
  - title edit saved as `Conflict Save QA`
  - undo restored `Auto Render QA`
  - redo restored `Conflict Save QA`
  - reload persisted `Conflict Save QA` and `Saved`
- Layout contained; console/page/network errors none.

## Scope note

This browser/API race validated render-output metadata merge on an existing vocal track. Fresh job-created track/clip preservation and repaint clip-path merge are backend behaviors covered by focused API tests but were not separately exercised in this browser pass.

## Artifacts

- `conflict_safe_save_results.json`
- `00_first_auto_job.png`
- `01_midedit_before_completion.png`
- `02_after_stale_put_merge.png` — key stale-race evidence
- `03_followup_completed.png`
- `04_title_redo_saved.png`
- `05_regression_reloaded.png`
