# Vertical Cross-Track Arrangement Clip Drag QA

Date: 2025-11-27  
Scope: uncommitted vertical cross-track arrangement clip dragging, arrangement multiselect interaction, trim/fade/horizontal regression, and live playback reconstruction.  
Environment: real visible Chrome over CDP, exact viewport `1272×837`, backend `127.0.0.1:8787`, rebuilt frontend (`tsc && vite build` succeeded), cache-busted URLs. No implementation files were modified.

## Verdict

The straight-path vertical/diagonal dragging, compatible-lane skipping, clamp behavior, context operations, trim/fade/horizontal editing, and live playback reconstruction were exercised. Two concrete defects were confirmed:

1. **Held-drag updates stop after the first cross-track lane migration.** Once a clip has moved lanes, further pointer movement in the same held drag no longer updates it. Dragging down then returning the pointer to the original lane leaves the clip in the lower lane; dragging vertically then adding horizontal movement leaves the start unchanged. This is consistent with the implementation searching for the clip in its original source track during every transient update.
2. **The arrangement canvas is too short for the required four-lane fixture.** Measured canvas height is `132px`, while the ruler plus four rows requires `160px` (`24 + 4×34`). The fourth/BGM lane is only a thin sliver and its clips/selection are effectively invisible.

Because of these defects, the change should not be considered fully correct.

## Evidence summary

| Check | Result | Evidence |
|---|---:|---|
| Exact `1272×837` viewport | PASS | `innerWidth=1272`, `innerHeight=837` |
| Single vertical drag skips vocal lane and preserves start | PASS | `A1` moved from track 0 to compatible track 2, skipping vocal track 1; start stayed `480` |
| Undo after single vertical move | PASS | `A1` returned to track 0/start `480` |
| Straight diagonal drag applies both axes | PASS | `B1` moved to track 3 and start `1440→1560` |
| Bottom clamp preserves group spacing | PASS | `(A1,B1)` moved to `(track2,track3)` at `(480,1440)`, spacing preserved |
| Top clamp preserves group spacing | PASS in continuous user-like probes | `(A1,B1)` returned to `(track0,track2)` at `(480,1440)` in repeated focused probes. A backend-reset/reload harness variant was unstable and was not counted as implementation evidence. |
| Selection remap/repeated group drag | PASS in continuous user-like probes | repeated down move produced `A1` track2 and `B1` track3 |
| Selection visually active | PASS with visibility caveat | white outline is visible on the selected clip in a visible lane; the selected clip in track3 cannot be visually inspected because track3 is clipped offscreen |
| Copy/paste after vertical move | PASS in focused continuous probes | two unique pasted IDs; tracks `{2,3}`; starts `1680` and `2640`, preserving `960`-tick spacing |
| Context delete after vertical move | PASS | both pasted clips removed |
| Undo/redo after delete | PASS | undo restored exactly the same two pasted IDs/tracks/starts; redo removed them again |
| Horizontal-only drag | PASS | lane preserved, start quantized `480→600` |
| Left trim | PASS | `start=720`, `duration=840`, `offset=120` |
| Fade drag | PASS | `fade_in_ticks=120`, start unchanged |
| Live playback reconstruction during vertical drag | PASS | sources `created 5→10`, `start 5→10`, `stop 0→5`; first stop/create at `197.8/198.0ms`; decode count stayed `1`; zero start/stop errors |
| Held drag can reverse back to original lane | **FAIL** | after dragging down then returning pointer to original lane before release, `A1` remained in track2 instead of track0 |
| Horizontal adjustment after vertical migration | **FAIL** | after vertical migration, adding `+56px` horizontal movement before release left start at `480` instead of expected quantized `600` |
| Four lanes fit arrangement viewport | **FAIL** | canvas height `132px`; required `160px` |
| Body/sidebar/transport overflow | PASS | body `1272/1272`, sidebar `235/235`, transport `1272/1272` |
| Console/HTTP | PASS | zero console messages; zero HTTP errors |
| Network failures | PASS with expected noise | only repeated `/api/events net::ERR_ABORTED` entries caused by intentional reloads of the persistent SSE connection |

## Defect details

### 1. Held-drag position freezes after lane migration

Runtime probes:

- Reverse-path probe final state: `A1` remained `track_index=2`, `start=480` even though the pointer was returned to the original lane before mouseup.
- Vertical-then-horizontal probe final state: `A1` remained `track_index=2`, `start=480` even though the pointer moved an additional `+56px` horizontally, which should quantize to start `600`.

Screenshots:

- `19_path_down_before_reverse.png`
- `20_path_reversed_while_held.png`
- `21_vertical_then_horizontal_held.png`
- Machine evidence: `drag_path_probe_results.json`

This means straight one-shot drags can pass while normal user correction/adjustment during the same drag fails.

### 2. Fourth lane is clipped out of the arrangement

Measured arrangement canvas: `714×132`; required height for ruler plus four rows: `160px`. The BGM/accommodation lane is essentially invisible, so users cannot see clips or selection state there.

Screenshots:

- `00_fixture_four_lanes.png`
- `18_final_layout.png`

## Harness note

An earlier broad harness pass produced false copy/paste evidence because it accidentally appended the same backend dictionary entry once per track while collecting pasted clips. A slower direct-per-track probe corrected that artifact. Separately, the backend-reset/reload sequence used to isolate phases made the top/copy sequence unstable in the recorded broad run; continuous user-like probes without external backend resets passed repeatedly (including top clamp, repeated group drag, copy/paste, delete, undo, and redo). Those continuous probes are treated as the valid evidence for the requested user flow.

## Key artifacts

- Recording: `/home/ubuntu/screencasts/vertical-clip-drag-authoritative/vertical-clip-drag-authoritative-edited.mp4`
- Machine summary: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/vertical_clip_drag_results.json`
- Continuous multi/copy probe: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/full_sequence_copy_probe_results.json`
- Copy/delete/undo probe: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/copy_delete_probe_results.json`
- Drag-path defect probe: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/drag_path_probe_results.json`
- Raw recorded-run output: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/vertical_clip_drag_final_raw.json`
