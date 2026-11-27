# Voice Library QA Report

Date: 2026-11-27
Scope: Iteration 37 persistent zero-shot reference voice library in real visible Chrome with fixture backend.

## Verdict

All requested functional checks passed. No implementation defect was confirmed. The Voice panel remains compact and professional at the exact 1272×837 viewport.

## Evidence summary

- Generated two valid 1.2s mono 44.1kHz WAV fixtures.
- Uploaded alpha through the visible Voice-panel **Upload** control.
- `/api/voices` metadata reported duration `1.2s`, sample rate `44100`, channels `1`, size `105884` bytes.
- Selecting/uploading a library voice persisted both exact fields on the track:
  - `voice_id`
  - `reference_voice_path`
- After browser reload/reopen, the beta assignment still matched exactly:
  - `voice_id=voice_7239c0fa3cbc`
  - `reference_voice_path=/home/ubuntu/repos/OpenACE/data/voices/voice_7239c0fa3cbc_beta_voice.wav`
  - visible select value also matched, and Rename was enabled.
- Rename through the visible control and browser prompt persisted as **Studio Voice Alpha** (`03_after_rename.png`).
- Safe default API DELETE probe against an in-use voice returned HTTP `409` with:
  - `voice is in use by project 'Voice Library QA' track 'Lead Vocal'`
- Visible Delete opened the expected confirmation. Accepting it with a real mouse click removed metadata/file and cleared the matching track assignment without a manual reload (`04_after_delete_no_reload.png`).
- Remaining beta voice was reassigned through the visible select.
- Rendering with the assigned library voice completed:
  - job `job_a8e9303e766e`
  - status `completed`
  - output `/home/ubuntu/repos/OpenACE/data/renders/project_a1d17f7a7aad/job_a8e9303e766e/vocal.wav`
- Final exact-layout pass at viewport `1272×837` showed:
  - right panel `x=950,w=322`, fully inside viewport
  - voice card/select/actions visible
  - Upload/Rename/Delete buttons on one row with no overlap
- No browser console errors or network failures were observed in the final instrumented pass.

## Harness transparency

Two harness mistakes occurred and were corrected; neither is an application defect:

1. The first automation pass treated the pre-existing default string `zero-shot-reference` as proof of assignment and reloaded before the debounced project save. The corrected pass waited for exact equality with the uploaded `voice_*` id/path.
2. The dialog handler incorrectly passed a boolean to Playwright `accept()`. The visible delete confirmation was then accepted with a real mouse click, which also provided direct visual confirmation of the no-reload unassignment behavior.

## Files

- `voice_library_results.json` — machine-readable results
- `01_first_voice_uploaded.png` — first voice visible in panel
- `02_reload_persistence.png` — initial reload pass
- `03_after_rename.png` — renamed voice evidence
- `04_after_delete_no_reload.png` — assignment cleared after confirmed delete without reload
- `05_render_complete.png` — completed render jobs and diagnostic
- `06_voice_panel.png` — isolated voice panel crop
- `07_beta_reload_persistence.png` — beta persistence after reload
- `08_exact_1272x837_layout.png` — exact requested viewport layout
- `alpha_voice.wav`, `beta_voice.wav` — generated fixtures
