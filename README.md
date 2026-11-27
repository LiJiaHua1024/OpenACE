# OpenACE

OpenACE is a local-first, open-source virtual singer workstation built to replicate the daily-production workflow of ACE Studio while remaining free of bundled commercial vocals, proprietary model weights, and cloud API-key requirements.

## Architecture

- **Web workstation**: React + Canvas arrangement view, piano-roll editor, lyric editing, vocal automation lanes, track mixer, render jobs, acoustic diagnostics, and export center.
- **Local API**: FastAPI project store, atomic editing endpoints, SSE synchronization, cancellable FIFO render orchestration, uploads, and format export.
- **Vocal core**: production adapter for [SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer) (Apache 2.0) score/melody SVS and SoulX-Singer-SVC.
- **Music/edit core**: production adapter for [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) (MIT), including ACE-Step `complete` Vocal2BGM and explicit interval repaint.
- **Agent surface**: `openace-tool` atomic CLI, `openace-mcp` MCP server (`stdio` and `streamable-http`), and `skills/openace/SKILL.md`.
- **Interop**: MIDI+LRC, OpenUtau `.ustx`, Synthesizer V `.svp`, VOCALOID `.vpr`, mastered `.wav`, and lyric `.mp4` export paths.

## Acoustic invariants

OpenACE treats the following as hard defects and covers them with tests:

1. no per-note octave folding or clamping during transposition;
2. no 0Hz/unvoiced-frame pollution in F0 smoothing; isolated octave artifacts are corrected without suppressing real melodic leaps;
3. note vowel onset is the absolute beat anchor, with consonant pre-onset constrained to the 40–90 ms performance zone;
4. unknown lyrics are explicit errors and are never silently replaced by “啦/la”.

Production rendering never synthesizes fake sine-wave vocals. The harmonic/noise fixture implementation is isolated in `openace/engines/fixture.py`, is refused unless `OPENACE_CI_SYNTH_FIXTURE=1`, and exists only for CPU CI/UI orchestration tests.

## Quick start (CPU sandbox / development)

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cd frontend && npm install && npm run build && cd ..
OPENACE_CI_SYNTH_FIXTURE=1 .venv/bin/openace-server
```

Open <http://127.0.0.1:8787>.

## Real GPU installation

On a local NVIDIA machine with about 12 GB VRAM:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[gpu]'
python scripts/verify_local_gpu.py --hf-endpoint https://hf-mirror.com  # optional mirror
.venv/bin/openace-server
```

`verify_local_gpu.py` clones the upstream engines, downloads public weights without API keys, runs real SoulX-Singer and ACE-Step inference in separate subprocesses, and writes `artifacts/local_gpu/report.json`. Model subprocesses are serialized by `VRAMManager`; the two large model families are never intentionally resident together.

## CLI examples

```bash
openace-tool create-project --title demo
openace-tool add-track <project-id> --name Lead --language zh
openace-tool add-note <project-id> <track-id> --start 0 --duration 480 --pitch 60 --lyric 你
openace-tool validate <project-id>
openace-tool export <project-id> svp out.svp
OPENACE_CI_SYNTH_FIXTURE=1 openace-tool render-vocal <project-id> <track-id>
```

## Arrangement editing

Timeline synchronization uses shared musical-tick state between arrangement, piano roll, automation, diagnostics, playback, and export. Transport time signatures are editable (including compound meters such as 6/8 and 12/8); grid and transport math are denominator-aware rather than hard-coded to four quarter notes per bar.

Audio clips are true timeline slices (`start/offset/duration`) with decoded waveforms, edge trimming, split-at-cursor, linear fade-in/out handles, and clip gain. Fade handles are dragged from the top corners; fades reshape the displayed waveform, schedule WebAudio gain ramps during monitor playback, and are rendered into master WAV exports. Overlapping faded clips therefore crossfade naturally.

Track cards provide right-click/⋯ operations for duplicate, reorder, color, and undoable delete in addition to mute/solo/volume/pan. The arrangement canvas draws real decoded waveform peaks for audio clips rather than placeholder stripes. Audio clips drag independently, trim from either edge while preserving source offsets, and split at the cursor through the context menu. Waveforms remap to the trimmed source segment, contiguous vocal-note groups drag as musical phrases, and all clip timing paths persist through the same playback/export pipeline. Overlapping clips on a track automatically receive equal-power crossfades: the overlap is shown with a compact XF badge and complementary curves, waveform peaks attenuate with the crossfade, WebAudio schedules the envelope, and master export applies the same cosine/sine gains. The clip context menu supports split at cursor, copy, paste at cursor (including empty arrangement space and other audio-capable tracks), duplicate, delete, and gain; pasted clips preserve source offsets, durations, fades, and gain, while menus are compacted and clamped inside the arrangement strip.

