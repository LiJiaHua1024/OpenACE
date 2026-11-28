# Pitch Anchor Workflow QA Report

Tested the uncommitted frontend-only ACE-style pitch-anchor workflow in visible Chrome after rebuild/restart/cache-bust (`index-BAXbrRIn.js`). No implementation files were modified. Project under test: `project_d3d67d057f15`.

## Defect found

### P2/P3 — right-click commits the anchor curve but also opens the note context menu

Exact repro:

1. Activate `∿ Anchor`.
2. Double-click a note, then left-click twice to append anchors.
3. Right-click blank/note area to end the session.

Observed backend result is correct, but the normal note context menu simultaneously opens and obstructs the canvas. Evidence: `01_rightclick_three_anchors.png` and `01_context_menu_after_rightclick_crop.png`; recorded in the video.

Likely cause: `onPointerDown` for right button calls `endAnchorSession()` and clears `anchorSessionRef`; the subsequent `contextmenu` event then sees no active session and falls through to `setMenu(...)`. `onContextMenu` has a guard for an active session, but by then the session has already been cleared.

All other tested workflow assertions passed.

## Exact workflow results

### 1. Right-click-ended creation transaction

Created out-of-order with double-click plus two clicks; right-click ended and sorted exactly:

```json
[
  {"offset_ms":125.0,"cents":-17.0},
  {"offset_ms":250.0,"cents":-50.0},
  {"offset_ms":375.0,"cents":17.0}
]
```

- Exactly three anchors: passed.
- Sorted by `offset_ms`: passed.
- Lyric editor opened: no (`lyric_editor_count=0`).
- One Ctrl+Z after commit: pitch curve exactly `[]` — passed.
- Ctrl+Shift+Z: exact three-anchor array restored — passed.
- Context menu after right-click: visible — failed/UX defect above.

### 2. Escape-ended creation variant

Second note exact sorted curve:

```json
[
  {"offset_ms":65.0,"cents":17.0},
  {"offset_ms":250.0,"cents":-17.0}
]
```

- Escape ended the session correctly: passed.
- Lyric editor opened: no — passed.

### 3. Marquee and Shift-additive selection

- Marquee around the first two note-A anchors selected them visually: passed.
- Shift marquee around note-B's first anchor added it without dropping the existing selection: passed.
- Visual evidence: selected anchors render white-filled with green outlines in `03_anchor_marquee_selection.png`, `04_anchor_shift_additive_selection.png`, and crops.

### 4. Group drag, undo/redo, geometry

Before:

```json
note_a=[
 {"offset_ms":125.0,"cents":-17.0},
 {"offset_ms":250.0,"cents":-50.0},
 {"offset_ms":375.0,"cents":17.0}
]
note_b=[
 {"offset_ms":65.0,"cents":17.0},
 {"offset_ms":250.0,"cents":-17.0}
]
```

Dragging selected note-A first anchor by dx +10 px / dy +15 px produced exactly:

```json
note_a=[
 {"offset_ms":171.0,"cents":-117.0},
 {"offset_ms":296.0,"cents":-150.0},
 {"offset_ms":375.0,"cents":17.0}
]
note_b=[
 {"offset_ms":111.0,"cents":-83.0},
 {"offset_ms":250.0,"cents":-17.0}
]
```

Measured shared selected-anchor delta: `+46 ms`, `-100 cents`.

- Selected note-A first/second anchors and selected note-B first anchor moved together: passed.
- Relative spacing preserved exactly (`125 ms` between first two selected A anchors; `33 cents` relative cents difference): passed.
- Unselected A third anchor and B second anchor unchanged exactly: passed.
- Note geometry unchanged exactly (`note_a`/`note_b` both remained `duration_ticks=480`, `pitch=65`; starts `120/600`): passed.
- Undo restored exact pre-drag arrays; redo restored exact post-drag arrays: passed.

### 5. Delete selected anchors

After Delete:

```json
note_a=[{"offset_ms":375.0,"cents":17.0}]
note_b=[{"offset_ms":250.0,"cents":-17.0}]
```

- Only selected anchors removed; unselected anchors preserved exactly: passed.
- Both notes still existed (`note_count=2`): passed.

### 6. Single existing-anchor drag regression

Remaining A anchor dragged by the same dx/dy gesture:

```json
after=[{"offset_ms":421.0,"cents":-83.0}]
expected=[{"offset_ms":421.0,"cents":-83.0}]
```

- Exact match: passed.
- Undo exact and redo exact: passed.

### 7. Alt-click deletion regression

After Alt-clicking remaining note-B anchor:

```json
note_a=[{"offset_ms":421.0,"cents":-83.0}]
note_b=[]
```

- B anchor deleted: passed.
- A anchor preserved exactly: passed.
- Both notes still existed (`note_count=2`): passed.

## Regression results

### Freehand pitch brush (`1`)

Visible brush stroke produced 16 nonzero automation points from ticks `154` through `497`, ranging `-33¢` to `-100¢`; exact array is in `anchor_workflow_stage2_results.json`.

- Automation changed from `[]`: passed.
- Existing A anchor `[{"offset_ms":421.0,"cents":-83.0}]` preserved: passed.
- Undo/redo exact: passed.

### Fixed pitch brush (`2`)

Fallback target path (no fresh render) wrote exact automation ending at readout:

```text
540 ticks · fixed target pitch -83¢
```

Result: 19 points, min `-83¢`, max `-33¢`; anchor-influenced target was copied across the swept range. Exact array is in `anchor_workflow_stage2_results.json`.

- Fixed brush changed automation correctly: passed.
- Undo/redo exact: passed.

### Pitch eraser (`3`)

Eraser sweep over ticks `304–454` produced exact zero boundaries:

```json
[
 {"ticks":304,"value":0.0,"curve":"linear"},
 {"ticks":454,"value":0.0,"curve":"linear"}
]
```

- No nonzero automation remained inside `[304,454]`: passed.
- 11 nonzero outside points remained: passed.
- Undo/redo exact: passed.

### Select/move (`V`)

- Note A moved from `start_ticks=120` to `start_ticks=60`; duration/pitch/velocity unchanged (`480/65/90`): passed.
- Undo restored exact original geometry: passed.

### Console/network/layout

- Browser console errors/warnings: none.
- Failed browser responses: none.
- Backend arrays and visual UI remained coherent throughout.

## Artifacts

- Video: `/home/ubuntu/screencasts/pitch-anchor-workflow-qa/pitch-anchor-workflow-qa-edited.mp4`
- Stage 1 exact results: `anchor_workflow_stage1_results.json`
- Regression exact results: `anchor_workflow_stage2_results.json`
- Key evidence:
  - `01_rightclick_three_anchors.png`
  - `01_context_menu_after_rightclick_crop.png`
  - `02_escape_curve.png`
  - `03_anchor_marquee_selection.png`
  - `04_anchor_shift_additive_selection.png`
  - `04_anchor_shift_additive_selection_crop.png`
  - `05_anchor_group_drag.png`
  - `05_anchor_group_drag_crop.png`
  - `06_delete_selected_anchors.png`
  - `07_alt_click_delete.png`
  - `08_regression_freehand_brush.png`
  - `09_regression_fixed_brush.png`
  - `10_regression_pitch_eraser.png`
  - `11_regression_select_move.png`
