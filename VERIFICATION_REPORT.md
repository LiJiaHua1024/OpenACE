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

`RenderService` atomically persists job records in `data/renders/jobs.json` on every state publication. Iteration 6 initially converted interrupted queued/running jobs into explicit failures to avoid silent loss or misleading perpetual-running state. Iteration 21 supersedes that fallback with automatic requeue for jobs whose original inputs are durable; legacy jobs missing required inputs still fail loudly.

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

## Iteration 11 — diagnostic target pitch consistency

The diagnostic target-F0 curve now includes the track-level pitch automation envelope in addition to per-note pitch handles and vibrato, matching the SoulX metadata path. Regression coverage verifies the automated target differs by the expected interpolated cents at intermediate frames.

## Iteration 12 — Air lane high-frequency DSP

The Air automation lane now affects rendered vocals as explicitly labeled post-render DSP rather than remaining editor-only data. The implementation extracts the 3 kHz+ residue already present in the rendered vocal and reinforces or attenuates it according to the lane; it does not inject synthetic noise or pretend SoulX has neural Air conditioning. Unit coverage verifies high-frequency content increases across a rising Air envelope and empty lanes remain transparent; fixture-render integration verifies the lane reaches the job pipeline and final provenance message.

## Iteration 13 — manual phoneme override and sequence-correct timing

Manual note phonemes can now be edited from the piano-roll context menu as space-separated symbols, timed by the backend, validated against empty/placeholder/no-vowel input, and reset to automatic lyric-derived phonemes. Phoneme timing is now sequence-correct: only pre-vowel consonants receive negative beat-preonset offsets, while post-vowel consonants remain after the beat-anchored vowel. Real-browser regression covers override persistence/reset and English coda placement; backend callers pass exact project-tempo note durations.

## Iteration 14 — cross-track clipboard regression proof

Real-browser regression now proves note clipboard state survives switching to a newly created vocal track and pastes the copied note into that track. This closes the cross-track clipboard gap; large-project sustained-performance profiling remains open.

## Iteration 15 — draggable beat-anchored phoneme boundaries

Implemented and verified:

- Phoneme lane rendering now positions segments by real `start_ms`/`duration_ms` relative to the beat-anchored note start, including negative pre-vowel consonants, and scales with the shared piano-roll zoom.
- Internal boundaries, first-consonant onset, and final end expose visible drag handles. The first-vowel 0ms anchor is locked; drags move contiguous neighbor boundaries transactionally with positive-duration constraints and a live millisecond readout.
- Backend validation rejects positive/nonpositive durations, gaps, overlaps, and first-vowel starts not anchored at 0ms. Generated timing now caps multi-coda allocation so short notes still end exactly at note duration rather than overrunning it.
- `tests/test_acoustic_invariants.py` covers invalid manual timing and short multi-coda exact end timing; `tests/test_piano_roll_e2e.py` drags a real English `sing` vowel/coda boundary in Chrome, verifies backend contiguity/persistence, and verifies Ctrl+Z restoration.

Browser QA evidence:

- The first independent QA run exposed a stale-backend false positive (`s/ŋ/ɪ` ordering from an old server process). After restarting from the current working tree, focused visible-Chrome QA in `artifacts/e2e_screenshots/phoneme_boundaries_qa/` passed: correct `s(-45,45), ɪ(0,1055), ŋ(1055,70)` layout, internal/onset/end dragging, persistence, exact undo/redo, col-resize hit zones, no accidental breath creation, and no console errors.
- Key evidence: `rerun_01_phonemes_before.png`, `rerun_05_after_three_drags.png`, `PHONEME_BOUNDARIES_RERUN_REPORT.md`, and `phoneme_rerun_results.json`.

Validation after iteration 15: frontend production build passed; full automated suite reached 39 passed.

## Iteration 16 — Energy/Tension expression DSP

Implemented and verified:

