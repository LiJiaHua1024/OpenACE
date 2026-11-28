# Stale Vocal Render Detection Focused Browser QA

Date: 2026-11-27  
Surface: real visible Chrome through Playwright/CDP, exact CSS viewport `1272×837`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1` and `OPENACE_CI_FIXTURE_DELAY_SECONDS=0.8`  
Frontend: rebuilt/cache-busted; implementation unchanged.

## Result

All 21 scripted focused checks passed. Fresh render hash parity was validated because the frontend did not mark a just-rendered track stale. Every tested render-input mutation produced both the amber TrackList badge and RenderPanel warning; undo restored the exact rendered input state and cleared both indicators.

## Evidence summary

- Fresh render: revision `4`, fingerprint `601955486b40e607`, badge `0`, warning `0`.
- Render-input mutations that correctly became stale: note pitch transpose, note lyric edit, dynamic automation point, breath event, BPM edit, and voice assignment.
- Each mutation retained the original fingerprint while the current input changed, displayed badge `1` + warning `1`, and then returned to badge `0` + warning `0` after one undo.
- Reload persistence: a lyric edit to `呀` still showed badge `1` + warning `1` after reload.
- Warning text: “Rendered audio is older than the current notes, expression, tempo, or voice. Playback/export still use the old render until you render again.”
- While stale, playback started and WAV export returned HTTP `200` with `432044` bytes.
- Supplemental manual playback timing on the legacy stale project advanced `00:00.26`, `00:00.52`, `00:01.02`, `00:01.64` at approximately 250/500/1000/1600ms.
- Rerender: revision `5`, badge `0`, warning `0`.
- Irrelevant edits did not create stale state: mute `true`, volume `0.08`, pan `0.96`, track name `Renamed irrelevant`, color `#2fb996`; fingerprint unchanged and badge/warning absent.
- Copied legacy project JSON with `render_fingerprint` removed: backend fingerprint `null`, badge `1`, warning `1`.
- Exact layout: body `1272/1272`, right panel `311/311`, transport `1272/1272`, warning `285/285`; no overflow.
- Console `0`; HTTP errors `0`; unexpected network failures `0` (only expected `/api/events` reload aborts).

## Files

- Recording: `/home/ubuntu/screencasts/stale-render-detection-final2/stale-render-detection-final2-edited.mp4`
- Machine results: `stale_render_detection_results.json`
- Key screenshots:
  - `00_fresh_render_no_stale.png`
  - `01_note_pitch_stale.png`
  - `02_note_lyric_stale.png`
  - `03_automation_stale.png`
  - `04_breath_stale.png`
  - `05_tempo_stale.png`
  - `06_voice_stale.png`
  - `07_reload_stale_preserved.png`
  - `08_playback_while_stale.png`
  - `09_rerender_clears_stale.png`
  - `10_irrelevant_edits_no_stale.png`
  - `11_legacy_missing_fingerprint_stale.png`
  - `12_final_layout.png`
  - `13_manual_playback_timing.png`
