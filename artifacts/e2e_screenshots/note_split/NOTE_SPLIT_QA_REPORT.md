# Piano-roll note splitting QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`; frontend rebuilt, backend restarted in fixture mode, cache-busted page. Isolated project `project_4e23d81052e7`. Used real piano-roll drawing, lyric editing, pitch-handle clicks, vibrato editor controls, right-click context menu, toolbar buttons, ruler seeks, Ctrl+E, undo/redo buttons, reloads, backend JSON verification, direct invalid-position API probes, CLI, and direct MCP function invocation. No implementation files were modified.

## Confirmed defects

### 1. Successful browser splits persist duplicate continuation notes

After one context-menu split at tick `960`, backend JSON contained three notes rather than two:

- first `note_6be45235-05d`, `0+960`, lyric `啊`
- second `note_80d89056ffe3`, `960+960`, lyric `-`
- **the exact same second `note_80d89056ffe3` duplicated again**, `960+960`, lyric `-`

The UI visibly reflected corruption: track metadata showed `3 notes` while selection read `2 selected` (`02_split_two_selected.png`). The same pattern repeated for each later frontend split:

- toolbar split created duplicate `note_930e60df0541`
- Ctrl+E split created duplicate `note_84e8afbc1876`
- final Chinese track state: 6 physical notes with duplicated continuation IDs at 480 and 1440 (`backend_duplicate_state.json`)

Direct backend/API splitting of equivalent simple and complex notes produced exactly two notes, so the backend operation itself is not the source. Likely frontend race mechanism: the split endpoint's SSE project state can arrive before the local response mutation. That incoming state already contains `first` and `second`; because `first` retains the original note id, the local splice still finds that id, replaces it with response `first+second`, and leaves the SSE-provided second behind. The resulting duplicate is then persisted by the post-transaction save.

Consequences: redo and reload did not persist the intended two-note split; they persisted the duplicated corrupted state.

### 2. Consonant-tail validation error is not readable in the browser

Splitting English `cat` inside the terminal consonant `/t/` correctly failed and did not mutate the note. DOM text was exactly `Split must land inside a sustained vowel`.

However, at exact viewport the `.split-error` bounding box was:

```json
{"x":1067.8984375,"width":0,"height":12}
```

while the visible editor toolbar right edge was `958`. The error is therefore effectively invisible (`12_error_visible_probe.png`, `error_visibility_probe.json`). This fails the requirement for an explicit readable error.

### 3. Piano toolbar overflows at exact required viewport

At `1272×837`, `.editor-toolbar` measured `scrollWidth=730`, `clientWidth=714`. Selection text is visibly clipped at the piano/right-panel boundary (for example `2 selecte` in `13_multi_select_split_disabled.png`). Body itself did not horizontally overflow (`1272/1272`), but the toolbar row is overcrowded.

## Passed behavior

- Exact viewport during primary run: `1272×837`.
- Real UI pencil drag created exact note `0+1920`, pitch70.
- Double-click lyric editing saved Mandarin `啊`; backend generated sustained vowel phoneme `a`, `0–2000ms`.
- Three pitch handles were added through the Pitch tool: `(495ms,+82c)`, `(748ms,-64c)`, `(1252ms,+45c)`.
- Vibrato was enabled through the visible editor. The harness reached start ratio `0.33` rather than intended `0.25`; this still exercised nontrivial rescaling.
- Context menu showed enabled `Split here`; exact right-click tick was `960`.
- Backend split pieces were adjacent and exact: `0+960` then `960+960`, no gap/overlap in the intended pair.
- Truthful continuation: first lyric `啊`, second lyric `-`, second technique `continuation`.
- Both intended split notes were selected immediately (`2 selected`).
- Timed phonemes exact: first vowel `0–1000ms`, second continuation vowel `0–1000ms`.
- Pitch-boundary interpolation exact: boundary `-9.5c` at `1000ms`; first ended there and second began with the same value, then shifted the later source point to `252ms/+45c`.
- Vibrato exact for original start `0.33`: first rescaled to `0.66`; second start `0` with phase `11.108671623093509`, matching the phase-continuation calculation. Visual waveform continuity is shown in `03_vibrato_boundary_crop.png`.
- A pre-split fixture render became visibly stale after splitting (`STALE RENDER` badge and warning in `02_split_two_selected.png`).
- Undo restored the original single `0+1920` note.
- Toolbar Split at playhead did trigger an exact split at tick480; Ctrl+E did trigger an exact split at tick1440. Both operations are nevertheless invalid end-to-end because of duplicate persistence defect 1.
- Split toolbar enablement: disabled at playhead boundary/outside, enabled when playhead is inside one selected note, disabled with two selected notes (`multi_select_enablement.json`).
- Invalid direct positions `0`, `1920`, `-1`, `5000` all returned HTTP422 and did not mutate note IDs/content.
- Right-clicking empty space showed `Split here` disabled.
- English `cat` tail rejection did not corrupt the note: one original `cat` note remained with phonemes `k(-45–0ms)`, `ae(0–1930ms)`, `t(1930–2000ms)`.
- CLI `split-note` passed and produced `啊` + `-` adjacent halves.
- MCP `split_note` passed and produced exact adjacent halves.
- Console and network transport errors: none observed.
- Body/layout horizontal overflow outside the toolbar: none.

## Harness caveats

- The first attempted run used a second unused track because project creation already includes `Lead Vocal`; it was discarded and rerun in a clean project. This was harness setup error, not application behavior.
- Vibrato start ratio ended at `0.33` because ArrowLeft interaction did not reach the intended `0.25`; validation was still valid and exact for `0.33`.
- The first matrix script crashed before writing final JSON because the English-track selector incorrectly searched text inside an input. Corrected supplements were used instead.

## Artifact index

- `00_note_ready_pitch_vibrato.png`
- `01_right_click_menu.png`
- `02_split_two_selected.png` — key duplicate evidence: UI says `3 notes`, `2 selected`, stale render
- `03_vibrato_boundary_crop.png`
- `04_undo_one_note.png`
- `05_reload_persisted_split.png`
- `06_toolbar_split.png`
- `07_ctrl_e_split.png`
- `08_empty_context_split_disabled.png`
- `10_english_tail_context.png`
- `11_english_tail_rejected.png`
- `12_error_visible_probe.png` — key invisible-error evidence
- `13_multi_select_split_disabled.png` — key toolbar overflow/enablement evidence
- `notesplitqa_first_run.log`
- `backend_duplicate_state.json`
- `backend_states.json`
- `english_tail_supplement.json`
- `error_visibility_probe.json`
- `enablement_layout_supplement.json`
- `multi_select_enablement.json`
- `cli_mcp_supplement.json`
