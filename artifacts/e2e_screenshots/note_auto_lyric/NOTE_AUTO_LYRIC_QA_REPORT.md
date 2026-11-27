# Piano-roll auto lyric entry QA

Date: 2025-11-27. Real visible Chrome, exact `1272x837`. Frontend rebuilt/cache-busted (`index-CfmfrfiN.js`); backend restarted. Project `project_c4c275c11f60`. No repo code modified.

## Verdict

Passed; no defects confirmed.

## Evidence

- Pencil drag created first note and auto-opened the lyric editor only after pointer-up.
- Editor was focused and positioned exactly over the note center:
  - first editor `left=344, top=548.5`, matching computed center position exactly
  - width `194`, height `24.5`, initial value empty
- Typing `你` and Enter committed exactly. Backend phonemes became `['n','i']`; canvas rendered lyric/phoneme text.
- Repeated second creation auto-opened again at exact expected center `left=456, top=548.5`; `好` committed with phonemes `['x','au']`.
- Existing-note move did not open the editor (`null`).
- Existing-note resize did not open the editor (`null`).
- Escape closed a third note's editor without committing typed text; note remained valid with empty lyric/phonemes.
- Blur committed a fourth note lyric `啦`; phonemes `['l','a']`.
- Ctrl+Z removed only the latest lyric commit (`啦` became empty); Ctrl+Y restored `啦` and phonemes exactly.
- Full reload persisted all notes/lyrics/phonemes exactly.
- Marquee regression: visible selection count `2 selected`.
- Copy/paste regression: note count `4 → 6` using visible Copy/Paste buttons.
- Console/network: clean.

## Files

Machine evidence `note_auto_lyric_results.json`; screenshots `01`-`09` in this directory, especially:
- `01_first_auto_editor.png`
- `02_first_committed.png`
- `04_move_resize_no_editor.png`
- `05_escape_uncommitted.png`
- `07_reload_notes.png`
- `09_copy_paste.png`
