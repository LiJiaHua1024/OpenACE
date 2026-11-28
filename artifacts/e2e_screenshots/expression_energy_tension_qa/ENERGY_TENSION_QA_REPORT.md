# Energy/Tension expression QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, driven through Playwright/CDP against a fixture backend restarted from the current working tree.

## Result

The requested user-facing closed loop completed. No application defect was found in this QA pass.

## Evidence summary

- Fresh two-note vocal project: `project_4a425419eadb`.
- Neutral fixture render completed first with empty Energy/Tension lanes.
- Energy line persisted exactly as `(0 ticks, 0.5) -> (960 ticks, 1.0)`.
- Tension line persisted exactly as `(0 ticks, 0.5) -> (960 ticks, 1.0)`.
- One-step undo removed the Tension line; redo restored both endpoints exactly.
- Automation render completed with visible/backend text: `completed with Energy/Tension post-processing`.
- Diagnostic provenance visibly includes:
  - `Energy lane harmonic-density DSP (not neural conditioning)`
  - `Tension lane presence-band DSP (not neural conditioning)`
- Playback advanced (`00:00.00` to about `00:01.09`/`00:01.13`) without deadlock.
- Erased/restored curve state survived autosave; after browser reload the exact Energy curve was still visible and persisted.
- No browser console errors or network failures were captured during the primary flow.

## Audio measurements

Measurements compare the rendered files against the neutral render using zero-phase time-domain filtering. The late window is 0.58–0.92s, where the automation is high.

| Render | Late total RMS ratio | Late 0.9–5.5k RMS ratio | Late residual RMS | Peak |
|---|---:|---:|---:|---:|
| Energy only | 2.109× | 3.394× | 0.2660 | 0.865 |
| Tension only | 1.020× | 1.202× | 0.0105 | 0.417 |
| Combined positive | 2.149× | 4.677× | 0.2761 | 0.885 |

Interpretation: Energy-only strongly increases total/harmonic energy. Tension-only selectively raises the presence band while leaving total RMS nearly unchanged. The combined render is strongest and remains peak-protected below 0.98.

Supplemental negative-curve check on project `project_33f3e6725e29`:

- Curves persisted exactly from `(0,0.5)` to `(960,0.0)` for both lanes.
- Job completed with `Energy/Tension post-processing`.
- Late total RMS ratio: `0.981×` (small because the fixture vocal has little high-band energy).
- Late presence-band ratio: `0.799×`, confirming audible attenuation in the intended band.
- Peak: `0.396`, no clipping.

## Isolation method

Energy-only and Tension-only renders were produced through the visible UI by using the lane erase tool on one lane at a time. Immediate backend reads sometimes raced the frontend autosave debounce; delayed verification and the job messages confirmed correct lane isolation. This was a test-timing issue, not an application failure.

## Important artifacts

- `evidence_isolated_audio_comparison.png` — positive lane-isolated RMS/presence/residual measurements.
- `evidence_negative_audio_comparison.png` — negative-curve attenuation evidence.
- `evidence_audio_comparison.png` — combined positive waveform/residual comparison.
- `evidence_diagnostic_provenance_crop.png` — diagnostic provenance wording.
- `06_energy_tension_job_card.png` — visible job completion text.
- `07_playback_after_render.png` — playback after render.
- `14_energy_curve_after_reload.png` — persisted Energy curve after reload.
- `energy_tension_results.json` — machine-readable assertions.
