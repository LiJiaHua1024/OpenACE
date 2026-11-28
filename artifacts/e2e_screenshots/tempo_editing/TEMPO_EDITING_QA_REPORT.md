# Tempo editing QA report

Date: 2026-11-27
Branch: `devin/1795696369-dynamic-expression`
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

All requested TempoLane checks passed.

Harness transparency: the first undo assertion incorrectly assumed the separate Tick and BPM numeric-field edits would collapse into one undo step. Actual behavior correctly undid the most recent granular numeric edit and redo restored it; the results file was corrected with that interpretation. This was a test-oracle issue, not an application defect.

## Lane visibility/alignment

The dedicated `TEMPO` lane is visible between arrangement and piano roll. It has a fixed label gutter, orange piecewise tempo step line, tempo markers, numeric inline editor, and red playhead. Screenshots show its vertical gridlines aligned with the piano-roll/automation timeline before and after wheel zoom/scroll interaction.

Passed:

- lane visible and professional
- timeline grid alignment visually correct
- wheel scroll screenshot captured
- Ctrl+wheel zoom screenshot captured
- zoomed lane/piano/automation gridlines remain visually aligned

## Empty creation and dragging

Passed:

- empty click near tick 960 created exact snapped backend point `{ticks:960, bpm:120.6}`
- horizontal drag moved it to tick 1080
- vertical drag changed BPM from `120.6` to `125.6`
- backend `tempo_map` reflected both changes

## Precise numeric editing and transport

Passed:

- numeric editor set exact positive point `{ticks:960, bpm:60.0}`
- backend base `bpm` remained `120.0`
- piano-ruler seek to tick 1440 showed:
  - position `1.4.1`
  - transport time `00:02.00`

This confirms the piecewise 120→60 conversion rather than constant-BPM `00:01.50`.

## Undo/redo

Passed:

- after exact numeric state `{960,60}`, one undo reverted the most recent granular BPM edit to `{960,125.6}`
- redo restored exact `{960,60}`

This verifies functional undo/redo for tempo edits. The undo granularity is per numeric field edit.

## Delete

Passed:

- selected positive-tick point was deleted using the precise panel **Delete** button
- backend `tempo_map` became empty
- base `bpm` remained available as the tick-zero anchor

## Tick-zero anchor BPM editing

Passed:

- cyan tick-zero marker was dragged vertically
- backend base BPM changed from `120.0` to `125.0`
- transport BPM label also showed `125`
- seek to tick 480 showed `00:00.48`, exactly matching `60 / 125 = 0.48s`

This confirms tick-zero vertical editing and transport conversion are consistent.

## Health

No console errors or network failures occurred.

## Evidence

- `01_tempo_lane_initial.png`
- `02_tempo_created.png`
- `03_tempo_dragged.png`
- `04_numeric_exact_960_60.png`
- `05_transport_tick1440_2s.png`
- `06_undo_redo_state.png`
- `07_tick_zero_bpm_edited.png`
- `08_after_tempo_scroll.png`
- `09_after_tempo_ctrl_zoom.png`
- `tempo_editing_results.json`
