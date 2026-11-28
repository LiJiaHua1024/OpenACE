# SVC Project-Clip Awareness QA Report

Date: 2026-11-28
Backend: restarted in explicit fixture mode (`OPENACE_CI_SYNTH_FIXTURE=1`, delay 1s), PID file `/tmp/openace-svc-clip-qa.pid`.
Frontend: production build `frontend/dist/assets/index-DJSdbq9w.js`, cache-busted in visible Chrome.
Project: `project_832a3769a65b` / `Untitled OpenACE Project`.
Implementation was not modified or committed.

## Defect list

No product defects found in this pass.

Workflow note, not counted as a defect: clicking an arrangement audio clip also selects that audio track, so the SVC button is disabled until the vocal track carrying the reference voice is reselected. The explicit clip/path source context correctly survives that reselection and conversion then uses the exact clip.

Harness limitation, not a product defect: the first real UI left-trim succeeded exactly, but the right edge of the original 3s clip was outside the visible arrangement canvas at default zoom. I completed the controlled right trim through the project API without reloading, preserving the browser's explicit clip context. The resulting geometry was exact and the rest of the workflow was browser-driven.

## Quantitative results

### 1. Import and controlled trim — passed

A controlled 3s/24kHz WAV was imported through the visible `Import audio as clip at playhead` control. Import immediately set the RenderPanel source without any separate `Upload vocal/audio source` step.

Initial imported clip:

```text
clip_e32e014fd922
start_ticks=0
duration_ticks=2880 (3s)
offset_ticks=0
path=data/uploads/clip_d275beb12e77_svc_clip_control_source.wav
```

After the real left trim plus exact API completion of the offscreen right trim:

```text
start_ticks=480   (0.5s at 120bpm)
duration_ticks=1920 (2s)
offset_ticks=480  (0.5s source offset)
visible source segment = 0.5–2.5s
```

RenderPanel immediately showed:

```text
path: clip_d275beb12e77_svc_clip_control_source.wav
hint: Vocal2BGM/SVC input: visible clip segment · aligned to clip start
SVC title: Convert the exact visible arrangement clip segment
Vocal2BGM title: Use the matching arrangement clip segment as input
```

Evidence: `01_reference_voice_uploaded.png`, `02_trimmed_clip_immediate_svc_source.png`, `phase1_import_trim_results.json`.

### 2. Exact excerpt and conversion output — passed

A valid reference voice was uploaded through the visible Voice `Upload` control:

```text
voice_34959253571a / svc_reference_voice
2.0s · 24.0kHz
```

The first controlled SVC job `job_87e443564989` carried exactly:

```json
{
  "clip_id": "clip_e32e014fd922",
  "source_start_s": 0.5,
  "source_end_s": 2.5,
  "arrangement_start_ticks": 480
}
```

Waveform inspection:

```text
source length:       72000 samples = 3.0s
excerpt length:      48000 samples = 2.0s
conversion output:   48000 samples = 2.0s
excerpt exactness:   bit-identical to source samples [0.5:2.5], max error 0.0
fixture conversion:  matches tremolo-transformed excerpt within PCM16 quantization, max error 3.05e-05
```

The generated conversion clip initially integrated at `start_ticks=480` with `duration_ticks=1920`, matching the source clip's then-current arrangement start and visible duration.

Evidence: `svc_excerpt_analysis.json`, `svc_waveform_quantitative_analysis.json`.

### 3. True mid-running move — passed

A second controlled conversion `job_7e1b417d4c93` captured the original clip position:

```text
arrangement_start_ticks=480
```

While the job was still `running` at progress `0.84` (`transcribing and integrating converted vocal`), the source clip was dragged one beat/right:

```text
clip_e32e014fd922 start_ticks: 480 → 960
duration_ticks remains 1920
offset_ticks remains 480
```

The job still carried its original captured `arrangement_start_ticks=480`, but the completed conversion clip integrated at the completion-time source position:

```text
clip_a08186746c23 start_ticks=960
duration_ticks=1920
```

This is direct proof of completion-time clip-position following during a true mid-running move, not merely a queued-job approximation.

Evidence: `06_source_clip_drag_held_during_svc.png`, `07_source_clip_moved_during_svc.png`, `08_second_svc_completed_at_moved_position.png`, `svc_move_results.json`.

### 4. Transcribed correction lane — passed

The SVC fixture output was transcribed into two words:

```text
for       0.0–0.4
watching! 0.4–1.94
```

Clicking the generated conversion clip selected its track and rendered the `SVC clip lyrics` correction lane with two editable text/time rows. No page error or crash occurred.

Evidence: `19_svc_correction_lane_visible.png`, `svc_duplicate_unanchored_results.json`.

### 5. Duplicate source-path disambiguation — passed

A second arrangement clip using the same source path was seeded as a controlled duplicate:

