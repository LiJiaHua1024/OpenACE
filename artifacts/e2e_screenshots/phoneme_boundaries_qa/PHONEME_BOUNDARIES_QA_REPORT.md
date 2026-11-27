# Phoneme boundaries QA

Visible Chrome 1272x837, Playwright/CDP, fixture server. Existing note was set to English `sing` through the same backend preparation path used by the regression test, then Breath & Phoneme was inspected and boundaries were dragged.

## Blocking finding

The tested long note did **not** generate the expected `s / ɪ / ŋ` timing/order. Backend state was:

- `s`: `-52.5ms`, duration `26.25ms`
- `ŋ`: `-26.25ms`, duration `26.25ms`
- `ɪ`: `0ms`, duration `270ms`

Thus the coda `ŋ` appeared before the first vowel and the displayed order/timing was effectively `s / ŋ / ɪ`. The lane visually showed only tiny compressed pre-note segments near the note start, not the expected vowel/coda layout across the note. Because there was no valid post-vowel coda boundary, the requested vowel/coda boundary scenario could not be meaningfully validated on this note.

## Results

- Symbols/timing for `sing`: **FAIL** — expected `s,ɪ,ŋ` with vowel at 0 and coda after vowel; got `s,ŋ,ɪ` timing/order.
- Visual layout: **FAIL/serious concern** — compressed tiny segments before note start; no clear usable vowel/coda layout.
- Boundary hit cursors: **PASS** — all three tested boundary positions reported `col-resize`.
- Drag persistence/contiguity: **partially observed** — drags persisted contiguously and did not trigger backend validation rejection, but they were not the requested valid vowel/coda scenario because generation was wrong.
- Undo/redo: **PASS** — final-end drag undo/redo restored exact states.
- Accidental breath creation: none observed.
- Console errors: none.

## Artifacts

- `01_phonemes_before.png`
- `02_internal_held.png`
- `03_onset_held.png`
- `04_end_held.png`
- `05_after_three_drags.png`
- `phoneme_results.json`
