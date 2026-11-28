# Real OpenUtau host validation

OpenUtau Linux x64 `v0.1.576.0` was downloaded from the official OpenUtau release and run visibly in the session desktop.

Validated observations:

- `openace_host_validation.ustx` opened directly in OpenUtau with the project filename shown in the title bar.
- The vocal track and voice part appeared in the arrangement. After double-clicking the part, both Chinese lyric notes (`你`, `好`) appeared at distinct C4/D4 pitch rows, with visible pitch/deviation and dynamics curves in the expression lanes.
- The initial export exposed an interoperability flaw: OpenACE's internal `zero-shot-reference` voice id was serialized as if it were an OpenUtau singer id, producing `[Missing] zero-shot-reference`. The exporter was fixed to emit an empty singer reference; the host then truthfully shows `Select Singer` instead of a broken missing dependency.
- `openace_host_wave_validation.ustx` opened directly and showed the imported audio wave part at the expected arrangement position with its source filename label.

Limits: no singer voicebank is installed in this sandbox, so OpenUtau synthesis/playback quality was not validated. Screenshots are empirical host-opening evidence, not automated host regression tests.
