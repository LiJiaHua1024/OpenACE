# Contiguous Note Merge QA

Implementation modified: no. Backend restarted; production bundle `index-CDHvqspN.js`; cache-busted browser.

## Verdict

Core feature passes. No product defects found.

## Evidence

- Ctrl+J merged three contiguous distinct-pitch lyric notes into exactly one note.
- Corrected positive endpoint state: duration exactly `1440`, lyric exactly `你好吗`, pitch `64`.
- Phonemes coherent continuous sequence: `n i x au m a`.
- Pitch step preserved in merged per-note curve: first segment `20c`, second jumps to `270c` at 500ms (pitch 67 = +300 plus -30 curve), third jumps to `110c` at 1000ms (pitch 65 = +100 plus +10 curve); final end anchor 1500ms.
- Undo restored 3 notes; redo restored 1; reload persisted 1 merged note.
- Split→merge roundtrip restored one `啊` note, duration `960`, one coalesced sustained vowel `a` lasting `1000ms`, no continuation technique.
- Visible actionable errors and no mutation for:
  - gap: `only exactly contiguous selected notes can be merged...`
  - velocity: `notes with different velocities cannot be merged truthfully...`
  - custom phonemes: `notes with custom phoneme overrides cannot be merged yet...`
  - vibrato: `vibrato-bearing notes cannot be merged yet...`
- CLI smoke passed on duplicated pre-merge project: one `你好吗` merged note, duration `1440`, coherent phonemes.
- Console/network clean in browser harness.

Harness note: an initial script click focused the piano roll by clicking empty canvas and accidentally created extra notes; those were deleted and the positive test rerun cleanly. Corrected results above supersede that pass.

## Files

- `01_positive_merged.png`
- `02_reload_persistence.png`
- `03_split_roundtrip.png`
- `04_negative_gap.png`
- `merge_notes_results.json`
- `positive_corrected.json`
