# Grid Alignment QA Report

Focused retest of the uncommitted grid-alignment fix in visible Chrome after backend restart and cache-busted production build. Implementation was not modified or committed.

## Results

All focused checks passed. Console errors, page errors, and failed network responses were empty.

| Check | Exact evidence | Result |
|---|---|---|
| Piano ruler seek at Grid `1/4` | Clicked ruler at raw tick ≈1170. Playhead became `1.3.1` / `00:01.00`, corresponding exactly to tick `960` at PPQ 480 / 120 BPM. | **PASS** |
| Piano ruler seek at Grid `1/32` | Same raw tick ≈1170. Playhead became `1.3.3` / `00:01.25`, corresponding exactly to tick `1200`. | **PASS** |
| Piano visual subdivisions at `1/4` | Pixel scan immediately after selector change, without reload/edit: centers `511.5, 623.5, 735.5, 847.5, 959.5`; every spacing exactly `112 px` = 480 ticks. | **PASS** |
| Piano visual subdivisions at `1/32` | Immediate scan: 38 adjacent grid-line groups with every measured spacing exactly `14 px` = 60 ticks. | **PASS** |
| Automation visual subdivisions at `1/4` | Immediate scan: centers `511.5, 623.5, 735.5, 847.5, 959.5`; every spacing exactly `112 px`. | **PASS** |
| Automation visual subdivisions at `1/32` | Immediate scan: 38 adjacent grid-line groups with every measured spacing exactly `14 px`. | **PASS** |
| Normal note editing regression | Existing note `audit_n2` dragged left one 1/32 step: backend exact `start_ticks 480→420`, duration stayed `480`. Ctrl+Z restored exact `start=480`, `duration=480`. | **PASS** |
| Console/network | No console errors, page errors, or failed network responses. | **PASS** |

## Evidence

- `10_piano_automation_grid_comparison.png` — direct visual comparison of immediate spacing changes
- `grid_alignment_results.json` — exact machine-readable measurements
- `00_grid14_visual.png`
- `01_grid14_ruler_seek.png`
- `02_grid32_visual.png`
- `03_grid32_ruler_seek.png`
- `04_note_drag_grid32.png`
- `05_note_drag_undo.png`

Recording: `/home/ubuntu/screencasts/grid-alignment-qa/grid-alignment-qa-edited.mp4` (produced when recording stops)
