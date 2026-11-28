# Anchor Context-Menu Suppression Retest

Tested only the previously reported defect against the current uncommitted revision after rebuild/restart/cache-bust. Loaded bundle: `index-JP2wy3ui.js`. No implementation files modified. Project: `project_f9f703f58702`.

## Result: fixed; no new defect found

### Right-click ending active anchor session

Exact repro: `∿ Anchor` → double-click note → two left clicks → right-click.

Backend curve exact and sorted:

```json
[
  {"offset_ms":125.0,"cents":-17.0},
  {"offset_ms":250.0,"cents":-50.0},
  {"offset_ms":375.0,"cents":17.0}
]
```

- Context menu count after right-click: `0` — passed.
- Lyric editor count: `0` — passed.
- Visual inspection confirms anchors visible and no menu.

### Escape still works

Exact sorted curve on second note:

```json
[
  {"offset_ms":65.0,"cents":17.0},
  {"offset_ms":250.0,"cents":-17.0}
]
```

- Escape end: passed.

### Suppression does not overreach

After waiting more than 500ms, normal right-click on a note outside an active anchor session opened the note context menu.

- Menu count: `1` — passed.
- Menu text included `Split here`, `Copy`, `Duplicate`, `Quantize`, `Vibrato…`.

### Console/network

- Browser console errors/warnings: none.
- Failed browser responses: none.

## Evidence

- Video: `/home/ubuntu/screencasts/pitch-anchor-contextmenu-retest/pitch-anchor-contextmenu-retest-edited.mp4`
- Exact results: `anchor_context_retest_results.json`
- `01_rightclick_no_context_menu.png` — anchor commit with no menu
- `02_escape_still_works.png` — Escape variant
- `03_normal_rightclick_menu.png` — normal menu still available