- Energy automation now affects rendered vocals as explicitly labeled post-render harmonic-density DSP. Positive values add harmonics through parallel soft saturation of the actual vocal; negative values blend toward a softened low-passed version. Peak protection prevents clipping.
- Tension automation now reinforces or attenuates the 0.9–5.5 kHz articulation/presence band extracted from the actual vocal. It is distinct from Air's breathy 3 kHz+ residue and explicitly labeled as non-neural DSP.
- RenderService applies Energy/Tension after Dynamic/Air, rewrites the WAV when any lane is active, and exposes lane names in final job messages plus explicit provenance in `diagnostic.png`.
- Unit coverage proves positive Energy increases harmonic density, positive Tension increases presence-band level, and empty lanes remain transparent. Fixture integration verifies the completed job message.

Browser/audio QA evidence:

- Independent visible-Chrome QA in `artifacts/e2e_screenshots/expression_energy_tension_qa/` restarted a current fixture backend, drew exact neutral→high Energy/Tension curves, rendered, verified undo/redo/reload persistence, job text `completed with Energy/Tension post-processing`, diagnostic non-neural provenance, playback, and zero console/network errors.
- Isolated positive late-window measurements versus neutral: Energy-only total RMS `2.109×` and 0.9–5.5k RMS `3.394×`; Tension-only total RMS `1.020×` and 0.9–5.5k RMS `1.202×`; combined total RMS `2.149×` and 0.9–5.5k RMS `4.677×`. Negative curves reduced the late presence band to `0.799×` without clipping.
- Key evidence: `06_energy_tension_job_card.png`, `evidence_isolated_audio_comparison.png`, `evidence_diagnostic_provenance_crop.png`, `ENERGY_TENSION_QA_REPORT.md`, and `energy_tension_results.json`.

Validation after iteration 16: frontend production build passed; full automated suite reached 43 passed.

## Iteration 17 — Falsetto spectral-tilt DSP

Implemented and verified:

- Falsetto automation now affects rendered vocals as explicitly labeled post-render spectral-tilt DSP. Positive values thin the ≤650 Hz chest-resonance band and reinforce existing >2.2 kHz vocal residue; negative values create a chestier/pressed tilt. It intentionally does not shift F0 and injects no synthetic noise.
- RenderService applies Falsetto after the other expression lanes, exposes it in job messages, and writes `Falsetto lane spectral-tilt DSP (not neural conditioning)` into diagnostic provenance.
- Unit coverage proves positive tilt decreases low/high spectral ratio without moving the dominant pitch, negative tilt increases chest ratio, and empty lanes remain transparent. Fixture integration verifies the completed job message.

Browser/audio QA evidence:

- Independent visible-Chrome QA in `artifacts/e2e_screenshots/expression_falsetto_qa/` restarted a current fixture backend, drew exact neutral→high Falsetto curves, verified undo/redo/reload persistence, job text `completed with Falsetto post-processing`, diagnostic non-neural provenance, playback, and zero console/network errors.
- Positive measured late-window chest band fell to `0.802×` and upper/chest tilt rose to `1.148×`; negative chest band rose to `1.177×` and upper/chest tilt fell to `0.911×`. Dominant F0 remained exactly `260.87 Hz` in neutral, positive, and negative renders.
- Fixture limitation is explicitly recorded: the CI fixture has almost no pre-existing >2.2 kHz residue, so absolute upper-residue reinforcement is not meaningfully measurable in fixture mode even though directional tilt is verified.
- Key evidence: `05_falsetto_job_card.png`, `evidence_falsetto_audio_analysis.png`, `evidence_diagnostic_provenance_crop.png`, `FALSETTO_QA_REPORT.md`, and `falsetto_results.json`.

Validation after iteration 17: frontend production build passed; full automated suite reached 47 passed.

## Iteration 18 — automatic arrangement crossfades

Implemented and verified:

