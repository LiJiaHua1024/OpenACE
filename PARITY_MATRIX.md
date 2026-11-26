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
| Interval repaint | Box-select a region and regenerate locally | **Partial** | ACE-Step `repaint` backend plus Alt-drag arrangement region selection and numeric seconds controls implemented. Masking semantics/real output validation pending GPU. |
| 12GB VRAM scheduling | Never co-resident large models | **Partial** | Process-local `VRAMManager`, CPU offload config, and subprocess serialization designed. Needs local physical memory telemetry validation. |
| Transposition conservation | Adjacent semitone intervals exactly preserved | **Done** | Core function, CLI/MCP path, regression tests, and UI transpose controls use uniform semitone shift; no octave folding/clamping. |
| F0 hygiene | No 0Hz filtering pollution or isolated octave jumps | **Done** | NaN masking and octave-error correction tests pass; diagnostics draw valid target/rendered F0. |
| Absolute beat anchoring | Vowel onset exactly on beat; consonant preonset 40–90ms | **Done** | Strict phoneme timing validation and regression tests pass. |
| Unknown lyric handling | Never silently replace unknown words with “la” | **Done** | Strict lexicon/CMUdict errors with HTTP 422; regression test. |
| Production anti-fake-audio rule | No sine/noise masquerading as synthesis | **Done** | Fixture is isolated, refuses unless `OPENACE_CI_SYNTH_FIXTURE=1`, and is visibly labeled in jobs/diagnostics. |

## P1 — DAW editing surface

| Capability | ACE Studio reference | Status | Evidence and remaining gap |
|---|---|---:|---|
| Multi-track arrangement | Track rows, clips, zoom/seek, drag | **Partial** | Canvas rows, note/clip rendering, shared zoom/scroll, content dragging, seek, mute/solo/volume/pan. No clip split/trim/fade/independent clip editing. |
| Piano roll | Dense high-frame-rate professional editor | **Partial** | Canvas brush/select/erase, drag, resize, lyric editing, velocity, zoom, grid, playhead. Missing marquee/multi-select/copy-paste/context menu/velocity lane/quantization UI. |
| Timeline synchronization | Arrangement, piano roll and automation share viewport | **Done** | Shared controlled timeline implemented and screenshot-verified. |
| Lyrics and phonemes | Fast lyric editing and visible phoneme decomposition | **Partial** | Double-click lyric editor, strict generated phoneme lane, vowel/consonant timing. No manual phoneme override or draggable boundaries. |
| Pitch automation | Draw pitch deviation and affect synthesis | **Partial** | Pitch lane edits persist and are written into SoulX target F0 metadata. Per-note vibrato/handle editing still shallow. |
| Air/Falsetto/Tension/Energy/Dynamics | Draw complete expression curves | **Partial** | Lanes edit/persist. Only Pitch is engine-conditioned so far; remaining curves are not yet consumed by SoulX. |
| Breath lane | Insert/edit breaths | **Partial** | Auto add-all and click add exist; no edge dragging/model consumption. |
| WebAudio playback | Transport plays rendered vocal/accompaniment | **Partial** | Decoded playback with volume/pan/mute/solo and moving playhead; now schedules all clips as well as latest render. No sample-accurate crossfade/live caching. |
| Undo/redo | Reliable DAW history | **Partial** | Project snapshots and transactions work for common editing. Needs coalescing and edge-case hardening. |
| Keyboard shortcuts | DAW-grade editing speed | **Partial** | Space, delete, Ctrl/Cmd+Z/Y implemented. Missing copy/paste/tool hotkeys. |
| Professional dark UI | ACE/Ableton-like density and polish | **Partial** | Dark multi-pane workstation, responsive transport fixes, project selector, no dead primary controls. Still below commercial visual depth. |

## P2 — audio/project production workflows

| Capability | Requirement | Status | Evidence and remaining gap |
|---|---|---:|---|
| Audio-to-MIDI import | Upload sung audio and edit extracted notes | **Partial** | `/api/import/audio`, UI control, librosa/pyin extraction, octave correction, explicit no-pitch failure. Browser/API verified. Lyric ASR is not yet merged into this import flow. |
| ASR lyrics | Real local transcription for cover/SVC | **Partial** | faster-whisper helper exists but is not yet integrated into the visible SVC/import workflow. |
| WAV master | Streaming-safe stereo mixdown | **Partial** | Clip-aware mixing with offsets, duplicate-path suppression, volume, approximate -14 LUFS/-1 dBTP normalization. Needs ffmpeg loudnorm/true-peak proof. |
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
| Render-job durability | Jobs survive backend restart | **Gap** | Job records are in-memory; project render paths persist. |

## P4 — tactile polish

| Capability | Status | Remaining gap |
|---|---:|---|
| Shared zoom/scroll | **Done** | Ctrl+wheel zoom and horizontal/vertical scroll synchronized; passive-listener console errors removed. |
| Project switching/creation | **Partial** | Selector, New Project, import-created project refresh. No delete/duplicate/recent-files UI. |
| Context menus | **Gap** | No right-click operations. |
| Advanced clip editing | **Gap** | No trim/split/fade/crossfade. |

## Highest-priority gaps for the next iteration

1. **Real GPU truth**: run `scripts/verify_local_gpu.py` on a 12GB NVIDIA machine; fix real SoulX/ACE-Step integration defects from actual logs and listening tests.
2. **Engine conditioning depth**: translate dynamic/air/falsetto/tension/energy/breath/vibrato into meaningful SoulX/SVC controls rather than editor-only persistence.
3. **Piano-roll professional depth**: marquee/multi-select/copy-paste/velocity lane/context menu/per-note pitch handles/quantize.
4. **Arrangement clip depth**: independent clip drag/trim/split/fades and visible waveform analysis.
5. **Commercial host validation**: open `.ustx`, `.svp`, `.vpr` in the real target applications and repair exact schemas.
6. **Job durability/recovery** and language coverage (validated Cantonese/Japanese frontends).
