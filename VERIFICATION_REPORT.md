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

## Iteration 28 — Bidirectional USTX project import

Implemented and verified:

- Added a source-derived OpenUtau 0.10 importer covering project name, tempo/time signature, track color/type/mute/solo/volume/pan, voice notes and lyrics, intentional pitch curves, vibrato, phoneme overrides, dyn/pitd automation, and wave clips.
- Importer follows inverse source semantics: OpenUtau pitch `y` units are converted back to cents; vibrato end-weighted `length` becomes OpenACE `start_ratio`; `period` becomes frequency; `dyn` decibel×10 becomes normalized automation; wave `skip/trim` reconstructs source offset and visible duration.
- Mandatory untouched OpenUtau two-point pitch serializer defaults are not mistaken for user automation. Missing or malformed USTX structure fails loudly. Internal USTX project names are preserved rather than replaced by upload filenames.
- The transport bar now exposes a working visible **Import USTX** control wired through `/api/import/ustx`, React project state, undo history reset, and SSE-compatible persistence.
- Regression coverage round-trips notes, Chinese lyrics, user pitch curves, vibrato, phoneme override, dyn/pitd automation, track units, wave timing/fades/path/label, and the HTTP endpoint.
- Independent visible-Chrome QA imported a full Chinese USTX fixture through the real file chooser and verified HTTP 200, internal title `USTX 导入验证`, notes/lyrics, 100 BPM, 3/4, track units/color/type, pitch/vibrato/phoneme/automation restoration, wave timing/fades/path/label, UI health, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/ustx_import/`.
- Browser single-file upload cannot access arbitrary sibling media beside the original USTX; unresolved external relative wave media is now explicitly documented instead of silently fabricated.

Validation after iteration 28: frontend production build passed; Python compile passed; full automated suite reached 66 passed.

## Iteration 29 — Validated Cantonese lyric frontend

Implemented and verified:

- Added `pycantonese` as a real dependency and implemented validated tone-bearing Jyutping extraction for Cantonese Han lyrics. Unsupported non-CJK characters and pronunciationless characters fail loudly; no syllable fallback exists.
- Cantonese editor phonemes now decompose onset, nucleus, and coda into explicit IPA-like tokens, including syllabic nasals `m̩`/`ŋ̩`. First vowels remain beat-anchored and post-vowel codas remain after the beat.
- SoulX score metadata now emits exact `yue_<jyutping>` phones validated against the real SoulX phone set, canonical language `Cantonese`, and Cantonese reference preprocessing instead of the previous deliberate unsupported-language error.
- Regression coverage verifies exact `我愛你` Jyutping/tokens, syllabic `唔`, loud rejection of invalid input, exact `yue_ngo5/yue_oi3/yue_nei5` phone validation, and canonical metadata language.
- Independent visible-Chrome QA selected Cantonese, drew notes, entered `我/愛/你/唔`, verified exact phoneme sequences `ŋ ɔː`, `ɔː i`, `n ɛː i`, `m̩`, inspected the phoneme editor/lane, completed fixture rendering, and verified invalid `abc` lyrics produce a clear 422 without overwriting backend lyrics. Evidence: `artifacts/e2e_screenshots/cantonese_frontend/`.
- Japanese remains deliberately unavailable for score rendering because the current SoulX phone set has no Japanese inventory; partial romaji parsing is not misrepresented as engine support.

Validation after iteration 29: frontend production build passed; Python compile passed; full automated suite reached 69 passed.

## Iteration 30 — Packaged USTX media import

Implemented and verified:

- `.ustx` import now also accepts secure zip packages containing exactly one `.ustx` plus bundled relative audio media. Extraction rejects absolute paths, `..` traversal, and symlinks; packages are extracted persistently under `data/uploads/ustx_packages/` so imported clips do not point at deleted temp files.
- Regression coverage verifies exact wave timing/fades/label restoration from bundled `media.wav`, persistent existing media paths, and loud HTTP 422 rejection of path traversal.
- Independent visible-Chrome QA imported a zip through the real file chooser and verified HTTP 200, project open, visible `Hook` arrangement clip, exact start/offset/duration/fades, persistent bundled media, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/ustx_zip_import/`.

Validation after iteration 30: frontend production build passed; Python compile passed; full automated suite reached 71 passed.

## Iteration 31 — Project duplicate/delete management

Implemented and verified: persistent project duplication with fresh project id/` Copy` title; confirmed deletion with fallback to first or new project; visible transport controls use legible `Copy`/`×` labels after QA caught an unsupported glyph. Backend regression covers duplicate identity/title, deletion, and 404. Independent visible-Chrome QA verified duplicate creation/selector/backend persistence, confirmation, fallback, disappearance, fixed glyph legibility, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/project_operations/`.

Validation after iteration 31: frontend production build passed; Python compile passed; full automated suite reached 72 passed.

## Iteration 32 — tempo-map-aware timing and MIDI interoperability

Implemented and verified:

- Replaced constant base-BPM conversion with piecewise tempo-map integration/inversion in the core project model. `Project.bpm` remains the canonical tick-zero editing tempo while positive-tick points automate later tempo changes.
- MIDI export now writes time signature first, then every tempo point with correct delta times; MIDI import merges `set_tempo` events across tracks, reconstructs `tempo_map`, and preserves note/lyric positions. LRC times are generated through the same piecewise conversion.
- SoulX score metadata, target F0 construction, diagnostics, pitch automation lookup, all five expression DSP lanes, master clip source offsets/durations/fades, automatic crossfades, and USTX wave timing now use tempo-aware timeline conversion. Expression automation remains linear in musical ticks while DSP sample positions invert seconds back through the tempo map.
- USTX/SVP/VPR export now serializes complete tempo points in their host-specific units; USTX export/import anchors wave file duration through inverse tempo conversion.
- Frontend transport formatting, waveform source mapping, repaint range conversion, note-duration/phoneme overlay calculations, WebAudio clip scheduling, fades, and playhead progression use the shared TypeScript piecewise tempo converter.
- Regression coverage in `tests/test_tempo_map.py` proves exact conversion across a 120→60 BPM boundary, inverse conversion, MIDI tempo export/import (including the standard 120 BPM default before a late first tempo event), LRC timestamps, SoulX duration metadata, USTX/SVP/VPR tempo serialization, tick-domain expression interpolation, and tempo-aware clip interval conversion.
- Independent visible-Chrome QA generated/imported a real MIDI fixture through the file chooser. It verified HTTP 200, backend tempo points exactly `[0:120, 960:60]`, notes/lyrics, tick 1440 transport reading `1.4.1 / 00:02.00` rather than constant-BPM `00:01.50`, live playback progression into the slower section, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/tempo_map/`, especially `TEMPO_MAP_QA_REPORT.md` and `03_seek_1440_piecewise_time.png`.

