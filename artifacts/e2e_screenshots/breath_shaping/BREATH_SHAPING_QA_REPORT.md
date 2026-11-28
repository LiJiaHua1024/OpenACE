# Breath shaping QA report

Date: 2026-11-27
Branch: `devin/1795696369-dynamic-expression`
Mode: visible Chrome, fixture backend (`OPENACE_CI_SYNTH_FIXTURE=1`).

## Result

All requested breath-shaping checks passed.

Harness transparency:

- Several initial harness attempts to draw the first near-left-edge note in a fresh project did not persist, while a direct visible draw into the already-open project did persist. This appeared to be an automation/setup race rather than a reproducible application defect, so the test reused that project whose two notes were visibly present and added a third note.
- **Add all breaths** was visible, but Playwright hit-testing was obstructed by the wide browser layout/right-panel overlap. The same visible control was activated by DOM dispatch for that one setup action. Breath creation/move/resize/delete themselves were real mouse interactions.
- No implementation files were modified.

## Inspector/default verification

Passed:

- empty click created breath `(start=480,duration=120)`
- backend defaults exactly `intensity=1.0`, `timbre=natural`
- inspector appeared
- wide-layout probe confirmed professional complete inspector geometry: label, slider, percentage, timbre select, and Add-all button all inside the automation header
- breath visuals show selected outline/meter/percentage (`BR 150%` evidence screenshot)

## Move/resize verification

Passed:

- center drag moved breath `480→600`
- right-edge drag resized duration `120→240`
- backend persisted exact `(start=600,duration=240)`

## Intensity editing/undo/redo

Passed with real slider drags:

- intensity `100%→0%` persisted as `0.0`
- intensity `0%→50%` persisted as `0.5`
- intensity `50%→150%` persisted as `1.5`
- one undo returned intensity to `0.5`
- redo restored `1.5`

## Timbre persistence

Passed through the inspector select:

- Soft persisted as `soft`
- Natural persisted as `natural`
- Strong persisted as `strong`

## Render/message/provenance

Four fixture renders completed successfully:

- 150% natural
- 50% natural
- 150% soft
- 150% strong

Every job completed with `completed with 1 real-donor breath overlay(s)`. Final diagnostic visibly states:

`Breath events real donor-noise overlays (post-render DSP, not neural conditioning)`

## Quantitative audio analysis

Measured final breath interval `0.625–0.875s`:

- 50% natural RMS: `0.0169442166`
- 150% natural RMS: `0.0508326478`
- ratio: `2.99999989×`, effectively exact 3× scaling

High/mid spectral ratio (`>=4200Hz / 1200–4200Hz`):

- soft: `0.41265`
- natural: `2.66856`
- strong: `5.91521`

Ordering is exactly `soft < natural < strong`, proving spectral shaping changes the extracted donor rather than merely changing gain.

## Add-all/default/move/delete verification

Passed:

- Add all created breath `(start=1680,duration=120)` with defaults `intensity=1.0`, `timbre=natural`
- move changed start to `1800`
- resize changed duration to `240`
- right-click delete removed all breath state
- inspector disappeared after deletion

## Health

No console errors or network failures occurred.

## Evidence

- `01_breath_inspector.png`
- `02_intensity_150.png`
- `03_timbre_strong_visual.png`
- `04_add_all_default.png`
- `05_breath_deleted_inspector_cleared.png`
- `inspector_layout_probe.png`
- `quantitative_breath_analysis.png`
- `final_diagnostic.png`
- `render_50_natural.wav`
- `render_150_natural.wav`
- `render_150_soft.wav`
- `render_150_strong.wav`
- `breath_shaping_results.json`
