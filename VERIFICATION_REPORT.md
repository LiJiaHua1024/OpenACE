# OpenACE Verification Report

Date: 2026-11-26  
Environment used here: CPU-only Linux sandbox; therefore all end-to-end orchestration audio used the explicitly labeled `OPENACE_CI_SYNTH_FIXTURE=1` fixture. **No claim of real neural output quality is made from this sandbox.** Real GPU acceptance is delegated to `scripts/verify_local_gpu.py` on a 12GB NVIDIA machine.

## Executive verdict

OpenACE is no longer a mock/MVP shell: it has a real local project model, strict acoustic invariant enforcement, a functional multi-canvas DAW-style browser workstation, real SoulX-Singer/ACE-Step subprocess adapters, working fixture-orchestrated render jobs, clip-aware playback/export, dynamic lyric MP4 generation, project-format exporters, MCP stdio/HTTP protocol tests, and MCP→SSE browser synchronization.

It is **not yet truthful to claim 100% commercial ACE Studio parity**. The largest blockers are absence of physical GPU validation, shallow expression-curve engine conditioning, missing advanced piano-roll/arrangement editing depth, and unvalidated commercial-host project compatibility. These are tracked honestly in `PARITY_MATRIX.md` and `KNOWN_ISSUES.md`.

## Automated test evidence

Commands run in `/home/ubuntu/repos/OpenACE`:

```bash
.venv/bin/python -m compileall -q openace scripts
cd frontend && npm run build
.venv/bin/pytest -q
.venv/bin/pip check
```

Results:

- Python compile: passed.
- Frontend TypeScript + Vite production build: passed.
- Test suite: **19 tests passed**.
- Dependency consistency: `pip check` reported no broken requirements.
- Console regression check in Chrome: no passive-wheel errors and no application console errors after favicon fix.

Representative coverage:

- transposition preserves every adjacent semitone interval and does not fold/clamp octaves;
- F0 sanitization masks 0Hz/unvoiced frames and corrects isolated octave artifacts without destroying deliberate leaps;
- vowels anchor exactly at note starts and consonants occupy the 40–90ms preonset zone;
- unknown lyrics raise errors rather than becoming “la”;
- pitch automation is serialized into SoulX target F0 metadata;
- SoulX preprocess uses the upstream `-m preprocess.pipeline` module entrypoint;
- explicit fixture refuses to run unless `OPENACE_CI_SYNTH_FIXTURE=1`;
- ACE-Step Vocal2BGM uses the upstream `complete` task rather than an incorrect cover task;
- MIDI+LRC roundtrip preserves Unicode lyrics;
- `.ustx`, `.svp`, `.vpr` exporters emit structural project data;
- MP4 lyric video export completes and its duration matches the input audio within 0.15s;
- MCP stdio initialization/tool invocation works against a real MCP client;
- MCP streamable HTTP initialization/tool listing works against a real MCP client.

## Browser/end-to-end evidence

Primary screenshot index: `artifacts/e2e_screenshots/`

Key current screenshots:

- `14_synced_timeline.png` — arrangement, piano roll and automation share synchronized zoom/scroll.
- `15_responsive_transpose_synced.png` — responsive transport no longer clips Import audio; transpose controls visible.
- `16_repaint_range_transpose.png` — Alt-drag yellow repaint region on arrangement plus transpose controls.
- `testing_agent/01_new_project_layout.png` — independent QA initial/new-project layout.
- `testing_agent/03_lyrics_phonemes.png` — lyric edit and phoneme lane.
- `testing_agent/04_zoom_synchronized.png` — zoom synchronization.
- `testing_agent/05_automation_pitch.png`, `06_automation_air.png`, `07_automation_tension.png` — automation brush editing.
- `testing_agent/08_uploaded_reference_and_source.png` — reference/source upload slots.
- `testing_agent/09_vocal_render_completed.png` — fixture vocal render completion and diagnostics.
- `testing_agent/12_bgm_repaint_svc_completed.png` — fixture Vocal2BGM/repaint/SVC job completion.
- `testing_agent/13_playback_moving.png` — transport playback position advancing.
- `testing_agent/14_export_panel.png` — export center.

Independent QA recording:

- `/home/ubuntu/screencasts/rec-e487d0a3-36a4-4faa-9f16-b86846a32985/rec-e487d0a3-36a4-4faa-9f16-b86846a32985-edited.mp4`