Direct arrangement import is also first-class: **Import audio as clip at playhead** validates real audio with SoundFile, measures its duration, converts seconds through the project tempo map, creates an `Audio — <name>` track when needed, and inserts a persistent editable clip. Uploaded media is served back to the browser for real waveform analysis and WebAudio playback while backend master export reads the same local media; corrupt files are rejected without creating arrangement garbage. When an audio/accompaniment track is selected the clip is inserted there; vocal-track selection intentionally falls back to a new audio track. Generic uploads use unique persistent names so same-name files cannot overwrite media already referenced by arrangements or jobs.

## Stem separation and dry/wet remix

`Separate vocal/instrumental` uses local open-source Demucs (`htdemucs`, optional `gpu` extra) with no API key. Production separation never falls back to fixture audio: if Demucs or weights/runtime support are unavailable the job fails loudly with installation guidance. The explicit CI fixture exists only for orchestration tests and is labeled as such. Completed separation creates independent `Separated vocal` and `Separated instrumental` arrangement tracks/clips with provenance metadata, so existing mute/solo/volume/pan/clip gain, waveform editing, playback, and loudness master export provide the dry/wet remix workflow. MCP `separate_stems` and CLI `openace-tool separate` expose the same operation to agents.

## Expression automation

Pitch deviation is written into SoulX target F0 metadata. SoulX-Singer does not expose a direct neural Dynamic control, so OpenACE applies the Dynamic lane as honest post-render gain automation: neutral `0.5`, ±6 dB range, sample-interpolated gain, clipping protection, and explicit diagnostic/job provenance. Air is also applied as honest post-render DSP: it reinforces or attenuates the 3 kHz+ residue already present in the rendered vocal, with no injected synthetic noise and explicit non-neural provenance. Energy adds harmonic density through parallel soft saturation for positive values and softens through low-pass blending for negative values. Tension reinforces or attenuates the 0.9–5.5 kHz articulation/presence band extracted from the actual vocal. Both are peak-protected and explicitly labeled as non-neural DSP. Falsetto uses a spectral-tilt approximation: positive values thin the low chest-resonance band and reinforce existing upper vocal residue, while negative values produce a chestier/pressed tilt; it does not shift F0 and is explicitly labeled as non-neural DSP.

## Piano-roll editing

Selected notes expose a professional vibrato editor (enable, start ratio, depth cents, rate Hz, phase) through the toolbar or context menu. Vibrato is drawn directly on note bodies as a parameter-driven sine indication and is consumed by the SoulX F0 metadata builder rather than being editor-only data.

The `∿` pitch-handle tool creates draggable per-note pitch points directly on note bodies. Handles are linearly interpolated (not sampled only at exact frames), affect the SoulX target F0 metadata, and appear in diagnostic target curves; Alt+click deletes a handle.

The note context menu also exposes manual phoneme overrides: enter space-separated symbols, OpenACE times pre-vowel consonants before the beat and post-vowel consonants in sequence, validates against placeholder/empty/no-vowel input, and can reset to automatic lyric-derived phonemes. In the Breath & Phoneme lane, visible onset/end and internal boundaries can be dragged with millisecond accuracy; neighboring segments remain contiguous, durations stay positive, and the first vowel is locked to the 0ms beat anchor.

The canvas piano roll supports brush/select/erase tools, marquee multi-select, multi-note move/resize with interval-preserving pitch deltas, copy/paste/duplicate, quantize, a right-click edit menu, and a bottom velocity lane whose values round-trip through MIDI/VPR export. Static notes/grid and the moving playhead are separate stacked canvases, gradients are cached, and dense views use level-of-detail fills/label elision; regression evidence sustains 60FPS playback and continuous scrolling with 3000 dense notes at 1400×900@2x.

## Repaint region selection

In the arrangement canvas, hold **Alt** and drag across the timeline to draw the yellow repaint region. The same region is reflected in the Vocal2BGM/Repaint panel as numeric seconds and is passed to the ACE-Step repaint job.

## Audio-to-MIDI and local ASR lyrics

`Import audio` transcribes a monophonic vocal into editable notes with librosa/pYIN octave-error correction, then runs local faster-whisper with word-level timestamps. Each recognized word is assigned once to the overlapping note (or a near-onset note within 300ms), the detected language is stored on the imported track, and CPU-heavy transcription runs outside the FastAPI event loop. Unaligned notes stay visually blank; OpenACE never fills them with “la”, dash, or fabricated placeholder lyrics. If ASR cannot produce or align timestamped words, import fails loudly instead of pretending the lyrics are known. The default local model is `small`; override with `OPENACE_WHISPER_MODEL`, `OPENACE_WHISPER_DEVICE`, and `OPENACE_WHISPER_COMPUTE_TYPE` when needed.

## Lyric correction

