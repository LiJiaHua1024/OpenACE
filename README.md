# OpenACE

OpenACE is a local-first, open-source virtual singer workstation built to replicate the daily-production workflow of ACE Studio while remaining free of bundled commercial vocals, proprietary model weights, and cloud API-key requirements.

## Architecture

- **Web workstation**: React + Canvas arrangement view, piano-roll editor, lyric editing, vocal automation lanes, track mixer, render jobs, acoustic diagnostics, and export center.
- **Local API**: FastAPI project store, atomic editing endpoints, SSE synchronization, render orchestration, uploads, and format export.
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

Audio clips are true timeline slices (`start/offset/duration`) with decoded waveforms, edge trimming, split-at-cursor, linear fade-in/out handles, and clip gain. Fade handles are dragged from the top corners; fades reshape the displayed waveform, schedule WebAudio gain ramps during monitor playback, and are rendered into master WAV exports. Overlapping faded clips therefore crossfade naturally, although automatic crossfade creation is not yet implemented.

The arrangement canvas draws real decoded waveform peaks for audio clips rather than placeholder stripes. Audio clips drag independently, trim from either edge while preserving source offsets, and split at the cursor through the context menu. Waveforms remap to the trimmed source segment, contiguous vocal-note groups drag as musical phrases, and all clip timing paths persist through the same playback/export pipeline.

## Expression automation

Pitch deviation is written into SoulX target F0 metadata. SoulX-Singer does not expose a direct neural Dynamic control, so OpenACE applies the Dynamic lane as honest post-render gain automation: neutral `0.5`, ±6 dB range, sample-interpolated gain, clipping protection, and explicit diagnostic/job provenance. Air, falsetto, tension, and energy lanes remain persistent editor data until a truthful engine or DSP mapping exists.

## Piano-roll editing

Selected notes expose a professional vibrato editor (enable, start ratio, depth cents, rate Hz, phase) through the toolbar or context menu. Vibrato is drawn directly on note bodies as a parameter-driven sine indication and is consumed by the SoulX F0 metadata builder rather than being editor-only data.

The `∿` pitch-handle tool creates draggable per-note pitch points directly on note bodies. Handles are linearly interpolated (not sampled only at exact frames), affect the SoulX target F0 metadata, and appear in diagnostic target curves; Alt+click deletes a handle.

The canvas piano roll supports brush/select/erase tools, marquee multi-select, multi-note move/resize with interval-preserving pitch deltas, copy/paste/duplicate, quantize, a right-click edit menu, and a bottom velocity lane whose values round-trip through MIDI/VPR export.

## Repaint region selection

In the arrangement canvas, hold **Alt** and drag across the timeline to draw the yellow repaint region. The same region is reflected in the Vocal2BGM/Repaint panel as numeric seconds and is passed to the ACE-Step repaint job.

## MCP

```bash
openace-mcp --transport stdio
openace-mcp --transport streamable-http --host 127.0.0.1 --port 8788
```

The MCP tools mirror the atomic CLI: create projects/tracks/notes, transpose with interval conservation, render, repaint, convert voices, and export project formats. No hosted model or vendor API key is involved.

## Repository layout

- `openace/core` — project model, timing, phonemes, pitch/F0 invariants, loudness, diagnostics
- `openace/engines` — SoulX-Singer, ACE-Step, VRAM scheduling, model bootstrap, explicit CI fixture
- `openace/server` — FastAPI app, render jobs, SSE
- `openace/exporters` / `openace/importers` — DAW/project/audio interoperability
- `frontend` — professional dark workstation UI
- `scripts` — one-command model bootstrap and real GPU verification
- `PARITY_MATRIX.md` — living ACE Studio parity audit
- `VERIFICATION_REPORT.md` — current verification evidence and limitations
