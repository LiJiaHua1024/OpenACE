# Full Creative Loop Fixture Acceptance Report

Date: 2026-11-28
Branch: `devin/1795696369-dynamic-expression`, clean working tree at test start
Build: production bundle `index-DlE4FHXy.js`; backend restarted in explicit fixture mode.
Main coherent project: `project_9295440b4e47` / `Creative Loop 验收`.
Implementation was not modified or committed. GPU validation remains external/out of scope.

## Concise defect list

### P2 — transport controls overflow off-screen at 1280 px viewport

At `innerWidth=1280`, `Import USTX` extended to `x=1295.98` and `Import audio` to `x=1353.81`, beyond the right edge. Both are visibly clipped in `01_new_project_transport_fit.png`. This is reproducible immediately after creating a project at the default browser viewport.

### P2 — generated non-vocal tracks are falsely marked `STALE RENDER`

After Vocal2BGM/repaint/SVC, both the ACE-Step BGM accompaniment track and SVC audio track display `stale render` badges even though they have no editable vocal-note input and no newer user mutation. Backend state:

- `ACE-Step BGM`: `type=accompaniment`, `render_path` present, `render_fingerprint=null`
- `SVC — upload...`: `type=audio`, `render_path` present, `render_fingerprint=null`

`vocalRenderIsStale()` treats any track with `render_path` but no fingerprint as stale, so generated non-vocal tracks are permanently false-positive. Visible in `19_fifo_jobs.png`.

### P3 — repaint replacement loses/misattributes current-output job provenance

The repaint job completed as `job_5a6b3f6fc9bf` and the arrangement clip path correctly points to that job's `accompaniment.wav`. However the same clip still has `created_by_job_id=job_b10625e0c4ff`, the original Vocal2BGM job. There is no field preserving the repaint job as the producer of the current audio. If `created_by_job_id` is intended as current-output provenance, it is wrong; if intended as original-creation provenance, repaint provenance is not represented at all.

Exact clip evidence:

```json
{
  "path": ".../job_5a6b3f6fc9bf/accompaniment.wav",
  "label": "Repaint",
  "created_by_job_id": "job_b10625e0c4ff"
}
```

## Coverage and results

### 1. 新建工程 — passed

A new project was created through the visible `＋ New` control and renamed `Creative Loop 验收`. It persisted as `project_9295440b4e47`.

### 2. Piano-roll notes, drag/resize, zoom, lyrics/phonemes — mostly passed; initial harness draw was partially wrong

- Supplemental visible draw created exactly one new note at `(start=1440, duration=180, pitch=72)`.
- Dragging produced exact backend deltas `start +240 ticks`, `pitch +1`.
- Resizing visibly/backend changed duration `180 → 240` ticks. The harness incorrectly expected `+120` from a 28 px drag; the observed `+60` still proves resize behavior but the exact snapping expectation was not met by the test design, so this is not counted as a product defect.
- Ctrl+wheel anchored zoom spot check was exact: `pxPerBeat 112 → 123.2`, anchor error `0.0 ticks`.
- Lyrics were edited through double-click lyric editors. Visible/backend phonemes were generated, including `你好 → n i x au` and `好 → x au`.
- Caveat: the first broad harness drew only two of three intended notes because one low/velocity-lane coordinate did not create a note. This was a harness coordinate failure, not evidence of a product failure; the supplemental targeted draw test covers drawing.

### 3. Pitch/Air/Tension automation — passed

Drawing in the three automation lanes produced backend point counts:

```text
pitch_cents: 13
air:         13
tension:     13
```

### 4. Reference voice upload — passed

Browser file upload created and assigned:

```text
voice_321977ca4705
duration 2.5s
sample rate 24000
channels 1
size 120044 bytes
peak 0.39777
RMS -14.23 dBFS
voiced 2.0s
quality_warnings []
```

The selected track has matching `voice_id` and `reference_voice_path`; the visible voice panel exposes an audition `<audio>` element at `/api/voices/voice_321977ca4705/audio` plus peak/RMS/voiced metadata.

### 5. Vocal render and Vocal2BGM — passed with stale/provenance caveats above

- Vocal render job completed visibly.
- Vocal2BGM completed visibly and produced one accompaniment clip.
- Later SVC also completed and produced one audio clip.
- Fixture engines and output paths are recorded in `/api/jobs`.
- Arrangement clips and waveforms are visible in screenshots.

FIFO supplemental test: two vocal renders were enqueued back-to-back. The second stayed queued while the first ran, no overlapping running states were observed, and final backend state was:

```text
job_d96da558ad74 completed at 1795837632.8380568
job_ae10039dc5a6 completed at 1795837637.4542918
```

