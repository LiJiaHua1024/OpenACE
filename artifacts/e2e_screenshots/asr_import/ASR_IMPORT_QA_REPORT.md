# ASR audio import QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend started with `OPENACE_CI_SYNTH_FIXTURE=1 OPENACE_WHISPER_MODEL=tiny`, frontend rebuilt.

## Result

The ASR import pipeline is functional, but the strict no-placeholder requirement is **not fully met**.

## Passed

- `Import audio` accepted `external/SoulX-Singer/example/audio/en_prompt.mp3` through the real UI file control.
- Busy label visibly changed to `Transcribing audio…` during import and input was disabled.
- Import completed in about `5.58s` and label returned to `Import audio`.
- New project `en_prompt` / `project_faec1b98647f` opened.
- Track language is visibly and persistently English (`vocal · en · 44 notes`).
- Backend contains 44 extracted notes.
- 11 notes have real non-placeholder lyric text, including:
  - `Never`
  - `mind,`
  - `I'll find`
  - `someone like`
  - `you`
  - `How`
  - `is`
  - `more`
  - `nothing`
- Piano roll visibly rendered many notes; 5,293 colored note pixels were detected.
- No console errors or network failures occurred.

## Defect / unmet criterion

Although stored lyric values contain no literal `la`, `啦`, or hyphen placeholder strings, **33 of 44 notes have empty lyrics**. The piano-roll renderer displays empty lyrics as a visible em dash (`—`), and the after-import screenshot clearly shows multiple dash placeholder notes.

Therefore the user's visual requirement “no `la`/`啦`/hyphen placeholders appear” is not strictly satisfied. Either unaligned notes need a cleaner empty presentation, or the import needs a different policy for unaligned notes.

## Evidence

- `01_before_import.png`
- `02_during_transcribing.png`
- `03_after_import.png`
- `evidence_asr_import_montage.png`
- `asr_import_results.json`