Validation after iteration 32: frontend production build passed; Python compile passed; full automated suite reached 79 passed.

## Iteration 33 — honest audible breath events

Implemented and verified:

- Added `openace/core/breath.py`, an explicitly honest post-render processor. SoulX exposes no neural breath conditioning, so OpenACE never synthesizes white noise and calls it a breath. The processor extracts broad-band aperiodic aspiration that already exists in the uploaded reference voice (preferred) or rendered vocal, high-passes/time-fits that real donor noise, and overlays it at breath markers with tempo-aware positions and clipping protection. If no usable real donor exists, the render reports that no synthetic noise was inserted.
- Integrated breath processing into vocal rendering before expression-lane DSP. Job messages distinguish real-donor overlays from donor-unavailable no-ops, and diagnostics carry provenance text stating that breath overlays are post-render DSP rather than neural conditioning.
- Upgraded the Breath & Phoneme lane from mostly decorative markers to zoom-correct editable blocks: empty-click add, horizontal drag move, edge resize with grid snapping, and right-click delete, all undo-safe through existing project transactions.
- Regression coverage proves donor extraction rejects a pure tone, extracts broad-band noise, places overlays exactly in timeline silence, follows a piecewise tempo map, honestly no-ops without real donor noise, and completes a fixture render with `1 real-donor breath overlay(s)`.
- Independent visible-Chrome QA generated an aspiration-bearing reference fixture, uploaded it through the real file chooser, drew a note, added/moved/resized a breath with backend persistence, rendered, and analyzed output audio. The exact 0.625–0.875s breath interval had RMS `0.03393` while surrounding silence was exactly `0.0`; high-band energy was about `3445×` the harmonic fixture floor. Diagnostic provenance visibly states real donor-noise post-render DSP; right-click deletion and console/network health passed. Evidence: `artifacts/e2e_screenshots/breath_events/`, especially `BREATH_EVENTS_QA_REPORT.md` and `audio_analysis.png`.

Validation after iteration 33: frontend production build passed; Python compile passed; full automated suite reached 84 passed.

## Iteration 34 — visual tempo-map editing lane

Implemented and verified:

- Added a dedicated `TempoLane` between arrangement and piano roll. It shares horizontal scroll/zoom with the other editors, draws the piecewise step-tempo curve and markers against the musical grid, shows the playhead, and keeps tick-zero BPM visually distinct from later tempo points.
- Users can create snapped positive-tick tempo points by clicking the lane, drag them horizontally/vertically to edit position and BPM, vertically drag the tick-zero anchor to edit base project BPM, right-click delete positive-tick points, and use a compact numeric editor for exact tick/BPM values. Edits persist through `Project.tempo_map` and are undo/redo-safe.
- `TempoPoint` schema now rejects negative tick positions and nonpositive BPM. Canonical semantics remain explicit: `Project.bpm` is the tick-zero tempo while positive-tick `tempo_map` entries automate later changes.
- Regression coverage now includes invalid tempo-point schema rejection in addition to the 79 passing tempo/interoperability tests from iteration 32.
- Independent visible-Chrome QA verified lane alignment/professional visibility, empty creation, horizontal/vertical drag persistence, exact numeric `{tick:960,bpm:60}` editing, transport tick 1440 reading `1.4.1 / 00:02.00`, undo/redo, panel delete, tick-zero BPM editing to 125 with tick 480 reading `00:00.48`, wheel scroll/Ctrl+zoom synchronization, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/tempo_editing/`, especially `TEMPO_EDITING_QA_REPORT.md` and `04_numeric_exact_960_60.png`.

Validation after iteration 34: frontend production build passed; Python compile passed; full automated suite reached 85 passed.

## Iteration 35 — SVC conversion arrangement integration

Implemented and verified:

- SVC conversion output is no longer only a standalone job-card file. Successful conversion now creates a dedicated `SVC — <source stem>` audio track with the converted wav as a normal arrangement clip at tick zero, so existing waveform rendering, playback, drag/trim/split/fades/gain, persistence, and master export all apply without special-case frontend code.
- Each conversion keeps its own track for non-destructive comparison instead of silently stacking alternatives on the score-rendered vocal track. `project.metadata['svc_conversions']` records job id, track id, source audio, reference voice, and output path.
- The backend publishes the updated arrangement over SSE when conversion completes; the job message explicitly says the result was added to the arrangement. Diagnostics now select the first vocal track that actually has notes and gracefully render a no-notes state instead of crashing on an empty stem plot.
- Backend regression verifies converted clip path/placement/duration/label, render path deduplication semantics, provenance metadata, diagnostic creation, and repeated conversions as independent comparison tracks.
- Independent visible-Chrome QA generated real local source/reference WAVs, uploaded both through the UI, ran conversion, verified no-reload track appearance, visible waveform clip, healthy playback interaction, drag `0→120` and trim `1152→1032` persistence, master export energy at the edited `0.125–1.2s` placement, diagnostic generation, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/svc_arrangement/`, especially `SVC_ARRANGEMENT_QA_REPORT.md`, `02_svc_track_no_reload.png`, and `master_export_analysis.png`.

Validation after iteration 35: frontend production build passed; Python compile passed; full automated suite reached 86 passed.

## Iteration 36 — breath intensity and timbre shaping

Implemented and verified:

