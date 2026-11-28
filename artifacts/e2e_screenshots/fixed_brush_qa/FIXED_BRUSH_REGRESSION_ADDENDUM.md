# Fixed brush regression addendum

No defects found; implementation untouched.

- Fresh rendered-F0 endpoint: 200.
- Objective dark-curve pixel evidence (near expected blended `#101927e8` color): fixed 454, freehand brush 454, eraser 454 while fresh.
- After fixed-brush mutation endpoint became 409 stale; matching dark-pixel count dropped to 26 and fixed-vs-stale crop had 343 materially changed pixels. Visual inspection agrees curve is present fresh and hidden stale.
- Select/move regression passed: note moved then undo restored exactly.
- Velocity regression passed: 90 → 124.

Artifacts: `fixed_brush_regression_addendum_results.json`, `20_darkcurve_{fixed,brush,eraser}.png`, `21_darkcurve_stale_hidden.png`. Recording `/home/ubuntu/screencasts/fixed-brush-regression-addendum/fixed-brush-regression-addendum-edited.mp4`.
