# Module-evaluation playback AudioContext prewarm final probe

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Build: rebuilt/cache-busted frontend, restarted fixture backend  
Implementation files: unchanged

## Verdict

Fast first playback is **not fixed**. Moving playback `AudioContext` prewarm to module evaluation time makes construction happen very early, but in this browser the context is then created in `suspended` state and therefore does not warm the output path at all. `resume()` is correctly attempted at play time, but the clock still takes about two seconds to start after that resume.

Immediate warm restart and loop remain functional once the context has actually warmed.

## Fast fresh-reload controlled probe

Exact timing:

- navigation-to-context-construction: `172.7ms`
- construction-to-click: `1.899s`
- state at construction: `suspended`
- currentTime at construction: `0`
- resume at play: yes, at `2072.1ms`, stateBefore `suspended`
- click → source start: `1.0ms`
- click → first playhead text update: `24.0ms`

Clock lag after click/source start:

| elapsed after click | wall minus AudioContext elapsed |
|---:|---:|
| 0.5054s | 0.4928s |
| 1.0132s | 1.0007s |
| 2.0187s | 1.9713s |
| 3.0321s | 1.9746s |

The tiny first playhead movement at 24ms is misleading: the clock moved one centisecond and then froze. Actual playback position was still only about `00:00.03` at two seconds after clicking, then began advancing.

Autoplay warnings in the OpenACE app console: none. Network failures: none. Despite the absence of a warning, the context factually remained `suspended` until play.

## Immediate warm restart / loop

In an integrated same-reload run:

- first play source start: `0.5ms`, but after 2.6s wall time playback had only reached about `00:00.61`, confirming the first-play stall
- immediate second start source latency: `0.3ms`
- immediate second start playhead latency: `41.9ms`
- second start context state: `running`
- loop active: yes
- loop wrap observed: yes
- second-run positions progressed continuously and wrapped; tail after wrap included `00:01.09|1.3.1`

Thus warm start/loop are still okay when restart happens immediately after the first warm playback.

Caveat from an additional probe: after a long idle period, playback can again exhibit startup delay. That is separate environmental audio-output behavior and was not counted as the immediate warm-start result.

## Conclusion

Module-evaluation prewarm is not an effective fix in the tested browser because early construction happens before user activation and produces a suspended context. It neither warms the audio hardware nor avoids the ~2s clock startup after play-time resume. The approach only helps when the context is created late enough/under conditions where it is already `running` and has approximately two seconds to warm before play.

## Artifacts

- `moduleprewarm_probe_results.json` — fast controlled probe exact data
- `moduleprewarm_integrated.json` — integrated first/warm/loop exact data
- `moduleprewarm_warm_loop.json` — long-idle warm caveat probe
- `moduleprewarm_probe_run.log`
- `20_moduleprewarm_first_play_1s.png`
- `21_moduleprewarm_first_play_3s.png`
- `23_moduleprewarm_immediate_warm_loop.png`
- `/home/ubuntu/screencasts/playback-module-prewarm-final/playback-module-prewarm-final-edited.mp4`
