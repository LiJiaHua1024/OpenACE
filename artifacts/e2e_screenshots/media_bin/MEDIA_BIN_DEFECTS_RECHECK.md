# Media-bin defect regression recheck

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Implementation files: unchanged

## Result

The two originally reported defects are materially fixed, with one remaining visibility caveat.

### 1. Long filename overflow — fixed

Exact measured geometry:

- viewport: `1272x837`
- media list clientWidth/scrollWidth: `277/277`
- long row clientWidth/scrollWidth: `273/273`
- row rect: x `963`, width `275`, right `1238`
- list right edge: `1250`
- row inside list: `true`
- audio clientWidth/scrollWidth: `257/257`
- audio right edge `1229`, inside row: `true`
- Add/Delete buttons inside row: `true`
- filename strong clientWidth/scrollWidth: `190/427`
- text overflow: `ellipsis`, white-space `nowrap`

Visible evidence confirms ellipsis (`Media Bin QA VERY LONG filena...`) and fully contained native audio controls/buttons.

Control clickability:

- native audio play area click started playback: `paused=false`, `currentTime=0.324664`, `readyState=4`
- `Add at playhead` click created an arrangement clip
- `Delete` click opened/accepted the confirmation and triggered the protected delete request

### 2. Used-delete readable error — text fixed, visibility caveat remains

Backend clip evidence after Add:

- project `project_c1f0a1baa0cc`
- new audio track `track_5f14f7bb1ec7`
- clip start `0`, duration `1920`
- clip path is the long uploaded media file

Delete while used remained blocked:

- network status `409`
- row remained present
- clip/file remained in use

Frontend now extracts concise readable detail without nested JSON:

`media file is used by arrangement clips in 1 project(s); remove those clips before deleting it`

**Remaining visibility caveat:** immediately after clicking Delete, the error banner was below the exact viewport and did not appear in `22_fix_used_delete_error.png`; manual scrolling of the right panel was required to reveal it. After scrolling, it was visible at y `769` to `817` within `1272x837` (`23_fix_error_after_panel_scroll.png`). Thus the text extraction is fixed, but error placement/visibility is still not ideal because the user receives no immediate visible feedback at the media-bin scroll position.

### Console/network

Only the deliberate `409` network response and browser-generated resource error were observed; no unexpected console/network errors.

## Artifacts

- `media_defects_recheck.json`
- `error_visibility_recheck.json`
- `media_defects_recheck.log`
- `20_fix_long_row.png`
- `21_fix_long_row_after_add.png`
- `22_fix_used_delete_error.png`
- `23_fix_error_after_panel_scroll.png`