## Independent QA defects found and fixed in this iteration

| Defect found by browser QA | Current verification |
|---|---|
| Vocal2BGM and repaint created overlapping accompaniment clips, causing arrangement/playback/export inconsistency | Repaint now replaces the prior generated accompaniment clip; playback schedules every clip; master export deduplicates current render path and clip path. |
| No transpose/翻调 control in UI | Transpose −12/−1/+1/+12 controls added; uniform shift preserves intervals. |
| MCP edits did not propagate to the open browser UI | MCP now persists then publishes to the local FastAPI SSE bus. Browser verification showed the visible note count changing 4→5 without manual reload. |
| Repaint was numeric-only, no box selection | Alt-drag arrangement region selection added and synchronized with numeric Start/End fields. |
| MP4 showed raw LRC tags and duration mismatch | Export now writes timed ASS subtitles, burns them through ffmpeg/libass, and explicitly clamps duration to the audio duration; regression test passes. |
| Transport clipped `Import audio`; New button text overflowed | Responsive transport CSS verified at 1272×837; both controls fit. |
| Arrangement labels were covered by clips | Redundant row labels removed; track identity remains in the dedicated track list/order/color strip. |
| Ctrl+wheel zoom emitted passive-listener console errors | `preventDefault` removed from React wheel handlers; repeat zoom produced no console errors. |
| Missing favicon caused a console 404 | SVG favicon added; subsequent browser check had no application console errors. |

## MCP/SSE verification details

1. Launched FastAPI workstation server with `OPENACE_CI_SYNTH_FIXTURE=1`.
2. Opened production frontend in Chrome/Playwright.
3. Posted the exact project payload shape used by the MCP loopback notifier to `/api/internal/project-updated`.
4. Browser track metadata changed from `4 notes` to `5 notes` without manual project switching/reload.
5. MCP stdio and streamable HTTP tests independently passed real client protocol initialization and tool invocation/listing.

## Audio/import verification details

- Uploaded an existing rendered WAV through `/api/import/audio`.
- API returned HTTP 200 and a new editable project containing four stable monophonic extracted notes.
- The endpoint returns HTTP 422 when no stable pitch contour exists rather than fabricating notes.

## Real GPU acceptance procedure

On a local 12GB NVIDIA machine:

```bash
git pull
python3 -m venv .venv
.venv/bin/pip install -e '.[gpu]'
python scripts/verify_local_gpu.py --hf-endpoint https://hf-mirror.com  # optional mirror
```

Expected artifacts:

- upstream source clones under `external/`;
- public model weights under `models/`;
- real SoulX inference smoke output;
- real ACE-Step inference smoke output;
- machine-readable `artifacts/local_gpu/report.json`.

This script intentionally removes `OPENACE_CI_SYNTH_FIXTURE` from child environments and is not a fixture test.

## Explicit non-claims / limitations

- No physical GPU inference was performed in this sandbox.
- No commercial ACE Studio proprietary assets, vocals, UI assets, or API keys are bundled.
- `.ustx`/`.svp`/`.vpr` files have structural tests but have not been opened in their licensed target applications.
- Automation lanes other than Pitch are not yet engine-conditioned.
- MP4 is synchronized lyric video, not polished commercial karaoke motion graphics.


## Final independent regression QA after defect fixes

A second persistent testing-agent run re-tested the production UI in real Chrome/Playwright at exactly 1272×837. Results are stored in `artifacts/e2e_screenshots/final_qa/`; recording: `/home/ubuntu/screencasts/rec-627854b9-e979-4b13-af47-06fbc93aab5c/rec-627854b9-e979-4b13-af47-06fbc93aab5c-edited.mp4`.

Passed in that run:

- transport fit at 1272×837, favicon/network/console health;
- piano-roll creation, Mandarin lyrics/phonemes, pitch/air/tension automation;
- transpose +1/-1 visible and correct;
- fixture vocal render, Vocal2BGM, repaint replacement (one accompaniment clip), playback URLs;
- all seven export formats;
- fresh MP4 duration within frame quantization and correctly timed Chinese ASS subtitles after installing host CJK font;
- MCP `add_note` live-updated the open browser from 3 to 4 notes through SSE.

