# Live Track/Master Metering QA Report

## Scope and environment

- Focused browser QA of uncommitted live track/master metering in `frontend/src/App.tsx`, `TrackList.tsx`, `LevelMeter.tsx`, and styles.
- Real visible Chrome at exactly `1272×837`.
- Frontend rebuilt and cache-busted before testing.
- Backend unchanged; no backend restart was required.
- Fixture project: `project_d152f8c8ae7d`, retitled **Live Metering QA** for the test.
- Fixture contained two audible tracks (`Meter Audio A`, `Meter Audio B`) with 14 contiguous nonzero-audio clips each, plus one empty silent track (`Meter Silent`).
- WebAudio was instrumented non-invasively by wrapping `createBufferSource`, source `start`/`stop`, `decodeAudioData`, `createAnalyser`, and `getByteTimeDomainData`.
- No implementation files were modified.

## Verdict

**Metering behavior passed. No metering implementation defect was confirmed.**

One non-blocking pre-existing graph-hygiene observation is documented below: repeated reconstructions call `source.stop()` on already-ended or never-started sources. Those exceptions are caught internally, do not surface in the console, and did not cause double audio or metering failures.

## Evidence

### Playback starts and meters become nonzero

Passed.

At initial playback:

- created sources: `28`;
- started sources: `28`;
- `decodeAudioData` calls: `1`;
- analyser nodes: `3` — master plus two audible tracks;
- source start errors: `0`.

First nonzero DOM meter widths:

| Meter | Width |
|---|---:|
| Meter Audio A | 0.243164 |
| Meter Audio B | 0.243164 |
| Meter Silent | 0 |
| Master | 0.389582 |

Stable-playback quantitative means:

| Measurement | Master | Track A | Track B | Silent |
|---|---:|---:|---:|---:|
| analyser peak mean | 0.26875 | 0.13594 | 0.13594 | n/a |
| DOM width mean | 0.39995 | 0.25152 | 0.25152 | 0 |

The master peak was approximately twice either identical synchronized track peak, as expected. DOM meter ranges during stable playback showed animation rather than a static value:

- Track A/B: `0.23399–0.26344`;
- Master: `0.36777–0.41406`;
- Silent: always `0`.

No zero/reset samples occurred during stable playback despite continuous playhead re-renders.

### Solo semantics

Passed.

Soloing `Meter Audio B` produced only two active analysers: master and audible B.

- Track A DOM mean fell to `0.00021` while decaying to zero.
- Track B and master DOM means were both `0.23258`.
- Baseline master DOM mean had been `0.39995`, so master correctly dropped when the non-solo track was removed.
- Rebuild stop/create latency after the solo click: `188.0/188.2ms`.

### Volume reduction

Passed.

A real mouse click on the track A volume slider reduced backend volume to `0.05`.

| Measurement | Master | Track A | Track B |
|---|---:|---:|---:|
| analyser peak mean | 0.14323 | 0.01302 | 0.13542 |
| DOM width mean | 0.26344 | 0.04907 | 0.25340 |

Track A and master both decreased relative to baseline. Track B remained high. Rebuild stop/create latency: `153.1/153.5ms`.

### Mute

Passed.

Muting track A produced only master plus audible-B analysers.

- Track A DOM mean: `0.00011`, decaying to zero.
- Track B DOM mean: `0.23481`.
- Master DOM mean: `0.23481`, matching B-only output.
- Rebuild stop/create latency: `283.9/284.1ms`.

The mute latency was slightly above the other edits but still produced exactly one correct reconstruction with no error.

### Live reconstruction while playing

Passed.

A real arrangement clip drag changed:

- `meter_a2.start_ticks`: `1440 → 1560`

Reconstruction evidence:

| Count | Before | After |
|---|---:|---:|
| created sources | 140 | 168 |
| started sources | 119 | 137 |
| stopped sources | 112 | 140 |
| decode calls | 1 | 1 |

Timing from drag-start marker:

- first old-source stop: `237.7ms`;
- first new-source create: `237.9ms`.

Old sources stopped before new sources were created/started. Only 18 of the 28 newly created sources started because the scheduler creates nodes for clips entirely in the past but does not start them. Decode cache remained reused.

### Pause, restart, and stop decay

Passed.

Pause produced a smooth meter decay rather than an instantaneous visual reset:

- Master widths: `0.21561 → 0.11918 → 0.06588 → 0.03235 → ... → 0.00007` over about `1.12s`.

Restart returned meters to nonzero values.

Stop also decayed smoothly and reset position:

- Master widths: `0.20783 → 0.10204 → 0.04450 → ... → 0.00011` over about `1.06s`;
- readout after Stop: `00:00.00`.

### Layout, console, and network

Passed.

Final exact viewport measurements:

- viewport: `1272×837`;
- body `scrollWidth/clientWidth`: `1272/1272`;
- sidebar `scrollWidth/clientWidth`: `235/235`;
- transport `scrollWidth/clientWidth`: `1272/1272`;
- console messages: `0`;
- network failures: `0`;
- HTTP errors: `0`.

## Non-blocking graph-hygiene observation

Instrumentation counted `43` caught `source.stop()` exceptions by the end of the run. They appear consistent with the scheduler retaining already-ended sources and creating never-started nodes for clips entirely in the past, then calling `stop()` on every node during later reconstruction/transport cleanup.

Impact in this test:

- no uncaught console errors;
- no network errors;
- no duplicate overlapping old/new audio graph behavior detected;
- no metering malfunction;
- decode cache remained at one decode.

This is not confirmed as a metering regression, but it is concrete graph-hygiene evidence worth cleaning up separately.

## Artifacts

- Recording: `/home/ubuntu/screencasts/live-metering-qa/live-metering-qa-edited.mp4`
- Machine-readable results: `live_metering_results.json`
- Full raw instrumentation data: `live_metering_raw.json`
- Key screenshots:
  - `00_loaded_meters_zero.png`
  - `01_playback_meters_active.png`
  - `02_solo_b_metering.png`
  - `03_volume_a_down.png`
  - `04_mute_a.png`
  - `05_clip_drag_held.png`
  - `06_after_clip_drag.png`
  - `07_pause_decay_zero.png`
  - `08_restart_active.png`
  - `09_stop_decay_zero.png`
  - `10_final_layout.png`
