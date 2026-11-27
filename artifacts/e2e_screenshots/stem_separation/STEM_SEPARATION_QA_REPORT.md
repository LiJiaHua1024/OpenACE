# Stem separation QA report

Date: 2026-11-27
Scope: Iteration 39 local stem separation/dry-wet arrangement workflow in real visible Chrome with explicit CI frequency-split fixture backend.

## Verdict

All requested checks passed. No implementation defect was confirmed.

## Test flow

- Generated `mixed_source.wav`: 2 seconds combining a 180 Hz low instrumental tone and a 900 Hz high vocal-like tone.
- Created a visible new project and uploaded the mixture through **Upload vocal/audio source**.
- Clicked **Separate vocal/instrumental** visibly.
- Waited for job completion and inspected the already-open UI without manual reload.
- Exercised mute, master export, arrangement drag, and edge trim.

## Results

- Job `job_ec926df50e1b` completed in mode `separate` with message `completed; added separated vocal/instrumental tracks for mixed_source`.
- Both tracks appeared live without reload:
  - `Separated vocal — mixed_source`
  - `Separated instrumental — mixed_source`
- Both arrangement clips appeared at tick 0 with visible waveform content.
- Backend provenance recorded `metadata['stem_separations']` with source, track ids, output paths, and engine `explicit CI separation fixture`.
- Both stem output files existed; initial clip durations were `1920` ticks each.
- Diagnostic existed and was copied to `separation_diagnostic.png`.
- Visible mute on the vocal stem persisted in backend state.
- Master exports returned HTTP 200 before/after mute.
- Quantitative dry/wet evidence: master high/low spectral ratio changed from `0.74930` before vocal mute to `0.000114` after vocal mute (about a 6565× reduction, ~99.985%; high stem effectively removed). Because loudness normalization applies global gain, this spectral-ratio comparison is the meaningful evidence.
- Arrangement interactions persisted:
  - vocal clip drag: start `0→120` ticks
  - right-edge trim: duration `1920→1680` ticks
- API job mode is visible as `separate`; CLI `separate --help` exits 0; `separate_stems` is registered in `openace/mcp_server.py` (script-only visibility checks).
- No console errors or network failures.
- Final 1272×837 layout remained professional: track cards, mute state, arrangement clips, ACE-Step panel, jobs and diagnostic layout were readable with no overlap.

## Harness transparency

Two harness issues were corrected; neither is an application defect:

1. The first mute selector used text matching, but track names live inside input values rather than text nodes. The corrected harness selected the second track card directly.
2. The first trim drag used a right-edge coordinate that did not account for the prior successful horizontal drag. A corrected edge hit trimmed the clip successfully.

## Evidence

- `stem_separation_results.json` — machine-readable checks/results
- `mixed_source.wav` — generated mixture
- `master_before_mute.wav`
- `master_after_vocal_mute.wav`
- `separation_diagnostic.png`
- `01_separated_tracks_no_reload.png`
- `02_vocal_stem_muted.png`
- `03_clip_dragged_trimmed.png`
- `04_final_layout.png`
