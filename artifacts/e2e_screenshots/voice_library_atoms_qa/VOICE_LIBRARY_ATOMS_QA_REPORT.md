# Persistent Reference Voice Library Atoms QA

Date: 2026-11-28  
Project: `project_4ab2cba2f0f4`  
Implementation modified: no  
Backend restarted before test; browser already running current production frontend.

## Verdict

No product defects found. External CLI voice-library operations update the visible reference panel live through SSE, assignment cleanup is truthful, and the panel layout remains clean.

## Evidence

- CLI import of real local WAV succeeded as `voice_1813dbbdcbe0`, distinctive name `CLI Atom Voice 1795852898`, duration exactly `2.5s`.
- UI voice list updated without reload in effectively immediate polling latency (`14ms` measured after command completion/polling start).
- Visible dropdown assignment succeeded: backend `voice_id` and reference path exact.
- Undo assignment returned to inherited/default `zero-shot-reference`; redo restored `voice_1813dbbdcbe0`.
- CLI trim succeeded: new profile `voice_03d218160d31`, exact duration `1.5s`, source voice id exact, truthful short-reference warning metadata.
- Trimmed profile appeared live without reload (`10ms` measured).
- CLI rename to `CLI Atom Voice 1795852898 Renamed` appeared live without reload (`10ms` measured).
- Delete while assigned correctly failed with exit code 2 and actionable error: voice in use; pass `--unassign`.
- Delete with `--unassign` succeeded; option disappeared live, visible select returned to empty, backend `voice_id=''` and `reference_voice_path=null`.
- Reload persistence passed: assignment remained cleared and deleted voice absent.
- Unsupported `.txt` import failed with exit code 2 and actionable `unsupported reference voice format: .txt`.
- Console errors/warnings: zero. Failed browser network responses: zero.
- Adversarial screenshot review: no overlap, dead controls, missing metadata, or broken reference-panel layout. Short-reference warning is explicit and truthful.

## Artifacts

- `01_cli_import_live.png`
- `02_cli_trim_live.png`
- `03_cli_rename_live.png`
- `04_cli_delete_unassign_live.png`
- `voice_atoms_results.json`
