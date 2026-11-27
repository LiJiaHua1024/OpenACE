# OpenACE ↔ ACE Studio Parity Matrix

Status legend: **Done** (implemented and exercised end-to-end in this repository), **Partial** (real implementation exists but production depth or validation is incomplete), **Gap** (missing). This is an adversarial living audit, not marketing copy.

Last audit iteration: 2026-11-26, after independent browser QA and defect-fix round.

## P0 — synthesis cores and acoustic invariants

| Capability | ACE Studio / OpenACE requirement | Status | Evidence and remaining gap |
|---|---|---:|---|
| Score-to-singing neural SVS | Commercial-grade singing from notes+lyrics | **Partial** | Real SoulX-Singer subprocess adapter, score metadata builder, strict phone validation, zero-shot preprocessing entrypoint, and local GPU verifier implemented. Not yet run on physical GPU in this sandbox. |
| Zero-shot reference voice | Upload reference and synthesize in that voice | **Partial** | Upload slot, persistence, preprocess invocation, render wiring implemented. Voice library/mixing/browser still primitive. |
| SVC hot-song conversion | Convert an existing performance | **Partial** | SoulX-Singer-SVC module invocation and F0 extraction path implemented; not GPU-verified. |
| Vocal2BGM | Generate musical accompaniment around a vocal | **Partial** | Correct upstream ACE-Step `complete` task semantics wired with `src_audio`; fixture/browser orchestration verified. Real musical quality not GPU-verified. |
| Interval repaint | Box-select a region and regenerate locally | **Partial** | ACE-Step `repaint` backend plus visible Alt-drag arrangement region selection and rounded numeric seconds controls implemented; regression screenshot verifies the overlay. Masking semantics/real output validation pending GPU. |
| 12GB VRAM scheduling | Never co-resident large models | **Partial** | Process-local `VRAMManager`, CPU offload config, and subprocess serialization designed. Needs local physical memory telemetry validation. |
| Transposition conservation | Adjacent semitone intervals exactly preserved | **Done** | Core function, CLI/MCP path, regression tests, and UI transpose controls use uniform semitone shift; no octave folding/clamping. |
| F0 hygiene | No 0Hz filtering pollution or isolated octave jumps | **Done** | NaN masking and octave-error correction tests pass; diagnostics draw valid target/rendered F0. |
| Absolute beat anchoring | Vowel onset exactly on beat; consonant preonset 40–90ms | **Done** | Strict phoneme timing validation and regression tests pass. |
| Unknown lyric handling | Never silently replace unknown words with “la” | **Done** | Strict lexicon/CMUdict errors with HTTP 422; regression test. |
| Production anti-fake-audio rule | No sine/noise masquerading as synthesis | **Done** | Fixture is isolated, refuses unless `OPENACE_CI_SYNTH_FIXTURE=1`, and is visibly labeled in jobs/diagnostics. |

## P1 — DAW editing surface

