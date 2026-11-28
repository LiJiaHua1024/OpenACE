# New-Track Undo Key-Order Retest

Focused visible-Chrome retest after backend restart/cache-bust. Implementation was not modified.

## Assertions

- **New vocal track created:** passed — `track_a8d422bb-71b` / `Vocal 2` saved with backend-normalized defaults.
- **Undo remains enabled after save/SSE echo:** passed.
- **One undo removes exactly that track:** passed — backend track list returned to only `track_snapqa`.
- **Redo restores same track exactly:** passed — same ID/name/type and complete backend-normalized object matched the post-add object exactly.
- **Piano-note regression:** passed — created exact `note_dde257f4-cf1`, `start_ticks=1200`, `duration_ticks=60`, pitch `70`, `pitch_snap_first=true`; undo removed it and redo restored exact fields.
- **Console/page/network:** passed — no errors or failed responses.

No defect reproduced.

## Evidence

- `undo_track_keyorder_retest_results.json`
- `01_track_added_after_echo.png`, `02_track_undo.png`, `03_track_redo.png`
- `04_note_after_echo.png`, `05_note_undo.png`, `06_note_redo.png`
