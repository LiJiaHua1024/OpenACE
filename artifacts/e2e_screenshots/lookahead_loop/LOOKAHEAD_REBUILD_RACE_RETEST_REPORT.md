# Lookahead Loop Mute/Rebuild Race Retest

Date: 2025-11-28
Build: uncommitted fix deferring playback edit rebuilds in 80 ms steps while loop lookahead commit is pending or boundary is within 550 ms
Browser: visible Chrome through Playwright/CDP
Backend: restarted fixture backend; cache-busted production UI
Instrumentation: direct `OscillatorNode` and `AudioBufferSourceNode` `start/stop/disconnect` instrumentation. Canceled future `start()` calls were counted as audible only when not stopped/disconnected before their scheduled start.

## Verdict

The intermittent mute/rebuild race previously reported **did not reproduce in 5/5 timed attempts**. Every attempt preserved the exact 500 ms metronome grid, retained the boundary downbeat, completed the playback rebuild after the exact loop commit, and produced no duplicates/storms or persistent phase shift.

No new defects were found in the focused retest.

## Boundary mute/rebuild attempts

| attempt | mute lead before boundary | boundary downbeat | first post-boundary rebuild-source creation | all intervals exact 500 ms | max grid residual | duplicates |
|---:|---:|---|---:|---|---:|---:|
| 1 | 351.38 ms | yes, 1760 Hz | +159.46 ms | yes | ~0 ms | 0 |
| 2 | 351.38 ms | yes, 1760 Hz | +89.80 ms | yes | 0 ms | 0 |
| 3 | 351.38 ms | yes, 1760 Hz | +147.85 ms | yes | 0 ms | 0 |
| 4 | 328.16 ms | yes, 1760 Hz | +43.36 ms | yes | ~0 ms | 0 |
| 5 | 351.38 ms | yes, 1760 Hz | +182.68 ms | yes | 0 ms | 0 |

Additional observations:

- minimum/maximum audible click interval in every attempt: `500.0 ms / 500.0 ms`
- intervals under 350 ms: 0 in every attempt
- exact same-time audible duplicates: 0 in every attempt
- playback remained active after every rebuild (`playing_button` still pause)
- historical canceled future oscillator/source `start()` calls remain as implementation noise, but all were stopped/disconnected before sounding

## Normal mid-loop mute regression

A mute edit was issued about `1164.08 ms` before the loop boundary, outside the 550 ms deferral window.

- first post-mute playback-source creation: **+371.52 ms**
- this was before the boundary-minus-550-ms deferral threshold, so the edit was not endlessly deferred
- playback remained active
- observed click intervals were exactly `500 ms`
- no duplicates/storms

## Quick regressions

### Baseline exact one-bar loop

- 17 audible clicks
- all intervals exactly `500 ms`
- zero exact audible duplicates and zero sub-350 ms intervals
- three reached boundaries validated
- at each boundary: 7 crossing outgoing sources, maximum scheduled stop deviation `0.0 ms`, replacement loop-start sources exact, no early/late/overrun sources

### Seek while pending

- invalidated pending sources: 14
- uncancelled/resurrected pending sources: 0
- post-seek audible click intervals: all exactly `500 ms`
- no duplicates or interleaving

### Disable loop while pending

- pending sources observed: 14
- uncancelled future sources after disable: 0
- playback continued past the old boundary without jumping back
- all audible click intervals exactly `500 ms`

## Console/network

Across the repeated rebuild test and quick regressions:

- console errors/warnings: 0
- page errors: 0
- failed network responses: 0

## Cleanup

Final project state was restored to:

- loop range `0–1920`, enabled
- empty tempo map
- 4/4 time signature
- playhead stopped at zero

## Evidence

- `34_rebuild_retest_analysis.png` — quantitative five-attempt chart
- `20_rebuild_retest_attempt1.png` and `20_rebuild_retest_attempt5.png` — boundary rebuild screenshots
- `21_rebuild_retest_final.png` — final repeated-attempt state
- `22_midloop_mute_prompt_rebuild.png` — normal mid-loop rebuild regression
- `30_retest_baseline_loop.png` — baseline loop regression
- `31_retest_seek_pending.png` — seek-pending regression
- `32_retest_disable_pending.png` — disable-pending regression
- `33_retest_final_state.png` — final cleaned state
- raw JSON results/snapshots are in this directory
