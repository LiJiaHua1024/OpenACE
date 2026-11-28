# Tempo-aware metronome fix retest

Date: 2026-11-28
Project: `project_c4bccc903fcc` / Global Workflow Audit
Browser: visible Chrome through Playwright/CDP
Instrumentation: patched `createOscillator`/`createGain`, `OscillatorNode.start/stop`, and `AudioNode.connect/disconnect` to distinguish audible scheduled clicks from canceled future `start()` calls. No UI-frame timing was used.

## Verdict

All required retest checks passed. The three previously reported metronome defects are fixed in audible behavior:

- no systematic 11.61 ms jump in the constant-tempo long run;
- seek/loop/rebuild produce **zero audible exact duplicate clicks** and no audible click interleaving/storm;
- canceled future oscillators remain as historical `start()` calls, as expected, but their stop/disconnect happens before their scheduled start time.

Residual observation, not counted as a failure of the stated retest criteria: loop-boundary intervals still stretch by **34.83 ms** at each loop restart. This is no longer accompanied by duplicates/interleaving and appears to be transport loop restart latency rather than a metronome scheduler collision, but it is visible in the click timing data.

## Quantitative results

### 1. Constant 120 BPM long run

Passed exactly.

- audible clicks captured: 15
- exact audible duplicates: 0
- intervals: every measured interval exactly `0.5 s`
- minimum interval: `500 ms`
- short intervals under 350 ms: 0
- max residual vs exact beat grid: **0.0 ms**
- frequency pattern: `1175, 1175, 1175, 1760` repeating for 4/4

The former systematic `+11.609977 ms` jump is gone.

### 2. Seek while playing

Passed.

After seeking to tick 960 during playback:

- audible clicks captured: 10
- exact audible duplicates: **0**
- post-seek audible clicks: 9
- post-seek intervals: exactly `0.5 s`
- short audible intervals under 350 ms: **0**
- canceled future historical `start()` noise: 5

The 5 historical starts were canceled before they could sound and are therefore implementation noise, not audible stale clicks.

### 3. Loop restart

Passed for duplicates/storms.

- audible clicks captured: 14
- exact audible duplicates: **0**
- short audible intervals under 350 ms: **0**
- canceled future historical `start()` noise: 8
- normal in-loop intervals: `0.5 s`
- loop boundary intervals: `0.53483 s` at each restart

The remaining `+34.83 ms` boundary stretch appears to be transport restart latency. It is not a duplicate click storm and does not interleave grids.

### 4. Mute-triggered playback rebuild

Passed exactly.

- audible clicks captured: 10
- exact audible duplicates: **0**
- intervals: every measured interval exactly `0.5 s`
- short audible intervals under 350 ms: **0**
- canceled future historical `start()` noise: 5

### 5. Toggle on during playback / toggle off

Passed.

- Enabling Metro during playback scheduled a batch of clicks without waiting for a transport restart. Measured first scheduling latency was approximately `183 ms` from the pre-click instrumentation timestamp; this includes browser/action measurement overhead, and multiple clicks were already scheduled by the first post-toggle snapshot.
- Focused toggle-off evidence: **0 audible clicks after cancellation**.
- Canceled future starts: 4.
- Toggle-off now cancels future lookahead immediately rather than allowing it to ring out; this is stricter than simple drain behavior and prevents stale clicks.
- Persistence remained correct:
  - reload off: `localStorage=off`, inactive button
  - reload on: `localStorage=on`, active button

### 6. Time signature/downbeats

Passed for 3/4.

Captured frequencies:

```text
1175, 1175, 1760, 1175, 1175, 1760, 1175, 1175, 1760
```

Thus the downbeat accent `1760 Hz` occurs every third beat; non-downbeats are `1175 Hz`. Intervals were exactly `0.5 s` at 120 BPM.

### 7. Piecewise tempo map

Passed exactly.

A tempo point was authored through the tempo lane UI at tick `1920`, `130 BPM`, step curve. Click intervals:

```text
0.5, 0.5, 0.5, 0.461538, 0.461538, 0.461538, ...
```

This matches:

- 120 BPM before the boundary: `0.5 s` per quarter note
- 130 BPM after the boundary: `60/130 = 0.461538 s` per quarter note

Residuals against the piecewise tempo model were `0.0 ms`. The temporary tempo point was removed afterward; backend positive tempo point count returned to `0`.

### 8. Export isolation

Passed.

Metro-on and Metro-off WAV exports were byte-identical:

```text
536d11231a8448a61f6f017c768bcfd99741bb9151ee4e374a0dfd470b39fc03
```

Files:

- `metronome_retest_export_on.wav`
- `metronome_retest_export_off.wav`

As in the prior QA, the fixture itself contains pre-existing periodic high-frequency source material, so byte equality is the meaningful isolation check.

### 9. Playback/Follow regression

Passed.

- Follow remained enabled.
- After seeking near the viewport edge and playing, the playhead remained visible and visually aligned across arrangement, tempo lane, and piano roll after paging.
- Position advanced from `3.1.1 / 00:04.02` to `3.4.2 / 00:05.74` during the regression check.

### 10. Console/network/project cleanup

Passed.

- console errors/warnings: none
- page errors: none
- network responses `>=400`: none
- time signature restored to `4/4`
- temporary positive tempo points removed
- track mute states restored to unmuted

## Artifacts

Primary evidence:

- `31_retest_webaudio_click_timing_analysis.png` — combined quantitative chart
- `metronome_retest_results.json` — full quantitative results
- `metronome_toggle_focus.json` — focused toggle cancellation evidence

Screenshots:

- `20_retest_baseline_playing.png`
- `21_retest_seek_clean_grid.png`
- `22_retest_loop_clean.png`
- `23_retest_rebuild_clean.png`
- `24_retest_toggle_off.png`
- `25_retest_reload_off.png`
- `26_retest_reload_on.png`
- `27_retest_time_signature_3_4.png`
- `28_retest_piecewise_tempo.png`
- `29_retest_follow_regression.png`
- `30_retest_final_overview.png`

Recording:

- `/home/ubuntu/screencasts/metronome-fix-retest/metronome-fix-retest-edited.mp4`
