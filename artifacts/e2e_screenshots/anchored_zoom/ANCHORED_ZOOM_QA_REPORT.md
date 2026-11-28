# Cursor-Anchored Timeline Zoom QA Report

Date: 2026-11-28
Project fixture: `project_c4bccc903fcc` / Global Workflow Audit
Build: production frontend bundle `index-DV-rdEsY.js`; backend restarted with fixture synth enabled.
Implementation files were not modified or committed by QA.

## Verdict

Cursor-anchored timeline zoom passed the requested quantitative browser QA. No product defect was found.

## Quantitative results

### 1. Cursor-anchor preservation and synchronization

A non-zero horizontal scroll was established before testing so zoom-out was measured away from the legitimate left-edge clamp. For each surface and x position, the musical tick under the cursor was computed before the wheel event and again after the event at the same screen x using the correct 64 px gutter.

Test matrix: arrangement, tempo lane, piano roll, automation lane × x positions 200/500/900 × zoom in/out = 24 measurements.

- Maximum absolute anchor error: **4.547473508864641e-13 ticks** (floating-point noise only)
- 23/24 measurements were exactly `0.0` ticks; the remaining one was the above sub-quantum floating-point residue
- All four surfaces remained synchronized throughout
- Final synchronized surface count: **4**
- Surfaces with `onTimelineChange`: **4**
- Unique shared timeline tuples across surfaces: **1**

Result: **passed**

### 2. Min/max clamp behavior

- Repeated Ctrl/Cmd zoom-out reached exactly `pxPerBeat = 32`; repeated further zoom-out made no additional change
- At minimum zoom, `scrollTicks` remained exactly `0` at the left edge
- Repeated Ctrl/Cmd zoom-in reached exactly `pxPerBeat = 360`; repeated further zoom-in made no additional change
- At maximum zoom, repeated additional zoom-in left both `pxPerBeat = 360` and `scrollTicks = 11425.333333333334` unchanged
- Across all captured states, minimum observed `scrollTicks` was **0**; no negative scroll and no non-finite values were observed

Result: **passed**

### 3. Normal wheel/modifier regressions

Measured shared timeline and internal piano-roll view state before/after each input:

- Arrangement Shift+wheel: horizontal scroll increased exactly `480` ticks for a 240-unit wheel delta; `pxPerBeat` unchanged
- Arrangement normal wheel vertical native scroll: after temporarily adding three BGM tracks through the visible UI to create overflow, `.arrangement-view.scrollTop` changed from `0` to the maximum available `59` (`scrollHeight 268`, `clientHeight 209`); the three temporary tracks were removed by restoring the exact project JSON afterward
- Piano normal wheel: horizontal scroll increased exactly `480` ticks; `pxPerBeat` unchanged
- Automation normal wheel: horizontal scroll increased exactly `480` ticks; `pxPerBeat` unchanged
- Piano Alt+wheel up: `rowHeight 15 → 16.5`, ratio exactly `1.1`; timeline unchanged
- Piano Alt+wheel down: `rowHeight 16.5 → 14.85`, ratio exactly `0.9`; timeline unchanged
- Piano Shift+wheel up: `topPitch 79 → 81`, delta exactly `+2`; timeline unchanged
- Piano Shift+wheel down: `topPitch 81 → 79`, delta exactly `-2`; timeline unchanged

Result: **passed**

### 4. Rapid alternating zoom

- 30 rapid alternating Ctrl+wheel zoom steps completed
- Maximum absolute anchor error: **0.0 ticks**
- All sampled `pxPerBeat` and `scrollTicks` values were finite
- No NaN, negative scroll, drift, or visible persistent flicker was observed

Result: **passed**

### 5. Playback/Follow regression and console/network

Visible manual playback was started after the zoom tests. The red playhead advanced and playback was audible/active according to loudness history. Follow paging advanced the shared timeline to bars 7–9 and kept the red playhead visible and aligned across arrangement, tempo lane, piano roll, and automation lane. Playback was then stopped cleanly.

Console/page-error/network monitoring in the quantitative runs captured:

- Console errors/warnings: **0**
- Page errors: **0**
- Failed network responses: **0**

Result: **passed**

## Test-process caveat

One early Playwright playback/Follow probe produced misleading frozen-position evidence because the final stop action raced asynchronous playback startup. A direct visible-browser retry confirmed normal playback and Follow behavior; the visible evidence is `04_playback_follow_paged.png`. This was a harness/timing artifact, not a product failure.

## Defects

None found.

## Evidence files

- `anchor_zoom_core_results.json` — full quantitative anchor/clamp/rapid/synchronization results
- `wheel_regression_results.json` — horizontal scroll, Alt row zoom, and Shift pitch navigation results
- `arrangement_vertical_results.json` — vertical native-scroll measurement
- `00_anchor_surface_pass.png` — post-anchor-test overview
- `01_after_rapid_zoom.png` — rapid zoom result
- `02_wheel_modifier_regressions.png` — modifier regression state
- `03_arrangement_vertical_scroll.png` — vertical overflow scroll evidence
- `04_playback_follow_paged.png` — visible Follow regression evidence
- `05_final_state.png` — final stopped state
