# Keyboard nudge form-control isolation micro-regression

Date: 2025-11-27  
Surface: real visible Chrome, exact viewport `1272x837`  
Build state: frontend rebuilt, backend restarted, browser cache-busted  
Implementation files: unchanged

## Verdict

Passed. No defect found.

## Exact evidence

- Four notes were selected before the test.
- The Grid control was focused; `document.activeElement` was exactly `SELECT` for every arrow press.
- Pressed `ArrowUp`, `ArrowDown`, `ArrowLeft`, and `ArrowRight` while the Grid select was focused.
- Backend note state after those presses was byte-for-byte equivalent in the tested tuple fields: every note id, start, duration, pitch, and lyric was unchanged.
- Grid remained `1/16` during this particular key sequence; the important isolation condition was still exactly satisfied because the events targeted the focused `SELECT`.
- Clicking an already-selected visible note moved focus to `DIV|piano-roll-wrap` while preserving `4 selected`.
- One piano-focused `ArrowRight` moved all four selected notes exactly `+120` ticks, matching the current 1/16 grid step (`480/4`), with zero pitch movement.
- Console errors/warnings: none.
- Failed network responses: none.

Harness note: the reused disposable keyboard-nudge fixture contained a fourth stray note from earlier piano-click setup. It was selected and measured like the other three notes; this does not affect the isolation conclusion.

## Files

- `form_control_isolation_supplement.json` — exact before/after note states, focus states, movement deltas, console/network result.
- `40_form_control_grid_arrows.png` — Grid-select interaction state before piano nudge.
- `41_piano_focus_nudge_after_select.png` — state after piano-focused nudge.
- `/home/ubuntu/screencasts/keyboard-nudge-form-isolation/keyboard-nudge-form-isolation-edited.mp4` — interaction recording.
