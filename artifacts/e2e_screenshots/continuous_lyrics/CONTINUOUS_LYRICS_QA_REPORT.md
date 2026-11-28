# Continuous Lyric Entry QA Report

Focused visible-Chrome verification of uncommitted continuous lyric entry after backend restart and cache-busted production build. Implementation was not modified or committed.

## Results

All valid-input focused checks passed. The final instrumented run had no console errors, page errors, or failed network responses.

| Check | Exact backend/UI evidence | Result |
|---|---|---|
| Open first lyric editor | Editor visible, focused, initial value `啦`. | **PASS** |
| Tab to second | After typing `啊` and pressing Tab, editor remained open/focused and value became second note lyric `嘿`. | **PASS** |
| Tab to third | After typing `吗` and pressing Tab, editor remained open/focused and value became third note lyric `呀`. | **PASS** |
| Forward continuous commit | Backend exactly: `audit_n1=啊`, `audit_n2=吗`, `audit_n3=呜`; no duplicated concatenation; editor closed at final boundary. | **PASS** |
| Shift+Tab previous | From third note, Shift+Tab reopened second note editor focused with exact value `吗`. | **PASS** |
| Edit previous + Enter | Second lyric changed exactly `吗→咩`; Enter closed editor. | **PASS** |
| Escape cancel | Tried changing first lyric to `噜`, pressed Escape; backend remained `啊`, editor closed. | **PASS** |
| Blur commit | Changed first lyric to `哈`, clicked outside; backend committed exactly `哈`, editor closed. | **PASS** |
| Undo/redo | Ctrl+Z changed first lyric `哈→啊`; Ctrl+Y restored `啊→哈`. | **PASS** |
| Boundary Tab at last | Editor closed cleanly; third lyric stayed exactly `呜`. | **PASS** |
| Console/network | Final valid-input run: no console errors, page errors, or failed network responses. | **PASS** |

Test-process note: an initial exploratory pass used ASCII syllables (`aa/bb/cc`) on a Mandarin track. Backend validation correctly rejected those lyrics with 422 because they are not valid Mandarin lyric input for this project; the test was restarted with valid Mandarin characters. That initial invalid-input attempt appears earlier in the screen recording but is not counted as a product failure.

## Evidence

- `continuous_lyrics_results.json` — exact machine-readable results
- `00_first_editor_open.png`
- `01_tab_second_focused.png`
- `02_tab_third_focused.png`
- `03_forward_chain_committed.png`
- `04_shift_tab_second_focused.png`
- `05_shift_edit_enter_committed.png`
- `06_escape_cancelled.png`
- `07_blur_committed.png`
- `08_undo_redo.png`
- `09_boundary_tab_last.png`

Recording: `/home/ubuntu/screencasts/continuous-lyrics-qa/continuous-lyrics-qa-edited.mp4`
