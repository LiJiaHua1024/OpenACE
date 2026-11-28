# Export Range Reset Recheck

Date: 2026-11-28  
Bundle: `index-Dr9rn0Vr.js`  
Implementation modified: no

## Result

The P4 cosmetic defect is fixed.

## Evidence

- Loop project initially set to `loop`; WAV href correctly included `?start_ticks=960&end_ticks=1920`.
- After switching to no-loop project `project_2d8c09379db6`:
  - selector value automatically became `full`
  - loop option remained disabled
  - warning count was `0`
  - WAV href was exactly `/api/projects/project_2d8c09379db6/export/wav` with no range query
- After switching back and reselecting loop:
  - WAV/STEMS range query returned exactly
  - MP4 remained full-length with no query
- Quick normal export regression on the audible loop project:
  - full-mode WAV href exactly `/api/projects/project_a67d2d8bc025/export/wav`
  - downloaded full WAV `1,155,044` bytes / `4.010417s`
- Console errors/warnings: zero. Failed browser network responses: zero.

Note: an intermediate download from the intentionally empty no-loop project was a valid 44-byte zero-length WAV header, not a failure of the regression. The meaningful audible-project export above supersedes it.

## Files

- `07_recheck_loop_project_range_selected.png`
- `08_recheck_no_loop_auto_full.png`
- `09_recheck_back_loop_range_returns.png`
- `range_reset_recheck_results.json`
- `downloads/recheck_full_audible.wav`
