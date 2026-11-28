# Global Creative-Loop Audit After Playback/Range Export Commits

Date: 2026-11-28  
Branch: `devin/1795696369-dynamic-expression`  
Project: `project_706a0c233a5d`  
Frontend: rebuilt production bundle `index-Dr9rn0Vr.js`; cache-busted URLs  
Backend: restarted fixture backend  
Implementation modified: no

## Verdict

**No new reproducible product defects found.** Console errors/warnings and failed browser network responses were zero in the broad audit and supplement.

Two initially red broad-harness results were harness artifacts, not product defects:

- only two of three notes were created because the first reused low piano-roll coordinate landed in the velocity/bottom interaction zone; downstream editing/render worked
- lyric mismatch was downstream of that missing note

The initial loop/metronome supplement also toggled already-enabled controls off; a corrected explicit-state test proved loop wrapping and metronome scheduling.

## Broad creative loop evidence

Passed:

- project creation and transport layout: no overflowing/wrapped transport controls at `1280×841`
- piano-roll note creation/editing, drag, lyric editing, generated phonemes
- transpose controls exact round trip `[64,68] → [65,69] → [64,68]`
- pitch/air/tension automation: 13 points each
- Ctrl+wheel zoom `112 → 136`
- real file-chooser reference/source upload
- fixture vocal render completed
- Vocal2BGM generated exactly one accompaniment clip before repaint
- Alt-drag repaint range visibly yellow while held, numeric range `0.54–1.31s`
- repaint replacement exactly one accompaniment clip labeled `Repaint`
- SVC completed and produced an SVC clip
- playback advanced `00:00.00 → 00:01.21`
- WAV/MP4/MID/LRC/USTX/SVP/VPR downloads all nonzero
- MCP-added note appeared live through SSE as `3 notes STALE RENDER`
- browser console/network clean

## Supplemental current-surface evidence

Passed:

- arrangement-ruler loop range persisted exactly `{start:960,end:1920,enabled:true}`
- corrected loop test wrapped visibly/quantitatively: `1.89 → 1.27s` and `1.68 → 1.08s`
- metronome enabled state active; 16 oscillator starts observed during playback
- export range hrefs correct: audio/stem formats include `start_ticks=960&end_ticks=1920`; MP4/interchange omit range
- range WAV exactly `1.000000s`; FLAC exactly `1.000000s`; OGG exactly `1.000000s`; MP3 `1.032s` codec padding; stems manifest exact range metadata
- audio imported as arrangement clip `clip_c403e6a82966` at tick `1092`
- media bin visible with actionable Tags/Add/Delete controls
- separation completed: `job_58b8110d67d7`, exact `clip_id`, `0.0–2.5s`, arrangement start `1092`; two separated tracks created
- project manager search found matching Creative Loop rows and exposed pin/tag/folder/copy/delete actions
- no visual overlap/dead control/missing link found in reviewed screenshots

## Artifacts

- `final_qa_results.json`
- `global_postrange_supplement_results.json`
- `loop_metronome_corrected.json`
- `compressed_range_results.json`
- screenshots `00`–`20` in this directory
- downloads in `downloads/`
