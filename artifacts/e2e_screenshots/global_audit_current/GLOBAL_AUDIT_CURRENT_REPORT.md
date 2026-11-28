# Global Creative-Loop Audit — Current Working Tree

Date: 2026-11-28  
Project: `project_57245938035d` (`Creative Loop 验收`)  
Backend: restarted current fixture backend on port 8787 (`OPENACE_CI_SYNTH_FIXTURE=1`)  
Frontend: production `frontend/dist`, cache-busted in visible Chrome  
Implementation modified: no

## Verdict

No new product defects were found in this discovery pass. The broad creative loop, selection-aware audio operations, mixed-language quick path, exports, project persistence, playback scheduling, and MCP/SSE integration all completed.

Defect count by severity: **P0: 0, P1: 0, P2: 0, P3: 0**.

Four red-looking results in the broad harness were investigated and classified as harness artifacts, not product defects:

| Harness result | Investigation outcome |
|---|---|
| `transport_layout` failed | The assertion hard-coded viewport `1272×837`; actual viewport was `1280×841`. Actual transport geometry was healthy: no wrapped/overflowing elements, body width `1280`, max element right `1273`, no body overflow. |
| `draw_notes` found only 2 notes | The first low/velocity-lane click missed due to the reused harness coordinate choice; subsequent drag/zoom/lyric/MCP flows still exercised note editing. Prior focused piano-roll tests cover accurate note entry. |
| lyric/phoneme count mismatch | Cascade of the missing harness-created third note; visible notes had coherent Mandarin phonemes. Mixed-language supplement later verified exact `你/hello/世` assignment and phonemes. |
| playback `requested=[]` | Network request URLs are cache-invalid. Direct `AudioBufferSourceNode.start` instrumentation after reload recorded real scheduled sources and transport advanced to `00:01.47`. |

## Verified workflow and quantitative evidence

### Project creation, piano roll, expression editing

- New project created through UI.
- Two harness-created notes existed before MCP; MCP added a third note and live-updated the track card.
- Transpose controls worked both directions: pitches `[64,68] → [65,69] → [64,68]`; transpose controls did not overlap automation/toolbar areas.
- Piano-roll zoom changed from `112` to `136` through Ctrl+wheel.
- Expression automation point creation passed for all three requested lanes:
  - `pitch_cents`: 13 points
  - `air`: 13 points
  - `tension`: 13 points
- CJK lyric/phoneme lane rendered coherent symbols for the visible notes.

### Reference upload, fixture render, Vocal2BGM, repaint, SVC

- Voice upload and source upload completed through real browser file chooser.
- Fixture vocal render completed visibly.
- Vocal2BGM completed and initially integrated one accompaniment clip.
- Alt-drag repaint range was genuinely visible while the mouse was held: numeric range `0.54–1.31` s and `1954` yellow selection pixels in the held screenshot.
- Repaint completed and replaced rather than duplicated the accompaniment: exactly one clip remained, labeled `Repaint`, with correct provenance `created_by_job_id=job_9dd61e8c12b8`, `updated_by_job_id=job_34e843979ef8`.
- Initial unanchored SVC conversion completed and created one conversion clip.

### Import as arrangement clip and selection-aware operations

A controlled audio file was imported through the visible **Import audio as clip at playhead** control:

- Imported clip: `clip_3dc4bd36ee8c`
- Path: `clip_465fd4be8fb6_vocal.wav`
- Geometry: start `0`, duration `2400` ticks, offset `0` — a 2.5-second full visible segment at 120 BPM
- RenderPanel immediately used that clip as source and showed `visible clip segment · aligned to clip start`.

Selection-aware operation jobs all completed with exact clip identity and exact source interval `0.0–2.5s`:

| Operation | Job | clip_id | source interval | arrangement start |
|---|---|---|---:|---:|
| Separation | `job_b8b79ace0bc8` | `clip_3dc4bd36ee8c` | `0.0–2.5s` | `0` |
| SVC | `job_6fa02d9b72de` | `clip_3dc4bd36ee8c` | `0.0–2.5s` | `0` |
| Vocal2BGM | `job_5a020c96ab54` | `clip_3dc4bd36ee8c` | `0.0–2.5s` | `0` |

