# Final Acceptance Fixes — Focused Regression Verification

Date: 2026-11-28  
Build: `index-A1rTsAMw.js`; fixture backend restarted.  
Implementation modified: no.

## Defect first

### P2 still reproducible — immediate first Undo after note creation does not undo while auto lyric editor is open

The autosave/serialization fix does not satisfy the exact requested regression because the first undo gesture is still consumed by the auto-open lyric editor interaction.

Focused sequence on a clean project:

1. Draw one note; lyric editor auto-opens.
2. Immediately click enabled toolbar Undo once.
3. Editor closes, but backend/UI remain `1 note`; Undo remains enabled.
4. Click Undo a second time.
5. Backend/UI then reach `0 notes`.

Rapid repeated verification without Escape produced accumulating counts:

- toolbar after 30ms: backend/UI `1`
- Ctrl+Z after 60ms: backend/UI `2`
- toolbar after 120ms: backend/UI `3`
- Ctrl+Z after 180ms: backend/UI `4`

Interpretation: toolbar clicks sometimes close the editor rather than undoing; Ctrl+Z while the lyric editor remains active does not trigger global note-creation undo. Therefore the exact user-visible defect remains, even though once Undo actually fires there was no observed stale-autosave resurrection.

Evidence: `undo_fix_results.json`, `undo_click_sequence.json`, `01_undo_editor_open_rapid.png`.

## Passed

### Normal lyric undo/redo

On a clean project:

- typed/committed lyric `你`
- Ctrl+Z reverted lyric to empty while preserving the note (`count=1`)
- Ctrl+Shift+Z restored `你` (`count=1`)

Evidence: `lyric_undo_redo_clean.json`, `02_lyric_undo_redo_clean.png`.

### MCP/CLI MP4 atoms

Using project `project_0aa8682e9327` with audible fixture-rendered audio:

- actual MCP stdio `export_project(fmt="mp4")`: success, `135075` bytes, valid `ftyp`, duration `2.5s`
- CLI `openace-tool export ... mp4`: success, `77794` bytes, valid `ftyp`, duration `2.5s`

Evidence: `mp4_atoms_results.json`, `mcp_export_test.mp4`, `cli_export_test.mp4`.

### Health

- Browser console errors/warnings: zero in undo verification.
- Failed browser network responses: zero in undo verification.
- Backend log HTTP 500 count during focused verification: zero.

## Harness note

The first lyric undo/redo script used the wrong visible button title (`Redo Ctrl+Shift+Z` instead of actual `Redo Ctrl+Y`); corrected verification used keyboard redo and passed. This was a harness selector issue, not a product defect.