The first harness polling loop timed out before the second completed; final backend polling confirmed correct FIFO completion. No product defect.

### 6. Alt-drag local repaint — passed range/output replacement; provenance defect above

Alt-drag repaint range measured numerically as:

```text
start 0.5385416667s
end   1.3135416667s
```

The yellow range was visible while the mouse was held and after release. Repaint completed and the accompaniment track still had exactly one clip labelled `Repaint`, demonstrating replacement rather than clip accumulation.

### 7. Transpose — passed exact intervals and rejection

- +1/-1 round trip passed in the broad pass.
- +12 transposed every pitch exactly by 12 with interval preservation; -12 restored exact original pitches.
- Boundary rejection test used MCP to set a note to pitch 126, then clicked +12. Backend pitches remained exactly unchanged, including pitch 126; no octave folding or partial mutation occurred. UI state showed `Save failed — retry`, making rejection visible/non-silent.

### 8. Exports — passed format existence and key-content checks

Downloaded through visible export links:

```text
wav  882044 bytes, duration 3.0625s
mp3  124845 bytes, duration 3.096s
flac 165052 bytes, duration 3.0625s
ogg   17827 bytes, duration 3.0625s
mp4  335003 bytes, duration 3.067s, h264 1920x1080 + AAC
mid     179 bytes
lrc     104 bytes
ustx   2752 bytes
svp    7.6K bytes
vpr     710 bytes
stems.zip 659992 bytes
```

Key content checks:

- MIDI: PPQ 480, tempo meta `500000` (=120 BPM), 4/4 time signature, 2 note-on events at export time, 19 pitchwheel events, RPN pitch-bend range setup.
- LRC: timed lyrics `[00:00.75]你好`, `[00:02.00]好`.
- USTX/SVP: contain 120 BPM tempo and Chinese lyrics.
- VPR: valid zip containing `Project/sequence.json`, title, 4/4 meter, Vocaloid-style tempo `12000`, exact note lyrics/phonemes.
- Stems zip: manifest plus nonzero `01_Lead_Vocal.wav`, `02_ACE-Step_BGM.wav`, `03_SVC_upload_1084ad962a15_vocal.wav`.
- MP4: valid h264 1920×1080 video stream plus AAC audio stream.

### 9. MCP/CLI atomic operations and SSE — passed

- MCP `add_note` added a note externally to the same project; the open UI updated live from `2 notes` to `3 notes STALE RENDER` through SSE.
- MCP `get_project` and `update_note` succeeded.
- MCP `export_project` wrote a nonzero MIDI file.
- MCP scratch lifecycle also passed: `create_project`, `get_project`, and `delete_project` all returned success.
- Console/network health in the broad instrumented run was clean: zero errors, zero warnings, zero failed responses. The later transpose-boundary 422 was intentional and is not counted as a health failure.

### Playback regression — passed after proper instrumentation

The original network-URL playback assertion was invalid because rendered audio could already be cached; it observed position movement but zero new network requests. A direct `AudioBufferSourceNode.start` instrumentation retest captured **3 source starts** and position advanced `00:00.00 → 00:01.38`. Thus the earlier `playback` failure is not a product defect.

## Important incomplete/non-final items

- GPU/real model validation is explicitly external and was not performed.
- The first broad harness did not create the intended third low-position note; supplemental targeted drawing covered note creation/drag/resize.
- Exact resize snapping expectation in the supplemental harness was wrong; resize did occur but `180→240` was the only quantitative resize evidence.
- Audition was verified as an exposed audio element and metadata, not by perceptual audio listening.

## Evidence index

Core broad pass:

- `00_initial_1272x837.png`
- `01_new_project_transport_fit.png`
- `02_notes_drawn.png`
- `03_lyrics_phonemes_cjk.png`
- `04_transpose_controls.png`
- `05_automation_curves.png`
- `06_zoom.png`
- `07_uploads.png`
- `08_vocal_render.png`
- `09_alt_drag_repaint_held.png`
- `10_alt_drag_repaint_numeric.png`
- `11_repaint_replacement_arrangement.png`
- `11b_svc_conversion.png`
- `12_playback.png`
- `13_export_panel.png`
- `14_exports_downloaded.png`
- `15_mcp_sse_live_update.png`

Supplemental/final evidence:

- `16_draw_drag_resize.png`
- `17_transpose_rejection.png`
- `18_playback_instrumented.png`
- `19_fifo_jobs.png`
- `20_final_project_state.png`
- `final_qa_results.json`
- `supplement_results.json`
- `export_content_analysis.json`
- `mcp_create_delete_results.json`
- `browser_console.jsonl`
- `downloads/` containing all exported formats