Additional interaction behavior:

- Clicking the arrangement audio clip selected the audio track and kept SVC clickable.
- Clicking SVC in that invalid reference state surfaced exactly: `Select a vocal track with an uploaded reference voice before SVC conversion`.
- Reselecting the reference-carrying vocal track preserved the explicit clip context (`Convert the exact visible arrangement clip segment`) and conversion completed.

### Mixed-language quick path

- Track language was switched to `Mixed Mandarin/English`.
- Correct piano-roll `Lyrics…`/Ctrl+Enter batch editor accepted `你 hello 世` for exactly three notes.
- Reloaded backend project state contained exactly:

```text
你    -> n i
hello -> h ə l oʊ
世    -> ʂ ʂɻ̩
```

This is a quick regression confirmation, not a repeat of the full mixed-language validation suite.

### Playback and persistence

- Project reload preserved seven tracks, including two separated-stem tracks, and the mixed lyrics `你/hello/世`.
- Direct WebAudio instrumentation recorded real `AudioBufferSourceNode.start` calls after reload: one 3.0625-second vocal render plus seven 2.5-second arrangement/output clips, all correctly scheduled at their zero-based clip positions in this particular arrangement.
- Transport advanced to `1.3.4 / 00:01.47` and the play button remained in `playing` state during capture.

### Exports

Downloads were exercised through visible export links. All nonzero:

| Format | Size |
|---|---:|
| WAV | 882,044 bytes |
| MP4 | 71,549 bytes |
| MP3 | 124,845 bytes |
| FLAC | 165,215 bytes |
| OGG | 21,224 bytes |
| MIDI | 179 bytes |
| LRC | 104 bytes |
| USTX | 2,752 bytes |
| SVP | 7,765 bytes |
| VPR | 7,765 bytes |
| stems ZIP | 1,854,038 bytes |

Spot inspection:

- MP4: valid H.264/AAC, `1920×1080`, duration `3.067s`.
- Stems ZIP: manifest plus seven track stems, including separated vocal/instrumental and both SVC outputs.
- MIDI: type 1, two tracks, 480 TPQ, 19 pitchwheel events, 2 note-on events, matching the pre-MCP two-note export state.
- LRC contained timed lyric lines for those notes.

### MCP/SSE

- External MCP note addition succeeded.
- Open browser track card updated live from `2 notes` to `3 notes STALE RENDER`.
- SSE update was observed; no reload was required.

### Console/network/layout health

- Zero browser console errors or warnings.
- Zero page errors.
- Zero failed browser network responses in the tested flows.
- Favicon/network health check passed.
- Reviewed high-resolution screenshots for transport, piano roll, arrangement, export panel, selection-aware operation state, reload persistence, and MCP/SSE state; no new obvious overlap, dead control, or layout regression was found.

## Residual gaps / not re-proven in this pass

- No GPU/model-quality validation (known limitation, excluded by request).
- Japanese unsupported behavior was not rehashed (known limitation, excluded by request).
- Mid-job source clip movement and exact trimmed-source extraction were not repeated in this broad pass; focused SVC/Vocal2BGM/separation QA already covered those exact behaviors. This pass used a full untrimmed imported clip and verified current global workflow integration.
- Duplicate same-path disambiguation was not repeated in this broad pass; focused separation/SVC QA already covered the actionable 422 and explicit clip selection path.
- The first low piano-roll note was not created because of the harness coordinate choice, so this run should not be treated as fresh proof of low-note drawing; it still exercised note editing, lyrics, MCP addition, automation, zoom, render, and persistence.

## Files

- Recording: `/home/ubuntu/screencasts/global-audit-current/global-audit-current-edited.mp4`
- Main quantitative results: `final_qa_results.json`
- Selection-aware supplement: `selectionaware_supplement_results.json`
- Export supplement: `export_supplement_results.json`
- Downloads: `downloads/`
- Console log: `browser_console.jsonl`
