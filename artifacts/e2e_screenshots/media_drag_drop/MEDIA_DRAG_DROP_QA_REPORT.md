# Media-bin drag/drop end-to-end QA report

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Input method: real native browser HTML5 drag initiated with Playwright/CDP mouse input, not synthetic JavaScript drops  
Implementation files: unchanged

## Verdict

Core drag/drop functionality passed end-to-end. Real media-row drags carried `application/x-openace-media`; empty-area, existing-audio-lane, accompaniment-lane, Alt fine-placement, and vocal-row fallback drops all produced correct backend tracks/clips without reload. Playback scheduled the dropped media, invalid rows were not draggable, and media-bin search/audition/Add/Delete regressions passed. Console/network/layout were clean.

One intermittent UX defect remains: the cyan insertion indicator was absent during some real diagonal drags even though dragover and drop were occurring inside the arrangement.

## Exact results

### Real drag payload

- Valid `svclyrics_words.wav` row started native HTML5 drags.
- Dragover/drop events carried `application/x-openace-media`.
- Each intentional drop produced exactly one `drop` and `dragend` sequence.
- Invalid row `dnd_invalid_probe.wav`:
  - DOM draggable value: `false`
  - text: `dnd_invalid_probe.wav invalid Add at playhead Delete`
  - native attempted drag produced zero drag events
  - project track count unchanged

### Empty lower arrangement drop

- Drag target raw tick `600`.
- Cyan indicator measured before release:
  - left `176px`, top `58px`, height `34px`
  - color `rgb(103, 232, 249)`
  - this corresponds to snapped beat tick `480`
- Drop created exactly one new audio track.
- Exact clip:
  - start `480`
  - duration `1920`
  - duration matches 2 seconds at project ppq/tempo
- No reload.

### Existing audio lane drop

- Drag target raw tick `2520`; nearest-beat snap expected `2400`.
- Indicator measured at left `624px`, row top `58px`, cyan.
- Drop reused the existing audio track; no additional track was created.
- Exact second clip start: `2400`, duration `1920`.

### Accompaniment/BGM lane drop

- Added BGM track through visible `+ BGM` control.
- Dropped media on accompaniment lane.
- Track count remained exactly `3`; no fallback track was created.
- BGM track received exactly one clip, duration `1920`.
- Clip start was `1440`.
- Note: the raw target tick was `1200`, exactly half-way between beats 960 and 1440. The implementation uses JavaScript `Math.round`, which ties upward, so `1440` is correct for the implemented nearest-beat rule.

### Alt fine placement

- Direct normal-vs-Alt indicator probe:
  - normal drag indicator left `176px` = snapped tick `480`
  - Alt drag indicator left `204px` = raw target tick `600`
- Alt drop created a new audio track in lower empty space.
- Exact clip start `600`, duration `1920`.
- `600` is not beat-aligned, proving Alt preserved fine placement.
- Harness note: the first harness expectation of `603` was a coordinate-rounding error; the final integer pixel maps exactly to tick `600`.

### Vocal row drop

- Dropped media over the vocal row.
- Vocal track remained uncorrupted: exact clips list `[]`.
- A separate fallback audio track was created.
- Exact clip start `1440`, duration `1920`.
- This satisfies the “create elsewhere/fallback” behavior and does not misuse the vocal lane.

### Playback

Initial playback proof from the first dropped clip:

- exactly one source initially scheduled
- offset `0`
- duration `2`
- decoded buffer duration `1.9999773242630385`

Supplemental visual/transport proof after later overlapping drops:

- playback remained active
- position advanced to `2.2.3 00:02.81+`
- multiple 2-second media sources scheduled, as expected because several dropped clips overlap
- screenshot `16_playback_position_proof.png` shows active pause button, advanced transport, arrangement clips, and audio meter activity

### Media-bin regressions

- Search `svclyrics`: exactly one row.
- Native audition click:
  - src `/uploads/svclyrics_words.wav`
  - `paused=false`
  - currentTime `0.245028`
  - readyState `4`
- Existing `Add at playhead` still worked:
  - track count `5 -> 6`
  - new track type `audio`
  - clip created
- Unused upload `dnd_unused_delete.wav`:
  - uploaded successfully
  - Delete succeeded
  - row count after delete `0`
  - file absent from `data/uploads`
  - media-library SSE created/deleted events observed

### Layout, console, network

- Exact viewport `[1272,837]`.
- media list clientWidth/scrollWidth `277/277`.
- visible row clientWidth/scrollWidth `273/273`.
- no media-bin horizontal overflow.
- console errors/warnings: none.
- failed network responses: none.

## Defect: intermittent cyan-indicator disappearance

During the primary real diagonal drags for the accompaniment lane and Alt fine placement:

- native `dragstart` occurred
- final `dragover` and `drop` occurred inside arrangement coordinates
- the drop succeeded
- but `.media-drop-indicator` was `null` at the pre-drop measurement and screenshots `05`/`07` show no obvious cyan indicator

A direct steady-position probe proved the indicator can render correctly (`normal left176`, `Alt left204`), and the primary empty/audio/vocal drags also showed it. Therefore this is not a total failure; it is an intermittent disappearance/flicker during real drag movement. The likely risk is that `dragleave` unconditionally clears the indicator even when the pointer remains within the arrangement/drop target hierarchy. This should be investigated because users may lose insertion feedback exactly while dragging.

## Harness corrections

The first automated pass produced several false defect strings due to harness arithmetic/coordinate assumptions. Corrected interpretation is stored in `media_drag_drop_analysis.json`:

- empty indicator row top is correctly `58px`, not `80px`
- accompaniment/vocal raw tick `1200` ties upward to `1440`
- Alt pixel maps exactly to tick `600`, not `603`

These were not implementation defects.

## Artifacts

- `media_drag_drop_results.json` — raw full run evidence
- `media_drag_drop_analysis.json` — corrected assertion summary
- `indicator_probe.json` — row-by-row steady-position indicator probe
- `alt_indicator_probe.json` — normal-vs-Alt indicator geometry
- `drag_start_probe.json` — drag-start reliability probe from row head/audio/button areas
- `playback_supplement.json` — transport/source proof
- `media_dnd_run.log` — raw output
- `00_indicator_snapped_empty.png`
- `01_after_drop_empty.png`
- `02_playback_dropped_clip.png`
- `03_indicator_audio_lane.png`
- `04_after_audio_lane_drop.png`
- `05_indicator_accompaniment_lane.png` — indicator-missing evidence
- `06_after_accompaniment_drop.png`
- `07_indicator_alt_fine.png` — indicator-missing evidence
- `08_after_alt_fine_drop.png`
- `09_indicator_vocal_row.png`
- `10_after_vocal_row_drop.png`
- `11_search_audition_regression.png`
- `12_final_layout.png`
- `13_alt_indicator_direct.png`
- `14_normal_indicator_direct.png`
- `15_bgm_indicator_direct.png`
- `16_playback_position_proof.png`
- `/home/ubuntu/screencasts/media-drag-drop-qa/media-drag-drop-qa-edited.mp4`