- Overlapping clips on the same arrangement track now receive automatic equal-power crossfades. Earlier/outgoing clips use cosine-shaped attenuation and later/incoming clips use complementary sine-shaped gain; no clip metadata mutation or manual fade overwrite is required.
- Master WAV export applies the same overlap envelopes vectorized at audio rate. Regression coverage verifies exact boundary/midpoint gains and exported overlap energy shape.
- WebAudio playback composes manual fades, clip gain, and automatic crossfades into scheduled `AudioParam` automation with 12-point equal-power approximations per overlap.
- Arrangement waveforms attenuate according to automatic crossfade gain. Cyan overlap shading, complementary curves, and a compact `XF` badge visualize the automatic region without overwriting manual fades.

Browser/audio QA evidence:

- Independent visible-Chrome QA in `artifacts/e2e_screenshots/arrangement_crossfade_qa/` used real UI drags to create overlap and verified cyan shading confined to x `231–288`, correct outgoing/incoming curve direction, undo/redo removal/restoration, trim following, 26 scheduled AudioParam ramps, manual fade composition, playback, and zero console/network errors.
- Export measurement: overlap/outside broadband RMS `0.997×` versus simple summing reference `~1.414×`; outgoing low-band cosine correlation `0.99988`; incoming high-band sine correlation `0.99962`.
- Initial QA found the long `auto xfade` label crowded the clip label. It was replaced with a compact `XF` badge; focused recheck (`evidence_xf_badge_zoom.png`) confirmed clear separation and understandable curves.
- Key evidence: `evidence_crossfade_visual_states.png`, `evidence_crossfade_export_analysis.png`, `evidence_xf_badge_zoom.png`, `ARRANGEMENT_CROSSFADE_QA_REPORT.md`, `XF_BADGE_RECHECK_ADDENDUM.md`, and `crossfade_results.json`.

Validation after iteration 18: frontend production build passed; full automated suite reached 49 passed.

## Iteration 19 — arrangement clip context operations

Implemented and verified:

- Arrangement clip context menus now support Copy, Paste at cursor, Duplicate, Delete, Split at cursor, and numeric gain. Empty arrangement space exposes Paste at cursor when the internal clip clipboard is populated.
- Pasted clips preserve path, label, source offset, visible duration, manual fades, and gain. Paste works across audio-capable tracks at snapped cursor position; Duplicate inserts immediately after the source clip. All mutations participate in normal undo/redo.
- Menus are compact two-column grids with inline gain editing and measured-position clamping inside the 132px arrangement strip.

Browser QA evidence:

- Independent visible-Chrome QA in `artifacts/e2e_screenshots/arrangement_clip_ops_qa/` verified copy is non-mutating, same-track and cross-track paste at tick `2400`/`2760`, exact preservation of `offset_ticks=240`, `duration_ticks=960`, `fade_in=120`, `fade_out=120`, `gain_db=-6`, duplicate insertion at `960`, delete/undo/redo, crossfade behavior after dragging a duplicate into overlap, playback, WAV export, and zero console/network errors.
- Initial QA found the full menu overflowed into the piano roll and sidebar. Two focused rechecks diagnosed a CSS specificity failure and then a residual 2px clamp error. The final implementation uses the measured 130px full-menu height with 1px top/bottom containment inside the 132px strip; empty menus retain 4px margins.
- Key evidence: `evidence_clip_ops_montage.png`, `evidence_menu_overflow_recheck_montage.png`, `evidence_menu_overflow_recheck2_montage.png`, `ARRANGEMENT_CLIP_OPS_QA_REPORT.md`, both menu addenda, and `clip_ops_results.json`.

Validation after iteration 19: frontend production build passed; arrangement browser regression passed; full automated suite remains 49 passed.

## Iteration 20 — large-project piano-roll performance architecture

Implemented and verified:

- The piano-roll static scene and moving playhead are now separate stacked canvases. Playback no longer repaints thousands of notes/grid rows every frame; the overlay is pointer-transparent and the static canvas remains interactive.
- Canvas backing stores in PianoRoll, ArrangementView, and AutomationLane resize only when dimensions actually change. Per-note gradients are cached.
- Dense views use honest level-of-detail rendering: when more than 220 notes are visible, unreadable overlapping labels/strokes are elided and solid fills replace gradients. Sparse projects retain full labels, phonemes, gradients, strokes, vibrato, and pitch-handle detail.
- `tests/test_performance_e2e.py` seeds 3000 dense overlapping notes, continuously scrolls within the dense region at 1400×900@2x, and asserts at least 55 FPS with p95 frame time ≤22ms.

Performance evidence:

- Automated regression evidence in `artifacts/e2e_screenshots/performance_large_project/performance_metrics.json`: playback `60.002 FPS`, p95 `16.7ms`; continuous dense scrolling `60.002 FPS`, p95 `16.7ms` with 3000 notes at 1400×900@2x.
- Independent visible-Chrome QA in `artifacts/e2e_screenshots/piano_performance_qa/` verified sparse labels/phonemes/gradients/handles, selection/marquee/move/zoom/scroll/static redraw, playhead alignment, dense LOD rendering, dense click/drag/undo, playback `59.34 FPS` p95 `16.8ms`, continuous dense scrolling `60.00 FPS` p95 `16.7ms`, and zero console/network errors.
- Key evidence: `dense_project_dpr2.png`, `performance_metrics.json`, `01_sparse_initial.png`, `14_dense_playhead_late.png`, `PIANO_PERFORMANCE_QA_REPORT.md`, and `piano_performance_results.json`.

Validation after iteration 20: frontend production build passed; performance regression passed; full automated suite reached 50 passed.

## Iteration 21 — automatic render-job requeue after restart

Implemented and verified:

- `RenderJob` now durably stores source audio, reference voice, caption, and repaint interval inputs required to reconstruct music/SVC work. SVS jobs are recoverable from project/track identity alone.
- FastAPI startup scans persisted queued/running jobs. Recoverable jobs are reset to `queued`, marked `requeued after backend restart`, and rerun serially through the same render service. Legacy jobs lacking required inputs become explicit failures instead of silently disappearing.
- CLI, MCP, and HTTP job creation all persist the same recovery inputs.
- Backend regressions prove: interrupted SVS jobs requeue and complete through `recovery_coro`; repaint source/caption/start/end survive a service restart; unrecoverable legacy music jobs fail loudly; duplicate in-process recovery scans do not schedule the same job twice.
- End-to-end restart proof launched the real FastAPI service with `OPENACE_CI_SYNTH_FIXTURE=1`, created a project/note/job, killed the backend, restored the job to a simulated power-loss running state in `jobs.json`, restarted the backend on the same data directory, and observed the job automatically complete with real output and diagnostic files. Evidence: `artifacts/e2e_screenshots/render_recovery_proof.json`.

Validation after iteration 21: frontend production build passed; Python compile passed; full automated suite reached 53 passed, including the real FastAPI restart/requeue regression.

## Iteration 22 — track-level context operations

Implemented and verified:

- Track cards now provide both right-click and visible `⋯` entry points to a real context menu: duplicate, move up/down, six color swatches, and delete.
- Duplicate performs a deep copy with fresh track/note/clip/breath IDs, inserts immediately after the source, and selects the copy. Delete/reorder/color are undoable project operations persisted through the existing project API.
- Menu geometry clamps inside narrow and short viewports; Escape/outside click close it. Zero-track deletion is safe and undoable rather than crashing the workstation.
- `tests/test_track_operations_e2e.py` verifies exact backend persistence for duplicate content/fresh note IDs, reorder, color, delete, undo/redo, menu close behavior, and zero console errors. Evidence: `artifacts/e2e_screenshots/track_operations/`.
- Independent visible-Chrome QA in `artifacts/e2e_screenshots/track_operations_qa/` verified top/bottom/narrow clamping, duplicate fresh IDs/selection, arrangement color propagation, delete/undo/redo, reload persistence, single-track delete-all recovery, and rename/mute/solo/volume/pan/add-track regressions with zero console/network failures.

