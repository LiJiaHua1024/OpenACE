# SVC arrangement integration QA report

Date: 2026-11-27
Branch: `devin/1795696369-dynamic-expression`
Mode: visible Chrome at 1272×837, fixture backend (`OPENACE_CI_SYNTH_FIXTURE=1`).

## Result

All requested SVC arrangement-integration checks passed.

Harness transparency: the first master-export oracle incorrectly expected the dragged start tick 120 to mean 0.25s. At 120 BPM/480 PPQ it is exactly 0.125s; the measured master onset was about 0.125s, so the implementation was correct and the results file was corrected. This was a test-oracle issue, not an application defect.

## Inputs

Generated explicit local test WAVs:

- `svc_source_phrase.wav`: 1.2s harmonic source phrase
- `svc_reference_voice.wav`: 1.0s reference-like tone plus broadband aspiration noise

Both were uploaded through visible browser file-chooser controls.

## Conversion/job/backend verification

Visible **SVC voice conversion** click completed job `job_3b02b38b4a1c`.

Passed:

- job status `completed`
- job message exactly included `completed; added to arrangement as SVC — svc_source_phrase`
- output path exists
- diagnostic path exists
- new backend audio track `SVC — svc_source_phrase`
- clip at tick 0 with path equal to the job output WAV
- `project.metadata['svc_conversions']` records job id, track id, source, reference, and output path
- new track appeared in the visible track list without page reload

## Arrangement/waveform/playback verification

Passed:

- arrangement visibly shows green `SVC: svc_source_phrase` waveform clip at tick 0
- waveform decode/fetch produced no errors
- visible playback interaction advanced transport from `1.1.1` to `1.2.3` / `00:00.83`
- no decode errors, console errors, or network failures occurred
- clip path exists and is the arrangement playback source; track `render_path` intentionally matches the same file but is deduplicated by playback/export logic

## Clip editing verification

Passed:

- arrangement drag moved clip from `start=0` to `start=120`
- right-edge drag trimmed duration from `1152` to `1032`
- backend persisted `start=120`, `duration=1032`, `offset=0`

At 120 BPM/480 PPQ this means the edited clip occupies about 0.125–1.2 seconds.

## Master export verification

Passed:

- `/export/wav` returned HTTP 200 and 345,644 bytes
- exported master duration: 1.2s at 48kHz
- first nonzero range: approximately 0.125–1.2s
- RMS in the early converted region: `0.16268`

This objectively matches the dragged clip placement and proves the conversion is included in master export.

## Diagnostic verification

Passed: diagnostic PNG exists and gracefully renders `No vocal notes in project` for a project whose vocal track has no notes, while still showing spectral occupancy and fixture provenance.

## Health

No console errors or network failures occurred.

## Evidence

- `svc_source_phrase.wav`
- `svc_reference_voice.wav`
- `svc_master_export.wav`
- `master_export_analysis.png`
- `svc_diagnostic.png`
- `01_uploaded_source_reference.png`
- `02_svc_track_no_reload.png`
- `03_after_playback_interaction.png`
- `04_clip_dragged_trimmed.png`
- `05_svc_job_diagnostic_panel.png`
- `svc_arrangement_results.json`
