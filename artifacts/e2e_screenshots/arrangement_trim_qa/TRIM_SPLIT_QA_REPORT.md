# Arrangement trim/split QA report

Real visible Chrome QA through Playwright/CDP on branch `devin/1795694748-arrangement-trim-split`, using fixture project `project_e3f52a65d029` at `http://127.0.0.1:8787` with `OPENACE_CI_SYNTH_FIXTURE=1`. Viewport was 1272×837. No product code was modified. Project state was restored afterward.

## Result: PASS — no remaining defect found in this targeted QA

| Check | Result | Evidence |
|---|---:|---|
| Trim affordance and cursor | PASS | center cursor `grab`; left/right edge cursor `ew-resize`; visible edge handle pixels present |
| Initial decoded waveform | PASS | varying spans min 2 / max 9, unique spans `[2,4,5,6,7,8,9]` |
| Right-edge inward trim | PASS | `(start,offset,duration)` became `(0,0,1440)` from `(0,0,2400)` |
| Left-edge inward trim | PASS | became `(480,480,960)` |
| Waveform remapping after trim | PASS | first half mean span 2.8 vs second half 6.54, matching quiet→loud source segment |
| Context menu | PASS | visible `Split at cursor`, clickable/not dead |
| Split positions | PASS | `(480,480,480)` + `(960,960,480)`, contiguous with no overlap |
| Split waveform remapping | PASS | first segment mean span 2.88 vs second 7.19 |
| Undo/redo around split | PASS | undo restored `(480,480,960)`; redo restored both split segments |
| Future playback scheduling | PASS | delay/offset/duration `(0.5,0.5,0.5)` and `(1.0,1.0,0.5)` |
| Positive seek playback | PASS | at tick 720 (.75s): first `offset=.75,duration=.25` immediate; second delayed `.25s` with `offset=1,duration=.5` |
| Outward edge extension | PASS | right `1440→1920`; left `(480,480,1440)→(0,0,1920)` |
| Master export slicing/placement | PASS | 1.5s export; max amplitude 0 before .45s, quiet first segment .201, loud second .666, zero after 1.55s |
| Console/network health | PASS | no browser console errors or failed network responses observed |
| Cleanup | PASS | project restored to `(0,0,2400)` and vocal unmuted |

## Visual evidence

Trimmed waveform remapped honestly: the left/source-quiet side is low and the right/source-loud side is tall.

![Left-trimmed waveform remap](https://app.devin.ai/attachments/2ca9178d-3c93-40eb-95d0-361614f50642/evidence_after_left_trim_crop.png#w=1428&h=196)

Context menu is visible and actionable.

![Split context menu](https://app.devin.ai/attachments/3944e46f-8629-44a7-b817-c72777667296/06_split_context_menu.png#w=1272&h=837)

After splitting, the first clip is low-amplitude and the second is high-amplitude, matching their source regions.

![Split waveform segments](https://app.devin.ai/attachments/b18944d1-4253-461f-a43e-1b74d5e8a911/evidence_after_split_crop.png#w=1428&h=196)

Positive-seek instrumentation overlay:

![Correct positive seek instrumentation](https://app.devin.ai/attachments/3b3f0969-119f-450b-b6ce-210c5c463642/09_split_playback_instrumentation.png#w=1272&h=837)

Outward left-edge extension while held:

![Outward left trim](https://app.devin.ai/attachments/082d72f2-088b-4918-b598-bc0e3829d766/12_left_edge_outward_drag_held.png#w=1272&h=837)

## Harness note

During the recorded run, one positive-seek click initially used a miscalculated harness coordinate (tick 1080 rather than tick 720 for .75s). The observed playback was actually correct for that clicked position; the corrected tick-720 check passed exactly, and a final full supplemental pass produced the clean `trim_split_results.json` and empty console/network log included here. This was a harness correction, not a product defect.

## Artifact index

- Recording: `/home/ubuntu/screencasts/rec-752ca1ef-bc28-4021-b34f-42ee35a78372/rec-752ca1ef-bc28-4021-b34f-42ee35a78372-edited.mp4`
- Machine-readable results: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_trim_qa/trim_split_results.json`
- Export proof WAV: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_trim_qa/trimmed_split_master.wav`
- Console/network log: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_trim_qa/browser_console.jsonl` (empty)