Validation after iteration 22: frontend production build passed; Python compile passed; full automated suite reached 54 passed.

## Iteration 23 — standards-compliant WAV master loudness

Implemented and verified:

- Replaced approximate master normalization with a ffmpeg-validated export pipeline. OpenACE first applies transparent constant-gain normalization when true-peak headroom permits; when linear gain cannot satisfy both targets it falls back to two-pass ffmpeg `loudnorm` using measured input statistics.
- Export validation independently measures the final WAV with ffmpeg EBU R128 loudness/true-peak statistics. Compliant output must be within ±0.3 LU of `-14.0 LUFS` and strictly below `-1.0 dBTP`; otherwise export raises a loud error rather than silently shipping a false master. Silence remains a explicit no-signal bypass because integrated loudness is undefined.
- Regression coverage now proves both a sustained musical mix and peaky material whose linear normalization cannot fit under the true-peak ceiling. Existing clip offset/fade/crossfade tests continue to pass with oscillating program material rather than physically impossible constant-DC loudness fixtures.
- Evidence in `artifacts/loudness_validation.json`: musical input `-20.44 LUFS/-15.21 dBTP` exported as `-13.95 LUFS/-8.77 dBTP`; peaky input `-19.72 LUFS/-1.05 dBTP` exported through the dynamic fallback as `-14.11 LUFS/-1.10 dBTP`.
- ffmpeg is now explicitly documented as a required local runtime dependency for standards-compliant WAV/MP4 export.

Validation after iteration 23: frontend production build passed; Python compile passed; full automated suite reached 56 passed.

## Iteration 24 — local ASR lyrics in audio import

Implemented and verified:

- `/api/import/audio` now combines librosa/pYIN monophonic transcription with local faster-whisper word-level timestamps. The endpoint runs both CPU-heavy stages in worker threads, stores the detected language on the imported track, and assigns each ASR word once to the note with maximum temporal overlap or a near onset within 300ms.
- Import fails loudly when ASR produces no timestamped words or none can be aligned. Unaligned notes remain visually blank; the piano roll no longer draws em-dash pseudo-lyrics for empty notes. No `la`, `啦`, hyphen, or fabricated placeholder is inserted.
- The TransportBar import control now shows `Transcribing audio…` and disables the file input while ASR/pitch extraction is in progress.
- Unit/API regressions cover Chinese concatenation, English spacing, near-onset tolerance, per-word single assignment, successful endpoint persistence, and loud failure when words cannot align.
- Real validation with the tiny faster-whisper model against the local SoulX example vocal produced 13 timestamped words, 44 extracted notes, 13 aligned words, 11 lyric-bearing notes, language `en`, and zero placeholder lyrics. Committed evidence redacts lyric text: `artifacts/asr_import_validation.json`.
- Independent visible-Chrome QA uploaded the real MP3 through the browser. It verified the busy state, English track metadata, 44 rendered notes, visible real lyric text, zero white-text pixels on sampled empty-lyric notes after the em-dash fix, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/asr_import/fix_04_after_import_settled.png`, `ASR_IMPORT_FIX_RECHECK_REPORT.md`, `asr_import_fix_results.json`, and the recheck montage.

Validation after iteration 24: frontend production build passed; Python compile passed; full automated suite reached 60 passed.

## Iteration 25 — OpenUtau 0.10 USTX contract correction

Implemented and verified:

- Cloned and inspected the actual OpenUtau source (`external/OpenUtau`, validation reference only) instead of guessing the file format. Corrected `.ustx` export to the current 0.10 contract: no serialized top-level `resolution` because OpenUtau marks it `YamlIgnore` and fixes it at 480, exact serialized `UNote` keys, and mandatory two-point default pitch data because OpenUtau validation indexes `pitch.data[0]`.
- Fixed real unit mismatches: pitch-handle cents now convert to OpenUtau 0.1-semitone `y` units; OpenACE vibrato start ratio converts to OpenUtau end-weighted vibrato length, frequency to millisecond period, depth/phase within OpenUtau ranges; linear track volume converts to OpenUtau's -24..+12 dB fader scale; pan converts from -1..1 to -100..100; hex colors map to nearest named OpenUtau palette color; the phonemizer id is the real `OpenUtau.Core.DefaultPhonemizer`.
- Automation now uses OpenUtau curve schema (`abbr`, `xs`, `ys`). Dynamic maps from normalized ±6dB to OpenUtau `dyn` decibel×10 units and pitch deviation maps directly to `pitd` cents. Voice parts include beat-aligned durations.
- Manual phoneme symbols remain overrides, but OpenACE millisecond offsets are no longer falsely written into OpenUtau's tick-delta `offset` field.
- Source-derived regressions cover exact note shape/default pitch points, unit conversions, vibrato conversion, curve schema, phoneme override shape, color/phonemizer/track units, non-480 PPQ scaling into OpenUtau’s fixed resolution, and beat-aligned part duration.
- Independent visible-Chrome QA clicked the real USTX export control, verified the browser download/backend HTTP 200, UI health, parsed `ustx_version=0.10`, exact note keys, pitch/vibrato/curve/track conversions, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/ustx_contract/`, especially `USTX_CONTRACT_QA_REPORT.md`, `ustx_contract_export.ustx`, and `02_workstation_after_ustx_click.png`.

