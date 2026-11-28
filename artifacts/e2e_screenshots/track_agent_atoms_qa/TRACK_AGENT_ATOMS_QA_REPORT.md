# Agent-Native Track Operations QA

Date: 2026-11-28  
Build restarted with existing app bundle `index-F6zjEFqI.js`.  
Implementation modified: no.

## Defect-first verdict

No product defect found.

## Coverage

Workstation project `project_ccbb037d0c35` remained open in visible Chrome while operations were executed externally through the real CLI and real MCP stdio client. No manual reload was used for live-update checks.

### CLI `update-track` live atom

Passed. CLI exit `0` applied and persisted:

- name `Agent QA Lead`
- color `#22ccff`
- language `mixed`
- mute `true`, solo `false`
- volume `0.55`, pan `-0.25`
- MIDI channel `3`, program `18`
- OpenUtau singer `Agent Singer`, phonemizer `ZH`

Without reload, the visible first track showed the new name, cyan color `rgb(34, 204, 255)`, active mute button, volume `0.55`, pan `-0.25`, and OpenUtau mapping values. Backend state matched exactly.

Evidence: `02_cli_update_live.png`.

### Invalid patch validation/rollback

Passed. CLI patch containing valid-looking earlier fields plus invalid volume `1.5` rejected with exit `2` and actionable JSON:

`track volume must be normalized in [0, 1]`

No mutation occurred: name/color/volume remained `Agent QA Lead` / `#22ccff` / `0.55`; UI remained unchanged.

Evidence: `03_invalid_patch_no_mutation.png`, `track_agent_atoms_results.json`.

### CLI `duplicate-track` live atom

Passed. CLI exit `0` duplicated the rendered vocal track as `Agent QA Copy` and the new card appeared live without reload.

Backend proof:

- fresh track id `track_38e177640588`
- note ids disjoint from source
- note count preserved: `3`
- duplicate `render_path=null`
- duplicate `render_revision=0`
- duplicate `render_fingerprint=null`
- duplicate `created_by_job_id=null`
- source retained truthful render path/revision

Visible proof: source card retained `STALE RENDER`; duplicate card did not falsely inherit it.

Evidence: `04_cli_duplicate_live.png`.

### MCP `reorder-track` / `delete-track` live atoms

Passed through real MCP stdio client:

- reorder duplicate to index `0`: UI order changed live to `Agent QA Copy`, `Agent QA Lead`, ... and backend order matched exactly
- delete duplicate: card disappeared live without reload; backend count returned `5 → 4`; duplicate id absent

Evidence: `05_mcp_reorder_live.png`, `06_mcp_delete_live.png`.

### Reverse combination: MCP update/duplicate + CLI reorder/delete

Passed additionally:

- MCP `update_track` set pan `-0.2`, solo `true`, MIDI channel `4`, program `24`; UI/backend updated live
- MCP `duplicate_track` returned fresh id with `render_path=null`, `render_revision=0`, `created_by_job_id=null`
- CLI `reorder-track` moved `MCP QA Copy` to index `0` live
- CLI `delete-track` removed it live; backend count returned to `4`

Afterward the source mixer test values were restored to the prior QA state.

Evidence: `08_reverse_mcp_cli_atoms_live.png`, `track_agent_atoms_reverse_results.json`.

### Reload persistence

Passed. After browser reload, the track list still showed `Agent QA Lead` first, volume `0.55`, pan `-0.25`, backend exact color/language/mute/MIDI/OpenUtau mapping, and count `4`.

Evidence: `07_reload_persistence.png`.

### Health

- browser console errors/warnings: zero
- failed browser network responses: zero
- backend HTTP 500s: zero
- backend tracebacks: zero

## Harness note

The first harness attempt used a nonexistent Playwright `all_input_values()` helper before any mutation occurred. After correcting the harness helper, all product operations passed. This was not a product defect.
