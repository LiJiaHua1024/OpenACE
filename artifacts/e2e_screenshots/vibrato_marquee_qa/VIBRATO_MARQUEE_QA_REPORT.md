# Vibrato Marquee Selection/Deletion QA

Visible-Chrome QA of the uncommitted multi-vibrato marquee implementation after rebuild/restart/cache-bust (`index-Dt_n0Wuv.js`). No implementation files modified.

## Result

No product defect found. All requested final assertions passed.

## Exact seeded objects

```json
va={"start_ratio":0.25,"depth_cents":45,"frequency_hz":5.2,"phase":0,"attack_ratio":0.2,"release_ratio":0.1}
vb={"start_ratio":0.3,"depth_cents":60,"frequency_hz":4.8,"phase":0.5,"attack_ratio":0.1,"release_ratio":0.25}
vc={"start_ratio":0.2,"depth_cents":75,"frequency_hz":6,"phase":0.75,"attack_ratio":0.3,"release_ratio":0.2}
vd={"start_ratio":0.35,"depth_cents":50,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.15,"release_ratio":0.3}
ve=null
```

Initial note count: `5`; all notes `duration_ticks=480`, `pitch=65`, starts `120/600/1200/1800/2400`.

## Marquee and deletion

- Blank-space marquee intersecting A/B spans visually selected both with white/green highlight and dashed span outline.
- Shift-additive marquee added C while preserving A/B; D remained visually unselected.
- Escape cleared the visual selection; pressing Delete afterward changed nothing.
- Switching away from `∿ Vib` and back cleared the tool-specific selection; pressing Delete afterward changed nothing.

After reselecting A/B/C and pressing Delete:

```json
va=null
vb=null
vc=null
vd={"start_ratio":0.35,"depth_cents":50,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.15,"release_ratio":0.3}
ve=null
```

- Only selected vibrato objects were cleared: passed.
- Note count stayed `5`: passed.
- All note starts/durations/pitches/velocities stayed exactly unchanged: passed.
- One undo restored all exact original vibrato objects: passed.
- Redo deleted A/B/C again exactly while preserving D: passed.
- Reload after redo/delete preserved the exact deleted state: passed.

Exact before/after/undo/redo/reload JSON is in `vibrato_marquee_main_results.json`.

## Regression results

These were retested in a fresh clean project after explicitly activating `∿ Vib` with its toolbar button (`vibrato_marquee_regression_results.json`).

### Handle regressions on preserved vibrato

Before:

```json
{"start_ratio":0.35,"depth_cents":50,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.15,"release_ratio":0.3}
```

After depth handle drag:

```json
{"start_ratio":0.35,"depth_cents":80,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.15,"release_ratio":0.3}
```

After attack handle drag:

```json
{"start_ratio":0.35,"depth_cents":80,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.35,"release_ratio":0.3}
```

After release handle drag:

```json
{"start_ratio":0.35,"depth_cents":80,"frequency_hz":5.5,"phase":0.25,"attack_ratio":0.35,"release_ratio":0.5}
```

All exact expectations passed; unrelated parameters preserved.

### Direct creation regression

Right-to-left drag created exactly:

```json
{"start_ratio":0.23214285714285715,"depth_cents":30,"frequency_hz":5.2,"phase":0,"attack_ratio":0,"release_ratio":0}
```

Undo removed it; redo restored it exactly.

### Blank-click regression

A blank click without meaningful drag produced no phantom edit: vibrato map, geometry, and note count were exactly unchanged (`note_count=2`).

### Console/network

No browser console errors/warnings and no failed network responses.

## Harness note

The first regression attempt after reload accidentally continued in the default non-vibrato tool because the harness did not reactivate `∿ Vib`; that harness mistake created extra temporary notes in the test project. It was not a product result. The regression tests were rerun cleanly with the toolbar button explicitly active (`tool active`), and the corrected results above are the valid regression evidence.

## Key artifacts

- `01_marquee_ab.png` / crop
- `02_shift_additive_abc.png` / crop
- `03_escape_cleared.png` / crop
- `04_selected_before_delete.png` / crop
- `05_after_delete.png` / crop
- `08_correct_handle_regressions.png`
- `09_correct_direct_create.png`
- `vibrato_marquee_main_results.json`
- `vibrato_marquee_regression_results.json`
