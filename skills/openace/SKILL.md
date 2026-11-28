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
openace-tool batch-add-notes <project-id> <track-id> '[{"start_ticks":0,"duration_ticks":480,"pitch":60,"lyric":"你"}]'
openace-tool update-note <project-id> <track-id> <note-id> '{"pitch":64}'
openace-tool delete-note <project-id> <track-id> <note-id>
openace-tool ripple-delete-range <project-id> <start-ticks> <end-ticks>
openace-tool validate <project-id>
openace-tool transpose <project-id> <track-id> 2
openace-tool set-expression <project-id> <track-id> dynamic '[{"ticks":0,"value":0.5},{"ticks":960,"value":1.0}]'
openace-tool upsert-breath <project-id> <track-id> '{"start_ticks":960,"duration_ticks":120,"intensity":1.2,"timbre":"natural"}'
openace-tool upsert-clip <project-id> <track-id> '{"path":"/path/audio.wav","start_ticks":0,"duration_ticks":960}'
openace-tool set-tempo <project-id> --bpm 120 --points-json '[{"ticks":960,"bpm":60}]'
openace-tool assign-voice <project-id> <track-id> <voice-id> --reference-voice /path/reference.wav
openace-tool duplicate-project <project-id> --title "Copy"
openace-tool organize-project <project-id> --pinned true --tags "lead,draft"
openace-tool delete-project <project-id>
openace-tool import-audio vocal.wav --title "Imported Vocal"
openace-tool import-midi input.mid --title "Imported Song"
openace-tool render-vocal <project-id> <track-id>
# If a queued server-side render was a mistake:
openace-tool cancel-render-job <job-id>
openace-tool vocal2bgm <project-id> --track <vocal-track-id> --caption "professional instrumental accompaniment"
openace-tool vocal2bgm <project-id> <source.wav> [--clip-id <clip-id>] --caption "professional instrumental accompaniment"
# with --clip-id, the exact visible/trimmed clip segment is the input and output aligns to that clip
openace-tool repaint <project-id> <source.wav> --start 1.0 --end 5.0 [--clip-id <clip-id>] --caption "warmer rock backing"
# start/end are arrangement seconds; the source must exist as an intersecting arrangement clip
openace-tool separate <project-id> <source.wav>
openace-tool svc <project-id> <source.wav> <reference.wav> [--clip-id <clip-id>]
openace-tool export <project-id> svp output.svp
openace-tool export <project-id> ustx output.ustx
openace-tool export <project-id> vpr output.vpr
openace-tool export <project-id> mid output.mid
openace-tool export <project-id> wav output.wav
```

JSON arguments may be inline JSON or paths to JSON files. Use exact musical ticks. `ripple-delete-range` destructively cuts that musical interval across all tracks, truthfully splitting boundary vocal notes/audio clips and shifting downstream material; confirm the user wants destructive ripple editing before using it. Expression values are normalized 0–1 except `pitch_cents` (±100 cents). Breath intensity is 0–2 and timbre is `soft`, `natural`, or `strong`.

## MCP reference

Start locally:

```bash
openace-mcp --transport stdio
# or
openace-mcp --transport streamable-http --host 127.0.0.1 --port 8788
```

Use tools with the same semantics as the CLI. Prefer many small atomic calls over ad-hoc JSON mutation so validation and SSE synchronization remain intact. Available editing tools include `batch_add_notes`, `update_note`, `delete_note`, `ripple_delete_range`, `set_expression_lane`, `upsert_breath`, `delete_breath`, `upsert_audio_clip`, `delete_audio_clip`, `set_tempo_map`, `organize_project`, `assign_voice`, and `import_midi_project`, in addition to project/track/note creation, transposition, rendering, queued/running render cancellation (`cancel_render_job`), separation, conversion, repaint, and export.
Media-library atoms: `openace-tool list-media`, `openace-tool place-media-clip <project> <media_name> --start-ticks <ticks> [--track-id <id>]`, and `openace-tool delete-media <media_name>`. Deletion is safe and fails while arrangement clips reference the media.
