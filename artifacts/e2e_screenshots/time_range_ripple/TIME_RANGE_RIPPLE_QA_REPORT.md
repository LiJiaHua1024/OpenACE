# Time-range ripple delete QA

Date: 2025-11-27  
Browser: real visible Chrome through Playwright/CDP  
Viewport: exactly `1272x837`  
Frontend: rebuilt/cache-busted, bundle `index-CuTfryrC.js`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1`  
Project: `project_cb1be4b6e904` / `Time Range Ripple QA`  
Input range: Alt-dragged arrangement repaint range `480-960` ticks (ripple `480`)

## Verdict

The core backend time-range ripple operation is quantitatively correct for the tested notes, breaths, automation points, crossing audio clips, and downstream cross-track material. However the feature is **not fully correct end-to-end** because browser undo does not restore the pre-delete state, and bottom-row clip context menus overflow the arrangement viewport vertically.

## Exact passing evidence

### Alt-drag range and operation

A real Alt-drag created the visible repaint region from tick `480` to tick `960`; screenshot `02_alt_range_480_960.png` shows the orange range over exactly the first bar half. The context-menu item `Ripple delete time range` was enabled for this range and disabled for a zero-length out-and-back drag.

### Vocal notes

Canonical:

- `n_main`: start `0`, duration `960`, lyric `你`
- `n_after`: start `1440`, duration `480`, lyric `好`

After range delete:

- `n_main`: start `0`, duration `480`, lyric `你`
- `n_after`: start `960`, duration `480`, lyric `好`

The portion of the long note inside `480-960` was removed after vowel-aware boundary splitting; the downstream note shifted by exactly `-480`.

### Breaths

Canonical:

- `br_before` at `240`
- `br_inside` at `600`
- `br_after` at `1440`

After:

- `br_before` remains at `240`
- `br_inside` removed
- `br_after` shifted to `960`

### Audio clips, including split/source offsets

Canonical audio track:

- `clip_before`: start `0`, duration `240`, offset `0`
- `clip_cross`: start `240`, duration `1200`, offset `0` (end `1440`, crossing the full range)
- `clip_downstream`: start `1440`, duration `480`, offset `0`

After:

- `clip_before`: unchanged start `0`, duration `240`, offset `0`
- `clip_cross` left fragment: start `240`, duration `240`, offset `0`
- generated right fragment `clip_30fe500213d2`: start `480`, duration `480`, offset `720`
- `clip_downstream`: shifted to start `960`, duration `480`, offset `0`

This is source-accurate for deletion of `480-960`: the right fragment begins at deleted-range start `480`, and its source offset advances by `960-240=720` ticks.

Canonical accompaniment track:

- `acc_inside`: start `480`, duration `240` — fully inside range
- `acc_overlap_right`: start `720`, duration `480` — crosses end boundary
- `acc_downstream`: start `1920`, duration `480`

After:

- `acc_inside` removed exactly
- `acc_overlap_right`: start `480`, duration `240`, offset `240`
- `acc_downstream`: shifted to `1440`

### Automation positions

Dynamic input points `(0,.4),(480,.6),(960,.8),(1440,1.0)` became `(0,.4),(480,.8),(960,1.0)`.

Pitch input points `(0,0),(480,20),(960,40),(1440,0)` became `(0,0),(480,40),(960,0)`.

Positions and deletion/shift amounts are exact. Note the semantic caveat that the implementation places the end-of-range value at the new boundary; this changes interpolation leading into the boundary compared with the untouched pre-range curve. I am reporting this as a design caveat, not a failure of the requested positional behavior.

### Zero/invalid range safety

- Alt-dragging out and back to the same tick produced a zero-length range; the menu item was disabled and no mutation occurred.
- Direct scripted API regression with `start_ticks=480,end_ticks=480` returned HTTP `422` with `ripple delete requires 0 <= start_ticks < end_ticks` and left the project unchanged.
- Browser console and network errors: none.

### Reload persistence and playback sanity

- Reload after redo preserved the post-delete backend state exactly.
- Playback smoke passed: transport advanced from `1.1.1 / 00:00.00` to `1.2.4 / 00:00.94`, with the playing state active.

## Confirmed defects

### 1. Ctrl+Z undo does not restore the pre-delete state

After the operation, Ctrl+Z left the backend state identical to the post-delete state rather than canonical. Therefore:

- `undo_matches_canonical: false`
- `redo_matches_post: true`, but this is not meaningful proof of correct history because undo never left the post state.

Likely integration cause: `rippleDeleteSelectedTimeRange` performs the backend mutation first. The backend publishes the updated project over SSE before/while the frontend subsequently calls `updateProject(..., false)`. The history baseline can therefore already be the mutated post-operation project, so undo restores the mutated state instead of the pre-operation state.

### 2. Bottom-row clip context menu overflows vertically

When right-clicking a clip on the bottom row, the menu measured:

- menu rect: left `732`, right `936`, top `59`, bottom `215`, size `204x156`
- arrangement viewport: left `236`, right `950`, top `58`, bottom `190`
- containment: `inside=false`

Thus the menu extends 25 px below the arrangement viewport and is visibly clipped. The menu action itself remained clickable in this case, but lower clip controls are not fully contained. A bare empty-area menu was correctly contained (`204x39`, bottom `149` inside bottom `190`), so this is specifically the taller clip-menu case.

## Files

- `time_range_ripple_results.json` — full machine-readable evidence
- `menu_supplement.json` — bare-menu containment supplement
- `00_canonical_arrangement.png`
- `01_zero_range_menu_disabled.png`
- `02_alt_range_480_960.png`
- `03_menu_contained_range_enabled.png`
- `04_after_range_ripple.png`
- `05_undo.png`
- `06_redo.png`
- `07_reload_post_state.png`
- `08_playback_sanity.png`
- `09_empty_zero_menu.png`
- `10_empty_range_menu.png`

## Defect-fix retest — 2025-11-27

Frontend rebuilt/cache-busted (`index-C5rGxxtO.js`) and backend restarted. Fresh project: `project_cca733ac0871` / `Time Range Ripple Fix Recheck`.

### Undo/redo defect retest: passed

- Ctrl+Z now restored the canonical pre-delete state exactly across notes, clips, breaths, dynamic automation, and pitch automation.
- Ctrl+Y then restored the exact post-delete state, including generated clip id `clip_e27e047ffe49`.
- `undo_matches_canonical: true`
- `redo_matches_post: true`

### Core ripple regression: passed

The same `480-960` operation remained exact:

- `n_main`: `0+960 你` → `0+480 你`
- `n_after`: `1440+480 好` → `960+480 好`
- inside breath removed; `br_after` `1440→960`
- crossing audio clip split into `240+240 offset0` plus generated right fragment `480+480 offset720`
- downstream audio clip `1440→960`
- inside accompaniment clip removed; overlapping accompaniment clip became `480+240 offset240`; downstream accompaniment `1920→1440`
- dynamic `(0,.4),(480,.8),(960,1.0)`
- pitch `(0,0),(480,40),(960,0)`

### Bottom-row clip-menu containment retest: failed

The measured menu geometry is unchanged in the important respect:

- menu rect: left `732`, right `936`, top `59`, bottom `215`, size `204x156`
- arrangement viewport: left `236`, right `950`, top `58`, bottom `190`
- containment: `inside=false`

The updated clamp reaches the top of the arrangement (`top59`, internal top about `1`), but a `156px` menu cannot fit inside this `132px` arrangement viewport (`58→190`). Thus simply correcting the estimated menu height is insufficient for the three-track viewport; the menu needs scrolling/compaction or a different overlay/containment strategy.

Retest screenshots:

- `11_retest_canonical.png`
- `12_retest_bottom_clip_menu.png`
- `13_retest_post.png`
- `14_retest_undo.png`
- `15_retest_redo.png`

Machine evidence was merged into `time_range_ripple_results.json` under `defect_retest_after_fixes`.

## Final menu CSS retest — 2025-11-27

Frontend rebuilt/cache-busted (`index-CePYMYBc.js`, CSS `index-CDcooTUj.css`) and backend restarted. Fresh project: `project_839f57352a45` / `Time Range Menu Final Recheck`.

### Bottom-row clip-menu containment: passed

- Menu rect: left `732`, right `936`, top `59`, bottom `187`, size `204x128`
- Arrangement viewport: left `236`, right `950`, top `58`, bottom `190`
- `inside=true`
- `clientHeight=116`, `scrollHeight=154`, `scrollable=true`
- Real mouse wheel over the menu moved `scrollTop` from `0` to `38`; bottom controls including `Ripple delete`, `Ripple delete across tracks`, and `Clip gain` became visible.
- All 8 action buttons were reachable/visible across top and scrolled positions.

### Ripple action after menu CSS change: passed

`Ripple delete time range` was clicked once after scrolling back to the top. Exact regression evidence remained correct:

- notes exactly `n_main 0+480 你`, `n_after 960+480 好`
- breaths exactly `br_before 240`, `br_after 960`
- generated crossing-clip right fragment `480+480 offset720`
- `clip_downstream 960+480`
- `acc_overlap_right 480+240 offset240`
- `acc_downstream 1440+480`
- `acc_inside` removed
- console/network errors: none

Minor residual visual observation, outside the narrow containment fix: long labels such as `Ripple delete time range` remain horizontally clipped in the two-column `204px` menu, although the buttons are reachable and clickable.

Screenshots: `16_final_menu_initial.png`, `17_final_menu_scrolled.png`, `18_final_after_ripple.png`. Machine evidence is merged into `time_range_ripple_results.json` under `final_menu_css_retest`.
