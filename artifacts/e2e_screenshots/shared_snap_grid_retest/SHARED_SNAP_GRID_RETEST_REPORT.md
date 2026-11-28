# Shared Snap Grid Defect Retest

Focused visible-Chrome retest after backend restart/cache-bust. Implementation was not modified.

## Assertions

- **Immediate arrangement redraw 1/16 → 1/4:** passed — measured subdivision spacing changed immediately from `28px` (120 ticks) to `112px` (480 ticks), with no project edit or reload.
- **Immediate arrangement redraw 1/4 → 1/32:** passed — measured spacing changed immediately to dense `14px` (60 ticks).
- **Nonzero note creation exact:** passed — at 1/32, clicking raw tick ≈1170 created `note_554db960-210` at exact `start_ticks=1200`, `duration_ticks=60`, pitch 70, with `pitch_snap_first=true`.
- **Undo survives save/SSE echo:** passed — after waiting 1.8s through save, Undo remained enabled.
- **Undo/redo exact:** passed — one undo removed exactly the created note; redo restored the same ID and exact musical fields `1200/60/pitch70`.
- **Basic clip snapping regression:** passed — at 1/32, a ~86-raw-tick arrangement drag moved clip exact `0 → 60`; undo restored `0`.
- **Console/page/network:** passed — no errors or failed responses.

No defect reproduced.

## Evidence

- `shared_snap_grid_retest_results.json` — measured spacing arrays and exact backend states.
- `10_immediate_grid_spacing_comparison.png` — immediate visual spacing comparison.
- `03_created_note_after_save_echo.png`, `04_created_note_undo.png`, `05_created_note_redo.png`.
