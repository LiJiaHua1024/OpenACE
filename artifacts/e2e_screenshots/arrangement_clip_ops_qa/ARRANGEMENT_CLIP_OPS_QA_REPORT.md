# Arrangement clip context operations QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, driven through Playwright/CDP against a backend restarted from the current working tree.

## Result

The requested context-operation loop completed. No functional blocker, dead button, accidental split, playback/export failure, or console error was found.

Non-blocking layout concern: the context menus visibly overflow the small arrangement lane. The full clip menu is 212px tall in a 132px arrangement strip and extends 155px into the piano-roll area. The empty-space paste menu extends 42px right into the sidebar; on the second audio row it also extends 17px below the arrangement. The controls remain visible and clickable, but the overflow is visually untidy.

## Fixture

Project `project_c51755914b78` was API-seeded with two audio-capable accompaniment tracks. The source clip deliberately used non-default values:

```text
start=0, duration=960, offset=240, fade_in=120, fade_out=120, gain=-6dB
```

All context operations themselves were performed with real mouse clicks.

## Verified behavior

- Clip menu contains Split at cursor, Copy, Paste at cursor, Duplicate, Delete, and Clip gain.
- Copy did not mutate or split the original clip.
- Empty-space same-track paste at tick 2400 worked.
- Empty-space paste into the second accompaniment track at tick 2400 worked.
- Both pasted clips preserved exactly:
  - media path/label
  - `offset_ticks=240`
  - `duration_ticks=960`
  - `fade_in_ticks=120`
  - `fade_out_ticks=120`
  - `gain_db=-6`
- Pasted clips visibly rendered waveform/fade imagery.
- Paste undo/redo was exact on both tracks.
- Duplicate inserted immediately after the source at tick 960 and preserved the same clip fields.
- Duplicate undo/redo was exact.
- Dragging the duplicate back to tick 720 created overlap; automatic cyan crossfade pixels spanned the expected x `231–288` overlap region.
- Delete removed the cross-track pasted clip; undo restored it and redo deleted it again.
- Final clips all remained full 960-tick clips with unique IDs; no accidental split fragments appeared.
- Playback advanced from `00:00.00` to `00:00.69` without dead controls.
- WAV export control was clicked successfully and backend export returned 200 with a 1,008,044-byte WAV.
- No browser console errors or network failures occurred.

## Important artifacts

- `evidence_clip_ops_montage.png` — menu layout, paste, overlap/crossfade, and cross-track visual evidence.
- `02_clip_context_menu.png` — full clip menu.
- `03_empty_same_track_menu.png` — empty-space paste menu.
- `06_after_cross_track_paste.png` — cross-track pasted clip.
- `09_duplicate_dragged_into_overlap.png` — duplicate overlap with automatic crossfade.
- `11_after_delete.png` — delete result.
- `12_playback_after_clip_ops.png` — playback state.
- `clip_ops_master.wav` — exported WAV.
- `clip_ops_results.json` — machine-readable assertions.