Validation after iteration 25: frontend production build passed; Python compile passed; full automated suite reached 62 passed.

## Iteration 26 — Synthesizer V SVP contract correction

Implemented and verified:

- Corrected `.svp` export using OpenUtau's real SVP importer as a source reference. Vocal groups now have deterministic UUIDs and `mainRef` carries matching `groupID`, blick offsets, database name, and voice defaults instead of hiding voice metadata in an ignored group field.
- Fixed vibrato time units: `tF0VbrStart` is now seconds within the note rather than incorrectly writing OpenACE's ratio directly.
- Pitch, Dynamic, Tension, and Air automation now export as flattened blick/value curves: pitchDelta in semitones, loudness in dB, tension/breathiness centered into -1..1. Timing remains scaled through the 705600000-blicks-per-quarter contract.
- Source-derived regressions cover group/reference identity, database/voice shape, vibrato depth/frequency/start seconds, and exact flattened automation values.
- Independent visible-Chrome QA clicked the real SVP export control, verified browser download/backend HTTP 200, UI health, matching group/mainRef IDs, correct vibrato/automation values, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/svp_contract/`.

Validation after iteration 26: frontend production build passed; Python compile passed; full automated suite reached 63 passed.

## Iteration 27 — USTX arrangement wave parts

Implemented and verified:

- `.ustx` export no longer silently drops arrangement audio clips. Each clip becomes a real OpenUtau `wave_parts` entry with measured `file_duration_ms`, a path relative to the exported project, fixed-480 tick-scaled `position`, source-offset `skip`, computed `trim`, and scaled `fadein`/`fadeout`.
- The trim calculation follows OpenUtau's actual `UWavePart.UpdateDuration` semantics so the host derives exactly the OpenACE clip duration from full source duration minus skip/trim. Missing/unmeasurable audio fails loudly instead of writing a false part.
- No invalid schema extensions or fake per-clip gain fields are emitted; per-clip gain remains a documented interoperability limitation because UWavePart has no such field.
- Regression coverage proves non-zero start/offset/duration/fades, measured duration, relative path, exact derived duration, and absence of invalid extra keys.
- Independent visible-Chrome QA clicked the real USTX export control and verified HTTP 200, UI health, exact wave-part schema, `position=480`, `skip=240`, `trim=240`, derived duration 480, fades, relative path, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/ustx_wave_parts/`.

Validation after iteration 27: frontend production build passed; Python compile passed; full automated suite reached 64 passed.
