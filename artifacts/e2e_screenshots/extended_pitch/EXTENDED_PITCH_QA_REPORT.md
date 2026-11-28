# Extended ±600-cent Pitch Editing QA Report

## Environment

- Real visible Chrome/CDP viewport: `1272×837`
- Backend: `http://127.0.0.1:8787`
- Fresh project: `project_4ac597a5b53e` (`Extended Pitch QA`)
- Rebuilt/cache-busted frontend bundle: `index-D0yT-4hP.js`
- Backend restarted before testing
- Repo code was not modified

## Quantitative results

### Per-note pitch inverse mapping

A pitch64 quarter note (`0+480`, lyric `你`) was created. Per-note pitch gestures were started inside the note and dragged by exact piano-row distances:

| target rows | readout while dragging | backend cents |
|---|---:|---:|
| +1 semitone | `65 ms · +100¢` | `+100.0` |
| +2 semitones | `194 ms · +200¢` | `+200.0` |
| +6 semitones | `324 ms · +600¢` | `+600.0` |
| -6 semitones | `454 ms · -600¢` | `-600.0` |
| -1 semitone (supplement) | `135 ms · -100¢` | `-100.0` |
| -2 semitones (supplement) | `202 ms · -200¢` | `-200.0` |

The negative one/two-semitone rows were checked in a supplemental real-browser pass after the main recording. The rendered curve visibly spans/crosses note rows rather than remaining squashed inside the source note rectangle. See `01_multisemitone_curve.png`.

### Point drag/delete

- The former `+200¢` point was dragged to exactly `+400¢`.
- Alt-clicking that point deleted exactly that point.
- Remaining backend curve after deletion: `+100¢`, `+600¢`, `-600¢`.

### Pitch automation lane

Brush clicks at the physical top, midpoint, and bottom of the pitch lane persisted exact backend values:

| lane position | backend value |
|---|---:|
| top | `+600.0` |
| midpoint | `0.0` |
| bottom | `-600.0` |

Tick positions were `969`, `1449`, and `1929`; these are ordinary pixel-to-tick rounding positions and do not affect the requested value validation.

### Undo/redo/reload

- Automation Ctrl+Z removed the last `-600` write; Ctrl+Y restored the exact pre-undo automation list.
- A separate `+300¢` per-note pitch point was created on the second note:
  - Ctrl+Z restored the exact pre-creation note state.
  - Ctrl+Y restored the exact post-creation state.
- Reload persisted exact notes, lyrics, phonemes, per-note pitch curves, and automation points.

### Regression checks

- Created a second adjacent note `好`; dragging the first note into it resolved to exact non-overlap (`120+360` before `480+240`).
- Backend overlap scan: zero overlaps.
- Lyrics/phonemes survived: `你 → n i`, `好 → x au`.
- Note audition remained functional during note movement: exact pitch64 triangle frequency `329.6275569128699 Hz`.
- Layout visually reviewed in captured screenshots: piano-roll curve, automation lane, toolbar, and right panel remained contained at `1272×837`.
- Browser console errors: `0`
- Browser warnings: `0`
- Network responses `>=400`: `0`

## Verdict

**Passed.** No defect was confirmed in the extended ±600-cent pitch editing implementation during this adversarial real-browser run.

## Evidence

- `extended_pitch_results.json` — complete machine-readable evidence
- `00_initial_note.png`
- `01_multisemitone_curve.png` — multi-row crossing curve
- `02_point_drag_delete.png`
- `03_automation_extremes.png` — pitch automation lane extremes
- `04_reload.png`
- `05_move_audition_overlap.png` — note move/overlap/audition regression state
- `06_per_note_undo_redo.png`