That run exposed one remaining visualization bug: Alt-drag updated numeric repaint times but the yellow region was not drawn. This has now been fixed and specifically re-verified: the arrangement canvas contains 946 yellow-range pixels after Alt-drag, numeric fields display editor-friendly rounded values (`1.63`, `2.48`), and no console errors occurred (`artifacts/e2e_screenshots/17_repaint_range_visible_fixed.png`).

## Iteration 2 — piano-roll professional editing depth

Branch focus: marquee/multi-select, clipboard editing, velocity lane, quantization, and context-menu operations.

Implemented and verified:

- Select-tool marquee rectangle selects multiple notes on canvas.
- Shift-click additive selection and multi-note move/resize share one transaction.
- Multi-note pitch movement applies one uniform delta to every selected note, preserving adjacent semitone intervals exactly while constraining the whole gesture to the editable pitch range.
- Ctrl+C/Ctrl+V/Ctrl+D copy, paste at playhead, and duplicate selected notes; the toolbar and right-click menu expose the same operations.
- Q/Quant button quantizes selected notes (or all notes when nothing is selected) to the active grid.
- Bottom velocity lane edits per-note velocity by dragging; velocities persist and are exported through MIDI/VPR paths.
- Right-click context menu exposes Copy/Paste/Duplicate/Quantize/Delete.
- Repaint overlay no longer pollutes arrangement by default; it appears only after an explicit nonzero region is drawn or entered.
- Toolbar density/polish adjusted so edit controls fit without clipped hint text.

Automated regression added: `tests/test_piano_roll_e2e.py` launches an isolated FastAPI server and drives system Chrome through Playwright. It verifies three-note creation, marquee selection of two notes, clipboard paste/duplicate producing seven notes, velocity-lane editing below velocity 20, context-menu visibility, and zero browser console errors.

Current full-suite result after this iteration: **20 tests passed**; frontend production build passed; backend compile passed.

Independent adversarial QA then verified the feature in visible Chrome at exact 1400×900 with a 1272×837 responsive glance (`artifacts/e2e_screenshots/piano_depth_qa/`). It confirmed marquee visuals, clipboard/duplicate persistence, undo/redo, multi-select movement, velocity persistence, context-menu operations, repaint overlay behavior, toolbar fit, and zero console/network failures. QA exposed one real defect: negative horizontal multi-note movement was swallowed because the grid-snapping helper clamped negative deltas to zero. This was fixed by separating absolute-position snapping (`snap`) from signed gesture snapping (`snapDelta`), and the automated Chrome regression now explicitly verifies that moving two selected notes later/up then earlier/down restores their exact start ticks and pitches. A final independent targeted real-Chrome recheck (`artifacts/e2e_screenshots/piano_depth_qa/final_recheck/`) confirmed exact restoration `(840,61)/(1440,63) → (360,60)/(960,62)` with no console or network failures.

## Iteration 3 — arrangement waveform truth and independent clip movement

Branch focus: remove fake waveform visualization and make arrangement editing semantics match playback/export.

Implemented and verified:

- Audio clips now decode their real render files in the browser and draw measured waveform peaks; placeholder occupancy stripes were removed.
- Audio clips drag independently rather than moving the entire track.
- Contiguous vocal notes drag as grouped musical phrases while preserving relative spacing.
- Signed drag deltas work in both directions and clamp only at the timeline boundary.
- Playback/master export already consume `clip.start_ticks`, so arrangement clip movement is reflected in the actual audio path rather than being a visual-only operation.
- New isolated-server real-Chrome regression `tests/test_arrangement_e2e.py` generates asymmetric test-only fixture audio, verifies decoded waveform pixels inside the clip interior, and verifies clip dragging `0 → 480 → 0` ticks with backend persistence and no browser console errors.

Independent arrangement QA initially exposed a real live-playback scheduling defect: a clip moved later in the timeline rendered/exported correctly but started immediately in WebAudio playback. `App.tsx` now schedules future clips with an AudioContext delay while positive seeks still start immediately at the correct intra-clip offset. The regression test instruments `AudioBufferSourceNode.start` and verifies a 480-tick clip delay schedules `when-now≈0.5s` with `offset=0`.

