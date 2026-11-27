# Media bin end-to-end QA report

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Build: frontend rebuilt/cache-busted; fixture backend restarted  
Implementation files: unchanged

## Verdict

Core media-bin functionality passed end-to-end: uploads appeared through SSE without reload, metadata was truthful, search/filter/empty state worked, native audition could play, Add-at-playhead created an exact measured audio clip on a new audio track, playback included the clip, used-file deletion was blocked, and unreferenced/unused/invalid rows could be deleted with SSE updates.

Two defects/UX problems were confirmed:

1. **Long filenames cause severe horizontal overflow in the media list.**
2. **The used-file delete error is visible but raw nested JSON rather than a readable user message.**

## Exact results

### Upload, SSE, metadata

- Created a fresh project through the visible `New` button: `project_d6cc2dca39e1`.
- Uploaded `Media Bin QA VERY LONG filename — oscillator reference take 01 final final.wav` through visible `Upload vocal/audio source` file chooser.
- Row appeared without reload: count `1`.
- SSE `media_library` action `created` received with exact metadata:
  - duration `2.0s`
  - sample rate `48000`
  - channels `1`
  - valid `true`
- Row metadata visible: `2.00s · 48k`.
- Audio audition control had correct `/uploads/...wav` src.
- Scripted native-control audition after real user gestures: `paused=false`, `readyState=4`, currentTime advanced to `0.310199s`.

### Search and empty state

- Search `oscillator`: exactly `1` media row.
- Search `zzzz-no-media`: inside `.media-bin-section`, exactly `0` rows and exactly one empty state: `No uploaded audio`.
- Clearing restored rows.

### Invalid uploaded file

- Uploaded `not_actually_audio.wav` containing plain text.
- Backend/media bin represented it as invalid rather than crashing:
  - row text: `not_actually_audio.wav invalid Add at playhead Delete`
  - Add at playhead disabled: `true`
  - SSE metadata included `valid=false` and `Format not recognised`
- Row could later be deleted successfully.

Caveat: generic upload still accepts the invalid file as an ACE-Step source path; the media bin correctly marks it invalid, but upload-source validation itself is outside this feature's confirmed scope.

### Add at playhead / arrangement integration

- Clicked arrangement ruler to exact playhead position `1.3.1 00:01.00` = tick `960`.
- Clicked media-row `Add at playhead` without reload.
- Backend exact result:
  - project track count `2`
  - new track type `audio`
  - new track name `Audio — Media Bin QA VERY LONG filename — oscillator reference take 01 final final`
  - clip start exactly `960`
  - clip duration exactly `1920` ticks, matching 2 seconds at 120bpm/480ppq
  - clip path exactly the uploaded media file
- Arrangement visibly showed the green clip beginning at the playhead position.

### Arrangement playback includes the clip

- Pressed play from the clip position.
- Exactly one playback source was scheduled:
  - buffer duration `2s`
  - source offset `0`
  - source duration `2`
  - decoded buffer reused from `OfflineAudioContext`
- Playhead position advanced from zero/initial state.
- Since the fresh project had no rendered vocal audio, this source is necessarily the imported arrangement clip.

### Delete while used

- Clicked Delete for the media row and accepted confirmation.
- Backend returned deliberate HTTP `409` as requested.
- Row remained: count `1`.
- File remained on disk: `true`.
- Error banner appeared visibly.

**Defect/UX problem:** the visible error is developer-oriented raw nested JSON:

`409: {"detail":{"detail":"media file is used by arrangement clips","projects":["project_d6cc2dca39e1"]}}`

It is visible and blocks deletion, but it is not a polished readable user message.

### Delete clip reference, then delete media

- Right-clicked arrangement clip and used visible context-menu `Delete`.
- Backend clips after deletion: exactly `[]`.
- Clicked media Delete again.
- Row disappeared without reload: count `0`.
- Physical file deleted: `false` for existence.
- SSE `media_library` action `deleted` received.

### Unused upload deletion

- Uploaded `unused_media_bin_delete_test.wav`.
- Row appeared without reload.
- Did not place it in arrangement.
- Delete succeeded.
- Row disappeared: count `0`.
- SSE created/deleted events were received.

### Long filename layout

**Defect confirmed** at exact viewport `1272x837`:

- right panel clientWidth: `311`
- media list clientWidth: `277`
- long media row clientWidth/scrollWidth: `509`
- long row right edge: `1474.4` versus list right edge `1250`
- row extends about `224px` beyond the media list/right edge
- strong filename scrollWidth/clientWidth: `427`
- audio scrollWidth/clientWidth: `493`
- row `inside=false`

So the row is not contained; it creates horizontal overflow/clipping in the media list. Visually the row is clipped and horizontally scrollable rather than cleanly constrained/ellipsized.

### Console/network

- Only network failure: deliberate HTTP `409` for the used-media delete.
- Only console error: browser-generated resource message for that same deliberate `409`.
- No unexpected console errors/warnings or network failures.

## Artifacts

- `media_bin_results.json` — exact machine-readable evidence
- `long_geometry_supplement.json` — exact overflow geometry
- `media_empty_probe.json` — scoped empty-state supplement
- `media_bin_run.log` — raw output
- `00_fresh_project_media_bin.png`
- `01_long_upload_sse_row.png`
- `02_search_empty_state.png`
- `03_invalid_upload_row.png`
- `04_added_at_playhead_arrangement.png`
- `05_media_layout_long_filename.png`
- `06_used_delete_error.png`
- `07_clip_context_menu.png`
- `08_long_delete_success.png`
- `10_long_filename_geometry_supplement.png`
- `11_long_filename_visible_overflow.png`
- `/home/ubuntu/screencasts/media-bin-qa/media-bin-qa-edited.mp4`
