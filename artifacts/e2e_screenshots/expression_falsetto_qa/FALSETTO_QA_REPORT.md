# Falsetto expression QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, driven through Playwright/CDP against a fixture backend restarted from the current working tree.

## Result

The requested user-facing closed loop completed. No application defect was found in this QA pass.

## UI/provenance evidence

- Positive test project: `project_a4cf2bb4a39d`.
- Fresh two-note vocal project contained exactly `(0,480,C4)` and `(480,480,C4)`.
- Neutral fixture render completed first with empty lanes.
- Falsetto line persisted exactly as `(0 ticks, 0.5) -> (960 ticks, 1.0)`.
- One-step undo removed the Falsetto line; redo restored both endpoints exactly.
- After browser reload, the same exact Falsetto curve remained visible and persisted.
- Render job completed with visible/backend text: `completed with Falsetto post-processing`.
- Diagnostic provenance visibly includes `Falsetto lane spectral-tilt DSP (not neural conditioning)`.
- Playback advanced from `00:00.00` to about `00:01.10` without deadlock.
- No browser console errors or network failures were captured.

## Audio measurements

Measurement window: late high-automation region, 0.58–0.92s. Filters mirror the implementation intent using zero-phase filtering: chest <=650Hz and upper residue >2.2kHz.

| Render | <=650Hz chest ratio | upper/chest tilt ratio | Dominant F0 | Peak |
|---|---:|---:|---:|---:|
| Positive Falsetto | 0.802× | 1.148× | 260.87Hz, unchanged | 0.392 |
| Negative Falsetto | 1.177× | 0.911× | 260.87Hz, unchanged | 0.475 |

Interpretation:

- Positive values clearly thin the chest band and increase the upper/chest spectral-tilt ratio.
- Negative values increase chest weight and decrease the upper/chest spectral-tilt ratio, as expected for a chestier/pressed tilt.
- Dominant pitch remains exactly the original note estimate; no F0 shift was detected.
- The fixture source has essentially no pre-existing >2.2kHz harmonic residue (`upper RMS ≈ 0.000695` versus chest RMS `≈0.2186`), so absolute reinforcement of real upper residue is not meaningfully measurable in fixture mode. The spectral-tilt ratio still verifies the intended direction.

## Important artifacts

- `evidence_falsetto_audio_analysis.png` — chest ratio, tilt ratio, and F0 comparison.
- `evidence_diagnostic_provenance_crop.png` — diagnostic provenance wording.
- `05_falsetto_job_card.png` — visible job completion text.
- `04_falsetto_curve_after_reload.png` — curve persistence after reload.
- `06_playback_after_render.png` — playback after render.
- `07_negative_falsetto_curve.png` and `08_negative_falsetto_job.png` — negative-curve supplemental evidence.
- `falsetto_results.json` — machine-readable assertions.
- Rendered WAVs: `neutral_render.wav`, `falsetto_render.wav`, `negative_neutral_render.wav`, `negative_falsetto_render.wav`.
