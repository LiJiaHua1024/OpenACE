# Voice library SSE addendum

Date: 2026-11-27
Scope: targeted regression for external/API voice-library changes refreshing the open Voice panel without manual reload.

## Result

Passed.

## Checks

- With the app already open, direct backend API `POST /api/voices` created `gamma_api.wav`.
- The new voice appeared in `.voice-select` without reloading the page.
- Normal visible assignment through the select still persisted exact `voice_id` and `reference_voice_path`.
- Direct backend API rename to **External Renamed** refreshed both the selected voice card and select option without reload.
- Direct backend API `DELETE ...?unassign=true` removed the voice, deleted the file, cleared the track assignment, and reset the panel to **Zero-shot reference slot** without reload.
- Remaining options contained only the pre-existing beta voice; no duplicate or stale gamma/External Renamed entries remained.
- No console errors or network failures.

## Evidence

- `sse_01_external_create.png`
- `sse_02_external_rename.png`
- `sse_03_external_delete.png`
- `voice_sse_results.json`
