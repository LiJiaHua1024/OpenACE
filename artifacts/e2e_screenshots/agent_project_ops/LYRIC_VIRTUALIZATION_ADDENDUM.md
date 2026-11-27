# Lyric Virtualization Regression Addendum

Focused visible-Chrome regression after rebuilding and cache-busting the frontend.

## Passing focused checks

- 30-note project initially mounted only 15 lyric rows rather than all 30.
- Initial rows were aligned at 34px pitch with no vertical or input/phoneme overlap.
- A real mouse-wheel scroll moved the window to later rows 15-29 with correct indices/lyrics and no blank overlap.
- Row 27 was edited through real mouse/keyboard input from `la` to `hey`; backend persisted `hey` and phonemes `hh ey`.
- Dense 1200-note project mounted only 15 row DOM nodes, not 1200; spacer scrollHeight was 40800px in a 220px viewport.
- No console errors or network failures.

## Implementation defect found

After scrolling the 30-note list, switching to the dense project, and selecting `Dense Vocal` after a zero-note vocal track had caused the list to unmount/remount, the lyric viewport was blank. DOM `scrollTop` was 0 while the virtual window retained `translateY(646px)`; mounted rows began at index 20 below the visible viewport. A real wheel scroll recovered rows 12-17, confirming stale virtual scroll state rather than missing data.

Evidence: `lyric_virtualization_blank_defect.png`, `lyric_virtualization_scroll_recovery.png`, `lyric_virtualization_check.png`; machine results in `lyric_virtualization_results.json`.

## Fix recheck

After the reset fix and a frontend rebuild/cache-bust, the exact failing repro was rerun:

- 30-note list scrolled first (`scrollTop=640`, rows 15-29).
- Row 28 edit still persisted: `la` -> `hey`, phonemes `hh ey`.
- After switching to the dense project and selecting `Dense Vocal` through the zero-note/unmount path, viewport was not blank.
- Dense reset state was exactly `scrollTop=0`, `transform=translateY(0px)`, first indices 1-5, 7 visible rows, 15 mounted rows for 1200 notes.
- Real wheel scrolling then produced `scrollTop=640`, `transform=translateY(476px)`, first indices 15-19, 8 visible rows.
- Rows remained aligned at 34px pitch without overlap; no console/network errors.

Evidence: `lyric_virtualization_fix_check.png`, `lyric_fix_dense_scrolled.png`, `lyric_fix_30_scrolled_edit.png`, `lyric_virtualization_fix_results.json`.

Harness note: the first machine-output oracle incorrectly inspected only the first five `firstIndices`; full row data showed rows 15-29, and the corrected oracle passes.
