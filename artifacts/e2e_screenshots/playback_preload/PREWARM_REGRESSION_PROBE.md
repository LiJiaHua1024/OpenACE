# Playback AudioContext prewarm regression probe

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Build: frontend rebuilt/cache-busted; fixture backend restarted  
Implementation files: unchanged

## Verdict

Early construction **does not reliably remove** the first-play clock stall for a fast first click. It only removes the stall if the pre-created playback `AudioContext` has already had roughly two seconds to warm before the user presses play.

The stall is therefore not caused by media decode. The measurements show an approximately two second `AudioContext` output-clock startup delay after context creation/startup in this Chrome/desktop audio environment. Moving construction earlier shifts that delay earlier; it does not eliminate the delay.

## Fast-click fresh reload probe

The playback context was pre-created during preload:

- creation time after navigation: `1484.1ms`
- state at creation: `running`
- currentTime at creation: `0`
- sample rate: `44100`
- media decode: one `OfflineAudioContext` decode, `1486.4–1489.1ms`
- no `resume()` call observed because state was already `running`
- autoplay/console warnings: none
- network failures: none

The play click occurred only `0.6509s` after context creation:

- click → source start: `1.1ms`
- click → first playhead update: `1359.6ms`
- source buffer was the exact offline-decoded buffer

Clock lag after click/source start:

| elapsed after click | wall minus AudioContext elapsed |
|---:|---:|
| 0.5124s | 0.5113s |
| 1.0013s | 1.0002s |
| 2.0207s | 1.3346s |
| 3.0245s | 1.3283s |

Interpretation: the clock remained frozen for the first ~1.33s after click. Because construction had already happened `0.6509s` before click, total construction-to-clock-start latency was still approximately `1.98s`.

## Long-prewarm fresh reload probe

When the same context was allowed to warm for `2.86s` before pressing play:

- pre-click context currentTime: `0.847528s`
- click → source start: `0.4ms`
- click → playhead update: `24.5ms`

Corrected clock lag using the initial source even across the loop boundary:

| elapsed after click | wall minus AudioContext elapsed |
|---:|---:|
| 0.5196s | 0.00836s |
| 1.0170s | 0.00653s |
| 2.0178s | 0.00887s |
| 3.0154s | 0.00802s |

Thus early construction can fully remove the user-visible stall, but only if enough warmup time has elapsed before play.

## Minimal page-side experiment

A minimal visible HTML page created silent-output contexts. On a fresh localhost origin with no prior media engagement:

- context created immediately at load: state `suspended`, currentTime `0`; Chrome emitted the standard autoplay warning
- context created at click: state `running`, currentTime `0`
- click-created context reached 20ms of clock time at age `2.0086s`
- reached 500ms of clock time at age `2.492s`
- reached 1s of clock time at age `2.975s`

This independently confirms that a click-created running `AudioContext` takes about two seconds before its clock starts advancing in this environment.

The load-created minimal context could not be used as a direct warm comparison on the fresh port because autoplay policy kept it suspended. That is itself an important caveat: in browsers/profiles where autoplay policy suspends pre-created contexts, pre-creating without resuming cannot warm the output path. In the OpenACE app origin used here, the context happened to be created in `running` state and no autoplay warning appeared.

## Conclusion

- Decode preloading works and is not the bottleneck.
- Early construction helps only by moving an intrinsic ~2s audio-output clock startup earlier.
- Fast first playback still has a residual stall proportional to how little warmup time elapsed.
- After approximately two seconds of warmup, playback is tightly synchronized with sub-10ms clock lag.
- The prewarm change is therefore a partial improvement, not a complete fix for immediate first-play startup.

## Artifacts

- `prewarm_probe_results.json` — fast-click fresh reload exact data
- `prewarm_longwait_results.json` — long-prewarm exact data
- `minimal_audioctx_experiment.json` — minimal AudioContext experiment
- `prewarm_probe_run.log`
- `prewarm_longwait_run.log`
- `10_prewarm_first_play_1s.png`
- `11_prewarm_first_play_3s.png`
- `12_prewarm_longwait_3s.png`
- `13_minimal_audioctx_experiment.png`
- `/home/ubuntu/screencasts/playback-prewarm-probe/playback-prewarm-probe-edited.mp4`
