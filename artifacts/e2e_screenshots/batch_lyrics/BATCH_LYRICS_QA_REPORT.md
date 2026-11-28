# Batch Lyrics QA Report

Focused visible-Chrome test after backend restart/cache-bust. Implementation was not modified or committed.

## Defect found

**P1 — preserved melisma `-` tokens are rejected by the backend.** Input `你好，-` correctly displayed `3 lyric tokens → 3 track notes`, implying tokens `你 / 好 / -`, but Apply produced a project-save `422`; backend lyrics remained exactly `哈/咩/呜`. Direct backend validation also rejects a Mandarin note whose lyric is `-` (`unsupported character '-'`). Thus the advertised melisma preservation currently makes the entire batch assignment fail to persist.

## Passed checks

- Punctuation-skipping Mandarin distribution: `你好吗！` assigned exactly `你/好/吗` to the three time-sorted notes; no 422.
- Ctrl+Enter committed and closed the editor.
- One Ctrl+Z restored all prior lyrics `哈/咩/呜`; Ctrl+Y restored exactly `你/好/吗`.
- Reload persisted `你/好/吗`.
- Correctly selected first two notes (click then Shift+click): `星辰` assigned exactly `星/辰/吗`; third unselected note stayed `吗`.
- Mismatch case on two selected notes: count `1 lyric tokens → 2 selected notes`; warning exactly `Notes beyond the supplied tokens keep their existing lyrics.`; Apply assigned only first selected note, producing `孤/好/吗` as documented.
- Escape closed the batch editor without committing.
- Continuous lyric Tab regression passed: typing `春` in first note and pressing Tab opened second editor with value `好`.
- Batch editor geometry remained inside viewport (`x=577,y=406,w=360,h=205`).
- No page errors. The only console/network failure was the melisma-related 422 defect above.

## Incomplete

- English whitespace distribution: untested. The available fixture is a Mandarin track whose existing valid Mandarin lyrics make switching language non-trivial/destructive; focused time was spent on the requested Mandarin punctuation/melisma/subset/mismatch behavior.

## Evidence

- `batch_lyrics_results.json`
- `00_melisma_editor_count.png`, `01_melisma_after_apply.png`
- `02_valid_editor.png`, `03_valid_applied.png`, `04_after_reload.png`
- `09_subset_editor_corrected.png`, `10_mismatch_warning_corrected.png`
- `08_final_batch_editor.png`

Recording: `/home/ubuntu/screencasts/batch-lyrics-qa/batch-lyrics-qa-edited.mp4`
