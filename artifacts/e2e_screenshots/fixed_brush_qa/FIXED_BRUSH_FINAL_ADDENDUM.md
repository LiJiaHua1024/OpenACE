# Fixed brush final addendum

No defect found; implementation untouched. Rebuilt/restarted bundle `index-Cgo0UEJu.js`.

- Rendered fixed brush remained accurate: 38 compared points, max absolute difference 4.17 cents vs extracted rendered F0 relative to written note (within reasonable extraction/rounding tolerance for vibrato-copying QA).
- Dense sampling: 37 points within swept 180–520 tick span; no runaway point explosion beyond stroke rewrite behavior (16 preexisting → 38 total).
- Edited/stale state: endpoint 409 and dark-curve matching pixels 0.
- Undo exact pre-stroke input: endpoint returned 200 and dark-curve matching pixels recovered to 420.
- Redo exact edited stroke: endpoint returned 409.
- Shortcut-3 eraser regression: no nonzero continuous automation remained inside 180–520.

Artifacts: `fixed_brush_final_results.json`, `30_final_stale_hidden.png`, `31_final_undo_fresh_visible.png`.
