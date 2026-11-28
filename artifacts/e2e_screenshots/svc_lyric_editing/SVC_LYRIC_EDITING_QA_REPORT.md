# SVC clip lyric editing QA

Date: 2025-11-27  
Mode: real visible Chrome, exact `1272×837`, rebuilt/cache-busted frontend  
Project: `project_709af284eb64`  
Recording: `/home/ubuntu/screencasts/svc-lyric-editing-qa/svc-lyric-editing-qa-edited.mp4`

## Verdict

All focused acceptance checks passed. No implementation defect was confirmed.

## Evidence

| Assertion | Result | Evidence |
|---|---:|---|
| `SVC clip lyrics` section appears for selected audio/SVC clip track | PASS | Panel visible with `4 ASR words · svc lyrics source` |
| ASR word/timing rows render | PASS | Rows for `you/are/my/world`, each with text/start/end/add/delete controls |
| Edit word | PASS | `you` → `hey` persisted in backend |
| Edit start time | PASS | `are` start `0.45→0.55`; canvas lyric x moved from about `165` to `187.5–198.5` |
| React redraw/canvas reflection | PASS | Canvas groups after edit: x `87–99`, `187.5–198.5`, `311–321`, `389.5–409` |
| Reload persistence | PASS | Backend and canvas groups identical after cache-busted reload |
| Undo/redo | PASS | Fresh timing edit `0.55→0.65` moved group to x `210–220.5`; visible Undo restored `0.55`/x `187.5–198.5`; visible Redo reapplied `0.65`/x `210–220.5` |
| Add real word | PASS | Prompt accepted `newword`; backend inserted it at start `0.42`, end `0.72`; no placeholder fabricated |
| Delete word | PASS | `newword` removed; backend returned to 4 expected rows |
| Invalid `end<=start` atomic rejection | PASS | Attempted end `0.50` with start `0.55` showed `Lyric end must be after its start.`; backend before/after identical |
| Layout at 1272×837 | PASS | No body overflow; panel `scrollWidth=clientWidth=311` |
| Console/network | PASS | No app errors. Canvas warning was QA readback instrumentation; SSE aborts were deliberate reloads |

Note: reload resets undo history as expected, so undo/redo was verified using visible toolbar buttons after a fresh timing edit rather than across reload.

## Artifacts

- Results: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyric_editing/svc_lyric_editing_results.json`
- Panel/initial: `01_svc_clip_lyrics_panel.png`
- Edited word/time/canvas: `02_edited_word_time_canvas.png`
- Reload persistence: `03_reload_persistence.png`
- Invalid atomic error: `06_invalid_atomic_error.png`
- Added word: `07_added_word.png`
- Deleted word: `08_deleted_word.png`
- Visible undo/redo: `10_visible_undo.png`, `11_visible_redo.png`

No implementation files were modified.
