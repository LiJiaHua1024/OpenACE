# USTX import title preservation recheck

Date: 2026-04-27  
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

The quick regression passed.

## Verified

- Re-imported the existing `ustx_import_roundtrip.ustx` fixture through the visible `Import USTX` control using the real browser file chooser.
- `/api/import/ustx` returned HTTP 200.
- Backend project title is now the internal USTX fixture title: `USTX 导入验证`.
- UI title input also shows `USTX 导入验证`.
- Backend note lyrics remain exactly `你`, `好`.
- Piano-roll pixel verification still found dense white lyric text inside colored note bodies (`341` sampled white text pixels); the screenshot visibly shows the imported notes and lyric `好`.
- No console errors or network failures occurred.

## Evidence

- `title_01_before_import.png`
- `title_02_after_import.png`
- `ustx_title_recheck_results.json`
