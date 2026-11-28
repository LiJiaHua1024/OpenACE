# Project-aware Vocal2BGM QA Report

Date: 2026-11-28
Backend: restarted in explicit fixture mode (`OPENACE_CI_SYNTH_FIXTURE=1`, delay 1s).
Frontend: production build `index-SdrYJvB9.js`, cache-busted in visible Chrome at `1280×841`.
Project: `project_00d47d7aaeff` / `Vocal2BGM Aware QA`.
Implementation was not modified or committed.

## Defect list

### P3 — invalid Vocal2BGM backend inputs are rejected as generic unhandled HTTP 500s

Direct API probes confirm the backend does reject both invalid input classes, but the client receives only `500 Internal Server Error` with no actionable detail:

- Ambiguous duplicate arrangement clips without `clip_id`: `500 Internal Server Error`; backend log contains `ValueError: multiple arrangement clips use this source audio; pass clip_id explicitly`.
- Stale selected vocal render: `500 Internal Server Error`; backend log contains `ValueError: selected vocal render is stale; render the current vocal before Vocal2BGM`.

Evidence: `ambiguity_probe_results.json`, `stale_api_probe_results.json`, backend log lines 410–411 and 484–485 in `/tmp/openace-vocal2bgm-aware.log`.

This did not affect the browser flow because the UI disables stale input and sends an explicit clip id for arrangement clips. It is an API ergonomics/error-contract defect rather than a core rendering failure.

## Results

### 1. Fresh selected vocal render input — passed

A new project was created through the visible `＋ New` control. Two vocal notes ending at 2s were seeded through the project API, then the visible `Render vocal` button completed fixture job `job_e268860b058c`.

Without uploading any manual source:

- path readout: `selected vocal render`
- hint: `input: selected vocal render`
- Vocal2BGM button enabled
- button title: `Use the selected vocal track render as input`

Vocal2BGM completed as `job_bca62ccee32f` with:

```json
{
  "track_id": "track_dfcd46b3f185",
  "source_audio": ".../job_e268860b058c/vocal.wav",
  "clip_id": null,
  "source_start_s": null,
  "source_end_s": null,
  "arrangement_start_ticks": 0
}
```

The integrated accompaniment clip started at `0` and lasted `2400` ticks = `2.5s`, matching the fixture vocal render duration.

Evidence: `01_selected_vocal_render_input_hint.png`, `02_fresh_vocal_bgm_integrated.png`, `fresh_vocal_results.json`.

### 2. Stale disable/re-enable — passed

After a visible `+12` transpose mutation:

- Vocal2BGM became disabled.
- Title became `Selected vocal render is stale; render it first`.
- The vocal track showed one stale-render badge.

After clicking `Render vocal` again and job `job_ea246e15cb45` completed:

- Vocal2BGM re-enabled.
- Title returned to `Use the selected vocal track render as input`.
- Stale badge cleared.

Evidence: `03_stale_vocal_bgm_disabled.png`, `04_rerendered_vocal_bgm_enabled.png`, `stale_reenable_results.json`.

### 3. Controlled trimmed source clip — passed

The controlled 3s source was uploaded through the visible upload control as:

```text
upload_2c545b1a0fae_vocal2bgm_control_source.wav
```

A clip was seeded through the project API with exact controlled geometry:

```text
arrangement start: 960 ticks  = 1s
duration:         1920 ticks = 2s
source offset:     480 ticks = 0.5s
```

With that uploaded source selected, the UI showed:

```text
input: visible clip segment · aligned to clip start
```

and button title `Use the matching arrangement clip segment as input`; no manual clip id had to be entered.

The Vocal2BGM job `job_335613909e4d` carried exactly:

```json
{
  "clip_id": "clip_707e5a808080",
  "source_start_s": 0.5,
  "source_end_s": 2.5,
  "arrangement_start_ticks": 960
}
```

The materialized excerpt and generated accompaniment were quantitatively correct:

```text
source length:   72000 samples = 3.0s
excerpt length:  48000 samples = 2.0s
output length:   48000 samples = 2.0s
excerpt vs exact source[0.5:2.5]: max abs error 0.0
first/last samples exactly matched source-file samples
```

Evidence: `05_controlled_clip_input_hint.png`, `controlled_clip_results.json`, `controlled_excerpt_analysis.json`, `13_controlled_excerpt_alignment.png`.

### 4. Clip movement before completion — passed with a timing caveat

A direct attempt to move the clip after clicking Vocal2BGM completed the move 105 ms after click while the job status was still `running`, but fixture integration had already happened; that output correctly remained at the original position. This was not counted as a defect because the move landed after integration, and fixture generation is deliberately very fast.

