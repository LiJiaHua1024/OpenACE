# Shared Musical Snap Grid QA

Visible Chrome validation on fixture project `Snap Grid QA` after backend restart/cache-bust. Project contains two piano notes and a real rendered-fixture waveform clip. Implementation was not modified.

## Exact assertions

- **Default grid remains 1/16:** passed — selector value `4`; dragging the second note by ~86 raw ticks landed at exact `start_ticks=600` (`480+120`, not an unsnapped position). Undo restored `480`.
- **1/4 arrangement snapping:** passed — dragging the clip by ~257 raw ticks moved exact `start_ticks 0 → 480`; undo restored `0`.
- **1/4 piano movement:** passed — same ~257 raw-tick drag moved note 2 exact `480 → 960`; undo restored `480`.
- **1/4 piano creation:** passed — clicking raw tick ≈1170 created exact note `start_ticks=960`, `duration_ticks=480`, pitch 70. This distinguishes quarter snapping from 1/16 behavior.
- **1/32 arrangement snapping:** passed — dragging the clip by ~86 raw ticks moved exact `0 → 60`; undo restored `0`, redo restored `60`.
- **1/32 piano snapping:** passed — same drag moved note 2 exact `480 → 540`; undo restored `480`, redo restored `540`.
- **1/32 tempo editing:** passed — clicking raw tick ≈1170 produced a persisted tempo point at exact `ticks=1200` (`bpm=123.3`) after redo. Undo removed it and redo restored it.
- **Automation sharing after reload:** passed — Shift+range selection over raw ≈1170–1250 displayed exact `60t`, proving endpoints snapped `1200 → 1260` at 1/32.
- **Grid persistence:** passed — before/after browser reload selector value and `localStorage.openace_grid_division` were both `8` (1/32).
- **Project persistence:** passed — after reload backend state retained clip `start_ticks=60`, note 2 `start_ticks=540`, and tempo point `ticks=1200`.
- **Layout/console/network:** passed — no horizontal overflow, clipping, console errors, page errors, or failed network responses.

## Defects found

1. **Arrangement visual subdivision density is stale immediately after changing Grid.** Pixel inspection of arrangement screenshots:
   - immediately after selecting 1/4, visible subdivisions remained spaced `28px` (`120` ticks, old 1/16 density);
   - immediately after selecting 1/32, visible subdivisions remained effectively at prior quarter density (`112px` strong spacing);
   - only after another project edit (or reload) did correct dense `14px` (`60` tick) subdivision lines appear.
   This is consistent with `snapGrid` not being included in the ArrangementView draw-effect dependency list. Snapping behavior itself used the new resolution correctly.

2. **Undo for a newly created note is cleared after the backend save echo.** Immediately after creation, Undo was enabled; after the save completed/SSE echo arrived, Undo became disabled. The created note itself was correct (`960/480`). Likely cause: the frontend-created note omits optional/defaulted `pitch_snap_first`, while backend normalization returns `pitch_snap_first: true`; the semantic signature treats that as unknown ancestry. This appears adjacent to the earlier undo-hardening work rather than snap math, but it affects the requested undo regression.

## Evidence

- `shared_snap_grid_results.json` — exact backend tick state after every step.
- `10_arrangement_grid_visual_comparison.png` — direct visual proof of stale-then-correct arrangement density.
- `04_quarter_note_create.png` — created quarter-snapped note.
- `08_reloaded_grid32.png` — reloaded 1/32 shared grid/project state.
- `09_automation_range_60t.png` — automation range displays `60t`.
