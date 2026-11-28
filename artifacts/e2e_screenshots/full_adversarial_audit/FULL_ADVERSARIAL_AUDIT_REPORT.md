# Full adversarial ACE Studio creative-loop audit

Date: 2026-11-27
Checkout: `/home/ubuntu/repos/OpenACE` rolling-branch state supplied by the lead
Mode: real visible Chrome through Playwright/CDP, exact CSS viewport `1272×837`, cache-busted load
Backend: fixture synthesis backend (`OPENACE_CI_SYNTH_FIXTURE=1`)
Project under test: `project_dd9a28d7eaa0`
Recording: `/home/ubuntu/screencasts/rec-10a4fb42-6bc8-4742-a7b1-0c130d977260/rec-10a4fb42-6bc8-4742-a7b1-0c130d977260-edited.mp4`

## Executive verdict

The full requested creative-loop **orchestration** was exercised end-to-end and mostly passed: new project, piano-roll note creation/editing, lyrics/phonemes, transpose controls, zoom, pitch/air/tension curves, reference-voice upload, vocal render, Vocal2BGM, Alt-drag repaint, SVC conversion, playback integration, all seven export formats, and MCP→SSE live update.

This run found **one minor confirmed implementation defect**: at exact `1272×837`, the piano editor toolbar is `764px` wide inside a `714px` container (`50px` overflow) and visibly truncates the selection readout to approximately `1` instead of `1 selected`/hint text. This is a responsive-layout/polish defect, not a creation-loop blocker.

No broken orchestration, missing job integration, arrangement waveform failure, export dead control, console error, or network failure was confirmed in the tested loop.

Fixture audio quality was intentionally **not** treated as a defect.

## Explicit classification

### Confirmed implementation defects

1. **Minor responsive-layout defect — editor toolbar truncation**
   - Evidence: `.editor-toolbar` measured `scrollWidth=764`, `clientWidth=714`, overflow `50px`.
   - Visible effect: selection readout is cut at the right edge in `13_export_panel.png`; zoomed evidence in `toolbar_truncation_zoom.png`.
   - Severity: minor/polish; does not block the tested loop.

### Missing ACE-parity capabilities

1. **No true key/scale-aware transposition mode was exposed in the tested UI.**
   - The visible `Transpose` controls are only `-12`, `-1`, `+1`, `+12` semitone operations.
   - They worked correctly (`[64,68]→[65,69]→[64,68]`), but this is not the same as a mode/scale-aware “翻调模式”.
   - Classification: missing ACE-parity capability, not a defect in the implemented semitone transpose controls.

### Harness/model limitations

1. **Initial third scripted note draw missed.** The primary harness expected three notes but only created two because the first scripted coordinate did not land in valid empty note space. This was not treated as an implementation defect.
2. A supplemental real pencil interaction in clear empty note space increased note count `3→4`; see `16_supplemental_drawn_note.png`.
3. Consequently, the exact-count lyric oracle failed, but lyric/phoneme functionality itself worked on the two notes actually present.
4. Fixture synthesis proves orchestration/state/job/export integration only; timbre/model quality was not judged.
5. Structured exports were produced before the MCP-added note, so their two-note content is correct for the project state at export time.

## Test-by-test evidence

| Area | Result | Quantitative/objective evidence |
|---|---:|---|
| Exact viewport/transport layout | PASS | `innerWidth=1272`, `innerHeight=837`; no transport overflow/wrapping; no body overflow |
| Piano-roll note drawing | PASS with harness caveat | Primary pass created 2 notes: `(start,duration,pitch) = (720,600,64), (1440,600,67)`; supplemental draw `3→4` |
| Note drag/transposition | PASS | Backend pitches `[64,68]→[65,69]→[64,68]` |
| Lyrics + phonemes | PASS with count caveat | Lyrics `['你好','好']`; phoneme counts `[4,2]`; symbols `n i x au`, `x au` |
| Zoom | PASS | slider/backend zoom `112→136` |
| Pitch/Air/Tension curves | PASS | 13 nonzero points in each of `pitch_cents`, `air`, `tension` |
| Reference voice upload | PASS | `reference_voice_path=/home/ubuntu/repos/OpenACE/data/voices/voice_9d0507989312_vocal.wav`; voice id `voice_9d0507989312` |
| Vocal render + Vocal2BGM | PASS | jobs completed; arrangement had BGM clip before repaint |
| Alt-drag repaint selection | PASS | range `0.32→1.09`; 2,827 yellow overlay pixels in held and release screenshots |
| Repaint job/replacement | PASS | completed job `job_9ca44ef87767`; arrangement clip label `Repaint`, duration `2400` ticks |
| SVC conversion | PASS | completed job `job_d8aefc6a380a`; track `SVC — upload_b78cb4ecad73_vocal` with 1 clip |
| Playback integration | PASS | playhead `00:00.00→00:01.19`; all three expected render URLs requested |
| Export UI/downloads | PASS | WAV/MP4/MID/LRC/USTX/SVP/VPR all downloaded nonzero |
| MCP-driven mutation + SSE | PASS | external `add_note` succeeded; open UI track card changed `2 notes→3 notes` without reload |
| Browser health | PASS | no console errors, no warnings, no network failures, favicon ok |
| Editor toolbar fit | FAIL | `scrollWidth=764`, `clientWidth=714`, overflow `50px`; visible selection-readout truncation |

