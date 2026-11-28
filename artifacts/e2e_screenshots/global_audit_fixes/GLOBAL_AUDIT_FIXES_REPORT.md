# Global Audit Fixes Retest Report

Focused retest of the uncommitted fixes for the prior global workflow audit. Backend restarted with CI fixture enabled; frontend production build completed and browser was cache-busted. Implementation was not modified or committed.

## Results

All focused checks passed. Console errors, page errors, and failed network responses were empty.

| Original defect | Verification | Exact evidence | Result |
|---|---|---|---|
| Reload opened first pinned project | Opened `project_c4bccc903fcc` / **Global Workflow Audit**, reloaded browser | selected ID remained `project_c4bccc903fcc`; title remained `Global Workflow Audit`; `localStorage.openace_current_project_id=project_c4bccc903fcc` | **PASS** |
| Ctrl+Shift+Z did not redo | Time signature 4/4 → 3/4, Ctrl+Z, Ctrl+Shift+Z, then Ctrl+Z/Ctrl+Y regression | after Ctrl+Z `4/4`; after Ctrl+Shift+Z `3/4`; after second Ctrl+Z `4/4`; after Ctrl+Y `3/4`; final Ctrl+Z `4/4` | **PASS** |
| New track not selected | Clicked `+ Vocal` | track count `4→5`; new `track_1083c4f5-e6f` / `Vocal 5`; selected card exactly `Vocal 5`; Undo restored count `4` | **PASS** |
| Escape did not close Project manager | Opened Projects, pressed Escape | backdrop+popover count `2→0`; track list clickable afterward | **PASS** |
| Media drag hard-snapped to quarter | Grid `1/32`, dragged `steady440_20.wav` to raw tick ≈330 on Reference Audio | exactly one added clip: `track_audit_audio`, `start_ticks=360`, label `steady440_20` | **PASS** |
| Alt fine media drop regression | Alt-dragged same media to raw tick ≈330 | exactly one added clip: `track_audit_audio`, `start_ticks=330` | **PASS** |
| Add at playhead always created track | Selected existing `Reference Audio`, sought tick 960, clicked Media Bin → Add at playhead | track count stayed `4→4`; exactly one added clip in `track_audit_audio` at `start_ticks=960`; Reference Audio clip count became `5` | **PASS** |
| Transport clipped at 1600 px | Measured all transport children at viewport width 1600 | max right edge `1588`; Import audio right edge `1588`; no overflowing elements; body scroll width `1600` | **PASS** |

## Evidence files

- `global_audit_fixes_results.json` — exact machine-readable results
- `00_reload_restores_current_project.png`
- `01_transport_geometry.png`
- `02_ctrl_shift_z_redo.png`
- `03_new_track_selected.png`
- `04_project_manager_escape_closed.png`
- `05_media_drag_snap360.png`
- `06_alt_media_drag_raw330.png`
- `07_media_add_selected_track.png`
- `08_final_overview.png`

Recording: `/home/ubuntu/screencasts/global-audit-fixes-retest/global-audit-fixes-retest-edited.mp4`
