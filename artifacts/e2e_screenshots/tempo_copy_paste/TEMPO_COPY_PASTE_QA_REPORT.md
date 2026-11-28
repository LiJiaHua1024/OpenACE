# Tempo Copy/Paste Focused Browser QA

Date: 2026-05-15  
Surface: real visible Chrome through Playwright/CDP, exact viewport `1272×837`  
Frontend: rebuilt and cache-busted; implementation unchanged by QA  
Fixture: positive tempo points at 480/150 step, 720/130 step replacement target, and 960/90 linear

## Result

All requested focused checks passed. No tempo copy/paste implementation defect was confirmed.

## Evidence summary

- Exact viewport/layout: `1272×837`; body `1272/1272`; arrangement `714/714`, height `166`; tempo lane `714/714`, height `54`.
- Step source editor showed tick `480`, BPM `150`, curve `step`; Copy and Paste controls were present.
- Copied step point and moved playhead to snapped tick `240`; paste created exactly one point at `240` with BPM `150.0` and curve `step`, and the editor selected it.
- Linear source editor showed tick `960`, BPM `90`, curve `linear`.
- Copied linear point and pasted over existing target tick `720` that was previously BPM `130` step. Result was exactly one point at `720` with BPM `90.0` and curve `linear`; no duplicate remained.
- The tempo lane screenshot showed the expected diagonal linear ramp into tick `720`.
- Undo restored exactly one tick-`720` point with BPM `130.0` and curve `step`.
- Redo reapplied exactly one tick-`720` point with BPM `90.0` and curve `linear`.
- Reload preserved the full positive tempo map exactly: `240/150 step`, `480/150 step`, `720/90 linear`, `960/90 linear`.
- After reload, selecting tick `720` showed BPM `90` and curve `linear` in the editor.
- Tempo editor measured `400.3×46px`, inside tempo lane `714×54`; internal `scrollWidth 398 <= clientWidth 398`; no lane/arrangement overflow.
- Console messages: `0`; HTTP errors: `0`; network failures: only two expected `/api/events net::ERR_ABORTED` entries caused by intentional navigation/reload.

## Files

- Recording: `/home/ubuntu/screencasts/tempo-copy-paste-qa/tempo-copy-paste-qa-edited.mp4`
- Machine results: `tempo_copy_paste_results.json`
- Key screenshots: `00` through `11` in this directory, especially:
  - `04_lane_after_step_paste.png`
  - `07_lane_after_linear_replace.png`
  - `10_final_reload_editor.png`
