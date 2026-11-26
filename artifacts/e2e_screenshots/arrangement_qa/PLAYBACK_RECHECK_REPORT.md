# Targeted playback-offset recheck

Real-Chrome Playwright/CDP recheck of branch `devin/1795693399-arrangement-waveforms` against the fixture server, using rendered project `project_e3f52a65d029`. Viewport 1272×837.

## Result: PASS

The future-clip playback defect is fixed in the targeted recheck.

| Check | Result | Evidence |
|---|---:|---|
| Waveform remains visually/functionally present | PASS | column spans still vary 2–8px; bucket range 6.0 |
| Clip drag later | PASS | persisted `start_ticks=480` |
| Future playback scheduling | PASS | instrumentation: `when-now=0.500s`, `offset=0` |
| Positive seek playback | PASS | instrumentation: `when-now=0.000s`, `offset=0.5` |
| Clip drag earlier | PASS | restored `start_ticks=0` |
| Console/network health | PASS | no console errors or failed responses |

Runtime instrumentation screenshot:

![Playback instrumentation recheck](https://app.devin.ai/attachments/788ffa7c-7f26-4725-a3d6-e90c7ad43515/recheck_03_playback_instrumentation.png#w=1272&h=837)

Waveform regression screenshot:

![Waveform still visible](https://app.devin.ai/attachments/30c9e88a-816b-4e25-9945-064361b453d6/recheck_01_waveform_still_visible.png#w=1272&h=837)

Artifacts:

- Recording: `/home/ubuntu/screencasts/rec-a9b89513-a322-4d22-9ed1-2adf3ff35a78/rec-a9b89513-a322-4d22-9ed1-2adf3ff35a78-edited.mp4`
- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/playback_recheck_results.json`
- Screenshots: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/recheck_01_waveform_still_visible.png`, `recheck_02_clip_moved_later.png`, `recheck_03_playback_instrumentation.png`, `recheck_04_clip_restored.png`