The right-hand **Lyric correction** panel exposes a compact per-note correction workflow for imported or manually written vocal tracks. It shows note/missing counts, bar·pitch position, editable lyric rows, and regenerated phoneme feedback. Batch paste maps continuous CJK text one Unicode character per note while whitespace-separated chunks stay together for romanized/multi-letter syllables; a count mismatch is rejected atomically rather than partially overwriting the melody. Per-note commits and batch application use normal persistence/undo, and changing a lyric clears stale phonemes so the strict backend validator regenerates timing for the new language-specific lyric.

## Multilingual lyric validation

Mandarin uses strict pinyin decomposition, English uses CMUdict-backed phones, and Cantonese uses `pycantonese` tone-bearing Jyutping. Cantonese editor phonemes decompose onset/nucleus/coda explicitly (including syllabic `m̩`/`ŋ̩`), while SoulX metadata emits validated `yue_<jyutping>` phones with canonical language `Cantonese`. Unsupported characters or missing pronunciations fail loudly; Japanese remains unavailable rather than fake because the current SoulX phone set has no Japanese inventory.

## OpenUtau USTX interoperability

`.ustx` export follows the OpenUtau 0.10 source schema rather than a guessed YAML shape: exact `UNote` keys and mandatory two-point pitch defaults, scaling from any OpenACE PPQ to OpenUtau’s fixed 480 PPQ, OpenUtau pitch units (0.1 semitone), vibrato length/period/depth/shift conversion, beat-aligned voice-part durations, `xs`/`ys` automation curves, decibel track faders, -100..100 pan, named track colors, and the real default phonemizer id. Dynamic automation maps to OpenUtau `dyn` in decibel×10 units and pitch deviation maps to `pitd` cents. Manual phoneme symbols are exported as overrides, but OpenACE millisecond offsets are not misrepresented as OpenUtau tick deltas. Arrangement audio clips now export as real OpenUtau `wave_parts` with measured source duration, relative paths, fixed-480 tick-scaled position/source-skip/trim, and fade times; clip gain is not faked because UWavePart has no per-clip gain field. `.ustx` import is bidirectional and restores internal project names, tempo/time signature, track units/colors/types, voice notes and lyrics, intentional pitch curves (while ignoring mandatory serializer defaults), vibrato, phoneme overrides, dyn/pitd automation, and wave-clip timing/fades. For wave media portability, the same import control accepts a secure zip package containing exactly one `.ustx` plus bundled relative audio; extraction rejects traversal/symlinks and media persists under OpenACE uploads. Plain single-file `.ustx` upload still cannot magically access sibling media beside the original project, so unresolved external wave media remains a documented host/file-packaging limitation rather than being fabricated.

## Synthesizer V SVP interoperability

`.svp` export uses the real Synthesizer V group/reference shape: deterministic group UUIDs, `mainRef` database/voice metadata, blick-based timing, and flattened automation point pairs. Pitch deviation exports as semitone `pitchDelta`, Dynamic as loudness dB, Tension/Air as centered -1..1 tension/breathiness curves, and vibrato start time is correctly converted from an OpenACE note ratio into seconds.

## Mastering and export

Master WAV export is not approximate peak normalization: OpenACE first uses transparent constant-gain loudness normalization when peak headroom permits, falls back to two-pass ffmpeg `loudnorm` for peaky material, then independently measures the resulting file with ffmpeg EBU R128 loudness/true-peak statistics. Compliant masters are approximately `-14.0 LUFS` with true peak below `-1.0 dBTP`; material that cannot be validated fails loudly instead of silently shipping a false master. ffmpeg is therefore a required local runtime dependency for WAV/MP4 export.

## MCP

```bash
openace-mcp --transport stdio
openace-mcp --transport streamable-http --host 127.0.0.1 --port 8788
```

The MCP tools mirror the atomic CLI: create/duplicate/delete projects, create tracks/notes, batch/edit notes, write expression lanes and breath events, edit audio clips and tempo maps, assign reference voices, transpose with interval conservation, render, separate stems, repaint, convert voices, import real audio/MIDI projects, and export project formats. External project creation/import/deletion and render-produced arrangement changes issue best-effort loopback SSE notifications so an already-open workstation updates without reload. No hosted model or vendor API key is involved.

## Repository layout

- `openace/core` — project model, timing, phonemes, pitch/F0 invariants, loudness, diagnostics
- `openace/engines` — SoulX-Singer, ACE-Step, VRAM scheduling, model bootstrap, explicit CI fixture
- `openace/server` — FastAPI app, durable auto-requeued/cancellable render jobs, SSE
- `openace/exporters` / `openace/importers` — DAW/project/audio interoperability
- `frontend` — professional dark workstation UI
- `scripts` — one-command model bootstrap and real GPU verification
- `PARITY_MATRIX.md` — living ACE Studio parity audit
- `VERIFICATION_REPORT.md` — current verification evidence and limitations
