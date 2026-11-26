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