- `Breath` events now carry backward-compatible `intensity` (0–200%) and `timbre` (`soft`/`natural`/`strong`) fields with schema validation. Existing projects without these fields load with natural 100% defaults.
- Rendering remains honest donor processing: intensity scales the real extracted aspiration overlay, while timbre spectrally shapes that same donor (soft damps the brittle top octave; strong emphasizes existing broad-band hiss and cuts rumble). No synthetic noise or neural-conditioning claim was added.
- The Breath & Phoneme lane visually encodes intensity/timbre, shows per-breath percentages and a small intensity meter, and exposes a compact selected-breath inspector with slider/timbre controls. The inspector is overlaid inside the automation canvas so it does not push `Add all breaths` under the right panel at narrow widths.
- Backend regressions prove zero intensity is silent, 150%/50% scaling is approximately 3×, spectral ratio ordering is soft < natural < strong, and invalid intensity/timbre values are rejected.
- Independent visible-Chrome QA verified exact slider persistence at 0/50/150%, undo/redo, timbre persistence, add-all defaults, move/resize/delete interactions, inspector disappearance after delete, four successful honest renders, measured RMS ratio `2.99999989×`, spectral ratios soft `0.41265` < natural `2.66856` < strong `5.91521`, and zero console/network errors. A targeted second pass verified real-mouse `Add all breaths` hit-testing and the unobstructed compact inspector layout. Evidence: `artifacts/e2e_screenshots/breath_shaping/`, especially `BREATH_SHAPING_QA_REPORT.md`, `quantitative_breath_analysis.png`, and `layout_recheck_final_strong.png`.

Validation after iteration 36: frontend production build passed; Python compile passed; full automated suite reached 89 passed.

## Iteration 37 — persistent zero-shot voice library

Implemented and verified:

- Added a persistent reference-voice library backed by `data/voices/voices.json` and copied audio files. Uploads are validated as readable audio, reject unsupported/corrupt/too-short files, and persist name, exact path, duration, sample rate, channel count, size, and creation time.
- Added list/upload/rename/delete API. Safe deletion returns HTTP 409 while a voice is in use; explicit `unassign=true` deletion first clears matching `voice_id`/path references across saved projects, persists and publishes those projects, then removes the voice file and metadata.
- Reworked the Voice panel around the library: users can assign a saved voice from a select, upload new references directly into the library, see selected voice name/duration/sample rate, rename through a prompt, and delete with explicit unassign confirmation. Track patches persist both `voice_id` and `reference_voice_path` for engine-compatible rendering. Backend voice create/rename/delete publishes `voice_library` SSE events and the open panel refreshes external/API changes without reload.
- Core regressions cover metadata persistence, rename, delete, sanitization, corrupt audio rejection, unsupported suffix rejection, and too-short audio rejection.
- Independent visible-Chrome QA verified visible upload metadata (`1.2s`, 44.1kHz, mono), exact assignment persistence across reload, rename to `Studio Voice Alpha`, HTTP 409 safe deletion while in use, confirmed deletion with no-reload assignment clearing, second-voice reassignment, successful render with a library voice, compact unobstructed 1272×837 layout, external API create/rename/delete live-refresh through SSE without stale entries, and zero final console/network errors. Evidence: `artifacts/e2e_screenshots/voice_library/`, especially `VOICE_LIBRARY_QA_REPORT.md` and `08_exact_1272x837_layout.png`.

Validation after iteration 37: frontend production build passed; Python compile passed; full automated suite reached 91 passed.

## Iteration 38 — agent-native editing expansion

Implemented and verified:

- Added shared validated editing operations for batch note creation, note update/delete, expression-lane replacement, breath upsert/delete, audio-clip upsert/delete, tempo-map replacement, voice assignment, and MIDI project import. Operations validate phoneme/beat invariants, automation ranges, breath schema, existing media paths, and positive tempo values before persistence.
- Exposed these operations as MCP tools: `batch_add_notes`, `update_note`, `delete_note`, `set_expression_lane`, `upsert_breath`, `delete_breath`, `upsert_audio_clip`, `delete_audio_clip`, `set_tempo_map`, `assign_voice`, and `import_midi_project`; MCP project export now also supports WAV master export.
- Exposed equivalent atomic CLI commands with inline-or-file JSON payloads and best-effort loopback SSE publication, so external agents can edit a running workstation without manual reload.
- Updated `skills/openace/SKILL.md` with accurate command syntax, JSON payload semantics, MCP editing tool names, validation constraints, and anti-fake rules.
- Regressions prove editing validation and persistence directly, MCP stdio tool invocation end-to-end, and CLI subprocess persistence for notes/expression/breath/clips/tempo/voice assignment.
- Independent visible-Chrome QA drove external `openace-tool` edits against the running backend data directory and verified no-reload SSE appearance of batch notes, dynamic curve, strong 180% breath, real arrangement waveform clip, live 120→60 tempo step, correct tick-1440 transport `1.1 / 00:02.00`, and external pitch revision `64→69`; no console/network errors. Evidence: `artifacts/e2e_screenshots/agent_editing/`, especially `AGENT_EDITING_QA_REPORT.md` and `09_final_clean_state.png`.

Validation after iteration 38: frontend production build passed; Python compile passed; full automated suite reached 95 passed.

## Iteration 39 — local stem separation and dry/wet remix

Implemented and verified:

