# Arrangement waveform/drag iteration QA report

Tested branch/worktree `devin/1795693399-arrangement-waveforms` in visible real Chrome driven through Playwright/CDP against the production fixture server at `http://127.0.0.1:8787`. Used existing rendered-fixture project `project_e3f52a65d029`, which contains a real rendered accompaniment clip and a vocal render. The arrangement state was restored after testing (`clip start=0`, notes back to original positions, vocal unmuted).

## Verdict

Waveform rendering, clip dragging, master-export offsets, phrase dragging, repaint Alt-drag, and console health passed. One significant playback defect remains: **a clip moved later in the arrangement starts playback immediately instead of waiting until its timeline position**.

## Results

| Check | Result | Evidence |
|---|---:|---|
| Decoded waveform looks like varying peaks | PASS | waveform column spans varied 2–8px; bucket averages ranged across 2.0–8.0; visual crop shows envelope variation rather than uniform stripes |
| Audio clip drag later | PASS | 224px drag persisted `start_ticks 0→960` |
| Audio clip drag earlier | PASS | inverse drag restored `start_ticks 960→0` |
| Future-clip playback scheduling | **FAIL** | after moving clip to 960 ticks (1s at 120 BPM), instrumentation captured `AudioBufferSourceNode.start(when=0, offset=0)` instead of a ~1s delayed start |
| Playback offset when seeking inside clip | PASS | with playhead at 1.5s and clip at 1s, instrumentation captured `start(when=0, offset=0.5)` |
| Master export clip offset | PASS | exported WAV had max amplitude `0.0` during first 0.95s and `0.6287` after 1.05s; duration 3.5s |
| Vocal phrase drag | PASS | grouped notes moved together by exactly `[+480,+480,+480]` ticks; distant ungrouped note delta was `0` |
| Vocal phrase inverse drag | PASS | all grouped notes restored exactly to original positions |
| Alt-drag repaint region | PASS | yellow region visible while held/after release; numeric Start/End `0.38→1.32` |
| Browser console/network health | PASS | zero console errors and zero network failures |

## Playback defect details

With the accompaniment clip dragged to `start_ticks=960` (1 second at 120 BPM), pressing Play from zero produced this runtime instrumentation result:

```text
future clip start: AudioBufferSourceNode.start(when=0, offset=0)
expected: approximately start(when=1, offset=0), or an equivalent delayed scheduling time
```

When the playhead was explicitly placed at 1.5 seconds, the same clip correctly started immediately at `offset=0.5`. So playback handles positive in-clip offsets but does not delay clips whose start time is still in the future. The exported master WAV does handle the offset correctly, creating a silent first second.

The screenshot below intentionally includes a red **TEST instrumentation** overlay; it is runtime test instrumentation, not application UI.

## Key evidence

![Decoded varying waveform crop](https://app.devin.ai/attachments/8620c048-89d1-4ea4-a50e-ca6d4c157e1b/evidence_true_waveform_crop.png#w=1428&h=190)

![Clip moved later with timeline gap](https://app.devin.ai/attachments/ba42fc27-36cc-4533-835b-21e46bc6ed14/02_clip_moved_later.png#w=1272&h=837)

![Playback instrumentation](https://app.devin.ai/attachments/ab81498a-07cb-4043-ac32-6b66c484732e/03_playback_start_instrumentation.png#w=1272&h=837)

![Vocal phrase moved later](https://app.devin.ai/attachments/c02bd2a4-30c2-4732-bcc8-48dbb1866e45/05_vocal_phrase_moved_later.png#w=1272&h=837)

![Alt-drag yellow repaint region](https://app.devin.ai/attachments/46dc89ab-c022-42b0-b3d5-3abc7d4ef3ba/07_alt_drag_repaint_held.png#w=1272&h=837)

## Artifacts

- Recording: `/home/ubuntu/screencasts/rec-5aa91c3b-5718-4d2e-9fcb-a8763fc19a36/rec-5aa91c3b-5718-4d2e-9fcb-a8763fc19a36-edited.mp4`
- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/arrangement_qa_results.json`
- Exported proof WAV: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/clip_offset_master.wav`
- Empty console/network log: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/browser_console.jsonl`
- Screenshot directory: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/arrangement_qa/`

## Targeted playback-offset recheck

After the playback scheduling fix, a focused real-Chrome recheck passed: clip drag persisted at 480 ticks, future playback scheduled exactly 0.5s ahead with offset 0, positive seeking still used offset 0.5, clip restoration returned to tick 0, waveform variation remained visible, and no console/network errors occurred. See `PLAYBACK_RECHECK_REPORT.md` and `playback_recheck_results.json`.
