# Final playback preload/prewarm validation

Exact viewport `1272x837`; rebuilt/cache-busted frontend; restarted fixture backend; implementation unchanged.

## Results

### Realistic workflow: fresh reload → harmless Shift first interaction → wait ~2.2s → first play

Passed.

- preload playback context created at `1491.6ms`, state `running`
- offline media decode completed once in `2.4ms`
- after Shift + ~2.2s idle, context was `running`, currentTime `0.534s`
- first play click → source start: `0.8ms`
- click → first playhead update: `24.6ms`
- clock lag after ~1.5s playback: `-0.0027s` (within `<20ms`; negative means audio clock marginally ahead of wall estimate)
- playback advanced continuously to `00:01.50`

### Warm restart and loop

Passed.

- warm click → source start: `0.3ms`
- click → playhead update: `27.5ms`
- clock lag: `-0.0041s`
- loop wrap observed: yes
- playback continued normally after wrap

### Direct play as first click, cold output path

Residual intrinsic startup remains, but is not worse.

- context construction: `1348.1ms`, state `running`
- click: `1500.9ms` (only `152.8ms` after construction)
- click → source start: `0.5ms`
- at 0.5s and 1.0s: no position advancement beyond initial state
- at `1.9908s` wall after source start, AudioContext elapsed only `0.16254s`
- therefore residual clock stall was about `1.83s`, consistent with the established intrinsic ~2s output startup cost

This cold direct-path probe used an explicit close plus eight seconds idle to avoid warm-device contamination. A direct click while the device was still warm was fast, so warm measurements alone would have been misleading.

### Console/network

- OpenACE console warnings/errors: none
- failed network responses: none

## Caveat

In the realistic workflow on this OpenACE localhost origin, the preload-created context was already `running` before the harmless Shift, so this test cannot prove how much the new first-keydown/pointerdown resume contributed versus the already-running prewarm. It does prove the complete user-visible strategy works in the real app environment.

## Artifacts

- `final_prewarm_validation.json`
- `direct_cold_probe.json`
- `final_prewarm_validation.log`
- `30_final_realistic_first_play.png`
- `31_final_warm_loop.png`
- `32_final_direct_first_play.png`
- `33_direct_cold_first_play.png`
- `/home/ubuntu/screencasts/playback-final-validation/playback-final-validation-edited.mp4`
