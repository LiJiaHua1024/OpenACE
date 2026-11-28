# Truthful SVC Key/Transposition QA

Date: 2026-11-28  
Project: `project_68e4581f3701`  
Frontend build: `index-B0hguVu8.js`  
Backend: restarted with CI fixture synthesis  
Implementation modified: no

## Summary

The transposition feature itself passed deeply in UI, fixture DSP, metadata/provenance, validation, CLI, MCP, reload persistence, and clip integration. One serious incidental backend reliability defect was reproduced: during SVC completion/project persistence, a concurrent project read transiently returned HTTP 500 because the project JSON was read while partially written (`Invalid JSON: trailing characters`). The project later became readable and the UI recovered, but this violates clean-network expectations and can surface as intermittent workstation/API failure.

## Defect

### P1/P2 — transient HTTP 500 from non-atomic project JSON writes during SVC completion

Evidence: `project_read_500_race_excerpt.log`

- `GET /api/projects/project_68e4581f3701` returned 500 while the first SVC job was completing.
- Pydantic error: `Invalid JSON: trailing characters at line 351 column 1`.
- Root code path observed: `Project.save` writes directly with `path.write_text(...)`; concurrent readers can observe a partial/torn file.
- This is not specific to transposition mathematically, but the new SVC completion path writes project state and makes it easy to hit in normal use.

## Passed assertions

### UI control and browser conversions

- Control visible with exact options: Preserve source key, Auto-match reference voice, Manual semitone shift.
- Manual numeric input accepted typed `-3` visibly.
- Preserve UI conversion completed:
  - job `job_2f846ce5358b`
  - `pitch_shift=0`, `auto_shift=false`
- Manual UI conversion completed:
  - job `job_437946095819`
  - `pitch_shift=-3`, `auto_shift=false`
- Auto UI conversion completed:
  - job `job_0295c41254d2`
  - `pitch_shift=0`, `auto_shift=true`
- Project metadata `svc_conversions` carried the same exact mode fields.
- Arrangement integration exact for every successful conversion: one audio clip, clip path exactly matching job output, duration `1800` ticks at project timing.
- After external CLI/MCP conversions, browser DOM track count matched backend track count (`14`) without manual reload, indicating live project refresh.
- Reload persistence passed: all conversion metadata/tracks/clips/reference voice remained.
- Undo/redo smoke did not corrupt project readability, conversion metadata, or track count. Note: render completion is not a meaningful user-edit undo transaction, so this was only an integrity regression check.
- No reference-panel/SVC-control visual overlap or broken layout found in reviewed screenshots.

### Quantitative fixture DSP analysis

Source median F0: `329.774 Hz`; reference median F0: `91.401 Hz`.

| Mode | Median output F0 | Measured shift | Expected/interpretation |
|---|---:|---:|---|
| Preserve | `329.790 Hz` | `+0.0008 st` | exact key preservation |
| Manual `-3` | `277.408 Hz` | `-2.9936 st` | truthful -3 semitone shift |
| Auto | `92.637 Hz` | `-21.9819 st` | matches reference/source median-key calculation, approximately -22 st |
| MCP manual `+1` | `349.315 Hz` | `+0.9966 st` | truthful +1 semitone shift |
| CLI manual `+2` | `370.259 Hz` | `+2.0047 st` | truthful +2 semitone shift |

Spectral centroid moved in the same direction: manual `-3` median centroid ratio `0.832x`; auto `0.303x`. Durations remained exactly `2.5s` at 24kHz.

### Validation and exact invocation

- API `pitch_shift=2&auto_shift=true`: HTTP 422, actionable conflict message.
- API `pitch_shift=-25` and `+25`: HTTP 422, actionable range message.
- CLI same manual+auto conflict: exit code 2 with actionable JSON error.
- CLI successful exact `--pitch-shift 2` conversion completed in fixture mode: `job_beddcfd04ba3`, `pitch_shift=2`, `auto_shift=false`.
- MCP successful exact `pitch_shift=1, auto_shift=false` conversion completed: `job_6f0ad252b1b6`.
- Upstream SoulX command construction probe passed:
  - manual `-3`: exact `--pitch_shift -3`, no `--auto_shift`
  - auto: exact `--pitch_shift 0 --auto_shift`
  - preserve: exact `--pitch_shift 0`, no `--auto_shift`
  - flags match upstream `cli/inference_svc.py` argument names.

## Caveats / incomplete coverage

- Real SoulX model execution was not possible because the local checkpoint is absent; fixture mode and command-construction probing were used instead. This is expected in the current environment, not a product failure.
- The first CLI success attempt accidentally lacked fixture environment variables and predictably failed with the missing SoulX checkpoint; rerunning with fixture env completed. This was a harness invocation issue.
- Subsequent browser console/error arrays were clean, but overall clean-network cannot be claimed because of the transient project-read HTTP 500 above.

## Artifacts

- `01_svc_transpose_control.png`
- `03_manual_minus3_typed.png`
- `03_manual_minus3_complete.png`
- `04_auto_complete.png`
- `05_reload_undo_redo.png`
- `06_external_cli_mcp_live_tracklist.png`
- `svc_transpose_continue_results.json`
- `svc_final_browser_state.json`
- `svc_audio_analysis.json`
- `svc_validation_cli_mcp_results.json`
- `svc_cli_plus2_fixture.json`
- `svc_upstream_flags_probe.json`
- `clip_integration.json`
- `project_read_500_race_excerpt.log`
