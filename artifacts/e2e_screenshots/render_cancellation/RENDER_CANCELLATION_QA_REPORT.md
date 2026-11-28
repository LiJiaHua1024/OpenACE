# Render cancellation QA

Real visible Chrome 1272×837, backend restarted with `OPENACE_CI_SYNTH_FIXTURE=1 OPENACE_CI_FIXTURE_DELAY_SECONDS=8`; repo unchanged.

Passed:
- Created lyric note and enqueued two vocal renders quickly; FIFO state observed: one running, one queued.
- Cancel queued became `canceled` in 0.545s; cancel button disappeared.
- Cancel running became `canceled` in 0.532s, far before the 8s fixture delay; output_path remained null.
- Neither canceled job produced output.
- A third render subsequently completed with real `vocal.wav`; completed jobs showed no cancel button.
- Reload preserved durable statuses `completed,canceled,canceled`.
- Repeat cancel of completed job through scripted API returned exact 409 detail `cannot cancel render job in state completed`.
- Additional adoption check: after canceling a fourth running job, existing track render_path remained exactly the prior completed render; latest canceled job had null output.
- CLI presence check passed: `openace-tool cancel-render-job [-h] job`.
- Console/network clean; the 409 was scripted and intentionally not triggered in browser UI because completed jobs correctly have no cancel button.

Note: third completion wait measured 9.92s from click using the 8s delayed CI fixture plus fixture/render overhead; cancellation itself was responsive at ~0.53s. MCP tool presence was not tested.

Evidence: `render_cancellation_results.json`, screenshots 01–05.
