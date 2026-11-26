---
name: openace
description: Compose, tune, render, revise, and export local-first virtual singer songs through OpenACE's atomic CLI or MCP tools without API keys.
---

# OpenACE Agent Skill

Use OpenACE when the user asks to write, tune, synthesize, convert, repaint, or export a vocal song locally. OpenACE is agent-native: prefer the MCP tools when available, otherwise use the atomic `openace-tool` CLI. It has no hosted-vendor API key dependency.

## Operating rules

1. Never fabricate vocals or claim audio is real model output when it came from the CI fixture. Fixture output exists only when `OPENACE_CI_SYNTH_FIXTURE=1` is explicitly set.
2. Never silently replace unknown lyrics with `啦`/`la`. If validation returns a lyric/phoneme error, ask the user for corrected lyrics or choose supported replacement words explicitly.
3. Preserve melodic intervals exactly when transposing. Use OpenACE's transpose tool rather than editing pitches one note at a time.
4. Treat vowel onset as the beat anchor. Do not manually stretch phoneme timings unless the OpenACE API exposes a validated operation.
5. On 12GB GPUs, run one heavy engine stage at a time: finish vocal rendering before Vocal2BGM/repaint/SVC.
6. Inspect `diagnostic.png` after every render. Report pitch/beat issues plainly instead of claiming perfection.

## Standard creative workflow

1. Create or open a project.
2. Add a vocal track with the intended language (`zh` or `en`; unsupported languages must fail loudly).
3. Add notes with exact tick positions, duration, MIDI pitch, and lyrics.
4. Run project validation before rendering.
5. Render vocals. Check `diagnostic.png` for target-vs-rendered pitch and beat offset.
6. If the performance is wrong, revise notes/lyrics/pitch and render again; do not mask errors by editing audio externally.
7. Generate accompaniment with Vocal2BGM only after vocals are stable.
8. Use repaint for a bounded time interval when only a section needs regeneration.
9. Export project/audio formats requested by the user.
10. Return local paths/URLs and mention any validation limitation honestly.

## CLI reference

```bash
openace-tool create-project --title "Song Title"
openace-tool add-track <project-id> --name "Lead" --language zh
openace-tool add-note <project-id> <track-id> --start 0 --duration 480 --pitch 60 --lyric 你
openace-tool validate <project-id>
openace-tool transpose <project-id> --semitones 2
openace-tool render-vocal <project-id> <track-id>
openace-tool vocal2bgm <project-id> --source-audio reference.wav
openace-tool repaint <project-id> --start-ms 1000 --end-ms 5000 --prompt "warmer rock backing"
openace-tool export <project-id> svp output.svp
openace-tool export <project-id> ustx output.ustx
openace-tool export <project-id> vpr output.vpr
openace-tool export <project-id> mid output.mid
openace-tool export <project-id> wav output.wav
```

## MCP reference

Start locally:

```bash
openace-mcp --transport stdio
# or
openace-mcp --transport streamable-http --host 127.0.0.1 --port 8788
```

Use tools with the same semantics as the CLI. Prefer many small atomic calls over ad-hoc JSON mutation so validation and SSE synchronization remain intact.