| Capability | ACE Studio reference | Status | Evidence and remaining gap |
|---|---|---:|---|
| Multi-track arrangement | Track rows, clips, zoom/seek, drag | **Partial** | Canvas rows, note/clip rendering, shared zoom/scroll, seek, mute/solo/volume/pan, independent audio-clip dragging, edge trimming with source-offset preservation, right-click split-at-cursor, grouped-note dragging, and real decoded waveform peaks remapped to trimmed segments. Linear fade-in/out endpoints, clip gain, playback gain ramps, export fades, and automatic equal-power crossfades for overlapping clips, copy/paste/duplicate/delete context operations, and compact clamped clip menus are implemented; track cards also provide real right-click/⋯ context operations for duplicate with fresh IDs, reorder, color, delete, and undo/redo-safe project persistence. Deeper project/media management remains absent. |
| Piano roll | Dense high-frame-rate professional editor | **Partial** | Canvas brush/select/erase, drag, resize, lyric editing, marquee multi-select, multi-note move/resize, cross-track copy/paste/duplicate, quantize, velocity lane, context menu, zoom/grid/playhead. Sustained dense-project 60FPS profiling is regression-verified at 1400×900@2x. Cross-track clipboard is regression-verified. Vibrato and per-note pitch handles now have visual/editor controls and are written into SoulX F0/diagnostic target curves. |
| Timeline synchronization | Arrangement, piano roll and automation share viewport | **Done** | Shared controlled timeline implemented and screenshot-verified. |
| Lyrics and phonemes | Fast lyric editing and visible phoneme decomposition | **Partial** | Double-click lyric editor, strict generated phoneme lane, vowel/consonant timing. Manual symbol override/reset is implemented with backend timing and validation. Phoneme onset/end boundaries are draggable in the Breath & Phoneme lane with contiguous timing, positive-duration constraints, and a locked 0ms first-vowel beat anchor. |
| Pitch automation | Draw pitch deviation and affect synthesis | **Partial** | Pitch lane edits persist and are written into SoulX target F0 metadata. Per-note vibrato editing is implemented with start/depth/rate/phase and canvas indication; per-note pitch handles can be created, dragged, Alt-click deleted, and are linearly interpolated into SoulX/diagnostic F0. |
| Air/Falsetto/Tension/Energy/Dynamics | Draw complete expression curves | **Partial** | Lanes edit/persist. Pitch is engine-conditioned in SoulX F0; Dynamic is honestly applied as ±6dB post-render gain automation with clipping protection because SoulX exposes no neural dynamic control. Air is honest high-frequency post-render DSP derived from the vocal (not injected noise or neural conditioning); Energy is harmonic-density/softening DSP; Tension is 0.9–5.5kHz presence-band DSP; Falsetto is spectral-tilt DSP that thins/reinforces chest resonance without shifting F0. |
| Breath lane | Insert/edit breaths | **Partial** | Auto add-all and click add exist; no edge dragging/model consumption. |
| WebAudio playback | Transport plays rendered vocal/accompaniment | **Partial** | Decoded playback with volume/pan/mute/solo and moving playhead; now schedules all clips as well as latest render. No sample-accurate crossfade/live caching. |
| Undo/redo | Reliable DAW history | **Partial** | Project snapshots and transactions work for common editing. Needs coalescing and edge-case hardening. |
| Keyboard shortcuts | DAW-grade editing speed | **Partial** | Space, delete, Ctrl/Cmd+Z/Y, Ctrl+A/C/V/D and V/B/E/Q tool/edit hotkeys implemented. Additional ACE-specific hotkey mapping can be deepened. |
| Professional dark UI | ACE/Ableton-like density and polish | **Partial** | Dark multi-pane workstation, responsive transport fixes, project selector, no dead primary controls. Still below commercial visual depth. |

## P2 — audio/project production workflows

| Capability | Requirement | Status | Evidence and remaining gap |
|---|---|---:|---|
| Audio-to-MIDI import | Upload sung audio and edit extracted notes | **Partial** | `/api/import/audio`, UI control, librosa/pyin extraction, octave correction, explicit no-pitch failure, and local faster-whisper word-timestamp alignment are browser/API verified on a real vocal example. Empty unaligned notes remain blank rather than placeholder text. Monophonic extraction quality and lyric correction depth remain below a commercial editor. |
| ASR lyrics | Real local transcription for cover/SVC | **Partial** | Local faster-whisper word timestamps are integrated into audio import with detected language, async execution, strict no-placeholder failure, and browser proof. A dedicated lyric-correction workflow and SVC-side lyric display remain absent. |
| WAV master | Streaming-safe stereo mixdown | **Done** | Clip-aware mixing with offsets/duplicate-path suppression/volume/crossfades writes through transparent constant-gain normalization when possible, with two-pass ffmpeg loudnorm fallback for peaky material. Output is independently measured through ffmpeg EBU R128 loudness/true-peak statistics at about -14 LUFS and below -1 dBTP; non-conforming edge material fails loudly rather than silently exporting a false master. |
| MP4 dynamic lyric video | Shareable synchronized lyric render | **Partial** | Rewritten to burn timed ASS subtitles and explicitly match audio duration; regression test passes. Karaoke highlighting/polished typography still absent; CJK rendering depends on host fonts. |
| MIDI+LRC | Interoperable lyric MIDI export/import | **Partial** | UTF-8 roundtrip tests pass; tempo-map edge cases remain. |
| OpenUtau `.ustx` | Openable in OpenUtau | **Partial** | Structural YAML writer/test. Not validated in actual OpenUtau. |
| Synthesizer V `.svp` | Openable in SynthV | **Partial** | Structural JSON writer/test. Not validated in actual Synthesizer V. |
| VOCALOID `.vpr` | Openable in VOCALOID5/6 | **Partial** | ZIP `Project/sequence.json` writer/test. Not validated in actual VOCALOID. |
| Stem separation / dry-wet remix | ACE-like source separation workflow | **Gap** | No first-class stem separation workflow. |

