# Playback Startup Hardening QA

Date: 2026-11-28  
Branch: `devin/1795696369-dynamic-expression`  
Project: `project_5bf625fb46bb` (audible imported source, static SVC clip, editable rendered vocal)  
Frontend: rebuilt production bundle `index-CfGHWf5c.js`, cache-busted URLs  
Backend: restarted current fixture backend on port 8787  
Implementation modified: no

## Verdict

Core playback startup hardening passes. Normal playback, repeated transport control, seek, loop, live edit rebuild, frozen-clock recovery, and suspended-start recovery all work.

One minor UX defect remains: after recovery succeeds, the previous actionable error banner remains visible even though playback is now working. It is click-dismissible. Severity: **P3**.

## Normal playback regression

Direct `AudioBufferSourceNode.start` instrumentation and transport readouts:

- Initial playback advanced to `1.2 / 00:01.24` after `1.32s` wall time.
- Three expected sources were scheduled: editable rendered vocal at approximately zero and the two nonzero arrangement clips at approximately `0.5s`.
- Pause/play-toggle stopped advancement exactly: `00:01.43` remained `00:01.43` after 500ms.
- Second playback advanced to `2.3 / 00:02.33`; source scheduling count increased from 3 to 6.
- Stop button reset transport exactly to `1.1 / 00:00.00`.
- Arrangement-ruler seek landed at `1.1 / 00:01.00`.
- Loop activation showed active loop UI. Sampled positions:

```text
1.34s → 1.72s → 0.09s → 0.45s → 0.85s → 1.21s → 1.58s → 1.97s
```

The drop from `1.72s` to `0.09s` proves loop wrap rather than linear playback. Scheduled-source count increased at loop boundaries (`9 → 12`, later `12 → 15`).

- Live edit rebuild regression: while playing, toggling mute on the source audio track increased scheduled-source count `15 → 20` and playback continued advancing to `00:01.52` with no error.

## Frozen AudioContext clock failure path

Simulation: runtime monkeypatch of `BaseAudioContext.prototype.currentTime` to a frozen constant `0` before pressing Play. This directly exercised the RAF frozen-clock detector.

Observed timeline:

```text
159ms: playing=true, transport 00:00.00, no error
749ms: playing=true, transport still 00:00.00, no error
866ms: playing=false, transport still 00:00.00, actionable error visible
```

Exact error:

```text
Audio output clock stalled; playback was stopped instead of pretending transport time was advancing. Press Play again to rebuild the audio engine.
```

Important facts:

- The UI did enter `playing` briefly after scheduling, but it did **not** remain in a silent fake-playing state.
- Transport did not fabricate progress; it stayed at zero while the clock was frozen.
- Detection latency was `866ms` in this run, close to the intended 750ms detector plus frame/scheduling overhead.
- Three sources had been scheduled before detection.
- After restoring the normal `currentTime` getter and pressing Play again, playback rebuilt successfully:
  - transport advanced to `1.2 / 00:01.15`
  - playing state was true
  - scheduled source count increased `3 → 6`

## Suspended/hung startup failure path

Simulation: runtime monkeypatch of `AudioContext.prototype.resume` to return a never-resolving promise before pressing Play.

Observed timeline:

- no `playing` state at any sample
- zero `AudioBufferSourceNode.start` calls
- transport stayed `00:00.00`
- actionable error first observed at `1651ms`

Exact error:

```text
Audio output could not start. Check the browser/system audio device, then press Play again.
```

This matches the intended 1500ms startup timeout plus click/polling overhead. The play button never entered a fake playing state.

After restoring normal `resume` and pressing Play again:

- playback advanced to `1.2 / 00:01.14`
- playing state was true
- three real sources were scheduled
- this also proves the `starting` flag did not stick; otherwise the recovery click would have been ignored

## Defect

### P3 — stale failure banner remains after successful recovery

After both successful recovery paths, playback was genuinely working, but the old error remained visible:

- frozen-clock recovery: working playback plus stale `Audio output clock stalled…` banner
- startup-timeout recovery: working playback plus stale `Audio output could not start…` banner

The banner is click-dismissible; clicking it removed it in verification. This does not break recovery, but it can momentarily contradict the recovered playing state. Consider clearing playback-startup errors on successful schedule/play or making the transient nature explicit.

## Console/network/visual health

- Console errors/warnings: zero in normal, frozen-clock, and startup-timeout scripts.
- Failed browser network responses: zero.
- Reviewed screenshots for normal playback, loop region, frozen error, startup error, and recovery; no layout overlap or dead controls found.

## Artifacts

- `playback_normal_results.json`
- `playback_frozen_clock_results.json`
- `playback_start_timeout_results.json`
- `error_dismissal.json`
- `01_normal_first_playback.png`
- `02_normal_pause_second_stop.png`
- `03_loop_playback.png`
- `04_live_edit_rebuild.png`
- `05_frozen_clock_actionable_error.png`
- `06_frozen_clock_recovery_playback.png`
- `07_start_timeout_actionable_error.png`
- `08_start_timeout_recovery_playback.png`
