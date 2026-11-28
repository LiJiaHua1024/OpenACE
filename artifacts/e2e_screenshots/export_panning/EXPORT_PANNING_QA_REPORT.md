# Export Panning QA

Visible Chrome validation after frontend rebuild/cache-bust and backend restart. Project `Export Panning QA` used three real fixture-backed clips: mono left vocal hard-left, independent mono right vocal hard-right, and a stereo center clip whose left/right channels were distinct real fixture audio. Repo code was not modified.

## Assertions

- **STEMS download:** passed — browser download `Export Panning QA_stems.zip`, `478,780` bytes.
- **Master WAV download:** passed — browser download `Export Panning QA.wav`, `288,044` bytes.
- **Hard-left panning:** passed — `01_Left_Vocal.wav` RMS L `0.216930`, RMS R exactly `0.0`; left channel matched the source within `5.29e-15`.
- **Hard-right panning:** passed — `02_Right_Vocal.wav` RMS L exactly `0.0`, RMS R `0.217007`; right channel matched the independent source exactly within PCM precision.
- **Center stereo regression:** passed — `03_Center_Stereo.wav` remained non-silent and matched the stereo source within `5.29e-15`; L/R RMS `0.216930`/`0.217007`.
- **Master panning:** passed — master was non-silent; left channel correlated with source A at `0.99999985`, right with source B at `0.99999975`, while cross-source correlations were about `-0.00065`.
- **Manifest/zip shape:** passed — manifest plus three stem WAVs.
- **Layout/console/network:** passed — right panel `clientWidth == scrollWidth == 311`, no horizontal page overflow, no console/page/network errors.
- **Prior stems temp-directory residue:** not reproduced — no `Export Panning QA_stems/` sibling directory remained in `data/exports`.

## Caveats

- Master loudness scaling prevents direct absolute amplitude comparison, so master correctness was assessed by channel waveform-shape correlation.
- Center stereo input was a test composite made from two distinct real rendered fixture vocal WAVs; no synthetic placeholder audio was used.

## Artifacts

- `panned_stems.zip`, `panned_master.wav`, `panned_stems_manifest.json`
- `pan_audio_analysis.json`, `pan_browser_results.json`
- `00_pan_export_ui.png`, `01_after_pan_exports.png`, `02_panning_waveforms.png`
