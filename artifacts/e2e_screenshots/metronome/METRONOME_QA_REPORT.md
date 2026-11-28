# Tempo-aware metronome adversarial QA

Date: 2026-11-28
Project: `project_c4bccc903fcc` / Global Workflow Audit
Browser: visible Chrome through Playwright/CDP
Instrumentation: `OscillatorNode.prototype.start` capture of exact WebAudio start times/frequencies; no UI-frame timing used

## Verdict

The feature is **not ready to merge**. Preference persistence, toggle-off scheduling, downbeat frequency patterns, piecewise tempo spacing, export isolation, playback/Follow regression, and console/network cleanliness passed. However, WebAudio instrumentation exposed three precise timing/restart defects:

1. **Constant playback phase jump:** after the initially scheduled lookahead batch, all later clicks are exactly **11.609977 ms late** at 120 BPM.
2. **Seek restart contamination:** seeking while playing leaves previously scheduled oscillators audible; old and new click grids interleave at intervals as small as **164 ms** instead of 500 ms.
3. **Loop/rebuild duplicate clicks:** loop and playback-graph rebuild restarts schedule exact duplicate oscillators at identical audio-clock times.

## Quantitative evidence

### Constant 120 BPM baseline

Expected beat spacing at 120 BPM: `0.5 s`.

Captured frequency pattern was correct for 4/4:

```text
1175, 1175, 1175, 1760, 1175, 1175, 1175, 1760, ...
```

The first four clicks were exactly on the beat, but beginning with click 5 every click was `+11.609977 ms`:

```text
click 1: +0.000 ms
click 2: +0.000 ms
click 3: +0.000 ms
click 4: +0.000 ms (downbeat 1760 Hz)
click 5+: +11.609977 ms consistently
```

Intervals:

```text
0.5, 0.5, 0.5, 0.51161, 0.5, 0.5, ...
```

`0.011609977324 s` is exactly `512 / 44100`, suggesting a fixed four-render-quantum clock discontinuity. Likely implementation cause: `schedulePlayback()` calls `scheduleMetronome()` before asynchronous graph construction finishes, then `playToggle()` overwrites `playback.current.startContextTime` after `await schedulePlayback(...)`; the first batch uses the old clock origin and later lookahead passes use the mutated one.

### Toggle off and persistence

Passed:

- Toggling Metro off during playback produced **0 new oscillator starts** after the already-scheduled 2.25 second lookahead horizon had drained.
- Reload with Metro off: `localStorage=off`, inactive button.
- Reload with Metro on: `localStorage=on`, active button.

Already-scheduled oscillators within the lookahead window still sound after toggle-off because they cannot be cancelled; this is understandable for toggle-off, but the same missing cancellation becomes a defect on seek/loop/rebuild.

### Seek while playing

A seek to tick 960 during playback produced interleaved old/new click grids. Chronological intervals included:

```text
0.335918, 0.164082, 0.335918, 0.164082, ...
```

Summary:

- captured click oscillators: 15
- exact same-time duplicates: 0
- intervals below 350 ms: **9**
- minimum interval: **164.08 ms**

Expected after restart: a single clean 500 ms click grid. Instead, already-scheduled old-transport clicks remained audible because `clearMetronome()` clears only the interval/dedupe set; it retains no oscillator references and cannot cancel already-scheduled oscillator starts.

### Loop restart

Looping bar 1 (`0–1920`) produced exact duplicate oscillators at identical audio-clock times:

- captured click oscillators: 21
- exact same-time/same-frequency duplicates: **8**
- intervals below 350 ms: **8**
- minimum interval: **0 ms**

Representative interval sequence:

```text
0.5, 0.5, 0.5, 0.51161, 0, 0.5, 0, 0.5, 0, ...
```

This means multiple click oscillators are literally scheduled for the same musical beat after loop restart.

### Playback graph rebuild

Toggling mute on a track during playback forced the existing playback rebuild path. Results:

- captured click oscillators: 16
- exact same-time/same-frequency duplicates: **3**
- intervals below 350 ms: **5**
- minimum interval: **0 ms**

This confirms the same missing-cancellation defect applies to rebuild restarts, not only manual loop/seek paths.

### Time signature/downbeats

Passed for 3/4. Captured frequencies:

```text
1175, 1175, 1760, 1175, 1175, 1760, 1175, 1175, 1760
```

Thus downbeat accent frequency `1760 Hz` occurred every third beat as expected; non-downbeats were `1175 Hz`.

### Piecewise tempo map

A tempo point was authored through the tempo lane UI at exact tick `1920`, `130 BPM`, step curve, then playback was measured.

Intervals:

```text
0.5, 0.5, 0.5, 0.473148, 0.461538, 0.461538, ...
```

Interpretation:

- `0.5 s` spacing before the tempo boundary is correct for 120 BPM.
- steady `0.461538 s` spacing after the boundary is correct for 130 BPM.
- the first post-boundary interval is inflated by the same `11.609977 ms` phase discontinuity (`0.461538 + 0.011610 = 0.473148`), so piecewise tempo math itself appears correct but is contaminated by the playback clock-origin defect.

The tempo point was removed afterward; backend positive tempo point count returned to `0`.

### Export isolation

Passed with an important fixture caveat.

- WAV exported while Metro was enabled.
- WAV exported again while Metro was disabled.
- Files were **byte-identical**:
  - SHA-256 both: `536d11231a8448a61f6f017c768bcfd99741bb9151ee4e374a0dfd470b39fc03`

The current fixture contains `mixed_source.wav`, which already has periodic high-frequency click-like source material and predates the metronome work. Therefore raw spectral clicks in this particular export are not evidence of metronome leakage. The byte-identical Metro-on/Metro-off comparison is the meaningful isolation evidence.

### Playback/Follow regression

Passed as a focused regression:

- Follow remained enabled.
- After seeking near the viewport edge and starting playback, the playhead remained visible and visually aligned across arrangement, tempo lane, and piano roll after paging.
- No audio-clock console errors or render-graph rebuild loops were observed.

### Console/network

Passed in the instrumented run:

- console errors/warnings: none
- page errors: none
- network responses `>=400`: none

## Artifacts

- `metronome_results.json` — full quantitative oscillator/event data
- `10_webaudio_click_timing_analysis.png` — visual analysis of residuals, seek interleaving, loop duplicates, and tempo-transition intervals
- `01_metronome_playing.png`
- `02_metronome_toggled_off.png`
- `03_reload_persists_off.png`
- `04_reload_persists_on.png`
- `05_seek_restart_click_overlap.png`
- `06_loop_restart_duplicate_clicks.png`
- `07_time_signature_3_4.png`
- `08_piecewise_tempo_map.png`
- `09_final_overview.png`
- `11_export_wav_control.png`
- `12_follow_regression_after_paging.png`
- `13_rebuild_duplicate_clicks.png`
- `metronome_export.wav` / `metronome_export_off.wav`

## Recommended fixes

1. Establish the playback audio-clock origin exactly once before any metronome scheduling, or pass the intended origin into `scheduleMetronome`; do not mutate `playback.current.startContextTime` after `scheduleMetronome()` has already scheduled clicks.
2. Track scheduled metronome oscillators and cancel/stop future oscillators in `clearMetronome()`. Since `OscillatorNode.stop()` can be called before start, retain references until their stop time and call `stop(0)` or disconnect them when transport restarts.
3. Ensure seek, loop, and rebuild paths all share the same cancellation semantics before rescheduling.
4. Add an automated browser-level regression that instruments `OscillatorNode.prototype.start` and rejects duplicate exact start times or non-beat interleaving after transport restarts.
