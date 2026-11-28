# Piano-roll performance architecture QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, Playwright/CDP, backend restarted from current tree and frontend rebuilt.

## Result

The sparse-editing regression checks and dense 3000-note performance checks passed. No stale static canvas, blank dense scene, playhead misalignment, z-index/input regression, or console error was found.

Harness transparency: the first continuous-scroll comparison accidentally scrolled forward and backward by equal amounts, returning close to the origin and making the visual diff artificially small. I corrected the check to a one-direction continuous scroll; the corrected measurement passed with a large visual redraw diff. This was a test artifact, not an application defect.

## Sparse normal-density project

Passed:

- Static scene and playhead are separate stacked canvases with identical geometry.
- Overlay has `z-index:2` and `pointer-events:none`; static canvas remains the input target.
- Note labels are visible in normal density.
- Phoneme text is visible.
- Gradient rendering is present; sampled note interior had 107 unique colors.
- Vibrato waveform and pitch handles/curve are visible.
- Click selection shows `1 selected`.
- Marquee held-drag visual is visible and selects exactly `2 selected`.
- Moving selected notes updates backend exactly:
  - first note `(start,pitch)` → `(240,61)`
  - second note `(start,pitch)` → `(1200,63)`
- Static canvas visibly redraws after move, zoom, and scroll:
  - zoom mean absolute diff `3.87`
  - scroll mean absolute diff `11.54`
- Ruler seek playhead appears at x `287` versus expected x `288`.
- During playback, detected playhead x advanced `375 → 562` while transport advanced.
- No overlay artifacts were visible.

## Dense 3000-note project

Passed:

- Approximately 611 notes were estimated visible, so the >220-note LOD path was active.
- Dense scene rendered as solid note blocks without blanking; 173,471 colored note pixels were detected.
- Dense LOD correctly omitted ordinary white label text (`0` white text-like pixels detected), avoiding unreadable clutter.
- Real mouse click selected a dense note (`1 selected`).
- Real mouse drag moved exactly one note from tick `276` to `396` (+120 ticks); undo restored it.
- Playback measurement: **59.34fps**, p95 frame time **16.8ms**.
- Dense playhead advanced visibly/pixel-wise from x `172` to x `456`.
- Corrected one-direction continuous-scroll measurement: **60.00fps**, p95 frame time **16.7ms**.
- Scroll redraw mean absolute diff: **28.80**.
- No blank/stale playhead or z-index/input regression was observed.
- No console errors or network failures occurred.

## Important artifacts

- `evidence_piano_performance_montage.png`
- `01_sparse_initial.png`
- `06_sparse_marquee_held.png`
- `08_sparse_after_move.png`
- `11_dense_initial.png`
- `14_dense_playhead_late.png`
- `15_dense_after_scroll.png`
- `piano_performance_results.json`
- `browser_console.jsonl`
