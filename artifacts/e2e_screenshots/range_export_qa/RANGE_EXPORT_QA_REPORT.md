# Musical Range Export QA

Date: 2026-11-28  
Branch: `devin/1795696369-dynamic-expression`  
Project: `project_a67d2d8bc025` (`SVC Editable Score QA Copy`)  
Frontend: rebuilt production bundle `index-DXkkazWJ.js`, cache-busted URL  
Backend: restarted current fixture backend  
Implementation modified: no

## Verdict

Core musical range export passes. A valid nonzero saved loop at ticks `960–1920` in a 90 BPM project exports exact tempo-map-converted durations, range waveform content matches the corresponding full-export slice almost exactly, stems and CLI outputs are correct, invalid API ranges are actionable 422s, and MP4/interchange range misuse is rejected.

One minor UI roughness remains: when switching from a loop-enabled project to a project without a saved loop while the Range selector is already set to “Playback loop range”, the disabled loop option remains displayed as the selected value alongside the warning. Export behavior is still safe/full-length, and choosing Full works; severity **P4 cosmetic**.

## Browser/UI evidence

- BPM changed through the visible transport control to `90`.
- Loop range created through a real arrangement-ruler drag and persisted as `{start: 960, end: 1920, enabled: true}`.
- Export Range control was visible and loop-enabled.
- Loop hint exact: `Audio/stem exports use loop ticks 960–1920; project interchange/video formats remain full-length.`
- Full mode hrefs had no range query.
- Loop mode hrefs were correct:
  - WAV/MP3/FLAC/OGG/STEMS included `?start_ticks=960&end_ticks=1920`
  - MP4/MID/LRC/USTX/SVP/VPR had no range query
- In a project without a saved loop, the loop option had a disabled attribute, warning was visible, and WAV href was full-length.
- Console errors/warnings: zero. Failed browser network responses: zero.

## Exact audio results

At 90 BPM with PPQ 480:

- ticks `960–1920` = exactly `1.3333333333333333s`
- expected samples at 48kHz: `64000`

Measured UI downloads:

- range WAV: exactly `64000` frames / `1.333333s`
- range FLAC: exactly `1.333333s`
- full WAV regression: `192500` frames / `4.010417s`, nonzero
- range/full boundary content comparison:
  - full-export slice at ticks 960–1920 also exactly `64000` frames
  - normalized correlation: `0.999999999999954`
  - relative residual after best scale: `3.03e-7`
  - best scale range/full-slice: `0.998849`
- stems ZIP:
  - manifest `range_ticks` exactly `{start: 960, end: 1920}`
  - all three audible stems exactly `64000` frames / `1.333333s`
  - peaks nonzero: approximately `0.198`, `0.225`, `0.198`

Supplemental trailing-silence test:

- API range `960–4800` produced exactly `256000` frames / `5.333333s`
- final 0.5s peak exactly `0.0`, proving trailing silence padding beyond the source mix

## API validation

All invalid cases returned actionable HTTP 422, not 500:

- missing end: `export range requires both start_ticks and end_ticks`
- missing start: `export range requires both start_ticks and end_ticks`
- reversed range: `export range must satisfy 0 <= start_ticks < end_ticks`
- negative start: `export range must satisfy 0 <= start_ticks < end_ticks`
- MP4 with range: `range export is currently supported for audio masters/stems, not mp4`
- MIDI with range: `range export is currently supported for audio masters/stems, not mid`

## CLI verification

- `openace-tool export project_a67d2d8bc025 wav ... --start-ticks 960 --end-ticks 1920` succeeded.
- CLI WAV exactly `64000` frames / `1.333333s`.
- `openace-tool export ... stems ...` succeeded.
- CLI stems manifest exact `range_ticks`; all stem durations exactly `1.333333s`.

## Minor defect / roughness

### P4 — stale selected loop mode can display on a no-loop project

When the Range selector is already set to “Playback loop range” and the user switches to a project with no valid loop, the selector still displays “Playback loop range” even though that option is disabled. The UI does show `No valid playback loop range is saved in this project.`, hrefs correctly remain full-length, and selecting Full works. This is cosmetic/state roughness rather than incorrect exporting.

## Artifacts

- `01_loop_range_bpm90_ui.png`
- `02_export_range_control_loop_available.png`
- `03_export_range_loop_hrefs.png`
- `04_export_full_mode.png`
- `05_export_range_control_loop_visible.png`
- `06_export_range_loop_disabled_no_loop_project.png`
- `range_export_browser_results.json`
- `range_export_ui_visual_results.json`
- `audio_analysis.json`
- `api_invalid_range_results.json`
- `cli_extended_analysis.json`
- `downloads/ui_range.wav`
- `downloads/ui_range.flac`
- `downloads/ui_range.zip`
- `downloads/ui_full.wav`
- `downloads/cli_range.wav`
- `downloads/cli_range.zip`
