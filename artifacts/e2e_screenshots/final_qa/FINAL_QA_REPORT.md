# OpenACE final regression QA report

Tested the production frontend in the visible real Chrome browser through Playwright/CDP at exactly **1272×837** against `http://127.0.0.1:8787` with `OPENACE_CI_SYNTH_FIXTURE=1`. Test project: `project_e3f52a65d029`. This validates UI/orchestration only, not real model output.

## Verdict

Most defect fixes verified. One claimed fix remains incomplete: **Alt-drag updates the numeric repaint Start/End fields, but no yellow repaint range is visibly drawn in the arrangement while dragging or after release** (zero yellow pixels detected in the arrangement canvas crop).

## Results

| Check | Result | Evidence |
|---|---:|---|
| Exact 1272×837 viewport | PASS | `innerWidth=1272`, `innerHeight=837` |
| Responsive transport layout | PASS | No overflowing or wrapped transport controls; Import audio right edge `1263` within `1272` |
| Favicon/network/console health | PASS | Zero browser errors, zero warnings, zero network failures; favicon 200 |
| Piano-roll notes/lyrics/phonemes | PASS | 3 notes; lyrics `你好/好/唱`; phoneme counts `[4,2,2]` |
| Transpose controls | PASS | `+1` changed `[60,64,68]→[61,65,69]`; `-1` restored them |
| Automation brush | PASS | 13 points each in pitch/air/tension |
| Ctrl+wheel zoom | PASS | Zoom `112→136`, no passive-wheel console errors |
| Vocal render + Vocal2BGM | PASS | Fixture jobs completed; one pre-repaint accompaniment clip |
| Alt-drag numeric repaint sync | PARTIAL | Start/end updated to `0.317708333333333/1.091666666666666` |
| Yellow repaint range visualization | **FAIL** | No yellow range pixels while held or after release |
| Repaint replacement | PASS | Clip count remained 1; clip label changed to `Repaint` |
| Playback source consistency | PASS | Playhead advanced; browser fetched exactly the vocal and repaint accompaniment render URLs |
| Export controls/downloads | PASS | All 7 formats downloaded nonzero |
| Fresh MP4 timing/subtitles | PASS | MP4 video 3.120s vs audio 3.125s; frame at 0.4s shows timed `你好`, frame at 1.0s shows timed `好`; no raw LRC tags |
| MCP SSE live update | PASS | MCP added a note; open UI track count updated live `3→4` |
| Arrangement row-label overlap | PASS visually | Rows are clean; former type/clip text overlap is gone |

## Important remaining defects / polish issues

1. **Yellow repaint selection is absent.** Numeric synchronization works, but the arrangement canvas gives no visual range feedback. This fails the advertised “draws a yellow repaint range” behavior.
2. **Repaint numeric fields show excessive floating-point precision** (`0.317708333333333`) despite `step=0.1`, which is not production-editor polish.
3. Chinese browser-canvas glyphs still depend on host fonts. I installed `NotoSansCJKsc-Regular.otf` in the user font directory before the run; the freshly exported MP4 correctly renders Chinese subtitles, while the already-running browser process still shows some CJK glyphs poorly in canvas/input screenshots. This is an environment/font-cache caveat rather than proof of an application font bug.

## Key evidence

![Transport fits at 1272×837](https://app.devin.ai/attachments/b5f098b9-9ef8-40c6-a747-198c9ef34e29/evidence_transport_fit.png#w=2544&h=130)

![Alt-drag numeric sync but no yellow region](https://app.devin.ai/attachments/fbacc7e1-0d6e-469f-9105-c30835a52487/09_alt_drag_repaint_held.png#w=2544&h=1674)

![Arrangement labels clean](https://app.devin.ai/attachments/dfb0e5e8-18ba-40d8-abb8-1196a89cf82f/evidence_arrangement_labels_clean.png#w=1170&h=280)

![MP4 timed subtitle frame](https://app.devin.ai/attachments/890d6f2b-7b43-4a54-8f83-8c935f7bd64a/mp4_frame_0_4s.png#w=1920&h=1080)

![MCP SSE live update](https://app.devin.ai/attachments/c545132a-48b4-45dd-a922-b13bf66eeab0/15_mcp_sse_live_update.png#w=2544&h=1674)

## Artifact locations

- Recording: `/home/ubuntu/screencasts/rec-627854b9-e979-4b13-af47-06fbc93aab5c/rec-627854b9-e979-4b13-af47-06fbc93aab5c-edited.mp4`
- Screenshots/results/downloads: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/final_qa/`
- Machine-readable results: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/final_qa/final_qa_results.json`