Final independent real-Chrome recheck passed: decoded varying waveform remained visible; clip drag persisted `0→480→0`; future playback measured `when-now=0.500s`, `offset=0`; positive seek measured `offset=0.5`; contiguous vocal phrase movement remained exact; repaint Alt-drag remained intact; zero console/network failures. Focused evidence is indexed in `artifacts/e2e_screenshots/arrangement_qa/`.

Validation after the fix: frontend production build passed; Python compile passed; full automated suite reached 21 passed.

## Iteration 4 — arrangement trim/split with source-time correctness

Branch focus: turn arrangement clips from movable render-file references into editable timeline segments.

Implemented and verified:

- `AudioClip.offset_ticks` now represents the source-file insertion point; `duration_ticks` is the visible timeline segment length.
- Left/right edge dragging trims or re-extends clips within source bounds. Left trims move `start_ticks`, `offset_ticks`, and `duration_ticks` together so source-time continuity is preserved.
- Right-click `Split at cursor` creates contiguous non-overlapping clips whose offsets remain sample-accurate in tick time.
- WebAudio playback honors timeline delay, source offset, and segment duration. A rapid duplicate-start race is guarded while buffers decode.
- Master WAV export slices the same source offset/duration rather than always rendering the entire file.
- Waveform rendering remaps to the visible segment rather than compressing the whole source into every trimmed clip.
- `tests/test_arrangement_e2e.py` verifies trim `(480,480,960)`, split into `(480,480,480)+(960,960,480)`, and playback delay/offset/duration `(0.5,0.5,0.5)` plus `(1.0,1.0,0.5)`.
- `tests/test_interop.py::test_master_export_honors_clip_source_offset_and_duration` verifies backend export slicing.

Independent visible-Chrome QA passed: trim cursor/handles, waveform remapping (quiet/loud spans match source regions), split menu, contiguous clips, undo/redo, outward re-extension, positive seek, master export placement, and zero console/network errors. Evidence is indexed in `artifacts/e2e_screenshots/arrangement_trim_qa/`.
Validation after iteration 4: frontend production build passed; Python compile passed; full automated suite reached 22 passed.


## Iteration 5 — truthful Dynamic expression post-processing

Branch focus: make the Dynamic lane affect rendered audio without falsely claiming unsupported neural conditioning.

Implemented and verified:

- `openace/core/expression.py` interpolates Dynamic automation in project time and applies it as post-render gain: neutral `0.5`, ±6 dB range, vectorized sample-rate interpolation, and uniform peak protection above `0.98`.
- Vocal render output is rewritten after processing; diagnostics and completed jobs explicitly label `Dynamic lane gain post-processing (not neural conditioning)`.
- Empty lanes remain transparent AI/auto mode.
- The normalized automation lane neutral guide now represents value `0.5` instead of an arbitrary visual position.
- Unit tests verify interpolation, relative gain, transparent empty lanes, and clipping protection.
- Explicit fixture integration proves a rendered two-note vocal becomes measurably louder across a rising curve and that job provenance remains visible.

Independent visible-Chrome QA drew exact endpoints `(0,0.0)` and `(960,1.0)`, rendered fixture audio, and measured first/second note RMS `0.17056 → 0.34032` (`2.00×`) with peak `0.726`, no clipping, working playback, and zero console/network errors. QA initially exposed that the final job message dropped the Dynamic provenance; this was fixed and covered by regression assertion. Evidence is indexed in `artifacts/e2e_screenshots/dynamic_expression_qa/`.
Validation after iteration 5: frontend production build passed; Python compile passed; full automated suite reached 26 passed.


## Iteration 6 — durable render-job recovery

`RenderService` now atomically persists job records in `data/renders/jobs.json` on every state publication. A restarted service reloads completed/failed history and converts previously queued/running jobs into explicit failures with `backend restarted before job completion`, avoiding silent loss or misleading perpetual-running state. Regression coverage constructs a running job, recreates the service, and verifies the recovered failed state.

## Iteration 7 — phoneme placeholder validation enforcement

Manual and generated phoneme inventories now both pass through `validate_phoneme_inventory`; a manually supplied literal placeholder `la` is rejected instead of slipping through editing/persistence. Regression coverage verifies `ensure_note_phonemes` raises `PhonemeError` for that forbidden placeholder.

## Iteration 8 — per-note vibrato editing consumed by SoulX F0

Implemented and verified:

