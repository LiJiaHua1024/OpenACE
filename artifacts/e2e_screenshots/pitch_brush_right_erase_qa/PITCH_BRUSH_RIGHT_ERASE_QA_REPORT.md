# Pitch brush right-click erase QA

No defects found; implementation untouched. Rebuilt/restarted `index-CjLmKK1s.js`.

Exact evidence:
- seeded 13 automation points: `+100¢` at 180/253/327/401/474/548 and `-200¢` at 1209/1283/1356/1429/1503/1576/1650.
- right-drag `350→520` produced zero anchors exactly `350` and `520`.
- interior nonzero points after erase: `[]`.
- outside points preserved exactly.
- center interpolation `100¢ → 0¢`.
- no `.piano-context-menu` in pitchBrush mode (`count=0`).
- one Ctrl+Z restored seeded array exactly; redo restored erased array exactly.
- left brush afterward changed automation (`13 → 18` points).
- select-mode right click still opened context menu (`count=1`).
- console/network clean.

Artifacts: `right_erase_results.json`, `01_right_erased.png`, `02_select_context_menu.png`; recording `/home/ubuntu/screencasts/pitch-right-erase-qa/pitch-right-erase-qa-edited.mp4`.