```text
clip_dup_svc_probe
start_ticks=48   (0.1s)
duration_ticks=480 (0.5s)
offset_ticks=960 (1.0s source offset)
visible source segment = 1.0–1.5s
```

Direct API conversion with the same `source_audio` but no `clip_id` produced an actionable validation error:

```text
HTTP 422
{"detail":"multiple arrangement clips use this source audio; pass clip_id explicitly"}
```

Clicking the duplicate arrangement clip updated the source context to the same path, then explicit browser-triggered conversion produced job `job_d2709f0cb582` with exact disambiguation:

```json
{
  "clip_id": "clip_dup_svc_probe",
  "source_start_s": 1.0,
  "source_end_s": 1.5,
  "arrangement_start_ticks": 48
}
```

The output file was exactly `0.5s`; its excerpt was bit-identical to source `[1.0:1.5]`; the integrated conversion clip started at `48` ticks and lasted `480` ticks.

Evidence: `14_duplicate_same_path_explicitly_selected.png`, `15_duplicate_same_path_svc_completed.png`, `svc_duplicate_explicit_results.json`, `svc_output_file_facts.json`.

### 6. Arbitrary unanchored upload regression — passed

The visible `Upload vocal/audio source` control was used for a separate 1.5s file that was never placed in the arrangement.

UI state before conversion:

```text
path: upload_124cbe561773_svc_unanchored_source.wav
clip hint count: 0
SVC title: Convert the uploaded source file
button enabled
```

Job `job_006aa4e224fa` completed with:

```json
{
  "clip_id": null,
  "source_start_s": null,
  "source_end_s": null,
  "arrangement_start_ticks": 0
}
```

The output file was exactly `1.5s`; the integrated clip started at `0` and lasted `1440` ticks.

Evidence: `12_unanchored_upload_source_ready.png`, `13_unanchored_svc_completed.png`, `svc_duplicate_unanchored_results.json`.

### 7. Vocal2BGM regression — passed

The controlled arrangement clip was clicked again, restoring explicit clip context. Browser-triggered Vocal2BGM job `job_0e84c5f915cb` carried exactly:

```json
{
  "clip_id": "clip_e32e014fd922",
  "source_start_s": 0.5,
  "source_end_s": 2.5,
  "arrangement_start_ticks": 960
}
```

The generated accompaniment clip integrated at:

```text
start_ticks=960
duration_ticks=1920
```

Its source excerpt was exactly 2s and bit-identical to source `[0.5:2.5]`; accompaniment output was exactly 2s.

Evidence: `16_controlled_clip_reselected_for_vocal2bgm.png`, `17_vocal2bgm_regression_completed.png`, `vocal2bgm_regression_results.json`, `vocal2bgm_regression_analysis.json`.

### 8. Playback and browser health — passed

Direct `AudioBufferSourceNode.start` instrumentation captured the expected arrangement scheduling, including:

```text
controlled source clip: when≈1.035, offset=0.5, duration=2, bufferDuration=3
duplicate visible clip: when≈0.085, offset=1.0, duration=0.5, bufferDuration=3
unanchored conversion:  when≈0.035, offset=0, duration=1.5, bufferDuration=1.5
controlled conversion:  when≈1.035, offset=0, duration=2
Vocal2BGM output:       when≈1.035, offset=0, duration=2
```

Transport advanced and remained in playing state:

```text
first pass:  1.4.3 / 00:01.82
second pass: 2.3.4 / 00:03.41
```

Across the browser passes:

```text
console errors:   0
console warnings: 0
page errors:      0
failed browser network responses: 0
```

Evidence: `18_playback_instrumented_svc_project.png`, `svc_playback_results.json`.

## Artifact index

- `00_fresh_project_seeded_notes.png`
- `01_reference_voice_uploaded.png`
- `02_trimmed_clip_immediate_svc_source.png`
- `03_vocal_reference_reselected_clip_context_ready.png`
- `06_source_clip_drag_held_during_svc.png`
- `07_source_clip_moved_during_svc.png`
- `08_second_svc_completed_at_moved_position.png`
- `09_svc_transcribed_correction_lane.png`
- `12_unanchored_upload_source_ready.png`
- `13_unanchored_svc_completed.png`
- `14_duplicate_same_path_explicitly_selected.png`
- `15_duplicate_same_path_svc_completed.png`
- `16_controlled_clip_reselected_for_vocal2bgm.png`
- `17_vocal2bgm_regression_completed.png`
- `18_playback_instrumented_svc_project.png`
- `19_svc_correction_lane_visible.png`
- `20_final_state.png`
- `phase1_import_trim_results.json`
- `svc_move_results.json`
- `svc_excerpt_analysis.json`
- `svc_waveform_quantitative_analysis.json`
- `svc_duplicate_unanchored_results.json`
- `svc_duplicate_explicit_results.json`
- `svc_output_file_facts.json`
- `svc_playback_results.json`
- `vocal2bgm_regression_results.json`
- `vocal2bgm_regression_analysis.json`
