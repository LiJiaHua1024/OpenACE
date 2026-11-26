# Final backward-drag regression recheck

Targeted real-Chrome verification of the signed `snapDelta` fix, using visible Chrome driven by Playwright/CDP against `http://127.0.0.1:8787` with the CI synthesis fixture. Viewport: **1272×837**. Test project: `project_93a92fbd3ebf`.

## Result: PASS

Two notes were drawn, marquee-selected together, dragged later/up, then dragged back earlier/down.

| Stage | Note 1 `(start,duration,pitch)` | Note 2 `(start,duration,pitch)` |
|---|---:|---:|
| Initial | `(360,360,60)` | `(960,360,62)` |
| After later/up drag | `(840,360,61)` | `(1440,360,63)` |
| After earlier/down drag | `(360,360,60)` | `(960,360,62)` |

- Forward movement: exact `+480 ticks` and `+1 semitone` for both notes.
- Reverse movement: exact restoration of original start time, duration, and pitch for both notes.
- Selection: `2 selected`.
- Final note count: 2.
- Browser console errors: none.
- Network failures: none.

![Final restored piano-roll state](https://app.devin.ai/attachments/f91f0983-aca7-4237-ae2a-1bef0169e952/final_recheck_restored.png#w=1272&h=837)

Artifacts:

- Screenshot: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/piano_depth_qa/final_recheck/final_recheck_restored.png`
- Machine-readable results: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/piano_depth_qa/final_recheck/final_recheck_results.json`
- Recording: `/home/ubuntu/screencasts/rec-31d0a28f-c969-4e2a-99f4-04bc062cd6de/rec-31d0a28f-c969-4e2a-99f4-04bc062cd6de-edited.mp4`
