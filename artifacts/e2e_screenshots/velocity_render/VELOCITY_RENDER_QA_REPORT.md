# Note velocity render integration QA report

Date: 2025-11-27  
Surface: real visible Chrome, exact viewport `1272x837`  
Mode: `OPENACE_CI_SYNTH_FIXTURE=1`  
Build state: frontend rebuilt, backend restarted, browser cache-busted  
Implementation files: unchanged

## Verdict

All requested velocity-render integration checks passed. No implementation defect was confirmed.

One non-blocking playback observation: after pressing play, the transport stayed at `00:00.01` for about 2.1 seconds while decode/scheduling completed, then advanced normally (`00:00.21`, `00:00.58`, `00:00.94`). Playback does work, but startup latency is visible. This appears to be general playback scheduling latency rather than a velocity-DSP correctness failure.

## Exact evidence

### Fixture and velocity90 transparency

- Fixture: two equal Mandarin `啊` notes, same pitch `64`, same duration `960` ticks, adjacent at `0–960` and `960–1920`.
- Initial velocities: exactly `[90,90]`.
- Baseline velocity90 render completed with job message exactly `completed` — no Velocity post-processing label.
- Baseline central-span RMS values were identical:
  - note1 center `0.25–0.75s`: `0.23795942481196106`
  - note2 center `1.25–1.75s`: `0.23795942481196106`
  - ratio exactly `1.0`

### Velocity lane editing and stale behavior

Real velocity-lane drags produced exact backend velocities:

- first note: `127`
- second note: `30`

The drag remained smooth: recent frame intervals were consistently about `16.6–16.8ms`, approximately `60.006fps`.

After the velocity edit:

- stale badge count: `1`
- stale warning count: `1`

So velocity edits correctly invalidate the prior render.

### Final render and provenance

Final render job message:

`completed with Velocity post-processing`

Job card visible text included the same message. Diagnostic image exists and visibly includes:

`Note velocity post-render gain (not neural articulation conditioning)`

This is honest provenance: it does not pretend SoulX consumes velocity as neural articulation conditioning.

### Quantitative audio analysis

Rendered WAV:

- sample rate: `24000`
- duration: `2.5s`

Central-span RMS:

- baseline note1: `0.23795942481196106`
- baseline note2: `0.23795942481196106`
- velocity-render note1 velocity127: `0.47479143244285815`
- velocity-render note2 velocity30: `0.05885201416801799`

Ratios:

- baseline ratio: `1.0`
- final ratio: `8.067547715314637`
- normalized ratio: `8.067547715314637`
- theoretical expected ratio: `8.067548278657412`
- final ratio in dB: `18.134830854153666dB`

This is essentially exact: velocity127 is +6dB and velocity30 is about -12.135dB, yielding about 18.135dB separation.

### Click safety at exact note boundary

Boundary at 1.0s:

- final boundary ±10ms max first-difference: `0.00834202766418457`
- final boundary ±10ms 95th percentile: `0.003409862518310547`
- baseline boundary max first-difference: `0.0047607421875`
- interior final max first-difference: `0.01620471477508545`

The boundary maximum is below the interior maximum and far from a gross click discontinuity. The ±25ms waveform plot shows a smooth amplitude transition centered on the note boundary.

### Playback and browser health

- Play button entered playing state.
- Playhead advanced after decode/scheduling latency.
- Console errors/warnings: none.
- Failed network responses: none.

## Artifacts

- `velocity_render_results.json` — machine-readable exact results
- `velocity_render_run.log` — raw PASS output
- `velocity90_baseline.wav` — velocity90 transparent baseline render
- `velocity127_30_render.wav` — final velocity127/30 render
- `velocity_render_diagnostic.png` — final diagnostic with provenance
- `07_boundary_waveform_zoom.png` — ±25ms click-safety visualization
- `00_fixture_loaded.png` — initial fixture
- `02_velocity_drag_first_held.png` — first velocity drag held
- `03_velocity_drag_second_held.png` — second velocity drag held
- `04_velocity_edited_stale.png` — exact edited velocities and stale render state
- `05_velocity_render_job.png` — final render job state
- `06_velocity_job_card.png` — job card provenance
- `09_velocity_playback_recheck.png` — playback recheck
- `/home/ubuntu/screencasts/velocity-render-qa/velocity-render-qa-edited.mp4` — interaction recording
