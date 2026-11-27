# USTX contract QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted with `OPENACE_CI_SYNTH_FIXTURE=1`, frontend rebuilt.

## Result

All requested USTX export checks passed.

## Verified UI behavior

- Created project `USTX Contract QA` / `project_0eef7b1b6db1` with two vocal notes, pitch automation, dynamic automation, vibrato, phonemes, volume/pan/color.
- Clicked the visible `USTX` control in the Export panel.
- Browser download started successfully.
- Backend export endpoint returned HTTP 200 with a 1,746-byte `.ustx` file.
- UI remained healthy after export: project title remained `USTX Contract QA`; piano roll remained present.
- No console errors or network failures occurred.

## Verified file contract

- `ustx_version: '0.10'` present as parsed value `0.10`.
- No top-level `resolution`.
- Exact note key order:
  `position, duration, tone, lyric, pitch, vibrato, tuning, phoneme_expressions, phoneme_overrides`
- Custom pitch point correctly converted: `{x: 12.5, y: 3.0, shape: io}`.
- Note without user pitch curve has the mandatory two default points.
- Vibrato conversion verified: length `75`, period `250`, depth `40`.
- Phoneme overrides contain index/phoneme only, no wrong millisecond offsets.
- Curves use `xs`/`ys`:
  - `dyn`: `xs=[0,480]`, `ys=[0,60]`
  - `pitd`: `xs=[0,480]`, `ys=[-25,50]`
- No curve-level `x`/`y` arrays.
- Track conversions verified:
  - volume `-6.021`
  - pan `25.0`
  - nearest color `Purple`
  - phonemizer `OpenUtau.Core.DefaultPhonemizer`
- Beat-aligned voice-part duration: `960`.

## Evidence

- `01_workstation_before_ustx_click.png`
- `02_workstation_after_ustx_click.png`
- `evidence_export_panel_crop.png`
- `ustx_contract_export.ustx`
- `clicked_download.ustx`
- `ustx_contract_results.json`
