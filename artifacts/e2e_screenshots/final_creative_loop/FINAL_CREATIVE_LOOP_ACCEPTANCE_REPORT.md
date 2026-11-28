# Final Creative Loop Acceptance — b415982

Date: 2026-11-28  
Branch/commit: `b415982`; working tree was clean before testing.  
Mode: visible Chrome + fixture CPU orchestration; implementation unchanged.  
Primary browser project: `project_0fd2a05d5da2`; MCP project: `project_0aa8682e9327`.

## Defects first

### P2 — immediate undo after drawing a note is swallowed while the auto-open lyric editor remains active

Reproduced repeatedly:

1. Draw a note. The lyric editor automatically opens.
2. Click enabled **Undo** or press Ctrl+Z without dismissing that editor.
3. Note remains locally/backend.

Focused A/B:
- Escape/dismiss editor first, then Undo: backend `0 notes`, UI `0 notes`.
- Leave auto-open editor active, then Undo: backend `1 note`, UI `1 note`.
- Control check: undoing a committed lyric edit works (`你` reverted to empty), so generic undo is not completely broken.

Evidence: `undo_creation_defect.json`, `24_undo_creation_defect_state.png`.

### P3 — MCP export parity gap: `mp4` is unsupported

The actual MCP workflow completed creation, voice import/assignment, notes/lyrics/expression, vocal render, Vocal2BGM, repaint, SVC `-3`, and exported 10 formats successfully. But `export_project(fmt="mp4")` rejected with `unsupported format: mp4` even though browser MP4 export works and validates. If MCP is intended to drive the same end-to-end workflow, this is a concrete parity gap.

Evidence: `mcp_workflow_results.json`.

## Passed coverage

### 1. Piano roll creation/editing

- Visible new project creation passed.
- Corrected focused pass drew exactly 3 notes at 1272×837.
- Drag exact: last note `(1440,pitch69) → (1920,pitch70)`.
- Resize exact: first note duration `480 → 600` ticks.
- Ctrl+wheel zoom exact: `112 → 136`.
- Lyrics/phonemes passed on created notes: examples `n i x au`, `x au`; MCP project exact phonemes `n i`, `x au`, `ʈʂʰ aŋ`.
- Pitch/Air/Tension curves each stored 13 points in the browser pass; MCP lanes stored exact normalized/cents points.
- Transpose controls exact `[64,68] → [65,69] → [64,68]`.
- Reload persistence passed: 3 notes and exact durations remained.

### 2. Reference, vocal render, Vocal2BGM, playback

- Real reference/source upload through browser file chooser passed.
- Fixture vocal render completed.
- Vocal2BGM completed and exactly one accompaniment clip existed before repaint.
- After jobs settled, playback advanced `00:00.00 → 00:01.35` and requested all expected rendered sources: vocal, original/repaint accompaniment, SVC.

### 3. Repaint

- Alt-drag produced visible held-state yellow range and exact numeric range `0.54–1.31s`.
- Repaint completed.
- Accompaniment integration remained exactly one clip, labeled `Repaint`, with updated job provenance.

### 4. SVC key/transposition

Fresh final-branch conversions all completed and exact job/provenance/card text matched:

- Auto: `pitch_shift=0`, `auto_shift=true`, card `key: auto-match reference`.
- Preserve: `pitch_shift=0`, `auto_shift=false`, card `key: preserve source`.
- Manual: `pitch_shift=-3`, `auto_shift=false`, card `key: -3 semitones`.

No job-card overflow observed.

### 5. Browser export of every format

All 11 browser downloads existed/nonzero:

`wav/mp3/flac/ogg/stems/mp4/mid/lrc/ustx/svp/vpr`

Spot validation passed:

- WAV/FLAC/OGG exactly `3.0625s`, 48kHz, nonzero peak.
- MP3 `3.096s` including codec padding.
- MP4 valid `ftyp`, `3.067s`.
- Stems was a real ZIP with manifest and 3 audible stem entries; silent editable score stem skipped truthfully.
- LRC/USTX/SVP valid UTF-8 text/JSON/YAML-like content.
- MIDI had valid `MThd` magic.
- VPR had ZIP magic.

Evidence: `export_validation.json`.

### 6. Actual MCP end-to-end workflow

Using real MCP stdio client/tools, not CLI:

- Created project `project_0aa8682e9327`.
- Imported persistent reference voice and assigned it.
- Added 3 lyrical notes and expression lanes.
- SSE/live browser update passed: open track card updated to `3 notes` without manual reload.
- Render vocal completed.
- Vocal2BGM completed.
- Repaint completed.
- SVC manual `-3` completed with exact fields.
- Exported 10/11 formats nonzero; MP4 gap above.
- Final MCP project visually showed reference, notes/phonemes, repaint clip, and SVC clip coherently.

### 7. Layout, console/network, persistence

- Exact 1272×837: no body overflow, no transport overflow, no right-panel overflow.
- Exact 1920×1080: no body/transport/right-panel overflow.
- Return to 1272×837 remained clean.
- Browser console errors/warnings: zero across main and supplemental passes.
- Failed browser network responses: zero across main and supplemental passes.
- Reviewed high-resolution screenshots; no additional dead/miswired visible control or layout breakage found.

## Harness artifacts / not product defects

The raw first-pass `final_qa_results.json` contains several false entries that were investigated rather than hidden:

- `transport_layout=false`: harness expected 1272×837 but browser initially measured 1280×841. Exact 1272×837 supplement passed.
- `draw_notes=false` / downstream lyric count mismatch: one intentionally reused low canvas coordinate landed in the velocity/bottom zone, so only two notes were created in that pass. Corrected focused supplement created exactly 3.
- `svc_conversion=false`: fixed 30s wait elapsed while ASR-backed SVC was still running; the job later completed with exact `-3` provenance.
- `playback=false`: first playback probe happened before all SVC/render jobs had settled. Post-settle supplement passed and requested all sources.
- Fixture mode intentionally uses CI DSP, so timbre/model quality was not validated; orchestration, data flow, file output, UI, and measurable fixture transformations were real.

## Artifact index

- Browser results: `final_qa_results.json`
- Export validation: `export_validation.json`
- Playback supplement: `playback_supplement.json`
- Piano/viewport/undo supplement: `piano_viewport_undo_results.json`
- SVC modes: `svc_modes_final.json`
- MCP workflow: `mcp_workflow_results.json`
- Undo defect evidence: `undo_creation_defect.json`
- Screenshots: numbered PNGs in this directory
- Downloads: `downloads/`; MCP exports: `mcp_exports/`
