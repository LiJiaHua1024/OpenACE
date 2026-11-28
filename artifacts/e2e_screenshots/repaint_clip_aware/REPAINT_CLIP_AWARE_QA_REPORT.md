# Clip-aware Repaint Integration QA Report

Date: 2026-11-28
Branch/worktree: current uncommitted `/home/ubuntu/repos/OpenACE` working tree.
Backend: restarted in explicit fixture mode (`OPENACE_CI_SYNTH_FIXTURE=1`, delay 1s).
Frontend: production build `index-Mu702bxO.js`, cache-busted in visible Chrome at `1280×841`.
Implementation was not modified or committed.

Test project: `project_c706171a3614` / `Clip Repaint QA`.
Controlled source files:

- `data/qa_sources/repaint_clip_control_source.wav` — 3s, 24kHz, low-level 80Hz control tone
- `data/qa_sources/repaint_clip_control_other.wav` — 3s, 24kHz, separate decoy tone

## Defect list

No product defects were found in this focused pass.

One setup limitation was understood and not counted as a product defect: directly seeded source files under `data/qa_sources` are outside the frontend's `/renders/`/`/uploads/` media URL mapping, so decoy waveforms/playback for those original seed paths were not meaningful. The repaint target output itself moved under `/renders/` and was fully playable/schedulable, which was the required playback assertion.

## Controlled arrangement case

At 120 BPM, PPQ 480:

```text
clip start:      960 ticks  = 1.0 arrangement seconds
clip duration:  1920 ticks  = 2.0 arrangement seconds
clip offset:     480 ticks  = 0.5 source-file seconds
arrangement select: 0.75 → 2.25 seconds
visible intersection: 1.0 → 2.25 seconds
expected source interval: 0.5 + (1.0−1.0) → 0.5 + (2.25−1.0)
                       = 0.5 → 1.75 source-file seconds
```

Three overlapping accompaniment clips were seeded/displayed:

1. `Target clip` — control source, nonzero offset/trim/fades/gain
2. `Decoy same source` — same control source
3. `Decoy other source` — different source

The target was first in track order and therefore was the deterministic UI-selected overlap target.

## Results

### 1. Project creation and controlled clip display — passed

A new project was created through the visible `＋ New` control and renamed `Clip Repaint QA`. Controlled target/decoy clips were seeded through the project API because exact nonzero trim/offset/fade/gain setup is cumbersome through pointer UI; this is explicitly allowed by the test brief. The open UI updated live and displayed the target/decoy arrangement clips.

Evidence: `00_seeded_controlled_clips.png`, `seed_results.json`.

### 2. Disabled state when range misses clips — passed

With numeric repaint range `10 → 11` seconds:

- `Repaint selection` was disabled.
- No `.repaint-target` hint existed.
- Button title was `Draw a region overlapping an accompaniment clip`.

Evidence: `01_repaint_disabled_miss.png`, `disabled_miss_results.json`.

### 3. Alt-drag overlap, target hint, and launch — passed

A real Alt-drag on the arrangement produced exactly `0.75 → 2.25` seconds. The range was visibly drawn over the arrangement. The UI then showed:

```text
target: Target clip
```

Button title:

```text
Repaint Target clip using source-file timing
```

No manual source upload was present (`no source selected`), confirming the new clip-aware path rather than the old manually-selected-source dependency.

The repaint job completed:

```json
{
  "id": "job_f2468c141366",
  "status": "completed",
  "mode": "repaint",
  "start_s": 0.75,
  "end_s": 2.25,
  "clip_id": "clip_0de208e26647",
  "source_start_s": 0.5,
  "source_end_s": 1.75,
  "source_audio": ".../repaint_clip_control_source.wav",
  "output_path": ".../job_f2468c141366/accompaniment.wav",
  "engine": "explicit CI music fixture"
}
```

Evidence: `02_alt_drag_repaint_held.png`, `03_repaint_target_hint_exact_range.png`, `04_repaint_completed.png`, `repaint_trigger_results.json`.