## P3 — agent-native operation

| Capability | Requirement | Status | Evidence and remaining gap |
|---|---|---:|---|
| Atomic CLI | Complete agent operation without keys | **Partial** | Project/track/note/transpose/render/export commands implemented. Missing batch note editing/import/clip commands. |
| MCP stdio | Standard agent integration | **Done** | Real MCP client protocol smoke test passes: initialize, list tools, create project, add validated note. |
| MCP streamable HTTP | HTTP agent transport | **Done** | Real MCP streamable HTTP client smoke test passes. |
| MCP→UI live synchronization | External agent edits appear in workstation | **Done** | MCP writes persist then issue best-effort loopback publish into the FastAPI SSE bus; browser verification showed 4→5 notes without manual reload. |
| Agent skill | Drop-in instructions | **Partial** | `skills/openace/SKILL.md` exists; should be installed/used in more real agent sessions. |
| Acoustic X-ray diagnostics | Every render emits inspectable diagnostic | **Done** | Target/rendered F0, beat offsets, spectrogram, fixture provenance labels; browser/API verified. |
| Render-job durability | Jobs survive backend restart | **Done** | Job records persist atomically in `data/renders/jobs.json`; queued/running jobs with durable inputs are automatically requeued after backend restart and serially rerun, while legacy jobs missing inputs fail loudly rather than silently disappearing. Restart integration proof passed. |

## P4 — tactile polish

| Capability | Status | Remaining gap |
|---|---:|---|
| Shared zoom/scroll | **Done** | Ctrl+wheel zoom and horizontal/vertical scroll synchronized; passive-listener console errors removed. |
| Project switching/creation | **Partial** | Selector, New Project, import-created project refresh. No delete/duplicate/recent-files UI. |
| Context menus | **Partial** | Piano-roll note context menu implements copy/paste/duplicate/quantize/delete; arrangement clips expose split/copy/paste/duplicate/delete/gain in a compact clamped menu; track cards expose duplicate/reorder/color/delete through right-click and ⋯ menus. Project-level context/recent-file operations remain absent. |
| Advanced clip editing | **Partial** | Independent move, edge trim/re-extension, source offsets, and split-at-cursor implemented. Richer clip operations remain missing. |

## Highest-priority gaps for the next iteration

1. **Real GPU truth**: run `scripts/verify_local_gpu.py` on a 12GB NVIDIA machine; fix real SoulX/ACE-Step integration defects from actual logs and listening tests.
2. **Breath modeling depth**: translate breath events into meaningful SoulX/SVC or honest audio behavior rather than editor-only persistence; vibrato is F0-consumed, Dynamic is gain DSP, Air is high-frequency DSP, Energy is harmonic-density DSP, Tension is presence-band DSP, and Falsetto is spectral-tilt DSP.
3. **Piano-roll professional depth**: advanced editing feel/visual parity can still deepen; large-project dense scrolling/playback at sustained 60FPS is now regression-verified, cross-track clipboard is verified, and vibrato/pitch-handle editing is engine-consumed.
4. **Arrangement operational depth**: project/media management depth; independent dragging, trim, split, fades, clip gain, automatic equal-power crossfades, clip copy/paste/duplicate/delete, track duplicate/reorder/color/delete, and real waveform analysis are now implemented.
5. **Commercial host validation**: open `.ustx`, `.svp`, `.vpr` in the real target applications and repair exact schemas.
6. **Language coverage** (validated Cantonese/Japanese frontends).
