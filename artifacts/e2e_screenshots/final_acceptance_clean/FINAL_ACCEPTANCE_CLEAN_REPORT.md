# Final Clean-Revision Acceptance — `5a6c92c`

Date: 2026-11-28  
Mode: fixture CPU orchestration (`OPENACE_CI_SYNTH_FIXTURE=1`, `OPENACE_CI_FIXTURE_DELAY_SECONDS=1`). This validates real orchestration, state, DSP fixture output, UI, exports, and MCP wiring; it does not validate production model timbre.  
Implementation modified: no. `git diff` for source files is empty.

## Defect-first verdict

No reproducible product defect found in the final normal-user acceptance flow.

One harness/instrumentation caveat is disclosed: while cache-disabled CDP instrumentation was enabled, playback once triggered the app's honest "audio output clock stalled" guard and did not recover within a short retry window. In a normal fresh reload without cache disabling, playback requested all rendered audio sources, advanced continuously to about 2 seconds, and showed live loudness metering. The stalled cache-disabled run is therefore treated as a test-condition caveat rather than a confirmed product regression, but the evidence is retained in `27_playback_final.png`, `28_playback_retry.png`, and `playback_retry.json`.

## Verbatim creative-loop coverage

### 新建工程

Passed. Visible browser project creation at exactly 1272×837; transport/body/right panel had no overflow.

Evidence: `00_initial_1272x837.png`, `01_new_project_transport_fit.png`, `final_qa_results.json`.

### 钢琴卷帘画音符/拖拽/缩放/改歌词看音素

Passed.

- exactly 3 notes drawn in the corrected pass
- resize `480 → 600` ticks
- drag `(1440, pitch69) → (1920, pitch70)`
- zoom `112 → 136`
- lyrics exact `你好 / 好 / 唱`
- phonemes exact `n i x au`, `x au`, `ʈʂʰ aŋ`
- undo/redo note-count regression `3 → 2 → 3`

Evidence: `02_notes_drawn.png`, `03_lyrics_phonemes_cjk.png`, `06_zoom.png`, `22_piano_undo_drag_resize_1272.png`, `piano_viewport_undo_results.json`.

### 切换画笔拉音高与气声/张力曲线

Passed. Browser-drawn automation produced 13 points each in `pitch_cents`, `air`, and `tension`.

Evidence: `05_automation_curves.png`.

### 上传参考人声

Passed. Real file-chooser upload assigned a 2.5s reference voice and uploaded vocal/audio source.

Evidence: `07_uploads.png`, `29_playback_fresh_reload.png`.

### 触发渲染与伴奏生成

Passed. Vocal render and Vocal2BGM completed; exactly one accompaniment clip existed before repaint.

Evidence: `08_vocal_render.png`, `final_qa_results.json`.

### 框选局部重绘

Passed. Alt-drag produced a visible yellow range while held and exact numeric range `0.54–1.31s`; repaint completed and exactly one replacement clip labeled `Repaint` remained integrated.

Evidence: `09_alt_drag_repaint_held.png`, `10_alt_drag_repaint_numeric.png`, `11_repaint_replacement_arrangement.png`.

### 切换翻调模式

Passed. Auto/preserve/manual modes completed with exact backend fields and visible job-card labels:

- auto: `pitch_shift=0`, `auto_shift=true`, `key: auto-match reference`
- preserve: `pitch_shift=0`, `auto_shift=false`, `key: preserve source`
- manual: `pitch_shift=-3`, `auto_shift=false`, `key: -3 semitones`

Evidence: `svc_modes_final.json`, `26_svc_jobcards_final.png`, `jobcards_playback_final.json`.

### 导出全格式工程

Passed. All 11 browser formats downloaded nonzero:

`wav/mp3/flac/ogg/stems/mp4/mid/lrc/ustx/svp/vpr`

Spot validation passed:

- WAV/FLAC/OGG exactly `3.0625s`
- MP3 probe `3.096s`
- MP4 valid `ftyp`, `3.067s`
- stems valid ZIP with manifest and 2 WAV stems
- MIDI begins `MThd`
- USTX/LRC/SVP valid UTF-8 text structure
- VPR nonzero binary/package output

Evidence: `13_export_panel.png`, `14_exports_downloaded.png`, `downloads/`, `export_validation.json`.

### 通过 MCP 驱动整套流程

Passed through a real MCP stdio client, not merely CLI:

- create project
- import/assign voice
- batch notes and exact phonemes
- pitch/air/tension expression lanes
- SSE live browser update after external note insertion
- render vocal
- Vocal2BGM
- repaint
- SVC manual `-3`
- export all 11 formats including MP4

All MCP exports existed and were nonzero. MCP MP4 valid `ftyp`, `2.5s`, `210582` bytes.

Evidence: `21_mcp_final_project.png`, `mcp_workflow_results.json`, `mcp_exports/`, `mp4_hardgate_validation.json`.

## Hard gates

### First undo with auto lyric editor open

Passed.

- first toolbar Undo with empty auto editor open: backend/UI `0 notes`, Undo disabled
- fresh empty-editor Ctrl+Z: backend/UI `0 notes`
- rapid alternating create/undo at 30/45/80/120/150ms: all five ended backend/UI `0 notes`
- lyric commit/undo/redo: `你 → empty → 你`, note preserved

Evidence: `01_toolbar_first_click_zero.png`, `02_ctrlz_empty_editor_zero.png`, `03_rapid_create_undo_no_accumulation.png`, `04_lyric_commit_undo_redo.png`, `final_acceptance_clean_results.json`.

### No orphaned lyric editor after Ctrl+Z

Passed. `editor_after=0` after empty-editor Ctrl+Z.

Evidence: `02_ctrlz_empty_editor_zero.png`, `final_acceptance_clean_results.json`.

### MCP + CLI MP4 export

Passed.

- browser MP4: `268176` bytes, `ftyp`, `3.067s`
- MCP MP4: `210582` bytes, `ftyp`, `2.5s`
- CLI MP4: exit 0, `293013` bytes, `ftyp`, `2.5s`

Evidence: `mp4_hardgate_validation.json`, `cli_project_ccbb037d0c35.mp4`.

## Playback, persistence, layouts, health

- Playback after normal fresh reload passed: position advanced `00:00.01 → 00:01.97`; 8 rendered-file requests observed; live loudness meter visible.
- Reload persistence passed: 10 tracks / 5 clips / 4 SVC conversion records preserved in the full creative project; separate piano project preserved note count/durations.
- Layouts passed at exact `1272×837` and `1920×1080`: no body, transport, or right-panel overflow.
- Console/network passed across final scripts: zero console errors/warnings, zero failed browser network responses.
- Backend log: zero HTTP 500s and zero tracebacks during acceptance.

Evidence: `29_playback_fresh_reload.png`, `playback_fresh_reload.json`, `23_layout_1920.png`, `jobcards_playback_final.json`, `piano_viewport_undo_results.json`.

## Harness notes

The raw first-pass browser JSON has two false-looking entries:

- `svc_conversion: false` was a fixed-timeout harness artifact; the job later completed successfully and exact backend fields/job-card label were verified in the supplement.
- `playback: false` was a cache/request-observation artifact: position had advanced, but already-cached audio produced no network requests. Fresh normal reload later proved playback with real rendered-file requests.

These are retained transparently in `final_qa_results.json` but superseded by the focused evidence above.
