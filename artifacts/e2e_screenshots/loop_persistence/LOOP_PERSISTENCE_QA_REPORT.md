# Per-project loop playback persistence QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`, backend restarted in fixture mode, frontend rebuilt/cache-busted. Real ruler drags, transport clicks, project manager actions, project switching, piano-roll note drawing, undo/redo buttons, reloads, SSE updates, canvas instrumentation, backend JSON inspection, and `AudioBufferSourceNode.start` instrumentation were used. No implementation files were modified.

## Result

No implementation defect confirmed. The raw matrix reported **14/16** because two checks were harness measurement false negatives; both were resolved by direct screenshot/supplemental timing evidence:

1. The undo/redo loop-band instrumentation marker was taken after the canvas redraw, so it missed an already-painted band. The captured screenshot clearly shows the cyan `loop` band still present after note redo while backend metadata remains exact.
2. The first metadata-toggle probe stopped too close to the one-second loop boundary. A focused supplement with playhead sampling captured the natural restart and proved no immediate audio-graph rebuild.

## Verified behavior

- Exact viewport/fixture: passed (`1272×837`, rendered nine-lane project).
- Dragging the ruler loop `0–480` wrote backend `metadata.playback_loop` exactly as `{start:0,end:480,enabled:true}`.
- Cyan band measured exactly x `64`, width `112px` for `480` ticks at `112px/beat`.
- Reload restored exact range+enabled state and redrew the cyan band.
- Toggle off persisted `{enabled:false}` across reload while retaining the range and subdued band.
- Toggle back on persisted `{enabled:true}` across reload.
- New project had no `playback_loop`, no cyan band, and inactive Loop button.
- Switching back to the original project restored its exact loop.
- Natural project duplication copied exact loop metadata and showed the loop in the duplicate.
- Deleting the duplicate fell back to a loop-less project without retaining stale loop UI/state.
- Loop-only changes did not create an undo entry: Undo was disabled after loop creation/project reopen. Drawing a third note enabled Undo; Undo removed it (`3→2`), Redo restored it (`2→3`), and loop metadata remained exact throughout.
- SSE project updates applied loop enabled off/on without reload; subdued/enabled bands redraw correctly.
- Playback loop `0–480` still cycled after all persistence operations: 5 source starts, intervals `0.5224, 0.4992, 0.4876, 0.4992`, mean `0.5021s`, stdev `0.0127s`.
- Metadata-only toggle supplement on a `0–960` loop: no start occurred immediately after toggles; first restart occurred `1186.7ms` after playback start / `281.5ms` after re-enable, consistent with natural loop-boundary restart rather than metadata graph rebuild.
- Layout, console, HTTP, and network were clean. Only expected `/api/events` aborts occurred during intentional reloads.

## Key evidence

- `00_dragged_loop_enabled.png`
- `01_reload_restores_loop.png`
- `02_reload_loop_disabled_range_retained.png`
- `03_new_project_no_loop.png`
- `04_switch_back_loop_restored.png`
- `05_duplicate_project_loop_copied.png`
- `06_deleted_duplicate_fallback_no_stale_loop.png`
- `07_note_undo_redo_loop_preserved.png`
- `08_sse_loop_state_applied.png`
- `09_loop_cycles_after_persistence.png`
- `10_graph_toggle_supplement.png`
- `loop_persistence_results.json` — raw matrix including the two harness false negatives
- `graph_rebuild_supplement.json` — focused metadata-toggle timing supplement
