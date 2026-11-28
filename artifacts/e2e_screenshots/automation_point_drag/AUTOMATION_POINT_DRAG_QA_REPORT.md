# Automation Point Drag QA

Focused visible-Chrome regression after backend restart/cache-bust on reset `Snap Grid QA`. Implementation was not modified.

## Assertions

- **Line tool creation:** passed — Volume line created exactly two endpoints at ticks `480` and `960`; backend values were `0.7999998900267455` and `0.2999998900267455` due continuous canvas-coordinate mapping.
- **Direct point dragging:** passed — Brush drag moved the second point to exact snapped `ticks=1260`, backend value `0.599999780053491` at 1/32 grid.
- **Undo/redo transaction:** passed — one undo restored `960 / 0.2999998900267455`; redo restored exact dragged `1260 / 0.599999780053491`.
- **Reload persistence:** passed — final Volume curve remained exactly `480 / 0.7999998900267455` and `1260 / 0.599999780053491`.
- **Bipolar clamp:** passed — Pan point dragged beyond top clamped exactly to `+1.0`; dragged beyond bottom clamped exactly to `-1.0`.
- **Right-click delete:** passed — right-click removed the dragged Volume point; one undo restored it exactly.
- **Right-click empty canvas:** passed — no stray point created; point list unchanged.
- **Erase regression:** passed — erase tool removed the selected Volume point.
- **Shift range regression:** passed — Shift+drag at 1/32 displayed exact `60t`.
- **Layout/console/network:** passed — no horizontal overflow, console errors, page errors, or failed network responses.

No defects found.

## Evidence

- `automation_point_drag_results.json`
- `00_volume_line_created.png` through `10_shift_range.png`
