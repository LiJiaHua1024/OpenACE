# Piano-roll note audition QA

Date: 2025-11-27  
Browser: real visible Chrome through Playwright/CDP  
Viewport: exactly `1272x837`  
Frontend: rebuilt/cache-busted, bundle `index-BPIlxO1T.js`, CSS `index-C5e_Y6kE.css`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1`  
Project: `project_18b1db3048e8` / `Note Audition QA Final`  
Instrumentation: page-level `AudioContext.createOscillator` and `AudioParam.setValueAtTime` monitoring; no repo code modified.

## Verdict

Most audition behavior is correct: the toolbar toggle is visible/layout-contained and persistent, note creation and note selection produce exact expected triangle-oscillator frequencies, controlled vertical drags end at the correct pitch, toggle-off suppresses new audition nodes, undo/redo and playback still work, and console/network are clean.

One defect remains: **fast vertical pitch drags bypass the throttle whenever the pitch changes**, producing a pileup of simultaneous oscillators. In the measured fast drag, 9 oscillators were created within 149 ms and all 9 overlapped. They did stop/end afterward, so this is excessive overlap rather than a permanent node leak.

## Passing evidence

### Toggle visibility/layout and persistence

- `♪ Audition` visible in the piano-roll toolbar.
- Button rect: `394.39→448.82 x 251.5→276.5`, fully inside toolbar `236→950 x 245→284`.
- Toolbar `scrollWidth=714`, `clientWidth=714`: no horizontal overflow.
- Normalized starting state: localStorage `on`, active `true`.
- Clicking toggle: localStorage `off`, active `false`.
- Reload preserved off exactly.
- Clicking toggle on and reloading preserved localStorage `on`, active `true`.

### Note creation frequencies

Real pencil clicks created notes at two rows:

- pitch62/D4 produced `293.6647679174076 Hz`; expected `293.6647679174076`
- pitch64/E4 produced `329.6275569128699 Hz`; expected `329.6275569128699`
- oscillator type: `triangle`

### Clicking/selecting an existing note

Clicking the existing pitch62 note produced exactly one new audition event at `293.6647679174076 Hz`.

### Controlled vertical drag

A controlled drag moved pitch62 → pitch67. Captured frequencies:

`293.6648, 311.1270, 329.6276, 349.2282, 369.9944, 391.9954 Hz`

Final frequency exactly matched pitch67 (`391.99543598174927 Hz`). Backend note pitch was `67`. Maximum theoretical overlap was 3 oscillators, consistent with the 240 ms audition envelope and controlled drag speed. All 6 controlled-drag oscillators ended.

### Toggle-off suppression

After turning `♪ Audition` off:

- oscillator event count stayed `18 → 18`
- creating a new note produced no new oscillator
- clicking an existing note produced no new oscillator
- state remained localStorage `off`, inactive button

### Normal editing/undo/redo/playback

- Controlled drag backend result: pitch62 → pitch67.
- Ctrl+Z restored pitch62 exactly.
- Ctrl+Y restored pitch67 exactly.
- Playback smoke advanced `00:00.00 → 00:00.91` with playing state active.
- Console errors/warnings: none.
- Network errors: none.

## Confirmed defect: fast pitch-drag oscillator pileup

A fast vertical drag moved pitch67 → pitch75. Captured frequencies:

`391.9954, 415.3047, 440, 466.1638, 493.8833, 523.2511, 554.3653, 587.3295, 622.2540 Hz`

Measurements:

- 9 oscillator events
- created over only `149 ms`
- maximum simultaneous overlap: **9**
- all eventually ended, so no permanent leak was observed

Cause visible in implementation: the throttle suppresses a repeat only when `last.pitch === pitch` and the event is within 90 ms. Every semitone change bypasses the time throttle, so rapid pointer movement creates one overlapping 240 ms oscillator per semitone. This violates the requested no-runaway-overlap behavior even though the final pitch and note edit are correct.

## Files

- `note_audition_results.json` — complete machine-readable evidence
- `00_audition_toolbar.png`
- `01_audition_off.png`
- `02_audition_on_after_reload.png`
- `03_created_notes.png`
- `04_after_vertical_drag.png`
- `05_fast_drag.png`
- `06_toggle_off_no_new_notes.png`
- `07_playback.png`

## Fast-drag throttle retest — 2025-11-27

Frontend rebuilt/cache-busted (`index-DPLtVoFY.js`) and backend restarted. Fresh project: `project_e3c250042e79` / `Note Audition Throttle Recheck`.

### Result: passed

The non-forced throttle now applies across pitch changes.

Fast pitch67→75 drag:

- oscillator count reduced from **9** to **2**
- event spacing: `100.7 ms`
- maximum simultaneous overlap: **2**
- captured frequencies: `391.99543598174927 Hz` then `554.3652619537442 Hz`
- backend note still reached final pitch75
- no runaway/excessive overlap observed

Controlled pitch62→67 drag:

- 6 correct ascending frequencies retained:
  `293.6648, 311.1270, 329.6276, 349.2282, 369.9944, 391.9954 Hz`
- final pitch67 frequency exact
- maximum overlap **2**
- all controlled-drag oscillators ended

Quick regressions:

- create pitch62/pitch64 frequencies exact: `293.6647679174076`, `329.6275569128699`
- clicking existing pitch62 exact: `293.6647679174076`
- toggle persistence still exact across reload in both directions
- toggle-off suppression exact: oscillator count `11 → 11`
- Ctrl+Z/Ctrl+Y around controlled drag exact
- playback advanced `00:00.00 → 00:00.91`
- console/network clean

Machine evidence merged into `note_audition_results.json` under `fast_drag_throttle_retest`. Screenshots `00`-`07` were refreshed by this retest.
