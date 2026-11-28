# Piano-roll Left-edge Note Resize QA Report

## Environment

- Real visible Chrome/CDP viewport: `1272×837`
- Backend: `http://127.0.0.1:8787`
- Fresh project: `project_6a8e75356d2f` (`Left Resize QA`)
- Rebuilt/cache-busted frontend bundle: `index-HgrgxKek.js`
- Backend restarted before testing
- Repo code was not modified
- Grid step in all exact expectations: `120` ticks (`1/16` at PPQ `480`)

## Results

### Single-note left-edge resize

Baseline note: `你`, pitch64, `start=240`, `duration=240`, fixed end `480`, with lyric/phonemes, vibrato, and a pitch-curve point attached.

| gesture | result | expectation | verdict |
|---|---|---|---|
| left edge dragged right by `240` ticks | `start=360`, `duration=120`, `end=480` | clamped to one-grid minimum; end fixed | passed |
| left edge dragged left by `120` ticks | `start=120`, `duration=360`, `end=480` | exact inverse start/duration math | passed |
| left edge dragged left by `480` ticks | `start=0`, `duration=480`, `end=480` | clamped at zero timeline | passed |
| right edge dragged right by `120` ticks | `start=240`, `duration=360`, `end=600` | existing right-edge regression unchanged | passed |

The note's lyric, phonemes, vibrato object, and pitch curve remained attached and unchanged through the left-resize operations.

### Undo/redo

- Ctrl+Z after the first left-resize restored the exact baseline note list, including ids and attachments.
- Ctrl+Y reapplied the exact post-resize state.
- Collision-resolution undo/redo also matched exact pre/post states.
- Multi-note zero-clamp undo/redo matched exact positive/zero states.

### Multi-select collective left resize

Two notes were resized collectively from the left edge:

- positive collective drag:
  - `啦`: `480+240 → 600+120`, end fixed at `720`
  - `吗`: `1200+240 → 1320+120`, end fixed at `1440`
  - start spacing remained exactly `720`
- a further rightward drag was fully clamped because both notes were already at grid-minimum duration
- large leftward drag clamped collectively at zero:
  - `啦`: `0+720`, end fixed at `720`
  - `吗`: `720+720`, end fixed at `1440`
  - start spacing remained exactly `720`
  - backend overlap scan: none

### Collision behavior

Collision fixture:

- previous `前`: `240+240`
- next `后`: `480+240`

Dragging `后`'s left edge left by `120` produced exact resolved state:

- `前`: `240+120`, end `360`
- `后`: `360+360`, end `720`
- backend overlap scan: none
- lyrics/phonemes survived: `前 → tɕʰ iɛn`, `后 → x ou`

### Creation/move/copy/reload regressions

- Auto lyric editor appeared after pencil creation and committed lyrics successfully.
- Moving an existing note did **not** reopen the lyric editor.
- Visible Copy/Paste controls increased note count by exactly one; undo restored exact pre-paste state.
- Reload persistence was exact.
- Final cleanup removed the temporary multi-resize fixture, leaving only the collision pair; final backend overlap scan: none.
- Browser console errors/warnings: `0`
- Network responses `>=400`: `0`

## Harness note

The first multi-fixture cleanup click/shift-click sequence removed only one temporary note, so one extra fixture appeared in the first final screenshot. This was a harness cleanup issue, not an application failure. It was then visibly selected/deleted; `08_final_cleaned.png` and `harness_cleanup` in the JSON show the cleaned two-note final state.

## Verdict

**Passed.** No defect was confirmed in left-edge note resizing, collective clamps, overlap resolution, attachment preservation, undo/redo, reload persistence, or nearby editing regressions.

## Evidence

- `note_left_resize_results.json` — complete machine-readable evidence
- `01_single_left_expand.png`
- `02_single_zero_clamp.png`
- `03_right_edge_regression.png`
- `04_multi_positive.png`
- `05_multi_zero_clamp.png`
- `06_collision_resolved.png`
- `07_reload_final.png`
- `08_final_cleaned.png`
