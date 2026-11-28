# Playback cache/sample-accurate timing QA

Recording: `/home/ubuntu/screencasts/playback-cache-qa/playback-cache-qa-edited.mp4`

## Verdict

Passed on the authoritative fresh cache-busted page. No implementation defect confirmed.

## Evidence

- Fixture project had valid audio clips with trim offset `480` ticks, fade in/out `240` ticks, and overlap for crossfade scheduling.
- Playback started successfully and playhead advanced continuously.
- Timing samples over 2.3s wall time:
  - 0.453s wall → 00:00.43 playhead
  - 0.912s → 00:00.89
  - 1.370s → 00:01.35
  - 1.834s → 00:01.81
  - 2.294s → 00:02.29
- Maximum observed wall/playhead difference in samples: about 0.04s.
- Instrumented fresh cache run:
  - `/uploads/svclyrics_words.wav` fetch count stayed `1` across repeated stop/start cycles.
  - `decodeAudioData` count stayed `1`.
  - `AudioContext` construction count stayed `1`.
- No console errors or network failures.
- Layout at `1272×837`: no body overflow.

Harness note: an initial measurement accidentally reused an already-open stale page and showed refetch/recreate counts. A fresh cache-busted page with the rebuilt bundle was then measured and is authoritative. This matches the saved cache-busting skill.

Observable limitation: fade/crossfade scheduling was verified only to the extent browser-observable without audio metering: trimmed/overlapping/faded clips loaded and playback ran without errors; no audible gain contour was quantitatively measured.

Artifacts:
- `playback_cache_results.json`
- `playback_cache_instrumented_fresh.json`
- `03_instrumented_reuse_fresh.png`

No implementation files modified.
