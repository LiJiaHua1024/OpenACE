# Phoneme boundaries — focused rerun after backend restart

The backend was killed and restarted from the current working tree with `OPENACE_CI_SYNTH_FIXTURE=1`. The prior `s/ŋ/ɪ` result did not reproduce.

## API generation check

PASS. The test note now generates correct English `sing` timing/order:

- `s`: `-45ms`, duration `45ms`
- `ɪ`: `0ms`, duration `1055ms`
- `ŋ`: `1055ms`, duration `70ms`

## Focused visible-browser results

All focused assertions passed.

- Internal vowel/coda boundary drag: PASS — vowel end/coda start moved from `1055ms` to `1108.571ms`, contiguous.
- Outer first-consonant onset drag: PASS — onset moved from `-45ms` to `-89.643ms`, contiguous to locked 0ms vowel start.
- Final end boundary drag: PASS — dragging inward shortened coda end; coda duration became `8ms`. Note: an outward drag is clamped at the note end by design, so the valid adversarial direction is inward.
- Persistence: PASS — backend API reflected every legitimate drag without validation rejection.
- Hit zones/cursor: PASS — all boundary positions reported `col-resize`.
- Undo/redo: PASS — one-step undo restored pre-end-drag state and redo restored exact post-drag state.
- Visual layout: PASS — small pre-note `s`, long vowel across note body, small final `ŋ`; alignment matched beat-anchored note start/shared zoom.
- Accidental breath creation: none observed.
- Console errors: none.

## Rerun artifacts

- `rerun_01_phonemes_before.png`
- `rerun_02_internal_held.png`
- `rerun_03_onset_held.png`
- `rerun_04_end_held.png`
- `rerun_05_after_three_drags.png`
- `phoneme_rerun_results.json`

Harness note: the first rerun attempt incorrectly tried to drag the final end outward beyond the note duration. That is clamped by design; the valid final-end test is inward. This was a harness correction, not a product defect.
