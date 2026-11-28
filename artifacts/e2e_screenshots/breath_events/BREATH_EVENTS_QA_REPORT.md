# Breath events QA report

Date: 2026-11-27
Branch: `devin/1795696369-dynamic-expression`
Mode: visible Chrome, fixture backend (`OPENACE_CI_SYNTH_FIXTURE=1`).

## Result

All requested breath-event checks passed.

Harness transparency: the first automation script crashed after the successful render because of a duplicate keyword in the test harness while recording the diagnostic result. This was not an application defect; the same live browser session was continued to complete diagnostic inspection, right-click deletion, and health checks. The initial audio-analysis plot also used an incorrect assumed breath interval; it was corrected to the backend-event interval before writing this report.

## Fixture

Generated `aspiration_reference.wav` outside the implementation:

- 24 kHz mono WAV
- low harmonic tone in the opening section
- strong deterministic broad-band noise/aspiration from about 0.55–1.25s
- uploaded through the visible **Upload reference voice** control/file chooser

## UI editing verification

Passed:

- custom reference uploaded and displayed as `custom reference loaded`
- one pencil-drawn note created at `(start=0, duration=480, pitch=60)`
- empty click in **Breath & Phoneme** added breath `(start=480, duration=120)`
- center drag moved it to `(start=600, duration=120)`
- right-edge drag resized it to `(start=600, duration=240)`
- backend state persisted after every edit

At 120 BPM/480 PPQ, final event timing is:

- start: 600 ticks = 0.625s
- end: 840 ticks = 0.875s

## Render/provenance verification

Visible **Render vocal** click returned HTTP 200. Job `job_0b9390fa2c4c` completed with message:

`completed with 1 real-donor breath overlay(s)`

The diagnostic image was visually inspected and includes:

`Breath events real donor-noise overlays (post-render DSP, not neural conditioning)`

## Audio analysis

Measured output `breath_render_output.wav`:

- length: 1.0s at 24kHz
- harmonic fixture note occupies 0–0.5s
- pre-breath interval 0.5–0.625s RMS: `0.0`
- breath interval 0.625–0.875s RMS: `0.0339277722`
- breath interval high-band (≥1500Hz) metric: `1.1927334541`
- harmonic-note high-band metric: `0.0003462252`
- high-band ratio breath/harmonic: about `3445×`
- post-breath interval 0.875–1.0s RMS: `0.0`

This objectively confirms real nonzero energy was inserted exactly in the authored breath interval rather than the harmonic note or surrounding silence.

## Delete/health verification

- right-click on the breath block deleted it
- backend `breaths` became `[]`
- no console errors
- no network failures

## Evidence

- `aspiration_reference.wav`
- `breath_render_output.wav`
- `audio_analysis.png`
- `diagnostic.png` / `diagnostic_2x.png`
- `01_reference_uploaded.png`
- `02_breath_added.png`
- `03_breath_moved.png`
- `04_breath_resized.png`
- `05_render_completed.png`
- `06_breath_deleted.png`
- `07_render_job_panel.png`
- `breath_results.json`
