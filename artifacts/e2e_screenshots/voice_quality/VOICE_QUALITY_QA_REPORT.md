# Zero-shot reference voice quality QA

Date: 2025-11-27  
Browser: real visible Chrome through Playwright/CDP  
Viewport: exactly `1272x837`  
Frontend: rebuilt/cache-busted, bundle `index-Ccw_biS1.js`, CSS `index-BW9XciD7.css`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1`  
Project: `project_5bb00b345fd1` / `Voice Quality QA`  
No repo code modified.

## Verdict

The requested voice-quality feature passes end to end for clean, short, clipped, silent, too-short, and corrupt fixtures. Clean audio metrics are truthful, warning text is specific, valid warning files still upload/assign, invalid files reject without library growth, native audition playback progresses, rename/reload/delete/unassign regressions pass, and the right-panel layout remains contained.

No implementation defect was confirmed. One minor UX observation: invalid-upload errors are displayed as raw JSON strings such as `{"detail":"reference voice is too short"}` rather than polished human-readable text.

## Exact evidence

### Clean 3s nonzero reference

Fixture: 3s mono 48kHz sine-like nonzero WAV, nominal peak `0.4`.

Backend measurements:

- duration `3.0s`, sample rate `48000`, channels `1`
- peak `0.40002`
- clipping ratio `0.0`
- RMS `-10.97dBFS`
- silence ratio `0.0`
- voiced `3.0s`
- warnings: `[]`

UI showed `peak 0.40 · RMS -11.0dB · voiced 3.0s` and no warnings.

Native audio control:

- src `/api/voices/voice_f13a7ab5e119/audio`
- real click on the native play control progressed from `0` to `0.821874s`
- `paused=false`, `readyState=4`

### Short valid reference

1s nonzero valid WAV uploaded and assigned without hard failure.

- peak `0.40002`
- RMS `-10.97dBFS`
- voiced `1.0s`
- exact warning: `reference is shorter than 2s; zero-shot timbre may be unstable`

### Clipped valid reference

3s clipped WAV uploaded and assigned without hard failure.

- peak `1.0`
- clipping ratio `0.494167`
- RMS `-1.69dBFS`
- voiced `3.0s`
- exact warning: `reference appears clipped; use a cleaner non-distorted vocal take`

### Silent valid-duration reference

3s silent WAV uploaded and assigned without hard failure.

- peak `0.0`
- RMS `-180.0dBFS`
- silence ratio `1.0`
- voiced `0.0s`
- exact warnings:
  - `reference is mostly silence or contains too little usable voiced material`
  - `reference level is very low; increase input gain without clipping`

### Too-short and corrupt rejection

- 0.03s WAV: rejected; voice count `7 → 7`; error `{"detail":"reference voice is too short"}`
- corrupt text masquerading as WAV: rejected; voice count `7 → 7`; error `{"detail":"reference voice is not readable audio"}`

The two resulting 422 responses and browser resource errors are expected rejection evidence, not unexpected runtime failures. There were no other console or network errors.

### Layout

At `1272x837`:

- voice quality block `963→1250`, inside right panel `950→1272`
- audio element width `287px`, contained
- no horizontal overflow in the right panel
- amber warnings visibly contained without overlap

### Rename / SSE / reload / delete regression

- Clean voice assigned through the visible select.
- Browser prompt rename to `QA Renamed Reference` succeeded.
- Backend, voice card, and selected option all showed the new name.
- After full reload and project reselection, the renamed voice still showed correctly and list persistence was exact.
- Delete confirmation succeeded.
- Backend voice removed; list no longer contained it.
- Project track unassigned exactly: `voice_id=""`, `reference_voice_path=null`.
- UI returned to `Zero-shot reference slot`.

## Files

- `voice_quality_results.json` — machine-readable evidence
- `clean_ref.wav`, `clipped_ref.wav`, `silent_ref.wav`, `short_ref.wav`, `too_short_ref.wav`, `corrupt_ref.wav` — fixtures
- `01_clean_metrics.png`
- `02_clean_audio_playing.png`
- `03_short_warning.png`
- `04_clipped_warning.png`
- `05_silent_warning.png`
- `06_invalid_rejections.png`
- `07_renamed.png`
- `08_after_delete.png`

## Readable-error UX retest — 2025-11-27

Frontend rebuilt/cache-busted (`index-DtX-f3GA.js`) and backend restarted. Fresh project `project_a7380794b127`.

### Result: passed

Invalid voice-upload errors are now polished plain text:

- too-short fixture: `reference voice is too short`
- corrupt fixture: `reference voice is not readable audio`
- neither string contains JSON braces or the `detail` key
- both files still rejected with voice-library count unchanged

Regressions passed:

- clean upload metrics exact: `peak 0.40 · RMS -11.0dB · voiced 3.0s`, no warnings
- native audio progressed to `0.618509s`, `readyState=4`
- short warning exact: `reference is shorter than 2s; zero-shot timbre may be unstable`
- quality block/audio remained inside right panel with no horizontal overflow
- console/network contained only the two expected 422 resource entries for intentional invalid uploads; no unexpected errors

Evidence merged into `voice_quality_results.json` under `readable_error_retest`. Screenshots `09_ux_clean_regression.png`, `10_ux_short_warning.png`, `11_ux_too_short_error.png`, and `11_ux_corrupt_error.png`.
