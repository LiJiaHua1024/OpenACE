# Dedicated tempo editor strip QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`, backend restarted in fixture mode, frontend rebuilt/cache-busted. Real mouse/keyboard interactions, backend persistence checks, canvas hit inspection, undo/redo/reload, layout measurements, and dense-point supplemental inspection. No implementation files modified.

## Result: all requested checks passed

### Original overlay reproduction

With positive points `480/720/960`, after selecting `480` then Ctrl-selecting `720`, tick `960`'s original coordinate `(524, 258.52)` hit-tested `CANVAS` rather than `.tempo-editor`. A real Ctrl-click selected it additively and backend tempo points were byte-for-byte unchanged, proving no number-input spinner mutation.

### Lane/canvas geometry at exact viewport

- Collapsed/no selection: tempo lane `55px` including border; canvas exactly `54px`.
- Expanded/selected: lane `106px`; canvas still exactly `54px`; editor begins at canvas bottom y `278` and ends y `324`, so it is fully below the graph.
- Exact body remained `1272/1272`; no horizontal overflow or layout overlap.
- Screenshots: `12_lane_expanded_editor_below.png`, `13_lane_collapsed_no_selection.png`.

### Dense-point inspection

Dense fixture: 13 positive points every `120` ticks from `480` through `1920`. After selecting tick `960`, all 13 visible point centers hit-tested canvas; zero hit-tested the editor. Evidence: `14_dense_zero_covered.png`, `layout_dense_supplement.json`.

### Regression matrix: 19/19 passed

- exact viewport/fixture
- normal click/primary editor
- original tick-960 hit target canvas
- real Ctrl-click at 960 without mutation
- Ctrl additive 3-point selection and white visuals
- Ctrl toggle off
- Shift inclusive range with clicked point primary
- Copy 3 / paste at snapped playhead with exact spacing `0/+240/+480`, BPM `150/100/90`, curves `step/linear/step`, collision replacement
- undo exact pre-paste state and redo exact post-paste state
- reload persistence
- group delete button
- right-click single delete and selected-group delete
- single-point drag regression
- numeric tick/BPM/curve editing regression
- zero-tick anchor behavior
- geometric layout overflow check
- console/network/HTTP cleanliness (only expected SSE aborts on reload)
