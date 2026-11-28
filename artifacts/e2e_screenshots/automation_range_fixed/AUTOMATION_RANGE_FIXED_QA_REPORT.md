# Automation range clipboard fix QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`, backend restarted in fixture mode, frontend rebuilt/cache-busted. Real mouse Shift-drags/clicks/tool gestures were used. Backend project JSON was inspected for exact ticks, values, and curves. No implementation files modified.

## Result: 18/18 checks passed

### Exact defect reproductions

- Dragging tick `500 → 950` now produces a snapped `480–960` selection labeled `480t`; cyan band width is `112px`, exactly one beat/four sixteenths at `112px/beat`.
- Source dynamic interior point `720` had `curve: "step"`; pasted corresponding target point `1440` is exactly `curve: "step"`.

### Boundary interpolation and paste exactness

The fixture used off-grid outer points `450=0.2` and `990=0.3`, so snapped boundaries still required interpolation:

- start `480`: `0.32000000000000006` (expected `0.32`), linear
- interior `600→target1320`: `0.8`, linear
- interior `720→target1440`: `0.4`, step
- interior `840→target1560`: `0.9`, linear
- end `960→target1680`: `0.41999999999999993` (expected `0.42`), linear

Paste at imperfect playhead `1225` snapped to tick `1200`; target-range collision `1200=0.7` was replaced. Repeated paste did not duplicate points.

### Regression coverage

- Shift micro-drag below one grid cell creates no selection.
- Undo restores exact pre-paste dynamic automation; redo and reload persist pasted automation.
- Range delete removes target interior/boundary points; undo restores them.
- Copy Dynamic then switch Air hides Paste due lane mismatch.
- Pitch copy/paste preserves exact `-100`, `+100`, `-50` values.
- Brush, Line, and Erase regressions pass on Energy.
- Compact controls remain inside reserved gutter (`left 4`, `right 60` within 64px); header `714/714`, no overflow.
- Breath & Phoneme lane switches cleanly and range controls are hidden.
- Console, HTTP, and network are clean.
