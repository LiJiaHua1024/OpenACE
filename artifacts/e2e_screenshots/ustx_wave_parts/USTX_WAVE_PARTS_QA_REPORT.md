# USTX wave-parts QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted with `OPENACE_CI_SYNTH_FIXTURE=1`, frontend rebuilt.

## Result

All requested USTX wave-part checks passed.

## Fixture and UI behavior

- Generated `/tmp/ustx_wave_fixture.wav` outside the repo: stereo 1.0s WAV.
- Seeded project `USTX Wave QA` / `project_871b2cc19a32` with an accompaniment clip:
  - start `480`
  - source offset `240`
  - duration `480`
  - fade-in `48`
  - fade-out `96`
  - gain `-6dB` (intentionally not exported because UWavePart has no gain field)
- Clicked the visible `USTX` export control in the Export panel.
- Browser download started successfully.
- Backend export endpoint returned HTTP 200 with a 1,061-byte `.ustx` file.
- UI remained healthy; arrangement and export panel stayed visible.
- No console errors or network failures occurred.

## Verified YAML wave part

Exactly one wave part was emitted:

```yaml
name: Hook
track_no: 1
position: 480
relative_path: ../../../../../../tmp/ustx_wave_fixture.wav
file_duration_ms: 1000.0
skip: 240
trim: 240
fadein: 48
fadeout: 96
```

Checks passed:

- schema keys are exactly `name`, `track_no`, `position`, `relative_path`, `file_duration_ms`, `skip`, `trim`, `fadein`, `fadeout`
- `relative_path` is relative, not absolute, and points to the fixture WAV
- measured file duration is `1000ms`
- fixed-480 tick-scaled `position=480`, `skip=240`, fades `48/96`
- full source duration is 960 ticks at 120 BPM/480 PPQ
- derived visible duration: `960 - 240 - 240 = 480`
- no `_openace_duration_ticks`, `gain`, or other invalid extra keys

## Evidence

- `01_workstation_before_ustx_click.png`
- `02_workstation_after_ustx_click.png`
- `ustx_wave_export.ustx`
- `clicked_download.ustx`
- `ustx_wave_results.json`
