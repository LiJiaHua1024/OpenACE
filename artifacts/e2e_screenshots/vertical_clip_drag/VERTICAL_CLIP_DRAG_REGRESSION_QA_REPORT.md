# Vertical Clip Drag Regression QA

Date: 2025-11-27  
Scope: fixed vertical cross-track drag source lookup and dynamic arrangement height.  
Environment: real visible Chrome over CDP, exact viewport `1272×837`, backend `127.0.0.1:8787`, rebuilt frontend (`tsc && vite build` succeeded), cache-busted URLs. No implementation files were modified.

## Verdict

The two primary fixed defects are corrected:

- Held-drag reversal now follows the pointer back to the original lane.
- Horizontal adjustment remains live after vertical migration.
- The arrangement now dynamically expands to `166px` for four lanes, making the accompaniment lane and its clip visible/editable.

Multi-track spacing, selection remap, copy/delete/undo, live playback reconstruction, console/network, and exact-layout checks passed in the final clean run.

Two notes remain:

1. **Specification mismatch, not implementation failure:** at the current zoom/grid (`112px/beat`, `480ppq`, `120`-tick quantization), `+56px` is `240` ticks, so the mathematically correct result is `480→720`. The requested `480→600` corresponds to `+28px` (`120` ticks). I verified both: `+56px→720` and `+28px→600`.
2. **Minor residual context-menu positioning defect:** the arrangement context menu is still clamped using the old hardcoded `132px` height. When right-clicking a clip in lane 2 at relative Y `109`, the menu appears at relative Y `1` instead of approximately Y `38` for the new `166px` arrangement height. It remains usable, but it is visually detached from the click and overlaps the top of the arrangement/transport area.

## Final regression results

| Check | Result | Evidence |
|---|---:|---|
| Exact viewport | PASS | `1272×837` |
| Dynamic arrangement height | PASS | wrapper/canvas `166px`, expected minimum `166px` |
| Fourth lane visible | PASS | `C1` fully visible in lane 3 |
| Fourth-lane clip editable | PASS | `C1` horizontal drag `480→600`; undo restored `480` |
| Held-drag reversal | PASS | drag down then return before mouseup ended in original track 0/start `480` |
| Horizontal adjustment after vertical migration, `+56px` | PASS with corrected expectation | ended track 2/start `720` (`+240` ticks, mathematically correct) |
| Horizontal adjustment yielding requested `480→600` | PASS | `+28px` produced track 2/start `600` |
| Bottom clamp group spacing | PASS | `A1` track2/start480, `B1` track3/start1440 |
| Top clamp group spacing | PASS | `A1` track0/start480, `B1` track2/start1440 |
| Selection remap/repeated drag | PASS | repeated down drag restored `A1` track2 and `B1` track3 |
| Copy/paste | PASS | two unique pasted IDs, tracks `{2,3}`, starts `1680/2640`, spacing `960` |
| Context delete | PASS | both pasted clips removed |
| Undo after delete | PASS | exactly the same two pasted IDs/tracks/starts restored |
| Live playback reconstruction | PASS | sources `created 5→10`, `start 5→10`, `stop 0→5`; first stop/create at `202.6/202.7ms`; decode count stayed `1`; zero start/stop errors |
| Body/sidebar/transport overflow | PASS | body `1272/1272`, sidebar `235/235`, transport `1272/1272` |
| Console/HTTP | PASS | zero console messages; zero HTTP errors |
| Network failures | PASS with expected noise | only `/api/events net::ERR_ABORTED` entries caused by intentional reloads/navigation |
| Context menu position in taller arrangement | **FAIL (minor)** | click relative Y `109`; menu relative Y `1`; dynamic height `166` |

## Harness note

During diagnosis, taking a CDP screenshot while the mouse was still held altered input timing enough to invalidate multi-selection evidence. The final clean run avoids mid-drag screenshots for the multi-select sequence; the screen recording supplies the visual held-drag evidence, and after-state screenshots/backend snapshots supply the assertions.

## Key artifacts

- Final recording: `/home/ubuntu/screencasts/vertical-drag-regression-final/vertical-drag-regression-final-edited.mp4`
- Final results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/vertical_clip_drag_regression_results_v3.json`
- Context-menu geometry probe: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/context_menu_geometry_probe.json`
- Four-lane layout: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_00_four_lanes_visible.png`
- Reverse-path evidence: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_04_reverse_path_after.png`
- Horizontal-adjustment evidence: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_06_vertical_then_horizontal_after.png`
- Paste evidence: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_12_after_paste.png`
- Live reconstruction: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_14_live_reconstruction.png`
- Final layout: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_15_final_layout.png`
