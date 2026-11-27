# Track operations QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted and frontend rebuilt from current tree.

## Result

All tested track-operation behavior passed. No clipped menu, glyph/font failure, fake operation, shared mutable ID, accidental selection loss, persistence failure, or console/network error was found.

Harness transparency: the first harness run stopped because of a test-script typo (`typewrite`); no application failure was involved. The corrected full run passed.

## Verified

- Right-click menu opens and stays inside viewport at top position.
- `⋯` ellipsis entry point opens the same menu.
- Menu contains Duplicate track, Move up/down, six color swatches, Delete track; glyph is readable.
- Duplicate inserted `Lead QA copy` immediately after the source.
- Duplicate preserved full content exactly apart from IDs/name.
- Track, note, and breath IDs were fresh; no shared mutable IDs.
- Duplicate became the selected track.
- Move down reordered `Lead QA / BGM QA / Lead QA copy` correctly.
- Color changes persisted and were visibly reflected in the track card/content; orange/pink pixels were visible in the UI.
- Delete removed the copied track; undo restored it; redo removed it again.
- Escape and outside click closed the menu.
- Rename, mute, solo, volume, pan, and +Vocal add-track regressions passed.
- Bottom menu was clamped inside the viewport.
- Narrow-viewport right-edge clamp kept the menu inside the window.
- Backend state persisted exactly after reload.
- Single-track delete-all edge reached zero tracks without crashing; undo restored the track.
- Zero console errors/network failures.

## Key measurements

- Top menu: `176×172` at `(112,161)`, inside viewport.
- Bottom menu: `176×172` at `(112,641)`, inside viewport.
- Narrow right-clamped menu: `176×172` at `(138,149)` in a temporary 320px-wide viewport.
- Volume/pan regression values persisted as `volume=0.49`, `pan=0.01`.

## Evidence

- `evidence_track_operations_montage.png`
- `01_top_context_menu.png`
- `02_after_duplicate.png`
- `04_after_color_move.png`
- `06_bottom_context_menu.png`
- `08_narrow_right_clamp.png`
- `09_delete_all_single_track.png`
- `track_ops_results.json`
