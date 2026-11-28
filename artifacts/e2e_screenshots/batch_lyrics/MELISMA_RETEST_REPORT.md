# Batch Lyrics Melisma Retest

All focused retest checks passed. Implementation untouched.

- `你好，-` persisted exactly `你/好/-` with no 422.
- Backend phonemes: preceding `好` ends in vowel `au`; continuation `-` has exactly one vowel phoneme `au` at `start_ms=0`, `duration_ms=500`, matching the preceding final vowel.
- One undo restored `春/好/吗`; redo restored exact `你/好/-`.
- Orphan `-` was rejected visibly/non-silently: transport showed `Save failed — retry` and a bottom-right error toast stated `melisma continuation '-' cannot appear before a sung lyric note`; backend state stayed exactly `你/好/-`.
- Quick regression passed: punctuation batch `你好吗！ → 你/好/吗`; selected first-two subset `星辰 → 星/辰/吗`; continuous Tab opened second lyric with value `好`.
- English whitespace distribution remains untested (no safe non-destructive English fixture was available in the focused pass).
- Only network/console error was the intentional orphan-`-` rejection; no unrelated failures.

Evidence: `melisma_retest_results.json`, `11_melisma_fixed.png`, `12_orphan_dash.png`, `13_regression_final.png`.
