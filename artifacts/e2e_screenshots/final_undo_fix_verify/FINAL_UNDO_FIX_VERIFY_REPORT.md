# Final Undo Fix Verification

Date: 2026-11-28  
Build: `index-c5ccD6mi.js`; fixture backend restarted.  
Implementation modified: no.

## Verdict

The exact reported undo/autosave regression is fixed. The first toolbar Undo click and empty-editor Ctrl+Z now immediately remove a newly drawn note, and rapid create/undo cycles do not accumulate notes.

One smaller residual UX defect remains on the Ctrl+Z path: after global undo deletes the note, the now-orphaned empty lyric editor remains visibly open over the piano roll. It is harmless—typing/committing it does not recreate or mutate a note—but it visually resembles a floating note/input for a deleted object and should ideally close when its note disappears.

## Exact acceptance results

### Toolbar Undo

Project: `project_31ad83561c6f`

- auto lyric editor open before undo: yes
- first toolbar Undo click
- backend count after click: `0`
- UI after click: `0 notes`
- Undo button disabled afterward: yes

Result: passed.

### Empty-editor Ctrl+Z

Project: `project_1a381437fd69`

- auto lyric editor open before Ctrl+Z: yes
- backend count after Ctrl+Z: `0`
- UI after Ctrl+Z: `0 notes`
- residual editor still open: yes (`1`) — residual UX issue noted above

Result: exact zero-note requirement passed; stale editor flagged separately.

### Rapid repeated create/undo attempts

Five rapid alternating attempts with 30/45/80/120/150 ms delays:

1. toolbar: backend `0`, UI `0 notes`
2. Ctrl+Z: backend `0`, UI `0 notes`
3. toolbar: backend `0`, UI `0 notes`
4. Ctrl+Z: backend `0`, UI `0 notes`
5. toolbar: backend `0`, UI `0 notes`

Result: passed; no accumulation or resurrection observed.

## Lyric behavior

Committed lyric test:

- typed and committed `你`
- Ctrl+Z after commit reverted lyric to empty while preserving the note (`count=1`)
- Ctrl+Shift+Z restored `你` (`count=1`)

Result: passed.

Nonempty editor text behavior:

- typed `ab`
- Ctrl+Z changed text to `a` only; note count remained `1`
- Ctrl+Shift+Z changed text back to `ab`; note count remained `1`

Result: passed; nonempty editor retains normal input undo/redo behavior.

## Residual stale-editor probe

After Ctrl+Z deleted the note:

- backend count: `0`
- editor open: `1`

Typing `后` into that stale editor and pressing Enter:

- backend count remained `0`
- editor closed
- no console/network errors

Result: harmless but visually incorrect orphan editor remains until dismissed/committed.

## Health

- Browser console errors/warnings: zero
- Failed browser network responses: zero
- Backend HTTP 500 count in focused log: zero

## Evidence files

- `final_undo_fix_verify_results.json`
- `stale_editor_after_ctrlz_probe.json`
- `nonempty_editor_undo_probe.json`
- `nonempty_editor_redo_probe.json`
- `01_toolbar_first_click_zero.png`
- `02_ctrlz_empty_editor_zero.png` — shows the orphan empty editor after Ctrl+Z despite zero notes
- `03_rapid_create_undo_no_accumulation.png`
- `04_lyric_commit_undo_redo.png`
- `05_stale_editor_after_ctrlz_commit.png`
- `06_nonempty_editor_ctrlz.png`
- `07_nonempty_editor_ctrlshiftz.png`
