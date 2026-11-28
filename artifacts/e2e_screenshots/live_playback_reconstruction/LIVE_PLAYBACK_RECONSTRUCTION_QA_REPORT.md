# Live Playback Reconstruction Regression QA Report

## Scope and environment

- Regression QA of the fixed live playback reconstruction logic in `frontend/src/App.tsx`.
- Real visible Chrome at exactly `1272×837`, driven through Playwright UI interactions.
- Frontend rebuilt and cache-busted before testing.
- Backend schema unchanged; no backend restart was required.
- Fixture project: `project_d152f8c8ae7d` / **Live Playback Reconstruction QA**.
- Canonical fixture clips used valid audible `/uploads/svclyrics_words.wav` audio at varied starts:
  - `A1`: start 480, duration 1440
  - `B1`: start 1920, duration 1440
  - `A2`: start 3360, duration 1440
- WebAudio and timers were instrumented non-invasively in-page by wrapping `createBufferSource`, source `start`/`stop`, `decodeAudioData`, and `setTimeout`/`clearTimeout`.
- No implementation files were modified.

## Regression verdict

**Passed. No implementation defects were confirmed in this regression.**

The previously confirmed defects are fixed in the tested revision:

1. arrangement clip drag now reconstructs playback;
2. undo/redo now reconstructs playback;
3. same-snapshot project/SSE re-renders no longer permanently cancel the rebuild timer.

## Controlled evidence

### Initial playback positioning

Passed.

- Seek position for the initial probe: `00:02.50`.
- Click-to-decode call: `48.7ms`.
- Click-to-first-source-create: `52.3ms`.
- In-progress clip source offset: `0.5s`, correct for a clip that started at `2.0s` when playback begins at `2.5s`.
- Next future clip scheduled exactly `1.0s` ahead.
- The playhead did not start ahead because of decode latency.

The approximately `1.85s` delay before visual movement is the previously established Linux Chrome `AudioContext` warm-up limitation, reproduced even with a raw fresh audio context; it is not attributed to this implementation.

### Arrangement clip drag while playing

Passed.

A real mouse drag changed:

- `B1.start_ticks`: `1920 → 2040`

WebAudio counts changed:

| Count | Before | After |
|---|---:|---:|
| created sources | 24 | 27 |
| source starts | 8 | 11 |
| source stops | 21 | 24 |

Timing:

- rebuild timer fired `126.8ms` after scheduling;
- `171.7ms` after the scripted drag-start marker.

The reconstruction occurred while playback and even the final portion of the drag gesture were still in progress, which is expected debounce behavior. The playhead remained continuous.

### Left trim while playing

Passed.

A real edge drag changed:

- `B1`: `2040/1440/offset 0 → 2160/1320/offset 120`

Counts changed:

| Count | Before | After |
|---|---:|---:|
| created sources | 27 | 30 |
| source starts | 11 | 14 |
| source stops | 24 | 27 |

Timing:

- rebuild timer fired `126.9ms` after scheduling;
- `88.2ms` after mouse release.

### Undo/redo while playing

Passed.

Undo restored:

- `B1`: `2040/1440/offset 0`

Redo reapplied:

- `B1`: `2160/1320/offset 120`

Counts:

| Operation | Created before/after | Starts before/after | Stops before/after | Click-to-rebuild |
|---|---:|---:|---:|---:|
| Undo | 30 / 33 | 14 / 16 | 27 / 30 | 166.3ms |
| Redo | 33 / 36 | 16 / 18 | 30 / 33 | 163.3ms |

Timer-only latency was approximately `120–122ms` for both. Fewer than three new sources started because some clips were already in the past at the moment of the edit; the important stop/create reconstruction counts still changed correctly.

### Rapid successive edit debounce

Passed.

Three playback-affecting track edits were performed within `13.8ms`.

Timer instrumentation showed correct debounce behavior:

- first 120ms timer scheduled;
- cleared `4.6ms` later when the next snapshot arrived;
- replacement timer fired once after `120.3ms`;
- final-input-to-rebuild latency: `118.7ms`.

Exactly one reconstruction batch occurred for the sub-120ms burst. The slower earlier sequence also showed correct clear/reschedule behavior rather than permanent cancellation.

### Source ordering and duplicate-graph behavior

Passed.

For every observed reconstruction, old sources were stopped before new sources were created or started. No evidence of overlapping duplicate old/new graphs was observed in the instrumentation.

### Playhead continuity

Passed.

Across the active drag/trim/undo/redo sequence:

- unexpected backward jumps: `0`;
- forward jumps over `0.2s`: `0`;
- measured playhead rate: `1.003×` wall clock.

The only backward movement in the broader test came from intentional seek/stop actions.

### Decode cache reuse

Passed.

`decodeAudioData` count remained `1` through repeated reconstructions and stop/restart. Unchanged audio was not re-decoded.

### Stop/restart

Passed.

- Pause readout: `00:04.41`.
- Restart readout after roughly 500ms: `00:04.90`.
- Transport resumed without resetting to zero.

Note: by that point mute/solo state made only a subset of clips audible, so source-start count is not a useful assertion there; the transport itself demonstrably resumed.

### Layout, console, and network

Passed.

Final cache-busted reload:

- viewport: `1272×837`;
- body `scrollWidth/clientWidth`: `1272/1272`;
- transport `scrollWidth/clientWidth`: `1272/1272`;
- console messages: `0`;
- network failures: `0`;
- HTTP errors: `0`.

## Limitations

- Fade-during-playback remains untested in this regression. The feasible repeated controlled case requested by the user was trim, which was tested successfully.
- Browser instrumentation cannot prove sample-level audible gain continuity, but it does prove source ordering, scheduling times, offsets, decode reuse, and playhead continuity.

## Key artifacts

- Recording: `/home/ubuntu/screencasts/live-playback-reconstruction-regression-qa/live-playback-reconstruction-regression-qa-edited.mp4`
- Full event/timer/sample data: `live_regression_full_data.json`
- Compact active-operation results: `live_regression_compact_ops.json`
- Fast rapid-edit evidence: `live_regression_fast_rapid.json`
- Final health evidence: `live_regression_final_health.json`
- Machine-readable summary: `live_playback_reconstruction_results.json`
- Key screenshots:
  - `31_compact_drag_held.png`
  - `32_compact_after_drag.png`
  - `33_compact_after_trim.png`
  - `34_compact_after_undo.png`
  - `35_compact_after_redo.png`
  - `36_compact_after_rapid.png`
  - `39_fast_rapid_edits.png`
  - `40_regression_final_layout.png`