## Export content validation

Exports were not only nonzero downloads; basic structure/content was inspected:

| Format | Evidence |
|---|---|
| WAV | `900044` bytes, `3.125s`, `48000Hz`, stereo, RMS `0.149156` |
| MP4 | `50263` bytes, `3.125s`, `1920×1080` video stream plus audio stream |
| MID | `104` bytes, Standard MIDI format 1, 2 tracks, `480` ticks/quarter, 4 note on/off messages for the 2 exported notes |
| LRC | `99` bytes, 6 nonempty lines, 2 timed lyric lines (`你好`, `好`) |
| USTX | `2752` bytes, valid YAML-like project structure, 1 voice part, 2 notes, 2 wave parts, first note has 4 phoneme overrides |
| SVP | `7797` bytes, version `153`, 3 tracks, lead track has 2 notes and phonemes `n i x au` |
| VPR | `710` bytes, valid zip containing `Project/sequence.json`, 1 vocal track, 2 lead notes, sampling rate `48000` |

Note: exports happened before the MCP-added note, so 2-note export content is expected and correct.

## Visual audit notes

I reviewed the contact sheet plus high-resolution key screenshots, especially upload/reference voice, arrangement/jobs, export panel, repaint, and SVC states.

Observed positives:
- Main arrangement remained legible after repaint + SVC with colored clips and visible waveforms.
- Job cards show completed status, inline players, and acoustic X-Ray panel without blank regions.
- Export buttons are all visible and operable.
- Reference voice library state is compact and readable after upload.
- No obvious dead primary controls in the exercised workflow.

Observed roughness:
- Confirmed toolbar truncation described above.
- Lyric-correction helper textarea text is vertically tight/clipped in `07_uploads.png`; this is polish roughness but not function-blocking.
- Acoustic X-Ray axis labels are very small at `1272×837`, though the panel renders and is not blank.

## Prioritized gaps

1. **Fix responsive editor toolbar overflow at 1272×837** — confirmed implementation defect; likely hide lower-priority hint/readout, allow wrapping, compress controls, or provide overflow scrolling.
2. **Implement or clarify true key/scale transposition mode** — missing ACE-parity capability if “翻调模式” means more than semitone nudges.
3. **Polish dense right-panel helper text at compact width** — cosmetic only.
4. **Production model/audio quality remains unvalidated by design** — fixture-only limitation, not a defect.

## Toolbar-fix delta recheck — still failing

A focused recheck was run after the responsive-CSS delta in visible Chrome at exact `1272×837` with a cache-busted reload and a selected note.

- **Result: FAIL / incomplete fix.**
- `.editor-toolbar`: `scrollWidth=727`, `clientWidth=714`, remaining overflow `13px`.
- This is improved from the original `50px` overflow, but the selection readout still visually truncates at the right edge as approximately `1 selecte` even though DOM text is `1 selected`.
- Shortcut hint is now hidden (`display:none`), confirming the CSS delta is active.
- Controls remain usable/readable through `Vibrato`; `Copy`, `Dup`, `Quant`, and `Vibrato` are enabled with one selected note; `Paste` is disabled only because the clipboard is empty.
- Evidence: `toolbar_fix.png`, zoomed `toolbar_fix_zoom.png`.
- Recheck recording: `/home/ubuntu/screencasts/toolbar-fix-recheck/toolbar-fix-recheck-edited.mp4`.

## Toolbar second-fix delta recheck — fixed

A second focused recheck was run after the tighter slider/button responsive CSS in visible Chrome at exact `1272×837` with a cache-busted reload and one selected note.

- **Result: PASS.**
- `.editor-toolbar`: `scrollWidth=714`, `clientWidth=714`, overflow `0px`, satisfying `scrollWidth <= clientWidth`.
- DOM selection text: `1 selected`; visual inspection shows the full untruncated `1 selected` readout.
- Selection readout right edge `922.90px`, comfortably inside toolbar right edge `950px`.
- Controls remain visible/readable through `Vibrato`; `Copy`, `Dup`, `Quant`, and `Vibrato` are enabled with one selected note; `Paste` is disabled only because the clipboard is empty.
- Evidence: `toolbar_fix2.png`, zoomed `toolbar_fix2_zoom.png`.
- Recheck recording: `/home/ubuntu/screencasts/toolbar-fix2-recheck/toolbar-fix2-recheck-edited.mp4`.

## Artifact files

- Machine results: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/full_adversarial_audit/final_qa_results.json`
- Screenshot index: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/full_adversarial_audit/SCREENSHOT_INDEX.md`
- Contact sheet: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/full_adversarial_audit/screenshot_index_contact_sheet.jpg`
- Downloads: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/full_adversarial_audit/downloads/`
- Console log: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/full_adversarial_audit/browser_console.jsonl`
- Recording: `/home/ubuntu/screencasts/rec-10a4fb42-6bc8-4742-a7b1-0c130d977260/rec-10a4fb42-6bc8-4742-a7b1-0c130d977260-edited.mp4`

No implementation files were modified.
