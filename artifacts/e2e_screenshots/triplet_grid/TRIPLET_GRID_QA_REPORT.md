# Triplet Grid QA Report

Focused visible-Chrome verification of the uncommitted triplet grid options after backend restart and cache-busted production build. Implementation was not modified or committed.

## Results

All focused checks passed. Console errors, page errors, and failed network responses were empty in the instrumented run.

| Check | Exact evidence | Result |
|---|---|---|
| Selector labels | Options include value `3` label `1/8T` and value `6` label `1/16T`. | **PASS** |
| Ruler seek at `1/8T` | Raw target ≈1170 became `1.3.2` / `00:01.17`, exactly tick `1120` = 7×160. | **PASS** |
| Ruler seek at `1/16T` | Raw target ≈1170 became `1.3.3` / `00:01.25`, exactly tick `1200` = 15×80. | **PASS** |
| Arrangement movement at `1/8T` | Clip `audit_clip1` moved exact `0→160` ticks; Undo restored exact `0`. | **PASS** |
| Arrangement movement at `1/16T` | Clip `audit_clip1` moved exact `0→80` ticks; Undo restored exact `0`. | **PASS** |
| Piano shared snapping at `1/8T` | Raw creation target ≈2500 created exact note `start_ticks=2560`, `duration_ticks=160`; Undo removed it. | **PASS** |
| Piano shared snapping at `1/16T` | Raw creation target ≈2500 created exact note `start_ticks=2480`, `duration_ticks=80`; Undo removed it. | **PASS** |
| Piano visual spacing | Immediate scan: `37/37.5 px` repeating at 1/8T (160 ticks) and `18.5/19 px` repeating at 1/16T (80 ticks). | **PASS** |
| Automation visual spacing | Same measured spacing patterns as piano at both triplet resolutions. | **PASS** |
| Persistence across reload | After reload selector value and `localStorage.openace_grid_division` were both `6`. | **PASS** |
| Console/network | No console errors, page errors, or failed network responses. | **PASS** |

Test-process note: the first automated note-undo attempt occurred while the newly opened lyric editor still had keyboard focus, so Ctrl+Z went to that editor rather than global undo. After closing the lyric editor with Escape, creation Undo passed exactly. This was a test-sequence issue, not a product failure.

## Evidence

- `10_triplet_visual_grid_comparison.png` — side-by-side piano/automation density comparison
- `triplet_grid_results.json` — exact machine-readable evidence
- `00_grid_1_8T_visual.png`
- `01_grid_1_8T_ruler_seek.png`
- `02_grid_1_8T_clip_move.png`
- `03_grid_1_8T_note_create.png`
- `04_grid_1_16T_visual.png`
- `05_grid_1_16T_ruler_seek.png`
- `06_grid_1_16T_clip_move.png`
- `07_grid_1_16T_note_create.png`
- `08_after_reload_grid16T.png`
- `09_note_undo_corrected.png`

Recording: `/home/ubuntu/screencasts/triplet-grid-qa/triplet-grid-qa-edited.mp4`
