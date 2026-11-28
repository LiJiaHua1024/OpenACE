# Per-note pitch handles — adversarial real Chrome QA

## Scope and method

Visible Chrome 1272x837 was driven with Playwright over CDP against the fixture server. A fresh project was created through the UI, a C4 note was drawn and selected, pitch mode was entered by toolbar and `P`, three signed handles were created, one was dragged across the others, one was deleted with Alt+click, and persistence plus one-step undo/redo were checked against both the backend API and the on-disk project file.

## Outcome

All functional assertions passed. No blocking defect or interaction dead end was found.

## Results

| Check | Result | Evidence |
|---|---|---|
| Create/select note | PASS | project `project_852c4e48e709`; note `(start=0,duration=1080,pitch=60)`; `1 selected` visible |
| Toolbar pitch mode | PASS | `∿` button became active |
| `P` shortcut | PASS | after leaving pitch mode, `P` reactivated it; visible hint includes `V/B/E/P` |
| Create multiple signed handles | PASS | exact persisted points: `(225ms,+75¢)`, `(619ms,-75¢)`, `(900ms,+75¢)` on a 1125ms note |
| Drag one handle across others | PASS | first 225ms handle moved to 1035ms/+55¢; sorted ratios became `[0.55,0.8,0.92]`; screenshot captured while mouse was held |
| Green curve/handle rendering | PASS with usability note | 240 green pixels detected; magnified crop shows continuous segments and handles clearly, but default 15px row height makes them small |
| Alt+click delete | PASS | middle negative handle at ratio ~0.55 removed; final API curve `[(900ms,+75¢),(1035ms,+55¢)]` |
| Disk persistence | PASS | `data/projects/project_852c4e48e709.openace.json` exactly matches final API curve |
| One-step undo | PASS | deletion undo restored 3 handles |
| One-step redo | PASS | redo restored exact 2-handle post-delete state |
| Console/network health | PASS | no browser console errors or network failures |

## Supplemental backend interpolation check

A direct non-recorded Python check of `interpolated_pitch_cents` using the pre-delete curve returned exact continuous values: midpoint `(619ms,-75¢) → (900ms,+75¢)` interpolated to `0.0¢`; quarter-point was `-37.5¢`; pre-first and post-last values held at `-75¢` and `+55¢` respectively. This is supplemental script evidence, not recorded UI coverage.

## Critical-user observations

- Functional precision is good: mouse-created positions and cent signs persisted exactly as designed, crossing/reordering worked, and Alt+click deletion did not create accidental extra handles.
- At the default 15px row height, handles are only about 2–3px and vertical travel is confined to the note body. The curve is visible, but demanding users will likely need to increase row height for comfortable editing.
- There is no numeric offset/cents readout while dragging. The backend values are precise, but the user cannot see exact numeric values in the UI.
- Discovery is acceptable but not strong: the toolbar uses only the cryptic `∿` glyph; the tooltip and `P` hint help, but there is no textual label.

These are usability concerns rather than blocking functional defects.

## Artifacts

- `pitch_handles_results.json` — structured API/geometry evidence
- `browser_console.jsonl` — empty console/network health log
- `01_note_created.png`
- `02_three_pitch_handles_created.png`
- `03_drag_across_handles_held.png` — captured while drag was still held
- `04_after_crossing_drag.png`
- `05_after_alt_click_delete.png`
- `06_after_undo_delete.png`
- `07_after_redo_delete.png`
- `evidence_pitch_curve_crop_x4.png`
- `evidence_drag_held_crop_x4.png`
- `evidence_after_delete_crop_x4.png`
- `evidence_after_redo_crop_x4.png`