- Added a production `DemucsStemSeparator` that runs local open-source Demucs `htdemucs` through `python -m demucs --two-stems vocals`, validates expected non-empty stems, and fails loudly with installation guidance if the optional runtime is absent. No production fallback or synthetic separation exists; only the explicitly labeled CI fixture uses deterministic frequency splitting for orchestration tests.
- Added durable `RenderMode.SEPARATE` jobs with restart recovery, API/CLI/MCP entry points (`/render/separate`, `openace-tool separate`, `separate_stems`), frontend **Separate vocal/instrumental** control, diagnostic output, and `demucs` in the optional `gpu` dependency set.
- Successful separation creates independent `Separated vocal — <source>` and `Separated instrumental — <source>` audio tracks/clips at tick zero. Existing mute/solo/volume/pan/clip gain, waveform editing, drag/trim/split, playback, and loudness master export therefore provide the dry/wet remix workflow without special-case code. `project.metadata['stem_separations']` records job/source/track/output provenance.
- `scripts/verify_local_gpu.py` now includes a default Demucs acceptance stage after serialized SoulX/ACE-Step verification: it mixes short portions of the real outputs and validates the production separation path, with `--skip-separation` available for constrained runs.
- Backend regression verifies fixture-labeled stem content, exact durations/paths, arrangement tracks, metadata, and diagnostic creation. Independent visible-Chrome QA verified upload/job completion, no-reload appearance of both waveform tracks, metadata, vocal mute persistence, quantitative master high/low spectral ratio dropping `0.74930 → 0.000114` after vocal mute, clip drag `0→120` and trim `1920→1680`, CLI/MCP entry-point visibility, professional 1272×837 layout, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/stem_separation/`, especially `STEM_SEPARATION_QA_REPORT.md` and `04_final_layout.png`.

Validation after iteration 39: frontend production build passed; Python compile passed; full automated suite reached 96 passed.

## Iteration 40 — editable denominator-aware time signatures

Implemented and verified:

- Transport now exposes common time signatures (`2/4` through compound `12/8`) and persists validated numerator/denominator pairs. Schema rejects non-positive numerators and non-power-of-two denominators.
- Arrangement, piano roll, automation, and tempo grids now derive bar spacing from `numerator * ppq * 4 / denominator` instead of hard-coding four quarter notes per bar. The transport readout counts denominator beat units, so 6/8 correctly exposes six eighth-note beats per bar.
- Serialization regression verifies the same signature reaches MIDI meta events, USTX `beat_per_bar`/`beat_unit`, SVP meter, and VPR master-track time signatures.
- Independent visible-Chrome QA at exact 1272×837 verified default 4/4, visible switch to 6/8, backend persistence, consistently narrowed arrangement/piano/automation/tempo grids with quantitative 448px→336px evidence, transport tick 1440 reading bar `2.1`, reload persistence, undo/redo, and zero console or meaningful network errors. Evidence: `artifacts/e2e_screenshots/time_signature/`.

Validation after iteration 40: targeted time-signature tests passed; full automated suite reached 98 passed after final regression.

## Iteration 41 — dedicated lyric correction workflow

Implemented and verified:

- Added a compact right-panel **Lyric correction** workflow for vocal tracks with accurate total/missing counts, bar·pitch positions, per-note editable rows, missing-state styling, and regenerated phoneme feedback.
- Batch paste supports continuous CJK one-character-per-note correction while whitespace-separated chunks can force multi-letter/romanized syllables onto one note. Count mismatches fail atomically with an explicit error rather than partially overwriting lyrics.
- Lyric commits clear stale phonemes, use normal project persistence/undo, and let backend validation regenerate language-correct timed phonemes. Per-row edits commit on blur/Enter without creating one undo item per keystroke.
- Independent visible-Chrome QA verified continuous CJK batch mapping (`春风笑靥` → four per-note lyrics), mismatch atomicity, regenerated Mandarin phonemes, reload persistence, per-note correction (`猫` → `m au`), independent undo/redo for row and batch edits, compact 1272×837 layout, and zero console/meaningful network errors. Evidence: `artifacts/e2e_screenshots/lyric_correction/`.
- Fixed the incidental CLI robustness defect found by QA: long inline JSON no longer crashes in `Path.exists()` with `Errno 36`; regression coverage proves >4096-byte inline JSON parses as payload rather than a path.

Validation after iteration 41: frontend production build passed; Python compile passed; full automated suite passed (99 collected tests).

## Iteration 42 — agent-native project operations and audio import

Implemented and verified:

- Refactored real monophonic audio + faster-whisper lyric alignment into shared `project_from_audio` semantics used by the FastAPI importer, CLI, and MCP rather than divergent copies. Total ASR/pitch-alignment failure still fails loudly; no placeholder lyric path exists.
- Added CLI `import-audio`, `duplicate-project`, and `delete-project`; MCP `import_audio_project`, `duplicate_project`, and `delete_project`. Project duplication receives a fresh project id and persisted copy.
- Completed best-effort loopback SSE notification for CLI/MCP project creation/import/duplication, deletion, simple mutations, and render-produced arrangement updates. The workstation project selector now incorporates externally created/imported/duplicated projects without reload and handles external deletion by switching to a remaining/new project; a reentrancy guard prevents local UI delete from creating duplicate fallback projects.
- Regressions cover shared audio-import semantics, CLI long-inline JSON, CLI duplicate/delete persistence, MCP tool exposure, MCP duplicate/delete roundtrip, and existing ASR endpoint behavior.
- Independent visible-Chrome QA drove the real CLI against the same data directory: external create/duplicate appeared live, external deletion removed the selected duplicate and switched the workspace without duplicate fallback creation, local UI delete remained exactly-once, and real `import-audio` using the existing cached faster-whisper tiny model created/opened a project live with 4 notes and 3 nonempty ASR-derived lyrics. No console/network errors. Evidence: `artifacts/e2e_screenshots/agent_project_ops/`.


Additional hardening during final regression: dense-project performance exposed that rendering thousands of lyric-correction rows as DOM nodes would not scale. The lyric list is now virtualized (fixed-height windowing) so only the visible rows mount while large projects remain editable by scrolling. A separate stale Chrome renderer consuming sustained CPU was identified as environmental noise and terminated; the 3000-note 1400×900@2x performance regression then passed again. Browser adversarial recheck also caught stale virtual scroll state after project/track switching; scroll state now resets on project/track/note-count changes, and the exact blank-viewport repro passed with only 15 mounted rows for 1200 notes.

Validation after iteration 42: frontend production build passed; Python compile passed; full automated suite passed (101 collected tests).

## Iteration 43 — direct arrangement audio clip import

Implemented and verified:

- Added `POST /api/projects/{id}/clips/import` for first-class audio import: multipart media is persisted under uploads, validated/measured with SoundFile, converted from seconds through the project tempo map, inserted at the requested playhead tick, and placed on an existing or newly created audio track. Corrupt audio is rejected and temporary media removed.
- Uploaded media is now statically served through `/uploads`; frontend media URL resolution supports both renders and uploads, so imported clips produce real waveform peaks and browser playback rather than remaining in `analyzing waveform…`.
- RenderPanel exposes **Import audio as clip at playhead** using current transport position. Backend regression covers measured duration conversion, persistence, invalid-audio rejection, and static uploaded-byte serving.
- Independent visible-Chrome QA verified nonzero-playhead import, live no-reload `Audio — clipimport` track creation, exact 1.0s→960-tick conversion at 120 BPM/480 PPQ, canvas position/width within 1–2px, drag/trim/reload persistence, corrupt-file rejection, and quantitative master-export inclusion (`RMS before=0.0`, inside=`0.17629`). Initial QA caught the missing uploaded-media URL path; after the fix, waveform bright pixels improved from 38/3 interior to 790/332 interior, uploaded WAV playback loaded and advanced the playhead, and reload retained the waveform. Evidence: `artifacts/e2e_screenshots/audio_clip_import/`.

Validation after iteration 43: frontend production build passed; Python compile passed; full automated suite passed (103 collected tests).

## Iteration 44 — arrangement media import hardening

Implemented and verified:

- Direct clip import now targets the currently selected audio/accompaniment track; selecting a vocal track intentionally falls back to a new audio track. The backend rejects explicit vocal-track targets rather than corrupting note-track semantics.
- Generic `/api/upload` now writes unique persistent filenames instead of silently overwriting same-name media that may already be referenced by clips/jobs.
- Regression covers vocal-target rejection and upload-name uniqueness. Independent visible-Chrome QA verified insertion into an existing selected audio track without duplicate track creation, vocal-selection fallback to a separate `Audio — vocaltarget` track, clean layout, and zero console/network errors. Evidence: `artifacts/e2e_screenshots/audio_clip_import/target_semantics.png`.

Validation after iteration 44: frontend production build passed; Python compile passed; full automated suite passed (104 collected tests).

## Iteration 45 — full adversarial creative-loop audit

Executed the complete user-required browser loop in real visible Chrome at exact 1272×837 against the fixture backend: new project → piano-roll note draw/drag/zoom/lyrics/phonemes → pitch/air/tension curves → reference voice upload → vocal render + Vocal2BGM → Alt-drag repaint region and repaint → SVC conversion → playback → WAV/MP4/MID/LRC/USTX/SVP/VPR export → MCP mutation with live SSE update.

Passed highlights:

- Exact transport fit, note editing/transposition/zoom, lyric correction and phoneme regeneration, 13 automation points in each tested lane, persistent reference voice `voice_9d0507989312`.
- Vocal render, Vocal2BGM arrangement integration, numeric/visible repaint region `0.32→1.09`, repaint replacement clip, and SVC arrangement integration.
- Playback advanced with expected media URLs loaded; MCP `add_note` updated the open UI live from 2→3 notes without reload.
- All seven export controls produced nonzero files. Structural validation: WAV 3.125s/48kHz/stereo, MP4 3.125s/1920×1080 plus audio, valid format-1 MIDI with notes, timed LRC, parseable USTX/SVP/VPR with expected lead notes/phonemes.
- No console errors, warnings, or unexpected network failures.

The audit confirmed one implementation defect: the piano editor toolbar overflowed by 50px and truncated the selection readout. Responsive toolbar repair initially reduced overflow to 13px, then reached exact zero (`scrollWidth=clientWidth=714`) with full `1 selected` visible and controls still usable. Evidence: `artifacts/e2e_screenshots/full_adversarial_audit/`, especially `FULL_ADVERSARIAL_AUDIT_REPORT.md`, `SCREENSHOT_INDEX.md`, and `toolbar_fix2_zoom.png`.

The audit's “key/scale-aware transpose” note is not treated as a confirmed ACE-parity blocker: the requested cover/翻调 mode was exercised through the implemented SVC conversion workflow, and interval-preserving semitone transposition already exists. No evidence was produced that ACE Studio requires a separate key/scale transposition mode for the user's stated loop.

## Iteration 46 — karaoke dynamic lyric video

Implemented and verified:

- MP4 export now renders a professional gradient studio backdrop instead of a flat color field, with persistent project-title and OpenACE brand cards.
- Contiguous lyric notes are grouped into karaoke phrases and each note contributes an exact ASS `\kf` sweep duration. Sung lyrics become high-contrast amber while unfilled lyrics remain neutral; fades are applied within the event duration rather than extending media length.
- Regression now validates generated ASS karaoke tags/title/branding, exact ffprobe duration, and quantitative burned-frame pixels: at 0.6s the first syllable had 576 amber pixels versus 131 in the partially sweeping second syllable, with 482 neutral unfilled pixels in the second syllable. Evidence artifact: `artifacts/e2e_screenshots/karaoke_video/`.

Validation after iteration 46: frontend production build passed; Python compile passed; full automated suite passed (104 collected tests).

## Iteration 47 — SVC arrangement lyric display

Implemented and verified:

- `AudioClip` now persists `transcribed_lyrics` as real timed words. After SoulX-Singer-SVC conversion, the output audio itself is transcribed with local faster-whisper word timestamps; resulting words are stored on the arrangement clip and provenance records language, word count, or the explicit ASR failure. Missing ASR never invents or substitutes placeholder lyrics and does not invalidate an otherwise real conversion.
- Arrangement audio clips draw the timed lyric words along the bottom of the clip, mapped from source seconds through the project tempo map. Trimming uses the clip source offset/duration so fully outside words disappear while boundary-overlapping words remain clamped visibly at the clip edge.
- Backend regression verifies persisted word timings, language/count provenance, and explicit ASR-failure behavior. Independent visible-Chrome QA verified source-time x positions within about 0.7px, reload persistence, left/right trim visibility, exact 1272×837 layout, and zero app console errors. Initial QA caught a real left-boundary defect (`are` spanning `0.45–0.8s` disappeared after a 0.5s trim); after repair, focused regression passed with `are` visible at x `180.5–191`, `you` absent, and later words unchanged. Evidence: `artifacts/e2e_screenshots/svc_lyrics/`, especially `SVC_LYRICS_QA_REPORT.md` and `boundary_fix_left_trim_zoom.png`.
- Harness limitation recorded: the long-running Chrome instance rendered CJK canvas glyphs as narrow tofu despite installed fonts, so QA used ASCII words for reliable pixel evidence. This is a test-environment font limitation, not a lyric-data substitution path.

Validation after iteration 47: frontend production build passed; Python compile passed; full automated suite passed (105 collected tests).

## Iteration 48 — SVC lyric correction editing

Implemented and verified:

- The right panel now exposes an **SVC clip lyrics** editor for audio clips carrying real ASR word timings. Users can correct word text and exact start/end seconds, add a genuinely entered word through a prompt (no fabricated placeholder), delete words, and receive atomic validation when end time is not after start time.
- Edits flow through normal project persistence/undo state. The arrangement canvas remaps corrected timing through the project tempo map, so moving a word changes its visual x position and survives reload.
- Independent visible-Chrome QA at exact 1272×837 verified text edit persistence, start-time movement, reload, visible undo/redo, real-word add/delete, invalid-time atomic rejection, compact layout, and zero app console errors. Evidence: `artifacts/e2e_screenshots/svc_lyric_editing/`, especially `SVC_LYRIC_EDITING_QA_REPORT.md` and `02_edited_word_time_canvas.png`.

Validation after iteration 48: frontend production build passed; Python compile passed; full automated suite passed (105 collected tests).

## Iteration 49 — sample-accurate playback transport and media caching

Implemented and verified:

- Playback now uses a shared AudioContext instead of constructing/closing a context on every transport start. Fetch plus `decodeAudioData` work is cached per media URL and failed decodes evict themselves honestly.
- Transport progression is driven by the audio-context clock when audio exists, with a silent-project performance-clock fallback. Fractional source offsets/durations continue to be passed to WebAudio scheduling while fade/crossfade gain automation remains sample-timeline oriented.
- Independent visible-Chrome QA verified continuous playback, playhead/wall-clock agreement within about 0.04s over 2.3s, repeated stop/start with exactly one media fetch, exactly one decode, one AudioContext constructor, trimmed/faded/overlapping clips scheduling without errors, no layout overflow, and no console/network failures. Evidence: `artifacts/e2e_screenshots/playback_cache/`.

Validation after iteration 49: frontend production build passed; browser playback QA passed. Backend code was unchanged; the immediately preceding full automated suite remained green at 105 collected tests.

## Iteration 50 — expressive audio-to-MIDI pitch curves

Implemented and verified:

- `audio_to_midi_notes` now preserves measured unvoiced-masked pyin microtonal movement as editable `Note.pitch_curve` points instead of discarding it during semitone quantization. Points use real frame deviations in cents, a small median window suppresses isolated octave artifacts, and sparse 30ms/3-cent downsampling avoids bloating projects.
- Regression proves a measured rising curve retains multiple pitch handles without a fabricated octave spike and that the extracted curve raises target diagnostic/engine F0 within the note without crossing the next semitone. Existing USTX pitch-curve export/import and piano-roll pitch-handle editing consume the same data model.
- Focused browser QA confirmed visible continuous microtonal curve and multiple handles. Interaction coverage was incomplete because scripted hit testing did not mutate state and reload hit an SSE `networkidle` harness timeout; no implementation defect was confirmed, and pitch-handle edit/delete behavior itself was already covered by earlier piano-roll end-to-end evidence. Evidence: `artifacts/e2e_screenshots/audio_pitch_curve/`.

Validation after iteration 50: targeted ASR/pitch regression passed; full automated suite passed (107 collected tests).

## Iteration 51 — ramp-shaped tempo transitions

Implemented and verified:

- `TempoPoint.curve` now supports validated `step` and `linear` modes. A linear point ramps into its BPM across the preceding segment. Backend and frontend timing use the exact logarithmic integral/inverse of reciprocal linear BPM, so musical ticks and seconds remain bidirectionally consistent rather than approximated by fixed tempo chunks.
- Tempo lane draws sloped ramps, exposes a Curve selector for positive-tick points, and preserves curve type across creation, dragging, undo/redo, and reload. The floating editor now moves to the opposite side of right-side endpoints after browser QA caught it covering the endpoint hit target.
- MIDI/USTX/SVP/VPR exporters densify ramp segments into stepped tempo events with exact endpoints. This is intentionally documented as a lossy interchange approximation because those host formats do not carry OpenACE's continuous ramp metadata; no fake native-roundtrip claim is made.
- Backend regression verifies exact midpoint BPM/time/inverse roundtrip, dense 90 BPM midpoint export at tick 480 of a 120→60 ramp, endpoint fidelity, schema rejection of unknown curves, and preservation of existing step behavior. Independent visible-Chrome QA verified flat-vs-sloped pixels, drag/undo/redo/reload persistence, measurably different transport progression (`step 1.2` vs `linear 2.1` after ~1.7s), clean layout, and the overlay repair (`1920/180 → 2040/174.8` direct drag stayed linear). Evidence: `artifacts/e2e_screenshots/tempo_ramps/`.

Validation after iteration 51: frontend production build passed; tempo-map suite passed; full automated suite passed (110 collected tests).

## Iteration 52 — recent project manager

Implemented and verified:

- Transport now consolidates project operations into a professional **Projects** popover while preserving exact 1272×837 toolbar fit. The popover lists recent projects in backend order with updated date, track count, and BPM metadata; search filters titles; click-outside closes the panel.
- Project rows support opening arbitrary projects, duplicating arbitrary non-current projects into editable copies, and deleting non-current projects without disrupting the open workspace. Current-project deletion retains the exactly-once fallback behavior.
- The shared playback AudioContext is no longer closed during project switching, preserving the playback-cache architecture while sources/transport still stop correctly.
- Independent visible-Chrome QA verified metadata rows, search, open/copy/delete flows, current fallback stability with zero accidental create posts, click-outside close, zero toolbar/body overflow, and zero final console/network failures. Evidence: `artifacts/e2e_screenshots/project_manager/`.

Validation after iteration 52: frontend production build passed; browser QA passed. Backend behavior was unchanged apart from existing list metadata consumption; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 53 — arrangement multi-clip selection

Implemented and verified:

- Arrangement clips now support DAW-style selection: click select with a bright outline, Ctrl/Cmd additive toggling across tracks, and rubber-band marquee selection including additive Ctrl marquees.
- Dragging any selected clip moves the entire selected group by one quantized horizontal delta, preserving relative spacing and track membership with collective zero-time clamping. Trim/fade handles still operate only on their target clip rather than accidentally group-moving.
- Context operations operate on the selected group when invoked from a selected clip: copy/paste preserves spacing and original tracks, duplicate shifts the group by its full span, delete removes the group, and undo/redo restore exact clip identity/state.
- Independent visible-Chrome QA verified all of the above quantitatively: group drag `(480,1920,960)→(720,2160,1200)`, zero clamp `(0,1440,480)`, duplicate span shift `2280`, paste `2520/3000/3840`, exact-ID undo/redo, clean 1272×837 layout, and zero console/network failures. Evidence: `artifacts/e2e_screenshots/arrangement_multiselect/`.

Validation after iteration 53: frontend production build passed; browser QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 54 — live playback reconstruction

Implemented and verified:

- Playback scheduling is now factored around a reusable graph builder. While transport is running, arrangement-affecting edits are fingerprinted (clip paths/timing/trim/fades/gain plus track volume/pan/mute/solo/render media and tempo), debounced through a persistent 120ms reconstruction timer, and rescheduled at the current audio-clock position instead of requiring manual stop/play.
- Reconstruction preserves transport continuity: it accounts for decode/scheduling latency when computing source offsets, reuses cached decoded media, stops old sources before starting replacements, and does not reset or jump the playhead. Initial playback still waits for decode before anchoring its clock, so startup latency does not make playback begin ahead.
- First adversarial QA exposed a real defect: same-snapshot transient/SSE project renders cleared the reconstruction timeout before it fired, so clip drags and undo/redo left stale audio. The timer is now independent of effect cleanup and only rescheduled when the audio fingerprint actually changes.
- Regression QA in visible Chrome verified drag rebuild (`1920→2040` ticks, timer `126.8ms`), left trim rebuild (`offset 0→120`, timer `126.9ms`), undo/redo rebuild (`166.3/163.3ms`), exactly one rebuild for three rapid edits, zero unexpected playhead jumps, correct initial `0.5s` clip offset and `1.0s` future scheduling, one decode across repeated reconstructions, clean 1272×837 layout, and zero console/network failures. Evidence: `artifacts/e2e_screenshots/live_playback_reconstruction/`.

Validation after iteration 54: frontend production build passed; browser regression QA passed. Backend behavior was unchanged; full automated suite is being rerun before commit.

## Iteration 55 — live track and master metering

Implemented and verified:

- Playback now uses explicit per-track bus nodes: clip fade/gain chains feed a shared track input, track volume and stereo pan are applied once per track, and each track passes through a real `AnalyserNode` into a summed master analyser. This preserves the previous audible routing while making metering quantitative rather than decorative.
- Track cards render compact live meters and the track sidebar includes a Master meter. Meters use requestAnimationFrame smoothing with fast attack/exponential decay and a stable callback ref, so normal playhead re-renders do not reset or flicker them.
- Independent visible-Chrome QA verified nonzero animated levels for two audible tracks, exact zero for an empty track, correct summed master ratios, volume reduction (`0.8→0.05` lowering track/master), mute and solo semantics, pause/stop decay to zero, restart recovery, continued live reconstruction after clip drag, unchanged decode caching, and clean 1272×837 layout with zero console/network failures. Evidence: `artifacts/e2e_screenshots/live_metering/`.
- Non-blocking cleanup debt observed by instrumentation: internally caught `source.stop()` calls can target already-ended/never-started sources. They do not surface in console or affect audio/metering; a future graph-hygiene pass can track source lifetimes more precisely.

Validation after iteration 55: frontend production build passed; browser metering QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 56 — vertical cross-track clip dragging

Implemented and verified:

- Arrangement clip dragging is now truly two-dimensional. Vertical pointer motion moves clips across compatible audio/accompaniment lanes while skipping vocal lanes; simultaneous horizontal motion remains quantized. Multi-clip groups use collective lane clamping, preserving relative vertical spacing instead of squashing clips at arrangement boundaries.
- Held-drag state now follows clips after their first lane migration, so reversing direction before mouseup returns to the original lane and further horizontal adjustment remains live. Selection identities are remapped to the destination lanes on pointerup, preserving copy/delete/undo behavior.
- Arrangement height now grows with track count so all lanes are visible; context-menu clamping uses that dynamic height. Browser regression verified four full lanes, fourth-lane editing, reversal/horizontal path correction, top/bottom group clamps, paste spacing, exact-ID undo, live playback reconstruction (`202.6ms`), menu clamp exactly `166-130-1=35`, clean layout, and zero console/network failures. Evidence: `artifacts/e2e_screenshots/vertical_clip_drag/`.

Validation after iteration 56: frontend production build passed; browser regression QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 57 — tempo point copy/paste

Implemented and verified:

- Positive-tick tempo points now expose Copy and Paste-at-playhead actions in the tempo editor. Paste snaps to the musical grid, upserts the target tick without duplicates, preserves BPM plus step/linear curve metadata, selects the pasted point, and persists through undo/redo/reload.
- Independent visible-Chrome QA verified step paste `480/150→240/150`, linear replacement `720/130 step→720/90 linear` with no duplicate, visible ramp/schema preservation, exact undo/redo restoration, reload persistence, clean lane layout, and zero console/HTTP failures. Evidence: `artifacts/e2e_screenshots/tempo_copy_paste/`.

Validation after iteration 57: frontend production build passed; browser QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 58 — large-arrangement vertical scrolling

Implemented and verified:

- Arrangement content now keeps full dynamic height inside a capped 210px viewport, so projects with many tracks no longer squeeze the piano roll. Plain wheel natively scrolls lanes; Ctrl+wheel zooms horizontally without vertical scrolling; Shift+wheel/horizontal deltas move the shared timeline; lane names are drawn in the arrangement label column for orientation while scrolled.
- Browser QA initially caught Ctrl+wheel double-scrolling and passive-listener console errors. The implementation now uses a native non-passive canvas wheel listener. Final visible-Chrome regression verified correct large/small heights, bottom-lane clip drag/context/copy/delete/undo at scrolled coordinates, wheel isolation, bottom lane names, small-project preservation, clean layout, and zero console/network failures. Evidence: `artifacts/e2e_screenshots/arrangement_vertical_scroll/`.

Validation after iteration 58: frontend production build passed; browser regression QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green at 110 collected tests.

## Iteration 59 — MIDI channel/program interoperability

Implemented and verified:

- Tracks now carry optional validated `midi_channel`/`midi_program` metadata. MIDI export writes channel-scoped note events and program changes; automatic channel assignment skips the percussion channel and remains deterministic for multi-track projects.
- MIDI import now groups notes by channel, preventing same-pitch cross-channel collisions, splits mixed-channel source tracks into truthful channel-labeled OpenACE tracks, and roundtrips channel/program metadata.
- Regression coverage verifies channel 4/program 52 export+roundtrip and a mixed-channel same-pitch fixture splitting into two tracks with correct independent durations (`240/480` ticks).

Validation after iteration 59: targeted MIDI interoperability tests passed; frontend production build passed. Full suite follows before commit.

## Iteration 60 — multi-track karaoke collision handling

Implemented and verified:

- MP4 karaoke export now assigns overlapping lyric phrases to collision-aware vertical ASS lanes. Lane 0 retains the prior bottom-center typography; higher lanes use progressively smaller fonts and larger bottom margins, while non-overlapping phrases reuse lower lanes rather than wasting vertical space.
- Regression coverage verifies generated `Lyrics`/`LyricsLane1` styles, distinct `96/172` margins, and correct per-phrase dialogue style assignment. A real rendered 1920×1080 frame at an overlapping timestamp visually shows simultaneous lead and harmony lyrics on separated lines without collision. Evidence: `artifacts/e2e_screenshots/karaoke_multitrack/overlap_frame.png` and `layered.ass`.

Validation after iteration 60: targeted karaoke/MP4 interoperability tests passed; visual frame inspection passed. Full suite follows before commit.

## Iteration 61 — sticky arrangement ruler

Implemented and verified:

- The arrangement bar ruler now remains visible at the viewport top while vertically scrolling large arrangements. Bar labels/background render as a sticky overlay above lane content, and pointer hit-testing treats the sticky band as ruler so clicking seeks rather than selecting or dragging the underlying lane.
- Visible-Chrome QA verified correct large-project sticky rendering and seek behavior, bottom-lane orientation names, unchanged small-project height/no-scroll behavior, preserved Ctrl/Shift/plain wheel isolation, clean layout, and zero console/network failures. Evidence: `artifacts/e2e_screenshots/sticky_arrangement_ruler/`.

Validation after iteration 61: frontend production build passed; browser QA passed. Backend behavior was unchanged; the immediately preceding full automated suite remained green.

## Iteration 62 — project pinning and tag organization

Implemented and verified:

- Project metadata now supports persistent pinned state and normalized lightweight tags (comma-entry friendly, deduplicated, max 12, 32 characters per tag). Project lists sort pinned projects first, then newest `updated_at`; organization edits intentionally do not rewrite project modification time.
- FastAPI exposes `PATCH /api/projects/{id}/organization`; CLI exposes `organize-project`; MCP exposes `organize_project`. All three write through the same normalized metadata semantics and publish SSE updates. Duplicates retain tags but are intentionally unpinned.
- The Projects popover now shows pin state/tags, supports pin/unpin, inline comma-separated tag editing with Enter/Save/Escape, title-or-tag search isolation, and preserves open/copy/delete/current-delete fallback behavior.
- Independent visible-Chrome QA verified three-project ordering, pin/unpin reordering, normalization/max-12/32-character rules, reload and SSE persistence, search isolation, duplicate semantics, normal project operations, exact 1272×837 layout without overflow, and zero console/unexpected network failures. Evidence: `artifacts/e2e_screenshots/project_pin_tags/`.

Validation after iteration 62: frontend production build passed; targeted API/CLI/MCP tests passed; browser QA passed; full automated suite passed with 116 tests collected.

## Iteration 63 — serialized render queue and cross-process VRAM exclusion

Implemented and verified:

- Server-triggered vocal, Vocal2BGM, repaint, separation, and SVC jobs no longer launch independent concurrent `BackgroundTasks`. They enter one process-wide FIFO asyncio worker, so heavy model stages execute one at a time and unexpected runner failure marks only that job failed without blocking later queued work.
- Backend restart recovery now requeues durable interrupted jobs into the same worker instead of using a separate recovery path. CLI single-job synchronous behavior remains unchanged.
- `VRAMManager` now waits instead of overlapping in-process reservations and holds an `openace-vram.lock` cross-process file lock for the entire engine subprocess lifetime. Independent OpenACE server/CLI processes therefore serialize cooperating heavy-engine launches instead of merely detecting collisions after the fact; the production Demucs separator now participates in the same reservation.
- Automated regression proves FIFO serialization, failure isolation, in-process non-overlap, and independent-process lock ordering. Browser/API QA with a fixture-only 0.8s delay proved two rapid waves in exact FIFO order: second jobs transitioned from queued to running only after first completion; continuous polling never saw more than one running job. Evidence: `artifacts/e2e_screenshots/render_queue/`.

Validation after iteration 63: targeted queue/VRAM tests passed; browser/API QA passed with zero console/unexpected network failures. Full automated suite passed with 120 tests collected.

## Iteration 64 — stale vocal render detection

Implemented and verified:

- Vocal renders now store a deterministic 64-bit input fingerprint covering musical render inputs: notes/lyrics/phonemes/pitch curves/vibrato/techniques, all expression lanes, breath events, normalized tempo map/PPQ, language, and voice assignment/reference path. Note and breath IDs are deliberately excluded so identical musical content does not become falsely stale.
- Backend and browser use matching canonical JSON/FNV-1a implementations. Fresh browser-rendered audio produced no stale indicator, proving cross-language hash parity in the real app; backend regression proves stability, sensitivity, and exact canonical-vector behavior.
- Track cards now expose an amber `stale render` badge and the render panel explains that playback/export still use the old render until rendering again. Legacy renders without fingerprints are conservatively marked stale rather than silently trusted.
- Independent visible-Chrome QA verified fresh-clean state, pitch/lyric/automation/breath/tempo/voice edits, exact undo clearing, reload persistence, rerender clearing, irrelevant mixer/name/color edits remaining clean, legacy missing-fingerprint behavior, playback/export truthfulness, clean 1272×837 layout, and zero console/unexpected network failures. Evidence: `artifacts/e2e_screenshots/stale_render_detection/`.

Validation after iteration 64: frontend production build passed; targeted fingerprint/render tests passed; browser QA passed. Full automated suite passed with 123 tests collected.
