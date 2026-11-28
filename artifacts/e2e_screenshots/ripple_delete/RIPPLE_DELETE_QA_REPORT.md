# Arrangement clip ripple-delete QA report

Date: 2025-11-27  
Surface: real visible Chrome, exact viewport `1272x837`  
Build state: frontend rebuilt, backend restarted, browser cache-busted  
Implementation files: unchanged  
Fixture audio: real uploaded fixture `/uploads/svclyrics_words.wav` rendered as waveform clips

## Verdict

All requested ripple-delete checks passed. No implementation defect was confirmed.

Semantics are understandable for a DAW user: `Ripple delete` is a standard destructive edit term, the menu item is visually distinct from plain `Delete`, and the observed behavior matches the expected mental model: remove the selected clip region(s), then close the resulting gap on the same track only. Multi-selection union behavior is not previewed before committing, but undo works exactly, so the behavior is recoverable and comprehensible.

## Exact scenario results

### Single clip

Canonical Single lane:

- `S-Early`: `0 + 240`
- `S-Mid`: `480 + 480`
- `S-Later`: `1440 + 480`

After context-menu `Ripple delete` on `S-Mid`:

- `S-Early`: unchanged at `0 + 240`
- `S-Mid`: deleted
- `S-Later`: exactly `960 + 480`
- all clips on Contig/Overlap/MultiA/MultiB exactly unchanged

Undo restored the exact canonical state. Redo reapplied the exact ripple state. Reload persisted the exact ripple state.

### Two contiguous selected clips

Canonical Contig lane:

- `C1`: `480 + 480`, ending `960`
- `C2`: `960 + 480`, ending `1440`
- `C-Later`: `1920 + 480`

After selecting both with real Ctrl+clicks and ripple-deleting from the context menu:

- `C1`/`C2`: deleted
- `C-Later`: exactly `960 + 480`
- merged ripple duration: exactly `960` ticks
- earlier `C-Early` and all other lanes unchanged

### Two overlapping selected clips

Canonical Overlap lane:

- `O1`: `480 + 720`, ending `1200`
- `O2`: `960 + 720`, ending `1680`
- union interval: `480–1680`, exactly `1200` ticks
- `O-Later`: `2400 + 480`

After ripple delete:

- `O1`/`O2`: deleted
- `O-Later`: exactly `1200 + 480`
- the result proves the overlap was not double-counted; naive summed durations would have shifted it to `960`
- earlier `O-Early` and all other lanes unchanged

### Multi-track selection

Canonical MultiA/MultiB lanes each had:

- selected clip: `480 + 480`
- later clip: `1920 + 480`

After selecting one clip on each track and ripple-deleting once:

- both selected clips deleted
- both later clips exactly `1440 + 480`
- equal ripple durations preserved synchronization across the two tracks
- earlier clips and unrelated tracks unchanged
- multi-track undo restored the exact canonical two-track state
- redo reapplied the exact ripple state
- reload persisted the exact ripple state

## Menu geometry

Measured context-menu rectangles against the actual arrangement viewport:

- five-lane top-row menu: `204x127` at `(468,99)`, fully inside viewport `(236,58)-(950,258)`
- five-lane bottom-row menu: `204x127` at `(468,107)`, fully inside same viewport
- one-lane/small arrangement menu: `204x127` at `(468,59)`, fully inside viewport `(236,58)-(950,190)`

No horizontal or vertical clipping observed.

## Console/network

- Console errors/warnings: none
- Failed network responses: none

## Evidence files

- `ripple_delete_results.json` — exact backend state assertions and menu geometry
- `ripple_delete_run.log` — raw PASS lines
- `00_fixture_loaded.png` — five-lane real-waveform fixture
- `01_single_ripple_menu.png` — context menu and Ripple delete item
- `02_single_ripple_after.png` — single ripple result
- `03_single_ripple_reload.png` — reload persistence
- `06_contiguous_after.png` — contiguous merge result
- `09_overlap_after.png` — overlapping union result
- `12_multitrack_after.png` — synchronized multi-track result
- `13_menu_top.png`, `14_menu_bottom.png`, `15_menu_small_height.png` — menu geometry evidence
- `16_multitrack_undo_redo_reload.png` — multi-track undo/redo/reload evidence
- `/home/ubuntu/screencasts/ripple-delete-qa/ripple-delete-qa-edited.mp4` — interaction recording
