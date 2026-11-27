# ASR import placeholder-fix recheck

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend started with `OPENACE_CI_SYNTH_FIXTURE=1 OPENACE_WHISPER_MODEL=tiny`, frontend rebuilt.

## Result

The placeholder fix passed focused recheck.

## Verified

- Real UI audio import was repeated for `external/SoulX-Singer/example/audio/en_prompt.mp3`.
- `Transcribing audio…` busy label appeared during import.
- Settled imported project: `project_ffbcdd982db4`.
- Track language: English.
- Backend note count: 44.
- Real lyric-bearing notes: 11.
- Real lyric text remains visible in the piano roll.
- Empty lyrics are now visually blank.
- Pixel verification on the settled imported piano roll:
  - `Never`: 19 white text pixels sampled
  - `mind,`: 21 white text pixels sampled
  - `I'll find`: 18 white text pixels sampled
  - sampled empty-lyric notes: 0 white text pixels each
- No visible em-dash placeholder notes remain in the after-import screenshot.
- No console errors or network failures.

Harness transparency: the first recheck read the previous same-title imported project before the new request finished. I corrected this by validating the settled newly imported project (`project_ffbcdd982db4`) after the UI switched. This was a test race, not an application defect.

## Evidence

- `fix_01_before_import.png`
- `fix_02_during_transcribing.png`
- `fix_03_after_import.png`
- `fix_04_after_import_settled.png` — settled project evidence
- `evidence_asr_import_fix_montage.png`
- `asr_import_fix_results.json`
