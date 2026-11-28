# Live Base-Tempo/Meter Playback Rebuild QA

Date: 2025-11-28
Build: uncommitted live base-tempo/meter playback rebuild fix in `/home/ubuntu/repos/OpenACE`
Browser: visible Chrome driven through Playwright/CDP
Backend: fixture backend restarted; cache-busted production UI
Instrumentation: direct `OscillatorNode` and `AudioBufferSourceNode` `start/stop/disconnect` instrumentation. Canceled future `start()` calls were counted as audible only if not stopped/disconnected before their scheduled start.

## Verdict

The live transport rebuild fix passed the focused quantitative QA. Base BPM edits and meter edits triggered automatic continuous rebuilds without pressing play again, steady-state metronome spacing was exact, position advanced monotonically with no backward/forward tick jump, and no click/source storms were observed.

No defects were found in this focused pass.

## 1. Live base BPM edits: 120 → 90 → 130

Setup: empty `tempo_map`, base BPM 120, 4/4, loop off, metronome on.

### 120 → 90

- BPM edited live through the transport BPM input; playback was **not** manually restarted.
- automatic rebuild-source creation latency: **359.91 ms**
- post-edit 90 BPM click group:
  - audible clicks: 3 in the limited observation window
  - intervals: `0.666667, 0.666667`
  - expected 90 BPM beat: `0.666667 s`
- one transition interval into the rebuilt grid: `0.620998 s`
- no exact duplicates and no sub-350 ms intervals

### 90 → 130

- automatic rebuild-source creation latency: **278.64 ms**
- post-edit 130 BPM click group:
  - audible clicks: 10
  - all 9 intervals exactly `0.461538 s`
  - expected 130 BPM beat: `0.461538 s`
- one transition interval into the rebuilt grid: `0.502508 s`
- no exact duplicates and no sub-350 ms intervals

### Source-generation behavior

- 90 BPM rebuild: one creation-time cluster, 13 uncancelled replacement sources
- 130 BPM rebuild: three close creation timestamps spanning only `11.61 ms`, consistent with asynchronous graph construction batching rather than a repeated rebuild storm
- no endlessly repeating rebuild generations observed
- playback button remained in pause/playing state throughout

### Position continuity

Sampled bar.beat.subdivision position was monotonic across both edits and rebuild windows:

- before 90 edit: `1.3.2`
- just after 90 input: `1.4.1`
- after 90 rebuild window: `2.1.1`
- 90 stable: `2.2.3`
- just after 130 input: `2.3.1`
- after 130 rebuild window: `2.4.2`
- 130 stable: `3.4.2`

All sampled tick deltas were positive; no backward jump or large forward inverse-conversion jump was observed. The wall-clock time readout changed as expected because the same tick position maps differently under a new BPM; the musical tick position itself did not jump backward.

## 2. Live meter edit: 4/4 → 3/4

Setup: base BPM 120, empty `tempo_map`, loop off, metronome on.

- meter edited live through the transport select; playback was **not** manually restarted.
- automatic rebuild latency: **290.25 ms**
- post-edit beat intervals: all exactly `500 ms`
- post-edit accent times:
  - `52.679092970521545`
  - `54.179092970521545`
  - `55.679092970521545`
- accent intervals: exactly `1.5 s, 1.5 s`
- post-edit frequency pattern: `1175, 1175, 1760` repeating
- exact audible duplicate clicks: 0
- meter restored to 4/4 after the test

## 3. Quick regressions

### Loop

- 17 audible clicks
- all intervals exactly `500 ms`
- zero duplicates/sub-350 ms intervals
- three reached loop boundaries validated
- each boundary: 7 crossing sources, max scheduled stop deviation `0.0 ms`, exact replacement starts, no audible overruns

### Seek while loop lookahead pending

- pending sources observed before seek: 3
- uncancelled/resurrected pending sources: 0
- post-seek click intervals: all exactly `500 ms`
- no interleaving or duplicates

### Follow

- seek before playback: `3.1.1 / 00:04.02`
- during playback after Follow paging: `3.4.2 / 00:05.74`
- red playhead remained visible and aligned across arrangement, tempo lane, and piano roll

## 4. Console/network

All formal phases had:

- console errors/warnings: 0
- page errors: 0
- failed network responses: 0

## 5. Cleanup

Final state restored:

- base BPM 120
- empty `tempo_map`
- 4/4 time signature
- loop `0–1920` enabled
- playback stopped at zero

## Evidence index

- `10_live_tempo_rebuild_analysis.png` — quantitative summary chart
- `00_live_tempo_130_playing.png` — live 130 BPM playback after both tempo edits
- `01_live_meter_3_4_playing.png` — live 3/4 playback after meter edit
- `02_loop_regression.png` — loop regression
- `03_seek_regression.png` — seek regression
- `04_follow_regression.png` — Follow regression
- `05_final_state.png` — cleaned final state
- raw JSON results/snapshots are in this directory