- Piano-roll note bodies draw a parameter-driven vibrato indication when `note.vibrato` exists.
- Toolbar/context-menu vibrato editor supports enable/disable, start ratio, depth cents, rate Hz, and phase. Changes are transactional, so one undo restores the prior state.
- `tests/test_acoustic_invariants.py` now proves vibrato changes SoulX target F0 metadata rather than remaining editor-only data.
- `tests/test_piano_roll_e2e.py` opens the real context menu in Chrome, enables vibrato, edits depth to `80¢`, verifies backend persistence, and verifies Ctrl+Z removes it as one transaction.

Browser QA evidence:

- Initial real-Chrome QA (`artifacts/e2e_screenshots/vibrato_qa/`) verified exact UI/backend persistence (`start_ratio=0.6`, `depth_cents=80`, `frequency_hz=6.2`, `phase=1.43`), one-step undo/redo, note-body indication, and zero console/network failures. It exposed a low-note context-menu popover overflow into the automation lane.
- The overflow was fixed by clamping editor placement inside the piano-roll wrap. Focused revalidation (`artifacts/e2e_screenshots/vibrato_qa_clamp/`) measured the low-note popup fully inside the wrap with bottom `623` vs wrap bottom `643`, controls still usable, toolbar placement correct, and zero console/network failures.

## Iteration 9 — per-note pitch handles and continuous F0 interpolation

Implemented and verified:

- Added the piano-roll `∿` pitch-handle tool (`P`). Clicking a note creates a handle, dragging moves it, and Alt+click deletes it. Handles and linear pitch segments are drawn directly on note bodies.
- Replaced exact-frame-only `note.pitch_curve` consumption with continuous linear interpolation shared by the SoulX metadata builder and diagnostic target-F0 curve.
- `tests/test_acoustic_invariants.py` proves a `0→100¢` pitch-handle ramp is interpolated into both SoulX target F0 and diagnostic target F0 at intermediate frames.
- `tests/test_piano_roll_e2e.py` creates two handles in real Chrome, verifies positive/negative cent persistence, drags an existing handle lower, Alt-click deletes it, and verifies backend state.

Browser QA evidence:

- Real-Chrome QA (`artifacts/e2e_screenshots/pitch_handles_qa/`) verified toolbar/`P` activation, exact signed handle persistence, crossing drags with sorted output, Alt-click deletion, disk persistence, undo/redo, green segment rendering, and zero console/network failures.
- QA found no blocking defect. It flagged cramped default-row handles and missing numeric precision feedback; follow-up polish enlarged handles slightly, renamed the toolbar control to `∿ Pitch`, and added a live `offset ms · ±cents` readout while dragging.

## Iteration 10 — arrangement clip fades and clip gain

Implemented and verified:

- `AudioClip` now persists `fade_in_ticks`/`fade_out_ticks`; arrangement top-corner handles drag linear fades, waveform peaks are attenuated by the fade envelope, and split redistributes fades so internal cut edges do not acquire unintended fades.
- WebAudio playback schedules real `AudioParam` gain ramps for clip fades; `gain_db` is now also honored in monitor playback instead of remaining dead model data.
- Master WAV export applies the same linear fade envelopes to source slices and honors `gain_db` in clip mixing.
- `tests/test_interop.py` verifies exported fade-in/fade-out shape; `tests/test_arrangement_e2e.py` drags both fade handles in real Chrome, verifies persistence, observes at least two audio-param ramp calls during playback, and verifies split fade redistribution.

Browser QA evidence:

- Real-Chrome QA (`artifacts/e2e_screenshots/arrangement_fades_qa/`) verified fade persistence/direction, waveform attenuation, body/trim/fade zone separation, split redistribution, and real AudioParam ramps. It exposed two defects: visible inner fade endpoints were not hit-testable, and outward trim could restore `2399` rather than `2400` ticks due floored decode duration.
- Fixes made endpoint dragging authoritative, enlarged handles, rounded decoded source-end ticks, and exposed numeric clip gain in the clip context menu. Focused recheck (`artifacts/e2e_screenshots/arrangement_fades_fix_qa/`) verified endpoint dragging without clip movement, exact `2400`-tick restoration, and stepped gain persistence; it exposed direct `-6` typing coercion.
- The gain input is now uncontrolled while typing and commits only complete numeric input, preserving negative signs. The arrangement regression covers endpoint dragging and `-6 dB` persistence.
