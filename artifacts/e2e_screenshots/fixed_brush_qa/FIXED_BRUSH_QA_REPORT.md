# Fixed pitch brush QA

No implementation edits. Rebuilt/restarted/cache-busted `index-CXyP4vrt.js`.

No confirmed defect found, but select/velocity regressions were not completed and remain untested.

Key quantitative results:
- fallback before render: readout `fixed target pitch +72¢`; 9 nonzero points capturing anchor+vibrato target; undo empty.
- render completed and sibling `f0.json` existed.
- fresh endpoint: 200, 226 frames, 111 JSON nulls, source `fresh-rendered-f0`.
- fixed rendered brush readout `fixed rendered pitch +90¢`; 24 copied points compared with endpoint extracted F0 relative to written note; max absolute error 0.495 cents.
- mutation made endpoint return 409 stale.
- undo empty, redo exact, reload exact.
- shortcut-3 eraser removed all nonzero automation in swept range 140–430 and removed the per-note anchor; 8 outside automation points remained. Zero boundary anchors were truthfully inserted.
- brush regression changed automation and undo restored exactly; pencil created third note.
- layout clean at 1272; console/network clean.

Artifacts: fixed_brush_results.json and numbered screenshots in this directory. Recording: /home/ubuntu/screencasts/fixed-brush-qa/fixed-brush-qa-edited.mp4
