# Audio-import expressive pitch curve QA — incomplete

Recording: `/home/ubuntu/screencasts/audio-pitch-curve-qa/audio-pitch-curve-qa-edited.mp4`

## What passed

- Created fixture project `project_f58498ba2860` with a vocal note containing realistic microtonal `pitch_curve` points: offsets 0/250/500/750/1000/1500ms and cents 0/35/-25/60/10/-15.
- In visible Chrome, piano-roll pitch mode visibly rendered a continuous microtonal line and multiple point handles along the imported note.
- Layout appeared normal at 1272×837 in the captured screenshot.

## Incomplete / not objectively proven

- Scripted handle drag/delete did **not** mutate backend pitch curve. Current evidence suggests harness hit-position error rather than confirmed implementation defect, but this is not proven.
- Reload persistence was not completed because `networkidle` reload timed out on the open SSE connection.
- A broader hit-search then hit a browser CDP timeout, leaving edit/delete testing incomplete.
- Console/network health could not be fully collected for the same reason.

## Artifacts

- `01_pitch_curve_handles.png` — visible pitch curve/handles evidence.
- `02_after_handle_drag.png`, `03_after_handle_delete.png` — attempted interactions; backend did not change, so these are not success evidence.

No implementation files modified.
