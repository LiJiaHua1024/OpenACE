# Direct Audio Clip Import QA Report

Focused visible-Chrome acceptance with fixture backend, rebuilt frontend, exact 1272x837 viewport.

## Passing checks

- Real ruler click set a nonzero playhead; imported clip started at tick 1011.
- Valid 1.0s WAV imported through the visible `Import audio as clip at playhead` control.
- New `Audio — clipimport` audio track appeared live without reload; selector/state not manually refreshed.
- Backend duration was 960 ticks as expected at 120 BPM/480 PPQ.
- Canvas scan matched expected visual geometry: x 301 vs expected 299.9; width 223 vs expected 224 px.
- Drag persisted start 1011 -> 1371 ticks. Right-edge trim persisted duration 960 -> 720 ticks.
- Reload persistence passed with identical final start/duration.
- Visible WAV master export included the clip: RMS before 0.0, inside 0.17629 at 48kHz.
- Corrupt audio was rejected with explicit `invalid audio clip` detail; no track/clip created and the temporary upload was removed.
- Layout remained compact/professional at 1272x837.
- No unexpected console/network errors. The 422 console entry was expected from the intentional negative test; export abort/SSE aborts were download/reload artifacts.

## Implementation defect

**Imported uploaded clips never produce a real waveform in the arrangement.** The clip remains stuck at `analyzing waveform…` after waiting and after reload. Evidence: `waveform_missing_zoom.png`. The imported path is under `data/uploads`, but frontend `renderFileUrl` only maps `/renders/` paths, so waveform/playback URL resolution returns null for these imported clips. Backend master export is unaffected because it reads the local path directly.

## Minor UX caveat

Invalid-audio feedback is clear but displayed as raw JSON/detail text with a full local path rather than a polished user-facing message.

## Uploads/renderFileUrl fix recheck

After rebuilding, restarting the backend, verifying `/uploads/vocal.wav` returned 200 before browser testing, and cache-busting the page, the exact defect path passed:

- Direct uploaded clip URL returned HTTP 200, `audio/x-wav`, 88244 bytes.
- Upload resource responses in browser were HTTP 200.
- Canvas bright-pixel evidence increased from broken baseline 38/3 interior to 790/332 interior; clip visibly shows real peaks rather than `analyzing waveform…`.
- Visible transport play loaded `/uploads/clip_1aa009c0549a_clipimport.wav` (resource entry encodedBodySize 88244), entered playing state, and advanced to `00:01.28` after 1.3s.
- Reload preserved clip start/duration and waveform peaks returned after reload.
- Layout remained professional; no console errors or unexpected network failures. Only deliberate reload SSE aborts occurred.

Artifacts: `fix_waveform_peaks.png`, `fix_waveform_peaks_zoom.png`, `fix_reload_waveform_layout.png`, `audio_clip_import_fix_results.json`.

Harness note: an earlier recheck hit a stale backend process that still returned 404; the server was force-restarted and `/uploads` was verified 200 before the valid recorded run.

## Selected-track target semantics recheck

Rebuilt/cache-busted visible-Chrome regression passed:

- Existing project began with 2 tracks: vocal plus `Audio — clipimport` with 1 clip.
- After visibly selecting the existing audio track and importing `targetsem.wav` at a nonzero playhead, track count stayed 2 and the same audio track had 2 clips (`clipimport`, `targetsem`); no duplicate track was created.
- After visibly selecting the vocal track and importing `vocaltarget.wav`, a new `Audio — vocaltarget` audio track was created with 1 clip; the vocal track still had 0 clips.
- Final arrangement/layout at 1272x837 showed the two clips on the existing audio track and the separate new audio-track clip clearly.
- No console errors or network failures.

Evidence: `target_semantics.png`, `target_semantics_audio_track.png`, `clip_target_semantics_results.json`.
