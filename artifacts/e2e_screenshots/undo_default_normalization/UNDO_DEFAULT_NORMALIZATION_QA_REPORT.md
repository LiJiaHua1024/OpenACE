# Undo Default Normalization QA

Focused visible-Chrome regression after backend restart/cache-bust. Corrected run explicitly verified `Snap Grid QA` was open because pinned `FolderQA Beta` can boot first. Implementation was not modified.

## Corrected-run assertions

- **Add new track after save/SSE echo:** failed — `track_e64eadbd-f32` / `Vocal 2` was created and saved, but Undo was disabled after waiting through the echo, so it could not be removed in one undo. Redo was also disabled. The later “track still present” state is not evidence of undo/redo success.
- **Create piano note after save/SSE echo:** passed — exact note `note_0cd69e45-4d3`, `start_ticks=1200`, `duration_ticks=60`, pitch `70`, `pitch_snap_first=true`; Undo remained enabled, one undo removed it, redo restored the same note exactly.
- **Create breath after save/SSE echo:** passed — exact breath `br_bf282e8e`, `start_ticks=1170`, `duration_ticks=120`, intensity `1.0`, timbre `natural`; Undo remained enabled, one undo removed it, redo restored it exactly.
- **Ordinary arrangement clip editing:** passed — at 1/32, clip moved exact `0 → 60`; undo restored `0`.
- **Console/page/network:** passed — no errors or failed responses.

## Root-cause evidence for remaining track failure

A request/response probe captured the actual PUT and backend GET. The local newly added track key order is:

`id,name,type,color,voice_id,reference_voice_path,language,notes,clips,automation,breaths,mute,solo,volume,pan,render_path,render_revision`

The backend/model key order inserts defaulted optional fields in schema positions:

`...,reference_voice_path,openutau_singer,openutau_phonemizer,language,...,pan,midi_channel,midi_program,created_by_job_id,render_path,render_revision,render_fingerprint`

Although the new normalization fills missing values, it appends missing keys at the end. Since `undoSemanticSignature` ultimately uses order-sensitive `JSON.stringify`, semantically equivalent objects can still produce different strings. This is consistent with the observed track-only failure. Numeric `int/float` differences seen in Python are not sufficient explanation because JavaScript numbers stringify equivalently.

## Caveat

The first automated pass initially interacted with pinned `FolderQA Beta` because project selection had not settled; that pass was discarded. The corrected run explicitly verified the target project before acting and is the evidence above.

## Artifacts

- `undo_default_normalization_corrected_results.json`
- `track_signature_probe.json`
- screenshots `20_corrected_initial.png` through `30_clip_drag.png`
