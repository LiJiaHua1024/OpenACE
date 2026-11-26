# Arrangement fades — adversarial real Chrome QA

## Scope and method

Visible Chrome 1272x837 was driven with Playwright over CDP against a restarted current-tree fixture server. Existing rendered-fixture project `project_e3f52a65d029` was selected through the visible project picker. QA covered fade-in/out corner drags, waveform/line visuals, interaction-zone separation, visual fade-handle behavior, split redistribution, playback AudioParam ramps, and console/network health. The fixture project was restored afterward.

## Outcome

Core fade rendering/editing works, but two defects remain. Clip gain could not be visibly tested because the current UI exposes no clip-gain control.

## Defects

### 1. Visible fade-handle endpoint is not the actual fade drag target

After creating a 240-tick fade-in, the visible white fade handle/end affordance sits at the end of the fade slope. Dragging that visible handle did **not** adjust the fade. Instead it initiated ordinary clip-body dragging and moved the whole clip from `start_ticks=0` to `120`, while `fade_in_ticks` remained `240`.

Evidence: `05_visual_handle_drag_result.png` and `evidence_visual_handle_moved_clip_crop_x2.png`.

This is a significant interaction mismatch: the control that visually appears draggable performs a different operation.

### 2. Full outward right-trim restoration loses one tick

Right-edge inward trim correctly changed duration `2400 -> 2280` without disturbing fades. Dragging back outward restored only `2399`, not `2400`. Browser decoding resamples the 2.5s/24000Hz WAV to `110249/44100 = 2.499977324s`; the implementation floors the source end, producing `2399` ticks. This is small (~1.04ms at 120 BPM) but objectively loses one tick at the source boundary.

## Results

| Check | Result | Evidence |
|---|---|---|
| Load fixture audio clip | PASS | clip `(start=0,duration=2400,offset=0,fades=0)` |
| Fade-in drag direction/persistence | PASS | top-left drag right persisted `fade_in_ticks=240`; start/duration unchanged |
| Fade-out drag direction/persistence | PASS | top-right drag left persisted `fade_out_ticks=240`; start/duration unchanged |
| Fade line/waveform visuals | PASS | diagonal fade lines visible; waveform visibly attenuated toward both edges |
| Fade/trim/body hit priority at exact tested zones | PASS | top corners created fades, body drag moved clip, lower-right edge trimmed clip |
| Cursor affordance | PASS with concern | body `grab`, edge/top corner `ew-resize`; no distinct fade cursor or larger visible affordance |
| Visible fade-handle endpoint drag | FAIL | moves whole clip instead of adjusting fade |
| Ordinary body drag | PASS | `0 -> 120 -> 0`, fades preserved |
| Lower-right trim | FAIL/minor | inward `2400 -> 2280` correct; outward restored `2399` rather than `2400` |
| Split outer-fade redistribution | PASS | first `(fade_in=240,fade_out=0)`; second `(fade_in=0,fade_out=240)`; inner boundary clean |
| Split positions | PASS relative to pre-split state | first `(0,1200,offset0)`, second `(1200,1199,offset1200)` because pre-split duration was already 2399 |
| Playback | PASS | transport advanced to `00:01.12`, no deadlock |
| AudioParam ramps | PASS | 2 `linearRampToValueAtTime` events captured; fade-in ramp to 0.8 and final fade-out ramp to 0.0001 |
| Clip gain | UNTESTED | no visible clip-gain control exists in the UI |
| Console/network health | PASS | zero browser console errors and zero network failures |
| Cleanup | PASS | fixture project restored to original unsplit `(0,2400,0)` clip |

## Critical-user observations

- Fade direction is correct: fade-in drags right to lengthen; fade-out drags left to lengthen.
- The fade envelope visuals are genuinely readable once present, and waveform attenuation is clear.
- The handles are very small (2x4px) and the top fade hit strip is only about 8px tall. Combined with the same `ew-resize` cursor as trimming, discoverability is weak even before the hit-zone mismatch.
- Exact top-corner interactions do prioritize fades over trims, and lower-edge trim still works; the zone overlap logic itself is not dead.

## Harness note

The first harness pass loaded the wrong project because this app ignores `?project=` on initial boot. That was corrected by using the visible project picker. This was test-harness state, not a product defect.

## Artifacts

- `arrangement_fades_results.json` — structured geometry/data/playback evidence
- `browser_console.jsonl` — empty console/network health log
- `original_project_backup.json` — pre-test fixture backup
- `01_initial_clip.png`
- `02_fade_in_drag_held.png`
- `03_fade_out_drag_held.png`
- `04_fades_applied.png`
- `05_visual_handle_drag_result.png` — visible-handle hit-zone defect
- `06_after_lower_edge_trim_restore.png`
- `07_split_context_menu.png`
- `08_after_split_fades.png`
- `09_playback_after_split.png`
- `evidence_fades_crop_x2.png`
- `evidence_visual_handle_moved_clip_crop_x2.png`
- `evidence_split_fades_crop_x2.png`
