# SVC arrangement lyric display QA

Date: 2025-11-27  
Mode: real visible Chrome at exact `1272×837`, cache-busted backend-served frontend  
Project: `project_709af284eb64`  
Recording: `/home/ubuntu/screencasts/svc-lyrics-qa/svc-lyrics-qa-edited.mp4`

## Summary

The SVC timed-lyric arrangement canvas feature mostly works: timed lyrics render near the bottom of the audio clip, their x positions match source-time mapping closely, they survive reload, and words fully outside the visible source range disappear after left/right trim operations.

One focused implementation defect was confirmed: a word that straddles the **left trim boundary** incorrectly disappears. Example: after trimming the left edge to source offset `0.5s`, the word `are` spanning `0.45–0.8s` still overlaps the visible source range `0.5–2.0s`, but is not rendered. The implementation appears to clamp its local start to zero, placing it exactly at the clip x origin, then rejects it with the `lyricX < x + 4` boundary test.

Chinese glyphs could not be fairly validated in this long-running Chrome instance because canvas/DOM CJK fallback rendered narrow tofu despite the environment font. ASCII timed words (`you/are/my/world`) were therefore used as readable realistic lyric tokens. This is classified as a harness/environment limitation, not an application defect.

## Fixture

- WAV: `/home/ubuntu/repos/OpenACE/data/uploads/svclyrics_words.wav`
- Duration: 2.0s, valid PCM WAV
- Clip initial state: `start_ticks=0`, `duration_ticks=1920`, `offset_ticks=0`
- Timed words:
  - `you`: `0.10–0.40s`
  - `are`: `0.45–0.80s`
  - `my`: `1.10–1.40s`
  - `world`: `1.45–1.80s`

## Results

| Assertion | Result | Evidence |
|---|---:|---|
| Timed lyrics render near bottom of arrangement clip | PASS | `01_ascii_initial_timed_lyrics.png` and zoom show `you`, `are`, `my`, `world` along lower clip area |
| Lyrics are positioned by clip/source timing | PASS | Expected x starts `[86.4,164.8,310.4,388.8]`; observed `[87,165,311,389.5]`; max error about `0.7px` |
| Reload persistence | PASS | Reload produced identical 4 groups and `298` yellow lyric pixels; backend clip state unchanged |
| Left trim removes fully outside words | PASS | After left trim to offset `0.5s`, `you` disappeared; `my/world` remained |
| Right trim removes fully outside words | PASS | Strong right-only trim left visible range `0.0–0.5s`; only `you/are` remained, `my/world` disappeared |
| Boundary-overlapping word remains visible | FAIL | `are` overlapped visible range after left trim but disappeared; confirmed implementation defect |
| Layout at 1272×837 | PASS | No body overflow; arrangement `scrollWidth=clientWidth=714` |
| Console/network health | PASS with expected noise | No app errors. Canvas warning came from QA `getImageData`; SSE aborts were deliberate reloads |

## Quantitative canvas evidence

Initial/reload lyric pixel groups:

- `you`: x `87–99`, count `66`
- `are`: x `165–176`, count `65`
- `my`: x `311–321`, count `58`
- `world`: x `389.5–409`, count `109`

After left trim (`start=480`, `offset=480`, `duration=1440`):

- only `my/world` groups remained
- `you` correctly disappeared
- **`are` incorrectly disappeared despite overlapping the visible source range**

After strong right-only trim (`start=0`, `offset=0`, `duration=480`):

- only `you/are` groups remained
- `my/world` correctly disappeared

## Classification

### Confirmed implementation defect

1. **Left-boundary straddling lyric is incorrectly hidden.** The clamped word starts exactly at the clip edge and is rejected by the edge-boundary test. This is small but real trimming behavior incorrectness.

### Harness/environment limitation

1. **CJK glyph rendering unavailable in the active browser instance.** Chinese words rendered as narrow tofu (`measureText('你')≈2.92px` at 8px), so ASCII words were used for readable verification.

### Missing ACE-parity capability

None identified in this focused slice.

## Left-boundary fix recheck — fixed

Focused regression after the drawX clamping fix, using the exact same left-trim case:

- Initial fixture reset to `start=0`, `offset=0`, `duration=1920`.
- Left edge dragged right by 112px, producing exactly `start=480`, `offset=480`, `duration=1440` — visible source range `0.5–2.0s`.
- **PASS:** `are` (`0.45–0.8s`) is now visible near the clamped left edge as a lyric pixel group at x `180.5–191`.
- `you` remains absent as expected.
- Later words remain at their timed positions: `my` x `311–321`, `world` x `389.5–409`.
- Evidence: `boundary_fix_left_trim.png` and `boundary_fix_left_trim_zoom.png`.
- Recording: `/home/ubuntu/screencasts/svc-lyrics-boundary-fix/svc-lyrics-boundary-fix-edited.mp4`.

## Artifacts

- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/svc_lyrics_results.json`
- Contact sheet: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/svc_lyrics_contact_sheet.jpg`
- Initial: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/01_ascii_initial_timed_lyrics.png`
- Reload: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/02_ascii_reload_persisted.png`
- Left trim: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/03_ascii_after_left_trim.png`
- Left+right trim boundary defect: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/04_ascii_after_right_trim.png`
- Right-only strong trim: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/svc_lyrics/05_ascii_after_right_only_strong_trim.png`

No implementation files were modified.
