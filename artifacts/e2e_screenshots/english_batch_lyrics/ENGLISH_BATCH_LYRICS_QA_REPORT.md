# English Batch Lyrics QA Report

Date: 2026-11-28
Branch: `devin/1795696369-dynamic-expression` (clean working tree at test start)
Build: production bundle `index-DV-rdEsY.js`; backend restarted with fixture synthesis enabled.
Implementation was not modified or committed.

## Verdict

English whitespace batch lyric distribution passed the requested functional QA. No feature defect was found.

One unrelated layout defect was observed and is documented below.

## Defect

### P3 — Lyrics toolbar button is mostly obscured at a 1280 px-wide viewport

At `innerWidth=1280`, the piano-roll toolbar `Lyrics…` button measured approximately `x=868.35`, width `40.87`; the right panel began at `x=884`. Only the left ~16 px of the button was clickable; its center was beneath/intercepted by the right-panel region, so a standard center click timed out in Playwright. Clicking the exposed left edge did open the modal. This does not affect tokenization logic but is a real narrow-viewport usability/layout issue.

## Functional results

### Exact English whitespace distribution

Input:

```text
hello world again dream love me
```

Batch modal count:

```text
6 lyric tokens → 6 track notes
```

Backend lyric order after Apply:

```text
hello / world / again / dream / love / me
```

This is exactly one whitespace-separated word per note in time order.

Backend phoneme inventories were exact and contained no placeholder/fallback `la`:

```text
hello → h ə l oʊ
world → w ɝ l d
again → ah g eh n
dream → d r i m
love  → l ʌ v
me    → m i
```

Result: passed.

### Undo / redo / reload

- One Ctrl+Z after the full batch assignment restored all six lyrics to empty strings.
- One Ctrl+Y restored exactly `hello/world/again/dream/love/me`.
- Reload preserved the same six lyrics and exact phoneme inventories.

Result: passed.

### Selection targeting and count mismatch

A non-prefix selection of only the final three notes was used so fallback-to-all behavior would be visibly different. Input:

```text
shine bright
```

Batch modal count/warning:

```text
2 lyric tokens → 3 selected notes
Notes beyond the supplied tokens keep their existing lyrics.
```

Before the final-three test, lyrics were:

```text
hello / - / world / bright / love / me
```

After Apply:

```text
hello / - / world / shine / bright / me
```

This proves targeting and partial assignment precisely:

- only selected notes were eligible;
- tokens went to the first two selected notes in time order;
- the third selected note (`me`) retained its existing lyric;
- unselected prefix notes were unchanged.

Result: passed.

### English melisma continuation

Input to the selected prefix notes:

```text
hello - world
```

Resulting lyrics:

```text
hello / - / world / dream / love / me
```

Backend phonemes for the `-` note were exactly:

```json
[{"symbol":"oʊ","start_ms":0.0,"duration_ms":500.0,"is_vowel":true,"locked":false}]
```

This correctly sustained the final vowel `oʊ` of `hello` for the full 500 ms note duration. No 422 or silent placeholder occurred.

Result: passed.

### Continuous Tab lyric regression

The fourth note lyric was edited to `bright`; pressing Tab committed it and opened the next note's lyric editor with existing value `love`. The next-editor screenshot clearly shows this state. Final backend order after that regression and before non-prefix subset testing was:

```text
hello / - / world / bright / love / me
```

Result: passed.

### Final reload

After the non-prefix subset test, reload preserved exactly:

```text
hello / - / world / shine / bright / me
```

Final phoneme inventories remained valid, including `- → oʊ` and `bright → b r ay t`.

Result: passed.

### Console/network

The main instrumented run captured:

- console errors/warnings: 0
- page errors: 0
- failed network responses: 0

Result: passed.

## Test-process notes

- An initial harness pass accidentally clicked in pencil mode and created extra blank notes in a disposable first test project. That project was abandoned; a fresh six-note English project was created and used for all reported results. This was a harness artifact, not a product defect.
- The first marquee rectangle intentionally overlapped four notes; results were still consistent, but selection targeting was then retested with a stricter non-prefix three-note selection. The stricter test is the authoritative targeting evidence.

## Evidence

- `english_batch_lyrics_results.json`
- `nonprefix_subset_results.json`
- `00_exact_english_distribution.png`
- `01_undo_restored_blank.png`
- `02_reload_persisted_exact.png`
- `03_subset_mismatch_partial.png`
- `04_melisma_applied.png`
- `05_continuous_tab_next_editor.png`
- `06_final_reload.png`
- `07_exact_batch_modal_count.png`
- `08_subset_mismatch_modal_warning.png`
- `09_nonprefix_subset_modal.png`
- `10_nonprefix_subset_applied.png`
- `11_final_reload_nonprefix.png`

Recording: `/home/ubuntu/screencasts/english-batch-lyrics-qa/english-batch-lyrics-qa-edited.mp4`
