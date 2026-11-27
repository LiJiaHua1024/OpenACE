# Tempo Ramp Browser QA

## Verdict

Core ramp-shaped tempo transitions pass in real visible Chrome at exact `1272×837`: the linear tempo line visibly slopes, backend JSON preserves `curve: "linear"`, drag/undo/redo/reload preserve the curve, and transport progression measurably differs from step mode.

One confirmed UI usability defect remains: the floating tempo editor can cover the selected positive-tick endpoint. In the original `1920/180` position, the endpoint was underneath the editor, so a direct drag grabbed the BPM input/spinner instead of the tempo point.

## Quantitative evidence

- Step-mode canvas scan slope: `-0.000196 px/x` — effectively flat.
- Linear-mode canvas scan slope: `-0.059445 px/x` — clearly sloped.
- Linear-mode sample y positions: `(70,38.5) → (190,31.5) → (310,24) → (430,17)`.
- Backend after selecting linear: `[{ticks:1920,bpm:180,curve:"linear"}]`.
- Real unobscured drag: `960/180 → 1080/174.4`, backend still `curve:"linear"`.
- Undo: `1080/174.4 → 960/180`, still linear.
- Redo: `960/180 → 1080/174.4`, still linear.
- Final reload backend: `[{ticks:1080,bpm:174.4,curve:"linear"}]`.
- Transport over approximately `1.70s` wall time:
  - step mode: musical position `1.4.2`
  - linear ramp: musical position `2.1.1`
- Final clean reload: no console messages and no network failures.
- Layout: `innerWidth=1272`, `innerHeight=837`, no body overflow.

## Confirmed implementation defect

**Selected endpoint can be occluded by its own editor overlay.**

Measured geometry for the original endpoint:

- endpoint canvas-relative position: `x=512`, `y=13`
- editor overlay spans canvas-relative `x=443.73..706`, `y=6..52`

Therefore the point lies entirely inside the overlay. A real mouse drag at the endpoint focused/grabbed the BPM input instead of moving the point; the backend remained `1920/180 linear`. After moving the point to an unobscured location, the same real drag worked correctly and preserved linear mode. This is a UI hit-target/overlay placement defect, not a tempo-model defect.

## Environment note

The first attempt exposed a stale-backend setup artifact: because the Python server does not hot reload, the old process stripped the new `curve` field during validation. After restarting the fixture backend cleanly, `curve:"linear"` persisted correctly. This is not counted as an implementation defect.

## Evidence files

- `00_step_baseline.png` — flat step-mode baseline.
- `01_linear_ramp_slopes.png` — visibly sloped linear ramp.
- `02_overlay_blocks_direct_drag.png` — defect evidence: mouse drag lands in BPM input under overlay.
- `02_point_moved_to_960_for_drag.png` — point moved away from overlay for isolated drag test.
- `03_drag_held_linear_preserved.png` — real drag while held: `1080/174.4`, curve linear.
- `03_drag_released_linear_preserved.png` — released drag state persisted.
- `04_reload_curve_editor_linear.png` — after reload, reselected point still shows linear ramp.
- `04_reload_curve_persistence.png` — final clean reload slope.
- `05_linear_transport_playing.png` — transport advancing in ramp mode.
- `tempo_ramp_results.json` — curated machine-readable evidence.
- `tempo_ramp_results_raw.json` — raw pre-curation measurements.

## Overlay fix regression

Passed. With the endpoint reset to `1920/180 linear`, selecting it now renders the editor with class `tempo-editor left`. The editor occupies canvas-relative `x=72..334.27`, while the endpoint is at `x=512,y=13`, so there is no overlap. A real direct mouse drag from the endpoint changed it to `2040/174.8` and backend JSON preserved `curve:"linear"`. Exact viewport remained `1272×837` with no body overflow.

Evidence: `overlay_fix_regression.png`.