To verify the intended current-position semantics deterministically, the controlled Vocal2BGM job was then queued behind a slow fixture vocal render:

- job captured original `arrangement_start_ticks=960`
- while it was still queued behind the running vocal job, the source clip was moved to `1920`
- the job later completed and the generated accompaniment clip was integrated at exactly `start_ticks=1920`, not the originally captured `960`
- generated duration remained exactly `1920` ticks = 2s

This proves completion-time clip-position following. A true mid-running move remains impractical to time in fixture mode because generation/integration completes in tens of milliseconds.

Evidence: `06_controlled_clip_bgm_integrated.png`, `07_queued_move_followed_clip_position.png`, `queued_move_results.json`.

### 5. Arbitrary uploaded file outside arrangement — passed

A separate 1.5s file was uploaded through the visible upload control and never placed into the arrangement:

```text
upload_4ad536d092cc_vocal2bgm_arbitrary_source.wav
```

UI state before clicking:

- path readout showed that uploaded file
- `.vocal2bgm-source` hint count was `0`
- title was `Use the uploaded source file as input`
- button was enabled

Job `job_89efbc8cfc69` completed with:

```json
{
  "clip_id": null,
  "source_start_s": null,
  "source_end_s": null,
  "arrangement_start_ticks": 0
}
```

Generated accompaniment output was exactly `1.5s`, integrated at `start_ticks=0`, `duration_ticks=1440`.

Evidence: `08_arbitrary_upload_input.png`, `09_arbitrary_upload_integrated.png`, `arbitrary_upload_results.json`.

### 6. Repaint regression — passed

With repaint range `1.25–2.25s` overlapping generated accompaniment:

- `Repaint selection` was enabled
- target hint existed: `target: Vocal2BGM`
- title was `Repaint Vocal2BGM using source-file timing`

Evidence: `10_repaint_target_regression.png`, `repaint_playback_results.json`.

### 7. Playback — passed

Direct `AudioBufferSourceNode.start` instrumentation captured six expected sources:

- three at arrangement time zero with durations `3.5`, `2.5`, and `1.5` seconds
- one at +1s duration 2s
- two at +2s duration 2s, including the controlled source clip with source offset `0.5s`

A second cached-buffer playback pass remained in playing state and advanced to `1.3.3 / 00:01.33`, proving playback continued rather than merely creating nodes.

Evidence: `11_playback_project_aware.png`, `12_playback_position_advanced.png`, `playback_position_results.json`.

### 8. Console/network and visual inspection — passed for browser flows

Across fresh render, stale/re-render, controlled clip, arbitrary upload, repaint, and playback browser passes:

- console errors: 0
- console warnings: 0
- page errors: 0
- failed browser network responses: 0

The intentional direct-API ambiguity/stale probes produced backend 500s outside the browser and are reported as the P3 API error-contract defect above.

Visual inspection found no obvious layout overlap, dead control, stale input hint, fake progress, duplicate integration, or arrangement corruption.

## Evidence index

- Recording: `/home/ubuntu/screencasts/vocal2bgm-project-aware-qa/vocal2bgm-project-aware-qa-edited.mp4`
- `00_seeded_vocal_project.png`
- `01_selected_vocal_render_input_hint.png`
- `02_fresh_vocal_bgm_integrated.png`
- `03_stale_vocal_bgm_disabled.png`
- `04_rerendered_vocal_bgm_enabled.png`
- `05_controlled_clip_input_hint.png`
- `06_controlled_clip_bgm_integrated.png`
- `07_queued_move_followed_clip_position.png`
- `08_arbitrary_upload_input.png`
- `09_arbitrary_upload_integrated.png`
- `10_repaint_target_regression.png`
- `11_playback_project_aware.png`
- `12_playback_position_advanced.png`
- `13_controlled_excerpt_alignment.png`
- `fresh_vocal_results.json`
- `stale_reenable_results.json`
- `controlled_clip_results.json`
- `controlled_excerpt_analysis.json`
- `queued_move_results.json`
- `arbitrary_upload_results.json`
- `repaint_playback_results.json`
- `playback_position_results.json`
- `ambiguity_probe_results.json`
- `stale_api_probe_results.json`

## Post-QA API error-contract resolution

The P3 HTTP 500 defect reported above was fixed after this browser run: Vocal2BGM/repaint input-validation `ValueError`s are now converted to actionable HTTP 422 responses with detail. Focused API regression coverage proves duplicate-source ambiguity returns 422 mentioning `clip_id` and stale selected vocal input returns 422 mentioning `stale`.