### 4. Quantitative source-file interval proof — passed exactly

Output/input lengths and sample rate:

```text
input:  72000 samples @ 24000Hz
output: 72000 samples @ 24000Hz
```

Expected replacement source interval:

```text
0.5–1.75s = samples 12000–42000
```

Measured output analysis:

```text
max |output-input| outside interval: 0.0
max error vs exact 220Hz fixture sine inside: 3.0229e-05
RMS error vs exact 220Hz fixture sine inside:  1.7550e-05
max amplitude inside replacement:             0.120026
max original control amplitude inside:        0.020020
```

The small sine error is consistent with PCM16 quantization. Outside the expected interval the output is bit-identical to the input. This proves correct source-file-time mapping, not naive arrangement-time replacement.

Evidence: `repaint_quantitative_results.json`, `07_repaint_waveform_interval_analysis.png`.

### 5. Clip targeting/provenance and preservation — passed

After repaint, the target clip was exactly:

```json
{
  "id": "clip_0de208e26647",
  "path": ".../job_f2468c141366/accompaniment.wav",
  "start_ticks": 960,
  "duration_ticks": 1920,
  "offset_ticks": 480,
  "fade_in_ticks": 24,
  "fade_out_ticks": 36,
  "gain_db": -3.0,
  "created_by_job_id": "job_seed_target",
  "updated_by_job_id": "job_f2468c141366"
}
```

Thus start, duration, offset, fades, gain, and original creation provenance were preserved exactly. Only media path/update provenance changed, plus the existing intentional label normalization to `Repaint`.

Same-source decoy remained unchanged:

```json
{
  "path": ".../repaint_clip_control_source.wav",
  "created_by_job_id": "job_seed_same",
  "updated_by_job_id": null
}
```

Other-source decoy remained unchanged:

```json
{
  "path": ".../repaint_clip_control_other.wav",
  "created_by_job_id": "job_seed_other",
  "updated_by_job_id": null
}
```

### 6. Playback scheduling after repaint — passed

Direct `AudioBufferSourceNode.start` instrumentation captured the repainted target clip:

```json
{
  "when_minus_contextTime": 1.0,
  "offset": 0.5,
  "duration": 2
}
```

This exactly matches arrangement start `1s`, source offset `0.5s`, and visible duration `2s`. A second cached-buffer playback pass remained playing and advanced to `1.3.4 / 00:01.44`, confirming playback continued rather than merely creating a node.

Only one source was expected/valid in this seeded setup because the decoy original paths were outside the frontend media URL mapping; the repainted target output was under `/renders/` and playable.

Evidence: `05_playback_after_repaint.png`, `06_playback_position_advanced.png`, `playback_schedule_results.json`, `playback_position_results.json`.

### 7. Console/network cleanliness — passed

Across repaint trigger and playback instrumentation:

- console errors: 0
- console warnings: 0
- page errors: 0
- failed network responses: 0

## Visual review notes

The target hint, numeric range, yellow repaint overlay, target/decoy clips, post-repaint arrangement state, transport state, and playback state were visually inspected. No obvious layout overlap, dead control, stale target hint, or clip duplication was observed.

## Evidence index

- `00_seeded_controlled_clips.png`
- `01_repaint_disabled_miss.png`
- `02_alt_drag_repaint_held.png`
- `03_repaint_target_hint_exact_range.png`
- `04_repaint_completed.png`
- `05_playback_after_repaint.png`
- `06_playback_position_advanced.png`
- `07_repaint_waveform_interval_analysis.png`
- `seed_results.json`
- `disabled_miss_results.json`
- `repaint_trigger_results.json`
- `repaint_quantitative_results.json`
- `playback_schedule_results.json`
- `playback_position_results.json`
- Recording: `/home/ubuntu/screencasts/repaint-clip-aware-qa/repaint-clip-aware-qa-edited.mp4`
